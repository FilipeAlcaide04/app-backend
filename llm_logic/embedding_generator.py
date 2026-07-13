"""
Serviço de Embeddings - Gera vetores semânticos
Usa sentence-transformers com singleton pattern para reutilizar o modelo
Inclui cache para evitar regenerar embeddings do mesmo texto
"""

import logging
import time
from typing import List, Dict, Tuple
from sentence_transformers import SentenceTransformer
from functools import lru_cache

logger = logging.getLogger(__name__)

_embedding_model = None
_model_lock = False
_embedding_cache: Dict[str, List[float]] = {}


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
        
        # Verificar cache primeiro
        text_clean = text.strip()
        if text_clean in _embedding_cache:
            return _embedding_cache[text_clean]

        try:
            embeddings = self.model.encode([text_clean])
            result = embeddings[0].tolist()
            # Guardar no cache
            _embedding_cache[text_clean] = result
            return result
        except Exception as e:
            logger.error(f"Erro ao gerar embedding: {e}")
            raise

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Gera múltiplos embeddings de uma vez (mais rápido que individual)"""
        if not texts:
            return []
        
        # Separar textos cached dos que precisam ser processados
        cached = {}
        to_process = []
        indices = []
        
        for i, text in enumerate(texts):
            text_clean = text.strip() if text else ""
            if text_clean in _embedding_cache:
                cached[i] = _embedding_cache[text_clean]
            else:
                to_process.append(text_clean if text_clean else "")
                indices.append(i)
        
        # Processar apenas os não-cached
        results = [None] * len(texts)
        
        if to_process:
            try:
                embeddings = self.model.encode(to_process, convert_to_tensor=False, show_progress_bar=False)
                for idx, i in enumerate(indices):
                    result = embeddings[idx].tolist() if hasattr(embeddings[idx], 'tolist') else list(embeddings[idx])
                    results[i] = result
                    _embedding_cache[to_process[idx]] = result
            except Exception as e:
                logger.error(f"Erro ao gerar embeddings em batch: {e}")
                raise
        
        # Preencher com cached
        for i, emb in cached.items():
            results[i] = emb
        
        return results


def get_embedding_generator() -> EmbeddingGenerator:
    return EmbeddingGenerator()


def clear_embedding_cache():
    global _embedding_model, _model_lock, _embedding_cache
    _embedding_model = None
    _model_lock = False
    _embedding_cache.clear()
    logger.debug("[embedding] cache limpo")
