from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, Boolean, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from config.config import settings

Base = declarative_base()

# ============================================================================
# Modelos principais
# ============================================================================

class Agent(Base):
    """Modelo de Agente - Schema simplificado sem config_json"""
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String, unique=True, index=True)
    name = Column(String, nullable=False)
    personality = Column(Text)
    system_prompt = Column(Text)
    description = Column(Text, nullable=True)
    avatar = Column(String, nullable=True)
    
    # Configurações de micro-agentes
    micro_agents = Column(Text)  # JSON array
    micro_agent_prompts = Column(Text, nullable=True)  # JSON object
    
    # Configurações comportamentais
    initial_memories = Column(Text, nullable=True)  # JSON array
    memory_namespace = Column(String, index=True)
    context_restricted = Column(String, default="false")
    behavior_specs = Column(Text, nullable=True)  # JSON
    
    # Configurações de modelo específicas (substitui config_json)
    model_name = Column(String, default="gpt-4-turbo-preview")
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=2000)
    top_p = Column(Float, default=1.0)
    frequency_penalty = Column(Float, default=0.0)
    presence_penalty = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamentos
    memories = relationship("Memory", back_populates="agent")
    documents = relationship("AgentDocument", back_populates="agent")
    memory_state = relationship("AgentMemoryState", back_populates="agent", uselist=False)

class Memory(Base):
    """Modelo de Memória"""
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(String, index=True)
    agent_id = Column(String, ForeignKey("agents.agent_id"), nullable=True, index=True)
    content = Column(Text)
    memory_type = Column(String)  # 'short', 'long', 'semantic', 'explicit'
    category = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    importance = Column(Float, default=0.5)
    tags = Column(Text, nullable=True)  # JSON string
    
    # Relacionamento
    agent = relationship("Agent", back_populates="memories")

class AgentPrompt(Base):
    """Modelo de Prompt de Agente"""
    __tablename__ = "agent_prompts"

    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(String, index=True)
    agent_name = Column(String, index=True)
    messages = Column(Text)  # JSON string
    response = Column(Text, nullable=True)
    model = Column(String, nullable=True)
    temperature = Column(Float, nullable=True)
    max_tokens = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Document(Base):
    """Modelo de Documento - armazena ficheiros completos"""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer, nullable=True)
    content_text = Column(Text, nullable=True)  # Texto completo extraído
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    document_metadata = Column(Text, nullable=True)  # JSON com metadados
    agent_id = Column(String, ForeignKey("agents.agent_id"), nullable=True, index=True)
    
    # Relacionamentos
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    agent_associations = relationship("AgentDocument", back_populates="document")

class DocumentChunk(Base):
    """Modelo de Chunk de Documento - divisão em pedaços"""
    __tablename__ = "document_chunks"

    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_number = Column(Integer, nullable=False)
    chunk_text = Column(Text, nullable=False)
    chunk_size = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    document = relationship("Document", back_populates="chunks")
    embeddings = relationship("DocumentEmbedding", back_populates="chunk", cascade="all, delete-orphan")

class DocumentEmbedding(Base):
    """Modelo de Embedding de Documento - vetores para busca semântica"""
    __tablename__ = "document_embeddings"

    id = Column(Integer, primary_key=True, index=True)
    chunk_id = Column(Integer, ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False, index=True)
    # Nota: Vector de 384 dimensões (sentence-transformers all-MiniLM-L6-v2)
    # Para armazenar: usar JSON se pgvector não estiver disponível
    embedding = Column(Text)  # JSON array ou VECTOR(384) com pgvector
    embedding_model = Column(String, default="all-MiniLM-L6-v2")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relacionamento
    chunk = relationship("DocumentChunk", back_populates="embeddings")

