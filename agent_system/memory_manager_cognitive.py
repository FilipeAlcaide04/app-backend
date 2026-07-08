"""
Memory Manager - Sistema completo de gestão de memórias persistentes
Suporta múltiplos tipos de memória, busca semântica, decaimento temporal
"""

from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from data.schema_cognitive import (
    Memory, MemoryType, MemoryEmbedding, Agent, ThoughtProcess
)
from llm_logic.embedding_generator import EmbeddingGenerator
from agent_system.prompt_manager import PromptManager
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import json
from enum import Enum
import logging
import re

logger = logging.getLogger(__name__)


class MemoryTypeEnum(str, Enum):
    """Tipos padrão de memória"""
    AUTOBIOGRAPHICAL = "autobiographical"  # Sobre a vida do agente
    SEMANTIC = "semantic"  # Fatos e conhecimento geral
    PROCEDURAL = "procedural"  # Como fazer coisas
    EMOTIONAL = "emotional"  # Memórias com forte carga emocional
    EPISODIC = "episodic"  # Eventos específicos
    RELATIONAL = "relational"  # Sobre relacionamentos com outros agentes
    SHORT_TERM = "short_term"  # Conversas recentes
    LONG_TERM = "long_term"  # Memórias persistentes
    TRAUMATIC = "traumatic"  # Memórias difíceis (podem estar bloqueadas)
    ASPIRATIONAL = "aspirational"  # Objetivos e sonhos


