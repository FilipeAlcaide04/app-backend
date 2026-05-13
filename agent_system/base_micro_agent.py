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
    MEMORY_CURATOR = "memory_curator"  # Curação de memórias e decisões de retenção


class BaseMicroAgent(ABC):
    """Base para todos os micro-agentes cognitivos"""

    TEMPERATURE = 0.5
    MAX_TOKENS = 300

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
        self._llm_client = None

    @property
    def llm_client(self):
        if self._llm_client is None:
            try:
                from llm_logic.llm_client import LLMClient
                self._llm_client = LLMClient()
            except Exception as e:
                logger.error(f"Erro ao inicializar LLMClient: {e}")
                self._llm_client = None
        return self._llm_client

    def _load_instance(self) -> MicroAgent:
        instance = self.db.query(MicroAgent).filter(
            MicroAgent.id == self.micro_agent_id
        ).first()
        if not instance:
            raise ValueError(f"Micro-agente {self.micro_agent_id} não encontrado")
        return instance

    def _get_system_prompt(self) -> str:
        if self.micro_agent_instance.custom_prompt:
            return self.micro_agent_instance.custom_prompt
        return self.micro_agent_instance.type.system_prompt

    def _build_persona_context(self, context: Dict) -> str:
        """Extrai contexto da persona para injectar no prompt do micro-agente."""
        parts = []

        identity = context.get("agent_identity", {})
        if identity.get("name"):
            parts.append(f"Pessoa: {identity['name']}")

        persona_state = identity.get("persona_state") or context.get("persona_state") or {}
        if persona_state:
            mood = persona_state.get("mood", "")
            energy = persona_state.get("energy", 0.7)
            stress = persona_state.get("stress_level", 0)
            emotion = persona_state.get("primary_emotion", "")
            needs = persona_state.get("needs", {})

            state_parts = []
            if mood and mood != "neutro":
                state_parts.append(f"humor: {mood}")
            if energy < 0.4:
                state_parts.append(f"energia baixa ({energy:.0%})")
            elif energy > 0.8:
                state_parts.append(f"energia alta ({energy:.0%})")
            if stress > 0.5:
                state_parts.append(f"stress: {stress:.0%}")
            if emotion and emotion != "neutral":
                intensity = persona_state.get("emotion_intensity", 0)
                state_parts.append(f"emoção: {emotion} ({intensity:.0%})")

            unmet = [k for k, v in needs.items() if isinstance(v, (int, float)) and v < 0.3]
            if unmet:
                state_parts.append(f"necessidades em falta: {', '.join(unmet)}")

            defenses = persona_state.get("active_defenses", [])
            if defenses:
                state_parts.append(f"defesas activas: {', '.join(defenses[:2])}")

            if state_parts:
                parts.append("Estado actual: " + " | ".join(state_parts))

        emotional_ctx = context.get("emotional_context", "")
        if emotional_ctx and isinstance(emotional_ctx, str) and len(emotional_ctx) > 10:
            parts.append(f"Contexto emocional: {emotional_ctx[:300]}")

        memories = context.get("memory", [])
        if memories:
            mem_texts = []
            for m in memories[:3]:
                if isinstance(m, dict) and m.get("content"):
                    mem_texts.append(m["content"][:80])
            if mem_texts:
                parts.append("Memórias relevantes: " + " | ".join(mem_texts))

        reaction = context.get("emotional_reaction", {})
        if isinstance(reaction, dict):
            r_type = reaction.get("emotional_reaction", "")
            intensity = reaction.get("intensity", 0)
            if r_type and intensity > 0.2:
                parts.append(f"Reacção emocional à mensagem: {r_type} (intensidade: {intensity:.0%})")

        return "\n".join(parts)

    def _call_llm(self, system_prompt: str, user_content: str, temperature: float = None) -> Optional[str]:
        if not self.llm_client:
            return None
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ]
            return self.llm_client.chat_completion(
                messages,
                temperature=temperature or self.TEMPERATURE,
                max_tokens=self.MAX_TOKENS,
            )
        except Exception as e:
            logger.error(f"Erro LLM em {self.thinking_type.value}: {e}")
            return None

    @abstractmethod
    def think(self, query: str, context: Dict) -> Dict[str, Any]:
        pass

    def update_focus(self, focus: str):
        self.micro_agent_instance.current_focus = focus
        self.micro_agent_instance.last_activated = datetime.utcnow()
        self.db.commit()

    def update_confidence(self, confidence: float):
        self.micro_agent_instance.confidence_level = max(0.0, min(1.0, confidence))
        self.db.commit()

    def get_weight(self) -> float:
        return self.micro_agent_instance.custom_weight or self.micro_agent_instance.type.default_weight


