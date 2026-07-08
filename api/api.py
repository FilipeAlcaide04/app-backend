"""
API REST - Sistema de Humanos Virtuais
Endpoints para criar, gerir e interagir com personas humanas

Como correr: python -m uvicorn api.api:app --reload
"""

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import time
import io
import json
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
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='agents' AND column_name='language'
                    ) THEN
                        ALTER TABLE agents ADD COLUMN language VARCHAR(10) DEFAULT 'pt-PT';
                    END IF;
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='thought_processes' AND column_name='conversation_id'
                    ) THEN
                        ALTER TABLE thought_processes ADD COLUMN conversation_id VARCHAR(36)
                            REFERENCES conversation_sessions(id) ON DELETE SET NULL;
                        CREATE INDEX IF NOT EXISTS ix_thought_processes_conversation_id
                            ON thought_processes(conversation_id);
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

    _migrate_prompt_user_knowledge(DATABASE_URL)
    _migrate_prompt_emotional_regulation(DATABASE_URL)
    _migrate_prompt_identity_framing(DATABASE_URL)

    logger.info("Servidor pronto")


def _migrate_prompt_user_knowledge(database_url: str):
    from data.schema_cognitive import PromptTemplate
    db = get_db_session(database_url)
    try:
        prompt = db.query(PromptTemplate).filter(PromptTemplate.key == "core.final_response").first()
        if prompt and "{user_knowledge_text}" not in (prompt.template or ""):
            prompt.template = prompt.template.replace(
                "{imagined_memory_text}\n\n---\n\nINSTRUÇÕES DE RESPOSTA HUMANA:",
                "{imagined_memory_text}\n\n{user_knowledge_text}\n\n---\n\nINSTRUÇÕES DE RESPOSTA HUMANA:",
            )
            if "user_knowledge_text" not in (prompt.variables or []):
                prompt.variables = (prompt.variables or []) + ["user_knowledge_text"]
            db.commit()
            logger.info("Prompt core.final_response atualizado com user_knowledge_text")
    except Exception as e:
        logger.warning(f"Migration prompt user_knowledge: {e}")
    finally:
        db.close()


def _migrate_prompt_emotional_regulation(database_url: str):
    from data.schema_cognitive import PromptTemplate
    db = get_db_session(database_url)
    try:
        prompt = db.query(PromptTemplate).filter(PromptTemplate.key == "core.final_response").first()
        if not prompt:
            return

        old_line = "- As tuas emoções actuais importam, mas não podem apagar toda a realidade da conversa."
        new_block = (
            "- As tuas emoções actuais importam, mas não podem apagar toda a realidade da conversa. "
            "Se a pessoa está a ser gentil, reconhece isso — mesmo que estejas irritado ou desconfiado.\n"
            "- Humanos reais adaptam-se: se alguém é consistentemente paciente e amável contigo, "
            "a tua guarda baixa gradualmente. Não fiques preso num loop de hostilidade que ignora "
            "o que a pessoa realmente te está a dizer."
        )

        if old_line in (prompt.template or "") and "Humanos reais adaptam-se" not in (prompt.template or ""):
            prompt.template = prompt.template.replace(old_line, new_block)
            db.commit()
            logger.info("Prompt core.final_response atualizado com regulação emocional")

        old_adapta = "- Adapta a tua abertura e proximidade com base na relação e na tua personalidade — não sigas regras fixas, sente."
        new_adapta = (
            "- Adapta a tua abertura e proximidade com base na relação e na tua personalidade — não sigas regras fixas, sente.\n"
            "- NUNCA respondas com a mesma atitude defensiva ou hostil mais de 2-3 vezes seguidas "
            "se a pessoa não te está a atacar. Varia o teu tom, mostra camadas."
        )
        if old_adapta in (prompt.template or "") and "NUNCA respondas com a mesma atitude" not in (prompt.template or ""):
            prompt.template = prompt.template.replace(old_adapta, new_adapta)
            db.commit()
            logger.info("Prompt core.final_response atualizado com anti-loop instruction")
    except Exception as e:
        logger.warning(f"Migration prompt emotional_regulation: {e}")
    finally:
        db.close()