class MemoryManager:
    """Gerencia memórias de um agente"""
    
    def __init__(self, db: Session, agent_id: str):
        self.db = db
        self.agent_id = agent_id
        self.embedding_generator = EmbeddingGenerator()
        self.prompts = PromptManager(db)
        self._verify_agent_exists()
        self._ensure_memory_types()
    
    def _verify_agent_exists(self):
        """Verifica se agente existe"""
        agent = self.db.query(Agent).filter(Agent.id == self.agent_id).first()
        if not agent:
            raise ValueError(f"Agente {self.agent_id} não existe")
    
    def _ensure_memory_types(self):
        """Cria tipos de memória padrão se não existirem"""
        default_types = [
            {
                "name": MemoryTypeEnum.AUTOBIOGRAPHICAL,
                "description": "Memórias sobre a vida e história pessoal do agente",
                "temporal_scope": "long_term",
                "decay_rate": 0.01,
            },
            {
                "name": MemoryTypeEnum.SEMANTIC,
                "description": "Conhecimento factual e geral",
                "temporal_scope": "long_term",
                "decay_rate": 0.001,
            },
            {
                "name": MemoryTypeEnum.PROCEDURAL,
                "description": "Habilidades e conhecimento de como fazer",
                "temporal_scope": "long_term",
                "decay_rate": 0.001,
            },
            {
                "name": MemoryTypeEnum.EMOTIONAL,
                "description": "Memórias com carga emocional significativa",
                "temporal_scope": "long_term",
                "decay_rate": 0.05,
            },
            {
                "name": MemoryTypeEnum.EPISODIC,
                "description": "Eventos específicos e datas",
                "temporal_scope": "long_term",
                "decay_rate": 0.02,
            },
            {
                "name": MemoryTypeEnum.RELATIONAL,
                "description": "Memórias sobre relacionamentos com outros agentes",
                "temporal_scope": "long_term",
                "decay_rate": 0.01,
            },
            {
                "name": MemoryTypeEnum.SHORT_TERM,
                "description": "Informações recentes de conversas",
                "temporal_scope": "short_term",
                "decay_rate": 0.5,
            },
            {
                "name": MemoryTypeEnum.TRAUMATIC,
                "description": "Memórias de eventos traumáticos",
                "temporal_scope": "long_term",
                "decay_rate": 0.02,
            },
            {
                "name": MemoryTypeEnum.ASPIRATIONAL,
                "description": "Objetivos, sonhos e aspirações",
                "temporal_scope": "long_term",
                "decay_rate": 0.01,
            },
        ]
        
        for mem_type_data in default_types:
            existing = self.db.query(MemoryType).filter(
                MemoryType.name == mem_type_data["name"]
            ).first()
            
            if not existing:
                mem_type = MemoryType(**mem_type_data)
                self.db.add(mem_type)
        
        self.db.commit()
    
    def create_memory(
        self,
        title: str,
        content: str,
        memory_type: str = MemoryTypeEnum.SEMANTIC,
        emotional_valence: float = 0.0,
        importance_score: float = 0.5,
        occurred_at: Optional[datetime] = None,
        is_autobiographical: bool = True,
        is_episodic: bool = False,
        relates_to_agent_ids: Optional[Dict[str, str]] = None,
        relates_to_topics: Optional[List[str]] = None,
    ) -> Memory:
        """Cria nova memória"""
        
        # Busca tipo de memória
        mem_type = self.db.query(MemoryType).filter(
            MemoryType.name == memory_type
        ).first()
        
        if not mem_type:
            raise ValueError(f"Tipo de memória {memory_type} não existe")

        # Validar emotional_valence e importance_score antes de criar ou consolidar
        emotional_valence = max(-1.0, min(1.0, float(emotional_valence)))
        importance_score = max(0.0, min(1.0, float(importance_score)))

        normalized_content = re.sub(r"\s+", " ", (content or "").strip().lower())

        # Evitar duplicados pelo conteúdo estável, mesmo que venham de caminhos diferentes.
        existing = self.db.query(Memory).filter(
            Memory.agent_id == self.agent_id,
            func.lower(func.regexp_replace(Memory.content, r"\s+", " ", "g")) == normalized_content,
            Memory.is_blocked == False,
        ).first()

        # Semantic dedup for all memory types — catches near-duplicates with different wording
        if not existing:
            try:
                new_embedding = self.embedding_generator.generate_embedding(content)
                candidates = self.db.query(Memory).filter(
                    Memory.agent_id == self.agent_id,
                    Memory.type_id == mem_type.id,
                    Memory.is_blocked == False,
                    Memory.created_at >= datetime.utcnow() - timedelta(days=30),
                ).limit(50).all()
                for cand in candidates:
                    if cand.embeddings:
                        sim = self._cosine_similarity(new_embedding, cand.embeddings[0].embedding)
                        if sim > 0.82:
                            existing = cand
                            break
            except Exception as e:
                logger.debug(f"Semantic dedup failed: {e}")
        if existing:
            existing.last_accessed = datetime.utcnow()
            existing.access_count = (existing.access_count or 0) + 1
            existing.importance_score = max(float(existing.importance_score or 0), importance_score)

            existing_valence = float(existing.emotional_valence or 0)
            if (
                abs(float(emotional_valence or 0)) > abs(existing_valence)
                or (
                    abs(float(emotional_valence or 0)) == abs(existing_valence)
                    and float(emotional_valence or 0) < existing_valence
                )
            ):
                existing.emotional_valence = emotional_valence

            existing.relates_to_topics = sorted(set(
                [str(t) for t in (existing.relates_to_topics or [])]
                + [str(t) for t in (relates_to_topics or [])]
            ))
            existing.relates_to_agent_ids = {
                **(existing.relates_to_agent_ids or {}),
                **(relates_to_agent_ids or {}),
            }
            existing.is_autobiographical = bool(existing.is_autobiographical or is_autobiographical)
            existing.is_episodic = bool(existing.is_episodic or is_episodic)

            if not existing.embeddings:
                try:
                    embedding_vector = self.embedding_generator.generate_embedding(existing.content)
                    self.db.add(MemoryEmbedding(
                        memory_id=existing.id,
                        embedding=embedding_vector,
                    ))
                except Exception as e:
                    logger.error(f"Erro ao gerar embedding para memória existente: {e}")

            self.db.commit()
            self.db.refresh(existing)
            return existing
        # Criar memória
        memory = Memory(
            agent_id=self.agent_id,
            type_id=mem_type.id,
            title=title,
            content=content,
            emotional_valence=emotional_valence,
            importance_score=importance_score,
            occurred_at=occurred_at or datetime.utcnow(),
            is_autobiographical=is_autobiographical,
            is_episodic=is_episodic,
            relates_to_agent_ids=relates_to_agent_ids or {},
            relates_to_topics=relates_to_topics or [],
        )
        
        self.db.add(memory)
        self.db.flush()  # Flush para ter ID antes de gerar embedding
        
        # Gerar embedding
        try:
            embedding_vector = self.embedding_generator.generate_embedding(content)
            embedding = MemoryEmbedding(
                memory_id=memory.id,
                embedding=embedding_vector,
            )
            self.db.add(embedding)
        except Exception as e:
            logger.error(f"Erro ao gerar embedding para memória: {e}")
        
        self.db.commit()
        self.db.refresh(memory)
        
        return memory
    
    def get_memories_by_type(self, memory_type: str) -> List[Memory]:
        """Busca memórias de um tipo específico"""
        mem_type = self.db.query(MemoryType).filter(
            MemoryType.name == memory_type
        ).first()
        
        if not mem_type:
            return []
        
        return self.db.query(Memory).filter(
            Memory.agent_id == self.agent_id,
            Memory.type_id == mem_type.id,
            Memory.is_blocked == False
        ).order_by(Memory.importance_score.desc()).all()
    
    def search_memories_semantic(
        self,
        query: str,
        top_k: int = 5,
        memory_types: Optional[List[str]] = None,
        min_similarity: float = 0.22,
    ) -> List[Memory]:
        """Busca memórias por similaridade semântica"""
        
        try:
            # Gerar embedding da query
            query_embedding = self.embedding_generator.generate_embedding(query)
            
            # Construir query base
            base_query = self.db.query(Memory).filter(
                Memory.agent_id == self.agent_id,
                Memory.is_blocked == False
            )
            
            # Filtrar por tipos se fornecidos
            if memory_types:
                type_objs = self.db.query(MemoryType).filter(
                    MemoryType.name.in_(memory_types)
                ).all()
                type_ids = [t.id for t in type_objs]
                base_query = base_query.filter(Memory.type_id.in_(type_ids))
            
            # Buscar memórias com embeddings
            memories = base_query.all()
            
            # Calcular similaridade cosina
            similarities = []
            for memory in memories:
                if memory.embeddings:
                    embedding = memory.embeddings[0]
                    similarity = self._cosine_similarity(
                        query_embedding,
                        embedding.embedding
                    )
                    if similarity >= min_similarity:
                        similarities.append((memory, similarity))
            
            # Ordenar por similaridade e retornar top_k
            similarities.sort(key=lambda x: x[1], reverse=True)
            return [m[0] for m in similarities[:top_k]]
        
        except Exception as e:
            logger.error(f"Erro na busca semântica de memórias: {e}")
            return []
    
    def update_memory(
        self,
        memory_id: str,
        title: Optional[str] = None,
        content: Optional[str] = None,
        importance_score: Optional[float] = None,
        emotional_valence: Optional[float] = None,
    ) -> Memory:
        """Atualiza memória existente"""
        
        memory = self.db.query(Memory).filter(
            Memory.id == memory_id,
            Memory.agent_id == self.agent_id
        ).first()
        
        if not memory:
            raise ValueError(f"Memória {memory_id} não encontrada")
        
        if title is not None:
            memory.title = title
        if content is not None:
            memory.content = content
            # Regenerar embedding se conteúdo mudou
            try:
                embedding_vector = self.embedding_generator.generate_embedding(content)
                if memory.embeddings:
                    memory.embeddings[0].embedding = embedding_vector
                else:
                    embedding = MemoryEmbedding(
                        memory_id=memory.id,
                        embedding=embedding_vector,
                    )
                    self.db.add(embedding)
            except Exception as e:
                logger.error(f"Erro ao regenerar embedding: {e}")
        
        if importance_score is not None:
            memory.importance_score = max(0.0, min(1.0, float(importance_score)))
        
        if emotional_valence is not None:
            memory.emotional_valence = max(-1.0, min(1.0, float(emotional_valence)))
        
        memory.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(memory)
        
        return memory
    
    def delete_memory(self, memory_id: str) -> bool:
        """Deleta memória (soft delete com is_blocked)"""
        
        memory = self.db.query(Memory).filter(
            Memory.id == memory_id,
            Memory.agent_id == self.agent_id
        ).first()
        
        if not memory:
            return False
        
        memory.is_blocked = True
        memory.updated_at = datetime.utcnow()
        self.db.commit()
        
        return True
    
    def should_store_memory(self, title: str, content: str, memory_type: str = "relational") -> bool:
        """
        AI gate: decides whether a candidate memory should be stored,
        comparing against similar existing memories via embeddings + LLM.
        """
        try:
            new_embedding = self.embedding_generator.generate_embedding(content)

            existing = self.db.query(Memory).filter(
                Memory.agent_id == self.agent_id,
                Memory.is_blocked == False,
            ).order_by(Memory.created_at.desc()).limit(100).all()

            similar = []
            for mem in existing:
                if mem.embeddings:
                    sim = self._cosine_similarity(new_embedding, mem.embeddings[0].embedding)
                    if sim > 0.5:
                        similar.append((sim, mem))

            similar.sort(key=lambda x: -x[0])
            top_similar = similar[:5]

            if not top_similar:
                return True

            # Very high similarity = obvious duplicate, skip LLM call
            if top_similar[0][0] > 0.92:
                logger.info(f"[MEMORY GATE] Auto-rejected (sim={top_similar[0][0]:.2f}): '{title[:50]}'")
                return False

            existing_list = "\n".join(
                f"- (sim={sim:.2f}) {m.title}: {(m.content or '')[:150]}"
                for sim, m in top_similar
            )

            from llm_logic.llm_client import get_llm_client
            prompt = (
                f"New memory candidate:\n"
                f"Title: {title}\nContent: {content[:250]}\nType: {memory_type}\n\n"
                f"Similar existing memories:\n{existing_list}\n\n"
                f"Should the new memory be stored? Answer ONLY with JSON: {{\"store\": true/false, \"reason\": \"short\"}}\n\n"
                f"Store = false if:\n"
                f"- Same fact already exists (even if worded differently)\n"
                f"- Content is trivial, vague, or adds nothing specific\n"
                f"- It's a generic observation like 'the conversation went well'\n\n"
                f"Store = true if:\n"
                f"- It contains a specific new fact, name, preference, or experience\n"
                f"- It updates or corrects an existing memory with new information\n"
                f"- It captures something emotionally significant not yet recorded"
            )

            raw = get_llm_client().generate(prompt, max_tokens=80, temperature=0.1).strip()
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                start = raw.find("{")
                end = raw.rfind("}")
                parsed = json.loads(raw[start:end + 1]) if start >= 0 and end > start else {}

            should_store = parsed.get("store", True)
            reason = parsed.get("reason", "")
            if not should_store:
                logger.info(f"[MEMORY GATE] Rejected: '{title[:50]}' — {reason}")
            return bool(should_store)

        except Exception as e:
            logger.debug(f"[MEMORY GATE] Error, storing as fallback: {e}")
            return True

    def get_recent_memories(self, days: int = 7, limit: int = 20) -> List[Memory]:
        """Obtém memórias recentes"""
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        return self.db.query(Memory).filter(
            Memory.agent_id == self.agent_id,
            Memory.created_at >= cutoff,
            Memory.is_blocked == False
        ).order_by(Memory.created_at.desc()).limit(limit).all()
    
    def get_important_memories(self, limit: int = 20) -> List[Memory]:
        """Obtém memórias mais importantes"""
        return self.db.query(Memory).filter(
            Memory.agent_id == self.agent_id,
            Memory.is_blocked == False
        ).order_by(
            Memory.importance_score.desc(),
            Memory.access_count.desc()
        ).limit(limit).all()
    
    def update_memory_access(self, memory_id: str):
        """Atualiza statisticas quando memória é acessada"""
        memory = self.db.query(Memory).filter(
            Memory.id == memory_id,
            Memory.agent_id == self.agent_id
        ).first()
        
        if memory:
            memory.access_count += 1
            memory.last_accessed = datetime.utcnow()
            # Aumentar relevance score ligeiramente com cada acesso
            memory.relevance_score = min(1.0, memory.relevance_score + 0.01)
            self.db.commit()
    
    def get_memory_context(self, limit_per_type: int = 3) -> Dict[str, List[Memory]]:
        """Obtém contexto de memórias importante para decisão"""
        context = {}
        
        memory_types = [
            MemoryTypeEnum.AUTOBIOGRAPHICAL,
            MemoryTypeEnum.EMOTIONAL,
            MemoryTypeEnum.RELATIONAL,
            MemoryTypeEnum.ASPIRATIONAL,
        ]
        
        for mem_type in memory_types:
            memories = self.get_memories_by_type(mem_type)
            context[mem_type] = memories[:limit_per_type]
        
        return context
    
    def recall_relevant_memories(
        self,
        topic: str,
        limit: int = 5,
        min_similarity: float = 0.22,
        include_learning: bool = False,
    ) -> List[Memory]:
        """Recupera memórias relevantes para um tópico"""
        # Primeiro tenta busca semântica
        semantic_matches = self.search_memories_semantic(
            topic,
            top_k=max(limit * 3, 15),
            min_similarity=min_similarity,
        )

        if not include_learning:
            semantic_matches = [
                m for m in semantic_matches
                if not self._is_noisy_learning_memory(m)
            ]

        if semantic_matches:
            return semantic_matches[:limit]

        # Fallback textual para evitar memórias aleatórias por importância
        words = [w for w in re.findall(r"\w+", (topic or "").lower()) if len(w) >= 4][:6]
        base_query = self.db.query(Memory).filter(
            Memory.agent_id == self.agent_id,
            Memory.is_blocked == False
        )

        if not include_learning:
            base_query = base_query.filter(
                ~func.lower(Memory.title).like("aprendizado:%")
            )

        if words:
            text_filters = []
            for w in words:
                pattern = f"%{w}%"
                text_filters.append(func.lower(Memory.title).like(pattern))
                text_filters.append(func.lower(Memory.content).like(pattern))
            text_matches = base_query.filter(or_(*text_filters)).order_by(
                Memory.importance_score.desc(),
                Memory.created_at.desc(),
            ).limit(limit * 5).all()
            if not include_learning:
                text_matches = [
                    m for m in text_matches
                    if not self._is_noisy_learning_memory(m)
                ]
            text_matches = text_matches[:limit]
            if text_matches:
                return text_matches

        return []

    def build_memory_awareness(
        self,
        query: str,
        conversation_context: str = "",
        max_memories: int = 24,
    ) -> Dict[str, object]:
        """
        Builds layered memory awareness with priority:
        Layer 1 (IDENTITY): Name, core facts, user identity — always included
        Layer 2 (RELATIONSHIP): Feelings, preferences, history with this person
        Layer 3 (RELEVANT): Semantically relevant to current query
        Layer 4 (RECENT): Latest interactions for continuity

        Each layer gets token budget by priority. Better memories, fewer of them.
        """

        combined_query = f"{conversation_context}\n{query}".strip()
        all_candidates: Dict[str, Memory] = {}

        def add_many(items: List[Memory]):
            for mem in items:
                if mem and not self._is_noisy_learning_memory(mem):
                    all_candidates[mem.id] = mem

        add_many(self.search_memories_semantic(
            combined_query or query,
            top_k=max_memories * 2,
            min_similarity=0.2,
        ))
        add_many(self.recall_relevant_memories(
            combined_query or query,
            limit=16,
            min_similarity=0.2,
            include_learning=False,
        ))
        add_many(self.get_important_memories(limit=10))
        add_many(
            self.db.query(Memory)
            .filter(Memory.agent_id == self.agent_id, Memory.is_blocked == False)
            .order_by(Memory.created_at.desc())
            .limit(8)
            .all()
        )

        # Classify into layers
        identity_mems = []
        relationship_mems = []
        relevant_mems = []
        recent_mems = []

        for mem in all_candidates.values():
            mem_type = mem.type.name if mem.type else "unknown"
            topics = {str(t).lower() for t in (mem.relates_to_topics or [])}
            importance = float(mem.importance_score or 0)

            if "user_name" in topics or "user_info" in topics or mem_type == "relational":
                relationship_mems.append(mem)
            elif mem_type in ("autobiographical", "semantic") and importance >= 0.6:
                identity_mems.append(mem)
            elif mem_type == "emotional" or "self_reflection" in topics:
                relevant_mems.append(mem)
            else:
                recent_mems.append(mem)

        # Sort each layer by importance/recency
        identity_mems.sort(key=lambda m: float(m.importance_score or 0), reverse=True)
        relationship_mems.sort(key=lambda m: (m.created_at or datetime.min), reverse=True)
        relevant_mems.sort(key=lambda m: float(m.importance_score or 0), reverse=True)
        recent_mems.sort(key=lambda m: (m.created_at or datetime.min), reverse=True)

        # Budget per layer: identity gets most, then relationship, then relevant, then recent
        layered = []
        layered.extend(("IDENTITY", m) for m in identity_mems[:8])
        layered.extend(("RELATIONSHIP", m) for m in relationship_mems[:6])
        layered.extend(("RELEVANT", m) for m in relevant_mems[:6])
        layered.extend(("RECENT", m) for m in recent_mems[:4])

        memories = [m for _, m in layered]

        awareness = self._summarize_memory_awareness(query, conversation_context, layered)
        return {
            "summary": awareness,
            "memories": memories[:12],
            "total_considered": len(all_candidates),
        }

    def _summarize_memory_awareness(
        self,
        query: str,
        conversation_context: str,
        layered_memories: List[tuple],
    ) -> str:
        if not layered_memories:
            return ""

        sections = {"IDENTITY": [], "RELATIONSHIP": [], "RELEVANT": [], "RECENT": []}
        for layer, mem in layered_memories:
            topics = mem.relates_to_topics or []
            memory_type = mem.type.name if mem.type else "unknown"
            line = (
                f"  - [{memory_type}] {mem.title}: {mem.content[:400]}"
                f" (importance={float(mem.importance_score or 0):.1f})"
            )
            sections.setdefault(layer, []).append(line)

        memory_text_parts = []
        layer_labels = {
            "IDENTITY": "IDENTITY (who I am, core facts about me)",
            "RELATIONSHIP": "RELATIONSHIP (what I know about this person)",
            "RELEVANT": "RELEVANT (related to current topic)",
            "RECENT": "RECENT (latest interactions)",
        }
        for layer_key in ["IDENTITY", "RELATIONSHIP", "RELEVANT", "RECENT"]:
            lines = sections.get(layer_key, [])
            if lines:
                memory_text_parts.append(f"=== {layer_labels[layer_key]} ===\n" + "\n".join(lines))

        memory_lines = "\n\n".join(memory_text_parts)

        prompt = self.prompts.render(
            "memory.awareness",
            query=query,
            conversation_context=conversation_context[:2200] or "(sem contexto recente)",
            memory_lines=memory_lines,
        )

        try:
            from llm_logic.llm_client import get_llm_client
            return get_llm_client().generate(prompt, max_tokens=900, temperature=0.15).strip()
        except Exception as e:
            logger.debug(f"[memory-awareness] falha ao resumir memórias: {e}")
            return memory_lines[:2000]

    def _is_noisy_learning_memory(self, memory: Memory) -> bool:
        topics = memory.relates_to_topics or []
        if isinstance(topics, str):
            topics = [topics]
        topic_set = {str(t).lower() for t in topics}

        if "imagined" in topic_set or "generated" in topic_set:
            return "autobiographical_imagination" not in topic_set

        return (
            (memory.title or "").lower().startswith("aprendizado:")
            or "learning" in topic_set
        )
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calcula similaridade cosina entre dois vetores"""
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a ** 2 for a in vec1) ** 0.5
        magnitude2 = sum(b ** 2 for b in vec2) ** 0.5
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    def create_initial_memories(self, initial_memories_data: List[Dict]):
        """Cria memórias iniciais quando agente nasce"""
        for mem_data in initial_memories_data:
            try:
                # Converter Pydantic models para dicts se necessário
                if hasattr(mem_data, 'dict'):
                    mem_dict = mem_data.dict()
                else:
                    mem_dict = mem_data
                
                self.create_memory(
                    title=mem_dict.get("title", ""),
                    content=mem_dict.get("content", ""),
                    memory_type=mem_dict.get("type", MemoryTypeEnum.AUTOBIOGRAPHICAL),
                    emotional_valence=mem_dict.get("emotional_valence", 0.0),
                    importance_score=mem_dict.get("importance_score", 0.8),
                    occurred_at=mem_dict.get("occurred_at"),
                    is_autobiographical=mem_dict.get("is_autobiographical", True),
                    is_episodic=mem_dict.get("is_episodic", False),
                    relates_to_topics=mem_dict.get("relates_to_topics", []),
                )
            except Exception as e:
                logger.error(f"Erro ao criar memória inicial: {e}")
