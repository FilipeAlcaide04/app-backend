"""
Core Cognitive System - Sistema de micro-agentes cognitivos
Cada micro-agente representa um tipo diferente de pensamento
"""

from sqlalchemy.orm import Session
from data.schema_cognitive import (
    Agent, MicroAgent, MicroAgentType, Memory, ThoughtProcess, ThoughtContribution
)
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from abc import ABC, abstractmethod
import json
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class MicroAgentThinkingType(str, Enum):
    """Tipos de pensamento cognitivo"""
    LOGICAL = "logical"  # Análise racional, matemática
    EMOTIONAL = "emotional"  # Processamento emocional, empatia
    CRITICAL = "critical"  # Questionamento, análise crítica
    CREATIVE = "creative"  # Ideias inovadoras, conexões não-óbvias
    ANALYTICAL = "analytical"  # Decomposição e análise detalhada
    ETHICAL = "ethical"  # Considerações morais e valores
    SOCIAL = "social"  # Dinâmica interpessoal, empatia social
    CONTEXTUAL = "contextual"  # Entendimento de contexto e circunstâncias
    INTUITIVE = "intuitive"  # Gut feelings e reconhecimento de padrões
    STRATEGIC = "strategic"  # Planejamento a longo prazo


class BaseMicroAgent(ABC):
    """Base para todos os micro-agentes"""
    
    def __init__(
        self,
        agent_id: str,
        micro_agent_id: str,
        thinking_type: MicroAgentThinkingType,
        db: Session,
    ):
        self.agent_id = agent_id
        self.micro_agent_id = micro_agent_id
        self.thinking_type = thinking_type
        self.db = db
        self.micro_agent_instance = self._load_instance()
        
        # Inicializar LLM Client (lazy load)
        self._llm_client = None
    
    @property
    def llm_client(self):
        """Lazy load do LLM Client"""
        if self._llm_client is None:
            try:
                from llm_logic.llm_client import LLMClient
                self._llm_client = LLMClient()
            except Exception as e:
                logger.error(f"Erro ao inicializar LLMClient: {e}")
                self._llm_client = None
        return self._llm_client
    
    def _load_instance(self) -> MicroAgent:
        """Carrega instância de micro-agente do banco"""
        instance = self.db.query(MicroAgent).filter(
            MicroAgent.id == self.micro_agent_id
        ).first()
        
        if not instance:
            raise ValueError(f"Micro-agente {self.micro_agent_id} não encontrado")
        
        return instance
    
    def _get_system_prompt(self) -> str:
        """Retorna o prompt do sistema (custom ou padrão)"""
        if self.micro_agent_instance.custom_prompt:
            return self.micro_agent_instance.custom_prompt
        return self.micro_agent_instance.type.system_prompt
    
    @abstractmethod
    def think(self, query: str, context: Dict) -> Dict[str, Any]:
        """
        Realiza pensamento específico deste micro-agente
        
        Returns:
            {
                "perspective": str,  # O que este agente pensa
                "confidence": float,  # 0-1
                "supporting_arguments": List[str],
                "opposing_arguments": List[str],
                "recommended_action": Optional[str],
            }
        """
        pass
    
    def update_focus(self, focus: str):
        """Atualiza foco atual deste micro-agente"""
        self.micro_agent_instance.current_focus = focus
        self.micro_agent_instance.last_activated = datetime.utcnow()
        self.db.commit()
    
    def update_confidence(self, confidence: float):
        """Atualiza nível de confiança"""
        self.micro_agent_instance.confidence_level = max(0.0, min(1.0, confidence))
        self.db.commit()
    
    def get_weight(self) -> float:
        """Retorna peso deste micro-agente nas decisões"""
        return self.micro_agent_instance.custom_weight or self.micro_agent_instance.type.default_weight


