"""
Memory Manager - Sistema completo de gestão de memórias persistentes
Suporta múltiplos tipos de memória, busca semântica, decaimento temporal
"""

from sqlalchemy.orm import Session
from data.schema_cognitive import (
    Memory, MemoryType, MemoryEmbedding, Agent, ThoughtProcess
)
from llm_logic.embedding_generator import EmbeddingGenerator
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import json
from enum import Enum
import logging

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
        
        # Validar emotional_valence e importance_score
        emotional_valence = max(-1.0, min(1.0, float(emotional_valence)))
        importance_score = max(0.0, min(1.0, float(importance_score)))
        
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
    
    def recall_relevant_memories(self, topic: str, limit: int = 5) -> List[Memory]:
        """Recupera memórias relevantes para um tópico"""
        # Primeiro tenta busca semântica
        semantic_matches = self.search_memories_semantic(topic, top_k=limit)
        
        if semantic_matches:
            return semantic_matches
        
        # Fallback para busca por importância (sem usar JSON LIKE)
        return self.db.query(Memory).filter(
            Memory.agent_id == self.agent_id,
            Memory.is_blocked == False
        ).order_by(Memory.importance_score.desc()).limit(limit).all()
    
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
