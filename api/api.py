"""
Cognitive API - API REST para sistema de agentes cognitivos
Endpoints para criar, gerenciar e interagir com agentes (pessoas artificiais)
"""

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime
# Database
from data.database_cognitive import init_cognitive_db, get_db_session

# Services
from agent_system.agent_service_cognitive import AgentServiceCognitive
from agent_system.memory_manager_cognitive import MemoryManager, MemoryTypeEnum
from agent_system.cognitive_orchestrator import CognitiveOrchestrator
from document_handlers.document_service_cognitive import DocumentServiceCognitive
from config.embedding_cache import preload_embedding_model  # 🚀 Pré-carregar modelo

import asyncio
import logging
import os
from dotenv import load_dotenv

# Carregar .env
load_dotenv()

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Sistema Cognitivo de Agentes Humanos Artificiais",
    description="API para criação e gestão de pessoas artificiais com pensamento cognitivo",
    version="2.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir arquivos estáticos (incluindo chat.html)
static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Inicializar BD
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:admin@localhost:5432/cognitive_agents")
init_cognitive_db(DATABASE_URL)

# ============================================================================
# 🚀 STARTUP - Pré-carregar modelo de embeddings
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """
    Executar ao iniciar servidor
    - Pré-carrega modelo de embeddings na memória
    - Evita delay na primeira request
    """
    logger.info("\n" + "="*80)
    logger.info("🚀 INICIANDO SERVIDOR - COGNITIVE API v2.0")
    logger.info("="*80)
    preload_embedding_model()
    logger.info("="*80 + "\n")

# ============================================================================
# MODELOS
# ============================================================================

class PersonalityTraits(BaseModel):
    """Traços de personalidade (Big Five, MBTI, etc)"""
    openness: Optional[float] = 0.5
    conscientiousness: Optional[float] = 0.5
    extraversion: Optional[float] = 0.5
    agreeableness: Optional[float] = 0.5
    neuroticism: Optional[float] = 0.5


class MicroAgentConfig(BaseModel):
    """Configuração customizada para um micro-agente"""
    type: str  # logical, emotional, critical, creative, ethical, social
    custom_prompt: Optional[str] = None  
    custom_weight: Optional[float] = None  
    activation_enabled: Optional[bool] = True


class InitialMemory(BaseModel):
    """Memória inicial do agente"""
    title: str
    content: str
    type: Optional[str] = "autobiographical"  # autobiographical, semantic, procedural, emotional, episodic, relational, short_term, traumatic, aspirational
    importance_score: Optional[float] = 0.8  # 0.0 - 1.0
    emotional_valence: Optional[float] = 0.0  # -1.0 (negative) to 1.0 (positive)
    is_autobiographical: Optional[bool] = True
    is_episodic: Optional[bool] = False
    occurs_at: Optional[str] = None  # ISO timestamp
    relates_to_topics: Optional[List[str]] = None


class CreateAgentRequest(BaseModel):
    """Request para criar novo agente com configuração completa"""
    name: str
    description: Optional[str] = None
    personality_traits: Optional[Dict] = None
    base_values: Optional[Dict] = None
    background_story: Optional[str] = None
    thinking_style: Optional[str] = "balanced"
    decision_making_approach: Optional[str] = "collaborative"
    debate_intensity: Optional[float] = 0.7
    initial_memories: Optional[List[InitialMemory]] = None  # Memórias iniciais do agente
    micro_agent_types: Optional[List[str]] = None
    micro_agents_config: Optional[List[MicroAgentConfig]] = None
    avatar: Optional[str] = "👤"


class ThinkRequest(BaseModel):
    """Request para iniciar processo de pensamento - NOVA VERSÃO HUMANIZADA"""
    message: str  # Query do utilizador
    user_id: Optional[str] = None  # ID do utilizador para personalização
    conversation_id: Optional[str] = None  # ID da conversa para contexto
    context: Optional[Dict] = None  # Contexto adicional
    # Legado (para compatibilidade)
    query: Optional[str] = None


class MemoryRequest(BaseModel):
    """Request para criar memória"""
    title: str
    content: str
    memory_type: str = "semantic"
    importance_score: Optional[float] = 0.5
    emotional_valence: Optional[float] = 0.0
    is_autobiographical: Optional[bool] = True
    relates_to_topics: Optional[List[str]] = None


