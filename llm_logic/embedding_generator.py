"""
Serviço de Embeddings - Gera vetores para documentos
Usa sentence-transformers para criar embeddings de alta qualidade

🚀 OTIMIZAÇÃO: Singleton pattern para evitar carregar modelo múltiplas vezes
   O modelo é carregado uma única vez na memória e reutilizado globalmente
"""

import numpy as np
import json
import logging
from typing import List, Tuple, Optional
from sentence_transformers import SentenceTransformer
from sqlalchemy.orm import Session
from data.database import (
    Document, DocumentChunk, DocumentEmbedding, 
    SessionLocal, get_db
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🔒 SINGLETON GLOBAL - Modelo carregado uma única vez
_embedding_model = None
_model_lock = False

class EmbeddingGenerator:
    """Gera embeddings para chunks de documentos"""
    
    # Modelo pré-treinado leve e rápido
    MODEL_NAME = "all-MiniLM-L6-v2"  # 384 dimensões
    
    # Modelos alternativos (comentados):
    # MODEL_NAME = "all-mpnet-base-v2"  # 768 dimensões, mais preciso mas mais lento
    # MODEL_NAME = "paraphrase-MiniLM-L6-v2"  # 384 dimensões, ótimo para paráfrases
    
    CHUNK_SIZE = 512  # Caracteres por chunk
    CHUNK_OVERLAP = 50  # Sobreposição entre chunks
    
    def __init__(self):
        """Inicializar modelo de embeddings (singleton - carrega uma única vez)"""
        global _embedding_model, _model_lock
        
        if _embedding_model is not None:
            # Modelo já carregado, reutilizar
            self.model = _embedding_model
            return
        
        if _model_lock:
            # Outro thread está carregando, esperar
            import time
            while _embedding_model is None:
                time.sleep(0.1)
            self.model = _embedding_model
            return
        
        # Carregar modelo
        _model_lock = True
        try:
            logger.info(f"Carregando modelo {self.MODEL_NAME}...")
            _embedding_model = SentenceTransformer(self.MODEL_NAME)
            logger.info(f"✓ Modelo {self.MODEL_NAME} carregado com sucesso")
            self.model = _embedding_model
        except Exception as e:
            logger.error(f"✗ Erro ao carregar modelo: {e}")
            _model_lock = False
            raise
        finally:
            _model_lock = False

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 512, overlap: int = 50) -> List[str]:
        """
        Dividir texto em chunks com sobreposição
        
        Args:
            text: Texto a dividir
            chunk_size: Tamanho de cada chunk em caracteres
            overlap: Sobreposição entre chunks
            
        Returns:
            Lista de chunks
        """
        if not text:
            return []
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk = text[start:end]
            
            if chunk.strip():  # Ignorar chunks vazios
                chunks.append(chunk.strip())
            
            # Próximo chunk começa antes do final do anterior (sobreposição)
            start = end - overlap if end < len(text) else len(text)
        
        return chunks if chunks else [""]  # Retornar pelo menos um chunk vazio

    def generate_embedding(self, text: str) -> List[float]:
        """
        Gerar embedding para um texto
        
        Args:
            text: Texto para embedder
            
        Returns:
            Lista de floats representando o embedding
        """
        if not text or not text.strip():
            # Retornar embedding zero se texto vazio
            return [0.0] * 384
        
        try:
            embeddings = self.model.encode([text])
            # Retornar como lista (json-serializable)
            return embeddings[0].tolist()
        except Exception as e:
            logger.error(f"✗ Erro ao gerar embedding: {e}")
            raise

    def process_document(self, document_id: int, db: Session) -> Tuple[int, int]:
        """
        Processar documento: criar chunks e gerar embeddings
        
        Args:
            document_id: ID do documento
            db: Sessão de BD
            
        Returns:
            Tuplo (número de chunks, número de embeddings gerados)
        """
        try:
            # Buscar documento
            document = db.query(Document).filter(
                Document.id == document_id
            ).first()
            
            if not document:
                logger.warning(f"Documento {document_id} não encontrado")
                return 0, 0
            
            if not document.content_text:
                logger.warning(f"Documento {document.filename} não tem conteúdo")
                return 0, 0
            
            logger.info(f"\nProcessando: {document.filename}")
            logger.info(f"Tamanho: {len(document.content_text)} caracteres")
            
            # 1. Dividir em chunks
            chunks = self.chunk_text(
                document.content_text,
                self.CHUNK_SIZE,
                self.CHUNK_OVERLAP
            )
            logger.info(f"✓ Criados {len(chunks)} chunks")
            
            # 2. Criar registros de chunks
            chunk_records = []
            for chunk_num, chunk_text in enumerate(chunks):
                db_chunk = DocumentChunk(
                    document_id=document_id,
                    chunk_number=chunk_num,
                    chunk_text=chunk_text,
                    chunk_size=len(chunk_text)
                )
                db.add(db_chunk)
                chunk_records.append(db_chunk)
            
            db.flush()  # Flush para obter IDs dos chunks
            logger.info(f"✓ Registros de chunks criados")
            
            # 3. Gerar embeddings
            embeddings_count = 0
            for chunk_num, db_chunk in enumerate(chunk_records):
                embedding_vector = self.generate_embedding(db_chunk.chunk_text)
                
                db_embedding = DocumentEmbedding(
                    chunk_id=db_chunk.id,
                    embedding=json.dumps(embedding_vector),  # Armazenar como JSON
                    embedding_model=self.MODEL_NAME
                )
                db.add(db_embedding)
                embeddings_count += 1
                
                if (chunk_num + 1) % 10 == 0:
                    logger.info(f"  {chunk_num + 1}/{len(chunks)} embeddings gerados")
            
            db.commit()
            logger.info(f"✓ {embeddings_count} embeddings gerados e armazenados")
            
            return len(chunks), embeddings_count
            
        except Exception as e:
            db.rollback()
            logger.error(f"✗ Erro ao processar documento: {e}")
            raise

    def process_all_documents(self, db: Session) -> dict:
        """
        Processar todos os documentos sem embeddings
        
        Args:
            db: Sessão de BD
            
        Returns:
            Dicionário com estatísticas
        """
        # Buscar documentos sem embeddings
        documents = db.query(Document).outerjoin(
            DocumentChunk, Document.id == DocumentChunk.document_id
        ).filter(
            DocumentChunk.id.is_(None)
        ).all()
        
        logger.info(f"Encontrados {len(documents)} documentos sem embeddings\n")
        
        stats = {
            "total_documents": len(documents),
            "processed": 0,
            "total_chunks": 0,
            "total_embeddings": 0,
            "errors": 0
        }
        
        for document in documents:
            try:
                chunks, embeddings = self.process_document(document.id, db)
                stats["processed"] += 1
                stats["total_chunks"] += chunks
                stats["total_embeddings"] += embeddings
            except Exception as e:
                logger.error(f"Erro ao processar {document.filename}: {e}")
                stats["errors"] += 1
        
        logger.info("\n" + "="*60)
        logger.info("RESUMO DE PROCESSAMENTO")
        logger.info("="*60)
        logger.info(f"Documentos processados: {stats['processed']}/{stats['total_documents']}")
        logger.info(f"Total de chunks criados: {stats['total_chunks']}")
        logger.info(f"Total de embeddings gerados: {stats['total_embeddings']}")
        logger.info(f"Erros: {stats['errors']}")
        logger.info("="*60 + "\n")
        
        return stats

