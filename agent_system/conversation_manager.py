"""
ConversationManager - Gestão de conversas persistentes em DB

Substitui o dict in-memory por persistência real.
Mantém histórico completo, restaura estado entre sessões.
Detecta tópicos, emoções, e gera memórias automaticamente.
"""

from sqlalchemy.orm import Session
from data.schema_cognitive import (
    ConversationSession, ConversationMessage, Agent, Memory, MemoryType
)
from agent_system.memory_manager_cognitive import MemoryManager
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from uuid import uuid4
import json
import re
import logging

logger = logging.getLogger(__name__)


class ConversationManager:
    """Gere conversas persistentes entre agente e utilizador"""

    def __init__(self, db: Session, agent_id: str):
        self.db = db
        self.agent_id = agent_id

    # ================================================================
    # SESSION MANAGEMENT
    # ================================================================

    def get_or_create_session(
        self,
        conversation_id: Optional[str] = None,
        user_id: str = "default_user"
    ) -> ConversationSession:
        """Obtém sessão existente ou cria nova"""

        if conversation_id:
            session = self.db.query(ConversationSession).filter(
                ConversationSession.id == conversation_id,
                ConversationSession.agent_id == self.agent_id
            ).first()

            if session:
                return session

        # Tentar encontrar sessão activa recente com este user
        recent = self.db.query(ConversationSession).filter(
            ConversationSession.agent_id == self.agent_id,
            ConversationSession.user_id == user_id,
            ConversationSession.is_active == True
        ).order_by(ConversationSession.started_at.desc()).first()

        # Se existe sessão activa das últimas 2 horas, reutilizar
        if recent and recent.started_at:
            age = (datetime.utcnow() - recent.started_at).total_seconds()
            if age < 7200:  # 2 horas
                return recent

        # Fechar sessões antigas
        if recent:
            recent.is_active = False
            recent.ended_at = datetime.utcnow()

        # Criar nova sessão
        session_id = conversation_id or str(uuid4())
        session = ConversationSession(
            id=session_id,
            agent_id=self.agent_id,
            user_id=user_id,
            is_active=True,
            started_at=datetime.utcnow(),
            message_count=0
        )
        self.db.add(session)
        self.db.commit()

        logger.debug(f"[session] nova: {session_id} agente={self.agent_id}")
        return session

    def add_message(
        self,
        session: ConversationSession,
        role: str,
        content: str,
        detected_emotion: Optional[str] = None,
        detected_intent: Optional[str] = None,
        importance: float = 0.5
    ) -> ConversationMessage:
        """Adiciona mensagem à sessão"""

        message = ConversationMessage(
            session_id=session.id,
            role=role,
            content=content,
            detected_emotion=detected_emotion,
            detected_intent=detected_intent,
            importance=importance,
            created_at=datetime.utcnow()
        )

        self.db.add(message)

        # Actualizar sessão
        session.message_count = (session.message_count or 0) + 1

        # Actualizar working memory (últimas 20 mensagens)
        working = session.working_memory or []
        working.append({
            "role": role,
            "content": content[:500],  # Limitar tamanho
            "timestamp": datetime.utcnow().isoformat(),
            "emotion": detected_emotion
        })
        session.working_memory = working[-20:]

        self.db.commit()
        return message

    def get_conversation_history(
        self,
        session_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Obtém histórico de mensagens de uma sessão"""

        messages = self.db.query(ConversationMessage).filter(
            ConversationMessage.session_id == session_id
        ).order_by(ConversationMessage.created_at.asc()).limit(limit).all()

        return [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.created_at.isoformat() if msg.created_at else None,
                "emotion": msg.detected_emotion,
                "intent": msg.detected_intent
            }
            for msg in messages
        ]

    def get_recent_context(
        self,
        session: ConversationSession,
        n_messages: int = 10
    ) -> List[Dict[str, str]]:
        """Obtém últimas N mensagens para contexto do LLM"""

        messages = self.db.query(ConversationMessage).filter(
            ConversationMessage.session_id == session.id
        ).order_by(ConversationMessage.created_at.desc()).limit(n_messages).all()

        # Inverter para ordem cronológica
        messages.reverse()

        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

    def get_all_sessions(
        self,
        user_id: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Lista sessões de conversa"""

        query = self.db.query(ConversationSession).filter(
            ConversationSession.agent_id == self.agent_id
        )

        if user_id:
            query = query.filter(ConversationSession.user_id == user_id)

        sessions = query.order_by(
            ConversationSession.started_at.desc()
        ).limit(limit).all()

        return [
            {
                "id": s.id,
                "user_id": s.user_id,
                "is_active": s.is_active,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "ended_at": s.ended_at.isoformat() if s.ended_at else None,
                "message_count": s.message_count or 0,
                "current_topic": s.current_topic,
                "emotional_tone": s.emotional_tone,
                "summary": s.summary
            }
            for s in sessions
        ]

    def close_session(self, session_id: str, summary: str = ""):
        """Fecha uma sessão de conversa"""

        session = self.db.query(ConversationSession).filter(
            ConversationSession.id == session_id
        ).first()

        if session:
            session.is_active = False
            session.ended_at = datetime.utcnow()
            if summary:
                session.summary = summary
            self.db.commit()

    # ================================================================
    # CONTEXT BUILDING
    # ================================================================

    def build_conversation_context(
        self,
        session: ConversationSession,
        include_previous_sessions: bool = True
    ) -> Dict[str, Any]:
        """
        Constrói contexto completo da conversa para o LLM.
        Inclui: mensagens recentes, resumos de sessões anteriores, tópicos.
        """

        context = {
            "current_messages": self.get_recent_context(session, n_messages=15),
            "current_topic": session.current_topic,
            "emotional_tone": session.emotional_tone,
            "message_count": session.message_count or 0,
            "session_duration": None,
        }

        if session.started_at:
            duration = (datetime.utcnow() - session.started_at).total_seconds()
            context["session_duration"] = int(duration)

        # Incluir resumos de sessões anteriores para continuidade
        if include_previous_sessions:
            previous = self.db.query(ConversationSession).filter(
                ConversationSession.agent_id == self.agent_id,
                ConversationSession.user_id == session.user_id,
                ConversationSession.id != session.id,
                ConversationSession.is_active == False
            ).order_by(ConversationSession.ended_at.desc()).limit(3).all()

            summaries = []
            for prev in previous:
                if prev.summary:
                    summaries.append({
                        "date": prev.ended_at.isoformat() if prev.ended_at else "?",
                        "summary": prev.summary,
                        "topic": prev.current_topic,
                        "tone": prev.emotional_tone,
                        "messages": prev.message_count or 0
                    })

            context["previous_sessions"] = summaries

        return context

    def update_session_metadata(
        self,
        session: ConversationSession,
        topic: Optional[str] = None,
        emotional_tone: Optional[str] = None,
        key_point: Optional[str] = None,
        unresolved: Optional[str] = None
    ):
        """Actualiza metadata da sessão"""

        if topic:
            session.current_topic = topic

        if emotional_tone:
            session.emotional_tone = emotional_tone

        if key_point:
            points = session.key_points or []
            points.append(key_point)
            session.key_points = points[-10:]

        if unresolved:
            questions = session.unresolved_questions or []
            questions.append(unresolved)
            session.unresolved_questions = questions[-5:]

        self.db.commit()

    # ================================================================
    # AUTO-MEMORY GENERATION
    # ================================================================

    def generate_session_memories(
        self,
        session: ConversationSession,
        memory_manager: MemoryManager
    ) -> List[str]:
        """
        Gera memórias automaticamente a partir de uma sessão.
        Chamado quando a sessão fecha ou periodicamente.
        Retorna IDs das memórias criadas.
        """

        if not session.message_count or session.message_count < 4:
            return []

        memory_ids = []

        # 1. Criar memória episódica da conversa
        messages = self.get_conversation_history(session.id, limit=100)
        user_messages = [m for m in messages if m["role"] == "user"]
        topics = self._extract_topics(user_messages)

        if topics:
            try:
                summary = self._summarize_conversation(messages)
                mem = memory_manager.create_memory(
                    title=f"Conversa sobre {', '.join(topics[:3])}",
                    content=summary,
                    memory_type="episodic",
                    importance_score=min(0.8, 0.3 + session.message_count * 0.02),
                    emotional_valence=self._estimate_valence(messages),
                    relates_to_topics=topics
                )
                memory_ids.append(mem.id)
            except Exception as e:
                logger.warning(f"Erro ao criar memória episódica: {e}")

        # 2. Criar memória relacional se houve informação pessoal
        personal_info = self._extract_personal_info(user_messages)
        if personal_info:
            try:
                mem = memory_manager.create_memory(
                    title=f"Sobre {session.user_id}: {personal_info[:50]}",
                    content=personal_info,
                    memory_type="relational",
                    importance_score=0.7,
                    emotional_valence=0.2,
                    relates_to_topics=["user_info", session.user_id or "unknown"]
                )
                memory_ids.append(mem.id)
            except Exception as e:
                logger.warning(f"Erro ao criar memória relacional: {e}")

        # Actualizar sumário da sessão
        if not session.summary and messages:
            session.summary = self._summarize_conversation(messages)
            self.db.commit()

        return memory_ids

    def _extract_topics(self, messages: List[Dict]) -> List[str]:
        """Extrai tópicos das mensagens"""

        all_text = " ".join(m.get("content", "") for m in messages).lower()

        # Palavras significativas (> 5 chars, não stopwords)
        stopwords = {
            "sobre", "como", "quando", "porque", "onde", "quero", "posso",
            "tenho", "estou", "estava", "seria", "poderia", "muito", "pouco",
            "também", "ainda", "depois", "antes", "entre", "outro", "outra",
            "algum", "alguma", "todos", "todas", "nenhum", "nenhuma",
            "aquilo", "isso", "isto", "estes", "estas", "esses", "essas",
            "minha", "minha", "nosso", "nossa", "vosso", "vossa",
            "fazer", "dizer", "saber", "poder", "querer", "achar",
        }

        words = re.findall(r'\b[a-záàâãéèêíìîóòôõúùûç]{5,}\b', all_text)
        word_freq = {}
        for w in words:
            if w not in stopwords:
                word_freq[w] = word_freq.get(w, 0) + 1

        # Top 5 palavras mais frequentes
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        return [w[0] for w in sorted_words[:5]]

    def _summarize_conversation(self, messages: List[Dict]) -> str:
        """Gera resumo simples da conversa"""

        user_msgs = [m["content"][:100] for m in messages if m["role"] == "user"]
        agent_msgs = [m["content"][:100] for m in messages if m["role"] == "assistant"]

        summary_parts = []

        if user_msgs:
            summary_parts.append(f"O utilizador falou sobre: {'; '.join(user_msgs[:3])}")

        if agent_msgs:
            summary_parts.append(f"Eu respondi sobre: {'; '.join(agent_msgs[:2])}")

        summary_parts.append(f"Total de {len(messages)} mensagens.")

        return " ".join(summary_parts)

    def _extract_personal_info(self, messages: List[Dict]) -> str:
        """Extrai informação pessoal partilhada pelo utilizador"""

        personal_patterns = [
            r"(?:eu sou|sou|trabalho como|moro em|vivo em|tenho \d+|chamo.me)\s+(.+?)[\.\,\!]",
            r"(?:meu nome|me chamo|gosto de|prefiro|detesto|adoro)\s+(.+?)[\.\,\!]",
            r"(?:a minha|o meu|na minha)\s+(.+?)[\.\,\!]",
        ]

        info_parts = []
        for msg in messages:
            text = msg.get("content", "")
            for pattern in personal_patterns:
                matches = re.findall(pattern, text.lower())
                info_parts.extend(matches)

        if info_parts:
            return "Informação partilhada: " + "; ".join(set(info_parts[:5]))

        return ""

    def _estimate_valence(self, messages: List[Dict]) -> float:
        """Estima valência emocional da conversa"""

        positive = ["obrigado", "gosto", "adoro", "excelente", "ótimo", "bom", "fixe", "incrível", "fantástico"]
        negative = ["mau", "péssimo", "odeio", "horrível", "triste", "raiva", "frustrado", "chateado"]

        text = " ".join(m.get("content", "") for m in messages).lower()

        pos = sum(1 for w in positive if w in text)
        neg = sum(1 for w in negative if w in text)

        if pos + neg == 0:
            return 0.0

        return (pos - neg) / (pos + neg)

    # ================================================================
    # LAST STATE RESTORATION
    # ================================================================

    def get_last_session_state(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtém o estado da última sessão com este utilizador.
        Usado para restaurar contexto quando uma nova conversa começa.
        """

        last_session = self.db.query(ConversationSession).filter(
            ConversationSession.agent_id == self.agent_id,
            ConversationSession.user_id == user_id,
            ConversationSession.is_active == False
        ).order_by(ConversationSession.ended_at.desc()).first()

        if not last_session:
            return None

        return {
            "session_id": last_session.id,
            "ended_at": last_session.ended_at.isoformat() if last_session.ended_at else None,
            "summary": last_session.summary,
            "topic": last_session.current_topic,
            "emotional_tone": last_session.emotional_tone,
            "key_points": last_session.key_points or [],
            "unresolved": last_session.unresolved_questions or [],
            "message_count": last_session.message_count or 0
        }