class SearchMemoriesRequest(BaseModel):
    """Request para busca semântica de memórias"""
    query: str
    memory_types: Optional[List[str]] = None
    top_k: Optional[int] = 5


class DocumentSearchRequest(BaseModel):
    """Request para busca semântica em documentos"""
    query: str
    top_k: Optional[int] = 5


class RelationshipRequest(BaseModel):
    """Request para criar/atualizar relacionamento"""
    agent_b_id: str
    relationship_type: Optional[str] = "acquaintance"
    trust_level: Optional[float] = 0.5
    affinity: Optional[float] = 0.0


class ChatMessage(BaseModel):
    """Mensagem em conversa com agente"""
    role: str  # "user" ou "assistant"
    content: str
    timestamp: Optional[str] = None


class ChatRequest(BaseModel):
    """Request para enviar mensagem a agente"""
    message: str
    user_id: Optional[str] = "default_user"
    conversation_id: Optional[str] = None  # Se None, cria nova conversa
    context: Optional[Dict] = None


class ChatResponse(BaseModel):
    """Response da conversa com agente"""
    conversation_id: str
    agent_response: str
    thinking_summary: Optional[Dict] = None
    messages_count: int
    duration_ms: Optional[int] = None


# ============================================================================
# DEPENDENCY
# ============================================================================

def get_db():
    """Dependency para obter sessão de BD"""
    db = get_db_session(DATABASE_URL)
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# ENDPOINTS - AGENTES
# ============================================================================

@app.post("/agents", tags=["Agents"])
async def create_agent(request: CreateAgentRequest, db: Session = Depends(get_db)):
    """Cria novo agente (pessoa artificial)"""
    
    service = AgentServiceCognitive(db)
    
    try:
        # Converter micro_agents_config para formato esperado
        micro_agents_config = None
        if request.micro_agents_config:
            micro_agents_config = {
                cfg.type: {
                    "custom_prompt": cfg.custom_prompt,
                    "custom_weight": cfg.custom_weight,
                    "activation_enabled": cfg.activation_enabled,
                }
                for cfg in request.micro_agents_config
            }
        
        agent = service.create_agent(
            name=request.name,
            description=request.description,
            personality_traits=request.personality_traits,
            base_values=request.base_values,
            background_story=request.background_story,
            thinking_style=request.thinking_style,
            decision_making_approach=request.decision_making_approach,
            debate_intensity=request.debate_intensity,
            initial_memories=request.initial_memories,
            micro_agent_types=request.micro_agent_types,
            avatar=request.avatar,
            micro_agents_config=micro_agents_config,
        )
        
        return service.agent_to_dict(agent)
    
    except Exception as e:
        logger.error(f"Erro ao criar agente: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/agents", tags=["Agents"])
