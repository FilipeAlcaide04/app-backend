"""
Logical Agent - Perspectiva Lógica e Racional
Foca em análise racional, estrutura, dados e conclusões lógicas
"""

from agent_system.base_micro_agent import BaseMicroAgent, MicroAgentThinkingType
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class LogicalAgent(BaseMicroAgent):
    """
    Agente Lógico - Análise racional e estruturada
    Foca em: lógica, dados, estrutura, conclusões baseadas em fatos
    """
    
    def __init__(self, agent_id: str, micro_agent_id: str, db):
        super().__init__(
            agent_id=agent_id,
            micro_agent_id=micro_agent_id,
            thinking_type=MicroAgentThinkingType.LOGICAL,
            db=db
        )
        self.perspective_name = "Logical"
        self.description = "Perspectiva lógica e racional"
    
    async def think(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa query com perspectiva lógica
        """
        logger.info(f"[{self.perspective_name}] Processando: {query}")
        
        # Contexto disponível
        documents = context.get("documents", {})
        user_context = context.get("user_context", {})
        memories = context.get("memories", [])
        neural_modifiers = context.get("neural_modifiers", {}).get(self.micro_agent_id, {})
        
        # Aplicar modificadores neurais
        confidence = 0.85 + neural_modifiers.get("confidence_boost", 0)
        temperature = neural_modifiers.get("temperature", 0.5)
        
        # Usar LLM para gerar perspectiva lógica
        perspective = await self._generate_logical_perspective(
            query=query,
            documents=documents,
            user_context=user_context,
            memories=memories,
            temperature=temperature
        )
        
        return {
            "agent_type": self.perspective_name,
            "perspective": perspective,
            "confidence": confidence,
            "reasoning": "Análise racional e estruturada baseada em fatos",
            "documents_used": documents.get("documents", []) if documents.get("has_documents") else []
        }
    
    async def _generate_logical_perspective(
        self,
        query: str,
        documents: Dict,
        user_context: Dict,
        memories: list,
        temperature: float
    ) -> str:
        """
        Gera perspectiva lógica usando LLM
        """
        from llm_logic.llm_client import LLMClient
        
        llm = LLMClient()
        
        # Construir prompt com contexto
        doc_context = ""
        if documents.get("has_documents"):
            doc_list = documents.get("documents", [])
            if doc_list:
                doc_context = "Documentos técnicos encontrados:\n"
                for doc in doc_list[:3]:
                    doc_context += f"- {doc.get('filename', 'Documento')}: {doc.get('description', '')}\n"
        
        prompt = f"""
Você é um agente lógico que analisa questões com pensamento crítico e racional.

Query: {query}

{doc_context}

Forneça uma análise que considere:
1. Fatos e dados disponíveis
2. Estrutura lógica do problema
3. Conclusões baseadas em evidências
4. Implicações técnicas

Seja preciso e estruturado. Cite os documentos consultados quando relevante.
"""
        
        response = llm.generate(prompt)
        return response
