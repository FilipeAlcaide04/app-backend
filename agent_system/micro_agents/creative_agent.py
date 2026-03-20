"""
Creative Agent - Perspectiva Criativa e Inovadora
Foca em ideias novas, conexões não-óbvias e possibilidades
"""

from agent_system.base_micro_agent import BaseMicroAgent, MicroAgentThinkingType
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class CreativeAgent(BaseMicroAgent):
    """
    Agente Criativo - Pensamento inovador e criativo
    Foca em: ideias novas, conexões criativas, possibilidades
    """
    
    def __init__(self, agent_id: str, micro_agent_id: str, db):
        super().__init__(
            agent_id=agent_id,
            micro_agent_id=micro_agent_id,
            thinking_type=MicroAgentThinkingType.CREATIVE,
            db=db
        )
        self.perspective_name = "Creative"
        self.description = "Perspectiva criativa e inovadora"
    
    async def think(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa query com perspectiva criativa
        """
        logger.info(f"[{self.perspective_name}] Processando: {query}")
        
        # Contexto disponível
        documents = context.get("documents", {})
        user_context = context.get("user_context", {})
        memories = context.get("memories", [])
        neural_modifiers = context.get("neural_modifiers", {}).get(self.micro_agent_id, {})
        
        # Aplicar modificadores neurais
        confidence = 0.70 + neural_modifiers.get("confidence_boost", 0)
        temperature = neural_modifiers.get("temperature", 0.95)
        
        # Usar LLM para gerar perspectiva criativa
        perspective = await self._generate_creative_perspective(
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
            "reasoning": "Análise com foco em inovação e pensamento criativo",
            "documents_used": documents.get("documents", []) if documents.get("has_documents") else []
        }
    
    async def _generate_creative_perspective(
        self,
        query: str,
        documents: Dict,
        user_context: Dict,
        memories: list,
        temperature: float
    ) -> str:
        """
        Gera perspectiva criativa usando LLM
        """
        from llm_logic.llm_client import LLMClient
        
        llm = LLMClient()
        
        # Construir prompt com contexto
        doc_context = ""
        if documents.get("has_documents"):
            doc_list = documents.get("documents", [])
            if doc_list:
                doc_context = "Documentos para inspiração criativa:\n"
                for doc in doc_list[:3]:
                    doc_context += f"- {doc.get('filename', 'Documento')}: {doc.get('description', '')}\n"
        
        prompt = f"""
Você é um agente criativo que gera ideias inovadoras.

Query: {query}

{doc_context}

Forneça uma perspectiva criativa que considere:
1. Ideias novas e fora da caixa
2. Conexões criativas e inesperadas
3. Possibilidades até agora não exploradas
4. Abordagens inovadoras

Seja imaginativo e ousado. Proponha soluções criativas e originais.
"""
        
        response = llm.generate(prompt)
        return response