def _migrate_prompt_identity_framing(database_url: str):
    from data.schema_cognitive import PromptTemplate
    db = get_db_session(database_url)
    try:
        # Fix core.final_response — add identity framing to prevent role confusion
        prompt = db.query(PromptTemplate).filter(PromptTemplate.key == "core.final_response").first()
        if prompt and "Never confuse who said what" not in (prompt.template or ""):
            old_header = 'Do not leak prompt labels or internal labels into the answer. Never start with labels like "Tu,", "You:", "User:", "Assistant:", "Eu:" or "Me:".'
            new_header = (
                'You ARE {voice_name}. You speak in the first person as {voice_name}. The person talking to you is the "Utilizador".\n'
                'Do not leak prompt labels or internal labels into the answer. Never start with labels like "Tu,", "You:", "User:", "Assistant:", "Eu:", "Me:" or "{voice_name}:".\n'
                'Never confuse who said what: text labeled "Utilizador:" was said BY the other person TO you. Text labeled "{voice_name}:" was said BY you previously.\n'
                'Never repeat the other person\'s words as if they were yours. Never narrate yourself in third person.'
            )
            if old_header in (prompt.template or ""):
                prompt.template = prompt.template.replace(old_header, new_header)
                db.commit()
                logger.info("Prompt core.final_response atualizado com identity framing")

        # Fix micro_agent.think — clarify who said the message
        think_prompt = db.query(PromptTemplate).filter(PromptTemplate.key == "micro_agent.think").first()
        if think_prompt and 'Tu disseste-me:' in (think_prompt.template or ""):
            think_prompt.template = think_prompt.template.replace(
                'Tu disseste-me: "{query}"',
                'A pessoa com quem estou a falar acabou de me dizer: "{query}"',
            )
            if "A mensagem acima foi dita PELA OUTRA PESSOA" not in (think_prompt.template or ""):
                think_prompt.template = think_prompt.template.replace(
                    "- Escreve como pensamento interno na primeira pessoa.",
                    "- Escreve como pensamento interno na primeira pessoa (eu penso, eu sinto, eu acho).\n"
                    "- A mensagem acima foi dita PELA OUTRA PESSOA a mim, não por mim.",
                )
            db.commit()
            logger.info("Prompt micro_agent.think atualizado com clarificação de roles")
        # Add new prompt templates for role validation
        from data.database.setup import PROMPT_TEMPLATES
        for tmpl in PROMPT_TEMPLATES:
            if tmpl["key"] in ("core.response_role_check", "core.response_role_repair"):
                existing = db.query(PromptTemplate).filter(PromptTemplate.key == tmpl["key"]).first()
                if not existing:
                    new_pt = PromptTemplate(
                        key=tmpl["key"],
                        name=tmpl["name"],
                        category=tmpl["category"],
                        description=tmpl["description"],
                        language=tmpl.get("language", "pt-PT"),
                        version=tmpl.get("version", 1),
                        variables=tmpl.get("variables", []),
                        template=tmpl["template"],
                        is_active=True,
                    )
                    db.add(new_pt)
                    db.commit()
                    logger.info(f"Prompt {tmpl['key']} criado")

    except Exception as e:
        logger.warning(f"Migration prompt identity_framing: {e}")
    finally:
        db.close()


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
    language: Optional[str] = "pt-PT"
    background_story: Optional[str] = None
    persona: Optional[Dict[str, Any]] = None
    personality_traits: Optional[Dict] = None
    thinking_style: Optional[str] = "balanced"
    decision_making_approach: Optional[str] = "collaborative"
    debate_intensity: Optional[float] = 0.7
    micro_agent_types: Optional[List[str]] = None
    initial_memories: Optional[List[InitialMemory]] = None
    is_shared: Optional[bool] = False


class ChatRequest(BaseModel):
    message: str
    user_id: Optional[str] = "default_user"
    conversation_id: Optional[str] = None
    context: Optional[Dict] = None


class TTSRequest(BaseModel):
    text: str
    voice: Optional[str] = None
    gender: Optional[str] = "female"
    language: Optional[str] = "pt-PT"
    emotion: Optional[str] = "neutral"


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


def _is_shared_agent(agent, db: Session) -> bool:
    """Verifica se o agente está marcado como partilhado no blueprint meta."""
    from data.schema_persona import PersonaBlueprint
    blueprint = db.query(PersonaBlueprint).filter(
        PersonaBlueprint.agent_id == agent.id
    ).first()
    if blueprint and isinstance(blueprint.meta, dict):
        return blueprint.meta.get("is_shared", False)
    return False


