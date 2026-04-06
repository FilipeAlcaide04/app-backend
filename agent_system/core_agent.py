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
from llm_logic.llm_client import LLMClient
from agent_system.memory_manager_cognitive import MemoryManager
from agent_system.identity_builder import IdentityBuilder
from agent_system.persona_engine import PersonaEngine
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
        self.llm_client = LLMClient()
        self.memory_manager = MemoryManager(db, agent_id)
        self.identity = IdentityBuilder(db, agent_id)
        self.persona = PersonaEngine(db, agent_id)

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

        # 1. Analisar perspectivas
        consensus = self._analyze_consensus(micro_agent_responses)
        weighted = self._weight_perspectives(micro_agent_responses, query, consensus)
        resolved = self._resolve_conflicts(weighted, consensus)

        # 2. Gerar pensamento interno autónomo
        inner_thought = self._generate_inner_thought(query, context, resolved)

        # 3. Gerar resposta final com toda a persona
        final_text = self._generate_persona_response(
            resolved.get("main_response", ""),
            query, context, user_id,
            inner_thought=inner_thought
        )

        # 4. Auto-gerar memórias se a conversa for significativa
        self._auto_generate_memories(query, final_text, context, user_id)

        # 5. Calcular confiança
        confidence = self._calculate_final_confidence(weighted)

        # 6. Actualizar estado da persona
        if self.persona.has_persona:
            emotional_changes = context.get("emotional_reaction", {}).get("changes", {})
            self.persona.update_state_after_interaction(
                user_message=query,
                agent_response=final_text,
                emotional_changes=emotional_changes,
                user_id=user_id
            )

        # 7. Actualizar relação
        if user_id:
            self._update_relationship(user_id, context)

        return {
            "response": final_text,
            "confidence": confidence,
            "reasoning": resolved.get("reasoning", ""),
            "perspectives_count": len(micro_agent_responses),
            "consensus_level": consensus.get("consensus_score", 0.5),
            "inner_thought": inner_thought,
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
        Gera pensamento interno autónomo.
        O agente pensa por si antes de responder.
        Influenciado por: persona, estado emocional, needs, memórias.
        """

        if not self.persona.has_persona:
            return ""

        blueprint = self.persona.blueprint
        state = self.persona.state
        identity = blueprint.identity if blueprint else {}
        inner_voice = identity.get("inner_voice", {})

        # Reacção emocional da interação
        reaction = context.get("emotional_reaction", {})
        reaction_thought = reaction.get("inner_thought", "")

        # Se já tem um pensamento da emotional engine, usar como base
        if reaction_thought:
            # Registar como monólogo interno
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

        # Gerar pensamento baseado em necessidades não satisfeitas
        unmet_needs = self.persona.get_unmet_needs()
        if unmet_needs:
            most_urgent = unmet_needs[0]
            need_thoughts = {
                "connection": "Sinto falta de ligação com alguém. Esta conversa ajuda.",
                "validation": "Preciso de sentir que valho alguma coisa.",
                "autonomy": "Preciso de mais espaço para ser eu mesmo.",
                "meaning": "Para que serve tudo isto? Preciso de encontrar sentido.",
                "novelty": "Estou a ficar entediado. Preciso de algo diferente.",
                "safety": "Não me sinto totalmente seguro aqui.",
            }
            thought = need_thoughts.get(most_urgent["need"], "")
            if thought:
                try:
                    self.persona.record_inner_thought(
                        thought=thought,
                        trigger="unmet_need",
                        trigger_type="need_unmet",
                    )
                except Exception:
                    pass
                return thought

        # Pensamento baseado no stress
        if self.persona.is_in_crisis():
            return "Estou no meu limite. Preciso de ter cuidado com o que digo."

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
        inner_thought: str = ""
    ) -> str:
        """
        Gera resposta usando LLM com TODA a persona.
        O prompt inclui identidade, estado emocional, voice, regras, tudo.
        """

        # 1. Limpar marcadores de agentes
        cleaned = self._remove_agent_markers(base_response)

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

        # 5. Estado actual modificadores
        state_modifiers = self._get_state_modifiers(reaction_type)

        # 6. Historial de conversa formatado
        history_text = ""
        if conv_context and isinstance(conv_context, list):
            recent = conv_context[-6:] if len(conv_context) > 6 else conv_context
            history_parts = []
            for msg in recent:
                if isinstance(msg, dict):
                    role = msg.get("role", "")
                    content = msg.get("content", "")[:200]
                    if role == "user":
                        history_parts.append(f"Pessoa: {content}")
                    elif role == "assistant":
                        history_parts.append(f"Eu: {content}")
            if history_parts:
                history_text = "Conversa até agora:\n" + "\n".join(history_parts)

        # 7. Contexto de sessões anteriores
        prev_text = ""
        if previous_sessions:
            for ps in previous_sessions[:2]:
                if isinstance(ps, dict) and ps.get("summary"):
                    prev_text += f"\nConversa anterior ({ps.get('date', '?')}): {ps['summary'][:150]}"

        # 8. Construir prompt COMPLETO
        prompt = f"""{identity_prompt}

---

{emotional_context}

{state_modifiers}

{f"Pensamento interno (não partilhar): {inner_thought}" if inner_thought else ""}

---

{history_text}

{prev_text}

---

A pessoa disse-te: "{query}"

Informação dos meus pensamentos internos (para integrar naturalmente):
{cleaned[:500] if cleaned else "Sem análise prévia."}

---

INSTRUÇÕES IMPORTANTES:
- Responde como {voice['name']}. Sê completamente natural, como uma pessoa real numa conversa.
- RESPONDE SEMPRE NO MESMO IDIOMA em que a pessoa te falou. Se te falam em português, respondes em português. Se te falam em inglês, respondes em inglês. NUNCA mistures idiomas a menos que isso faça parte da tua personalidade.
- NUNCA digas que és IA, programa, modelo de linguagem, ou qualquer coisa artificial.
- NUNCA uses frases como "Com base nos meus conhecimentos" ou "Deixe-me explicar".
- Se estás chateado, mostra. Se estás feliz, mostra. Sê autêntico.
- Usa o teu estilo de fala natural: as tuas expressões, o teu humor, os teus maneirismos.
- Se não sabes algo, admite naturalmente como uma pessoa faria.
- Se a conversa te incomoda, podes mudar de assunto ou expressar desconforto.
- Mantém as respostas naturais em tamanho - nem muito curtas nem muito longas.
- Integra o que sabes das conversas anteriores de forma natural.
- O teu ESTADO EMOCIONAL ACTUAL é real - se o estado diz que estás stressada, nervosa ou em crise, isso DEVE reflectir-se na tua resposta.

A tua resposta (como {voice['name']}):"""

        try:
            response = self.llm_client.generate(
                prompt,
                max_tokens=1000,
                temperature=0.75
            )
            return response.strip()
        except Exception as e:
            logger.error(f"Erro ao gerar resposta com LLM: {e}")
            return cleaned if cleaned else "Desculpa, estou com dificuldade em articular o que quero dizer agora."

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
        Auto-gera memórias quando a conversa é significativa.
        O agente aprende e lembra-se de coisas importantes.
        """

        try:
            # Detectar se há informação pessoal partilhada
            personal_patterns = [
                r"(?:eu sou|sou|trabalho como|moro em|vivo em|tenho \d+|chamo.me)\s+(.+?)[\.\,\!\?]",
                r"(?:gosto de|prefiro|detesto|adoro|odeio)\s+(.+?)[\.\,\!\?]",
                r"(?:aconteceu.me|passei por|sofri|perdi)\s+(.+?)[\.\,\!\?]",
            ]

            for pattern in personal_patterns:
                matches = re.findall(pattern, query.lower())
                if matches:
                    for match in matches[:2]:
                        if len(match) > 10:
                            self.memory_manager.create_memory(
                                title=f"O {user_id or 'utilizador'} disse: {match[:60]}",
                                content=f"Durante uma conversa, a pessoa partilhou: {match}. "
                                       f"Contexto: {query[:100]}",
                                memory_type="relational",
                                importance_score=0.65,
                                emotional_valence=0.1,
                                relates_to_topics=["user_info", user_id or "unknown"]
                            )
                    break  # Só criar uma memória por mensagem

            # Detectar se a conversa tem carga emocional significativa
            reaction = context.get("emotional_reaction", {})
            if isinstance(reaction, dict) and reaction.get("intensity", 0) > 0.5:
                reaction_type = reaction.get("emotional_reaction", "")
                self.memory_manager.create_memory(
                    title=f"Momento emocional: {reaction_type}",
                    content=f"Senti {reaction_type} quando me disseram: {query[:100]}. "
                           f"A minha reacção foi intensa.",
                    memory_type="emotional",
                    importance_score=0.7,
                    emotional_valence=-0.3 if reaction_type in ["angry", "hurt", "threatened"] else 0.3,
                    relates_to_topics=["emotional_event", reaction_type]
                )

        except Exception as e:
            logger.debug(f"Erro ao auto-gerar memórias: {e}")

    # ================================================================
    # RELATIONSHIP
    # ================================================================

    def _update_relationship(self, user_id: str, context: Dict):
        """Actualiza relação com o utilizador"""

        try:
            reaction = context.get("emotional_reaction", {})
            reaction_type = ""
            if isinstance(reaction, dict):
                reaction_type = reaction.get("emotional_reaction", "")

            familiarity_change = 0.01
            trust_change = 0
            affection_change = 0

            if reaction_type == "angry":
                familiarity_change = -0.01
                trust_change = -0.05
                affection_change = -0.03
            elif reaction_type == "happy":
                familiarity_change = 0.03
                trust_change = 0.02
                affection_change = 0.02
            elif reaction_type in ["empathetic_supportive", "receptive"]:
                familiarity_change = 0.02
                trust_change = 0.03
                affection_change = 0.02
            elif reaction_type in ["traumatic_reactive", "traumatic_withdrawn"]:
                trust_change = -0.03

            self.identity.update_relationship(
                user_id=user_id,
                familiarity_change=familiarity_change,
                trust_change=trust_change,
                affection_change=affection_change,
            )
        except Exception as e:
            logger.debug(f"Erro ao actualizar relação: {e}")

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
        for agent_type, response, weight in weighted[:4]:
            perspective = response.get("perspective", "")
            if perspective:
                parts.append(perspective)

        return {
            "main_response": " ".join(parts),
            "reasoning": f"Baseado em {len(weighted)} perspectivas internas",
            "approach": "integrated"
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