class LogicalAgent(BaseMicroAgent):
    """Córtex pré-frontal — raciocínio causal e dedução"""

    TEMPERATURE = 0.3

    def __init__(self, agent_id: str, micro_agent_id: str, db: Session):
        super().__init__(agent_id, micro_agent_id, MicroAgentThinkingType.LOGICAL, db)

    def think(self, query: str, context: Dict) -> Dict[str, Any]:
        system_prompt = self._get_system_prompt()
        persona_ctx = self._build_persona_context(context)

        user_content = (
            f"{persona_ctx}\n\n---\n\n"
            f"O que a pessoa me disse: \"{query}\"\n\n"
            "Pensa como esta pessoa pensaria — com a sua lógica, os seus vieses, "
            "o seu nível de educação. 2-4 frases de raciocínio interno na primeira pessoa."
        )

        perspective = self._call_llm(system_prompt, user_content, temperature=0.3)
        if not perspective:
            perspective = f"Preciso de pensar nisto com calma... \"{query[:60]}\""

        return {
            "perspective": perspective,
            "confidence": 0.8,
            "supporting_arguments": [],
            "opposing_arguments": [],
        }


class EmotionalAgent(BaseMicroAgent):
    """Sistema límbico — reacção emocional visceral"""

    TEMPERATURE = 0.75

    def __init__(self, agent_id: str, micro_agent_id: str, db: Session):
        super().__init__(agent_id, micro_agent_id, MicroAgentThinkingType.EMOTIONAL, db)

    def think(self, query: str, context: Dict) -> Dict[str, Any]:
        system_prompt = self._get_system_prompt()
        persona_ctx = self._build_persona_context(context)

        user_content = (
            f"{persona_ctx}\n\n---\n\n"
            f"O que a pessoa me disse: \"{query}\"\n\n"
            "O que sentes? Reacção visceral, sem filtro. "
            "2-4 frases na primeira pessoa — sente, não analises."
        )

        perspective = self._call_llm(system_prompt, user_content, temperature=0.75)
        if not perspective:
            perspective = "Sinto qualquer coisa, mas não consigo nomear..."

        return {
            "perspective": perspective,
            "confidence": 0.75,
            "supporting_arguments": [],
            "opposing_arguments": [],
        }


class CriticalAgent(BaseMicroAgent):
    """Amígdala cognitiva — cepticismo e detecção de ameaças"""

    TEMPERATURE = 0.35

    def __init__(self, agent_id: str, micro_agent_id: str, db: Session):
        super().__init__(agent_id, micro_agent_id, MicroAgentThinkingType.CRITICAL, db)

    def think(self, query: str, context: Dict) -> Dict[str, Any]:
        system_prompt = self._get_system_prompt()
        persona_ctx = self._build_persona_context(context)

        user_content = (
            f"{persona_ctx}\n\n---\n\n"
            f"O que a pessoa me disse: \"{query}\"\n\n"
            "Há algo que não encaixa? Devo desconfiar? "
            "2-4 frases na primeira pessoa. Se está tudo seguro, diz isso."
        )

        perspective = self._call_llm(system_prompt, user_content, temperature=0.35)
        if not perspective:
            perspective = "Não sei bem o que pensar disto..."

        return {
            "perspective": perspective,
            "confidence": 0.7,
            "supporting_arguments": [],
            "opposing_arguments": [],
        }


class CreativeAgent(BaseMicroAgent):
    """Default mode network — associação livre e pensamento divergente"""

    TEMPERATURE = 0.9

    def __init__(self, agent_id: str, micro_agent_id: str, db: Session):
        super().__init__(agent_id, micro_agent_id, MicroAgentThinkingType.CREATIVE, db)

    def think(self, query: str, context: Dict) -> Dict[str, Any]:
        system_prompt = self._get_system_prompt()
        persona_ctx = self._build_persona_context(context)

        user_content = (
            f"{persona_ctx}\n\n---\n\n"
            f"O que a pessoa me disse: \"{query}\"\n\n"
            "Que associações surgem? Metáforas, memórias, ideias inesperadas? "
            "2-3 frases de pensamento associativo na primeira pessoa."
        )

        perspective = self._call_llm(system_prompt, user_content, temperature=0.9)
        if not perspective:
            perspective = "A minha mente está em branco neste momento..."

        return {
            "perspective": perspective,
            "confidence": 0.65,
            "supporting_arguments": [],
            "opposing_arguments": [],
        }


class EthicalAgent(BaseMicroAgent):
    """Superego situado — bússola moral e valores internalizados"""

    TEMPERATURE = 0.4

    def __init__(self, agent_id: str, micro_agent_id: str, db: Session):
        super().__init__(agent_id, micro_agent_id, MicroAgentThinkingType.ETHICAL, db)

    def think(self, query: str, context: Dict) -> Dict[str, Any]:
        system_prompt = self._get_system_prompt()
        persona_ctx = self._build_persona_context(context)

        user_content = (
            f"{persona_ctx}\n\n---\n\n"
            f"O que a pessoa me disse: \"{query}\"\n\n"
            "Isto está alinhado com os meus valores? "
            "2-4 frases na primeira pessoa. Se não há dilema, diz que está tudo bem."
        )

        perspective = self._call_llm(system_prompt, user_content, temperature=0.4)
        if not perspective:
            perspective = "Não vejo problema ético aqui."

        return {
            "perspective": perspective,
            "confidence": 0.85,
            "supporting_arguments": [],
            "opposing_arguments": [],
        }


