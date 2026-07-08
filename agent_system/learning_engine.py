"""
Learning Engine - Motor de aprendizagem baseado em feedback
Permite que agentes aprendam e evoluam com cada interação
"""

from sqlalchemy.orm import Session
from data.schema_cognitive import (
    Agent, Memory, MemoryType, LearningEvent,
)
from agent_system.memory_manager_cognitive import MemoryManager
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
import logging

logger = logging.getLogger(__name__)


class LearningEngine:
    """
    Motor de aprendizagem que:
    1. Processa feedback do utilizador
    2. Reforça/enfraquece conexões baseado em sucesso
    3. Consolida memórias importantes
    4. Adapta comportamento ao longo do tempo
    """
    
    def __init__(self, db: Session, agent_id: str):
        self.db = db
        self.agent_id = agent_id
        self.memory_manager = MemoryManager(db, agent_id)
    
    def record_interaction(
        self,
        query: str,
        response: str,
        user_id: Optional[str] = None,
        context: Optional[Dict] = None
    ) -> str:
        """
        Regista uma interação para posterior aprendizagem.
        Retorna o ID da interação para associar feedback.
        """
        
        event = LearningEvent(
            agent_id=self.agent_id,
            user_id=user_id,
            query=query,
            response=response,
            feedback_type=None,  # Será preenchido com feedback
            feedback_score=None
        )
        
        self.db.add(event)
        self.db.commit()
        
        logger.debug(f"[learning] interação registada: {event.id}")
        return event.id
    
    def process_feedback(
        self,
        interaction_id: str,
        feedback_type: str,  # positive, negative, correction, clarification
        feedback_score: float = 0.0,  # -1 a +1
        feedback_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Processa feedback do utilizador e aprende com ele.
        """
        
        event = self.db.query(LearningEvent).filter(
            LearningEvent.id == interaction_id
        ).first()
        
        if not event:
            logger.warning(f"[learning] interação {interaction_id} não encontrada")
            return {"success": False, "reason": "Interação não encontrada"}
        
        # Atualizar evento com feedback
        event.feedback_type = feedback_type
        event.feedback_score = feedback_score
        event.feedback_text = feedback_text
        
        # Processar aprendizagem
        lessons = []
        
        if feedback_type == "positive":
            lessons = self._learn_from_success(event)
        elif feedback_type == "negative":
            lessons = self._learn_from_failure(event)
        elif feedback_type == "correction":
            lessons = self._learn_from_correction(event, feedback_text)
        elif feedback_type == "clarification":
            lessons = self._learn_from_clarification(event, feedback_text)
        
        # Registar lição aprendida
        if lessons:
            event.lesson_learned = "; ".join(lessons)
        
        self.db.commit()
        
        return {
            "success": True,
            "lessons_learned": lessons,
            "feedback_processed": feedback_type
        }
    
    def _learn_from_success(self, event: LearningEvent) -> List[str]:
        """Aprende com interação bem-sucedida"""

        lessons = []

        self.memory_manager.create_memory(
            title=f"Interação bem-sucedida",
            content=f"Query: {event.query}\nResposta bem recebida: {event.response[:200]}...",
            memory_type="episodic",
            importance_score=0.7,
            emotional_valence=0.6
        )
        lessons.append("Memória positiva criada")

        return lessons
    
    def _learn_from_failure(self, event: LearningEvent) -> List[str]:
        """Aprende com interação que não correu bem"""

        lessons = []

        self.memory_manager.create_memory(
            title=f"Aprendizagem: Melhorar resposta",
            content=f"Query: {event.query}\nResposta que não funcionou bem. Preciso melhorar abordagem neste tipo de questão.",
            memory_type="semantic",
            importance_score=0.8,
            emotional_valence=-0.2
        )
        lessons.append("Memória de aprendizagem criada")

        return lessons
    
    def _learn_from_correction(
        self,
        event: LearningEvent,
        correction: Optional[str]
    ) -> List[str]:
        """Aprende com correção do utilizador"""
        
        lessons = []
        
        if not correction:
            return lessons
        
        # 1. Criar memória da correção
        self.memory_manager.create_memory(
            title=f"Correção importante",
            content=f"Quando perguntado sobre: {event.query}\n"
                   f"Eu respondi: {event.response[:100]}...\n"
                   f"Mas a resposta correta é: {correction}",
            memory_type="semantic",
            importance_score=0.9,  # Muito importante
            emotional_valence=0.0,
            relates_to_topics=["correção", "aprendizagem"]
        )
        lessons.append("Correção memorizada")
        
        return lessons
    
    def _learn_from_clarification(
        self,
        event: LearningEvent,
        clarification: Optional[str]
    ) -> List[str]:
        """Aprende com clarificação do utilizador"""
        
        lessons = []
        
        if not clarification:
            return lessons
        
        # Criar memória de clarificação
        self.memory_manager.create_memory(
            title=f"Clarificação recebida",
            content=f"Sobre: {event.query}\n"
                   f"Clarificação: {clarification}",
            memory_type="semantic",
            importance_score=0.7,
            emotional_valence=0.3,
            relates_to_topics=["clarificação"]
        )
        lessons.append("Clarificação memorizada")
        
        return lessons
    
    def consolidate_memories(self, days_old: int = 1) -> Dict[str, Any]:
        """
        Consolida memórias recentes em conhecimento de longo prazo.
        Deve ser executado periodicamente (ex: diariamente).
        """
        
        cutoff = datetime.utcnow() - timedelta(days=days_old)
        
        # Buscar memórias recentes de alta importância
        recent_memories = self.db.query(Memory).filter(
            Memory.agent_id == self.agent_id,
            Memory.created_at >= cutoff,
            Memory.importance_score >= 0.7
        ).all()
        
        consolidated = 0
        
        for memory in recent_memories:
            # Verificar se já foi acedida múltiplas vezes
            if memory.access_count >= 3:
                # Aumentar importância (consolidação)
                memory.importance_score = min(1.0, memory.importance_score + 0.1)
                consolidated += 1
        
        self.db.commit()
        
        return {
            "memories_reviewed": len(recent_memories),
            "memories_consolidated": consolidated
        }
    
    def decay_unused_memories(self, days_inactive: int = 30) -> Dict[str, Any]:
        """
        Aplica decaimento a memórias não acedidas.
        Simula "esquecimento" natural.
        """
        
        cutoff = datetime.utcnow() - timedelta(days=days_inactive)
        
        # Memórias não acedidas há muito tempo
        old_memories = self.db.query(Memory).filter(
            Memory.agent_id == self.agent_id,
            Memory.last_accessed < cutoff,
            Memory.importance_score < 0.9  # Não afetar memórias muito importantes
        ).all()
        
        decayed = 0
        
        for memory in old_memories:
            # Diminuir importância gradualmente
            memory.importance_score = max(0.1, memory.importance_score - 0.05)
            decayed += 1
        
        self.db.commit()
        
        return {
            "memories_reviewed": len(old_memories),
            "memories_decayed": decayed
        }
    
    def get_learning_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas de aprendizagem"""
        
        # Contar eventos de aprendizagem
        total_events = self.db.query(LearningEvent).filter(
            LearningEvent.agent_id == self.agent_id
        ).count()
        
        positive = self.db.query(LearningEvent).filter(
            LearningEvent.agent_id == self.agent_id,
            LearningEvent.feedback_type == "positive"
        ).count()
        
        negative = self.db.query(LearningEvent).filter(
            LearningEvent.agent_id == self.agent_id,
            LearningEvent.feedback_type == "negative"
        ).count()
        
        return {
            "total_interactions": total_events,
            "positive_feedback": positive,
            "negative_feedback": negative,
            "success_rate": positive / max(1, positive + negative),
            "learning_health": "good" if positive > negative else "needs_improvement"
        }


def get_learning_engine(db: Session, agent_id: str) -> LearningEngine:
    """Factory function para criar LearningEngine"""
    return LearningEngine(db, agent_id)
