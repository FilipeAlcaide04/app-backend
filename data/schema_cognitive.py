"""
Schema Cognitive - Novo design de banco de dados para sistema cognitivo com micro-agentes
Sistema completo com suporte a:
- Agentes com identidade persistente
- Micro-agentes funcionando em paralelo
- Tipos de memória diferenciados
- Documentos privados por agente
- Interações entre agentes
- Debate e decisão cognitiva
"""

from sqlalchemy import (
    create_engine, Column, String, Text, DateTime, Float, Integer, Boolean, 
    ForeignKey, Index, JSON, UniqueConstraint, CheckConstraint, ARRAY
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
from uuid import uuid4
import json

Base = declarative_base()

# ============================================================================
# ENTIDADES PRINCIPAIS - AGENTES HUMANOS
# ============================================================================

class Agent(Base):
    """Agente humano artificial - pessoa completa com identidade"""
    __tablename__ = "agents"
    
    # Identidade
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    avatar = Column(String(10), default="👤")
    
    # Identidade psicológica
    birth_date = Column(DateTime)
    personality_traits = Column(JSON, default=dict)  # Big Five, MBTI, etc
    base_values = Column(JSON, default=dict)  # Valores fundamentais
    background_story = Column(Text)  # História de vida
    life_experiences = Column(JSON, default=dict)  # Experiências marcantes
    
    # Configurações cognitivas
    thinking_style = Column(String(50), default="balanced")  # logical, emotional, creative, balanced, etc
    decision_making_approach = Column(String(50), default="collaborative")  # how micro-agents decide
    debate_intensity = Column(Float, default=0.7)  # How much debate between micro-agents
    
    # Estado
    is_active = Column(Boolean, default=True, index=True)
    current_emotional_state = Column(JSON, default=dict)  # joy, sadness, fear, anger, etc
    last_interaction = Column(DateTime)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)
    
    # Relacionamentos
    micro_agents = relationship("MicroAgent", back_populates="agent", cascade="all, delete-orphan")
    memories = relationship("Memory", back_populates="agent", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="agent", cascade="all, delete-orphan")
    interactions_initiated = relationship("AgentInteraction", foreign_keys="AgentInteraction.initiator_id", back_populates="initiator")
    interactions_received = relationship("AgentInteraction", foreign_keys="AgentInteraction.responder_id", back_populates="responder")
    thought_processes = relationship("ThoughtProcess", back_populates="agent", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_agent_name', 'name'),
        Index('idx_agent_active', 'is_active'),
    )


# ============================================================================
# TIPOS E INSTÂNCIAS DE MICRO-AGENTES
# ============================================================================

class MicroAgentType(Base):
    """Define tipo de micro-agente (padrão cognitivo reutilizável)"""
    __tablename__ = "micro_agent_types"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(100), nullable=False, unique=True, index=True)  # logical, emotional, creative, etc
    description = Column(Text)
    category = Column(String(50), nullable=False)  # thinking_type
    
    # Instrução cognitiva
    system_prompt = Column(Text, nullable=False)
    cognitive_objective = Column(Text)  # O que este micro-agente tenta alcançar
    thinking_framework = Column(Text)  # Metodologia de pensamento
    
    # Comportamento
    default_weight = Column(Float, default=1.0)  # Peso na decisão final
    activation_conditions = Column(JSON)  # Quando este micro-agente é relevante
    response_style = Column(String(50))  # Modo de resposta
    
    # Metadata
    is_builtin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    instances = relationship("MicroAgent", back_populates="type")
    
    __table_args__ = (
        Index('idx_microagenttype_category', 'category'),
    )


class MicroAgent(Base):
    """Instância de micro-agente dentro de um agente principal"""
    __tablename__ = "micro_agents"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    agent_id = Column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    type_id = Column(String(36), ForeignKey("micro_agent_types.id"), nullable=False)
    
    # Customização pessoal
    custom_prompt = Column(Text)  # Override do system prompt se necessário
    custom_weight = Column(Float)  # Weight específico para este agente
    activation_enabled = Column(Boolean, default=True)
    
    # Estado interno
    current_focus = Column(String(255))  # O que este micro-agente está pensando agora
    recent_conclusions = Column(JSON, default=dict)  # Últimas conclusões
    confidence_level = Column(Float, default=0.5)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_activated = Column(DateTime)
    
    # Relacionamentos
    agent = relationship("Agent", back_populates="micro_agents")
    type = relationship("MicroAgentType", back_populates="instances")
    thought_contributions = relationship("ThoughtContribution", back_populates="micro_agent")
    
    __table_args__ = (
        UniqueConstraint('agent_id', 'type_id', name='unique_agent_microagent_type'),
        Index('idx_microagent_agent', 'agent_id'),
        Index('idx_microagent_type', 'type_id'),
    )


# ============================================================================
# SISTEMA DE MEMÓRIA AVANÇADO
# ============================================================================

