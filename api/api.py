"""
API REST - Sistema de Humanos Virtuais
Endpoints para criar, gerir e interagir com personas humanas

Como correr: python -m uvicorn api.api:app --reload
"""

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import time
from sqlalchemy.orm import Session

# Database
from data.database_cognitive import init_cognitive_db, get_db_session
from data.schema_cognitive import Agent
import data.schema_auth  # noqa: F401 - registar modelo User na Base

# Services
from agent_system.agent_service_cognitive import AgentServiceCognitive
from agent_system.cognitive_orchestrator import CognitiveOrchestrator
from agent_system.persona_engine import PersonaEngine
from document_handlers.document_service_cognitive import DocumentServiceCognitive
from config.embedding_cache import preload_embedding_model

import logging
import os
from dotenv import load_dotenv

load_dotenv()

from config.logging_config import setup_logging
setup_logging(os.getenv("LOG_LEVEL", "INFO"))

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
from api.auth import router as auth_router, get_current_user
from data.schema_auth import User
app.include_router(auth_router)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:admin@localhost:5432/cognitive_agents")
init_cognitive_db(DATABASE_URL)


@app.on_event("startup")
async def startup_event():
    logger.info("Servidor a iniciar — Human Simulation API v3.0")
    preload_embedding_model()

    from sqlalchemy import create_engine, text
    engine = create_engine(DATABASE_URL)
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='agents' AND column_name='owner_id'
                    ) THEN
                        ALTER TABLE agents ADD COLUMN owner_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE;
                        CREATE INDEX IF NOT EXISTS ix_agents_owner_id ON agents(owner_id);
                    END IF;
                END $$;
            """))
    except Exception as e:
        logger.warning(f"Migration owner_id: {e}")

    from api.auth import seed_admin_user
    db = get_db_session(DATABASE_URL)
    try:
        seed_admin_user(db)
    finally:
        db.close()

    logger.info("Servidor pronto")


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


class CreatePersonaRequest(BaseModel):
    name: str
    description: Optional[str] = None
    avatar: Optional[str] = "👤"
    background_story: Optional[str] = None
    persona: Optional[Dict[str, Any]] = None
    personality_traits: Optional[Dict] = None
    thinking_style: Optional[str] = "balanced"
    decision_making_approach: Optional[str] = "collaborative"
    debate_intensity: Optional[float] = 0.7
    micro_agent_types: Optional[List[str]] = None
    initial_memories: Optional[List[InitialMemory]] = None


class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = "default_user"
    conversation_id: Optional[str] = None
    context: Optional[Dict] = None


class UpdateBlueprintRequest(BaseModel):
    section: str
    data: Dict[str, Any]


# ============================================================================
# DEPENDENCY
# ============================================================================

def get_db():
    db = get_db_session(DATABASE_URL)
    try:
        yield db
    finally:
        db.close()


def _ensure_owner(agent, user: User):
    """Garante que o utilizador é dono do agente ou admin."""
    if user.role == "admin":
        return
    if agent.owner_id and agent.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Não tens acesso a este agente")


# ============================================================================
# ENDPOINTS - PERSONAS
# ============================================================================

@app.post("/personas", tags=["Personas"])
async def create_persona(
    request: CreatePersonaRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AgentServiceCognitive(db)

    try:
        traits = request.personality_traits or {}
        if request.persona:
            big_five = request.persona.get("personality_full", {}).get("big_five", {})
            if big_five:
                traits = {**traits, **big_five}

        if not traits:
            traits = {"openness": 0.6, "conscientiousness": 0.6, "extraversion": 0.5,
                      "agreeableness": 0.7, "neuroticism": 0.3}

        agent = service.create_agent(
            name=request.name,
            description=request.description or f"{request.name} é um humano virtual.",
            personality_traits=traits,
            background_story=request.background_story,
            thinking_style=request.thinking_style,
            decision_making_approach=request.decision_making_approach,
            debate_intensity=request.debate_intensity,
            initial_memories=[m.dict() for m in request.initial_memories] if request.initial_memories else None,
            micro_agent_types=request.micro_agent_types,
            avatar=request.avatar,
            owner_id=current_user.id,
        )

        agent_id = agent.id
        persona_engine = PersonaEngine(db, agent_id)
        persona_data = request.persona or {}

        if request.personality_traits and "personality_full" not in persona_data:
            persona_data["personality_full"] = {"big_five": request.personality_traits}

        if request.background_story and "identity" not in persona_data:
            persona_data["identity"] = {}

        persona_engine.create_persona(persona_data)

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


@app.get("/personas/{agent_id}/blueprint", tags=["Personas"])
async def get_persona_blueprint(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    _ensure_owner(agent, current_user)
    persona = PersonaEngine(db, agent_id)
    if not persona.has_persona:
        raise HTTPException(status_code=404, detail="Persona não encontrada")

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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    _ensure_owner(agent, current_user)
    persona = PersonaEngine(db, agent_id)
    if not persona.has_persona:
        raise HTTPException(status_code=404, detail="Persona não encontrada")

    try:
        persona.update_blueprint(request.section, request.data)
        return {"status": "success", "section": request.section, "message": "Blueprint actualizado"}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ============================================================================
# ENDPOINTS - CHAT
# ============================================================================

@app.post("/personas/{agent_id}/chat", tags=["Chat"])
async def chat_with_persona(
    agent_id: str,
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AgentServiceCognitive(db)
    agent = service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agente {agent_id} não encontrado")
    _ensure_owner(agent, current_user)

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


# ============================================================================
# ENDPOINTS - AGENTES
# ============================================================================

@app.get("/agents", tags=["Agents"])
async def list_agents(
    active_only: bool = True,
    limit: int = 100,
    offset: int = 0,
    all_users: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AgentServiceCognitive(db)
    owner_filter = None if (all_users and current_user.role == "admin") else current_user.id
    agents = service.list_agents(
        active_only=active_only, limit=limit, offset=offset, owner_id=owner_filter
    )
    return [service.agent_to_dict(agent) for agent in agents]


@app.get("/agents/{agent_id}", tags=["Agents"])
async def get_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AgentServiceCognitive(db)
    agent = service.get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    _ensure_owner(agent, current_user)
    return service.agent_to_dict(agent)


@app.put("/agents/{agent_id}", tags=["Agents"])
async def update_agent(
    agent_id: str,
    updates: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AgentServiceCognitive(db)
    existing = service.get_agent(agent_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    _ensure_owner(existing, current_user)

    agent = service.update_agent(agent_id, **updates)
    return service.agent_to_dict(agent)


@app.delete("/agents/{agent_id}", tags=["Agents"])
async def delete_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = AgentServiceCognitive(db)
    existing = service.get_agent(agent_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    _ensure_owner(existing, current_user)

    if not service.delete_agent(agent_id):
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    return {"message": f"Agente {agent_id} removido"}


# ============================================================================
# ENDPOINTS - MEMÓRIAS
# ============================================================================

@app.get("/agents/{agent_id}/memories", tags=["Memory"])
async def list_memories(agent_id: str, db: Session = Depends(get_db)):
    service = AgentServiceCognitive(db)
    memories = service.get_agent_memories(agent_id)
    return {"memories": memories}


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


# ============================================================================
# ENDPOINTS - MICRO-AGENTES
# ============================================================================

@app.get("/agents/{agent_id}/micro-agents", tags=["Cognition"])
async def list_micro_agents(agent_id: str, db: Session = Depends(get_db)):
    service = AgentServiceCognitive(db)
    return {"micro_agents": service.get_agent_micro_agents(agent_id)}


# ============================================================================
# ENDPOINTS - DASHBOARD STATS
# ============================================================================

@app.get("/dashboard/stats", tags=["Dashboard"])
async def get_dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from data.schema_cognitive import (
        Memory, Document, MicroAgent,
        ConversationSession, ConversationMessage,
        LearningEvent,
    )
    from sqlalchemy import func

    uid = current_user.id

    user_agents = db.query(Agent).filter(Agent.owner_id == uid, Agent.deleted_at.is_(None)).all()
    agent_ids = [a.id for a in user_agents]

    total_agents = len(user_agents)
    active_agents = sum(1 for a in user_agents if a.is_active)

    total_memories = 0
    total_documents = 0
    total_micro_agents = 0
    total_conversations = 0
    total_messages = 0
    total_learning = 0

    if agent_ids:
        total_memories = db.query(func.count(Memory.id)).filter(Memory.agent_id.in_(agent_ids)).scalar() or 0
        total_documents = db.query(func.count(Document.id)).filter(Document.agent_id.in_(agent_ids)).scalar() or 0
        total_micro_agents = db.query(func.count(MicroAgent.id)).filter(MicroAgent.agent_id.in_(agent_ids)).scalar() or 0
        total_conversations = db.query(func.count(ConversationSession.id)).filter(ConversationSession.agent_id.in_(agent_ids)).scalar() or 0
        total_messages = (
            db.query(func.count(ConversationMessage.id))
            .join(ConversationSession, ConversationMessage.session_id == ConversationSession.id)
            .filter(ConversationSession.agent_id.in_(agent_ids))
            .scalar() or 0
        )
        total_learning = db.query(func.count(LearningEvent.id)).filter(LearningEvent.agent_id.in_(agent_ids)).scalar() or 0

    agents_summary = []
    for a in user_agents:
        mem_count = db.query(func.count(Memory.id)).filter(Memory.agent_id == a.id).scalar() or 0
        doc_count = db.query(func.count(Document.id)).filter(Document.agent_id == a.id).scalar() or 0
        conv_count = db.query(func.count(ConversationSession.id)).filter(ConversationSession.agent_id == a.id).scalar() or 0
        msg_count = (
            db.query(func.count(ConversationMessage.id))
            .join(ConversationSession, ConversationMessage.session_id == ConversationSession.id)
            .filter(ConversationSession.agent_id == a.id)
            .scalar() or 0
        )
        agents_summary.append({
            "id": a.id,
            "name": a.name,
            "avatar": a.avatar,
            "is_active": a.is_active,
            "thinking_style": a.thinking_style,
            "memories": mem_count,
            "documents": doc_count,
            "conversations": conv_count,
            "messages": msg_count,
            "last_interaction": a.last_interaction.isoformat() if a.last_interaction else None,
            "created_at": a.created_at.isoformat() if a.created_at else None,
        })

    recent_conversations = []
    if agent_ids:
        recent_sessions = (
            db.query(ConversationSession)
            .filter(ConversationSession.agent_id.in_(agent_ids))
            .order_by(ConversationSession.started_at.desc())
            .limit(10)
            .all()
        )
        for s in recent_sessions:
            agent_name = next((a.name for a in user_agents if a.id == s.agent_id), "?")
            agent_avatar = next((a.avatar for a in user_agents if a.id == s.agent_id), "🤖")
            recent_conversations.append({
                "id": s.id,
                "agent_id": s.agent_id,
                "agent_name": agent_name,
                "agent_avatar": agent_avatar,
                "message_count": s.message_count or 0,
                "current_topic": s.current_topic,
                "emotional_tone": s.emotional_tone,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "is_active": s.is_active,
            })

    return {
        "totals": {
            "agents": total_agents,
            "active_agents": active_agents,
            "memories": total_memories,
            "documents": total_documents,
            "micro_agents": total_micro_agents,
            "conversations": total_conversations,
            "messages": total_messages,
            "learning_events": total_learning,
        },
        "agents": agents_summary,
        "recent_conversations": recent_conversations,
        "user": {
            "name": current_user.name,
            "created_at": current_user.created_at.isoformat() if current_user.created_at else None,
        },
    }
