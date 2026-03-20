"""
Critical Agent - Perspectiva Crítica e Questionadora
Foca em identificar problemas, questionar premissas e apontar riscos
"""

from agent_system.base_micro_agent import BaseMicroAgent, MicroAgentThinkingType
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class CriticalAgent(BaseMicroAgent):
    """
    Agente Crítico - Análise crítica e questionadora
    Foca em: problemas, riscos, questões, alternativas
    """
    
    def __init__(self, agent_id: str, micro_agent_id: str, db):
        super().__init__(
            agent_id=agent_id,
            micro_agent_id=micro_agent_id,
            thinking_type=MicroAgentThinkingType.CRITICAL,
            db=db
        )
        self.perspective_name = "Critical"
        self.description = "Perspectiva crítica e questionadora"
    
    async def think(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa query com perspectiva crítica
        """
        logger.info(f"[{self.perspective_name}] Processando: {query}")
        
        # Contexto disponível
        documents = context.get("documents", {})
        user_context = context.get("user_context", {})
        memories = context.get("memories", [])
        neural_modifiers = context.get("neural_modifiers", {}).get(self.micro_agent_id, {})
        
        # Aplicar modificadores neurais
        confidence = 0.8 + neural_modifiers.get("confidence_boost", 0)
        temperature = neural_modifiers.get("temperature", 0.6)
        
        # Usar LLM para gerar perspectiva crítica
        perspective = await self._generate_critical_perspective(
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
            "reasoning": "Análise crítica com foco em problemas e alternativas",
            "documents_used": documents.get("documents", []) if documents.get("has_documents") else []
        }
    
    async def _generate_critical_perspective(
        self,
        query: str,
        documents: Dict,
        user_context: Dict,
        memories: list,
        temperature: float
    ) -> str:
        """
        Gera perspectiva crítica usando LLM
        """
        from llm_logic.llm_client import LLMClient
        
        llm = LLMClient()
        
        # Construir prompt com contexto
        doc_context = ""
        if documents.get("has_documents"):
            doc_list = documents.get("documents", [])
            if doc_list:
                doc_context = "Documentos para análise crítica:\n"
                for doc in doc_list[:3]:
                    doc_context += f"- {doc.get('filename', 'Documento')}: {doc.get('description', '')}\n"
        
        prompt = f"""
Você é um agente crítico que questiona premissas e identifica problemas.

Query: {query}

{doc_context}

Forneça uma análise crítica que considere:
1. Problemas potenciais e riscos
2. Questões e premissas questionáveis
3. Alternativas não consideradas
4. Implicações a longo prazo

Seja questionador mas construtivo. Identifique fraquezas e gaps.
"""
        
        response = llm.generate(prompt)
        return response
