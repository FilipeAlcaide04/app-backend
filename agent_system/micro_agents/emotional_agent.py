"""
Emotional Agent - Perspectiva Emocional e Intuitiva
Foca em sentimentos, valores pessoais e dimensão humana
"""

from agent_system.base_micro_agent import BaseMicroAgent, MicroAgentThinkingType
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class EmotionalAgent(BaseMicroAgent):
    """
    Agente Emocional - Processamento emocional e intuitivo
    Foca em: sentimentos, valores, dimensão humana, bem-estar
    """
    
    def __init__(self, agent_id: str, micro_agent_id: str, db):
        super().__init__(
            agent_id=agent_id,
            micro_agent_id=micro_agent_id,
            thinking_type=MicroAgentThinkingType.EMOTIONAL,
            db=db
        )
        self.perspective_name = "Emotional"
        self.description = "Perspectiva emocional e intuitiva"
    
    async def think(self, query: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Processa query com perspectiva emocional
        """
        logger.info(f"[{self.perspective_name}] Processando: {query}")
        
        # Contexto disponível
        documents = context.get("documents", {})
        user_context = context.get("user_context", {})
        memories = context.get("memories", [])
        neural_modifiers = context.get("neural_modifiers", {}).get(self.micro_agent_id, {})
        
        # Aplicar modificadores neurais
        confidence = 0.75 + neural_modifiers.get("confidence_boost", 0)
        temperature = neural_modifiers.get("temperature", 0.9)
        
        # Usar LLM para gerar perspectiva emocional
        perspective = await self._generate_emotional_perspective(
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
            "reasoning": "Análise com consideração de dimensão emocional e humana",
            "documents_used": documents.get("documents", []) if documents.get("has_documents") else []
        }
    
    async def _generate_emotional_perspective(
        self,
        query: str,
        documents: Dict,
        user_context: Dict,
        memories: list,
        temperature: float
    ) -> str:
        """
        Gera perspectiva emocional usando LLM
        """
        from llm_logic.llm_client import LLMClient
        
        llm = LLMClient()
        
        # Construir prompt com contexto
        doc_context = ""
        if documents.get("has_documents"):
            doc_list = documents.get("documents", [])
            if doc_list:
                doc_context = "Documentos relacionados disponíveis:\n"
                for doc in doc_list[:3]:
                    doc_context += f"- {doc.get('filename', 'Documento')}: {doc.get('description', '')}\n"
        
        prompt = f"""
Você é um agente emocional que entende a dimensão humana das questões.

Query: {query}

{doc_context}

Forneça uma perspectiva que considere:
1. Sentimentos e bem-estar das pessoas envolvidas
2. Valores e significado pessoal
3. Intuição e reconhecimento de padrões
4. Empatia e compreensão

Seja autêntico e emocional. Expresse genuinamente como você sente sobre o assunto.
"""
        
        response = llm.generate(prompt)
        return response
