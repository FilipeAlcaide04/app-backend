"""
Document Awareness - Mecanismo inteligente para consulta de documentos
Agentes entendem quando e quais documentos consultar
"""

from sqlalchemy.orm import Session
from data.schema_cognitive import (
    Document, DocumentChunk, DocumentEmbedding, Agent, Memory, MemoryEmbedding
)
from llm_logic.embedding_generator import EmbeddingGenerator
from typing import List, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class DocumentAwareness:
    """
    Sistema inteligente que permite micro-agentes perceberem 
    e consultarem documentos relevantes
    """
    
    def __init__(self, db: Session, agent_id: str):
        self.db = db
        self.agent_id = agent_id
        self.embedding_generator = EmbeddingGenerator()
        self.agent = self._load_agent()
    
    def _load_agent(self) -> Agent:
        """Carrega agente"""
        agent = self.db.query(Agent).filter(Agent.id == self.agent_id).first()
        if not agent:
            raise ValueError(f"Agente {self.agent_id} não encontrado")
        return agent
    
    def should_consult_documents(self, query: str) -> bool:
        """
        Determina se vale a pena consultar documentos para esta query
        Evita overhead desnecessário
        """
        
        # Verificar se agente tem documentos
        doc_count = self.db.query(Document).filter(
            Document.agent_id == self.agent_id,
            Document.is_processed == True,
            Document.is_archived == False
        ).count()
        
        if doc_count == 0:
            return False
        
        # Verificar se query parece solicitar informação de documentos
        doc_keywords = ["documento", "arquivo", "file", "texto", "descreve", "contém",
                       "explica em", "segundo", "conforme", "baseado", "referencia"]
        
        query_lower = query.lower()
        has_doc_keyword = any(kw in query_lower for kw in doc_keywords)
        
        if has_doc_keyword:
            return True
        
        # Usar embedding para análise semântica se não houver keywords
        return self._semantic_doc_relevance(query) > 0.6
    
    def find_relevant_documents(
        self,
        query: str,
        limit: int = 3,
        similarity_threshold: float = 0.4
    ) -> List[Dict]:
        """
        Encontra documentos semanticamente relevantes para a query
        
        Retorna: [
            {
                "document_id": str,
                "filename": str,
                "similarity_score": float,
                "chunks": [
                    {"chunk_text": str, "similarity": float}
                ]
            }
        ]
        """
        
        # 1. Gerar embedding da query
        try:
            query_embedding = self.embedding_generator.generate_embedding(query)
            if not query_embedding:
                logger.warning("Não foi possível gerar embedding da query")
                return []
        except Exception as e:
            logger.error(f"Erro ao gerar embedding: {e}")
            return []
        
        # 2. Buscar documentos deste agente
        documents = self.db.query(Document).filter(
            Document.agent_id == self.agent_id,
            Document.is_processed == True,
            Document.is_archived == False
        ).all()
        
        relevant_docs = []
        
        for doc in documents:
            # Buscar chunks deste documento
            chunks = self.db.query(DocumentChunk).filter(
                DocumentChunk.document_id == doc.id
            ).all()
            
            if not chunks:
                continue
            
            # Calcular similaridade de cada chunk
            chunk_similarities = []
            
            for chunk in chunks:
                similarity = self._calculate_chunk_similarity(
                    query_embedding,
                    chunk
                )
                
                if similarity > similarity_threshold:
                    chunk_similarities.append({
                        "chunk_number": chunk.chunk_number,
                        "chunk_text": chunk.chunk_text[:300] + "..." if len(chunk.chunk_text) > 300 else chunk.chunk_text,
                        "similarity": similarity,
                        "start_page": chunk.start_page,
                        "end_page": chunk.end_page
                    })
            
            if chunk_similarities:
                # Calcular similaridade média do documento
                doc_similarity = sum(s["similarity"] for s in chunk_similarities) / len(chunk_similarities)
                
                relevant_docs.append({
                    "document_id": doc.id,
                    "filename": doc.filename,
                    "description": doc.document_description,
                    "similarity_score": doc_similarity,
                    "chunks": sorted(chunk_similarities, key=lambda x: x["similarity"], reverse=True)[:2],
                    "file_type": doc.file_type,
                    "uploaded_at": doc.uploaded_at.isoformat() if doc.uploaded_at else None
                })
        
        # Ordenar por similaridade e limitar
        relevant_docs = sorted(relevant_docs, key=lambda x: x["similarity_score"], reverse=True)[:limit]
        
        if relevant_docs:
            logger.info(f"Encontrados {len(relevant_docs)} documentos relevantes para agente {self.agent_id}")
        
        return relevant_docs
    
    def get_document_context_for_agent(
        self,
        query: str,
        max_chars: int = 2000
    ) -> Dict[str, any]:
        """
        Prepara contexto de documentos para uso by agentes
        Retorna informação digestível e pronta para LLM
        """
        
        relevant_docs = self.find_relevant_documents(query)
        
        if not relevant_docs:
            return {
                "has_documents": False,
                "documents": [],
                "context_text": "Nenhum documento relevante encontrado."
            }
        
        context_parts = []
        current_length = 0
        
        for doc in relevant_docs:
            doc_text = f"📄 {doc['filename']}\n"
            doc_text += f"Relevância: {doc['similarity_score']:.1%}\n"
            
            if doc['description']:
                doc_text += f"Descrição: {doc['description']}\n"
            
            doc_text += "Excertos relevantes:\n"
            
            for chunk in doc['chunks']:
                chunk_text = f"[Página {chunk['start_page']}-{chunk['end_page']}]\n{chunk['chunk_text']}\n"
                
                if current_length + len(chunk_text) <= max_chars:
                    doc_text += chunk_text
                    current_length += len(chunk_text)
                else:
                    break
            
            if current_length <= max_chars:
                context_parts.append(doc_text)
                current_length += len(doc_text)
            else:
                break
        
        context_text = "\n---\n".join(context_parts)
        
        return {
            "has_documents": True,
            "documents_count": len(relevant_docs),
            "documents": relevant_docs,
            "context_text": context_text,
            "source_info": f"Baseado em {len(relevant_docs)} documento(s)"
        }
    
    def _calculate_chunk_similarity(
        self,
        query_embedding: List[float],
        chunk: DocumentChunk
    ) -> float:
        """Calcula similaridade entre query embedding e chunk"""
        
        try:
            # Gerar embedding do chunk
            chunk_embedding = self.embedding_generator.generate_embedding(chunk.chunk_text)
            
            if not chunk_embedding:
                return 0.0
            
            # Calcular similaridade cosseno
            similarity = self._cosine_similarity(query_embedding, chunk_embedding)
            
            return max(0.0, min(1.0, similarity))
        
        except Exception as e:
            logger.debug(f"Erro ao calcular similaridade de chunk: {e}")
            return 0.0
    
    def _semantic_doc_relevance(self, query: str) -> float:
        """Calcula relevância semântica entre query e documentos disponíveis"""
        
        try:
            query_embedding = self.embedding_generator.generate_embedding(query)
            
            if not query_embedding:
                return 0.0
            
            # Amostrar alguns chunks para estimar relevância
            chunks = self.db.query(DocumentChunk).join(
                Document,
                DocumentChunk.document_id == Document.id
            ).filter(
                Document.agent_id == self.agent_id,
                Document.is_processed == True
            ).limit(5).all()
            
            if not chunks:
                return 0.0
            
            similarities = []
            for chunk in chunks:
                sim = self._calculate_chunk_similarity(query_embedding, chunk)
                similarities.append(sim)
            
            return sum(similarities) / len(similarities) if similarities else 0.0
        
        except Exception as e:
            logger.debug(f"Erro ao calcular relevância semântica: {e}")
            return 0.0
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calcula similaridade cosseno"""
        
        import math
        
        if len(vec1) != len(vec2) or len(vec1) == 0:
            return 0.0
        
        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))
        
        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0
        
        return dot_product / (magnitude1 * magnitude2)
    
    def create_document_memory(
        self,
        document: Document
    ) -> None:
        """
        Cria memória do agente sobre um documento
        Permite ao agente aprender sobre documentos disponíveis
        """
        
        from agent_system.memory_manager_cognitive import MemoryManager
        
        try:
            memory_manager = MemoryManager(self.db, self.agent_id)
            
            # Criar memória sobre o documento
            memory_title = f"Documento: {document.filename}"
            memory_content = f"""
Nome: {document.filename}
Tipo: {document.file_type}
Descrição: {document.document_description or 'N/A'}
Tamanho: {document.file_size} bytes

Conteúdo resumido:
{document.original_content[:500] if document.original_content else 'N/A'}...

Este documento foi disponibilizado para consulta.
"""
            
            memory_manager.create_memory(
                title=memory_title,
                content=memory_content,
                memory_type="semantic",  # Conhecimento factual sobre documentos
                importance_score=0.8,
                emotional_valence=0.0,
                relates_to_topics=["document", "resource", "reference"],
                relates_to_events=[]
            )
            
            logger.info(f"Memória criada para documento {document.filename}")
        
        except Exception as e:
            logger.warning(f"Erro ao criar memória de documento: {e}")