def _ensure_owner(agent, user: User, db: Session = None, allow_shared: bool = False):
    """Garante que o utilizador é dono do agente ou admin.
    Se allow_shared=True e o agente é partilhado, permite acesso de leitura/chat.
    """
    if user.role == "admin":
        return
    if agent.owner_id and agent.owner_id != user.id:
        if allow_shared and db and _is_shared_agent(agent, db):
            return
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
            language=request.language or "pt-PT",
        )

        agent_id = agent.id
        persona_engine = PersonaEngine(db, agent_id)
        persona_data = request.persona or {}

        if request.personality_traits and "personality_full" not in persona_data:
            persona_data["personality_full"] = {"big_five": request.personality_traits}

        if request.background_story and "identity" not in persona_data:
            persona_data["identity"] = {}

        if request.is_shared:
            persona_data.setdefault("meta", {})["is_shared"] = True

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
                "is_shared": bool(request.is_shared),
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
    _ensure_owner(agent, current_user, db=db, allow_shared=True)
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
    _ensure_owner(agent, current_user, db=db, allow_shared=True)

    try:
        start_time = time.time()
        orchestrator = CognitiveOrchestrator(db, agent_id)

        chat_context = request.context or {}
        chat_context["user_name"] = current_user.name

        result = await orchestrator.think(
            query=request.message,
            context=chat_context,
            user_id=current_user.id,
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
            "relationship": result.get("relationship"),
            "confidence": result.get("confidence"),
            "duration_ms": duration_ms,
            "thought_contributions": result.get("thought_contributions", []),
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Erro no chat: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/personas/{agent_id}/greeting", tags=["Chat"])
async def get_greeting(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Gera saudação dinâmica baseada na relação, memórias e estado emocional."""
    from agent_system.identity_builder import IdentityBuilder
    from agent_system.persona_engine import PersonaEngine
    from agent_system.memory_manager_cognitive import MemoryManager
    from agent_system.conversation_manager import ConversationManager
    from agent_system.prompt_manager import PromptManager
    from llm_logic.llm_client import get_llm_client

    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    _ensure_owner(agent, current_user, db=db, allow_shared=True)

    identity = IdentityBuilder(db, agent_id)
    persona = PersonaEngine(db, agent_id)
    memory = MemoryManager(db, agent_id)
    conversations = ConversationManager(db, agent_id)
    prompts = PromptManager(db)

    # Relação com este user
    rel_section = identity._section_relationship(current_user.id)
    relationship = identity.get_relationship_snapshot(current_user.id)
    state_summary = persona.get_state_summary() if persona.has_persona else {}
    mood = state_summary.get("mood", "neutro")
    energy = state_summary.get("energy", 0.7)
    stress = state_summary.get("stress_level", 0.2)
    primary_emotion = state_summary.get("primary_emotion", "neutral")

    # Memórias sobre o user — buscar por ID e por nome para cobertura total
    user_memories_by_id = memory.recall_relevant_memories(current_user.id, limit=10)
    user_memories_by_name = memory.recall_relevant_memories(current_user.name or "", limit=10) if current_user.name else []
    seen_ids = set()
    all_user_memories = []
    for m in user_memories_by_id + user_memories_by_name:
        if m.id not in seen_ids:
            seen_ids.add(m.id)
            all_user_memories.append(m)
    mem_text = "\n".join([f"- {m.title}: {m.content[:150]}" for m in all_user_memories[:8]]) if all_user_memories else "Sem memórias deste utilizador."

    # Última sessão — sumário + coisas por resolver
    last_state = conversations.get_last_session_state(current_user.id)
    last_session_text = ""
    if last_state:
        parts = []
        if last_state.get("summary"):
            parts.append(f"Última conversa: {last_state['summary'][:300]}")
        if last_state.get("unresolved"):
            parts.append(f"Coisas que ficaram pendentes: {'; '.join(str(q) for q in last_state['unresolved'][:3])}")
        if last_state.get("key_points"):
            parts.append(f"Pontos importantes: {'; '.join(str(p) for p in last_state['key_points'][:3])}")
        if last_state.get("emotional_tone"):
            parts.append(f"Tom emocional da última conversa: {last_state['emotional_tone']}")
        if last_state.get("ended_at"):
            parts.append(f"Quando: {last_state['ended_at']}")
        last_session_text = "\n".join(parts)

    voice = identity.get_voice_guidelines()

    prompt = prompts.render(
        "greeting.dynamic",
        identity_prompt=identity.get_identity_prompt(current_user.id),
        mood=mood,
        energy=f"{energy:.1f}",
        stress=f"{stress:.2f}",
        primary_emotion=primary_emotion,
        user_name=current_user.name,
        relationship=rel_section or "Pessoa nova, ainda não conheço.",
        memories=mem_text,
        last_session=last_session_text,
        language=getattr(agent, "language", "pt-PT"),
        voice_name=voice.get("name", agent.name),
    )

    try:
        llm = get_llm_client()
        raw = llm.generate(prompt, max_tokens=180, temperature=0.85).strip()
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}")
            parsed = json.loads(raw[start:end + 1]) if start >= 0 and end > start else {}

        should_greet = bool(parsed.get("should_greet"))
        greeting = str(parsed.get("greeting") or "").strip() if should_greet else ""
        confidence = parsed.get("confidence")
        if not isinstance(confidence, (int, float)):
            confidence = None

        return {
            "should_greet": should_greet and bool(greeting),
            "greeting": greeting,
            "mood": mood,
            "energy": energy,
            "persona_state": state_summary,
            "relationship": relationship,
            "confidence": max(0, min(1, float(confidence))) if confidence is not None else None,
        }
    except Exception as e:
        logger.error(f"Erro ao gerar saudação: {e}")
        return {
            "should_greet": False,
            "greeting": "",
            "mood": mood,
            "energy": energy,
            "persona_state": state_summary,
            "relationship": relationship,
            "confidence": None,
        }


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

    # Include shared agents from other users
    if owner_filter is not None:
        from data.schema_persona import PersonaBlueprint
        from sqlalchemy import cast, String
        shared_blueprints = db.query(PersonaBlueprint).filter(
            cast(PersonaBlueprint.meta["is_shared"], String) == "true"
        ).all()
        own_ids = {a.id for a in agents}
        for bp in shared_blueprints:
            if bp.agent_id not in own_ids:
                shared_agent = service.get_agent(bp.agent_id)
                if shared_agent and shared_agent.is_active and shared_agent.deleted_at is None:
                    agents.append(shared_agent)

    return [service.agent_to_dict(agent, db=db) for agent in agents]


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
    _ensure_owner(agent, current_user, db=db, allow_shared=True)
    return service.agent_to_dict(agent, db=db)


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
    return service.agent_to_dict(agent, db=db)


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


class DeleteMemoriesRequest(BaseModel):
    memory_ids: Optional[List[str]] = None


@app.delete("/agents/{agent_id}/memories", tags=["Memory"])
async def delete_memories(
    agent_id: str,
    body: Optional[DeleteMemoriesRequest] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from data.schema_cognitive import Memory, MemoryEmbedding, RelationshipBond

    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.owner_id == current_user.id,
        Agent.deleted_at.is_(None),
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")

    memory_ids = body.memory_ids if body and body.memory_ids else None

    if memory_ids:
        mem_filter = Memory.agent_id == agent_id, Memory.id.in_(memory_ids)
        embedding_ids = db.query(MemoryEmbedding.id).join(Memory).filter(*mem_filter)
        db.query(MemoryEmbedding).filter(MemoryEmbedding.id.in_(embedding_ids.subquery())).delete(synchronize_session=False)
        deleted_count = db.query(Memory).filter(*mem_filter).delete(synchronize_session=False)
    else:
        embedding_ids = db.query(MemoryEmbedding.id).join(Memory).filter(Memory.agent_id == agent_id)
        db.query(MemoryEmbedding).filter(MemoryEmbedding.id.in_(embedding_ids.subquery())).delete(synchronize_session=False)
        deleted_count = db.query(Memory).filter(Memory.agent_id == agent_id).delete(synchronize_session=False)
        db.query(RelationshipBond).filter(RelationshipBond.agent_id == agent_id).delete(synchronize_session=False)

    db.commit()
    return {"message": f"{deleted_count} memórias apagadas", "deleted": deleted_count}


@app.post("/agents/{agent_id}/conversations/reset", tags=["Conversation"])
async def reset_conversation(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from data.schema_cognitive import ConversationSession, ConversationMessage

    agent = db.query(Agent).filter(
        Agent.id == agent_id,
        Agent.deleted_at.is_(None),
    ).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agente não encontrado")
    _ensure_owner(agent, current_user, db=db, allow_shared=True)

    sessions = db.query(ConversationSession).filter(
        ConversationSession.agent_id == agent_id,
        ConversationSession.user_id == current_user.id,
    ).all()

    session_ids = [s.id for s in sessions]
    if session_ids:
        db.query(ConversationMessage).filter(
            ConversationMessage.session_id.in_(session_ids)
        ).delete(synchronize_session=False)
        db.query(ConversationSession).filter(
            ConversationSession.id.in_(session_ids)
        ).delete(synchronize_session=False)

    # Also reset emotional state to prevent stuck negative spirals
    from agent_system.persona_engine import PersonaEngine
    try:
        persona = PersonaEngine(db, agent_id)
        if persona.has_persona:
            persona.reset_emotional_state()
    except Exception as e:
        logger.warning(f"Failed to reset emotional state: {e}")

    db.commit()
    return {"message": "Conversa reiniciada", "sessions_cleared": len(session_ids)}


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


# ============================================================================
# ENDPOINTS - TTS (Text-to-Speech via Edge TTS)
# ============================================================================

TTS_VOICES = {
    "pt-PT": {"female": "pt-PT-RaquelNeural", "male": "pt-PT-DuarteNeural"},
    "en-US": {"female": "en-US-AriaNeural", "male": "en-US-GuyNeural"},
}

EN_PROSODY = {
    "neutral":  {"rate": "+0%",  "pitch": "+0Hz"},
    "happy":    {"rate": "+8%",  "pitch": "+5Hz"},
    "sad":      {"rate": "-15%", "pitch": "-8Hz"},
    "angry":    {"rate": "+10%", "pitch": "+3Hz"},
    "excited":  {"rate": "+12%", "pitch": "+8Hz"},
    "calm":     {"rate": "-10%", "pitch": "-5Hz"},
    "fear":     {"rate": "+5%",  "pitch": "+10Hz"},
    "surprise": {"rate": "+5%",  "pitch": "+12Hz"},
    "love":     {"rate": "-5%",  "pitch": "+2Hz"},
}

PT_PROSODY = {
    "neutral":  {"rate": "-3%",  "pitch": "+0Hz"},
    "happy":    {"rate": "+5%",  "pitch": "+3Hz"},
    "sad":      {"rate": "-12%", "pitch": "-6Hz"},
    "angry":    {"rate": "+8%",  "pitch": "+2Hz"},
    "excited":  {"rate": "+10%", "pitch": "+5Hz"},
    "calm":     {"rate": "-8%",  "pitch": "-3Hz"},
}

def _get_prosody(language: str, emotion: str) -> tuple[str, str]:
    prosody_map = EN_PROSODY if language == "en-US" else PT_PROSODY
    prosody = prosody_map.get(emotion, prosody_map.get("neutral", {"rate": "+0%", "pitch": "+0Hz"}))
    return prosody.get("rate", "+0%"), prosody.get("pitch", "+0Hz")


@app.post("/tts", tags=["TTS"])
async def text_to_speech(request: TTSRequest):
    import edge_tts

    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Texto vazio")
    if len(text) > 5000:
        raise HTTPException(status_code=400, detail="Texto demasiado longo (max 5000 chars)")

    lang = request.language if request.language in TTS_VOICES else "pt-PT"
    gender = request.gender if request.gender in ("female", "male") else "female"
    voice_name = request.voice or TTS_VOICES[lang][gender]
    emotion = request.emotion or "neutral"

    rate, pitch = _get_prosody(lang, emotion)

    try:
        communicate = edge_tts.Communicate(
            text,
            voice_name,
            rate=rate,
            pitch=pitch,
        )
        audio_buffer = io.BytesIO()

        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.write(chunk["data"])

        audio_buffer.seek(0)

        return StreamingResponse(
            audio_buffer,
            media_type="audio/mpeg",
            headers={
                "Content-Disposition": "inline",
                "Cache-Control": "no-cache",
            },
        )
    except Exception as e:
        logger.error(f"Erro TTS: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Erro ao gerar áudio")
