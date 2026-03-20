"""
Social Agent - Perspectiva Social e Interpessoal
Foca em dinâmica social, empatia, comunicação e impacto humano
"""

from agent_system.base_micro_agent import BaseMicroAgent, MicroAgentThinkingType
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class SocialAgent(BaseMicroAgent):
    """
    Agente Social - Entende dinâmica interpessoal
    Foca em: comunicação, empatia, colaboração, impacto social
    """
    
    def __init__(self, agent_id: str, micro_agent_id: str, db):
        super().__init__(
            agent_id=agent_id,
            micro_agent_id=micro_agent_id,
            thinking_type=MicroAgentThinkingType.SOCIAL,
            db=db
        )
        self.perspective_name = "Social"
        self.description = "Perspectiva social e interpessoal"
    
    async def think(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa query com perspectiva social
        """
        logger.info(f"[{self.perspective_name}] Processando: {query}")
        
        # Contexto disponível
        documents = context.get("documents", {})
        user_context = context.get("user_context", {})
        memories = context.get("memories", [])
        neural_modifiers = context.get("neural_modifiers", {}).get(self.micro_agent_id, {})
        
        # Aplicar modificadores neurais
        confidence = 0.8 + neural_modifiers.get("confidence_boost", 0)
        temperature = neural_modifiers.get("temperature", 0.8)
        
        # Usar LLM para gerar perspectiva social
        perspective = await self._generate_social_perspective(
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
            "reasoning": "Análise da dinâmica social e impacto interpessoal",
            "documents_used": documents.get("documents", []) if documents.get("has_documents") else []
        }
    
    async def _generate_social_perspective(
        self,
        query: str,
        documents: Dict,
        user_context: Dict,
        memories: list,
        temperature: float
    ) -> str:
        """
        Gera perspectiva social usando LLM
        """
        from llm_logic.llm_client import LLMClient
        
        llm = LLMClient()
        
        # Construir prompt com contexto
        doc_context = ""
        if documents.get("has_documents"):
            doc_list = documents.get("documents", [])
            if doc_list:
                doc_context = "Documentos relevantes encontrados:\n"
                for doc in doc_list[:3]:
                    doc_context += f"- {doc.get('filename', 'Documento')}: {doc.get('description', '')}\n"
        
        user_info = ""
        if user_context:
            user_info = f"Contexto do utilizador: {user_context.get('role', 'Utilizador')}\n"
        
        prompt = f"""
Você é um agente social que analisa questões do ponto de vista interpessoal e social.

Query: {query}

{user_info}
{doc_context}

Forneça uma perspectiva que considere:
1. Dinâmica social e colaboração
2. Impacto nas pessoas envolvidas
3. Comunicação e empatia
4. Perspectiva humana

Seja conversacional e genuinamente interessado. Não mencione que é uma "perspectiva social".
"""
        
        response = llm.generate(prompt)
        return response
