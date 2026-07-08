"""
Serviço de Embeddings - Gera vetores semânticos
Usa sentence-transformers com singleton pattern para reutilizar o modelo
"""

import logging
import time
from typing import List
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

_embedding_model = None
_model_lock = False


class EmbeddingGenerator:

    MODEL_NAME = "all-MiniLM-L6-v2"
    CHUNK_SIZE = 512
    CHUNK_OVERLAP = 50

    def __init__(self):
        global _embedding_model, _model_lock

        if _embedding_model is not None:
            self.model = _embedding_model
            return

        if _model_lock:
            while _embedding_model is None:
                time.sleep(0.1)
            self.model = _embedding_model
            return

        _model_lock = True
        try:
            logger.info(f"[embedding] a carregar {self.MODEL_NAME}...")
            _embedding_model = SentenceTransformer(self.MODEL_NAME)
            logger.info(f"[embedding] {self.MODEL_NAME} pronto")
            self.model = _embedding_model
        except Exception as e:
            logger.error(f"Erro ao carregar modelo: {e}")
            _model_lock = False
            raise
        finally:
            _model_lock = False

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 512, overlap: int = 50) -> List[str]:
        if not text:
            return []

        chunks = []
        start = 0

        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk = text[start:end]

            if chunk.strip():
                chunks.append(chunk.strip())

            start = end - overlap if end < len(text) else len(text)

        return chunks if chunks else [""]

    def generate_embedding(self, text: str) -> List[float]:
        if not text or not text.strip():
            return [0.0] * 384

        try:
            embeddings = self.model.encode([text])
            return embeddings[0].tolist()
        except Exception as e:
            logger.error(f"Erro ao gerar embedding: {e}")
            raise


def get_embedding_generator() -> EmbeddingGenerator:
    return EmbeddingGenerator()


def clear_embedding_cache():
    global _embedding_model, _model_lock
    _embedding_model = None
    _model_lock = False
    logger.debug("[embedding] cache limpo")