def regenerate_embeddings_for_document(document_id: int, db: Optional[Session] = None):
    """
    Regenerar embeddings para um documento específico
    Útil se mudou o modelo ou documento foi atualizado
    
    Args:
        document_id: ID do documento
        db: Sessão (opcional, cria uma se não fornecida)
    """
    if db is None:
        db = SessionLocal()
        close_db = True
    else:
        close_db = False
    
    try:
        # Remover chunks e embeddings antigos
        old_chunks = db.query(DocumentChunk).filter(
            DocumentChunk.document_id == document_id
        ).all()
        
        for chunk in old_chunks:
            db.delete(chunk)
        
        db.commit()
        logger.info(f"✓ Chunks antigos removidos")
        
        # Gerar novos
        generator = EmbeddingGenerator()
        chunks, embeddings = generator.process_document(document_id, db)
        
        logger.info(f"✓ Embeddings regenerados: {embeddings}")
        
    finally:
        if close_db:
            db.close()


def get_embedding_generator() -> EmbeddingGenerator:
    """
    Obter instância singleton do EmbeddingGenerator
    
    Uso recomendado em todo o código:
        from llm_logic.embedding_generator import get_embedding_generator
        generator = get_embedding_generator()  # Sempre a mesma instância
    
    Returns:
        EmbeddingGenerator (singleton)
    """
    return EmbeddingGenerator()


def clear_embedding_cache():
    """
    Limpar cache de embeddings (reiniciar modelo)
    Use apenas para debug ou quando mudar de modelo
    """
    global _embedding_model, _model_lock
    _embedding_model = None
    _model_lock = False
    logger.warning("⚠️ Cache de embeddings limpo. Próxima instância carregará modelo novamente.")

