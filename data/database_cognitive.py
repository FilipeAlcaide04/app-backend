"""
Database initialization for cognitive system + persona system
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from data.schema_cognitive import Base
# Importar schema_persona para registar os modelos na mesma Base
import data.schema_persona  # noqa: F401
import logging

logger = logging.getLogger(__name__)


def init_cognitive_db(database_url: str):
    """Inicializa banco de dados cognitivo + persona"""

    try:
        engine = create_engine(database_url)
        Base.metadata.create_all(engine)
        logger.info("Base de dados cognitiva + persona inicializada com sucesso")
        return engine
    except Exception as e:
        logger.error(f"Erro ao inicializar BD: {e}")
        raise


def get_db_session(database_url: str) -> Session:
    """Cria sessão de BD"""
    
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()
