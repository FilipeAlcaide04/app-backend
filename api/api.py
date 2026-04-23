"""
API REST v2 - Sistema de Humanos Virtuais Completos
Endpoints para criar, gerir e interagir com personas humanas

Novidades v2:
- Criação de personas com blueprint completo (digital_human_persona_v3)
- Chat persistente em DB (não em memória)
- Estado emocional persistente entre conversas
- Gestão de blueprint por secção
- Reset de estado emocional
- Histórico de conversas real
"""


"""
Como correr: python -m uvicorn api.api:app --reload
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
from data.schema_cognitive import Agent
from data.schema_persona import PersonaBlueprint, DynamicState
import data.schema_auth  # noqa: F401 - registar modelo User na Base

# Services
from agent_system.agent_service_cognitive import AgentServiceCognitive
from agent_system.memory_manager_cognitive import MemoryManager, MemoryTypeEnum
from agent_system.cognitive_orchestrator import CognitiveOrchestrator
from agent_system.persona_engine import PersonaEngine, get_default_persona_template
from agent_system.conversation_manager import ConversationManager
from document_handlers.document_service_cognitive import DocumentServiceCognitive
from config.embedding_cache import preload_embedding_model

import asyncio
import logging
import os
import time
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Sistema de Humanos Virtuais",
    description="API para criação e gestão de pessoas artificiais com personalidade, emoções, memória e pensamento autónomo",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth Router
from api.auth import router as auth_router
app.include_router(auth_router)

static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:admin@localhost:5432/cognitive_agents")
init_cognitive_db(DATABASE_URL)


@app.on_event("startup")
async def startup_event():
    logger.info("\n" + "=" * 80)
    logger.info("INICIANDO SERVIDOR - HUMAN SIMULATION API v3.0")
    logger.info("=" * 80)
    preload_embedding_model()

    # Seed admin user
    from api.auth import seed_admin_user
    db = get_db_session(DATABASE_URL)
    try:
        seed_admin_user(db)
    finally:
        db.close()

    logger.info("=" * 80 + "\n")


# ============================================================================
# MODELOS PYDANTIC
# ============================================================================

class InitialMemory(BaseModel):
    title: str
    content: str
    type: Optional[str] = "autobiographical"
    importance_score: Optional[float] = 0.8
    emotional_valence: Optional[float] = 0.0
    is_autobiographical: Optional[bool] = True
    is_episodic: Optional[bool] = False
    relates_to_topics: Optional[List[str]] = None


class CreateAgentRequest(BaseModel):
    name: str
    description: Optional[str] = None
    personality_traits: Optional[Dict] = None
    base_values: Optional[Dict] = None
    background_story: Optional[str] = None
    thinking_style: Optional[str] = "balanced"
    decision_making_approach: Optional[str] = "collaborative"
    debate_intensity: Optional[float] = 0.7
    initial_memories: Optional[List[InitialMemory]] = None
    micro_agent_types: Optional[List[str]] = None
    avatar: Optional[str] = "👤"


class CreatePersonaRequest(BaseModel):
    """Request para criar humano virtual com persona COMPLETA"""
    name: str
    description: Optional[str] = None
    avatar: Optional[str] = "👤"
    background_story: Optional[str] = None

    # Persona blueprint completo (ou parcial - faz merge com defaults)
    persona: Optional[Dict[str, Any]] = None

    # Configurações simplificadas (alternativa ao blueprint completo)
    personality_traits: Optional[Dict] = None  # Big Five simples
    thinking_style: Optional[str] = "balanced"
    debate_intensity: Optional[float] = 0.7

    # Micro-agentes
    micro_agent_types: Optional[List[str]] = None

    # Memórias iniciais
    initial_memories: Optional[List[InitialMemory]] = None


class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = "default_user"
    conversation_id: Optional[str] = None
    context: Optional[Dict] = None


class ThinkRequest(BaseModel):
    message: str
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    context: Optional[Dict] = None
    query: Optional[str] = None


class MemoryRequest(BaseModel):
    title: str
    content: str
    memory_type: str = "semantic"
    importance_score: Optional[float] = 0.5
    emotional_valence: Optional[float] = 0.0
    is_autobiographical: Optional[bool] = True
    relates_to_topics: Optional[List[str]] = None


class SearchMemoriesRequest(BaseModel):
    query: str
    memory_types: Optional[List[str]] = None
    top_k: Optional[int] = 5


class FeedbackRequest(BaseModel):
    interaction_id: str
    feedback_type: str
    feedback_score: Optional[float] = 0.0
    feedback_text: Optional[str] = None


class UpdateBlueprintRequest(BaseModel):
    section: str
    data: Dict[str, Any]


class DocumentSearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5


# ============================================================================
# DEPENDENCY
# ============================================================================

def get_db():
    db = get_db_session(DATABASE_URL)
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# ENDPOINTS - PERSONAS (CRIAR HUMANOS)
# ============================================================================

@app.get("/personas", tags=["Personas"])
async def list_personas(db: Session = Depends(get_db)):
    """Lista todas as personas criadas com resumo do estado actual."""

    blueprints = db.query(PersonaBlueprint).all()

    result = []
    for bp in blueprints:
        agent = db.query(Agent).filter(Agent.id == bp.agent_id).first()
        state = db.query(DynamicState).filter(
            DynamicState.agent_id == bp.agent_id,
            DynamicState.is_current == True
        ).first()

        identity = bp.identity or {}
        personality = bp.personality_full or {}

        result.append({
            "id": bp.agent_id,
            "name": agent.name if agent else "?",
            "self_concept": identity.get("self_concept", {}).get("how_they_see_themselves", ""),
            "attachment_style": personality.get("attachment_style", ""),
            "mood": state.current_mood if state else None,
            "energy": state.energy_level if state else None,
            "stress": state.current_stress_load if state else None,
            "primary_emotion": state.primary_emotion if state else None,
            "created_at": bp.created_at.isoformat() if bp.created_at else None,
        })

    return {"total": len(result), "personas": result}


@app.post("/personas", tags=["Personas"])
async def create_persona(request: CreatePersonaRequest, db: Session = Depends(get_db)):
    """
    Cria um humano virtual COMPLETO com persona detalhada.

    Pode enviar:
    - `persona`: Blueprint completo (JSON do schema digital_human_persona_v3)
    - `personality_traits`: Big Five simples (merge automático com defaults)
    - Ambos: persona tem prioridade, personality_traits preenche lacunas
    """

    service = AgentServiceCognitive(db)

    try:
        # Preparar personality traits
        traits = request.personality_traits or {}
        if request.persona:
            big_five = request.persona.get("personality_full", {}).get("big_five", {})
            if big_five:
                traits = {**traits, **big_five}

        if not traits:
            traits = {"openness": 0.6, "conscientiousness": 0.6, "extraversion": 0.5,
                      "agreeableness": 0.7, "neuroticism": 0.3}

        # Criar agente base
        agent = service.create_agent(
            name=request.name,
            description=request.description or f"{request.name} é um humano virtual.",
            personality_traits=traits,
            background_story=request.background_story,
            thinking_style=request.thinking_style,
            decision_making_approach="collaborative",
            debate_intensity=request.debate_intensity,
            initial_memories=[m.dict() for m in request.initial_memories] if request.initial_memories else None,
            micro_agent_types=request.micro_agent_types,
            avatar=request.avatar
        )

        agent_id = agent.id

        # Criar persona blueprint
        persona_engine = PersonaEngine(db, agent_id)

        persona_data = request.persona or {}

        # Se enviou personality_traits simples, injectar no persona_data
        if request.personality_traits and "personality_full" not in persona_data:
            persona_data["personality_full"] = {"big_five": request.personality_traits}

        # Se enviou background_story, injectar na identity
        if request.background_story and "identity" not in persona_data:
            persona_data["identity"] = {}

        blueprint = persona_engine.create_persona(persona_data)

        # Obter identity builder para preview
        from agent_system.identity_builder import IdentityBuilder
        identity = IdentityBuilder(db, agent_id)

        return {
            "status": "success",
            "message": f"Humano virtual '{request.name}' criado com sucesso!",
            "human": {
                "id": agent.id,
                "name": agent.name,
                "has_persona": True,
                "has_blueprint": True,
                "persona_sections": list(persona_data.keys()) if persona_data else ["defaults"],
                "identity_preview": identity.get_identity_prompt()[:500] + "...",
                "initial_state": persona_engine.get_state_summary(),
                "ready_for_interaction": True
            }
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao criar persona: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/personas/template", tags=["Personas"])
async def get_persona_template():
    """
    Retorna o template completo de persona com todos os campos e defaults.
    Use como base para criar personas customizadas.
    """
    return {
        "template": get_default_persona_template(),
        "description": "Template completo digital_human_persona_v3. Preencha os campos que quiser, os restantes usam valores padrão."
    }


@app.get("/personas/{agent_id}/blueprint", tags=["Personas"])
async def get_persona_blueprint(agent_id: str, db: Session = Depends(get_db)):
    """Obtém blueprint completo da persona"""

    persona = PersonaEngine(db, agent_id)
    if not persona.has_persona:
        raise HTTPException(status_code=404, detail="Persona não encontrada. Crie primeiro com POST /personas")

    bp = persona.blueprint
    return {
        "agent_id": agent_id,
        "identity": bp.identity,
        "internal_states_config": bp.internal_states_config,
        "personality_full": bp.personality_full,
        "memory_config": bp.memory_config,
        "emotional_config": bp.emotional_config,
        "cognitive_config": bp.cognitive_config,
        "social_config": bp.social_config,
        "behavioral_config": bp.behavioral_config,
        "worldview": bp.worldview,
        "growth_arc": bp.growth_arc,
        "behavior_prompts": bp.behavior_prompts,
        "meta": bp.meta,
        "created_at": bp.created_at.isoformat() if bp.created_at else None,
        "updated_at": bp.updated_at.isoformat() if bp.updated_at else None,
    }


@app.put("/personas/{agent_id}/blueprint", tags=["Personas"])
async def update_persona_blueprint(
    agent_id: str,
    request: UpdateBlueprintRequest,
    db: Session = Depends(get_db)
):
    """
    Actualiza uma secção específica do blueprint.
    Secções válidas: identity, internal_states_config, personality_full,
    memory_config, emotional_config, cognitive_config, social_config,
    behavioral_config, worldview, growth_arc, behavior_prompts, meta
    """

    persona = PersonaEngine(db, agent_id)
    if not persona.has_persona:
        raise HTTPException(status_code=404, detail="Persona não encontrada")

    try:
        persona.update_blueprint(request.section, request.data)
        return {"status": "success", "section": request.section, "message": "Blueprint actualizado"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/personas/{agent_id}/state", tags=["Personas"])
async def get_persona_state(agent_id: str, db: Session = Depends(get_db)):
    """Obtém estado dinâmico actual da persona (emoções, energia, needs, etc.)"""

    persona = PersonaEngine(db, agent_id)

    return {
        "agent_id": agent_id,
        "state": persona.get_state_summary(),
        "unmet_needs": persona.get_unmet_needs(),
        "in_crisis": persona.is_in_crisis(),
    }


@app.post("/personas/{agent_id}/reset-state", tags=["Personas"])
async def reset_persona_state(agent_id: str, db: Session = Depends(get_db)):
    """Reset do estado emocional da persona para valores iniciais"""

    persona = PersonaEngine(db, agent_id)
    persona.reset_emotional_state()

    return {
        "status": "success",
        "message": "Estado emocional resetado",
        "new_state": persona.get_state_summary()
    }


# ============================================================================
# ENDPOINTS - CHAT (CONVERSA NATURAL PERSISTENTE)
# ============================================================================

@app.post("/personas/{agent_id}/chat", tags=["Chat"])
async def chat_with_persona(
    agent_id: str,
    request: ChatRequest,
    db: Session = Depends(get_db)
):
    """
    Chat natural com persona. Conversas persistem em DB.
    O estado emocional persiste entre sessões.
    """

    service = AgentServiceCognitive(db)
    agent = service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agente {agent_id} não encontrado")

    try:
        start_time = time.time()

        orchestrator = CognitiveOrchestrator(db, agent_id)

        result = await orchestrator.think(
            query=request.message,
            context=request.context or {},
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            record_process=True
        )

        duration_ms = int((time.time() - start_time) * 1000)

        return {
            "conversation_id": result.get("conversation_id"),
            "agent_id": agent_id,
            "agent_name": agent.get("name") if isinstance(agent, dict) else getattr(agent, "name", ""),
            "agent_response": result.get("response", ""),
            "emotional_state": result.get("emotional_state"),
            "persona_state": result.get("persona_state"),
            "confidence": result.get("confidence"),
            "duration_ms": duration_ms
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Erro no chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# Manter endpoint antigo para compatibilidade
@app.post("/agents/{agent_id}/chat", tags=["Chat"])
async def chat_with_agent(agent_id: str, request: ChatRequest, db: Session = Depends(get_db)):
    """Chat com agente (redireciona para /personas/{id}/chat)"""
    return await chat_with_persona(agent_id, request, db)


@app.get("/personas/{agent_id}/conversations", tags=["Chat"])
async def list_persona_conversations(
    agent_id: str,
    user_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Lista conversas de uma persona"""

    conv_manager = ConversationManager(db, agent_id)
    sessions = conv_manager.get_all_sessions(user_id=user_id)

    return {"conversations": sessions, "total": len(sessions)}


@app.get("/personas/{agent_id}/conversations/{conversation_id}/history", tags=["Chat"])
async def get_conversation_history(
    agent_id: str,
    conversation_id: str,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Obtém histórico de mensagens de uma conversa"""

    conv_manager = ConversationManager(db, agent_id)
    messages = conv_manager.get_conversation_history(conversation_id, limit=limit)

    return {
        "conversation_id": conversation_id,
        "messages": messages,
        "total": len(messages)
    }


# ============================================================================
# ENDPOINTS - AGENTES (compatibilidade com v1)
# ============================================================================

@app.post("/agents", tags=["Agents"])
async def create_agent(request: CreateAgentRequest, db: Session = Depends(get_db)):
    """Cria agente (v1 - sem persona completa)"""

    service = AgentServiceCognitive(db)
    try:
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
        )
        return service.agent_to_dict(agent)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/agents", tags=["Agents"])
async def list_agents(
    active_only: bool = True, limit: int = 100, offset: int = 0,
    db: Session = Depends(get_db)
):
    service = AgentServiceCognitive(db)
    agents = service.list_agents(active_only=active_only, limit=limit, offset=offset)
    return [service.agent_to_dict(agent) for agent in agents]


@app.get("/agents/{agent_id}", tags=["Agents"])
async def get_agent(agent_id: str, db: Session = Depends(get_db)):
    service = AgentServiceCognitive(db)
    agent = service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    return service.agent_to_dict(agent)


@app.put("/agents/{agent_id}", tags=["Agents"])
async def update_agent(agent_id: str, updates: Dict[str, Any], db: Session = Depends(get_db)):
    service = AgentServiceCognitive(db)
    agent = service.update_agent(agent_id, **updates)
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    return service.agent_to_dict(agent)


@app.delete("/agents/{agent_id}", tags=["Agents"])
async def delete_agent(agent_id: str, db: Session = Depends(get_db)):
    service = AgentServiceCognitive(db)
    if not service.delete_agent(agent_id):
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    return {"message": f"Agente {agent_id} removido"}


# ============================================================================
# ENDPOINTS - PENSAMENTO COGNITIVO
# ============================================================================

@app.post("/agents/{agent_id}/think", tags=["Cognition"])
async def agent_think(agent_id: str, request: ThinkRequest, db: Session = Depends(get_db)):
    service = AgentServiceCognitive(db)
    try:
        query = request.message or request.query
        if not query:
            raise ValueError("'message' ou 'query' é obrigatório")

        result = await service.think(
            agent_id=agent_id, query=query,
            user_id=request.user_id,
            conversation_id=request.conversation_id,
            context=request.context
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENDPOINTS - EMOÇÕES E IDENTIDADE
# ============================================================================

@app.get("/agents/{agent_id}/emotional-state", tags=["Emotions"])
async def get_emotional_state(agent_id: str, db: Session = Depends(get_db)):
    from agent_system.emotional_engine import EmotionalEngine
    engine = EmotionalEngine(db, agent_id)
    return {
        "agent_id": agent_id,
        "emotional_state": engine.get_emotional_summary()
    }


@app.get("/agents/{agent_id}/identity", tags=["Identity"])
async def get_agent_identity(agent_id: str, db: Session = Depends(get_db)):
    from agent_system.identity_builder import IdentityBuilder
    identity = IdentityBuilder(db, agent_id)
    return {
        "agent_id": agent_id,
        "identity_prompt": identity.get_identity_prompt(),
        "voice_guidelines": identity.get_voice_guidelines(),
    }


# ============================================================================
# ENDPOINTS - FEEDBACK E APRENDIZAGEM
# ============================================================================

@app.post("/agents/{agent_id}/feedback", tags=["Learning"])
async def submit_feedback(agent_id: str, request: FeedbackRequest, db: Session = Depends(get_db)):
    service = AgentServiceCognitive(db)
    agent = service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")

    orchestrator = CognitiveOrchestrator(db, agent_id)
    result = orchestrator.process_feedback(
        interaction_id=request.interaction_id,
        feedback_type=request.feedback_type,
        feedback_score=request.feedback_score or 0.0,
        feedback_text=request.feedback_text
    )
    return {"status": "success", "learning_applied": True, **result}


# ============================================================================
# ENDPOINTS - MEMÓRIAS
# ============================================================================

@app.get("/agents/{agent_id}/memories", tags=["Memory"])
async def list_memories(agent_id: str, db: Session = Depends(get_db)):
    service = AgentServiceCognitive(db)
    memories = service.get_agent_memories(agent_id)
    return {"memories": memories}


@app.post("/agents/{agent_id}/memories", tags=["Memory"])
async def create_memory(agent_id: str, request: MemoryRequest, db: Session = Depends(get_db)):
    try:
        mm = MemoryManager(db, agent_id)
        memory = mm.create_memory(
            title=request.title, content=request.content,
            memory_type=request.memory_type,
            importance_score=request.importance_score,
            emotional_valence=request.emotional_valence,
            is_autobiographical=request.is_autobiographical,
            relates_to_topics=request.relates_to_topics,
        )
        return {"id": memory.id, "title": memory.title}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agents/{agent_id}/memories/search", tags=["Memory"])
async def search_memories(agent_id: str, request: SearchMemoriesRequest, db: Session = Depends(get_db)):
    try:
        mm = MemoryManager(db, agent_id)
        memories = mm.search_memories_semantic(
            query=request.query, top_k=request.top_k, memory_types=request.memory_types
        )
        return {
            "results": [
                {"id": m.id, "title": m.title, "type": m.type.name if m.type else "unknown",
                 "importance": m.importance_score}
                for m in memories
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ENDPOINTS - DOCUMENTOS
# ============================================================================

@app.get("/agents/{agent_id}/documents", tags=["Documents"])
async def list_documents(agent_id: str, db: Session = Depends(get_db)):
    service = DocumentServiceCognitive(db)
    documents = service.get_agent_documents(agent_id)
    return {"documents": [service.document_to_dict(doc) for doc in documents]}


@app.post("/agents/{agent_id}/documents/upload", tags=["Documents"])
async def upload_document(
    agent_id: str, file: UploadFile = File(...),
    description: Optional[str] = None, db: Session = Depends(get_db)
):
    service = DocumentServiceCognitive(db)
    try:
        content = await file.read()
        document = service.upload_document(
            agent_id=agent_id, filename=file.filename or "document",
            file_content=content, description=description,
        )
        return service.document_to_dict(document)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/agents/{agent_id}/documents/search", tags=["Documents"])
async def search_documents(agent_id: str, request: DocumentSearchRequest, db: Session = Depends(get_db)):
    service = DocumentServiceCognitive(db)
    results = service.search_documents_semantic(agent_id=agent_id, query=request.query, top_k=request.top_k)
    return {"results": results}


# ============================================================================
# ENDPOINTS - MICRO-AGENTES
# ============================================================================

@app.get("/agents/{agent_id}/micro-agents", tags=["Cognition"])
async def list_micro_agents(agent_id: str, db: Session = Depends(get_db)):
    service = AgentServiceCognitive(db)
    return {"micro_agents": service.get_agent_micro_agents(agent_id)}


@app.post("/agents/{agent_id}/micro-agents/reinitialize", tags=["Cognition"])
async def reinitialize_micro_agents(agent_id: str, db: Session = Depends(get_db)):
    service = AgentServiceCognitive(db)
    agent = service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")

    from data.schema_cognitive import MicroAgent
    db.query(MicroAgent).filter(MicroAgent.agent_id == agent_id).delete()
    db.commit()
    service._create_agent_micro_agents(agent_id)
    micro_agents = service.get_agent_micro_agents(agent_id)
    return {"message": "Micro-agentes reinicializados", "micro_agents_count": len(micro_agents)}


# ============================================================================
# ENDPOINTS - LEARNING STATS
# ============================================================================

@app.get("/agents/{agent_id}/learning-stats", tags=["Learning"])
async def get_learning_stats(agent_id: str, db: Session = Depends(get_db)):
    from data.schema_cognitive import LearningEvent, SynapticConnection
    from sqlalchemy import func

    events = db.query(LearningEvent).filter(LearningEvent.agent_id == agent_id).count()
    connections = db.query(SynapticConnection).filter(SynapticConnection.agent_id == agent_id).count()
    by_type = db.query(LearningEvent.feedback_type, func.count(LearningEvent.id)).filter(
        LearningEvent.agent_id == agent_id
    ).group_by(LearningEvent.feedback_type).all()

    return {
        "agent_id": agent_id,
        "total_learning_events": events,
        "synaptic_connections": connections,
        "events_by_type": {t: c for t, c in by_type if t}
    }


# ============================================================================
# ROOT
# ============================================================================

@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Sistema de Humanos Virtuais v3.0",
        "status": "active",
        "endpoints": {
            "create_persona": "POST /personas",
            "chat": "POST /personas/{id}/chat",
            "blueprint": "GET /personas/{id}/blueprint",
            "state": "GET /personas/{id}/state",
            "template": "GET /personas/template",
            "docs": "/docs"
        }
    }


@app.get("/chat", tags=["Chat"])
async def serve_chat():
    chat_file = os.path.join(os.path.dirname(__file__), "..", "static", "chat.html")
    if os.path.exists(chat_file):
        return FileResponse(chat_file)
    raise HTTPException(status_code=404, detail="Chat interface not found")
