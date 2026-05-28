"""
Auth API - Endpoints de autenticação segura
JWT tokens, bcrypt passwords, role-based access control
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from sqlalchemy import String, Text, or_
from datetime import datetime, timedelta
from typing import Optional, List, Any, Dict
from urllib.parse import urlencode
import jwt
import httpx
import os
import logging
import secrets

from data.schema_auth import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Auth"])

# Config
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# OAuth Config
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

security = HTTPBearer()


# ============================================================================
# MODELOS PYDANTIC
# ============================================================================

class LoginRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(BaseModel):
    name: str
    email: str
    password: str


class UpdateUserRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class AdminUpdateRequest(BaseModel):
    updates: Dict[str, Any]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


# ============================================================================
# JWT UTILS
# ============================================================================

def create_access_token(user_id: str, role: str) -> str:
    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")


# ============================================================================
# DEPENDENCIES
# ============================================================================

def get_db():
    """Cria sessão de BD para auth endpoints"""
    from data.database_cognitive import get_db_session
    database_url = os.getenv("DATABASE_URL", "postgresql://postgres:admin@localhost:5432/cognitive_agents")
    db = get_db_session(database_url)
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    payload = decode_token(credentials.credentials)
    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Utilizador não encontrado ou inactivo")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return current_user


PROMPT_LINKS = {
    "conversation.live_memory": [
        "ConversationManager.build_live_conversation_memory",
        "Contexto enviado a micro-agentes e à síntese final",
    ],
    "memory.awareness": [
        "MemoryManager.build_memory_awareness",
        "CognitiveOrchestrator/contexto de memórias",
        "CoreAgent._generate_persona_response",
    ],
    "core.final_response": [
        "CoreAgent._generate_persona_response",
        "Resposta final audível/enviada ao chat",
    ],
    "core.direct_address_repair": [
        "CoreAgent._repair_direct_address",
        "Reparação quando a resposta fala do utilizador em terceira pessoa",
    ],
    "core.direct_address_check": [
        "CoreAgent._repair_direct_address",
        "Decide semanticamente se a reparação é necessária",
    ],
    "core.self_reflection": [
        "CoreAgent._self_reflect",
        "Geração de memória de auto-reflexão",
    ],
    "emotion.intent_analysis": [
        "EmotionalEngine.analyze_user_intent",
        "Classificação emocional/relacional sem listas de palavras fixas",
    ],
    "relationship.signal": [
        "CoreAgent._classify_relationship_signal",
        "Atualização de confiança/familiaridade/afeto",
    ],
    "conversation.summary": [
        "ConversationManager._summarize_conversation",
        "Resumo de sessão para memória longa",
    ],
    "conversation.personal_info": [
        "ConversationManager._extract_personal_info",
        "Memórias relacionais extraídas de conversas",
    ],
    "conversation.valence": [
        "ConversationManager._estimate_valence",
        "Valência emocional das memórias episódicas",
    ],
    "memory.user_fact_extraction": [
        "CoreAgent._llm_extract_user_info",
        "Criação de memória relacional a partir da última interação",
    ],
    "memory.user_identity_extraction": [
        "CoreAgent._extract_user_name_semantic",
        "Atualização do nome/relação sem regex de apresentação",
    ],
    "learning.should_store_interaction": [
        "NeuralNetworkLayer._is_trivial_interaction",
        "Filtro semântico para evitar memórias de aprendizagem poluídas",
    ],
    "greeting.dynamic": [
        "GET /personas/{agent_id}/greeting",
        "Saudação inicial gerada pela própria persona",
    ],
    "micro_agent.think": [
        "LogicalAgent",
        "EmotionalAgent",
        "CriticalAgent",
        "CreativeAgent",
        "EthicalAgent",
        "SocialAgent",
    ],
    "micro_agent.memory_curator": [
        "MemoryCuratorAgent.think",
        "Decisão interna sobre o que guardar/ignorar",
    ],
    "micro_agent.imagination": [
        "ImaginationAgent.think",
        "Geração/expansão de memórias imaginadas coerentes",
    ],
    "micro_agent.imagination_gate": [
        "ImaginationAgent._should_imagine",
        "Evita que cumprimentos/desculpas/pedidos de escuta virem memórias imaginadas duradouras",
    ],
}


def _prompt_to_dict(prompt) -> Dict[str, Any]:
    return {
        "id": prompt.id,
        "key": prompt.key,
        "name": prompt.name,
        "category": prompt.category,
        "description": prompt.description,
        "template": prompt.template,
        "language": prompt.language,
        "version": prompt.version,
        "variables": prompt.variables or [],
        "is_active": prompt.is_active,
        "linked_to": PROMPT_LINKS.get(prompt.key, []),
        "created_at": prompt.created_at.isoformat() if prompt.created_at else None,
        "updated_at": prompt.updated_at.isoformat() if prompt.updated_at else None,
    }


def _jsonable(value):
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _row_to_dict(row) -> Dict[str, Any]:
    return {col.name: _jsonable(getattr(row, col.name)) for col in row.__table__.columns}


def _coerce_value(column, value):
    if value in ("", None):
        return None
    if hasattr(column.type, "python_type"):
        try:
            py_type = column.type.python_type
        except NotImplementedError:
            py_type = None
        if py_type is datetime and isinstance(value, str):
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    return value


def _admin_resources():
    from data.schema_cognitive import (
        Agent, MicroAgent, MicroAgentType, PromptTemplate, Memory, MemoryType,
        ThoughtProcess, ThoughtContribution, ConversationSession, ConversationMessage,
        LearningEvent,
    )
    from data.schema_persona import (
        PersonaBlueprint, DynamicState, PersonaMemoryDetail, InnerMonologue,
        RelationshipDynamic, BehavioralLog,
    )

    return {
        "prompt_templates": {
            "model": PromptTemplate,
            "label": "Prompts",
            "search": ["key", "name", "category", "description", "template"],
            "editable": ["key", "name", "category", "description", "template", "language", "version", "variables", "is_active"],
            "summary": "Prompts usados pelo core, memória, saudação e micro-agentes.",
        },
        "micro_agent_types": {
            "model": MicroAgentType,
            "label": "Tipos de micro-agente",
            "search": ["name", "description", "system_prompt", "cognitive_objective"],
            "editable": ["description", "system_prompt", "cognitive_objective", "thinking_framework", "default_weight", "activation_conditions", "response_style", "is_active"],
            "summary": "Prompts de sistema e pesos base dos micro-agentes.",
        },
        "micro_agents": {
            "model": MicroAgent,
            "label": "Micro-agentes por persona",
            "search": ["agent_id", "current_focus", "custom_prompt"],
            "editable": ["custom_prompt", "custom_weight", "activation_enabled", "current_focus", "recent_conclusions", "confidence_level"],
            "summary": "Overrides por agente e estado interno de cada micro-agente.",
        },
        "agents": {
            "model": Agent,
            "label": "Agentes",
            "search": ["name", "description", "background_story", "language"],
            "editable": ["name", "description", "avatar", "language", "personality_traits", "base_values", "background_story", "life_experiences", "thinking_style", "decision_making_approach", "debate_intensity", "is_active", "current_emotional_state"],
            "summary": "Identidade base, idioma e configuração cognitiva.",
        },
        "memories": {
            "model": Memory,
            "label": "Memórias",
            "search": ["title", "content", "agent_id"],
            "editable": ["title", "content", "emotional_valence", "importance_score", "relates_to_agent_ids", "relates_to_topics", "relates_to_events", "occurred_at", "relevance_score", "is_autobiographical", "is_episodic", "is_blocked"],
            "summary": "Memórias persistentes usadas no recall e na consciência de memória.",
        },
        "memory_types": {
            "model": MemoryType,
            "label": "Tipos de memória",
            "search": ["name", "description", "temporal_scope"],
            "editable": ["description", "temporal_scope", "decay_rate", "activation_threshold", "is_active"],
            "summary": "Classificação e política de ativação/decaimento das memórias.",
        },
        "persona_blueprints": {
            "model": PersonaBlueprint,
            "label": "Blueprints",
            "search": ["agent_id"],
            "editable": ["identity", "internal_states_config", "personality_full", "memory_config", "emotional_config", "cognitive_config", "social_config", "behavioral_config", "worldview", "growth_arc", "behavior_prompts", "meta"],
            "summary": "DNA estático da persona, incluindo comportamento e voz.",
        },
        "dynamic_states": {
            "model": DynamicState,
            "label": "Estados dinâmicos",
            "search": ["agent_id", "primary_emotion", "current_mood", "last_trigger"],
            "editable": [c.name for c in DynamicState.__table__.columns if c.name not in {"id", "agent_id", "created_at", "updated_at"}],
            "summary": "Stress, emoções, necessidades, defesas e estado atual da persona.",
        },
        "relationship_dynamics": {
            "model": RelationshipDynamic,
            "label": "Relações",
            "search": ["agent_id", "target_id", "target_name", "relationship_type", "dominant_feeling"],
            "editable": [c.name for c in RelationshipDynamic.__table__.columns if c.name not in {"id", "agent_id", "target_id", "created_at", "updated_at"}],
            "summary": "Confiança, familiaridade, afeto e padrões relacionais.",
        },
        "conversation_sessions": {
            "model": ConversationSession,
            "label": "Sessões de conversa",
            "search": ["agent_id", "user_id", "current_topic", "summary"],
            "editable": ["is_active", "working_memory", "current_topic", "emotional_tone", "summary", "key_points", "unresolved_questions", "message_count", "ended_at"],
            "summary": "Working memory, resumo e estado da conversa.",
        },
        "conversation_messages": {
            "model": ConversationMessage,
            "label": "Mensagens",
            "search": ["session_id", "role", "content", "detected_intent"],
            "editable": ["role", "content", "detected_emotion", "detected_intent", "importance"],
            "summary": "Histórico bruto usado para contexto conversacional.",
        },
        "thought_processes": {
            "model": ThoughtProcess,
            "label": "Processos cognitivos",
            "search": ["agent_id", "conversation_id", "query", "final_response"],
            "editable": ["context", "status", "final_response", "confidence", "reasoning"],
            "summary": "Registo do pensamento e resposta final por interação.",
        },
        "thought_contributions": {
            "model": ThoughtContribution,
            "label": "Contribuições cognitivas",
            "search": ["thought_process_id", "micro_agent_id", "perspective"],
            "editable": ["perspective", "confidence", "supporting_arguments", "opposing_arguments", "weight_in_decision", "was_decisive"],
            "summary": "Perspetivas individuais de cada micro-agente.",
        },
        "learning_events": {
            "model": LearningEvent,
            "label": "Aprendizagens",
            "search": ["agent_id", "user_id", "query", "response", "lesson_learned"],
            "editable": ["feedback_type", "feedback_score", "feedback_text", "lesson_learned", "affected_weights"],
            "summary": "Eventos de aprendizagem e feedback.",
        },
        "persona_memory_details": {
            "model": PersonaMemoryDetail,
            "label": "Detalhes de memória",
            "search": ["memory_id", "narrative_role", "life_period", "body_memory"],
            "editable": [c.name for c in PersonaMemoryDetail.__table__.columns if c.name not in {"id", "memory_id", "created_at", "updated_at"}],
            "summary": "Camada psicológica/traumática/sensorial das memórias.",
        },
        "inner_monologues": {
            "model": InnerMonologue,
            "label": "Monólogos internos",
            "search": ["agent_id", "trigger", "trigger_type", "thought"],
            "editable": ["trigger", "trigger_type", "thought", "inner_voice_tone", "emotional_impact", "led_to_action", "action_taken", "shared_with_user", "shared_how"],
            "summary": "Pensamentos internos persistidos.",
        },
        "behavioral_logs": {
            "model": BehavioralLog,
            "label": "Logs comportamentais",
            "search": ["agent_id", "behavior_type", "behavior_description", "trigger"],
            "editable": ["behavior_type", "behavior_description", "trigger", "stress_level_at_time", "emotional_state_at_time", "pattern_match", "conscious", "protective_function", "outcome", "adaptive"],
            "summary": "Padrões e comportamentos observados.",
        },
    }


# ============================================================================
# ENDPOINTS PÚBLICOS
# ============================================================================

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Login com email e password. Retorna JWT token."""
    user = db.query(User).filter(User.email == request.email).first()

    if not user or not user.verify_password(request.password):
        raise HTTPException(
            status_code=401,
            detail="Email ou password incorretos"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=403,
            detail="Conta desactivada. Contacta o administrador."
        )

    # Actualizar last_login
    user.last_login = datetime.utcnow()
    db.commit()

    token = create_access_token(user.id, user.role)

    return TokenResponse(
        access_token=token,
        user=user.to_dict()
    )