async def list_agents(
    active_only: bool = True,
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Lista agentes"""
    
    service = AgentServiceCognitive(db)
    agents = service.list_agents(active_only=active_only, limit=limit, offset=offset)
    
    return [service.agent_to_dict(agent) for agent in agents]


@app.get("/agents/{agent_id}", tags=["Agents"])
async def get_agent(agent_id: str, db: Session = Depends(get_db)):
    """Obtém agente por ID"""
    
    service = AgentServiceCognitive(db)
    agent = service.get_agent(agent_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    
    return service.agent_to_dict(agent)


@app.put("/agents/{agent_id}", tags=["Agents"])
async def update_agent(
    agent_id: str,
    updates: Dict[str, Any],
    db: Session = Depends(get_db)
):
    """Atualiza agente"""
    
    service = AgentServiceCognitive(db)
    agent = service.update_agent(agent_id, **updates)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    
    return service.agent_to_dict(agent)


@app.delete("/agents/{agent_id}", tags=["Agents"])
async def delete_agent(agent_id: str, db: Session = Depends(get_db)):
    """Deleta agente"""
    
    service = AgentServiceCognitive(db)
    
    if not service.delete_agent(agent_id):
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    
    return {"message": f"Agente {agent_id} removido"}


# ============================================================================
# ENDPOINTS - PENSAMENTO COGNITIVO
# ============================================================================

@app.post("/agents/{agent_id}/think", tags=["Cognition"])
async def agent_think(
    agent_id: str,
    request: ThinkRequest,
    db: Session = Depends(get_db)
):
    """
    🧠 Inicia processo de pensamento cognitivo HUMANIZADO
    
    NOVA ARQUITETURA:
    - Avaliação inteligente de relevância de micro-agentes
    - Consulta automática de documentos
    - Pensamento paralelo modificado por memória
    - Síntese humanizada pelo Core Agent
    - Aprendizado contínuo
    """
    
    service = AgentServiceCognitive(db)
    
    try:
        # Usar 'message' como preferência, fallback para 'query'
        query = request.message or request.query
        
        if not query:
            raise ValueError("'message' ou 'query' é obrigatório")
        
        # Chamar novo método think com parâmetros humanizados
        result = await service.think(
            agent_id=agent_id,
            query=query,
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            context=request.context
        )
        
        return result
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Erro no pensamento: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agents/{agent_id}/micro-agents/reinitialize", tags=["Cognition"])
async def reinitialize_micro_agents(
    agent_id: str,
    db: Session = Depends(get_db)
):
    """Reinicializa todos os 6 micro-agentes padrão do agente (garante que todos estejam criados)"""
    
    service = AgentServiceCognitive(db)
    agent = service.get_agent(agent_id)
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    
    try:
        # Deletar micro-agentes existentes
        from data.schema_cognitive import MicroAgent
        db.query(MicroAgent).filter(MicroAgent.agent_id == agent_id).delete()
        db.commit()
        
        # Recriar todos os 6 padrão
        service._create_agent_micro_agents(agent_id)
        
        # Retornar lista atualizada
        micro_agents = service.get_agent_micro_agents(agent_id)
        
        return {
            "message": "Micro-agentes reinicializados com sucesso",
            "agent_id": agent_id,
            "micro_agents_count": len(micro_agents),
            "micro_agents": micro_agents
        }
    except Exception as e:
        logger.error(f"Erro ao reinicializar micro-agentes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agents/{agent_id}/micro-agents", tags=["Cognition"])
async def list_micro_agents(agent_id: str, db: Session = Depends(get_db)):
    """Lista micro-agentes de um agente"""
    
    service = AgentServiceCognitive(db)
    micro_agents = service.get_agent_micro_agents(agent_id)
    
    return {"micro_agents": micro_agents}


@app.post("/agents/{agent_id}/micro-agents/{type_name}/enable", tags=["Cognition"])
async def enable_micro_agent(
    agent_id: str,
    type_name: str,
    db: Session = Depends(get_db)
):
    """Ativa micro-agente"""
    
    service = AgentServiceCognitive(db)
    
    if not service.enable_micro_agent(agent_id, type_name):
        raise HTTPException(status_code=400, detail="Tipo de micro-agente não existe")
    
    return {"message": f"Micro-agente {type_name} ativado"}


@app.post("/agents/{agent_id}/micro-agents/{type_name}/disable", tags=["Cognition"])
async def disable_micro_agent(
    agent_id: str,
    type_name: str,
    db: Session = Depends(get_db)
):
    """Desativa micro-agente"""
    
    service = AgentServiceCognitive(db)
    
    if not service.disable_micro_agent(agent_id, type_name):
        raise HTTPException(status_code=400, detail="Micro-agente não existe")
    
    return {"message": f"Micro-agente {type_name} desativado"}


# ============================================================================
# ENDPOINTS - MEMÓRIAS
# ============================================================================

@app.get("/agents/{agent_id}/memories", tags=["Memory"])
async def list_memories(agent_id: str, db: Session = Depends(get_db)):
    """Lista memórias de um agente"""
    
    service = AgentServiceCognitive(db)
    memories = service.get_agent_memories(agent_id)
    
    return {"memories": memories}


@app.post("/agents/{agent_id}/memories", tags=["Memory"])
async def create_memory(
    agent_id: str,
    request: MemoryRequest,
    db: Session = Depends(get_db)
):
    """Cria memória para um agente"""
    
    try:
        memory_manager = MemoryManager(db, agent_id)
        
        memory = memory_manager.create_memory(
            title=request.title,
            content=request.content,
            memory_type=request.memory_type,
            importance_score=request.importance_score,
            emotional_valence=request.emotional_valence,
            is_autobiographical=request.is_autobiographical,
            relates_to_topics=request.relates_to_topics,
        )
        
        return {
            "id": memory.id,
            "title": memory.title,
            "created_at": memory.created_at.isoformat() if memory.created_at else None,
        }
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Erro ao criar memória: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agents/{agent_id}/memories/search", tags=["Memory"])
async def search_memories(
    agent_id: str,
    request: SearchMemoriesRequest,
    db: Session = Depends(get_db)
):
    """Busca semântica em memórias"""
    
    try:
        memory_manager = MemoryManager(db, agent_id)
        
        memories = memory_manager.search_memories_semantic(
            query=request.query,
            top_k=request.top_k,
            memory_types=request.memory_types,
        )
        
        return {
            "results": [
                {
                    "id": m.id,
                    "title": m.title,
                    "type": m.type.name if m.type else "unknown",
                    "importance": m.importance_score,
                }
                for m in memories
            ]
        }
    
    except Exception as e:
        logger.error(f"Erro na busca de memórias: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENDPOINTS - DOCUMENTOS
# ============================================================================

@app.get("/agents/{agent_id}/documents", tags=["Documents"])
async def list_documents(agent_id: str, db: Session = Depends(get_db)):
    """Lista documentos de um agente"""
    
    service = DocumentServiceCognitive(db)
    documents = service.get_agent_documents(agent_id)
    
    return {
        "documents": [service.document_to_dict(doc) for doc in documents]
    }


@app.post("/agents/{agent_id}/documents/upload", tags=["Documents"])
async def upload_document(
    agent_id: str,
    file: UploadFile = File(...),
    description: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Upload de documento para um agente"""
    
    service = DocumentServiceCognitive(db)
    
    try:
        file_content = await file.read()
        
        document = service.upload_document(
            agent_id=agent_id,
            filename=file.filename or "document",
            file_content=file_content,
            description=description,
        )
        
        return service.document_to_dict(document)
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Erro ao fazer upload: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agents/{agent_id}/documents/search", tags=["Documents"])
async def search_documents(
    agent_id: str,
    request: DocumentSearchRequest,
    db: Session = Depends(get_db)
):
    """Busca semântica em documentos"""
    
    service = DocumentServiceCognitive(db)
    
    try:
        results = service.search_documents_semantic(
            agent_id=agent_id,
            query=request.query,
            top_k=request.top_k,
        )
        
        return {"results": results}
    
    except Exception as e:
        logger.error(f"Erro na busca de documentos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/agents/{agent_id}/documents/{document_id}", tags=["Documents"])
async def delete_document(
    agent_id: str,
    document_id: str,
    db: Session = Depends(get_db)
):
    """Deleta documento"""
    
    service = DocumentServiceCognitive(db)
    
    try:
        if not service.delete_document(agent_id, document_id):
            raise HTTPException(status_code=404, detail="Documento não encontrado")
        
        return {"message": f"Documento {document_id} removido"}
    
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Erro ao deletar documento: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENDPOINTS - RELACIONAMENTOS
# ============================================================================

@app.post("/agents/{agent_id}/relationships", tags=["Relationships"])
async def create_relationship(
    agent_id: str,
    request: RelationshipRequest,
    db: Session = Depends(get_db)
):
    """Cria relacionamento entre dois agentes"""
    
    service = AgentServiceCognitive(db)
    
    try:
        relationship = service.create_relationship(
            agent_a_id=agent_id,
            agent_b_id=request.agent_b_id,
            relationship_type=request.relationship_type,
            trust_level=request.trust_level,
            affinity=request.affinity,
        )
        
        return {
            "relationship_type": relationship.relationship_type,
            "trust_level": relationship.trust_level,
            "affinity": relationship.affinity,
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Erro ao criar relacionamento: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENDPOINTS - CHAT (Conversa Natural)
# ============================================================================

# Armazenar históricos de conversa em memória (em produção usar BD)
_chat_conversations: Dict[str, List[Dict]] = {}


@app.post("/agents/{agent_id}/chat", tags=["Chat"])
async def chat_with_agent(
    agent_id: str,
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """
    Chat natural com agente - mantém histórico de conversa
    
    Se conversation_id não é fornecido, cria nova conversa.
    Responde como pessoa natural com memória de conversa.
    """
    
    service = AgentServiceCognitive(db)
    
    try:
        # Validar agente
        agent = service.get_agent(agent_id)
        if not agent:
            raise HTTPException(status_code=404, detail=f"Agente {agent_id} não encontrado")
        
        # Gerar conversation_id se não fornecido
        if not request.conversation_id:
            request.conversation_id = f"conv_{agent_id}_{int(datetime.now().timestamp() * 1000)}"
        
        # Inicializar histórico se não existe
        if request.conversation_id not in _chat_conversations:
            _chat_conversations[request.conversation_id] = []
        
        conversation_history = _chat_conversations[request.conversation_id]
        
        # Adicionar mensagem do utilizador
        conversation_history.append({
            "role": "user",
            "content": request.message,
            "timestamp": datetime.now().isoformat()
        })
        
        # Preparar contexto com histórico
        context = request.context or {}
        context["conversation_history"] = conversation_history
        
        # Processar mensagem através do orchestrator
        import time
        start_time = time.time()
        
        try:
            # Obter orchestrator
            orchestrator = CognitiveOrchestrator(db, agent_id)
            
            # Usar think para processar a mensagem com pensamento cognitivo
            result = await orchestrator.think(request.message, context, record_process=True)
            
            duration_ms = int((time.time() - start_time) * 1000)
            agent_response = result.get("response", "")
            
        except Exception as e:
            db.rollback()  # Rollback de qualquer transação em falha
            logger.error(f"Erro no pensamento do agente: {e}", exc_info=True)
            # Fallback: usar resposta simples se o pensamento falhar
            agent_response = f"Desculpe, tive um problema ao processar sua mensagem: {str(e)}"
            duration_ms = int((time.time() - start_time) * 1000)
            result = {"response": agent_response, "confidence": 0.0}
        
        # Adicionar resposta ao histórico
        conversation_history.append({
            "role": "assistant",
            "content": agent_response,
            "timestamp": datetime.now().isoformat(),
            "agent_name": agent.name,
            "agent_avatar": agent.avatar
        })
        
        return {
            "conversation_id": request.conversation_id,
            "agent_id": agent_id,
            "agent_name": agent.name,
            "agent_avatar": agent.avatar,
            "agent_response": agent_response,
            "thinking_summary": result.get("thinking_summary"),
            "confidence": result.get("confidence"),
            "messages_count": len(conversation_history),
            "duration_ms": duration_ms
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Erro no chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/agents/{agent_id}/chat/{conversation_id}/history", tags=["Chat"])
async def get_conversation_history(agent_id: str, conversation_id: str):
    """Obtém histórico completo de conversa"""
    
    if conversation_id not in _chat_conversations:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    
    return {
        "conversation_id": conversation_id,
        "agent_id": agent_id,
        "messages": _chat_conversations[conversation_id],
        "total_messages": len(_chat_conversations[conversation_id])
    }


@app.get("/chat/conversations", tags=["Chat"])
async def list_conversations():
    """Lista todas as conversas ativas"""
    
    return {
        "total_conversations": len(_chat_conversations),
        "conversations": [
            {
                "conversation_id": conv_id,
                "messages_count": len(messages)
            }
            for conv_id, messages in _chat_conversations.items()
        ]
    }


# ============================================================================
# ROOT
# ============================================================================

@app.get("/", tags=["Root"])
async def root():
    """Redireciona para a interface de chat"""
    return {
        "message": "Sistema Cognitivo de Agentes Humanos Artificiais v2.0",
        "status": "active",
        "chat_url": "/static/chat.html",
        "api_docs": "/docs"
    }


@app.get("/chat", tags=["Chat"])
async def serve_chat():
    """Serve a interface de chat"""
    from fastapi.responses import FileResponse
    chat_file = os.path.join(os.path.dirname(__file__), "..", "static", "chat.html")
    if os.path.exists(chat_file):
        return FileResponse(chat_file)
    raise HTTPException(status_code=404, detail="Chat interface not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
