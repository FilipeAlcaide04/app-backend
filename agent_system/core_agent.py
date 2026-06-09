"""
CoreAgent v2 - Agente central com pensamento autónomo

Responsável por:
1. Sintetizar respostas dos micro-agentes
2. Aplicar TODA a persona ao output (voice, behavior, emotions)
3. Pensamento autónomo (inner monologue que influencia resposta)
4. Auto-geração de memórias a partir de conversas
5. Estado emocional influencia directamente a resposta
6. Growth tracking - detecta momentos de crescimento
"""

from sqlalchemy.orm import Session
from data.schema_cognitive import Agent, Memory, ThoughtProcess
from data.schema_persona import PersonaBlueprint, DynamicState, InnerMonologue
from llm_logic.llm_client import get_llm_client
from agent_system.memory_manager_cognitive import MemoryManager
from agent_system.identity_builder import IdentityBuilder
from agent_system.persona_engine import PersonaEngine
from agent_system.prompt_manager import PromptManager
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import json
import re
import logging

logger = logging.getLogger(__name__)


class CoreAgent:
    """
    Agente central que transforma pensamento cognitivo em resposta HUMANA.
    Usa toda a persona para garantir que a resposta é genuinamente "desta pessoa".
    """

    def __init__(self, db: Session, agent_id: str):
        self.db = db
        self.agent_id = agent_id
        self.agent = self._load_agent()
        self.llm_client = get_llm_client()
        self.memory_manager = MemoryManager(db, agent_id)
        self.identity = IdentityBuilder(db, agent_id)
        self.persona = PersonaEngine(db, agent_id)
        self.prompts = PromptManager(db)

    def _load_agent(self) -> Agent:
        agent = self.db.query(Agent).filter(Agent.id == self.agent_id).first()
        if not agent:
            raise ValueError(f"Agente {self.agent_id} não encontrado")
        return agent

    def synthesize_response(
        self,
        micro_agent_responses: Dict[str, Dict],
        query: str,
        context: Optional[Dict] = None,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sintetiza respostas em UMA resposta humanizada.
        Agora com pensamento autónomo e persona completa.
        """

        context = context or {}

        logger.info(f"[FASE 6] SÍNTESE: Combinando perspectivas de {len(micro_agent_responses)} micro-agentes")
        for agent_name, response_data in micro_agent_responses.items():
            full_perspective = response_data.get("perspective", "N/A")
            logger.info(
                f"[MICRO-AGENT OUTPUT] {agent_name} | confiança={response_data.get('confidence', 0):.2f}\n"
                f"{full_perspective}"
            )
            if response_data.get('supporting_arguments'):
                logger.debug(f"    Argumentos a favor: {response_data.get('supporting_arguments', [])[:2]}")
            if response_data.get('opposing_arguments'):
                logger.debug(f"    Argumentos contra: {response_data.get('opposing_arguments', [])[:2]}")

        # 1. Analisar perspectivas
        consensus = self._analyze_consensus(micro_agent_responses)
        weighted = self._weight_perspectives(micro_agent_responses, query, consensus)
        resolved = self._resolve_conflicts(weighted, consensus)

        logger.info(f"[SÍNTESE] Consenso: {consensus.get('consensus_score', 0):.2f}, Conflitos resolvidos")

        # 2. Gerar pensamento interno autónomo
        inner_thought = self._generate_inner_thought(query, context, resolved)
        if inner_thought:
            logger.info(f"[SÍNTESE] Pensamento interno completo:\n{inner_thought}")

        # 3. Gerar resposta final com toda a persona
        final_text = self._generate_persona_response(
            resolved.get("main_response", ""),
            query, context, user_id,
            inner_thought=inner_thought,
            resolved_context=resolved,
        )
        logger.info(f"[SÍNTESE] ✓ Resposta final gerada ({len(final_text)} chars)")
        logger.info(f"[FINAL OUTPUT]\n{final_text}")

        # 4. Calcular confiança
        confidence = self._calculate_final_confidence(weighted)
        logger.info(f"[SÍNTESE] Confiança final: {confidence:.2f}")

        # 6. Actualizar estado da persona
        if self.persona.has_persona:
            emotional_changes = context.get("emotional_reaction", {}).get("changes", {})
            self.persona.update_state_after_interaction(
                user_message=query,
                agent_response=final_text,
                emotional_changes=emotional_changes,
                user_id=user_id
            )
            logger.debug(f"[SÍNTESE] Estado da persona actualizado")

        # 7. Actualizar relação
        relationship_snapshot = {}
        if user_id:
            self._update_relationship(user_id, context)
            relationship_snapshot = self.identity.get_relationship_snapshot(user_id)

        return {
            "response": final_text,
            "confidence": confidence,
            "reasoning": resolved.get("reasoning", ""),
            "perspectives_count": len(micro_agent_responses),
            "consensus_level": consensus.get("consensus_score", 0.5),
            "inner_thought": inner_thought,
            "relationship": relationship_snapshot,
            "timestamp": datetime.utcnow().isoformat(),
            "agent_id": self.agent_id,
            "user_id": user_id,
            "conversation_id": conversation_id
        }

    # ================================================================
    # PENSAMENTO AUTÓNOMO
    # ================================================================

    def _generate_inner_thought(
        self,
        query: str,
        context: Dict,
        resolved: Dict
    ) -> str:
        """
        Gera pensamento interno autónomo via LLM.
        O agente pensa por si antes de responder, usando a sua persona completa.
        """

        if not self.persona.has_persona:
            return ""

        blueprint = self.persona.blueprint
        state = self.persona.state
        identity = blueprint.identity if blueprint else {}
        inner_voice = identity.get("inner_voice", {})

        reaction = context.get("emotional_reaction", {})
        reaction_thought = reaction.get("inner_thought", "")

        if reaction_thought:
            try:
                self.persona.record_inner_thought(
                    thought=reaction_thought,
                    trigger=query[:100],
                    trigger_type="emotional_shift",
                    shared_with_user=False
                )
            except Exception:
                pass
            return reaction_thought

        iv_tone = inner_voice.get("tone", "neutral")
        iv_example = inner_voice.get("example_inner_monologue", "")

        unmet_needs = self.persona.get_unmet_needs()
        needs_text = ""
        if unmet_needs:
            needs_text = "Unmet needs: " + ", ".join(
                f"{n['need']} ({n.get('level', 0):.0%})" for n in unmet_needs[:3]
            )

        in_crisis = self.persona.is_in_crisis()

        state_summary = self.persona.get_state_summary() if state else {}
        mood = state_summary.get("mood", "neutro")
        energy = state_summary.get("energy", 0.7)
        stress = state_summary.get("stress_level", 0.2)

        relationship = self.identity.get_relationship_snapshot(context.get("user_id"))
        rel_text = ""
        if relationship:
            rel_name = relationship.get("user_name") or context.get("user_name") or "this person"
            rel_text = (
                f"Relationship with {rel_name}: trust={relationship.get('trust_level', 0.5):.2f}, "
                f"familiarity={relationship.get('familiarity', 0):.2f}, "
                f"interactions={relationship.get('interaction_count', 0)}"
            )

        user_name = context.get("user_name") or "someone"
        target_language = getattr(self.agent, "language", "pt-PT") or "pt-PT"
        prompt = (
            f"You are {self.agent.name}. This is your INTERNAL THOUGHT; nobody will see it.\n"
            f"You speak and think in the first person as {self.agent.name}.\n"
            f"Target internal thought language: {target_language}\n"
            f"Inner voice: {iv_tone}. {'Example: ' + repr(iv_example) if iv_example else ''}\n"
            f"Current state: mood={mood}, energy={energy:.1f}, stress={stress:.2f}"
            f"{', IN CRISIS' if in_crisis else ''}\n"
            f"{needs_text}\n"
            f"{rel_text}\n\n"
            f"The person I am talking to ({user_name}) just said TO ME: \"{query[:200]}\"\n\n"
            f"What do I really think before answering? Think like my inner voice, "
            f"with my tone, fears, needs and feelings about this person. "
            f"Be honest with myself. 1-2 short first-person sentences in the target language."
        )

        try:
            thought = self.llm_client.generate(
                prompt, max_tokens=120, temperature=0.8,
                system_prompt=f"You are {self.agent.name}. Think in the first person. This is your private inner thought.",
            )
            thought = (thought or "").strip()
            if thought:
                try:
                    trigger_type = "crisis" if in_crisis else ("need_unmet" if unmet_needs else "interaction")
                    self.persona.record_inner_thought(
                        thought=thought,
                        trigger=query[:100],
                        trigger_type=trigger_type,
                        shared_with_user=False
                    )
                except Exception:
                    pass
            return thought
        except Exception as e:
            logger.debug(f"Erro ao gerar pensamento interno: {e}")
            return ""

    # ================================================================
    # GERAÇÃO DE RESPOSTA COM PERSONA
    # ================================================================

    def _generate_persona_response(
        self,
        base_response: str,
        query: str,
        context: Dict,
        user_id: Optional[str],
        inner_thought: str = "",
        resolved_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Gera resposta usando LLM com TODA a persona.
        O prompt inclui identidade, estado emocional, voice, regras, tudo.
        """

        # 1. Limpar marcadores de agentes
        cleaned = self._remove_agent_markers(base_response)
        resolved_context = resolved_context or {}

        # 2. Obter prompt de identidade completo
        identity_prompt = self.identity.get_identity_prompt(user_id)
        voice = self.identity.get_voice_guidelines()

        # 3. Contexto emocional
        emotional_context = context.get("emotional_context", "")
        reaction = context.get("emotional_reaction", {})
        reaction_type = reaction.get("emotional_reaction", "neutral") if isinstance(reaction, dict) else "neutral"

        # 4. Contexto de conversa anterior
        conv_context = context.get("conversation_history", [])
        previous_sessions = context.get("previous_sessions", [])
        conversation_thread = context.get("conversation_thread", "")
        conversation_memory = context.get("conversation_memory", {})
        memory_awareness = context.get("memory_awareness", "")
        target_language = getattr(self.agent, "language", "pt-PT") or "pt-PT"
        english_output = str(target_language).lower().startswith("en")
        persona_name = voice.get("name", self.agent.name) or "Persona"
        user_label = "Utilizador"
        assistant_label = persona_name

        # 5. Estado actual modificadores
        state_modifiers = self._get_state_modifiers(reaction_type)

        # 5.1. Estado da relação com quem está a falar comigo
        relationship = self.identity.get_relationship_snapshot(user_id)
        relationship_text = ""
        relationship_guidance = ""
        if relationship:
            rel_name = relationship.get("user_name") or context.get("user_name") or "this person"
            familiarity = relationship.get("familiarity", 0.0)
            trust = relationship.get("trust_level", 0.5)
            affection = relationship.get("affection", 0.5)
            interactions = relationship.get("interaction_count", 0)
            top_topics = ", ".join((relationship.get("conversation_topics") or [])[:3]) or "no clear pattern yet"
            moments = relationship.get("memorable_moments") or []
            moments_text = (
                " Memorable moments: " + "; ".join(str(m)[:60] for m in moments[-3:])
                if moments else ""
            )
            relationship_text = (
                f"Relationship with {rel_name}: familiarity={familiarity:.2f}, trust={trust:.2f}, affection={affection:.2f}, "
                f"interactions={interactions}. Usual topics: {top_topics}.{moments_text}"
            )
            relationship_guidance = (
                f"Adapt tone and openness based on the relationship signals and personality. "
                f"Do not follow fixed rules; feel the relationship as the persona would feel it."
            )

        # 6. Historial de conversa formatado
        history_text = ""
        recent_greeting_detected = False
        last_greeting_at: Optional[datetime] = None
        now = datetime.utcnow()
        if conv_context and isinstance(conv_context, list):
            recent = conv_context[-12:] if len(conv_context) > 12 else conv_context
            history_parts = []
            assistant_openings = []
            for msg in recent:
                if isinstance(msg, dict):
                    role = msg.get("role", "")
                    content = msg.get("content", "")[:200]
                    ts = msg.get("timestamp")
                    time_prefix = f"[{ts}] " if ts else ""
                    if role == "user":
                        history_parts.append(f"{time_prefix}{user_label}: {content}")
                    elif role == "assistant":
                        history_parts.append(f"{time_prefix}{assistant_label}: {content}")
                        opening = self._extract_opening_phrase(content)
                        if opening:
                            assistant_openings.append(opening)
                        if re.search(r"\b(olá|ola|oi|hello|hi|hey)\b", content.lower()):
                            if ts:
                                try:
                                    last_greeting_at = datetime.fromisoformat(ts.replace("Z", "+00:00")).replace(tzinfo=None)
                                except ValueError:
                                    last_greeting_at = now
                            else:
                                last_greeting_at = now
            if history_parts:
                history_text = (
                    f"Conversation so far (lines starting with \"{assistant_label}:\" are YOUR previous replies; "
                    f"lines starting with \"{user_label}:\" are what the other person said):\n"
                    + "\n".join(history_parts)
                )

        repeated_openings_text = ""
        if 'assistant_openings' in locals() and assistant_openings:
            unique_openings = []
            for opening in assistant_openings:
                if opening not in unique_openings:
                    unique_openings.append(opening)
            repeated_openings_text = (
                "Recent openings from you that must NOT be repeated literally or used as a crutch: "
                + " | ".join(unique_openings[-5:])
            )

        if last_greeting_at:
            minutes_since_greeting = (now - last_greeting_at).total_seconds() / 60
            recent_greeting_detected = minutes_since_greeting < 30

        # 7. Contexto de sessões anteriores
        prev_text = ""
        if previous_sessions:
            for ps in previous_sessions[:2]:
                if isinstance(ps, dict) and ps.get("summary"):
                    prev_text += f"\nPrevious conversation ({ps.get('date', '?')}): {ps['summary'][:150]}"

        imagined_memory = resolved_context.get("imagined_memory") or ""
        imagined_memory_text = (
            "Newly formed internal memory/experience relevant to THIS response:\n"
            f"{imagined_memory[:900]}"
            if imagined_memory else ""
        )
        conversation_thread_text = f"Full recent thread:\n{conversation_thread}" if conversation_thread else ""
        conversation_memory_text = self._format_conversation_memory(conversation_memory)

        # 7.5. Conhecimento sobre o utilizador + curiosidade
        user_knowledge_text = self._build_user_knowledge_context(user_id, context)

        # 8. Build structured messages for chat completion
        # System = identity (who I am)
        # History = alternating user/assistant messages
        # User = current turn (query + cognitive material + instructions)

        system_identity = (
            f"You are {persona_name}. You always speak in the first person as {persona_name}. "
            f"You are a real person in conversation, NOT an AI assistant. "
            f"Never speak about yourself in third person. "
            f"When the other person asks you a question, YOU answer it from your own experience and personality. "
            f"Never echo or repeat back what the other person said to you.\n\n"
            f"CRITICAL RULES:\n"
            f"1. PERSPECTIVE: Your life, memories, trauma, pets, job, family, feelings = \"I/my/me\". "
            f"The other person's life = \"you/your\". NEVER mix these up.\n"
            f"2. BREVITY: Match your reply length to the message you received. "
            f"Short greeting or simple question = short reply (1-3 sentences). "
            f"Deep topic or complex question = longer reply. "
            f"A real person does not write essays when someone says \"how are you?\".\n"
            f"3. NO MONOLOGUES: Do not dump your entire backstory unprompted. "
            f"Share details only when naturally relevant to what was asked.\n\n"
            f"{identity_prompt}\n\n"
            f"{emotional_context}\n"
            f"{state_modifiers}\n"
            f"{relationship_text}\n"
            f"{relationship_guidance}"
        )

        greeting_instruction = (
            "You already greeted this person less than 30 minutes ago. Do not greet again."
            if recent_greeting_detected
            else ""
        )
        direct_user_line = (
            f'You are speaking directly with: {context.get("user_name")}'
            if context.get("user_name")
            else ""
        )

        # Build chat messages from conversation history
        chat_messages = [{"role": "system", "content": system_identity}]

        if conv_context and isinstance(conv_context, list):
            for msg in conv_context[-10:]:
                if isinstance(msg, dict):
                    role = msg.get("role", "")
                    content = (msg.get("content") or "").strip()
                    if not content:
                        continue
                    if role == "user":
                        chat_messages.append({"role": "user", "content": content})
                    elif role == "assistant":
                        chat_messages.append({"role": "assistant", "content": content})

        voice_name = voice.get("name", self.agent.name)
        user_turn_parts = []
        if inner_thought:
            user_turn_parts.append(f"[Your private thought, do not share: {inner_thought}]")
        if memory_awareness:
            user_turn_parts.append(f"[Memory context: {memory_awareness[:600]}]")
        if imagined_memory_text:
            user_turn_parts.append(f"[{imagined_memory_text[:600]}]")
        if user_knowledge_text:
            user_turn_parts.append(f"[{user_knowledge_text[:400]}]")
        if prev_text:
            user_turn_parts.append(f"[Previous sessions: {prev_text[:300]}]")
        if repeated_openings_text:
            user_turn_parts.append(f"[{repeated_openings_text}]")
        if greeting_instruction:
            user_turn_parts.append(f"[{greeting_instruction}]")
        if direct_user_line:
            user_turn_parts.append(f"[{direct_user_line}]")
        if cleaned:
            user_turn_parts.append(
                f"[Internal cognitive material from your thought process — use as inspiration, "
                f"do not copy verbatim: {cleaned[:1000]}]"
            )

        user_turn_parts.append(query)

        final_user_content = "\n".join(user_turn_parts)

        # Remove the last history user message if it duplicates the current query
        if (len(chat_messages) >= 2
                and chat_messages[-1].get("role") == "user"
                and chat_messages[-1].get("content", "").strip() == query.strip()):
            chat_messages.pop()

        chat_messages.append({"role": "user", "content": final_user_content})

        try:
            response = self.llm_client.chat_completion(
                chat_messages,
                max_tokens=1000,
                temperature=0.75,
            ).strip()
            return self._validate_and_repair(response, query, persona_name, voice)
        except Exception as e:
            logger.error(f"Erro ao gerar resposta com LLM: {e}")
            return cleaned if cleaned else "Desculpa, estou com dificuldade em articular o que quero dizer agora."

    def _extract_opening_phrase(self, content: str) -> str:
        text = (content or "").strip()
        if not text:
            return ""
        first_sentence = re.split(r"(?<=[.!?])\s+", text, maxsplit=1)[0]
        words = first_sentence.split()
        return " ".join(words[:8]).strip()

    def _format_conversation_memory(self, memory: Dict[str, Any]) -> str:
        if not memory:
            return ""

        lines = ["Live memory of the recent conversation:"]
        fields = [
            ("summary", "Summary"),
            ("current_topic", "Current topic"),
            ("user_latest_intent", "Latest user intent"),
            ("assistant_recent_commitment", "My pending commitment/question"),
            ("pending_user_question", "Pending request/question"),
            ("continuity_guidance", "How to continue now"),
        ]
        for key, label in fields:
            value = memory.get(key)
            if value:
                lines.append(f"- {label}: {str(value)[:500]}")

        if memory.get("should_continue_previous_thread"):
            lines.append(
                "- Required continuity: before reacting emotionally, continue/answer the pending subject."
            )

        return "\n".join(lines)

    def _validate_and_repair(self, response: str, query: str, persona_name: str, voice: Dict) -> str:
        """Single-pass validation: checks all response problems at once, repairs if needed."""
        if not response or not query:
            return response

        check_prompt = self.prompts.render(
            "core.response_validation",
            persona_name=persona_name,
            query=query,
            response=response,
        )
        try:
            raw = self.llm_client.generate(check_prompt, max_tokens=150, temperature=0.1).strip()
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                start = raw.find("{")
                end = raw.rfind("}")
                parsed = json.loads(raw[start:end + 1]) if start >= 0 and end > start else {}

            if parsed.get("is_valid", True):
                return response

            problems = parsed.get("problems", [])
            reason = parsed.get("reason", "validation failed")
            logger.warning(f"[VALIDATE] Response problems: {problems} — {reason}")

            voice_name = voice.get("name", persona_name)
            repair_prompt = self.prompts.render(
                "core.response_repair",
                persona_name=persona_name,
                query=query,
                response=response,
                problems=", ".join(problems) if problems else reason,
                target_language=getattr(self.agent, "language", "pt-PT") or "pt-PT",
            )
            repaired = self.llm_client.generate(
                repair_prompt, max_tokens=700, temperature=0.3,
                system_prompt=f"You are {voice_name}. Fix the response. Speak as yourself in first person.",
            ).strip()
            return repaired or response

        except Exception as e:
            logger.debug(f"[VALIDATE] Check failed: {e}")

        return response

    def _get_state_modifiers(self, reaction_type: str) -> str:
        """Gera texto de modificadores de estado para o prompt"""

        if not self.persona.has_persona:
            return ""

        modifiers = self.persona.blueprint.behavior_prompts.get("emotional_state_modifiers", {})

        state = self.persona.state
        if not state:
            return ""

        parts = []

        # Energy-based modifiers
        energy = state.energy_level or 0.7
        if energy < 0.3:
            low_energy = modifiers.get("low_energy", {})
            if low_energy:
                parts.append(f"Energia baixa: respostas {low_energy.get('response_length', 'mais curtas')}, "
                           f"tom {low_energy.get('tone', 'plano')}, humor {low_energy.get('humor', 'ausente')}.")
        elif energy > 0.8:
            high_energy = modifiers.get("high_energy", {})
            if high_energy:
                parts.append(f"Energia alta: tom {high_energy.get('tone', 'animado')}, "
                           f"humor {high_energy.get('humor', 'presente')}.")

        # Reaction-based modifiers
        if reaction_type in ["traumatic_reactive", "traumatic_withdrawn"]:
            triggered = modifiers.get("triggered", {})
            if triggered:
                reg_age = triggered.get("regression_to_age", 0)
                rational = triggered.get("rational_capacity", 0.3)
                if reg_age > 0:
                    parts.append(f"Regressão emocional: comportas-te como se tivesses {reg_age} anos.")
                parts.append(f"Capacidade racional reduzida a {int(rational * 100)}%.")

        # Dissociation
        if state.intoxication_state == "numb" or state.intoxication_state == "dissociated":
            diss = modifiers.get("dissociating", {})
            if diss:
                parts.append(f"Dissociação: {diss.get('response_pattern', 'respostas vagas e desconectadas')}.")

        # Stress level
        stress = state.current_stress_load or 0
        if stress > 0.7:
            # Activar defesas do blueprint
            defenses = state.active_defenses or []
            if defenses:
                parts.append(f"Defesas activas: {', '.join(defenses[:2])}.")

        return "\n".join(parts)

    # ================================================================
    # AUTO-GERAÇÃO DE MEMÓRIAS
    # ================================================================

    def _auto_generate_memories(
        self,
        query: str,
        response: str,
        context: Dict,
        user_id: Optional[str]
    ):
        """
        Single AI call analyzes the interaction and extracts everything worth remembering:
        name, personal facts, emotional significance. Runs in background after response.
        """
        try:
            user_name = context.get("user_name", user_id or "utilizador")

            prompt = self.prompts.render(
                "memory.interaction_analysis",
                user_name=user_name,
                query=query[:800],
                response=response[:500],
            )
            raw = self.llm_client.generate(prompt, max_tokens=300, temperature=0.15).strip()

            try:
                analysis = json.loads(raw)
            except json.JSONDecodeError:
                start = raw.find("{")
                end = raw.rfind("}")
                if start >= 0 and end > start:
                    analysis = json.loads(raw[start:end + 1])
                else:
                    return

            # Process name if detected with high confidence
            name_data = analysis.get("person_name", {})
            detected_name = str(name_data.get("value") or "").strip()
            name_confidence = name_data.get("confidence", 0)
            if detected_name and isinstance(name_confidence, (int, float)) and name_confidence >= 0.8:
                name_content = f"{detected_name} told me their name. I should remember and use it."
                if self.memory_manager.should_store_memory(detected_name, name_content, "relational"):
                    self.memory_manager.create_memory(
                        title=f"This person's name is {detected_name}",
                        content=name_content,
                        memory_type="relational",
                        importance_score=0.9,
                        emotional_valence=0.3,
                        relates_to_topics=["user_name", "user_info", user_id or "unknown"]
                    )
                    if user_id:
                        self.identity.update_relationship(
                            user_id=user_id, user_name=detected_name,
                            familiarity_change=0.05, affection_change=0.02,
                        )

            # Process extracted facts
            for fact_data in analysis.get("facts", []):
                fact = str(fact_data.get("fact") or "").strip()
                importance = fact_data.get("importance", 0.5)
                fact_type = fact_data.get("type", "experience")
                if not fact or len(fact.split()) < 3:
                    continue

                fact_title = f"{user_name}: {fact[:80]}"
                fact_content = f"{user_name} revealed: {fact}. Context: \"{query[:150]}\""

                if self.memory_manager.should_store_memory(fact_title, fact_content, "relational"):
                    self.memory_manager.create_memory(
                        title=fact_title,
                        content=fact_content,
                        memory_type="relational",
                        importance_score=max(0.3, min(1.0, float(importance))),
                        emotional_valence=0.1,
                        relates_to_topics=["user_info", fact_type, user_id or "unknown"]
                    )

            # Process emotional significance
            emo = analysis.get("emotional_significance", {})
            if emo.get("is_significant") and emo.get("what_i_felt"):
                emo_text = str(emo["what_i_felt"]).strip()
                emo_title = f"Emotional moment with {user_name}: {emo_text[:50]}"
                emo_content = f"I felt {emo_text} when {user_name} said: {query[:100]}"

                if self.memory_manager.should_store_memory(emo_title, emo_content, "emotional"):
                    self.memory_manager.create_memory(
                        title=emo_title,
                        content=emo_content,
                        memory_type="emotional",
                        importance_score=0.7,
                        emotional_valence=0.2,
                        relates_to_topics=["emotional_event", user_id or "unknown"]
                    )

        except Exception as e:
            logger.debug(f"Erro ao auto-gerar memórias: {e}")

    # ================================================================
    # SELF-REFLECTION
    # ================================================================

    def _self_reflect(self, query: str, response: str, context: Dict, user_id: Optional[str]):
        """
        The bot briefly reflects on its own response — did it handle this well?
        Creates memories about its own patterns and growth, like a real person would.
        """
        try:
            if len(response) < 30 or len(query) < 10:
                return

            reaction = context.get("emotional_reaction", {})
            intensity = reaction.get("intensity", 0) if isinstance(reaction, dict) else 0
            if intensity < 0.3:
                return

            relationship = context.get("relationship_snapshot", {})
            trust = relationship.get("trust_level", 0.5) if relationship else 0.5
            user_name = context.get("user_name") or "a pessoa"

            prompt = self.prompts.render(
                "core.self_reflection",
                user_name=user_name,
                query=query[:800],
                response=response[:1000],
                trust=f"{trust:.2f}",
            )

            result = self.llm_client.generate(prompt, max_tokens=100, temperature=0.4)
            result = (result or "").strip()

            reflection = ""
            if result.startswith("REFLECTION:"):
                reflection = result[11:].strip()
            elif result.startswith("REFLEXÃO:"):
                reflection = result[9:].strip()
            if reflection:
                if len(reflection) > 10:
                    ref_title = f"Reflection: {reflection[:60]}"
                    ref_content = f"After speaking with {user_name}, I thought: {reflection}"
                    if self.memory_manager.should_store_memory(ref_title, ref_content, "episodic"):
                        self.memory_manager.create_memory(
                            title=ref_title,
                            content=ref_content,
                            memory_type="episodic",
                            importance_score=0.45,
                            emotional_valence=0.1,
                            relates_to_topics=["self_reflection", "growth", user_id or "unknown"]
                        )
        except Exception as e:
            logger.debug(f"Self-reflection failed: {e}")

    # ================================================================
    # RELATIONSHIP
    # ================================================================

    def _update_relationship(self, user_id: str, context: Dict):
        """Actualiza relação com o utilizador"""

        try:
            query = (context.get("latest_user_query") or "").strip()
            user_name = context.get("user_name")
            reaction = context.get("emotional_reaction", {})
            reaction_type = ""
            if isinstance(reaction, dict):
                reaction_type = reaction.get("emotional_reaction", "")

            # Every interaction builds familiarity; non-negative ones build trust
            familiarity_change = 0.02
            trust_change = 0.01
            affection_change = 0.005

            if reaction_type == "angry":
                familiarity_change = 0.0
                trust_change = -0.03
                affection_change = -0.02
            elif reaction_type == "happy":
                familiarity_change = 0.04
                trust_change = 0.04
                affection_change = 0.03
            elif reaction_type in ["empathetic_supportive", "receptive"]:
                familiarity_change = 0.03
                trust_change = 0.05
                affection_change = 0.03
            elif reaction_type in ["traumatic_reactive", "traumatic_withdrawn"]:
                trust_change = -0.01

            topic = self._extract_conversation_topic(query)
            signal = self._classify_relationship_signal(query)

            if signal == "positive":
                familiarity_change += 0.02
                trust_change += 0.04
                affection_change += 0.04
            elif signal == "vulnerable":
                familiarity_change += 0.03
                trust_change += 0.06
                affection_change += 0.05
            elif signal == "negative":
                familiarity_change -= 0.01
                trust_change -= 0.03
                affection_change -= 0.02

            memorable_moment = None
            if signal in ("vulnerable", "positive") and query:
                memorable_moment = query[:140]

            self.identity.update_relationship(
                user_id=user_id,
                user_name=user_name,
                familiarity_change=familiarity_change,
                trust_change=trust_change,
                affection_change=affection_change,
                topic=topic,
                memorable_moment=memorable_moment,
            )
        except Exception as e:
            logger.debug(f"Erro ao actualizar relação: {e}")

    def _extract_conversation_topic(self, query: str) -> Optional[str]:
        if not query:
            return None
        words = re.findall(r"[a-zA-ZÀ-ÿ0-9]+", query.lower())
        significant = [w for w in words if len(w) >= 4]
        if not significant:
            return None
        return " ".join(significant[:3])

    def _classify_relationship_signal(self, query: str) -> str:
        if not (query or "").strip():
            return "neutral"
        try:
            prompt = self.prompts.render(
                "relationship.signal",
                message=query[:1200],
                relationship_context="",
                emotional_reaction="",
            )
            raw = self.llm_client.generate(prompt, max_tokens=120, temperature=0.1).strip()
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                start = raw.find("{")
                end = raw.rfind("}")
                parsed = json.loads(raw[start:end + 1]) if start >= 0 and end > start else {}
            signal = str(parsed.get("signal", "neutral")).strip().lower()
            return signal if signal in {"positive", "vulnerable", "negative", "neutral"} else "neutral"
        except Exception as e:
            logger.debug(f"Falha ao classificar sinal relacional: {e}")
            return "neutral"

    # ================================================================
    # USER KNOWLEDGE & CURIOSITY
    # ================================================================

    def _build_user_knowledge_context(self, user_id: Optional[str], context: Dict) -> str:
        """
        Builds a factual summary of what the agent knows/doesn't know about the user.
        Curiosity behaviour emerges from the persona's own personality — nothing is hardcoded.
        """
        if not user_id:
            return ""

        user_name = context.get("user_name") or "esta pessoa"

        user_memories = self.memory_manager.recall_relevant_memories(user_id, limit=20)
        relational = [
            m for m in user_memories
            if "user_info" in (m.relates_to_topics or []) or "user_name" in (m.relates_to_topics or [])
        ]

        known_facts = []
        for m in relational:
            known_facts.append(f"- {m.title}: {m.content[:120]}")

        extra = self.memory_manager.recall_relevant_memories(user_name, limit=10)
        for m in extra:
            line = f"- {m.title}: {m.content[:120]}"
            if line not in known_facts:
                known_facts.append(line)

        relationship = self.identity.get_relationship_snapshot(user_id)
        trust = relationship.get("trust_level", 0.5) if relationship else 0.5
        familiarity = relationship.get("familiarity", 0.0) if relationship else 0.0
        affection = relationship.get("affection", 0.5) if relationship else 0.5
        interactions = relationship.get("interaction_count", 0) if relationship else 0

        known_section = "\n".join(known_facts[:15]) if known_facts else "Quase nada ainda."

        combined = " ".join(
            (m.content.lower() + " " + m.title.lower()) for m in relational
        )
        dimensions = [
            "nome", "profissão/ocupação", "idade", "onde vive",
            "hobbies/interesses", "família", "sonhos/objectivos",
            "medos/preocupações", "gostos culturais", "personalidade",
        ]
        dim_keywords = {
            "nome": ["nome", "chama", "name", "call me"],
            "profissão/ocupação": ["trabalh", "profiss", "estud", "work", "job"],
            "idade": ["anos", "idade", "age", "years old"],
            "onde vive": ["mora", "vive em", "live", "from", "cidade"],
            "hobbies/interesses": ["gost", "hobby", "interes", "like", "enjoy"],
            "família": ["famíl", "pai", "mãe", "irmã", "filh", "family", "mother", "father"],
            "sonhos/objectivos": ["sonh", "objectiv", "meta", "dream", "goal"],
            "medos/preocupações": ["medo", "preocup", "ansied", "fear", "worr"],
            "gostos culturais": ["músic", "film", "livro", "série", "jogo", "music", "movie", "book"],
            "personalidade": ["introvert", "extrovert", "tímid", "sociáv", "shy", "outgoing"],
        }
        unknown = [d for d in dimensions if not any(k in combined for k in dim_keywords.get(d, []))]

        # --- personality-driven parameters ---
        bp = self.persona.blueprint
        big5 = {}
        facets = {}
        social = {}
        if bp:
            pf = bp.personality_full or {}
            big5 = pf.get("big_five", {})
            facets = pf.get("facets", {})
            sc = bp.social_config or {}
            social = sc.get("relational_patterns", {})

        openness = big5.get("openness", 0.5)
        extraversion = big5.get("extraversion", 0.5)
        agreeableness = big5.get("agreeableness", 0.5)
        neuroticism = big5.get("neuroticism", 0.3)
        curiosity = facets.get("curiosity", 0.5)
        empathy = facets.get("empathy", 0.6)
        trust_default = social.get("trust_default", "neutral")
        with_strangers = "guarded"
        if bp and bp.social_config:
            with_strangers = (bp.social_config.get("social_roles") or {}).get("with_strangers", "guarded")

        personality_summary = (
            f"Your traits that influence how you relate:\n"
            f"  Openness: {openness:.2f} | Extraversion: {extraversion:.2f} | "
            f"Agreeableness: {agreeableness:.2f} | Neuroticism: {neuroticism:.2f}\n"
            f"  Curiosity: {curiosity:.2f} | Empathy: {empathy:.2f}\n"
            f"  Stance with strangers: {with_strangers} | Baseline trust: {trust_default}"
        )

        return (
            f"=== WHAT YOU KNOW ABOUT {user_name.upper()} ===\n"
            f"{known_section}\n\n"
            f"Things you still do NOT know: {', '.join(unknown) if unknown else 'You already know quite a lot.'}\n"
            f"Current relationship: trust={trust:.2f}, familiarity={familiarity:.2f}, "
            f"affection={affection:.2f}, interactions={interactions}\n\n"
            f"{personality_summary}\n\n"
            f"Based on your personality and the current relationship state, decide naturally:\n"
            f"- Whether you want to know more about this person (your curiosity is {curiosity:.2f}).\n"
            f"- How direct or subtle your question should be (your extraversion is {extraversion:.2f}).\n"
            f"- Whether you open up first or wait for the person to open up (your stance with strangers is '{with_strangers}').\n"
            f"- Whether you show vulnerability or keep distance (your neuroticism is {neuroticism:.2f}, agreeableness {agreeableness:.2f}).\n"
            f"- How much you genuinely care about what this person feels (your empathy is {empathy:.2f}).\n\n"
            f"Do not follow fixed rules; act as YOU act. If you are shy, be shy. If you are direct, be direct.\n"
            f"If you want to ask something, ask at most ONE question and let it arise naturally from the conversation.\n"
            f"Use what you already know to show that you remember; that creates real connection."
        )

    # ================================================================
    # CONSENSUS & WEIGHTING (mantido do v1, optimizado)
    # ================================================================

    def _analyze_consensus(self, responses: Dict[str, Dict]) -> Dict[str, Any]:
        if not responses:
            return {"consensus_score": 0.0, "agreement_count": 0, "conflict_count": 0}

        confidences = [r.get("confidence", 0.5) for r in responses.values()]
        avg = sum(confidences) / len(confidences)
        std = self._std_dev(confidences)

        return {
            "consensus_score": max(0, avg - std * 0.2),
            "agreement_count": sum(1 for c in confidences if c > 0.7),
            "conflict_count": sum(1 for c in confidences if c < 0.4),
            "avg_confidence": avg,
        }

    def _weight_perspectives(self, responses: Dict, query: str, consensus: Dict) -> List[Tuple[str, Dict, float]]:
        weighted = []
        for agent_type, response in responses.items():
            base_w = response.get("weight", 1.0)
            conf = response.get("confidence", 0.5)
            conf_factor = 0.8 + conf * 0.4
            final_w = base_w * conf_factor

            # Se imaginação criou memória útil, dá prioridade para entrar na resposta final
            if agent_type == "imagination" and response.get("created_memory"):
                final_w *= 1.35

            weighted.append((agent_type, response, final_w))

        total = sum(w for _, _, w in weighted) or 1
        return sorted(
            [(t, r, w / total) for t, r, w in weighted],
            key=lambda x: x[2], reverse=True
        )

    def _resolve_conflicts(self, weighted: List[Tuple], consensus: Dict) -> Dict:
        if not weighted:
            return {"main_response": "", "reasoning": "Sem perspectivas"}

        # Juntar perspectivas numa só
        parts = []
        included_agents = set()
        for agent_type, response, weight in weighted[:4]:
            if agent_type == "memory_curator":
                continue
            perspective = response.get("perspective", "")
            if perspective:
                parts.append(perspective)
                included_agents.add(agent_type)

        # Garante que cenário imaginado entra na síntese quando foi criado
        imagination_item = next(
            (
                item for item in weighted
                if item[0] == "imagination" and item[1].get("created_memory")
            ),
            None
        )
        imagined_memory = ""
        if imagination_item:
            imag_perspective = imagination_item[1].get("perspective", "")
            imag_excerpt = imagination_item[1].get("created_memory_excerpt", "")
            imagined_memory = imag_excerpt or imag_perspective
            if "imagination" not in included_agents:
                if imag_perspective:
                    parts.append(imag_perspective)
                if imag_excerpt:
                    parts.append(imag_excerpt)

        return {
            "main_response": " ".join(parts),
            "reasoning": f"Baseado em {len(weighted)} perspectivas internas",
            "approach": "integrated",
            "imagined_memory": imagined_memory,
        }

    def _calculate_final_confidence(self, weighted: List[Tuple]) -> float:
        if not weighted:
            return 0.3
        total_conf = sum(r.get("confidence", 0.5) * w for _, r, w in weighted)
        total_w = sum(w for _, _, w in weighted) or 1
        return total_conf / total_w

    def _remove_agent_markers(self, text: str) -> str:
        cleaned = re.sub(r'\s*\([a-z_]+\):\s*', ' ', text)
        cleaned = re.sub(r'\s*Adicionalmente\s+', ' ', cleaned)
        return re.sub(r'\s+', ' ', cleaned).strip()

    def _std_dev(self, values: List[float]) -> float:
        if not values:
            return 0.0
        avg = sum(values) / len(values)
        variance = sum((x - avg) ** 2 for x in values) / len(values)
        return variance ** 0.5
