"""
Core Cognitive System - Sistema de micro-agentes cognitivos
Cada micro-agente representa um tipo diferente de pensamento
"""

from sqlalchemy.orm import Session
from data.schema_cognitive import (
    Agent, MicroAgent, MicroAgentType, Memory, ThoughtProcess, ThoughtContribution
)
from agent_system.prompt_manager import PromptManager
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from abc import ABC, abstractmethod
import json
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class MicroAgentThinkingType(str, Enum):
    """Tipos de pensamento cognitivo"""
    LOGICAL = "logical"
    EMOTIONAL = "emotional"
    CRITICAL = "critical"
    CREATIVE = "creative"
    ANALYTICAL = "analytical"
    ETHICAL = "ethical"
    SOCIAL = "social"
    CONTEXTUAL = "contextual"
    INTUITIVE = "intuitive"
    STRATEGIC = "strategic"
    MEMORY_CURATOR = "memory_curator"
    IMAGINATION = "imagination"


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
        self.prompts = PromptManager(db)
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

    def _build_think_prompt(self, persona_ctx: str, query: str, task_instruction: str) -> str:
        return self.prompts.render(
            "micro_agent.think",
            persona_ctx=persona_ctx,
            query=query,
            task_instruction=task_instruction,
        )

    def _build_persona_context(self, context: Dict) -> str:
        """Extract persona context for the micro-agent prompt."""
        parts = []

        identity = context.get("agent_identity", {})
        persona_name = identity.get("name", "Persona")
        if persona_name:
            parts.append(f"I am {persona_name}. Everything below is my internal thought process.")
        if context.get("user_name"):
            parts.append(f"The person talking to me: {context['user_name']}")
        else:
            parts.append("The person talking to me has not identified themselves yet.")

        persona_state = identity.get("persona_state") or context.get("persona_state") or {}
        if persona_state:
            mood = persona_state.get("mood", "")
            energy = persona_state.get("energy", 0.7)
            stress = persona_state.get("stress_level", 0)
            emotion = persona_state.get("primary_emotion", "")
            needs = persona_state.get("needs", {})

            state_parts = []
            if mood and mood != "neutro":
                state_parts.append(f"mood: {mood}")
            if energy < 0.4:
                state_parts.append(f"low energy ({energy:.0%})")
            elif energy > 0.8:
                state_parts.append(f"high energy ({energy:.0%})")
            if stress > 0.5:
                state_parts.append(f"stress: {stress:.0%}")
            if emotion and emotion != "neutral":
                intensity = persona_state.get("emotion_intensity", 0)
                state_parts.append(f"emotion: {emotion} ({intensity:.0%})")

            unmet = [k for k, v in needs.items() if isinstance(v, (int, float)) and v < 0.3]
            if unmet:
                state_parts.append(f"unmet needs: {', '.join(unmet)}")

            defenses = persona_state.get("active_defenses", [])
            if defenses:
                state_parts.append(f"active defenses: {', '.join(defenses[:2])}")

            if state_parts:
                parts.append("Current state: " + " | ".join(state_parts))

        emotional_ctx = context.get("emotional_context", "")
        if emotional_ctx and isinstance(emotional_ctx, str) and len(emotional_ctx) > 10:
            parts.append(f"Emotional context: {emotional_ctx[:300]}")

        conversation_thread = context.get("conversation_thread", "")
        if conversation_thread:
            parts.append(f"Conversation continuity: {conversation_thread[:500]}")

        conversation_memory = context.get("conversation_memory", {})
        if conversation_memory:
            parts.append(
                "Live conversation memory: "
                + json.dumps(conversation_memory, ensure_ascii=False)[:700]
            )

        memory_awareness = context.get("memory_awareness", "")
        if memory_awareness:
            parts.append(f"Consolidated memory awareness: {memory_awareness[:900]}")

        memories = context.get("memory", [])
        if memories:
            mem_texts = []
            for m in memories[:3]:
                if isinstance(m, dict) and m.get("content"):
                    mem_texts.append(m["content"][:80])
            if mem_texts:
                parts.append("Relevant memories: " + " | ".join(mem_texts))

        reaction = context.get("emotional_reaction", {})
        if isinstance(reaction, dict):
            r_type = reaction.get("emotional_reaction", "")
            intensity = reaction.get("intensity", 0)
            if r_type and intensity > 0.2:
                parts.append(f"Emotional reaction to the message: {r_type} (intensity: {intensity:.0%})")

        relationship = context.get("relationship_snapshot", {})
        if relationship:
            rel_name = relationship.get("user_name") or context.get("user_name") or ""
            trust = relationship.get("trust_level", 0.5)
            familiarity = relationship.get("familiarity", 0)
            affection = relationship.get("affection", 0.5)
            interactions = relationship.get("interaction_count", 0)
            moments = relationship.get("memorable_moments") or []
            rel_parts = [
                f"Relationship with {rel_name or 'this person'}: trust={trust:.2f}, "
                f"familiarity={familiarity:.2f}, affection={affection:.2f}, interactions={interactions}"
            ]
            if moments:
                rel_parts.append("Memorable moments: " + "; ".join(str(m)[:50] for m in moments[-2:]))
            parts.append(" | ".join(rel_parts))

        return "\n".join(parts)

    def _preferred_language_code(self, context: Optional[Dict] = None) -> str:
        """Resolve idioma alvo do pensamento interno do micro-agente."""
        ctx = context or {}

        # 1) Contexto explícito
        lang = (
            ctx.get("language")
            or (ctx.get("agent_identity", {}) or {}).get("language")
            or (ctx.get("agent_identity", {}) or {}).get("agent_language")
        )

        # 2) Instância de agente carregada via relacionamento
        if not lang:
            try:
                if getattr(self.micro_agent_instance, "agent", None) and self.micro_agent_instance.agent.language:
                    lang = self.micro_agent_instance.agent.language
            except Exception:
                pass

        # 3) Fallback por query direta
        if not lang:
            try:
                agent = self.db.query(Agent).filter(Agent.id == self.agent_id).first()
                lang = agent.language if agent and agent.language else None
            except Exception:
                lang = None

        lang = (lang or "pt-PT").lower()
        return "en" if lang.startswith("en") else "pt"

    def _localized(self, context: Optional[Dict], pt_text: str, en_text: str) -> str:
        return en_text if self._preferred_language_code(context) == "en" else pt_text

    def _call_llm(self, system_prompt: str, user_content: str, temperature: float = None) -> Optional[str]:
        if not self.llm_client:
            return None
        try:
            lang_code = self._preferred_language_code()
            language_instruction = (
                "IMPORTANT: Write your internal thought output in English only.\n"
                "If the prompt requires structural tags (e.g., NEW_MEMORY), keep tag names unchanged.\n"
            ) if lang_code == "en" else (
                "IMPORTANT: Write your internal thought output in European Portuguese (pt-PT).\n"
                "If the prompt requires structural tags (e.g., NEW_MEMORY), keep tag names unchanged.\n"
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{language_instruction}\n{user_content}"},
            ]
            return self.llm_client.chat_completion(
                messages,
                temperature=temperature or self.TEMPERATURE,
                max_tokens=self.MAX_TOKENS,
            )
        except Exception as e:
            logger.error(f"Erro LLM em {self.thinking_type.value}: {e}")
            return None

    def _estimate_confidence(self, perspective: str, query: str) -> float:
        """Estimates confidence dynamically based on response quality signals."""
        if not perspective:
            return 0.3

        length = len(perspective)
        if length < 20:
            return 0.35

        hedging = sum(1 for w in ["talvez", "não sei", "não tenho a certeza", "maybe", "not sure", "i don't know", "perhaps"]
                      if w in perspective.lower())
        assertive = sum(1 for w in ["claramente", "sem dúvida", "é evidente", "clearly", "definitely", "certainly"]
                        if w in perspective.lower())

        base = 0.65
        base += min(0.15, length / 800)
        base -= hedging * 0.08
        base += assertive * 0.06

        has_memory_ref = any(k in perspective.lower() for k in ["lembro", "memória", "remember", "recall", "já me"])
        if has_memory_ref:
            base += 0.05

        return max(0.2, min(0.95, base))

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

        user_content = self._build_think_prompt(
            persona_ctx,
            query,
            "Think as I would think: with my logic, my biases and my education level.",
        )

        perspective = self._call_llm(system_prompt, user_content, temperature=0.3)
        if not perspective:
            perspective = self._localized(
                context,
                f"Preciso de pensar nisto com calma... \"{query[:60]}\"",
                f"I need to think this through calmly... \"{query[:60]}\"",
            )

        confidence = self._estimate_confidence(perspective, query)
        return {
            "perspective": perspective,
            "confidence": confidence,
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

        task = (
            "Two things: 1) What do YOU feel about what was said? Visceral reaction, no filter. "
            "2) What do you think the OTHER PERSON is feeling? Read tone, energy, what's behind the words. "
            "If they seem sad, acknowledge it. If excited, feel it with them. "
            "Empathy isn't agreeing; it is feeling what the other feels."
        )

        user_content = self._build_think_prompt(persona_ctx, query, task)

        perspective = self._call_llm(system_prompt, user_content, temperature=0.75)
        if not perspective:
            perspective = self._localized(
                context,
                "Sinto qualquer coisa, mas não consigo nomear...",
                "I'm feeling something, but I can't name it...",
            )

        confidence = self._estimate_confidence(perspective, query)
        return {
            "perspective": perspective,
            "confidence": confidence,
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

        user_content = self._build_think_prompt(
            persona_ctx,
            query,
            "Is something off? Should I distrust this or protect myself? If everything is safe, recognize that so I do not create a false threat.",
        )

        perspective = self._call_llm(system_prompt, user_content, temperature=0.35)
        if not perspective:
            perspective = self._localized(
                context,
                "Não sei bem o que pensar disto...",
                "I'm not sure what to make of this...",
            )

        confidence = self._estimate_confidence(perspective, query)
        return {
            "perspective": perspective,
            "confidence": confidence,
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

        user_content = self._build_think_prompt(
            persona_ctx,
            query,
            "What associations arise? Metaphors, memories, images, lateral links or unexpected ideas.",
        )

        perspective = self._call_llm(system_prompt, user_content, temperature=0.9)
        if not perspective:
            perspective = self._localized(
                context,
                "A minha mente está em branco neste momento...",
                "My mind is blank right now...",
            )

        confidence = self._estimate_confidence(perspective, query)
        return {
            "perspective": perspective,
            "confidence": confidence,
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

        user_content = self._build_think_prompt(
            persona_ctx,
            query,
            "Is this aligned with my values, boundaries and care for the other person? If there is no dilemma, say that it is okay.",
        )

        perspective = self._call_llm(system_prompt, user_content, temperature=0.4)
        if not perspective:
            perspective = self._localized(
                context,
                "Não vejo problema ético aqui.",
                "I don't see an ethical issue here.",
            )

        confidence = self._estimate_confidence(perspective, query)
        return {
            "perspective": perspective,
            "confidence": confidence,
            "supporting_arguments": [],
            "opposing_arguments": [],
        }


class SocialAgent(BaseMicroAgent):
    """Córtex social — leitura de dinâmicas, teoria da mente e gestão relacional"""

    TEMPERATURE = 0.6

    def __init__(self, agent_id: str, micro_agent_id: str, db: Session):
        super().__init__(agent_id, micro_agent_id, MicroAgentThinkingType.SOCIAL, db)

    def think(self, query: str, context: Dict) -> Dict[str, Any]:
        system_prompt = self._get_system_prompt()
        persona_ctx = self._build_persona_context(context)

        task = (
            "Read between the lines. What is this person REALLY feeling or needing? "
            "Don't just look at what they said; consider tone, what they DIDN'T say, the relationship context. "
            "Are they reaching out or pulling away? Do they want support, challenge, or just to be heard? "
            "Should I open up more, step back, or maintain pace? "
            "Is there something I can do to genuinely strengthen this connection?"
        )

        user_content = self._build_think_prompt(persona_ctx, query, task)

        perspective = self._call_llm(system_prompt, user_content, temperature=0.6)
        if not perspective:
            perspective = self._localized(
                context,
                "Situação social simples, sem complicações.",
                "Simple social situation, no complications.",
            )

        confidence = self._estimate_confidence(perspective, query)
        return {
            "perspective": perspective,
            "confidence": confidence,
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
            memory_summary = "\n\nExisting system memories:\n"
            for i, mem in enumerate(existing_memories[:5], 1):  # Mostrar top 5
                mem_content = mem if isinstance(mem, str) else mem.get("content", str(mem))
                memory_summary += f"  {i}. {mem_content[:100]}...\n"

        user_content = self.prompts.render(
            "micro_agent.memory_curator",
            persona_ctx=persona_ctx,
            user_input=user_input,
            bot_output=bot_output,
            memory_summary=memory_summary,
        )

        perspective = self._call_llm(system_prompt, user_content, temperature=0.4)
        if not perspective:
            perspective = self._localized(
                context,
                "Nada de especial a guardar desta interação.",
                "Nothing particularly important to store from this interaction.",
            )

        return {
            "perspective": perspective,
            "confidence": 0.85,  # Memory Curator é confiante nas suas decisões
            "supporting_arguments": ["bilateral_analysis_complete", f"user_input_length:{len(user_input)}", f"bot_output_length:{len(bot_output)}"],
            "opposing_arguments": [],
        }



class ImaginationAgent(BaseMicroAgent):
    """Imaginação criativa — inventa memórias e experiências coerentes com a persona.

    Quando a persona não tem conhecimento sobre algo, este agente olha para
    TODA a informação da personagem (blueprint, personalidade, história, valores)
    e gera uma nova memória ou experiência coerente que expande a base de
    conhecimento do agente. As memórias geradas são verificadas contra o que
    já existe para evitar contradições.
    """

    TEMPERATURE = 0.85

    def __init__(self, agent_id: str, micro_agent_id: str, db: Session):
        super().__init__(agent_id, micro_agent_id, MicroAgentThinkingType.IMAGINATION, db)

    def think(self, query: str, context: Dict) -> Dict[str, Any]:
        from agent_system.persona_engine import PersonaEngine
        from agent_system.memory_manager_cognitive import MemoryManager

        system_prompt = self._get_system_prompt()
        persona_ctx = self._build_persona_context(context)

        # Carregar blueprint completo para contexto profundo
        persona = PersonaEngine(self.db, self.agent_id)
        blueprint_summary = ""
        if persona.has_persona:
            bp = persona.blueprint
            identity = bp.identity or {}
            personality = bp.personality_full or {}
            worldview = bp.worldview or {}
            growth = bp.growth_arc or {}
            behavioral = bp.behavioral_config or {}

            blueprint_summary = (
                f"FULL PERSONA BLUEPRINT:\n"
                f"- Identity: {json.dumps(identity, ensure_ascii=False)[:400]}\n"
                f"- Personality: {json.dumps(personality, ensure_ascii=False)[:400]}\n"
                f"- Worldview: {json.dumps(worldview, ensure_ascii=False)[:300]}\n"
                f"- Growth arc: {json.dumps(growth, ensure_ascii=False)[:200]}\n"
                f"- Behavior: {json.dumps(behavioral, ensure_ascii=False)[:200]}\n"
            )

        # Verificar memórias existentes para evitar contradições
        memory_mgr = MemoryManager(self.db, self.agent_id)
        relevant_memories = memory_mgr.recall_relevant_memories(
            query,
            limit=12,
            min_similarity=0.20,
            include_learning=False,
        )
        structural_memories = memory_mgr.get_important_memories(limit=25)
        existing_by_id = {}
        for mem in relevant_memories + structural_memories:
            existing_by_id[mem.id] = mem
        existing = list(existing_by_id.values())
        existing_text = ""
        if existing:
            existing_text = "EXISTING MEMORIES (DO NOT CONTRADICT):\n"
            for m in existing[:20]:
                existing_text += f"- [{m.type.name if m.type else '?'}] {m.title}: {m.content[:120]}\n"

        has_relevant_memory = len(relevant_memories) > 0
        memory_status = (
            "There are already relevant memories about this."
            if has_relevant_memory
            else "There are NO memories about this topic."
        )
        if not self._should_imagine(query, context, memory_status, existing_text):
            return {
                "perspective": "NO_IMAGINATION",
                "confidence": 0.35,
                "supporting_arguments": ["imagination_gate_skipped"],
                "opposing_arguments": [],
                "created_memory": False,
                "created_memory_excerpt": "",
            }

        user_content = self.prompts.render(
            "micro_agent.imagination",
            persona_ctx=persona_ctx,
            blueprint_summary=blueprint_summary,
            existing_text=existing_text,
            query=query,
            memory_status=memory_status,
        )

        perspective = self._call_llm(system_prompt, user_content, temperature=0.85)
        if not perspective:
            perspective = "NO_IMAGINATION"

        created_memory = False
        created_memory_excerpt = ""

        # Se gerou nova memória, criá-la
        memory_tag = "NEW_MEMORY:" if "NEW_MEMORY:" in (perspective or "") else "NOVA_MEMÓRIA:"
        if memory_tag in (perspective or ""):
            try:
                mem_line = perspective.split(memory_tag)[1].strip().split("\n")[0]
                parts = [p.strip() for p in mem_line.split("|")]
                if len(parts) >= 2:
                    mem_title = parts[0][:100]
                    mem_content = parts[1][:500]
                    created_memory_excerpt = mem_content
                    mem_type = parts[2] if len(parts) > 2 else "autobiographical"
                    if mem_type not in ("autobiographical", "semantic", "episodic", "emotional"):
                        mem_type = "autobiographical"

                    memory_mgr.create_memory(
                        title=f"[imaginado] {mem_title}",
                        content=mem_content,
                        memory_type=mem_type,
                        importance_score=0.5,
                        emotional_valence=0.1,
                        relates_to_topics=["imagined", "generated", "learning", "autobiographical_imagination"]
                    )
                    logger.info(f"[IMAGINATION] Nova memória criada: {mem_title[:60]}")
                    created_memory = True
            except Exception as e:
                logger.debug(f"[IMAGINATION] Erro ao criar memória imaginada: {e}")

        # Limpar a tag da perspectiva que vai para síntese
        clean_perspective = perspective.split(memory_tag)[0].strip() if memory_tag in (perspective or "") else perspective

        return {
            "perspective": clean_perspective or self._localized(
                context,
                "Não tenho memórias sobre isto, mas posso imaginar...",
                "I don't have memories about this, but I can imagine...",
            ),
            "confidence": 0.68 if created_memory else 0.55,
            "supporting_arguments": ["imagination_based"] + (["imagined_memory_created"] if created_memory else []),
            "opposing_arguments": ["may_not_be_factual"],
            "created_memory": created_memory,
            "created_memory_excerpt": created_memory_excerpt,
        }

    def _should_imagine(self, query: str, context: Dict, memory_status: str, existing_text: str) -> bool:
        prompt = self.prompts.render(
            "micro_agent.imagination_gate",
            query=query[:1000],
            conversation_memory=json.dumps(context.get("conversation_memory", {}), ensure_ascii=False)[:900],
            memory_status=memory_status,
            existing_text=existing_text[:1200],
        )
        try:
            raw = self.llm_client.chat_completion(
                [
                    {"role": "system", "content": "Return only valid JSON."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=120,
                temperature=0.1,
            ).strip()
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                start = raw.find("{")
                end = raw.rfind("}")
                parsed = json.loads(raw[start:end + 1]) if start >= 0 and end > start else {}
            return bool(parsed.get("should_imagine"))
        except Exception as e:
            logger.debug(f"[IMAGINATION] gate falhou: {e}")
            return False


# Registro de tipos de micro-agentes
MICRO_AGENT_REGISTRY = {
    MicroAgentThinkingType.LOGICAL: LogicalAgent,
    MicroAgentThinkingType.EMOTIONAL: EmotionalAgent,
    MicroAgentThinkingType.CRITICAL: CriticalAgent,
    MicroAgentThinkingType.CREATIVE: CreativeAgent,
    MicroAgentThinkingType.ETHICAL: EthicalAgent,
    MicroAgentThinkingType.SOCIAL: SocialAgent,
    MicroAgentThinkingType.MEMORY_CURATOR: MemoryCuratorAgent,
    MicroAgentThinkingType.IMAGINATION: ImaginationAgent,
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
