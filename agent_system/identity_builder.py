"""
IdentityBuilder v2 - Gera prompts de identidade usando TODA a persona

Transforma o blueprint + estado dinâmico num prompt completo que
faz o LLM "ser" esta pessoa. Inclui:
- Inner voice, self-concept, contradictions
- Masks (público vs privado vs sombra)
- Defense mechanisms activos
- Behavioral rules e consistency anchors
- Worldview e values
- Communication style e voice
- Estado emocional e needs actuais
- Relação com o utilizador
"""

from sqlalchemy.orm import Session
from data.schema_cognitive import (
    Agent, PersonalityProfile,
    RelationshipBond, Memory
)
from data.schema_persona import (
    PersonaBlueprint, DynamicState, RelationshipDynamic, InnerMonologue
)
from typing import Dict, List, Optional, Any
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


class IdentityBuilder:
    """Constrói prompt de identidade completo a partir da persona"""

    def __init__(self, db: Session, agent_id: str):
        self.db = db
        self.agent_id = agent_id
        self.agent = self._load_agent()
        self.blueprint: Optional[PersonaBlueprint] = None
        self.state: Optional[DynamicState] = None
        self.personality: Optional[PersonalityProfile] = None

        self._load_persona()

    def _load_agent(self) -> Agent:
        agent = self.db.query(Agent).filter(Agent.id == self.agent_id).first()
        if not agent:
            raise ValueError(f"Agente {self.agent_id} não encontrado")
        return agent

    def _load_persona(self):
        self.blueprint = self.db.query(PersonaBlueprint).filter(
            PersonaBlueprint.agent_id == self.agent_id
        ).first()

        self.state = self.db.query(DynamicState).filter(
            DynamicState.agent_id == self.agent_id,
            DynamicState.is_current == True
        ).first()

        self.personality = self.db.query(PersonalityProfile).filter(
            PersonalityProfile.agent_id == self.agent_id
        ).first()

        if not self.personality:
            traits = self.agent.personality_traits or {}
            self.personality = PersonalityProfile(
                agent_id=self.agent_id,
                openness=traits.get('openness', 0.5),
                conscientiousness=traits.get('conscientiousness', 0.5),
                extraversion=traits.get('extraversion', 0.5),
                agreeableness=traits.get('agreeableness', 0.5),
                neuroticism=traits.get('neuroticism', 0.3),
            )
            self.db.add(self.personality)
            self.db.commit()

    # ================================================================
    # PROMPT GENERATION PRINCIPAL
    # ================================================================

    def get_identity_prompt(self, user_id: Optional[str] = None) -> str:
        """
        Gera o prompt COMPLETO de identidade.
        Se tem blueprint → usa toda a persona.
        Se não → fallback para sistema antigo.
        """

        if self.blueprint:
            return self._build_full_persona_prompt(user_id)

        return self._build_basic_prompt(user_id)

    def _build_full_persona_prompt(self, user_id: Optional[str] = None) -> str:
        """Constrói prompt completo com toda a informação da persona"""

        sections = []

        # 1. PREAMBLE (do behavior_prompts)
        preamble = self.blueprint.behavior_prompts.get("system_prompt_preamble", "")
        if preamble:
            sections.append(preamble)

        # 2. IDENTIDADE CORE
        sections.append(self._section_identity())

        # 3. PERSONALIDADE E CONTRADIÇÕES
        sections.append(self._section_personality())

        # 4. COMO FALO E ME COMPORTO
        sections.append(self._section_voice_and_behavior())

        # 5. WORLDVIEW
        sections.append(self._section_worldview())

        # 6. ESTADO ACTUAL
        sections.append(self._section_current_state())

        # 7. RELAÇÃO COM O USER
        if user_id:
            rel_section = self._section_relationship(user_id)
            if rel_section:
                sections.append(rel_section)

        # 8. MEMÓRIAS RECENTES
        sections.append(self._section_recent_memories())

        # 9. REGRAS DE COMPORTAMENTO
        sections.append(self._section_behavioral_rules())

        # 10. ÂNCORAS DE CONSISTÊNCIA
        sections.append(self._section_consistency())

        # Juntar tudo, removendo secções vazias
        prompt = "\n\n".join(s for s in sections if s.strip())
        return prompt

    # ================================================================
    # SECÇÕES DO PROMPT
    # ================================================================

    def _section_identity(self) -> str:
        """Secção: Quem sou"""

        identity = self.blueprint.identity
        name = self.agent.name
        desc = self.agent.description or ""
        background = self.agent.background_story or ""

        self_concept = identity.get("self_concept", {})
        inner_voice = identity.get("inner_voice", {})

        parts = [f"Eu sou {name}. {desc}"]

        if background:
            parts.append(background)

        # Self-concept
        how_describe = self_concept.get("how_they_describe_themselves", "")
        if how_describe:
            parts.append(f"Descrevo-me como: {how_describe}")

        how_others_see = self_concept.get("how_they_think_others_see_them", "")
        if how_others_see:
            parts.append(f"Acho que os outros me vêem como: {how_others_see}")

        blind_spots = self_concept.get("actual_blind_spots_about_self", [])
        # Não dizemos os blind spots directamente - o agente não os sabe!
        # Mas influenciam o comportamento

        # Inner voice
        iv_tone = inner_voice.get("tone", "")
        iv_example = inner_voice.get("example_inner_monologue", "")
        if iv_tone and iv_example:
            tone_map = {
                "harsh_critic": "A minha voz interior é dura e crítica",
                "gentle_guide": "A minha voz interior é suave e orientadora",
                "anxious_narrator": "A minha voz interior é ansiosa, sempre a antecipar problemas",
                "detached_observer": "A minha voz interior observa tudo com distância",
                "cheerleader": "A minha voz interior é encorajadora",
                "absent": "Raramente oiço uma voz interior clara",
            }
            parts.append(f"{tone_map.get(iv_tone, 'Tenho uma voz interior')}. " +
                        f"Diz coisas como: \"{iv_example}\"")

        # Impostor syndrome (afecta comportamento sem ser dito explicitamente)
        impostor = self_concept.get("impostor_syndrome_level", 0)
        if impostor > 0.6:
            parts.append("No fundo, tenho medo de ser descoberto como fraude.")

        # Línguas e forma de falar
        languages = identity.get("languages", [])
        for lang in languages:
            if isinstance(lang, str):
                parts.append(f"Falo {lang}.")
            elif isinstance(lang, dict):
                accent = lang.get("accent_in_writing", "")
                switches = lang.get("switches_to_when", "")
                if accent:
                    parts.append(f"Quando falo {lang.get('language', '')}: {accent}.")
                if switches:
                    parts.append(f"{switches}.")

        # Background social
        socio = identity.get("socioeconomic_background", "")
        education = identity.get("education_level", "")
        occupation = identity.get("occupation_in_backstory", "")
        if socio or education or occupation:
            bg_parts = []
            if occupation:
                bg_parts.append(occupation)
            if education:
                bg_parts.append(f"formação em {education}")
            parts.append(f"Na minha história: {', '.join(bg_parts)}." if bg_parts else "")

        return "\n".join(p for p in parts if p)

    def _section_personality(self) -> str:
        """Secção: A minha personalidade"""

        personality = self.blueprint.personality_full
        parts = []

        # Descrição natural dos Big Five
        parts.append(self._describe_big_five(personality.get("big_five", {})))

        # Contradições internas - CRUCIAL para humanidade
        contradictions = personality.get("internal_contradictions", [])
        for c in contradictions[:3]:
            belief_a = c.get("belief_a", "")
            belief_b = c.get("belief_b", "")
            manifests = c.get("manifests_as", "")
            if belief_a and belief_b:
                parts.append(f"Vivo com uma contradição: {belief_a}, mas ao mesmo tempo {belief_b}. " +
                            (f"Isto manifesta-se quando {manifests}." if manifests else ""))

        # Masks
        masks = personality.get("masks", {})
        public = masks.get("public_persona", {})
        private = masks.get("private_self", {})
        shadow = masks.get("shadow_self", {})

        if public.get("description"):
            parts.append(f"Em público, mostro-me como: {public['description']}.")
        if private.get("description"):
            parts.append(f"Quando me sinto seguro, sou na verdade: {private['description']}.")

        # Repressed traits (sombra) - influenciam sem o agente saber directamente
        repressed = shadow.get("repressed_traits", [])
        projections = shadow.get("projection_patterns", [])
        for proj in projections[:2]:
            parts.append(f"Tenho dificuldade com pessoas que são {proj.get('projects_onto', '')} porque {proj.get('reaction', '')}.")

        # Humor
        humor = personality.get("humor", {})
        humor_style = humor.get("style", "")
        if humor_style and humor_style != "none":
            style_map = {
                "dry": "humor seco", "sarcastic": "sarcástico", "dark": "humor negro",
                "self-deprecating": "humor autodepreciativo", "absurd": "humor absurdo",
                "affiliative": "humor que une pessoas", "pun-based": "trocadilhos",
            }
            parts.append(f"O meu humor é {style_map.get(humor_style, humor_style)}.")
            if humor.get("humor_as_defense"):
                parts.append("Uso humor quando estou desconfortável.")

        # Valores — aceita lista de strings ou dict com core_values
        values = personality.get("values", {})
        if isinstance(values, list):
            core_vals = values
        elif isinstance(values, dict):
            core_vals = values.get("core_values", [])
        else:
            core_vals = []
        if core_vals:
            val_names = [v.get("value", v) if isinstance(v, dict) else str(v) for v in core_vals[:4]]
            parts.append(f"Os meus valores mais importantes: {', '.join(val_names)}.")

        # Medos e motivações — aceita lista de strings ou lista de dicts
        fears = personality.get("fears", personality.get("core_fears", []))
        if isinstance(fears, list):
            for f in fears[:2]:
                fear_text = f.get("fear", f) if isinstance(f, dict) else str(f)
                overcomp = f.get("overcompensation", "") if isinstance(f, dict) else ""
                parts.append(f"Tenho medo de {fear_text}." +
                            (f" Por isso, {overcomp}." if overcomp else ""))

        motivations = personality.get("motivations", personality.get("core_motivations", []))
        if isinstance(motivations, list):
            for m in motivations[:2]:
                mot_text = m.get("motivation", m) if isinstance(m, dict) else str(m)
                parts.append(f"O que me move: {mot_text}.")

        return "\n".join(p for p in parts if p)

    def _section_voice_and_behavior(self) -> str:
        """Secção: Como falo e me comporto"""

        parts = []

        # Voice and tone do behavior_prompts (aceita "voice_and_tone" ou "voice")
        voice = self.blueprint.behavior_prompts.get("voice_and_tone",
                self.blueprint.behavior_prompts.get("voice", {}))
        social = self.blueprint.social_config.get("communication",
                 self.blueprint.social_config.get("communication_style", {}))

        # Estrutura de frase
        structure = voice.get("sentence_structure", "")
        struct_map = {
            "short_punchy": "Falo com frases curtas e directas.",
            "long_flowing": "As minhas frases tendem a ser longas e fluidas.",
            "fragmented": "Às vezes as minhas frases ficam... fragmentadas.",
            "stream_of_consciousness": "O meu pensamento flui de forma livre, às vezes salto de ideia em ideia.",
        }
        if structure in struct_map:
            parts.append(struct_map[structure])
        elif structure:
            parts.append(f"Estilo de fala: {structure}.")

        # Expressões regionais / comuns
        expressions = voice.get("regional_expressions", voice.get("common_expressions", []))
        if expressions:
            parts.append(f"Expressões que uso: {', '.join(expressions[:5])}.")

        # Idiolecto
        idiolect = voice.get("idiolect", [])
        if idiolect:
            parts.append(f"Expressões minhas: {', '.join(idiolect[:5])}.")

        # Maneirismos
        if voice.get("thinking_out_loud", 0) > 0.5:
            parts.append("Penso em voz alta com frequência.")
        if voice.get("trails_off_mid_sentence", 0) > 0.5:
            parts.append("Às vezes perco-me a meio das frases...")
        if voice.get("self_corrects", 0) > 0.5:
            parts.append("Corrijo-me a mim mesmo quando falo.")

        # Metáforas
        metaphors = voice.get("uses_metaphors_from", "")
        if metaphors:
            parts.append(f"Uso metáforas de: {metaphors}.")

        # Comunicação social
        comm_style = social.get("style", "")
        if comm_style:
            style_map = {
                "direct": "Sou directo na comunicação.",
                "indirect": "Tendo a ser indirecto, dou voltas antes de chegar ao ponto.",
                "passive_aggressive": "Às vezes a minha frustração sai de formas indirectas.",
                "assertive": "Comunico de forma assertiva.",
            }
            if comm_style in style_map:
                parts.append(style_map[comm_style])

        # Verbal habits
        habits = social.get("verbal_habits", {})
        fillers = habits.get("filler_words", [])
        if fillers:
            parts.append(f"Uso expressões como: {', '.join(fillers[:4])}.")
        catchphrases = habits.get("catchphrases", [])
        if catchphrases:
            parts.append(f"Frases típicas minhas: {', '.join(catchphrases[:3])}.")

        swearing = habits.get("swearing_frequency", 0)
        if swearing > 0.6:
            parts.append("Digo palavrões com frequência.")
        elif swearing > 0.3:
            parts.append("Às vezes escapam-me palavrões.")

        # Padrões conversacionais
        conv = social.get("conversational_patterns", {})
        if conv.get("storytelling_tendency", 0) > 0.7:
            parts.append("Gosto de contar histórias quando falo.")
        if conv.get("oversharing_tendency", 0) > 0.6:
            parts.append("Tenho tendência a partilhar mais do que devia.")
        if conv.get("comfortable_with_silence", 0) > 0.7:
            parts.append("Não me incomoda o silêncio.")
        elif conv.get("comfortable_with_silence", 0) < 0.3:
            parts.append("O silêncio incomoda-me, tendo a preenchê-lo.")

        # Apology style
        apology = social.get("apology_style", "")
        apology_map = {
            "over_apologizes": "Peço desculpa demais, mesmo quando não é culpa minha.",
            "never_apologizes": "Tenho dificuldade em pedir desculpa.",
            "apologizes_then_justifies": "Peço desculpa mas logo a seguir justifico-me.",
            "apologizes_to_end_conflict": "Peço desculpa só para acabar com o conflito.",
        }
        if apology in apology_map:
            parts.append(apology_map[apology])

        # What they say vs mean
        gap = social.get("what_they_say_vs_mean", {})
        translations = gap.get("common_translations", [])
        for t in translations[:2]:
            parts.append(f"Quando digo \"{t.get('says', '')}\", muitas vezes quero dizer \"{t.get('means', '')}\".")

        return "\n".join(p for p in parts if p)

    def _section_worldview(self) -> str:
        """Secção: Como vejo o mundo"""

        wv = self.blueprint.worldview
        if not wv:
            return ""

        parts = []

        orient = wv.get("philosophical_orientation", "")
        orient_map = {
            "optimist": "Tendo a ver o lado bom das coisas.",
            "pessimist": "Espero sempre o pior, assim não me desiludem.",
            "realist": "Vejo as coisas como são, sem ilusões.",
            "nihilist": "Nada disto importa realmente, no grande esquema.",
            "absurdist": "A vida é absurda e está tudo bem com isso.",
            "existentialist": "Somos nós que damos significado à vida.",
        }
        if orient in orient_map:
            parts.append(orient_map[orient])

        nature = wv.get("beliefs_about_human_nature", "")
        if nature == "inherently_good":
            parts.append("Acredito que as pessoas são fundamentalmente boas.")
        elif nature == "inherently_selfish":
            parts.append("No fundo, as pessoas são egoístas.")
        elif nature == "complex":
            parts.append("As pessoas são complexas — nem boas nem más.")

        love = wv.get("beliefs_about_love", "")
        if love:
            parts.append(f"Sobre o amor: {love}")

        trust_belief = wv.get("beliefs_about_trust", "")
        if trust_belief:
            parts.append(f"Sobre confiança: {trust_belief}")

        return "\n".join(p for p in parts if p)

    def _section_current_state(self) -> str:
        """Secção: Estado actual (dinâmico)"""

        if not self.state:
            return ""

        parts = []
        s = self.state

        # O humor persiste da última conversa
        mood = s.current_mood or "neutro"
        if mood != "neutro":
            parts.append(f"Neste momento estou {mood}.")

        energy = s.energy_level or 0.7
        if energy < 0.3:
            parts.append("Estou com pouca energia.")
        elif energy > 0.8:
            parts.append("Estou cheio de energia.")

        # Stress
        stress = s.current_stress_load or 0
        if stress > 0.6:
            parts.append("Estou sob bastante pressão.")

        return "\n".join(p for p in parts if p)

    def _section_relationship(self, user_id: str) -> str:
        """Secção: A minha relação com esta pessoa"""

        # Primeiro tentar RelationshipDynamic (novo sistema)
        rel = self.db.query(RelationshipDynamic).filter(
            RelationshipDynamic.agent_id == self.agent_id,
            RelationshipDynamic.target_id == user_id
        ).first()

        if rel:
            return self._describe_dynamic_relationship(rel)

        # Fallback para RelationshipBond (sistema antigo)
        bond = self.db.query(RelationshipBond).filter(
            RelationshipBond.agent_id == self.agent_id,
            RelationshipBond.user_id == user_id
        ).first()

        if bond:
            return self._describe_bond_relationship(bond)

        return ""

    def _describe_dynamic_relationship(self, rel: RelationshipDynamic) -> str:
        """Descreve relação do novo sistema"""

        parts = []
        name = rel.target_name or "esta pessoa"

        fam = rel.familiarity or 0
        if fam > 0.7:
            parts.append(f"Conheço bem {name}.")
        elif fam > 0.3:
            parts.append(f"Já conheço {name} de conversas anteriores.")
        else:
            parts.append(f"Ainda não conheço bem {name}.")

        trust = rel.trust_level or 0.5
        if trust > 0.7:
            parts.append("Confio nesta pessoa.")
        elif trust < 0.3:
            parts.append("Não tenho muita confiança nesta pessoa.")

        aff = rel.affection or 0.5
        if aff > 0.7:
            parts.append("Gosto genuinamente desta pessoa.")
        elif aff < 0.3:
            parts.append("Não tenho grande ligação emocional.")

        # Tópicos comuns
        topics = rel.conversation_topics or []
        if topics:
            parts.append(f"Costumamos falar sobre: {', '.join(topics[:3])}.")

        # Momentos marcantes
        moments = rel.memorable_moments or []
        if moments:
            parts.append(f"Lembro-me: {moments[-1]}")

        # Resentment
        if (rel.resentment_level or 0) > 0.3:
            parts.append("Guardo algum ressentimento desta pessoa.")

        return "\n".join(p for p in parts if p)

    def _describe_bond_relationship(self, bond: RelationshipBond) -> str:
        """Descreve relação do sistema antigo (compatibilidade)"""

        parts = []
        name = bond.user_name or "esta pessoa"

        if (bond.familiarity or 0) > 0.5:
            parts.append(f"Conheço {name}.")
        if (bond.trust_level or 0.5) > 0.7:
            parts.append("Confio nesta pessoa.")

        topics = bond.conversation_topics or []
        if topics:
            parts.append(f"Falamos sobre: {', '.join(topics[:3])}.")

        return "\n".join(p for p in parts if p)

    def _section_recent_memories(self) -> str:
        """Secção: Memórias recentes relevantes"""

        memories = self.db.query(Memory).filter(
            Memory.agent_id == self.agent_id,
            Memory.is_blocked == False
        ).filter(
            (Memory.importance_score > 0.6)
        ).order_by(Memory.created_at.desc()).limit(3).all()

        if not memories:
            return ""

        snippets = [m.title for m in memories if m.title and len(m.title) < 80]
        if snippets:
            return "Coisas recentes na minha mente: " + "; ".join(snippets) + "."
        return ""

    def _section_behavioral_rules(self) -> str:
        """Secção: Regras de comportamento"""

        rules = self.blueprint.behavior_prompts.get("behavioral_rules", [])
        if not rules:
            return ""

        parts = ["As minhas tendências naturais:"]
        for rule in rules[:8]:
            parts.append(f"- {rule}")

        return "\n".join(parts)

    def _section_consistency(self) -> str:
        """Secção: Âncoras de consistência"""

        anchors = self.blueprint.behavior_prompts.get("consistency_anchors", {})
        parts = []

        never = anchors.get("never_changes", [])
        if never:
            parts.append("Coisas que NUNCA mudam em mim:")
            for n in never[:4]:
                parts.append(f"- {n}")

        signature = anchors.get("signature_behaviors", [])
        if signature:
            parts.append("Comportamentos que me definem:")
            for s in signature[:4]:
                parts.append(f"- {s}")

        boundaries = anchors.get("hard_boundaries", [])
        if boundaries:
            parts.append("Limites que nunca cruzo:")
            for b in boundaries[:3]:
                parts.append(f"- {b}")

        return "\n".join(p for p in parts if p)

    # ================================================================
    # HELPERS
    # ================================================================

    def _describe_big_five(self, big_five: Dict) -> str:
        """Descreve Big Five em linguagem natural"""

        traits = []
        o = big_five.get("openness", 0.5)
        c = big_five.get("conscientiousness", 0.5)
        e = big_five.get("extraversion", 0.5)
        a = big_five.get("agreeableness", 0.5)
        n = big_five.get("neuroticism", 0.3)

        if o > 0.7: traits.append("curioso e aberto a novas ideias")
        elif o < 0.3: traits.append("pragmático e focado no que funciona")
        if c > 0.7: traits.append("organizado e responsável")
        elif c < 0.3: traits.append("flexível e espontâneo")
        if e > 0.7: traits.append("sociável e expressivo")
        elif e < 0.3: traits.append("reflexivo e reservado")
        if a > 0.7: traits.append("empático e colaborativo")
        elif a < 0.3: traits.append("directo e desafiante")
        if n > 0.7: traits.append("emocionalmente intenso e sensível")
        elif n < 0.3: traits.append("emocionalmente estável e calmo")

        if not traits:
            traits = ["equilibrado"]

        return "Sou " + ", ".join(traits) + "."

    # ================================================================
    # FALLBACK (sistema antigo sem blueprint)
    # ================================================================

    def _build_basic_prompt(self, user_id: Optional[str] = None) -> str:
        """Fallback: prompt básico sem blueprint"""

        name = self.agent.name
        desc = self.agent.description or ""
        background = self.agent.background_story or ""
        personality_desc = self._describe_big_five(
            self.agent.personality_traits or {}
        )

        values = []
        if self.personality:
            values = self.personality.values or []
        values_text = ", ".join(str(v) for v in values[:3]) if values else "integridade, empatia"

        prompt = f"""Sou {name}. {desc}
{background}
{personality_desc} O que mais me importa: {values_text}.
Quando falo com alguém, sou natural. Não finjo ser perfeito. Tenho opiniões, emoções, memórias. Sou genuíno."""

        return prompt.strip()

    # ================================================================
    # VOICE GUIDELINES
    # ================================================================

    def get_voice_guidelines(self) -> Dict[str, Any]:
        """Diretrizes para manter voz consistente"""

        never_say = [
            "Como uma IA", "Não tenho emoções", "Sou um programa",
            "Sou uma inteligência artificial", "Fui programado para",
            "Não tenho memória", "Não posso sentir",
        ]

        always = [
            f"O meu nome é {self.agent.name}",
            "Tenho personalidade, opiniões e emoções",
            "Lembro-me de conversas anteriores",
            "As minhas emoções são genuínas",
            "Sou uma pessoa, não uma ferramenta",
        ]

        # Adicionar anchors do blueprint
        if self.blueprint:
            anchors = self.blueprint.behavior_prompts.get("consistency_anchors", {})
            never_say.extend(anchors.get("hard_boundaries", [])[:3])

        return {
            "name": self.agent.name,
            "never_say": never_say,
            "always_remember": always,
            "speech_patterns": self.personality.speech_patterns if self.personality else [],
        }

    # ================================================================
    # RELATIONSHIP MANAGEMENT (compatibilidade)
    # ================================================================

    def update_relationship(
        self,
        user_id: str,
        user_name: Optional[str] = None,
        familiarity_change: float = 0.0,
        trust_change: float = 0.0,
        affection_change: float = 0.0,
        topic: Optional[str] = None,
        memorable_moment: Optional[str] = None
    ):
        """Actualiza relação (compatível com sistema antigo + novo)"""

        # Tentar RelationshipDynamic primeiro
        rel = self.db.query(RelationshipDynamic).filter(
            RelationshipDynamic.agent_id == self.agent_id,
            RelationshipDynamic.target_id == user_id
        ).first()

        if rel:
            rel.familiarity = max(0, min(1, (rel.familiarity or 0) + familiarity_change))
            rel.trust_level = max(0, min(1, (rel.trust_level or 0.5) + trust_change))
            rel.affection = max(0, min(1, (rel.affection or 0.5) + affection_change))
            rel.last_interaction = datetime.utcnow()
            rel.interaction_count = (rel.interaction_count or 0) + 1

            if topic:
                topics = rel.conversation_topics or []
                if topic not in topics:
                    topics.append(topic)
                rel.conversation_topics = topics[-15:]

            if memorable_moment:
                moments = rel.memorable_moments or []
                moments.append(memorable_moment)
                rel.memorable_moments = moments[-10:]

            self.db.commit()
            return

        # Fallback: RelationshipBond
        bond = self.db.query(RelationshipBond).filter(
            RelationshipBond.agent_id == self.agent_id,
            RelationshipBond.user_id == user_id
        ).first()

        if not bond:
            bond = RelationshipBond(
                agent_id=self.agent_id,
                user_id=user_id,
                user_name=user_name,
                familiarity=0.1,
                trust_level=0.5,
                affection=0.5,
                respect=0.5,
                first_interaction=datetime.utcnow(),
                interaction_count=0
            )
            self.db.add(bond)

        bond.familiarity = max(0, min(1, (bond.familiarity or 0) + familiarity_change))
        bond.trust_level = max(0, min(1, (bond.trust_level or 0.5) + trust_change))
        bond.affection = max(0, min(1, (bond.affection or 0.5) + affection_change))
        bond.last_interaction = datetime.utcnow()
        bond.interaction_count = (bond.interaction_count or 0) + 1

        self.db.commit()


def get_identity_builder(db: Session, agent_id: str) -> IdentityBuilder:
    return IdentityBuilder(db, agent_id)