class LogicalAgent(BaseMicroAgent):
    """Micro-agente focado em análise racional e lógica"""
    
    def __init__(self, agent_id: str, micro_agent_id: str, db: Session):
        super().__init__(agent_id, micro_agent_id, MicroAgentThinkingType.LOGICAL, db)
    
    def think(self, query: str, context: Dict) -> Dict[str, Any]:
        """Análise lógica e racional com LLM"""
        
        system_prompt = self._get_system_prompt()
        
        logger.info(f"LogicalAgent.think: Iniciando com query='{query[:50]}...'")
        logger.info(f"  - System prompt: {system_prompt[:80] if system_prompt else 'None'}...")
        logger.info(f"  - LLM Client: {self.llm_client}")
        
        # Se tem LLM disponível, usar
        if self.llm_client:
            try:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"{query}\n\nRetorne uma análise concisa em uma linha."}
                ]
                logger.info(f"  - Chamando LLM com {len(messages)} messages...")
                perspective = self.llm_client.chat_completion(messages, temperature=0.3, max_tokens=200)
                logger.info(f"  - Resposta LLM: {perspective[:100] if perspective else 'vazio'}...")
            except Exception as e:
                logger.error(f"Erro ao chamar LLM: {e}", exc_info=True)
                perspective = f"Análise lógica: {query}"
        else:
            logger.warning("LLM Client não disponível, usando fallback")
            # Fallback se não tiver LLM
            perspective = f"Análise lógica: {query}"
        
        return {
            "perspective": perspective,
            "confidence": 0.8,
            "supporting_arguments": [],
            "opposing_arguments": [],
            "recommended_action": "Proceder com abordagem racional",
        }


class EmotionalAgent(BaseMicroAgent):
    """Micro-agente focado em processamento emocional"""
    
    def __init__(self, agent_id: str, micro_agent_id: str, db: Session):
        super().__init__(agent_id, micro_agent_id, MicroAgentThinkingType.EMOTIONAL, db)
    
    def think(self, query: str, context: Dict) -> Dict[str, Any]:
        """Processamento emocional e empático com LLM"""
        
        system_prompt = self._get_system_prompt()
        
        if self.llm_client:
            try:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"{query}\n\nRetorne uma resposta empática e considerada em uma linha."}
                ]
                perspective = self.llm_client.chat_completion(messages, temperature=0.7, max_tokens=200)
            except Exception as e:
                logger.error(f"Erro ao chamar LLM: {e}")
                perspective = f"Perspectiva emocional: {query}"
        else:
            perspective = f"Perspectiva emocional: {query}"
        
        return {
            "perspective": perspective,
            "confidence": 0.75,
            "supporting_arguments": [],
            "opposing_arguments": [],
            "recommended_action": "Considerar bem-estar emocional",
        }


class CriticalAgent(BaseMicroAgent):
    """Micro-agente focado em pensamento crítico"""
    
    def __init__(self, agent_id: str, micro_agent_id: str, db: Session):
        super().__init__(agent_id, micro_agent_id, MicroAgentThinkingType.CRITICAL, db)
    
    def think(self, query: str, context: Dict) -> Dict[str, Any]:
        """Questionamento e análise crítica com LLM"""
        
        system_prompt = self._get_system_prompt()
        
        if self.llm_client:
            try:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"{query}\n\nRetorne uma análise crítica e questionadora em uma linha."}
                ]
                perspective = self.llm_client.chat_completion(messages, temperature=0.4, max_tokens=200)
            except Exception as e:
                logger.error(f"Erro ao chamar LLM: {e}")
                perspective = f"Análise crítica: Questiono {query}"
        else:
            perspective = f"Análise crítica: Questiono {query}"
        
        return {
            "perspective": perspective,
            "confidence": 0.7,
            "supporting_arguments": [],
            "opposing_arguments": [],
            "recommended_action": "Investigar mais antes de decidir",
        }