class AgentDocument(Base):
    """Relação muitos-para-muitos: Agentes e Documentos"""
    __tablename__ = "agent_documents"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String, ForeignKey("agents.agent_id"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relacionamentos
    agent = relationship("Agent", back_populates="documents")
    document = relationship("Document", back_populates="agent_associations")

class ConversationContext(Base):
    """Contexto de Conversa - manter histórico e contexto"""
    __tablename__ = "conversation_context"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, nullable=False, index=True, unique=True)
    agent_id = Column(String, ForeignKey("agents.agent_id"), nullable=False, index=True)
    user_id = Column(String, nullable=True, index=True)
    
    # Contexto estruturado
    context_data = Column(Text, nullable=False)  # JSON com contexto
    conversation_history = Column(Text, nullable=True)  # JSON com histórico
    
    # Últimos itens usados
    last_agent_used = Column(String, nullable=True)
    last_documents_used = Column(Text, nullable=True)  # JSON array
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    active = Column(Boolean, default=True, index=True)
    
    # Relacionamentos
    messages = relationship("ConversationMessage", back_populates="context", cascade="all, delete-orphan")

class ConversationMessage(Base):
    """Mensagem em Conversa - histórico detalhado"""
    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True, index=True)
    context_id = Column(Integer, ForeignKey("conversation_context.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    model_used = Column(String, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relacionamento
    context = relationship("ConversationContext", back_populates="messages")

class AgentMemoryState(Base):
    """Estado de Memória do Agente - manter contexto quem é/objetivos"""
    __tablename__ = "agent_memory_state"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String, ForeignKey("agents.agent_id"), nullable=False, unique=True, index=True)
    
    # Estado de identidade
    identity_context = Column(Text, nullable=True)  # JSON com quem é
    current_objectives = Column(Text, nullable=True)  # JSON com objetivos
    personality_state = Column(Text, nullable=True)  # JSON com estado personality
    
    # Contexto da conversa
    conversation_scope = Column(Text, nullable=True)  # Sobre o que estamos a falar
    active_topics = Column(Text, nullable=True)  # JSON array
    user_preferences = Column(Text, nullable=True)  # JSON com preferências
    
    # Estado do conhecimento
    relevant_memories = Column(Text, nullable=True)  # JSON array de memory IDs
    relevant_documents = Column(Text, nullable=True)  # JSON array de document IDs
    
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relacionamento
    agent = relationship("Agent", back_populates="memory_state", uselist=False)

# ============================================================================
# Modelos de Micro Agentes - Cada um com sua tabela linkada ao utilizador
# ============================================================================

class LogicAgent(Base):
    """Modelo de Logic Agent - seguindo padrão da tabela logic_agent"""
    __tablename__ = "logic_agent"

    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(String(255), nullable=False, index=True)
    user_id = Column(String(255), nullable=True, index=True)  # Linkado ao utilizador
    agent_name = Column(String(255), nullable=False, default="logic")
    prompt = Column(Text, nullable=False)
    temperature = Column(Float, nullable=False, default=0.7)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

class ThinkingAgent(Base):
    """Modelo de Thinking Agent - pensamento profundo"""
    __tablename__ = "thinking_agent"

    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(String(255), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)  # Linkado ao utilizador
    agent_name = Column(String(255), nullable=False, default="thinking")
    prompt = Column(Text, nullable=False)
    temperature = Column(Float, nullable=False, default=0.5)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

class KnowledgeAgent(Base):
    """Modelo de Knowledge Agent - busca de conhecimento"""
    __tablename__ = "knowledge_agent"

    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(String(255), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)  # Linkado ao utilizador
    agent_name = Column(String(255), nullable=False, default="knowledge")
    prompt = Column(Text, nullable=False)
    temperature = Column(Float, nullable=False, default=0.3)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

class ExpressionAgent(Base):
    """Modelo de Expression Agent - análise emocional"""
    __tablename__ = "expression_agent"

    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(String(255), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)  # Linkado ao utilizador
    agent_name = Column(String(255), nullable=False, default="expression")
    prompt = Column(Text, nullable=False)
    temperature = Column(Float, nullable=False, default=0.2)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

class PlannerAgent(Base):
    """Modelo de Planner Agent - planeamento"""
    __tablename__ = "planner_agent"

    id = Column(Integer, primary_key=True, index=True)
    persona_id = Column(String(255), nullable=False, index=True)
    user_id = Column(String(255), nullable=False, index=True)  # Linkado ao utilizador
    agent_name = Column(String(255), nullable=False, default="planner")
    prompt = Column(Text, nullable=False)
    temperature = Column(Float, nullable=False, default=0.4)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
