"""
Auth API - Endpoints de autenticação segura
JWT tokens, bcrypt passwords, role-based access control
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, List
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