class MemoryType(Base):
    """Define tipo de memória (classificação semântica)"""
    __tablename__ = "memory_types"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(100), nullable=False, unique=True)  # autobiographical, semantic, procedural, emotional, etc
    description = Column(Text)
    temporal_scope = Column(String(50))  # short_term, long_term, permanent
    decay_rate = Column(Float, default=0.0)  # Como memória enfraquece com o tempo (0=permanente, 1=desaparece)
    activation_threshold = Column(Float, default=0.5)  # Limite para ativar memória
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    memories = relationship("Memory", back_populates="type")


class Memory(Base):
    """Memória persistente de um agente"""
    __tablename__ = "memories"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    agent_id = Column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    type_id = Column(String(36), ForeignKey("memory_types.id"), nullable=False)
    
    # Conteúdo
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    emotional_valence = Column(Float, default=0.0)  # -1 (very negative) to +1 (very positive)
    importance_score = Column(Float, default=0.5)  # Quão importante é esta memória
    
    # Contexto
    relates_to_agent_ids = Column(JSON, default=dict)  # Sobre que agentes é esta memória
    relates_to_topics = Column(JSON, default=list)  # Tópicos relacionados
    relates_to_events = Column(JSON, default=list)  # Eventos específicos
    
    # Timing
    occurred_at = Column(DateTime)  # Quando aconteceu (pode ser diferente de created_at)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_accessed = Column(DateTime)
    
    # Retrieval
    access_count = Column(Integer, default=0)  # Quantas vezes foi usada
    relevance_score = Column(Float, default=0.5)  # Calculado dinamicamente
    
    # Metadata
    is_autobiographical = Column(Boolean, default=True)  # Sobre a vida deste agente
    is_episodic = Column(Boolean, default=False)  # Ligada a evento específico
    is_blocked = Column(Boolean, default=False)  # Memória traumática que pode estar reprimida
    
    # Relacionamentos
    agent = relationship("Agent", back_populates="memories")
    type = relationship("MemoryType", back_populates="memories")
    embeddings = relationship("MemoryEmbedding", back_populates="memory", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_memory_agent', 'agent_id'),
        Index('idx_memory_type', 'type_id'),
        Index('idx_memory_created', 'created_at'),
    )


class MemoryEmbedding(Base):
    """Embedding para busca semântica de memórias"""
    __tablename__ = "memory_embeddings"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    memory_id = Column(String(36), ForeignKey("memories.id", ondelete="CASCADE"), nullable=False)
    embedding = Column(JSON)  # Array de floats
    embedding_model = Column(String(100), default="all-MiniLM-L6-v2")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relacionamento
    memory = relationship("Memory", back_populates="embeddings")
    
    __table_args__ = (
        Index('idx_memory_embedding', 'memory_id'),
    )


# ============================================================================
# DOCUMENTOS PRIVADOS POR AGENTE
# ============================================================================

class Document(Base):
    """Documento pertence exclusivamente a um agente"""
    __tablename__ = "documents"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    agent_id = Column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Informações do documento
    filename = Column(String(255), nullable=False)
    file_path = Column(String(512), nullable=False)
    file_size = Column(Integer)
    file_type = Column(String(50))  # pdf, txt, docx, etc
    
    # Conteúdo
    original_content = Column(Text)  # Texto completo extraído
    is_processed = Column(Boolean, default=False)
    processing_status = Column(String(50), default="pending")  # pending, processing, completed, failed
    
    # Contexto
    document_description = Column(Text)  # Descrição manual do documento
    categories = Column(JSON, default=list)  # Tags/categorias
    
    # Metadata
    uploaded_by = Column(String(255))  # User que fez upload
    uploaded_at = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_archived = Column(Boolean, default=False)
    
    # Relacionamentos
    agent = relationship("Agent", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_document_agent', 'agent_id'),
        Index('idx_document_uploaded', 'uploaded_at'),
    )


class DocumentChunk(Base):
    """Divisão de documento em chunks para processamento"""
    __tablename__ = "document_chunks"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Chunk
    chunk_number = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_size = Column(Integer)
    
    # Positioning
    start_page = Column(Integer)
    end_page = Column(Integer)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    document = relationship("Document", back_populates="chunks")
    embeddings = relationship("DocumentEmbedding", back_populates="chunk", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_chunk_document', 'document_id'),
    )


class DocumentEmbedding(Base):
    """Embedding de chunk para busca semântica"""
    __tablename__ = "document_embeddings"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    chunk_id = Column(String(36), ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False)
    
    # Embedding (pode ser JSON array ou vector com pgvector extension)
    embedding = Column(JSON)  # [float, float, ..., float]
    embedding_model = Column(String(100), default="all-MiniLM-L6-v2")
    embedding_dimensions = Column(Integer, default=384)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relacionamento
    chunk = relationship("DocumentChunk", back_populates="embeddings")
    
    __table_args__ = (
        Index('idx_embedding_chunk', 'chunk_id'),
    )


# ============================================================================
# PROCESSO DE PENSAMENTO COGNITIVO
# ============================================================================

