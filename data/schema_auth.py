"""
Schema Auth - Tabela de utilizadores com autenticação segura
Passwords encriptadas com bcrypt, roles (admin/user), timestamps
"""

from sqlalchemy import Column, String, Boolean, DateTime, Text
from data.schema_cognitive import Base
from datetime import datetime
from uuid import uuid4
import bcrypt


class User(Base):
    """Utilizador do sistema com autenticação segura"""
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(Text, nullable=True)
    role = Column(String(50), nullable=False, default="user")  # "admin" ou "user"
    is_active = Column(Boolean, default=True, nullable=False)
    oauth_provider = Column(String(50), nullable=True)  # "google", "github", ou None
    oauth_id = Column(String(255), nullable=True)  # ID do provider
    avatar = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login = Column(DateTime, nullable=True)

    def set_password(self, password: str):
        """Hash password com bcrypt"""
        salt = bcrypt.gensalt(rounds=12)
        self.password_hash = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def verify_password(self, password: str) -> bool:
        """Verifica password contra o hash bcrypt"""
        if not self.password_hash:
            return False
        return bcrypt.checkpw(password.encode("utf-8"), self.password_hash.encode("utf-8"))

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "oauth_provider": self.oauth_provider,
            "avatar": self.avatar,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }
