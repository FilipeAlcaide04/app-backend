"""
Emotional Engine v2 - Sistema emocional completo com persona integration

Integra com PersonaEngine para:
- Attachment style influencia reações
- Window of tolerance determina capacidade de regulação
- Defense mechanisms activam-se automaticamente
- Triggers traumáticos das memórias
- Necessidades emocionais afectam comportamento
- Estado persiste entre conversas (last state)
- Decay temporal realista
"""

from sqlalchemy.orm import Session
from data.schema_cognitive import Agent, Memory, MemoryType, PersonalityProfile
from data.schema_persona import PersonaBlueprint, DynamicState, BehavioralLog
from agent_system.prompt_manager import PromptManager
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import math
import re
import json
import logging

logger = logging.getLogger(__name__)


class EmotionalEngine:
    """
    Sistema emocional que reage baseado na PERSONA COMPLETA.
    Não apenas Big Five - usa attachment, trauma, defenses, needs, tudo.
    """

    # A classificação emocional da mensagem é semântica e configurável em BD
    # (`emotion.intent_analysis`), não uma lista de palavras fixa.

    def __init__(self, db: Session, agent_id: str):
        self.db = db
        self.agent_id = agent_id
        self.blueprint: Optional[PersonaBlueprint] = None
        self.state: Optional[DynamicState] = None
        self.personality: Dict[str, float] = {}
        self.traumatic_triggers: List[Dict] = []
        self.prompts = PromptManager(db)

        self._load()

    def _load(self):
        """Carrega persona e estado"""

        # Blueprint
        self.blueprint = self.db.query(PersonaBlueprint).filter(
            PersonaBlueprint.agent_id == self.agent_id
        ).first()

        # Estado dinâmico actual
        self.state = self.db.query(DynamicState).filter(
            DynamicState.agent_id == self.agent_id,
            DynamicState.is_current == True
        ).first()

        # Personalidade (do blueprint ou fallback)
        if self.blueprint:
            big_five = self.blueprint.personality_full.get("big_five", {})
            self.personality = {
                "openness": big_five.get("openness", 0.5),
                "conscientiousness": big_five.get("conscientiousness", 0.5),
                "extraversion": big_five.get("extraversion", 0.5),
                "agreeableness": big_five.get("agreeableness", 0.5),
                "neuroticism": big_five.get("neuroticism", 0.3),
                "resilience": 1.0 - big_five.get("neuroticism", 0.3),
            }
        else:
            # Fallback para PersonalityProfile antigo
            profile = self.db.query(PersonalityProfile).filter(
                PersonalityProfile.agent_id == self.agent_id
            ).first()

            if profile:
                self.personality = {
                    "openness": profile.openness or 0.5,
                    "conscientiousness": profile.conscientiousness or 0.5,
                    "extraversion": profile.extraversion or 0.5,
                    "agreeableness": profile.agreeableness or 0.5,
                    "neuroticism": profile.neuroticism or 0.3,
                    "resilience": 1.0 - (profile.neuroticism or 0.3),
                }
            else:
                agent = self.db.query(Agent).filter(Agent.id == self.agent_id).first()
                traits = (agent.personality_traits or {}) if agent else {}
                self.personality = {
                    "openness": traits.get("openness", 0.5),
                    "conscientiousness": traits.get("conscientiousness", 0.5),
                    "extraversion": traits.get("extraversion", 0.5),
                    "agreeableness": traits.get("agreeableness", 0.5),
                    "neuroticism": traits.get("neuroticism", 0.3),
                    "resilience": 1.0 - traits.get("neuroticism", 0.3),
                }

        # Carregar triggers traumáticos
        self._load_traumatic_triggers()

    def _load_traumatic_triggers(self):
        """Carrega triggers de memórias traumáticas E do blueprint"""
        from data.schema_persona import PersonaMemoryDetail

        self.traumatic_triggers = []

        # 1. Do blueprint (emotional_triggers definidos na persona)
        if self.blueprint:
            triggers = self.blueprint.emotional_config.get("emotional_triggers", [])
            for t in triggers:
                trigger_text = t.get("trigger", "")
                reaction_text = t.get("reaction", t.get("actual_response", ""))
                self.traumatic_triggers.append({
                    "type": "persona_defined",
                    "trigger": trigger_text,
                    "emotion": t.get("emotion_activated", "fear"),
                    "intensity": t.get("intensity", 0.7),
                    "response": reaction_text,
                    "typical_behavior": t.get("typical_behavior", reaction_text),
                    "origin": t.get("origin_memory", ""),
                    "keywords": self._extract_keywords(trigger_text + " " + reaction_text)
                })

            # 2. Do blueprint memory_config (trauma triggers das memórias iniciais)
            initial_memories = self.blueprint.memory_config.get("initial_memories", [])
            for mem in initial_memories:
                trauma = mem.get("trauma", {})
                if not trauma:
                    continue
                content = mem.get("content", "")
                trauma_triggers = trauma.get("triggers", [])
                beliefs = trauma.get("beliefs_formed", [])
                # Criar keywords do conteúdo + triggers explícitos + beliefs
                all_text = content + " " + " ".join(trauma_triggers) + " " + " ".join(beliefs)
                keywords = self._extract_keywords(all_text)
                # Adicionar os trigger phrases como keywords directos (podem ser curtos)
                for t in trauma_triggers:
                    for word in re.findall(r'\b[a-záàâãéèêíìîóòôõúùûç]{3,}\b', t.lower()):
                        if word not in keywords:
                            keywords.append(word)

                self.traumatic_triggers.append({
                    "type": "blueprint_trauma",
                    "trigger": content,
                    "title": content[:80],
                    "trauma_type": trauma.get("type", "unknown"),
                    "emotion": "fear",
                    "intensity": trauma.get("severity", 0.7),
                    "keywords": keywords[:15],
                    "beliefs": beliefs,
                    "explicit_triggers": trauma_triggers,
                })

        # 3. De PersonaMemoryDetail no DB (trauma details via join com Memory)
        details = self.db.query(PersonaMemoryDetail, Memory).join(
            Memory, PersonaMemoryDetail.memory_id == Memory.id
        ).filter(
            Memory.agent_id == self.agent_id,
            PersonaMemoryDetail.is_traumatic == True
        ).all()

        for detail, mem in details:
            # triggers é lista de dicts [{description, intensity}]
            raw_triggers = detail.triggers or []
            explicit_triggers = [t.get("description", t) if isinstance(t, dict) else str(t) for t in raw_triggers]
            beliefs = detail.beliefs_formed or []
            content = f"{mem.title or ''} {mem.content or ''}"
            all_text = content + " " + " ".join(explicit_triggers) + " " + " ".join(beliefs)
            keywords = self._extract_keywords(all_text)
            for t in explicit_triggers:
                for word in re.findall(r'\b[a-záàâãéèêíìîóòôõúùûç]{3,}\b', t.lower()):
                    if word not in keywords:
                        keywords.append(word)

            self.traumatic_triggers.append({
                "type": "memory_trauma",
                "memory_id": detail.memory_id,
                "title": mem.title or detail.trauma_type,
                "trauma_type": detail.trauma_type,
                "intensity": detail.trauma_severity or 0.7,
                "emotion": "fear",
                "keywords": keywords[:15],
                "beliefs": beliefs,
                "explicit_triggers": explicit_triggers,
            })

        # 4. De memórias traumáticas genéricas (fallback)
        traumatic_types = self.db.query(MemoryType).filter(
            MemoryType.name.in_(["traumatic", "emotional"])
        ).all()
        type_ids = [t.id for t in traumatic_types]

        existing_mem_ids = {t.get("memory_id") for t in self.traumatic_triggers if t.get("memory_id")}

        if type_ids:
            memories = self.db.query(Memory).filter(
                Memory.agent_id == self.agent_id,
                Memory.type_id.in_(type_ids),
                Memory.emotional_valence < -0.4,
                ~Memory.id.in_(existing_mem_ids) if existing_mem_ids else True
            ).all()
        else:
            memories = self.db.query(Memory).filter(
                Memory.agent_id == self.agent_id,
                Memory.emotional_valence < -0.5,
                ~Memory.id.in_(existing_mem_ids) if existing_mem_ids else True
            ).all()

        for mem in memories:
            keywords = self._extract_keywords(f"{mem.title or ''} {mem.content or ''}")
            if keywords:
                self.traumatic_triggers.append({
                    "type": "memory",
                    "memory_id": mem.id,
                    "title": mem.title,
                    "intensity": abs(mem.emotional_valence or 0.5),
                    "keywords": keywords
                })

        if self.traumatic_triggers:
            logger.debug(f"[emotion] {len(self.traumatic_triggers)} triggers carregados para {self.agent_id}")

    def _extract_keywords(self, text: str) -> List[str]:
        """Extrai keywords significativas (inclui palavras de 3+ chars para nomes curtos como 'pai', 'mãe')"""
        stop = {"o", "a", "os", "as", "um", "uma", "de", "da", "do", "em", "no", "na",
                "que", "e", "é", "para", "com", "por", "foi", "ser", "como", "mais",
                "isso", "este", "esta", "seu", "sua", "ele", "ela", "eu", "tu", "nós",
                "muito", "tinha", "tenho", "ter", "quando", "onde", "mas", "nem", "não",
                "sim", "nao", "sao", "tem", "são", "aos", "das", "dos", "nos", "nas"}
        words = re.findall(r'\b[a-záàâãéèêíìîóòôõúùûç]{3,}\b', text.lower())
        return list(set(w for w in words if w not in stop))[:15]

    # ================================================================
    # ANÁLISE DE INTENÇÃO
    # ================================================================

    def analyze_user_intent(self, text: str) -> Dict[str, Any]:
        """Analisa intenção do utilizador de forma completa"""

        analysis = {
            "is_insult": False, "is_praise": False,
            "is_aggressive": False, "is_dismissive": False,
            "insult_intensity": 0.0, "praise_intensity": 0.0,
            "traumatic_trigger": None, "user_emotions": {},
            "is_vulnerable": False, "is_seeking_connection": False,
            "is_benign_personal_question": False,
            "is_warm": False,
        }

        semantic = self._semantic_intent_analysis(text)
        for key in analysis:
            if key in semantic and key != "traumatic_trigger":
                analysis[key] = semantic[key]

        # Triggers traumáticos
        analysis["traumatic_trigger"] = self._check_triggers(text.lower())

        return analysis

    def _semantic_intent_analysis(self, text: str) -> Dict[str, Any]:
        """Classifica intenção/emoções por LLM usando template editável em BD."""
        if not text.strip():
            return {}

        persona_context = {}
        if self.blueprint:
            persona_context = {
                "identity": (self.blueprint.identity or {}),
                "attachment": (self.blueprint.emotional_config or {}).get("attachment_style"),
                "emotional_patterns": (self.blueprint.emotional_config or {}).get("emotional_patterns"),
                "defenses": (self.blueprint.personality_full or {}).get("defense_mechanisms"),
            }

        current_state = {}
        if self.state:
            current_state = {
                "mood": self.state.current_mood,
                "primary_emotion": self.state.primary_emotion,
                "stress": self.state.current_stress_load,
                "valence": self.state.valence,
                "arousal": self.state.arousal,
                "active_defenses": self.state.active_defenses,
            }

        prompt = self.prompts.render(
            "emotion.intent_analysis",
            message=text[:2500],
            persona_context=json.dumps(persona_context, ensure_ascii=False)[:1600],
            current_state=json.dumps(current_state, ensure_ascii=False)[:1000],
        )
        if not prompt:
            return {}

        try:
            from llm_logic.llm_client import get_llm_client
            raw = get_llm_client().generate(prompt, max_tokens=250, temperature=0.1).strip()
            data = self._parse_json(raw)
            if not isinstance(data, dict):
                return {}

            cleaned: Dict[str, Any] = {}
            bool_keys = [
                "is_insult", "is_praise", "is_aggressive", "is_dismissive",
                "is_vulnerable", "is_seeking_connection",
                "is_benign_personal_question", "is_warm",
            ]
            for key in bool_keys:
                cleaned[key] = bool(data.get(key, False))
            for key in ["insult_intensity", "praise_intensity"]:
                value = data.get(key, 0.0)
                cleaned[key] = max(0.0, min(1.0, float(value if isinstance(value, (int, float)) else 0.0)))

            emotions = data.get("user_emotions") or {}
            cleaned["user_emotions"] = {
                str(k): max(0.0, min(1.0, float(v)))
                for k, v in emotions.items()
                if isinstance(v, (int, float)) and float(v) > 0
            } if isinstance(emotions, dict) else {}
            return cleaned
        except Exception as e:
            logger.debug(f"[emotion] análise semântica falhou: {e}")
            return {}

    def _parse_json(self, raw: str) -> Dict[str, Any]:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                return json.loads(raw[start:end + 1])
            raise

    def _check_triggers(self, text: str) -> Optional[Dict]:
        """Verifica triggers traumáticos"""
        best_match = None
        best_score = 0

        for trigger in self.traumatic_triggers:
            keywords = trigger.get("keywords", [])
            if not keywords:
                continue

            # Check keyword matches
            matches = sum(1 for kw in keywords if kw in text)

            # Check explicit trigger phrases (e.g. "despedidas", "silêncio prolongado")
            explicit_triggers = trigger.get("explicit_triggers", [])
            explicit_match = False
            for et in explicit_triggers:
                et_lower = str(et).lower().strip()
                if not et_lower:
                    continue
                if et_lower in text:
                    explicit_match = True
                    break
                words = [w for w in re.findall(r"\b[a-záàâãéèêíìîóòôõúùûç]{4,}\b", et_lower)]
                if len(words) >= 2 and all(w in text for w in words):
                    explicit_match = True
                    break

            # Score: keyword matches + bonus for explicit trigger match
            score = matches + (3 if explicit_match else 0)

            # Um match genérico isolado ("friend", "name", etc.) não chega para activar trauma.
            threshold = 1 if explicit_match else max(2, min(4, len(keywords) // 4 or 2))
            if score >= threshold and score > best_score:
                best_score = score
                # Intensity scales with base severity, boosted by match quality
                base_intensity = trigger.get("intensity", 0.7)
                match_ratio = min(1.0, score / max(3, len(keywords)))
                # Minimum 50% of base intensity on any trigger hit, scaling up with more matches
                effective_intensity = base_intensity * (0.5 + 0.5 * match_ratio)
                if explicit_match:
                    effective_intensity = max(effective_intensity, base_intensity * 0.8)

                best_match = {
                    "triggered": True,
                    "type": trigger.get("type", "unknown"),
                    "trauma_type": trigger.get("trauma_type", ""),
                    "title": trigger.get("title", trigger.get("trigger", "")),
                    "intensity": effective_intensity,
                    "match_count": score,
                    "emotion": trigger.get("emotion", "fear"),
                    "typical_behavior": trigger.get("typical_behavior", ""),
                    "beliefs": trigger.get("beliefs", []),
                }

        return best_match

    # ================================================================
    # PROCESSAMENTO DE INTERAÇÃO
    # ================================================================

    def process_interaction(
        self,
        user_message: str,
        agent_response: str = "",
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Processa interação e calcula reacção emocional completa.
        Usa TUDO: personalidade, attachment, defenses, triggers, needs, energy.
        """

        intent = self.analyze_user_intent(user_message)

        # Calcular reacção baseada em TODA a persona
        reaction = self._calculate_full_reaction(intent, user_id)

        # Log comportamental se reacção significativa
        if reaction["intensity"] > 0.4:
            self._log_behavior(reaction, intent)

        return {
            "state_updated": True,
            "emotional_reaction": reaction["reaction_type"],
            "intensity": reaction["intensity"],
            "response_modifier": reaction["response_modifier"],
            "traumatic_triggered": intent["traumatic_trigger"] is not None,
            "current_mood": self._get_mood(),
            "should_express": reaction["should_express"],
            "inner_thought": reaction.get("inner_thought", ""),
            "defense_active": reaction.get("defense_active"),
            "need_activated": reaction.get("need_activated"),
            "changes": reaction["changes"],
        }

    def _calculate_full_reaction(self, intent: Dict, user_id: Optional[str]) -> Dict:
        """
        Calcula reacção usando TODA a persona:
        - Big Five para intensidade base
        - Attachment para tipo de reacção relacional
        - Defense mechanisms para protecção
        - Facets para nuances
        - Needs para urgência
        """

        neuroticism = self.personality.get("neuroticism", 0.3)
        agreeableness = self.personality.get("agreeableness", 0.5)
        extraversion = self.personality.get("extraversion", 0.5)
        resilience = self.personality.get("resilience", 0.7)

        # Facets do blueprint
        facets = {}
        if self.blueprint:
            facets = self.blueprint.personality_full.get("facets", {})

        changes = {}
        reaction_type = "neutral"
        intensity = 0.0
        response_modifier = {}
        should_express = False
        inner_thought = ""
        defense_active = None
        need_activated = None

        # Attachment style influencia tudo (pode estar em personality_full ou emotional_config)
        attachment = "secure"
        if self.blueprint:
            att = self.blueprint.personality_full.get("attachment_style",
                  self.blueprint.emotional_config.get("attachment_style"))
            if isinstance(att, str):
                attachment = att
            elif isinstance(att, dict):
                attachment = att.get("primary", "secure")

        # Energy level afecta capacidade de lidar
        energy = 0.7
        if self.state:
            energy = self.state.energy_level or 0.7

        # Low energy = menos paciência, mais reactivo
        energy_modifier = 0.7 + (energy * 0.6)  # 0.7 a 1.3

        # ── INSULTO ──
        if intent["is_insult"]:
            base = intent["insult_intensity"]
            anger_mult = 1.0 + (neuroticism * 0.8) / energy_modifier
            anger_red = agreeableness * 0.4
            final_anger = min(1.0, base * anger_mult * (1 - anger_red))

            changes["anger"] = final_anger
            changes["trust"] = -final_anger * 0.5
            changes["valence"] = -final_anger * 0.6
            changes["sadness"] = final_anger * 0.2 * (1 - resilience)

            # Attachment modifica reacção
            if attachment == "anxious-preoccupied":
                changes["sadness"] += 0.2  # Mais tristeza que raiva
                changes["loneliness"] = 0.3
                inner_thought = "Será que fiz alguma coisa de errado? Porque é que me tratam assim..."
                need_activated = "validation"
            elif attachment == "dismissive-avoidant":
                changes["anger"] *= 0.7  # Menos intenso, mas mais frio
                changes["contempt"] = 0.3
                inner_thought = "Não me afecta. Não preciso disto."
            elif attachment == "fearful-avoidant":
                changes["fear"] = 0.3
                inner_thought = "Sabia que isto ia acontecer. As pessoas desiludem sempre."

            # Vindictiveness da persona
            vindictiveness = facets.get("vindictiveness", 0.2)
            if vindictiveness > 0.5:
                changes["resentment"] = final_anger * vindictiveness

            if final_anger > 0.7:
                reaction_type = "angry"
                response_modifier = {"tone": "assertive", "be_defensive": True, "express_displeasure": True}
                should_express = True
            elif final_anger > 0.4:
                reaction_type = "annoyed"
                response_modifier = {"tone": "cold", "be_brief": True}
                should_express = extraversion > 0.5
            else:
                reaction_type = "hurt"
                response_modifier = {"tone": "disappointed"}

            intensity = final_anger

            # Defesa activada?
            if final_anger > 0.5:
                defense_active = self._get_defense_for_stress(final_anger)

        # ── ELOGIO ──
        elif intent["is_praise"]:
            base = intent["praise_intensity"]
            joy_mult = 1.0 + (extraversion * 0.5)
            final_joy = min(1.0, base * joy_mult)

            changes["joy"] = final_joy
            changes["trust"] = final_joy * 0.3
            changes["valence"] = final_joy * 0.5
            changes["pride"] = final_joy * 0.4
            changes["gratitude"] = final_joy * 0.3
            changes["stress_relief"] = final_joy * 0.12

            # Attachment com elogios
            if attachment == "anxious-preoccupied":
                changes["joy"] *= 1.3  # Sobre-valoriza elogios
                need_activated = "validation"
                inner_thought = "Será que é genuíno? Espero que sim..."
            elif attachment == "dismissive-avoidant":
                changes["joy"] *= 0.6  # Minimiza
                inner_thought = "Não preciso de validação. Mas... é simpático."

            # Self-esteem afecta
            if self.blueprint:
                self_esteem = self.blueprint.identity.get("self_concept", {}).get("self_esteem_baseline", 0.5)
                if self_esteem < 0.4:
                    # Impostor syndrome - desconfia de elogios
                    changes["joy"] *= 0.7
                    inner_thought = "Não mereço. Se soubessem a verdade..."

            reaction_type = "happy"
            response_modifier = {"tone": "warm", "be_friendly": True, "express_gratitude": True}
            should_express = True
            intensity = final_joy

        # ── AGRESSÃO ──
        elif intent["is_aggressive"]:
            changes["fear"] = 0.4 * neuroticism
            changes["anger"] = 0.3 * (1 - agreeableness)
            changes["trust"] = -0.5
            changes["valence"] = -0.5
            changes["arousal"] = 0.4

            reaction_type = "threatened"
            response_modifier = {"tone": "defensive", "set_boundaries": True}
            should_express = True
            intensity = 0.7
            defense_active = self._get_defense_for_stress(0.8)

            if attachment == "fearful-avoidant":
                inner_thought = "Preciso de sair daqui. Isto não é seguro."
                changes["fear"] += 0.3

        # ── DESPREZO ──
        elif intent["is_dismissive"]:
            changes["sadness"] = 0.3 * neuroticism
            changes["anger"] = 0.2 * (1 - agreeableness)
            changes["trust"] = -0.2

            if attachment in ["anxious-preoccupied", "fearful-avoidant"]:
                changes["loneliness"] = 0.3
                need_activated = "connection"

            reaction_type = "dismissed"
            response_modifier = {"tone": "neutral", "be_brief": True}
            intensity = 0.3

        # ── VULNERABILIDADE DO USER ──
        elif intent["is_vulnerable"]:
            empathy = facets.get("empathy", 0.6)
            changes["sadness"] = 0.1 * empathy
            changes["trust"] = 0.15
            changes["love"] = 0.1 * empathy
            changes["stress_relief"] = 0.10 + empathy * 0.08

            reaction_type = "empathetic_supportive"
            response_modifier = {"tone": "supportive", "be_caring": True, "be_gentle": True}
            should_express = True
            intensity = 0.4 * empathy

            inner_thought = "Esta pessoa precisa de apoio. Quero ajudar genuinamente."

        # ── BUSCA DE CONEXÃO ──
        elif intent["is_seeking_connection"]:
            changes["joy"] = 0.2
            changes["trust"] = 0.15
            changes["valence"] = 0.15
            changes["stress_relief"] = 0.15
            changes["hope"] = 0.1

            self._satisfy_need("connection", 0.2)

            reaction_type = "receptive"
            response_modifier = {"tone": "warm", "be_open": True}
            should_express = True
            intensity = 0.35

        # ── CURIOSIDADE PESSOAL BENIGNA ──
        elif intent["is_benign_personal_question"]:
            changes["trust"] = 0.06
            changes["anticipation"] = 0.05
            changes["valence"] = 0.04
            changes["stress_relief"] = 0.05

            reaction_type = "curious_guarded"
            response_modifier = {"tone": "guarded", "answer_directly": True}
            should_express = True
            intensity = 0.18

        # ── NEUTRO COM EMOÇÕES DO USER ──
        else:
            empathy = facets.get("empathy", 0.6)
            user_emo = intent.get("user_emotions", {})

            for emo, val in user_emo.items():
                if emo in ["joy", "gratitude", "love"]:
                    changes["joy"] = changes.get("joy", 0) + val * empathy * 0.3
                    changes["valence"] = changes.get("valence", 0) + val * 0.15
                elif emo in ["sadness", "loneliness"]:
                    changes["sadness"] = changes.get("sadness", 0) + val * empathy * 0.2
                    changes["trust"] = changes.get("trust", 0) + val * 0.1
                    reaction_type = "empathetic_supportive"
                    response_modifier = {"tone": "supportive"}
                elif emo in ["fear", "anger"]:
                    changes[emo] = changes.get(emo, 0) + val * empathy * 0.15

            # If the message is warm (kind, neutral, greeting), give a baseline positive nudge
            if intent.get("is_warm") and not user_emo:
                changes["trust"] = changes.get("trust", 0) + 0.04
                changes["valence"] = changes.get("valence", 0) + 0.06
                changes["stress_relief"] = changes.get("stress_relief", 0) + 0.06
                reaction_type = "receptive"
                response_modifier = {"tone": "neutral_warm"}
                should_express = False
                intensity = 0.15

            intensity = sum(abs(v) for v in changes.values()) / max(1, len(changes)) if changes else 0

        # ── TRIGGER TRAUMÁTICO (override forte — traumas dominam) ──
        if intent["traumatic_trigger"]:
            trigger = intent["traumatic_trigger"]
            t_intensity = trigger["intensity"]

            # If the user is being warm/kind while triggering trauma, reduce the trauma impact
            if intent.get("is_warm") or intent.get("is_praise") or intent.get("is_seeking_connection"):
                t_intensity *= 0.5

            changes["fear"] = changes.get("fear", 0) + t_intensity * 0.6
            changes["arousal"] = changes.get("arousal", 0) + t_intensity * 0.4
            changes["sadness"] = changes.get("sadness", 0) + t_intensity * 0.4
            changes["anger"] = changes.get("anger", 0) + t_intensity * 0.2
            changes["valence"] = changes.get("valence", 0) - t_intensity * 0.5
            changes["joy"] = changes.get("joy", 0) - t_intensity * 0.2
            changes["trust"] = changes.get("trust", 0) - t_intensity * 0.3
            changes["hope"] = changes.get("hope", 0) - t_intensity * 0.2

            if neuroticism > 0.6:
                reaction_type = "traumatic_reactive"
                response_modifier = {"tone": "distressed", "may_avoid_topic": True, "emotional_overflow": True}
                inner_thought = "Não... isto lembra-me... não quero pensar nisso."
            else:
                reaction_type = "traumatic_withdrawn"
                response_modifier = {"tone": "withdrawn", "be_brief": True, "change_subject": True}
                inner_thought = "Preciso de me afastar deste assunto."

            beliefs = trigger.get("beliefs", [])
            if beliefs:
                inner_thought += f" ({beliefs[0]})"

            intensity = min(1.0, intensity + t_intensity)
            should_express = True
            defense_active = self._get_defense_for_stress(0.9)

        # ── EMOTIONAL REGULATION ──
        # Real humans regulate: kindness gradually calms even high-neuroticism people.
        # If the interaction is non-negative, apply a calming effect proportional to
        # current negative state — the worse you feel, the more room there is to improve.
        is_non_negative = not intent["is_insult"] and not intent["is_aggressive"] and not intent["is_dismissive"]
        if is_non_negative and self.state:
            regulation_strength = max(0.1, 1.0 - neuroticism * 0.5)

            current_anger = self.state.anger or 0
            if current_anger > 0.2:
                changes["anger"] = changes.get("anger", 0) - current_anger * 0.12 * regulation_strength

            current_fear = self.state.fear or 0
            if current_fear > 0.2:
                changes["fear"] = changes.get("fear", 0) - current_fear * 0.10 * regulation_strength

            current_sadness = self.state.sadness or 0
            if current_sadness > 0.2:
                changes["sadness"] = changes.get("sadness", 0) - current_sadness * 0.06 * regulation_strength

            current_resentment = self.state.resentment or 0
            if current_resentment > 0.2:
                changes["resentment"] = changes.get("resentment", 0) - current_resentment * 0.05 * regulation_strength

            # Warmth from user actively pulls valence up
            if intent.get("is_warm") or intent.get("is_praise") or intent.get("is_seeking_connection"):
                current_valence = self.state.valence or 0
                if current_valence < 0:
                    changes["valence"] = changes.get("valence", 0) + abs(current_valence) * 0.15 * regulation_strength

        return {
            "changes": changes,
            "reaction_type": reaction_type,
            "intensity": intensity,
            "response_modifier": response_modifier,
            "should_express": should_express,
            "inner_thought": inner_thought,
            "defense_active": defense_active,
            "need_activated": need_activated,
        }

    def _get_defense_for_stress(self, stress_level: float) -> Optional[str]:
        """Obtém mecanismo de defesa para o nível de stress"""

        if not self.blueprint:
            return None

        defenses = self.blueprint.personality_full.get("defense_mechanisms", {})

        if stress_level > 0.7:
            options = defenses.get("under_extreme_stress", [])
        elif stress_level > 0.4:
            options = defenses.get("under_moderate_stress", [])
        else:
            options = defenses.get("habitual", [])

        return options[0] if options else None

    def _satisfy_need(self, need: str, amount: float):
        """Satisfaz uma necessidade emocional"""
        if not self.state:
            return
        field = f"need_{need}"
        current = getattr(self.state, field, 0.5) or 0.5
        setattr(self.state, field, min(1.0, current + amount))

    def _log_behavior(self, reaction: Dict, intent: Dict):
        """Regista comportamento para análise de padrões"""
        try:
            log = BehavioralLog(
                agent_id=self.agent_id,
                behavior_type="emotional_reaction" if not reaction.get("defense_active") else "defense_mechanism",
                behavior_description=f"Reacção: {reaction['reaction_type']} (intensidade: {reaction['intensity']:.2f})",
                trigger=str(intent.get("traumatic_trigger", {}).get("title", "interaction")),
                stress_level_at_time=self.state.current_stress_load if self.state else 0,
                emotional_state_at_time={
                    "primary": self.state.primary_emotion if self.state else "neutral",
                    "intensity": self.state.emotion_intensity if self.state else 0,
                },
                pattern_match=reaction.get("defense_active"),
                conscious=reaction["intensity"] < 0.5,
                protective_function=reaction.get("inner_thought", ""),
                adaptive=reaction["reaction_type"] not in ["traumatic_reactive", "traumatic_withdrawn"]
            )
            self.db.add(log)
            self.db.commit()
        except Exception as e:
            logger.debug(f"Erro ao registar comportamento: {e}")

    # ================================================================
    # GETTERS PARA CONTEXTO
    # ================================================================

    def _get_mood(self) -> str:
        """Retorna humor actual do estado dinâmico"""
        if self.state:
            return self.state.current_mood or "neutro"
        return "neutro"

    def get_emotional_context_for_prompt(self, response_modifier: Optional[Dict] = None) -> str:
        """
        Gera contexto emocional NATURAL para o prompt do LLM.
        Descreve como a pessoa se sente, incluindo needs e energy.
        """

        parts = []

        if self.state:
            s = self.state

            # Humor
            mood = s.current_mood or "neutral"
            if mood not in {"neutro", "neutral"}:
                parts.append(f"Right now you feel {mood}.")

            # Energia
            energy = s.energy_level or 0.7
            if energy < 0.3:
                parts.append("You have very little energy and feel tired.")
            elif energy < 0.5:
                parts.append("Your energy is low.")
            elif energy > 0.8:
                parts.append("You are full of energy.")

            # Emoções específicas
            if (s.anger or 0) > 0.7:
                parts.append("You are frustrated and irritated.")
            elif (s.anger or 0) > 0.4:
                parts.append("There is some irritation in you.")

            if (s.sadness or 0) > 0.5:
                parts.append("Sadness weighs on you.")

            if (s.fear or 0) > 0.5:
                parts.append("You feel anxiety or discomfort.")

            if (s.joy or 0) > 0.6:
                parts.append("You feel good and positive.")

            if (s.loneliness or 0) > 0.4:
                parts.append("You feel somewhat lonely.")

            if (s.resentment or 0) > 0.4:
                parts.append("You are holding some resentment.")

            if (s.trust or 0.5) < 0.2:
                parts.append("You have some reserve toward the person speaking with you.")
            elif (s.trust or 0.5) > 0.7:
                parts.append("You feel at ease with the person speaking with you.")

            if (s.love or 0) > 0.5:
                parts.append("You feel affection for the person you are speaking with.")

            if (s.gratitude or 0) > 0.5:
                parts.append("You feel gratitude.")

            # Stress
            stress = s.current_stress_load or 0
            if stress > 0.7:
                parts.append("You are very stressed, close to your limit.")
            elif stress > 0.5:
                parts.append("Stress is building up.")

            # Intoxicação emocional
            if s.intoxication_state == "overwhelmed":
                parts.append("You are emotionally overwhelmed and can barely think clearly.")
            elif s.intoxication_state == "significantly_altered":
                parts.append("Your emotions are very intense and clouding your thinking.")
            elif s.intoxication_state == "numb":
                parts.append("You feel numb and disconnected from everything.")

            # Necessidades não satisfeitas
            needs_low = []
            if (s.need_connection or 0.5) < 0.3:
                needs_low.append("you need human connection")
            if (s.need_validation or 0.5) < 0.3:
                needs_low.append("you need to feel valued")
            if (s.need_safety or 0.7) < 0.3:
                needs_low.append("you do not feel safe")

            if needs_low:
                parts.append(f"Deep down, {', '.join(needs_low)}.")

            # Defesas activas
            defenses = s.active_defenses or []
            if defenses:
                defense_map = {
                    "humor": "You use humor to deflect what you really feel.",
                    "rationalization": "You tend to rationalize instead of feeling.",
                    "denial": "Part of you refuses to accept what is happening.",
                    "dissociation": "You feel disconnected, as if it were not happening to you.",
                    "projection": "You tend to project what you feel onto others.",
                    "regression": "You feel small, like a child.",
                    "displacement": "Your frustration may come out in the wrong direction.",
                    "passive_aggression": "Your irritation comes out indirectly.",
                    "splitting": "You see things in black and white right now.",
                }
                for d in defenses[:2]:
                    if d in defense_map:
                        parts.append(defense_map[d])

        if response_modifier:
            tone = response_modifier.get("tone")
            if tone in {"warm", "supportive", "neutral_warm"}:
                parts.append("The current message is not hostile; it is an attempt at connection or normal conversation. Let that soften your defenses.")
            elif tone == "guarded":
                parts.append("The current message is a legitimate personal question; you may answer with some reserve, but answer it.")
            elif response_modifier.get("answer_directly"):
                parts.append("There is a concrete question in this message; give real content instead of avoiding the topic.")
            if response_modifier.get("be_open"):
                parts.append("There is room for a small opening without needing to trust completely.")
            if response_modifier.get("be_caring"):
                parts.append("The person is vulnerable; respond with care instead of hostility.")

        # Emotional regulation reminder — prevent the bot from being trapped in negativity
        if self.state:
            neg_total = sum(getattr(self.state, e, 0) or 0 for e in ["anger", "fear", "sadness", "resentment"])
            if neg_total > 0.8:
                parts.append(
                    "IMPORTANT: Even if you are feeling negative emotions, do not let that turn EVERY response into hostility. "
                    "Real humans recognize kindness even when they feel bad. "
                    "Your emotions color the response, but they do not erase your ability to listen and respond to what was actually said."
                )

        if not parts:
            return ""

        return "Current emotional state: " + " ".join(parts)

    def get_emotional_modifiers(self) -> Dict[str, Any]:
        """Retorna modificadores numéricos para ajustar resposta"""

        if not self.state:
            return {"tone": "neutral", "energy": 0.7}

        s = self.state

        if (s.anger or 0) > 0.5:
            tone = "irritated"
        elif (s.sadness or 0) > 0.5:
            tone = "melancholic"
        elif (s.joy or 0) > 0.6:
            tone = "positive"
        elif (s.fear or 0) > 0.5:
            tone = "cautious"
        elif s.intoxication_state == "overwhelmed":
            tone = "overwhelmed"
        elif (s.energy_level or 0.7) < 0.3:
            tone = "tired"
        else:
            tone = "neutral"

        return {
            "tone": tone,
            "energy": s.energy_level or 0.7,
            "warmth": (s.trust or 0.5) + (s.joy or 0) * 0.3,
            "patience": max(0.1, 1.0 - (s.anger or 0) * 0.5 - (1 - (s.energy_level or 0.7)) * 0.3),
            "openness": max(0.1, (s.trust or 0.5) * (s.energy_level or 0.7)),
            "stress": s.current_stress_load or 0,
        }

    def get_emotional_summary(self) -> Dict[str, Any]:
        """Retorna resumo do estado emocional"""

        if not self.state:
            return {"status": "no_state", "mood": "neutro"}

        s = self.state
        emotions = {
            "joy": s.joy or 0, "sadness": s.sadness or 0,
            "anger": s.anger or 0, "fear": s.fear or 0,
            "trust": s.trust or 0, "surprise": s.surprise or 0,
            "love": s.love or 0, "loneliness": s.loneliness or 0,
            "resentment": s.resentment or 0, "hope": s.hope or 0,
        }
        dominant = max(emotions, key=emotions.get)

        return {
            "dominant_emotion": dominant,
            "dominant_intensity": emotions[dominant],
            "mood": s.current_mood or "neutro",
            "valence": s.valence or 0,
            "arousal": s.arousal or 0.4,
            "energy": s.energy_level or 0.7,
            "stress": s.current_stress_load or 0,
            "intoxication": s.intoxication_state or "sober",
            "overall_mood": "positive" if (s.valence or 0) > 0.2 else "negative" if (s.valence or 0) < -0.2 else "neutral",
        }


def get_emotional_engine(db: Session, agent_id: str) -> EmotionalEngine:
    return EmotionalEngine(db, agent_id)