class ThoughtProcess(Base):
    """Registra processo de pensamento durante uma interação"""
    __tablename__ = "thought_processes"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    agent_id = Column(String(36), ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Input
    query = Column(Text, nullable=False)
    context = Column(JSON)  # Contexto da interação
    
    # Processo
    status = Column(String(50), default="thinking")  # thinking, debating, concluding, completed
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime)
    
    # Output
    final_response = Column(Text)
    confidence = Column(Float)
    reasoning = Column(Text)  # Explicação do raciocínio
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    agent = relationship("Agent", back_populates="thought_processes")
    contributions = relationship("ThoughtContribution", back_populates="thought_process")
    
    __table_args__ = (
        Index('idx_thought_agent', 'agent_id'),
        Index('idx_thought_created', 'created_at'),
    )


class ThoughtContribution(Base):
    """Contribuição de um micro-agente para o processo de pensamento"""
    __tablename__ = "thought_contributions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    thought_process_id = Column(String(36), ForeignKey("thought_processes.id", ondelete="CASCADE"), nullable=False)
    micro_agent_id = Column(String(36), ForeignKey("micro_agents.id"), nullable=False, index=True)
    
    # Contribuição
    thinking_step = Column(Integer)  # Ordem de pensamento
    perspective = Column(Text, nullable=False)  # O que este micro-agente pensa
    confidence = Column(Float)
    supporting_arguments = Column(JSON, default=list)
    opposing_arguments = Column(JSON, default=list)
    
    # Influência
    weight_in_decision = Column(Float, default=1.0)
    was_decisive = Column(Boolean, default=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    thought_process = relationship("ThoughtProcess", back_populates="contributions")
    micro_agent = relationship("MicroAgent", back_populates="thought_contributions")
    
    __table_args__ = (
        Index('idx_contribution_thought', 'thought_process_id'),
        Index('idx_contribution_microagent', 'micro_agent_id'),
    )


# ============================================================================
# INTERAÇÕES ENTRE AGENTES
# ============================================================================

class AgentInteraction(Base):
    """Interação entre dois agentes (debate, colaboração, conflito)"""
    __tablename__ = "agent_interactions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    initiator_id = Column(String(36), ForeignKey("agents.id"), nullable=False, index=True)
    responder_id = Column(String(36), ForeignKey("agents.id"), nullable=False, index=True)
    
    # Tipo de interação
    interaction_type = Column(String(50), nullable=False)  # debate, collaboration, conflict, support, etc
    topic = Column(String(255))
    
    # Conteúdo
    initiator_message = Column(Text)
    responder_message = Column(Text)
    
    # Resultado
    outcome = Column(String(50))  # agreement, disagreement, compromise, unresolved, etc
    relationship_change = Column(Float, default=0.0)  # Como afeta relacionamento (-1 a +1)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime)
    
    # Relacionamentos
    initiator = relationship("Agent", foreign_keys=[initiator_id], back_populates="interactions_initiated")
    responder = relationship("Agent", foreign_keys=[responder_id], back_populates="interactions_received")
    
    __table_args__ = (
        Index('idx_interaction_initiator', 'initiator_id'),
        Index('idx_interaction_responder', 'responder_id'),
        Index('idx_interaction_created', 'created_at'),
    )


class AgentRelationship(Base):
    """Relacionamento entre agentes (amizade, conflito, etc)"""
    __tablename__ = "agent_relationships"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    agent_a_id = Column(String(36), ForeignKey("agents.id"), nullable=False, index=True)
    agent_b_id = Column(String(36), ForeignKey("agents.id"), nullable=False, index=True)
    
    # Relacionamento
    relationship_type = Column(String(50))  # friend, rival, mentor, peer, etc
    trust_level = Column(Float, default=0.5)  # 0 (no trust) to 1 (complete trust)
    affinity = Column(Float, default=0.0)  # -1 (hate) to +1 (love)
    
    # História
    history = Column(JSON, default=list)  # Lista de eventos no relacionamento
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_interaction = Column(DateTime)
    
    __table_args__ = (
        UniqueConstraint('agent_a_id', 'agent_b_id', name='unique_agent_pair'),
        Index('idx_relationship_agent_a', 'agent_a_id'),
        Index('idx_relationship_agent_b', 'agent_b_id'),
    )


# ============================================================================
# AUDITORIA E LOGGING
# ============================================================================

class AuditLog(Base):
    """Log de auditoria para todas as ações significativas"""
    __tablename__ = "audit_logs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    
    # Contexto
    agent_id = Column(String(36), ForeignKey("agents.id", ondelete="SET NULL"), index=True)
    action = Column(String(100), nullable=False)  # create, update, delete, access, etc
    resource_type = Column(String(50), nullable=False)  # agent, memory, document, etc
    resource_id = Column(String(36), nullable=False)
    
    # Mudanças
    old_values = Column(JSON)
    new_values = Column(JSON)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    __table_args__ = (
        Index('idx_audit_agent', 'agent_id'),
        Index('idx_audit_resource', 'resource_type', 'resource_id'),
    )


# ============================================================================
# Inicialização
# ============================================================================

def init_cognitive_db(database_url: str):
    """Inicializa banco de dados com schema cognitivo"""
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    return engine


def get_cognitive_session(database_url: str):
    """Cria session factory"""
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()
