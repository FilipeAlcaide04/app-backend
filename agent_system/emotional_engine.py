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
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import math
import re
import logging

logger = logging.getLogger(__name__)


class EmotionalEngine:
    """
    Sistema emocional que reage baseado na PERSONA COMPLETA.
    Não apenas Big Five - usa attachment, trauma, defenses, needs, tudo.
    """

    # === DETECÇÃO DE INTENÇÃO ===

    INSULT_PATTERNS = [
        r"\b(idiota|estúpido|burro|imbecil|parvo|palhaço|lixo|nojo|porcaria)\b",
        r"\b(cala.te|cala.a.boca|caluda|vai.te|desaparece)\b",
        r"\b(inútil|incompetente|fraco|patético|ridículo|nojento)\b",
        r"\b(odei[oa]|detest[oa]|não.presta|és.um|tu.és.um?)\b",
        r"\b(fod[ae]|crl|caralho|merda|puta|cona|pila)\b",
        r"\b(vai.à.merda|vai.para|vai.te.foder)\b",
        r"\b(não.serves|não.vales|és.péssimo|és.horrível)\b",
        r"\b(que.lixo|que.nojo|és.uma.fraude)\b",
    ]

    PRAISE_PATTERNS = [
        r"\b(obrigad[oa]|muito.obrigad[oa]|agradeço)\b",
        r"\b(incrível|fantástico|excelente|maravilhos[oa]|genial)\b",
        r"\b(gosto.de.ti|adoro.te|amo.te|és.fix[eo]|és.o.máximo)\b",
        r"\b(muito.bem|boa|bom.trabalho|perfeito|impecável)\b",
        r"\b(inteligente|esperto|brilhante|impressionante)\b",
    ]

    AGGRESSIVE_PATTERNS = [
        r"\b(vou.te|vou-te|ameaç[oa]|mat[oa]r|destruir)\b",
        r"\b(acabar.contigo|eliminar|apagar.te)\b",
    ]

    DISMISSIVE_PATTERNS = [
        r"\b(cala|deixa|para|chega|basta|chato)\b",
        r"\b(não.interessa|tanto.faz|que.seja|whatever)\b",
    ]

    EMOTION_KEYWORDS = {
        "joy": ["feliz", "alegre", "contente", "ótimo", "maravilhoso", "incrível", "adoro", "amo", "fantástico", "fixe", "topo"],
        "sadness": ["triste", "chateado", "deprimido", "mal", "péssimo", "horrível", "chorar", "lágrimas", "dor", "sofro"],
        "anger": ["raiva", "furioso", "irritado", "zangado", "odeio", "detesto", "merda", "frustrado", "farto"],
        "fear": ["medo", "ansioso", "preocupado", "nervoso", "assustado", "terror", "pânico", "receio"],
        "surprise": ["surpreso", "chocado", "incrível", "não acredito", "sério", "a sério", "wow", "uau"],
        "trust": ["confio", "acredito", "seguro", "confiança", "verdade", "honesto", "sincero"],
        "anticipation": ["ansioso", "expectativa", "espero", "mal posso esperar", "empolgado", "curioso"],
        "gratitude": ["obrigado", "agradeço", "grato", "gratidão", "valeu"],
        "disgust": ["nojo", "repugnante", "asqueroso", "insuportável"],
        "loneliness": ["sozinho", "solitário", "ninguém", "abandonado", "isolado"],
        "love": ["amo", "adoro", "amor", "carinho", "querido", "especial"],
    }

    def __init__(self, db: Session, agent_id: str):
        self.db = db
        self.agent_id = agent_id
        self.blueprint: Optional[PersonaBlueprint] = None
        self.state: Optional[DynamicState] = None
        self.personality: Dict[str, float] = {}
        self.traumatic_triggers: List[Dict] = []

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

        logger.info(f"Carregados {len(self.traumatic_triggers)} triggers para {self.agent_id}")

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

        text_lower = text.lower()
        analysis = {
            "is_insult": False, "is_praise": False,
            "is_aggressive": False, "is_dismissive": False,
            "insult_intensity": 0.0, "praise_intensity": 0.0,
            "traumatic_trigger": None, "user_emotions": {},
            "is_vulnerable": False, "is_seeking_connection": False,
        }

        # Insultos
        for p in self.INSULT_PATTERNS:
            if re.search(p, text_lower):
                analysis["is_insult"] = True
                analysis["insult_intensity"] += 0.3
        analysis["insult_intensity"] = min(1.0, analysis["insult_intensity"])

        # Elogios
        for p in self.PRAISE_PATTERNS:
            if re.search(p, text_lower):
                analysis["is_praise"] = True
                analysis["praise_intensity"] += 0.25
        analysis["praise_intensity"] = min(1.0, analysis["praise_intensity"])

        # Agressão
        for p in self.AGGRESSIVE_PATTERNS:
            if re.search(p, text_lower):
                analysis["is_aggressive"] = True

        # Desprezo
        for p in self.DISMISSIVE_PATTERNS:
            if re.search(p, text_lower):
                analysis["is_dismissive"] = True

        # Emoções do utilizador
        analysis["user_emotions"] = self._detect_user_emotions(text_lower)

        # Vulnerabilidade (user a partilhar algo pessoal/difícil)
        vuln_patterns = [
            r"(preciso de ajuda|não sei o que fazer|estou perdido|tenho medo)",
            r"(sinto.me sozinho|ninguém me entende|estou triste|quero desistir)",
        ]
        for p in vuln_patterns:
            if re.search(p, text_lower):
                analysis["is_vulnerable"] = True

        # Busca de conexão
        conn_patterns = [
            r"(como estás|tudo bem|conta.me|fala.me|o que achas)",
            r"(quero conversar|precisava de falar|posso desabafar)",
        ]
        for p in conn_patterns:
            if re.search(p, text_lower):
                analysis["is_seeking_connection"] = True

        # Triggers traumáticos
        analysis["traumatic_trigger"] = self._check_triggers(text_lower)

        return analysis

    def _detect_user_emotions(self, text: str) -> Dict[str, float]:
        """Detecta emoções no texto"""
        detected = {}
        for emotion, keywords in self.EMOTION_KEYWORDS.items():
            score = sum(0.3 for kw in keywords if kw in text)
            if score > 0:
                detected[emotion] = min(1.0, score)
        return detected

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
            explicit_match = any(
                et.lower() in text or any(w in text for w in et.lower().split() if len(w) >= 3)
                for et in explicit_triggers
            )

            # Score: keyword matches + bonus for explicit trigger match
            score = matches + (3 if explicit_match else 0)

            # Threshold: 1 keyword match OR explicit trigger hit
            if score >= 1 and score > best_score:
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

            reaction_type = "empathetic_supportive"
            response_modifier = {"tone": "supportive", "be_caring": True, "be_gentle": True}
            should_express = True
            intensity = 0.4 * empathy

            inner_thought = "Esta pessoa precisa de apoio. Quero ajudar genuinamente."

        # ── BUSCA DE CONEXÃO ──
        elif intent["is_seeking_connection"]:
            changes["joy"] = 0.15
            changes["trust"] = 0.1
            changes["valence"] = 0.1

            self._satisfy_need("connection", 0.15)

            reaction_type = "receptive"
            response_modifier = {"tone": "warm", "be_open": True}
            should_express = True
            intensity = 0.3

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

            intensity = sum(abs(v) for v in changes.values()) / max(1, len(changes)) if changes else 0

        # ── TRIGGER TRAUMÁTICO (override forte — traumas dominam) ──
        if intent["traumatic_trigger"]:
            trigger = intent["traumatic_trigger"]
            t_intensity = trigger["intensity"]

            # Trauma DOMINA o estado emocional — aumenta negativos, reduz positivos
            changes["fear"] = changes.get("fear", 0) + t_intensity * 0.8
            changes["arousal"] = changes.get("arousal", 0) + t_intensity * 0.5
            changes["sadness"] = changes.get("sadness", 0) + t_intensity * 0.5
            changes["anger"] = changes.get("anger", 0) + t_intensity * 0.3
            changes["valence"] = changes.get("valence", 0) - t_intensity * 0.8
            # Reduzir emoções positivas — trauma apaga a tranquilidade
            changes["joy"] = changes.get("joy", 0) - t_intensity * 0.4
            changes["trust"] = changes.get("trust", 0) - t_intensity * 0.5
            changes["hope"] = changes.get("hope", 0) - t_intensity * 0.3

            if neuroticism > 0.6:
                reaction_type = "traumatic_reactive"
                response_modifier = {"tone": "distressed", "may_avoid_topic": True, "emotional_overflow": True}
                inner_thought = "Não... isto lembra-me... não quero pensar nisso."
            else:
                reaction_type = "traumatic_withdrawn"
                response_modifier = {"tone": "withdrawn", "be_brief": True, "change_subject": True}
                inner_thought = "Preciso de me afastar deste assunto."

            # Se tem beliefs associadas ao trauma, incluir no inner thought
            beliefs = trigger.get("beliefs", [])
            if beliefs:
                inner_thought += f" ({beliefs[0]})"

            intensity = min(1.0, intensity + t_intensity)
            should_express = True
            defense_active = self._get_defense_for_stress(0.9)

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
            mood = s.current_mood or "neutro"
            if mood != "neutro":
                parts.append(f"Neste momento sentes-te {mood}.")

            # Energia
            energy = s.energy_level or 0.7
            if energy < 0.3:
                parts.append("Estás com pouca energia, cansado.")
            elif energy < 0.5:
                parts.append("A tua energia está em baixo.")
            elif energy > 0.8:
                parts.append("Estás cheio de energia.")

            # Emoções específicas
            if (s.anger or 0) > 0.6:
                parts.append("Estás frustrado e irritado.")
            elif (s.anger or 0) > 0.3:
                parts.append("Há alguma irritação em ti.")

            if (s.sadness or 0) > 0.5:
                parts.append("Uma tristeza pesa-te.")

            if (s.fear or 0) > 0.5:
                parts.append("Sentes ansiedade ou desconforto.")

            if (s.joy or 0) > 0.6:
                parts.append("Sentes-te bem, positivo.")

            if (s.loneliness or 0) > 0.4:
                parts.append("Sentes-te um pouco solitário.")

            if (s.resentment or 0) > 0.4:
                parts.append("Guardas algum ressentimento.")

            if (s.trust or 0.5) < 0.3:
                parts.append("Não confias muito nesta pessoa.")
            elif (s.trust or 0.5) > 0.7:
                parts.append("Sentes-te à vontade com esta pessoa.")

            if (s.love or 0) > 0.5:
                parts.append("Sentes carinho por quem falas.")

            if (s.gratitude or 0) > 0.5:
                parts.append("Sentes gratidão.")

            # Stress
            stress = s.current_stress_load or 0
            if stress > 0.7:
                parts.append("Estás muito stressado, perto do limite.")
            elif stress > 0.5:
                parts.append("O stress está a acumular-se.")

            # Intoxicação emocional
            if s.intoxication_state == "overwhelmed":
                parts.append("Estás emocionalmente sobrecarregado, mal consegues pensar com clareza.")
            elif s.intoxication_state == "significantly_altered":
                parts.append("As tuas emoções estão muito intensas, a nublar o teu pensamento.")
            elif s.intoxication_state == "numb":
                parts.append("Sentes-te anestesiado, desligado de tudo.")

            # Necessidades não satisfeitas
            needs_low = []
            if (s.need_connection or 0.5) < 0.3:
                needs_low.append("precisas de conexão humana")
            if (s.need_validation or 0.5) < 0.3:
                needs_low.append("precisas de sentir que vales")
            if (s.need_safety or 0.7) < 0.3:
                needs_low.append("não te sentes seguro")

            if needs_low:
                parts.append(f"No fundo, {', '.join(needs_low)}.")

            # Defesas activas
            defenses = s.active_defenses or []
            if defenses:
                defense_map = {
                    "humor": "Usas humor para desviar do que realmente sentes.",
                    "rationalization": "Tendes a racionalizar em vez de sentir.",
                    "denial": "Parte de ti recusa-se a aceitar o que está a acontecer.",
                    "dissociation": "Sentes-te desligado, como se não fosse contigo.",
                    "projection": "Tens tendência a projectar nos outros o que sentes.",
                    "regression": "Sentes-te pequeno, como uma criança.",
                    "displacement": "A tua frustração pode sair direccionada ao sítio errado.",
                    "passive_aggression": "A tua irritação sai de formas indirectas.",
                    "splitting": "Vês as coisas a preto e branco agora.",
                }
                for d in defenses[:2]:
                    if d in defense_map:
                        parts.append(defense_map[d])

        if not parts:
            return ""

        return "Estado emocional actual: " + " ".join(parts)

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