class CreativeAgent(BaseMicroAgent):
    """Micro-agente focado em pensamento criativo"""
    
    def __init__(self, agent_id: str, micro_agent_id: str, db: Session):
        super().__init__(agent_id, micro_agent_id, MicroAgentThinkingType.CREATIVE, db)
    
    def think(self, query: str, context: Dict) -> Dict[str, Any]:
        """Ideação criativa com LLM"""
        
        system_prompt = self._get_system_prompt()
        
        if self.llm_client:
            try:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"{query}\n\nRetorne uma ideia criativa e inovadora em uma linha."}
                ]
                perspective = self.llm_client.chat_completion(messages, temperature=0.9, max_tokens=200)
            except Exception as e:
                logger.error(f"Erro ao chamar LLM: {e}")
                perspective = f"Ideia criativa: {query}"
        else:
            perspective = f"Ideia criativa: {query}"
        
        return {
            "perspective": perspective,
            "confidence": 0.65,
            "supporting_arguments": [],
            "opposing_arguments": [],
            "recommended_action": "Explorar possibilidade criativa",
        }


class EthicalAgent(BaseMicroAgent):
    """Micro-agente focado em considerações éticas"""
    
    def __init__(self, agent_id: str, micro_agent_id: str, db: Session):
        super().__init__(agent_id, micro_agent_id, MicroAgentThinkingType.ETHICAL, db)
    
    def think(self, query: str, context: Dict) -> Dict[str, Any]:
        """Análise ética e moral com LLM"""
        
        system_prompt = self._get_system_prompt()
        
        if self.llm_client:
            try:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"{query}\n\nRetorne uma análise ética considerada em uma linha."}
                ]
                perspective = self.llm_client.chat_completion(messages, temperature=0.5, max_tokens=200)
            except Exception as e:
                logger.error(f"Erro ao chamar LLM: {e}")
                perspective = f"Perspectiva ética: {query}"
        else:
            perspective = f"Perspectiva ética: {query}"
        
        return {
            "perspective": perspective,
            "confidence": 0.85,
            "supporting_arguments": [],
            "opposing_arguments": [],
            "recommended_action": "Agir eticamente",
        }


class SocialAgent(BaseMicroAgent):
    """Micro-agente focado em dinâmica social"""
    
    def __init__(self, agent_id: str, micro_agent_id: str, db: Session):
        super().__init__(agent_id, micro_agent_id, MicroAgentThinkingType.SOCIAL, db)
    
    def think(self, query: str, context: Dict) -> Dict[str, Any]:
        """Análise social e interpessoal com LLM"""
        
        system_prompt = self._get_system_prompt()
        
        if self.llm_client:
            try:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"{query}\n\nRetorne uma perspectiva social considerada em uma linha."}
                ]
                perspective = self.llm_client.chat_completion(messages, temperature=0.6, max_tokens=200)
            except Exception as e:
                logger.error(f"Erro ao chamar LLM: {e}")
                perspective = f"Perspectiva social: {query}"
        else:
            perspective = f"Perspectiva social: {query}"
        
        return {
            "perspective": perspective,
            "confidence": 0.7,
            "supporting_arguments": [],
            "opposing_arguments": [],
            "recommended_action": "Considerar impacto social",
        }


# Registro de tipos de micro-agentes
MICRO_AGENT_REGISTRY = {
    MicroAgentThinkingType.LOGICAL: LogicalAgent,
    MicroAgentThinkingType.EMOTIONAL: EmotionalAgent,
    MicroAgentThinkingType.CRITICAL: CriticalAgent,
    MicroAgentThinkingType.CREATIVE: CreativeAgent,
    MicroAgentThinkingType.ETHICAL: EthicalAgent,
    MicroAgentThinkingType.SOCIAL: SocialAgent,
}


def create_micro_agent(
    agent_id: str,
    micro_agent_id: str,
    thinking_type: str,
    db: Session,
) -> BaseMicroAgent:
    """Factory para criar instância de micro-agente"""
    
    try:
        thinking_enum = MicroAgentThinkingType(thinking_type)
        agent_class = MICRO_AGENT_REGISTRY.get(thinking_enum)
        
        if not agent_class:
            logger.warning(f"Tipo de micro-agente {thinking_type} não tem implementação")
            # Retorna agente genérico
            return BaseMicroAgent(agent_id, micro_agent_id, thinking_enum, db)
        
        return agent_class(agent_id, micro_agent_id, db)
    
    except ValueError as e:
        logger.error(f"Tipo de pensamento inválido: {thinking_type}")
        raise
