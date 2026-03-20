"""
Document Service - Gestão de documentos privados por agente
Garante isolamento total e segurança de acesso
"""

from sqlalchemy.orm import Session
from data.schema_cognitive import (
    Document, DocumentChunk, DocumentEmbedding, Agent, AuditLog
)
from llm_logic.embedding_generator import EmbeddingGenerator
from document_handlers.document_processor import DocumentProcessor
from typing import List, Optional, Dict, Tuple
from datetime import datetime
import os
import json
import logging
from uuid import uuid4

logger = logging.getLogger(__name__)


class DocumentServiceCognitive:
    """Gestão de documentos com isolamento total por agente"""
    
    def __init__(self, db: Session, upload_dir: str = "uploads"):
        self.db = db
        self.upload_dir = upload_dir
        self.processor = DocumentProcessor()
        self.embedding_generator = EmbeddingGenerator()
        os.makedirs(upload_dir, exist_ok=True)
    
    # ========== VALIDAÇÃO E SEGURANÇA ==========
    
    def _verify_agent_access(self, agent_id: str, document_id: str) -> bool:
        """Verifica se agente pode acessar documento - CRÍTICO PARA SEGURANÇA"""
        
        document = self.db.query(Document).filter(
            Document.id == document_id,
            Document.agent_id == agent_id  # Filtra por agente_id
        ).first()
        
        return document is not None
    
    def _verify_agent_exists(self, agent_id: str) -> bool:
        """Verifica se agente existe"""
        return self.db.query(Agent).filter(Agent.id == agent_id).first() is not None
    
    def _audit_access(self, agent_id: str, document_id: str, action: str, success: bool):
        """Registra todas as tentativas de acesso (sucesso e falha)"""
        
        audit = AuditLog(
            agent_id=agent_id,
            action=action,
            resource_type="document",
            resource_id=document_id,
            new_values={"success": success},
        )
        self.db.add(audit)
        self.db.commit()
    
    # ========== UPLOAD E PROCESSAMENTO ==========
    
    def upload_document(
        self,
        agent_id: str,
        filename: str,
        file_content: bytes,
        description: Optional[str] = None,
        categories: Optional[List[str]] = None,
        uploaded_by: Optional[str] = None,
    ) -> Document:
        """Upload de documento exclusivo para um agente"""
        
        # Validar agente
        if not self._verify_agent_exists(agent_id):
            self._audit_access(agent_id, "unknown", "upload", False)
            raise ValueError(f"Agente {agent_id} não existe")
        
        # Validar tipo de ficheiro
        allowed_extensions = {'.pdf', '.txt', '.docx', '.md'}
        file_ext = os.path.splitext(filename)[1].lower()
        
        if file_ext not in allowed_extensions:
            self._audit_access(agent_id, "unknown", "upload", False)
            raise ValueError(f"Tipo de ficheiro não suportado: {file_ext}")
        
        try:
            # 1. Guardar ficheiro
            doc_id = str(uuid4())
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            safe_filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
            file_path = os.path.join(self.upload_dir, f"{timestamp}_{doc_id}_{safe_filename}")
            
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            # 2. Extrair texto
            original_content = self._extract_text(file_path, file_ext)
            
            # 3. Criar registro de documento
            document = Document(
                id=doc_id,
                agent_id=agent_id,  # CRÍTICO: Vincular ao agente
                filename=filename,
                file_path=file_path,
                file_size=len(file_content),
                file_type=file_ext,
                original_content=original_content,
                document_description=description,
                categories=categories or [],
                uploaded_by=uploaded_by or "system",
                processing_status="processing",
            )
            
            self.db.add(document)
            self.db.flush()
            
            # 4. Processar chunks e embeddings
            self._process_and_chunk(document, original_content)
            
            # 5. Atualizar status
            document.is_processed = True
            document.processing_status = "completed"
            self.db.commit()
            
            # Auditoria
            self._audit_access(agent_id, doc_id, "upload", True)
            logger.info(f"Documento {doc_id} criado para agente {agent_id}")
            
            return document
        
        except Exception as e:
            self.db.rollback()
            self._audit_access(agent_id, "unknown", "upload", False)
            logger.error(f"Erro ao fazer upload: {e}")
            raise
    
    def _extract_text(self, file_path: str, file_ext: str) -> str:
        """Extrai texto do ficheiro"""
        
        try:
            if file_ext == '.pdf':
                return self.processor.extract_text_from_pdf(file_path)
            elif file_ext in {'.txt', '.md'}:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return f.read()
            elif file_ext == '.docx':
                return self.processor.extract_text_from_docx(file_path)
        except Exception as e:
            logger.error(f"Erro ao extrair texto: {e}")
            return ""
    
    def _process_and_chunk(self, document: Document, content: str):
        """Divide documento em chunks e gera embeddings"""
        
        # Dividir em chunks (512 caracteres com 50 caracteres de overlap)
        chunks = self._create_chunks(content, chunk_size=512, overlap=50)
        
        for chunk_num, chunk_text in enumerate(chunks):
            try:
                # Criar chunk
                chunk = DocumentChunk(
                    document_id=document.id,
                    chunk_number=chunk_num,
                    chunk_text=chunk_text,
                    chunk_size=len(chunk_text),
                )
                self.db.add(chunk)
                self.db.flush()
                
                # Gerar embedding
                embedding_vector = self.embedding_generator.generate_embedding(chunk_text)
                
                embedding = DocumentEmbedding(
                    chunk_id=chunk.id,
                    embedding=embedding_vector,
                )
                self.db.add(embedding)
            
            except Exception as e:
                logger.error(f"Erro ao processar chunk {chunk_num}: {e}")
        
        self.db.commit()
    
    def _create_chunks(self, text: str, chunk_size: int = 512, overlap: int = 50):
        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunks.append(text[start:end])

            if end == text_len:
                break  # evita loop infinito no último chunk

            start = max(end - overlap, start + 1)

        return chunks

    
    # ========== ACESSO E BUSCA ==========
    
    def get_agent_documents(self, agent_id: str) -> List[Document]:
        """Lista documentos de um agente (SEGURO - filtra por agent_id)"""
        
        # Verificação de segurança
        if not self._verify_agent_exists(agent_id):
            return []
        
        return self.db.query(Document).filter(
            Document.agent_id == agent_id,  # CRÍTICO: Filtro por agente
            Document.is_archived == False
        ).order_by(Document.uploaded_at.desc()).all()
    
    def get_document(self, agent_id: str, document_id: str) -> Optional[Document]:
        """Obtém documento com validação de acesso"""
        
        # Validação CRÍTICA de segurança
        if not self._verify_agent_access(agent_id, document_id):
            self._audit_access(agent_id, document_id, "read", False)
            raise PermissionError(f"Agente {agent_id} não tem acesso ao documento {document_id}")
        
        self._audit_access(agent_id, document_id, "read", True)
        
        return self.db.query(Document).filter(
            Document.id == document_id,
            Document.agent_id == agent_id
        ).first()
    
    def search_documents_semantic(
        self,
        agent_id: str,
        query: str,
        top_k: int = 5,
    ) -> List[Dict]:
        """Busca semântica em documentos do agente"""
        
        # Validação de segurança
        if not self._verify_agent_exists(agent_id):
            return []
        
        try:
            # Gerar embedding da query
            query_embedding = self.embedding_generator.generate_embedding(query)
            
            # Buscar chunks do agente APENAS
            chunks = self.db.query(DocumentChunk).join(
                Document, DocumentChunk.document_id == Document.id
            ).filter(
                Document.agent_id == agent_id  # CRÍTICO: Filtro por agente
            ).all()
            
            # Calcular similaridade
            similarities = []
            
            for chunk in chunks:
                if chunk.embeddings:
                    embedding = chunk.embeddings[0]
                    similarity = self._cosine_similarity(
                        query_embedding,
                        embedding.embedding
                    )
                    similarities.append({
                        "chunk": chunk,
                        "similarity": similarity,
                        "document": chunk.document,
                    })
            
            # Ordenar e retornar top_k
            similarities.sort(key=lambda x: x["similarity"], reverse=True)
            
            results = []
            for item in similarities[:top_k]:
                results.append({
                    "document_id": item["document"].id,
                    "filename": item["document"].filename,
                    "chunk_number": item["chunk"].chunk_number,
                    "chunk_text": item["chunk"].chunk_text,
                    "similarity": item["similarity"],
                })
            
            self._audit_access(agent_id, "search", "search", True)
            return results
        
        except Exception as e:
            logger.error(f"Erro na busca semântica: {e}")
            self._audit_access(agent_id, "search", "search", False)
            return []
    
    # ========== GESTÃO ==========
    
    def delete_document(self, agent_id: str, document_id: str) -> bool:
        """Deleta documento com validação de acesso"""
        
        # Validação CRÍTICA
        if not self._verify_agent_access(agent_id, document_id):
            self._audit_access(agent_id, document_id, "delete", False)
            raise PermissionError(f"Agente {agent_id} não tem acesso ao documento")
        
        document = self.db.query(Document).filter(
            Document.id == document_id,
            Document.agent_id == agent_id
        ).first()
        
        if not document:
            return False
        
        try:
            # Apagar ficheiro
            if os.path.exists(document.file_path):
                os.remove(document.file_path)
            
            # Apagar registos da BD (cascata automática)
            self.db.delete(document)
            self.db.commit()
            
            self._audit_access(agent_id, document_id, "delete", True)
            logger.info(f"Documento {document_id} deletado para agente {agent_id}")
            
            return True
        
        except Exception as e:
            self.db.rollback()
            logger.error(f"Erro ao deletar documento: {e}")
            self._audit_access(agent_id, document_id, "delete", False)
            return False
    
    def archive_document(self, agent_id: str, document_id: str) -> bool:
        """Arquiva documento (soft delete)"""
        
        if not self._verify_agent_access(agent_id, document_id):
            raise PermissionError(f"Acesso negado ao documento")
        
        document = self.db.query(Document).filter(
            Document.id == document_id,
            Document.agent_id == agent_id
        ).first()
        
        if not document:
            return False
        
        document.is_archived = True
        document.updated_at = datetime.utcnow()
        self.db.commit()
        
        return True
    
    # ========== UTILITÁRIOS ==========
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calcula similaridade cosina"""
        
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = sum(a ** 2 for a in vec1) ** 0.5
        magnitude2 = sum(b ** 2 for b in vec2) ** 0.5
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    def document_to_dict(self, document: Document) -> Dict:
        """Converte documento para dict"""
        
        return {
            "id": document.id,
            "filename": document.filename,
            "description": document.document_description,
            "file_size": document.file_size,
            "file_type": document.file_type,
            "categories": document.categories,
            "uploaded_at": document.uploaded_at.isoformat() if document.uploaded_at else None,
            "is_processed": document.is_processed,
            "chunks_count": len(document.chunks),
        }
