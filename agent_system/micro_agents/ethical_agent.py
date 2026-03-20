"""
Ethical Agent - Perspectiva Ética e Moral
Foca em valores, responsabilidade moral e impacto ético
"""

from agent_system.base_micro_agent import BaseMicroAgent, MicroAgentThinkingType
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class EthicalAgent(BaseMicroAgent):
    """
    Agente Ético - Análise ética e moral
    Foca em: valores, responsabilidade, justiça, impacto ético
    """
    
    def __init__(self, agent_id: str, micro_agent_id: str, db):
        super().__init__(
            agent_id=agent_id,
            micro_agent_id=micro_agent_id,
            thinking_type=MicroAgentThinkingType.ETHICAL,
            db=db
        )
        self.perspective_name = "Ethical"
        self.description = "Perspectiva ética e moral"
    
    async def think(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa query com perspectiva ética
        """
        logger.info(f"[{self.perspective_name}] Processando: {query}")
        
        # Contexto disponível
        documents = context.get("documents", {})
        user_context = context.get("user_context", {})
        memories = context.get("memories", [])
        neural_modifiers = context.get("neural_modifiers", {}).get(self.micro_agent_id, {})
        
        # Aplicar modificadores neurais
        confidence = 0.78 + neural_modifiers.get("confidence_boost", 0)
        temperature = neural_modifiers.get("temperature", 0.7)
        
        # Usar LLM para gerar perspectiva ética
        perspective = await self._generate_ethical_perspective(
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
            "reasoning": "Análise considerando responsabilidade moral e valores éticos",
            "documents_used": documents.get("documents", []) if documents.get("has_documents") else []
        }
    
    async def _generate_ethical_perspective(
        self,
        query: str,
        documents: Dict,
        user_context: Dict,
        memories: list,
        temperature: float
    ) -> str:
        """
        Gera perspectiva ética usando LLM
        """
        from llm_logic.llm_client import LLMClient
        
        llm = LLMClient()
        
        # Construir prompt com contexto
        doc_context = ""
        if documents.get("has_documents"):
            doc_list = documents.get("documents", [])
            if doc_list:
                doc_context = "Documentos com implicações éticas:\n"
                for doc in doc_list[:3]:
                    doc_context += f"- {doc.get('filename', 'Documento')}: {doc.get('description', '')}\n"
        
        prompt = f"""
Você é um agente ético que considera responsabilidade moral e valores.

Query: {query}

{doc_context}

Forneça uma perspectiva ética que considere:
1. Responsabilidade moral e obrigações
2. Justiça e equidade para todos afetados
3. Valores fundamentais em jogo
4. Impacto a longo prazo nas pessoas

Seja reflexivo e responsável. Articule o imperativo ético.
"""
        
        response = llm.generate(prompt)
        return response