@router.post("/register", response_model=TokenResponse)
async def register(request: RegisterRequest, db: Session = Depends(get_db)):
    """Registo de novo utilizador."""
    # Verificar se email já existe
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(
            status_code=409,
            detail="Este email já está registado"
        )

    # Validar password
    if len(request.password) < 8:
        raise HTTPException(
            status_code=400,
            detail="A password deve ter pelo menos 8 caracteres"
        )

    # Criar utilizador
    user = User(
        name=request.name,
        email=request.email,
        role="user",
    )
    user.set_password(request.password)

    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id, user.role)

    return TokenResponse(
        access_token=token,
        user=user.to_dict()
    )


# ============================================================================
# ENDPOINTS AUTENTICADOS
# ============================================================================

@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    """Obtém perfil do utilizador autenticado."""
    return current_user.to_dict()


@router.put("/me")
async def update_me(
    updates: UpdateUserRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Actualiza perfil do utilizador autenticado."""
    if updates.name is not None:
        current_user.name = updates.name
    if updates.email is not None:
        existing = db.query(User).filter(User.email == updates.email, User.id != current_user.id).first()
        if existing:
            raise HTTPException(status_code=409, detail="Email já em uso")
        current_user.email = updates.email

    db.commit()
    db.refresh(current_user)
    return current_user.to_dict()


@router.post("/me/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Altera password do utilizador autenticado."""
    if not current_user.verify_password(request.current_password):
        raise HTTPException(status_code=400, detail="Password actual incorrecta")

    if len(request.new_password) < 8:
        raise HTTPException(status_code=400, detail="Nova password deve ter pelo menos 8 caracteres")

    current_user.set_password(request.new_password)
    db.commit()
    return {"message": "Password alterada com sucesso"}


# ============================================================================
# ENDPOINTS ADMIN - GESTÃO DE UTILIZADORES
# ============================================================================

@router.get("/admin/users")
async def admin_list_users(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Lista todos os utilizadores (apenas admin)."""
    users = db.query(User).order_by(User.created_at.desc()).all()
    return {"users": [u.to_dict() for u in users], "total": len(users)}


@router.get("/admin/users/{user_id}")
async def admin_get_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Obtém detalhes de um utilizador (apenas admin)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilizador não encontrado")
    return user.to_dict()


@router.put("/admin/users/{user_id}")
async def admin_update_user(
    user_id: str,
    updates: UpdateUserRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Actualiza um utilizador (apenas admin)."""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilizador não encontrado")

    if updates.name is not None:
        user.name = updates.name
    if updates.email is not None:
        existing = db.query(User).filter(User.email == updates.email, User.id != user.id).first()
        if existing:
            raise HTTPException(status_code=409, detail="Email já em uso")
        user.email = updates.email
    if updates.role is not None:
        user.role = updates.role
    if updates.is_active is not None:
        user.is_active = updates.is_active

    db.commit()
    db.refresh(user)
    return user.to_dict()


@router.delete("/admin/users/{user_id}")
async def admin_delete_user(
    user_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Remove um utilizador (apenas admin). Não pode remover a si próprio."""
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="Não podes remover a tua própria conta")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Utilizador não encontrado")

    db.delete(user)
    db.commit()
    return {"message": f"Utilizador {user.email} removido"}


# ============================================================================
# ENDPOINTS ADMIN - PROMPTS E BASE DE DADOS
# ============================================================================

@router.get("/admin/prompts")
async def admin_list_prompts(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Lista prompts editáveis e onde estão ligadas."""
    from data.schema_cognitive import PromptTemplate

    prompts = db.query(PromptTemplate).order_by(PromptTemplate.category, PromptTemplate.key).all()
    return {"prompts": [_prompt_to_dict(p) for p in prompts], "total": len(prompts)}


@router.get("/admin/prompts/{prompt_id}")
async def admin_get_prompt(
    prompt_id: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from data.schema_cognitive import PromptTemplate

    prompt = db.query(PromptTemplate).filter(PromptTemplate.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt não encontrada")
    return _prompt_to_dict(prompt)


@router.put("/admin/prompts/{prompt_id}")
async def admin_update_prompt(
    prompt_id: str,
    request: AdminUpdateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from data.schema_cognitive import PromptTemplate

    prompt = db.query(PromptTemplate).filter(PromptTemplate.id == prompt_id).first()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt não encontrada")

    allowed = {"key", "name", "category", "description", "template", "language", "version", "variables", "is_active"}
    for field, value in request.updates.items():
        if field in allowed:
            setattr(prompt, field, value)
    prompt.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(prompt)
    return _prompt_to_dict(prompt)


@router.get("/admin/db/resources")
async def admin_db_resources(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    resources = _admin_resources()
    data = []
    for key, cfg in resources.items():
        count = db.query(cfg["model"]).count()
        columns = [c.name for c in cfg["model"].__table__.columns]
        data.append({
            "key": key,
            "label": cfg["label"],
            "summary": cfg["summary"],
            "count": count,
            "columns": columns,
            "editable_fields": cfg["editable"],
            "search_fields": cfg["search"],
        })
    return {"resources": data}


@router.get("/admin/db/{resource}")
async def admin_db_list_rows(
    resource: str,
    q: str = "",
    limit: int = 50,
    offset: int = 0,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    resources = _admin_resources()
    cfg = resources.get(resource)
    if not cfg:
        raise HTTPException(status_code=404, detail="Recurso não permitido")

    limit = max(1, min(limit, 200))
    model = cfg["model"]
    query = db.query(model)
    if q.strip():
        clauses = []
        for field in cfg["search"]:
            col = getattr(model, field, None)
            if col is not None and isinstance(col.property.columns[0].type, (String, Text)):
                clauses.append(col.ilike(f"%{q.strip()}%"))
        if clauses:
            query = query.filter(or_(*clauses))

    order_col = getattr(model, "updated_at", None)
    if order_col is None:
        order_col = getattr(model, "created_at", None)
    if order_col is None:
        order_col = getattr(model, "id", None)
    if order_col is not None:
        query = query.order_by(order_col.desc() if hasattr(order_col, "desc") else order_col)

    total = query.count()
    rows = query.offset(max(offset, 0)).limit(limit).all()
    return {
        "resource": resource,
        "label": cfg["label"],
        "summary": cfg["summary"],
        "editable_fields": cfg["editable"],
        "columns": [c.name for c in model.__table__.columns],
        "rows": [_row_to_dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.put("/admin/db/{resource}/{row_id}")
async def admin_db_update_row(
    resource: str,
    row_id: str,
    request: AdminUpdateRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    resources = _admin_resources()
    cfg = resources.get(resource)
    if not cfg:
        raise HTTPException(status_code=404, detail="Recurso não permitido")

    model = cfg["model"]
    row = db.query(model).filter(model.id == row_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Registo não encontrado")

    editable = set(cfg["editable"])
    columns = {c.name: c for c in model.__table__.columns}
    for field, value in request.updates.items():
        if field in editable and field in columns:
            setattr(row, field, _coerce_value(columns[field], value))
    if "updated_at" in columns:
        setattr(row, "updated_at", datetime.utcnow())

    db.commit()
    db.refresh(row)
    return _row_to_dict(row)


# ============================================================================
# OAUTH - GOOGLE
# ============================================================================

@router.get("/google")
async def google_login():
    """Redireciona para o consent screen da Google."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=501, detail="Google OAuth não configurado. Adiciona GOOGLE_CLIENT_ID e GOOGLE_CLIENT_SECRET ao .env")

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": f"{BACKEND_URL}/auth/google/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return RedirectResponse(url=url)


@router.get("/google/callback")
async def google_callback(code: str, db: Session = Depends(get_db)):
    """Callback da Google OAuth. Troca code por token e cria/encontra user."""
    # Trocar code por access token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": f"{BACKEND_URL}/auth/google/callback",
                "grant_type": "authorization_code",
            },
        )

    if token_resp.status_code != 200:
        logger.error(f"Google token error: {token_resp.text}")
        return RedirectResponse(url=f"{FRONTEND_URL}/login?error=google_token_failed")

    token_data = token_resp.json()
    access_token = token_data.get("access_token")

    # Obter info do utilizador
    async with httpx.AsyncClient() as client:
        user_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if user_resp.status_code != 200:
        return RedirectResponse(url=f"{FRONTEND_URL}/login?error=google_userinfo_failed")

    google_user = user_resp.json()
    google_id = google_user.get("id")
    email = google_user.get("email")
    name = google_user.get("name", email.split("@")[0])
    avatar = google_user.get("picture")

    # Encontrar ou criar user
    user = db.query(User).filter(User.oauth_provider == "google", User.oauth_id == google_id).first()

    if not user:
        # Verificar se já existe user com este email (ligar contas)
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.oauth_provider = "google"
            user.oauth_id = google_id
            if avatar and not user.avatar:
                user.avatar = avatar
        else:
            user = User(
                name=name,
                email=email,
                oauth_provider="google",
                oauth_id=google_id,
                avatar=avatar,
                role="user",
                is_active=True,
            )
            db.add(user)
            db.flush()

    if not user.is_active:
        return RedirectResponse(url=f"{FRONTEND_URL}/login?error=account_disabled")

    user.last_login = datetime.utcnow()
    db.commit()
    db.refresh(user)

    # Gerar JWT e redirecionar para frontend
    jwt_token = create_access_token(user.id, user.role)
    return RedirectResponse(url=f"{FRONTEND_URL}/auth/callback?token={jwt_token}")


# ============================================================================
# OAUTH - GITHUB
# ============================================================================

@router.get("/github")
async def github_login():
    """Redireciona para o consent screen do GitHub."""
    if not GITHUB_CLIENT_ID:
        raise HTTPException(status_code=501, detail="GitHub OAuth não configurado. Adiciona GITHUB_CLIENT_ID e GITHUB_CLIENT_SECRET ao .env")

    params = {
        "client_id": GITHUB_CLIENT_ID,
        "redirect_uri": f"{BACKEND_URL}/auth/github/callback",
        "scope": "user:email read:user",
    }
    url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"
    return RedirectResponse(url=url)


@router.get("/github/callback")
async def github_callback(code: str, db: Session = Depends(get_db)):
    """Callback do GitHub OAuth. Troca code por token e cria/encontra user."""
    # Trocar code por access token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": f"{BACKEND_URL}/auth/github/callback",
            },
            headers={"Accept": "application/json"},
        )

    if token_resp.status_code != 200:
        logger.error(f"GitHub token error: {token_resp.text}")
        return RedirectResponse(url=f"{FRONTEND_URL}/login?error=github_token_failed")

    token_data = token_resp.json()
    access_token = token_data.get("access_token")

    if not access_token:
        logger.error(f"GitHub no access_token: {token_data}")
        return RedirectResponse(url=f"{FRONTEND_URL}/login?error=github_token_failed")

    # Obter info do utilizador
    async with httpx.AsyncClient() as client:
        user_resp = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )

    if user_resp.status_code != 200:
        return RedirectResponse(url=f"{FRONTEND_URL}/login?error=github_userinfo_failed")

    github_user = user_resp.json()
    github_id = str(github_user.get("id"))
    name = github_user.get("name") or github_user.get("login")
    avatar = github_user.get("avatar_url")

    # GitHub pode não devolver email no /user, temos de ir buscar
    email = github_user.get("email")
    if not email:
        async with httpx.AsyncClient() as client:
            emails_resp = await client.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            )
        if emails_resp.status_code == 200:
            emails = emails_resp.json()
            primary = next((e for e in emails if e.get("primary")), None)
            if primary:
                email = primary["email"]
            elif emails:
                email = emails[0]["email"]

    if not email:
        return RedirectResponse(url=f"{FRONTEND_URL}/login?error=github_no_email")

    # Encontrar ou criar user
    user = db.query(User).filter(User.oauth_provider == "github", User.oauth_id == github_id).first()

    if not user:
        user = db.query(User).filter(User.email == email).first()
        if user:
            user.oauth_provider = "github"
            user.oauth_id = github_id
            if avatar and not user.avatar:
                user.avatar = avatar
        else:
            user = User(
                name=name,
                email=email,
                oauth_provider="github",
                oauth_id=github_id,
                avatar=avatar,
                role="user",
                is_active=True,
            )
            db.add(user)
            db.flush()

    if not user.is_active:
        return RedirectResponse(url=f"{FRONTEND_URL}/login?error=account_disabled")

    user.last_login = datetime.utcnow()
    db.commit()
    db.refresh(user)

    jwt_token = create_access_token(user.id, user.role)
    return RedirectResponse(url=f"{FRONTEND_URL}/auth/callback?token={jwt_token}")


# ============================================================================
# SEED ADMIN
# ============================================================================

def seed_admin_user(db: Session):
    """Cria utilizador admin se não existir."""
    admin = db.query(User).filter(User.email == "admin@admin.ai").first()
    if not admin:
        admin = User(
            name="Administrador",
            email="admin@admin.ai",
            role="admin",
        )
        admin.set_password("admin")
        db.add(admin)
        db.commit()
        logger.info("[auth] admin criado: admin@admin.ai")
