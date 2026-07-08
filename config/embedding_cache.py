"""
Cache de embeddings — pré-carrega modelo no startup para evitar latência na primeira request.
"""

import logging
from llm_logic.embedding_generator import EmbeddingGenerator, _embedding_model

logger = logging.getLogger(__name__)


def preload_embedding_model() -> bool:
    try:
        EmbeddingGenerator()
        return True
    except Exception as e:
        logger.error(f"[embedding] falha ao pré-carregar: {e}")
        return False
