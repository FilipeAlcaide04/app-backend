"""
Database initialization for cognitive system
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from data.schema_cognitive import Base
import logging

logger = logging.getLogger(__name__)


def init_cognitive_db(database_url: str):
    """Inicializa banco de dados cognitivo"""
    
    try:
        engine = create_engine(database_url)
        Base.metadata.create_all(engine)
        logger.info("Base de dados cognitiva inicializada com sucesso")
        return engine
    except Exception as e:
        logger.error(f"Erro ao inicializar BD: {e}")
        raise


def get_db_session(database_url: str) -> Session:
    """Cria sessão de BD"""
    
    engine = create_engine(database_url)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()