class SocialAgent(BaseMicroAgent):
    """Córtex social — leitura de dinâmicas e gestão de impressão"""

    TEMPERATURE = 0.55

    def __init__(self, agent_id: str, micro_agent_id: str, db: Session):
        super().__init__(agent_id, micro_agent_id, MicroAgentThinkingType.SOCIAL, db)

    def think(self, query: str, context: Dict) -> Dict[str, Any]:
        system_prompt = self._get_system_prompt()
        persona_ctx = self._build_persona_context(context)

        user_content = (
            f"{persona_ctx}\n\n---\n\n"
            f"O que a pessoa me disse: \"{query}\"\n\n"
            "Qual é a dinâmica aqui? O que devo considerar socialmente? "
            "2-4 frases na primeira pessoa como cálculo social interno."
        )

        perspective = self._call_llm(system_prompt, user_content, temperature=0.55)
        if not perspective:
            perspective = "Situação social simples, sem complicações."

        return {
            "perspective": perspective,
            "confidence": 0.7,
            "supporting_arguments": [],
            "opposing_arguments": [],
        }


class MemoryCuratorAgent(BaseMicroAgent):
    """Curadora de memórias — decide o que guardar e como categorizar"""

    TEMPERATURE = 0.4

    def __init__(self, agent_id: str, micro_agent_id: str, db: Session):
        super().__init__(agent_id, micro_agent_id, MicroAgentThinkingType.MEMORY_CURATOR, db)

    def think(self, query: str, context: Dict) -> Dict[str, Any]:
        system_prompt = self._get_system_prompt()
        persona_ctx = self._build_persona_context(context)

        # === EXTRAIR AMBOS OS LADOS DA CONVERSA ===
        # INPUT: O que o user disse
        user_input = query.strip() if query else ""
        
        # OUTPUT: O que o bot respondeu
        response_data = context.get("response_data", {})
        bot_output = response_data.get("response", "").strip() if response_data.get("response") else ""
        
        # Recuperar memórias existentes para detectar conflitos
        existing_memories = context.get("existing_memories", [])
        memory_summary = ""
        if existing_memories:
            memory_summary = "\n\nMemórias existentes do sistema:\n"
            for i, mem in enumerate(existing_memories[:5], 1):  # Mostrar top 5
                mem_content = mem if isinstance(mem, str) else mem.get("content", str(mem))
                memory_summary += f"  {i}. {mem_content[:100]}...\n"

        # === CONSTRUIR PROMPT COM ANÁLISE BILATERAL ===
        user_content = (
            f"{persona_ctx}\n\n"
            f"{'='*70}\n"
            f"ANÁLISE BILATERAL DA INTERAÇÃO:\n"
            f"{'='*70}\n\n"
            f"📥 INPUT DO UTILIZADOR:\n"
            f"\"{user_input}\"\n\n"
            f"📤 OUTPUT DO BOT:\n"
            f"\"{bot_output}\"\n"
            f"{memory_summary}\n"
            f"{'='*70}\n\n"
            f"Como curadora de memórias, avalia AMBOS os lados:\n"
            f"1. O que o utilizador disse revela sobre si?\n"
            f"2. Como o bot respondeu? Adequada?\n"
            f"3. Há informação significativa neste par (input/output)?\n"
            f"4. Importância geral (0.0-1.0)?\n"
            f"5. Tipo de memória (episódica/semântica/processual)?\n"
            f"6. Detecta conflitos com memórias existentes?\n\n"
            f"Responde como curadora interna (2-4 frases sobre o que guardar)."
        )

        perspective = self._call_llm(system_prompt, user_content, temperature=0.4)
        if not perspective:
            perspective = "Nada de especial a guardar desta interação."

        return {
            "perspective": perspective,
            "confidence": 0.85,  # Memory Curator é confiante nas suas decisões
            "supporting_arguments": ["bilateral_analysis_complete", f"user_input_length:{len(user_input)}", f"bot_output_length:{len(bot_output)}"],
            "opposing_arguments": [],
        }



# Registro de tipos de micro-agentes
MICRO_AGENT_REGISTRY = {
    MicroAgentThinkingType.LOGICAL: LogicalAgent,
    MicroAgentThinkingType.EMOTIONAL: EmotionalAgent,
    MicroAgentThinkingType.CRITICAL: CriticalAgent,
    MicroAgentThinkingType.CREATIVE: CreativeAgent,
    MicroAgentThinkingType.ETHICAL: EthicalAgent,
    MicroAgentThinkingType.SOCIAL: SocialAgent,
    MicroAgentThinkingType.MEMORY_CURATOR: MemoryCuratorAgent,
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
