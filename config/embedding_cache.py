"""
🚀 CACHE DE EMBEDDINGS - Pré-carrega modelo no startup

Este módulo garante que o modelo de embeddings é carregado uma única vez
no início da aplicação e reutilizado em toda a duração da sessão.

Uso:
    1. Na main do servidor (api.cognitive_api.py):
       from config.embedding_cache import preload_embedding_model
       preload_embedding_model()  # Chamar no startup
    
    2. Em qualquer lugar que precisar:
       from llm_logic.embedding_generator import EmbeddingGenerator
       gen = EmbeddingGenerator()  # Sempre reutiliza o mesmo modelo
"""

import logging
from llm_logic.embedding_generator import EmbeddingGenerator, _embedding_model

logger = logging.getLogger(__name__)

def preload_embedding_model():
    """
    Pré-carregar o modelo de embeddings no startup
    
    Benefícios:
    ✅ Primeira request não fica lenta (modelo já carregado)
    ✅ Modelo carregado uma única vez em memória
    ✅ Todas instâncias de EmbeddingGenerator reutilizam o mesmo modelo
    
    Chamada:
        from config.embedding_cache import preload_embedding_model
        
        @app.on_event("startup")
        async def startup():
            preload_embedding_model()
    """
    try:
        logger.info("🚀 PRÉ-CARREGANDO MODELO DE EMBEDDINGS...")
        generator = EmbeddingGenerator()
        logger.info(f"✅ MODELO PRÉ-CARREGADO COM SUCESSO")
        logger.info(f"   Modelo: {generator.MODEL_NAME}")
        logger.info(f"   Dimensões: 384")
        logger.info(f"   Status: PRONTO PARA USO")
        return True
    except Exception as e:
        logger.error(f"❌ Erro ao pré-carregar modelo: {e}")
        return False

def get_model_status():
    """
    Verificar status do cache de embeddings
    
    Returns:
        dict: Status do modelo
    """
    from llm_logic.embedding_generator import _embedding_model
    
    return {
        "loaded": _embedding_model is not None,
        "model_name": "all-MiniLM-L6-v2" if _embedding_model is not None else None,
        "status": "PRONTO" if _embedding_model is not None else "NÃO CARREGADO"
    }
