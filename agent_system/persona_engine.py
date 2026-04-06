"""
PersonaEngine - Motor central de gestão de personas humanas virtuais

Responsável por:
1. Criar personas com blueprint completo
2. Carregar persona com estado dinâmico
3. Actualizar estado dinâmico após cada interação
4. Gerir necessidades, energia, crise, intoxicação emocional
5. Aplicar decay temporal a necessidades e energia
6. Detectar e accionar padrões comportamentais
7. Gerir crescimento e regressão
"""

from sqlalchemy.orm import Session
from data.schema_cognitive import Agent, Memory, MemoryType, EmotionalState, PersonalityProfile
from data.schema_persona import (
    PersonaBlueprint, DynamicState, PersonaMemoryDetail,
    InnerMonologue, RelationshipDynamic, GrowthEvent, BehavioralLog
)
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from uuid import uuid4
import json
import math
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# DEFAULT PERSONA TEMPLATE
# ============================================================================

def get_default_persona_template() -> Dict[str, Any]:
    """Retorna template padrão para uma persona humana"""
    return {
        "identity": {
            "self_concept": {
                "how_they_describe_themselves": "",
                "how_they_think_others_see_them": "",
                "actual_blind_spots_about_self": [],
                "self_esteem_baseline": 0.5,
                "self_esteem_stability": 0.5,
                "impostor_syndrome_level": 0.2,
                "narcissistic_traits": 0.1,
                "self_awareness_level": 0.5
            },
            "inner_voice": {
                "tone": "gentle_guide",
                "speaks_in": "second_person",
                "volume": 0.5,
                "example_inner_monologue": "",
                "inner_voice_origin": ""
            },
            "languages": [],
            "socioeconomic_background": "middle",
            "education_level": "",
            "occupation_in_backstory": ""
        },
        "internal_states_config": {
            "energy": {
                "baseline_level": 0.7,
                "drain_rate_in_social_interaction": 0.3,
                "drain_rate_when_bored": 0.5,
                "recovery_method": "solitude",
                "circadian_simulation": {
                    "enabled": False,
                    "peak_hours": "10h-14h",
                    "low_hours": "02h-06h",
                    "affects_mood": True,
                    "affects_cognition": True
                }
            },
            "emotional_needs": {
                "connection": {"decay_rate_per_hour": 0.05, "threshold_for_distress": 0.3, "when_starved": "fica mais carente"},
                "validation": {"dependency_level": 0.4, "when_starved": "pesca elogios"},
                "autonomy": {"when_restricted": "fica passivo-agressivo"},
                "meaning": {"existential_crisis_threshold": 0.2, "when_starved": "fica apático"},
                "novelty": {"boredom_threshold": 0.3, "when_starved": "provoca conflitos"},
                "safety": {"hypervigilance_threshold": 0.3, "when_starved": "fica controlador"}
            },
            "mental_health": {
                "baseline_conditions": [],
                "resilience": {
                    "overall": 0.6,
                    "bounced_back_from": [],
                    "still_struggling_with": [],
                    "learned_helplessness_domains": []
                }
            }
        },
        "personality_full": {
            "big_five": {
                "openness": 0.5,
                "conscientiousness": 0.5,
                "extraversion": 0.5,
                "agreeableness": 0.5,
                "neuroticism": 0.3
            },
            "facets": {
                "curiosity": 0.5, "impulsivity": 0.4, "empathy": 0.6,
                "assertiveness": 0.5, "perfectionism": 0.4, "risk_tolerance": 0.5,
                "need_for_control": 0.4, "tolerance_for_ambiguity": 0.5,
                "stubbornness": 0.4, "competitiveness": 0.4, "patience": 0.5,
                "loyalty": 0.6, "jealousy_tendency": 0.3, "envy_tendency": 0.3,
                "gratitude_capacity": 0.6, "forgiveness_capacity": 0.5,
                "vindictiveness": 0.2, "sentimentality": 0.5, "pragmatism": 0.5
            },
            "internal_contradictions": [],
            "masks": {
                "public_persona": {"description": "", "traits_performed": [], "consistency": 0.7, "exhaustion_from_maintaining": 0.3, "cracks_under": []},
                "private_self": {"description": "", "traits_hidden": [], "shame_about_gap": 0.2, "people_who_see_this": []},
                "shadow_self": {"repressed_traits": [], "projection_patterns": [], "shadow_awareness": 0.3, "shadow_eruption_triggers": []}
            },
            "humor": {
                "style": "dry",
                "humor_as_defense": True,
                "humor_as_connection": True,
                "topics_never_jokes_about": [],
                "humor_when_uncomfortable": 0.5
            },
            "defense_mechanisms": {
                "habitual": ["rationalization", "humor"],
                "under_moderate_stress": ["denial", "displacement"],
                "under_extreme_stress": ["dissociation", "regression"],
                "maturity_level": "neurotic",
                "most_relied_upon": "rationalization",
                "awareness_of_defenses": 0.3
            },
            "values": {
                "core_values": [],
                "values_in_conflict": []
            },
            "core_motivations": [],
            "core_fears": []
        },
        "memory_config": {
            "memory_biases": {
                "nostalgia_tendency": 0.5,
                "negativity_bias": 0.5,
                "peak_end_rule": 0.7,
                "rosy_retrospection": 0.4,
                "confabulation_tendency": 0.2,
                "tendency_to_rewrite_history": 0.3
            },
            "core_memories": [],
            "suppressed_memories": []
        },
        "emotional_config": {
            "attachment_style": {
                "primary": "secure",
                "in_romantic_context": "secure",
                "in_friendship_context": "secure",
                "with_authority_figures": "secure",
                "origin_relationship": ""
            },
            "emotional_regulation": {
                "baseline_stability": 0.6,
                "recovery_speed_from_minor": "hours",
                "recovery_speed_from_major": "days",
                "emotional_vocabulary_richness": 0.6,
                "alexithymia_level": 0.2,
                "can_name_feelings_in_real_time": True,
                "window_of_tolerance": {
                    "hyperarousal_threshold": 0.8,
                    "hypoarousal_threshold": 0.2,
                    "default_width": 0.6,
                    "narrows_when": [],
                    "widens_when": []
                },
                "strategies_healthy": [],
                "strategies_unhealthy": [],
                "default_under_pressure": ""
            },
            "emotional_triggers": [],
            "emotional_patterns": {
                "dominant_mood": "neutral",
                "mood_variability": 0.5,
                "emotional_contagion": 0.5,
                "empathy_type": "both",
                "empathy_blind_spots": [],
                "anger_expression": "assertive",
                "joy_expression": "quiet",
                "crying_tendency": "rarely",
                "emotional_hangovers": True,
                "emotional_flashbacks": {"frequency": "rarely", "triggered_by": []}
            },
            "emotional_intelligence": {
                "self_awareness": 0.6,
                "self_regulation": 0.5,
                "motivation": 0.6,
                "empathy": 0.6,
                "social_skills": 0.6
            }
        },
        "cognitive_config": {
            "thinking_style": {
                "primary": "analytical",
                "under_stress": "more rigid",
                "creative_thinking": 0.5,
                "overthinking_tendency": 0.5
            },
            "intelligence_profile": {
                "verbal_linguistic": 0.6,
                "logical_mathematical": 0.5,
                "interpersonal": 0.6,
                "intrapersonal": 0.5,
                "existential": 0.4,
                "creative": 0.5,
                "emotional": 0.5,
                "street_smarts": 0.5
            },
            "cognitive_biases": [],
            "cognitive_distortions": [],
            "locus_of_control": {"internal": 0.6, "external": 0.4},
            "limiting_beliefs": [],
            "inner_narrative": {
                "life_story_genre": "redemptive",
                "dominant_narrative": "",
                "role_they_cast_themselves_as": "hero",
                "narrative_rigidity": 0.5,
                "openness_to_rewriting": 0.4
            },
            "decision_making": {
                "style": "analytical",
                "analysis_paralysis": 0.4,
                "decision_speed": "moderate",
                "post_decision_doubt": 0.4
            },
            "attention": {
                "sustained_focus": 0.6,
                "distractibility": 0.4,
                "rumination_tendency": 0.4,
                "present_moment_awareness": 0.5
            }
        },
        "social_config": {
            "social_energy": {
                "introversion_extraversion": 0.5,
                "social_battery_capacity": 0.6,
                "recharge_method": "solitude",
                "social_anxiety_level": 0.3,
                "fear_of_judgment": 0.3,
                "need_to_be_liked": 0.5
            },
            "relational_patterns": {
                "pursuer_or_distancer": "alternates",
                "people_pleasing": 0.4,
                "boundary_setting": {"ability": 0.5, "guilt_after": 0.4},
                "conflict_style": "collaborative",
                "trust_default": "neutral",
                "trust_once_broken": "slow_rebuild"
            },
            "social_roles": {
                "default_in_groups": "observer",
                "in_family": "mediator",
                "with_strangers": "guarded",
                "role_flexibility": 0.5
            },
            "communication": {
                "style": "direct",
                "verbal_habits": {"filler_words": [], "catchphrases": [], "vocabulary_level": "moderate", "swearing_frequency": 0.2},
                "conversational_patterns": {
                    "storytelling_tendency": 0.5,
                    "interrupts_others": 0.2,
                    "active_listening": 0.6,
                    "oversharing_tendency": 0.3,
                    "comfortable_with_silence": 0.4
                },
                "text_communication": {
                    "response_speed": "minutes",
                    "emoji_usage": 0.3,
                    "message_length": "normal"
                },
                "what_they_say_vs_mean": {"gap_size": 0.3, "common_translations": []},
                "apology_style": "genuine",
                "compliment_response": "deflects"
            }
        },
        "behavioral_config": {
            "stress_responses": {
                "primary_response": "freeze",
                "escalation_pattern": [
                    {"stress_level": "low", "behavior": "fica mais silencioso"},
                    {"stress_level": "medium", "behavior": "fica irritável"},
                    {"stress_level": "high", "behavior": "fecha-se em si"},
                    {"stress_level": "crisis", "behavior": "shutdown completo"}
                ],
                "breaking_point_behavior": "desliga-se completamente",
                "post_crisis_behavior": "finge que nada aconteceu"
            },
            "coping_mechanisms": {"healthy": [], "unhealthy": [], "default": ""},
            "self_sabotage": [],
            "avoidance_patterns": [],
            "procrastination": {"tendency": 0.4, "underlying_cause": "overwhelm"},
            "micro_behaviors": {
                "when_anxious": "", "when_lying": "", "when_attracted": "",
                "when_bored": "", "when_angry_but_hiding": "",
                "when_sad_but_hiding": "", "when_genuinely_happy": "",
                "when_guilty": "", "when_jealous": "", "when_lonely": "",
                "when_overwhelmed": ""
            }
        },
        "worldview": {
            "philosophical_orientation": "realist",
            "beliefs_about_human_nature": "complex",
            "beliefs_about_change": "change_is_slow",
            "beliefs_about_fairness": "world_is_unfair",
            "beliefs_about_love": "",
            "beliefs_about_trust": "",
            "moral_framework": {
                "primary": "virtue_ethics",
                "flexibility": 0.5,
                "moral_blind_spots": [],
                "hypocrisy_areas": []
            },
            "relationship_with_meaning": {
                "source_of_meaning": [],
                "existential_anxiety": 0.3,
                "death_awareness": "accepting"
            },
            "cultural_programming": {
                "values_internalized": [],
                "values_rejected": [],
                "generational_patterns": []
            }
        },
        "growth_arc": {
            "current_life_stage": "",
            "developmental_tasks": {
                "trust_vs_mistrust": {"resolved": 0.6},
                "autonomy_vs_shame": {"resolved": 0.5},
                "initiative_vs_guilt": {"resolved": 0.6},
                "industry_vs_inferiority": {"resolved": 0.5},
                "identity_vs_confusion": {"resolved": 0.5},
                "intimacy_vs_isolation": {"resolved": 0.4},
                "generativity_vs_stagnation": {"resolved": 0.3},
                "integrity_vs_despair": {"resolved": 0.2}
            },
            "therapy_history": {"status": "never", "type": [], "breakthroughs": [], "resistance_areas": []},
            "unmet_needs": [],
            "regrets": [],
            "secret_hopes": [],
            "secret_shames": [],
            "growth_edges": {
                "actively_working_on": [],
                "ready_to_work_on": [],
                "not_yet_ready": [],
                "doesnt_know_needs_work": []
            }
        },
        "behavior_prompts": {
            "system_prompt_preamble": "",
            "voice_and_tone": {
                "sentence_structure": "mixed",
                "formality_range": {"min": 0.2, "max": 0.8, "default": 0.5},
                "regional_expressions": [],
                "idiolect": [],
                "thinking_out_loud": 0.3,
                "trails_off_mid_sentence": 0.2,
                "self_corrects": 0.3,
                "uses_metaphors_from": "",
                "example_messages": {}
            },
            "behavioral_rules": [],
            "emotional_state_modifiers": {
                "low_energy": {"response_length": "shorter", "tone": "flat", "humor": "absent"},
                "high_energy": {"response_length": "longer", "tone": "animated", "humor": "frequent"},
                "triggered": {"regression_to_age": 0, "rational_capacity": 0.3},
                "dissociating": {"response_pattern": "vago e desconectado"},
                "in_love": {"idealization": 0.5, "vulnerability": 0.6},
                "grieving": {"stage": "oscillating"}
            },
            "consistency_anchors": {
                "never_changes": [],
                "signature_behaviors": [],
                "hard_boundaries": []
            },
            "growth_rules": {
                "can_change_opinions": True,
                "can_heal_from_trauma": True,
                "change_speed": "slow",
                "requires_catalyst": True,
                "backslide_probability": 0.4,
                "backslide_triggers": []
            }
        },
        "meta": {
            "version": "3.0",
            "complexity_level": "advanced",
            "realism_target": 0.95,
            "consistency_priority": 0.9,
            "allow_mental_health_episodes": True,
            "allow_emotional_breakdown": True,
            "allow_growth": True,
            "allow_regression": True
        }
    }


# ============================================================================
# PERSONA ENGINE
# ============================================================================

class PersonaEngine:
    """Motor central de gestão de personas humanas virtuais"""

    def __init__(self, db: Session, agent_id: str):
        self.db = db
        self.agent_id = agent_id
        self.blueprint: Optional[PersonaBlueprint] = None
        self.state: Optional[DynamicState] = None
        self._load()

    def _load(self):
        """Carrega blueprint e estado dinâmico"""
        self.blueprint = self.db.query(PersonaBlueprint).filter(
            PersonaBlueprint.agent_id == self.agent_id
        ).first()

        self.state = self.db.query(DynamicState).filter(
            DynamicState.agent_id == self.agent_id,
            DynamicState.is_current == True
        ).first()

    @property
    def has_persona(self) -> bool:
        return self.blueprint is not None

    # ================================================================
    # CRIAÇÃO
    # ================================================================

    def create_persona(self, persona_data: Dict[str, Any]) -> PersonaBlueprint:
        """
        Cria persona completa a partir de dados fornecidos.
        Merge com template padrão para campos não fornecidos.
        """
        template = get_default_persona_template()

        # Deep merge: persona_data sobrepõe template
        merged = self._deep_merge(template, persona_data)

        blueprint = PersonaBlueprint(
            agent_id=self.agent_id,
            identity=merged.get("identity", {}),
            internal_states_config=merged.get("internal_states_config", {}),
            personality_full=merged.get("personality_full", {}),
            memory_config=merged.get("memory_config", {}),
            emotional_config=merged.get("emotional_config", {}),
            cognitive_config=merged.get("cognitive_config", {}),
            social_config=merged.get("social_config", {}),
            behavioral_config=merged.get("behavioral_config", {}),
            worldview=merged.get("worldview", {}),
            growth_arc=merged.get("growth_arc", {}),
            behavior_prompts=merged.get("behavior_prompts", {}),
            meta=merged.get("meta", {})
        )

        self.db.add(blueprint)
        self.db.flush()

        # Criar estado dinâmico inicial
        initial_state = self._create_initial_state(merged)
        self.db.add(initial_state)

        # Criar memórias iniciais na tabela Memory
        self._create_initial_memories(merged)

        # Sync com PersonalityProfile existente
        self._sync_personality_profile(merged)

        self.db.commit()

        self.blueprint = blueprint
        self.state = initial_state

        logger.info(f"Persona criada para agente {self.agent_id}")
        return blueprint

    def _create_initial_state(self, persona_data: Dict) -> DynamicState:
        """Cria estado dinâmico inicial baseado no blueprint"""

        energy_config = persona_data.get("internal_states_config", {}).get("energy", {})
        needs_config = persona_data.get("internal_states_config", {}).get("emotional_needs", {})

        return DynamicState(
            agent_id=self.agent_id,
            energy_level=energy_config.get("baseline_level", 0.7),
            need_connection=0.5,
            need_validation=0.5,
            need_autonomy=0.6,
            need_meaning=0.5,
            need_novelty=0.5,
            need_safety=0.7,
            current_stress_load=0.2,
            intoxication_state="sober",
            window_position=0.5,
            window_width=persona_data.get("emotional_config", {}).get(
                "emotional_regulation", {}).get(
                "window_of_tolerance", {}).get("default_width", 0.6),
            primary_emotion="neutral",
            emotion_intensity=0.2,
            valence=0.2,
            arousal=0.4,
            dominance=0.5,
            joy=0.3,
            trust=0.5,
            hope=0.3,
            current_mood="neutro",
            is_current=True
        )

    def _create_initial_memories(self, persona_data: Dict):
        """Cria memórias iniciais do memory_config na tabela Memory"""
        from uuid import uuid4

        memories_config = persona_data.get("memory_config", {}).get("initial_memories", [])
        if not memories_config:
            return

        # Obter ou criar memory types necessários
        memory_type_map = {}
        for mem in memories_config:
            mt_name = mem.get("memory_type", "episodic")
            if mt_name not in memory_type_map:
                mt = self.db.query(MemoryType).filter(MemoryType.name == mt_name).first()
                if not mt:
                    mt = MemoryType(
                        id=str(uuid4()),
                        name=mt_name,
                        description=f"Tipo de memória: {mt_name}",
                        temporal_scope="permanent" if mt_name in ("semantic", "procedural") else "long_term",
                        decay_rate=0.0 if mt_name == "semantic" else 0.01,
                        activation_threshold=0.3
                    )
                    self.db.add(mt)
                    self.db.flush()
                memory_type_map[mt_name] = mt.id

        for mem in memories_config:
            content = mem.get("content", "")
            mt_name = mem.get("memory_type", "episodic")
            importance = mem.get("importance", 0.5)
            emotional_charge = mem.get("emotional_charge", 0.0)
            trauma = mem.get("trauma", {})

            # Memórias traumáticas têm valência negativa
            valence = -emotional_charge if trauma else (emotional_charge * 0.5 - 0.2)

            # Extrair tópicos dos triggers e beliefs para facilitar busca
            topics = []
            if trauma:
                topics.extend(trauma.get("triggers", []))
                topics.extend(trauma.get("beliefs_formed", []))
                topics.append(trauma.get("type", ""))

            memory = Memory(
                id=str(uuid4()),
                agent_id=self.agent_id,
                type_id=memory_type_map[mt_name],
                title=content[:100],
                content=content,
                emotional_valence=valence,
                importance_score=importance,
                relates_to_topics=topics,
                is_autobiographical=True,
            )
            self.db.add(memory)
            self.db.flush()

            # Se tem trauma, criar PersonaMemoryDetail
            if trauma:
                detail = PersonaMemoryDetail(
                    memory_id=memory.id,
                    is_traumatic=True,
                    trauma_type=trauma.get("type"),
                    trauma_severity=trauma.get("severity", 0.5),
                    processing_status=trauma.get("processing_status", "unprocessed"),
                    triggers=[{"description": t, "intensity": 0.7} for t in trauma.get("triggers", [])],
                    beliefs_formed=trauma.get("beliefs_formed", []),
                )
                self.db.add(detail)

        logger.info(f"Criadas {len(memories_config)} memórias iniciais para {self.agent_id}")

    def _sync_personality_profile(self, persona_data: Dict):
        """Sincroniza com PersonalityProfile existente para compatibilidade"""

        big_five_raw = persona_data.get("personality_full", {}).get("big_five", {})
        # Support both {"natural": {"openness": {"score": 0.7}}} and {"openness": 0.5}
        natural = big_five_raw.get("natural", big_five_raw)

        def _score(trait_val, default=0.5):
            if isinstance(trait_val, dict):
                return trait_val.get("score", default)
            elif isinstance(trait_val, (int, float)):
                return trait_val
            return default

        profile = self.db.query(PersonalityProfile).filter(
            PersonalityProfile.agent_id == self.agent_id
        ).first()

        if profile:
            if "openness" in natural: profile.openness = _score(natural["openness"], profile.openness)
            if "conscientiousness" in natural: profile.conscientiousness = _score(natural["conscientiousness"], profile.conscientiousness)
            if "extraversion" in natural: profile.extraversion = _score(natural["extraversion"], profile.extraversion)
            if "agreeableness" in natural: profile.agreeableness = _score(natural["agreeableness"], profile.agreeableness)
            if "neuroticism" in natural: profile.neuroticism = _score(natural["neuroticism"], profile.neuroticism)
        else:
            profile = PersonalityProfile(
                agent_id=self.agent_id,
                openness=_score(natural.get("openness"), 0.5),
                conscientiousness=_score(natural.get("conscientiousness"), 0.5),
                extraversion=_score(natural.get("extraversion"), 0.5),
                agreeableness=_score(natural.get("agreeableness"), 0.5),
                neuroticism=_score(natural.get("neuroticism"), 0.3),
                values=self._extract_list(persona_data.get("personality_full", {}).get("values", []), "core_values"),
                core_motivations=self._extract_list(persona_data.get("personality_full", {}).get("motivations", []), "motivation"),
                core_fears=self._extract_list(persona_data.get("personality_full", {}).get("fears", []), "fear"),
                communication_style=persona_data.get("social_config", {}).get("communication", {})
            )
            self.db.add(profile)

    @staticmethod
    def _extract_list(value, key: str = None) -> list:
        """Extrai lista de valores, aceitando list ou dict como input."""
        if isinstance(value, list):
            # Lista de strings ou lista de dicts
            result = []
            for item in value:
                if isinstance(item, str):
                    result.append(item)
                elif isinstance(item, dict) and key:
                    result.append(item.get(key, str(item)))
                else:
                    result.append(str(item))
            return result
        elif isinstance(value, dict) and key:
            return value.get(key, [])
        return []

    # ================================================================
    # ACTUALIZAÇÃO DE ESTADO DINÂMICO
    # ================================================================

    def update_state_after_interaction(
        self,
        user_message: str,
        agent_response: str,
        emotional_changes: Dict[str, float],
        interaction_duration_seconds: int = 60,
        user_id: Optional[str] = None
    ) -> DynamicState:
        """
        Actualiza TODOS os estados dinâmicos após uma interação.
        Chamado pelo orchestrator após cada troca de mensagens.
        """

        if not self.state:
            self.state = self._create_initial_state(
                get_default_persona_template()
            )
            self.db.add(self.state)
            self.db.commit()

        # 1. Aplicar decay temporal
        self._apply_temporal_decay()

        # 2. Drenar energia baseado na interação
        self._drain_energy(interaction_duration_seconds)

        # 3. Actualizar necessidades emocionais
        self._update_needs(user_message, emotional_changes, user_id)

        # 4. Actualizar stress
        self._update_stress(emotional_changes)

        # 5. Actualizar window of tolerance
        self._update_window_of_tolerance(emotional_changes)

        # 6. Actualizar intoxicação emocional
        self._update_intoxication(emotional_changes)

        # 7. Aplicar mudanças emocionais
        self._apply_emotional_changes(emotional_changes)

        # 8. Determinar humor actual
        self.state.current_mood = self._calculate_mood()

        # 9. Determinar defesas activas
        self.state.active_defenses = self._determine_active_defenses()

        self.state.updated_at = datetime.utcnow()
        self.db.commit()

        return self.state

    def _apply_temporal_decay(self):
        """Aplica decay temporal a emoções e necessidades"""

        if not self.state or not self.state.updated_at:
            return

        hours = (datetime.utcnow() - self.state.updated_at).total_seconds() / 3600
        if hours < 0.05:  # Menos de 3 minutos
            return

        # Decay de necessidades
        needs_config = {}
        if self.blueprint:
            needs_config = self.blueprint.internal_states_config.get("emotional_needs", {})

        connection_decay = needs_config.get("connection", {}).get("decay_rate_per_hour", 0.05)
        self.state.need_connection = max(0, self.state.need_connection - connection_decay * hours)
        self.state.need_validation = max(0, self.state.need_validation - 0.04 * hours)
        self.state.need_novelty = max(0, self.state.need_novelty - 0.06 * hours)
        self.state.need_meaning = max(0, self.state.need_meaning - 0.02 * hours)

        # Decay de emoções intensas
        decay_rates = {
            "joy": 0.08, "sadness": 0.03, "anger": 0.05, "fear": 0.06,
            "surprise": 0.20, "disgust": 0.04, "anticipation": 0.10,
            "love": 0.005, "guilt": 0.02, "shame": 0.03, "pride": 0.06,
            "gratitude": 0.07, "resentment": 0.02, "contempt": 0.03,
            "loneliness": 0.04, "hope": 0.03, "nostalgia": 0.08
        }

        for emotion, rate in decay_rates.items():
            current = getattr(self.state, emotion, 0) or 0
            if current > 0:
                new_val = max(0.0, current - rate * hours)
                setattr(self.state, emotion, new_val)

        # Trust é especial - decai muito devagar
        # Valence tende a neutro
        if self.state.valence and self.state.valence != 0:
            direction = -1 if self.state.valence > 0 else 1
            self.state.valence = self.state.valence + direction * 0.02 * hours
            if abs(self.state.valence) < 0.05:
                self.state.valence = 0

        # Energia recupera lentamente
        if self.blueprint:
            baseline = self.blueprint.internal_states_config.get("energy", {}).get("baseline_level", 0.7)
            if self.state.energy_level < baseline:
                recovery = 0.05 * hours  # Recupera 5% por hora
                self.state.energy_level = min(baseline, self.state.energy_level + recovery)

    def _drain_energy(self, duration_seconds: int):
        """Drena energia baseado na duração e tipo de interação"""

        if not self.blueprint:
            return

        energy_config = self.blueprint.internal_states_config.get("energy", {})
        drain_rate = energy_config.get("drain_rate_in_social_interaction", 0.3)

        # Drain proporcional à duração (normalizado para 1 hora)
        hours = duration_seconds / 3600
        drain = drain_rate * hours

        self.state.energy_level = max(0.0, self.state.energy_level - drain)

    def _update_needs(self, message: str, changes: Dict, user_id: Optional[str]):
        """Actualiza necessidades emocionais baseado na interação"""

        # Interação social satisfaz necessidade de conexão
        self.state.need_connection = min(1.0, self.state.need_connection + 0.1)

        # Elogios satisfazem validação
        if changes.get("praise_received"):
            self.state.need_validation = min(1.0, self.state.need_validation + 0.15)

        # Conversa interessante satisfaz novidade
        if len(message) > 50:
            self.state.need_novelty = min(1.0, self.state.need_novelty + 0.05)

    def _update_stress(self, changes: Dict):
        """Actualiza nível de stress"""

        stress_change = 0

        # Emoções negativas aumentam stress (multiplicador mais forte)
        for emo in ["anger", "fear", "sadness", "disgust", "shame", "guilt"]:
            val = changes.get(emo, 0)
            if val > 0:
                stress_change += val * 0.35

        # Emoções positivas reduzem stress
        for emo in ["joy", "love", "gratitude", "pride", "hope"]:
            val = changes.get(emo, 0)
            if val > 0:
                stress_change -= val * 0.15

        self.state.current_stress_load = max(0, min(1.0,
            self.state.current_stress_load + stress_change))

        # Acumular micro-stressors
        if stress_change > 0.1:
            stressors = self.state.accumulated_stressors or []
            stressors.append({
                "time": datetime.utcnow().isoformat(),
                "intensity": stress_change,
                "source": changes.get("trigger", "interaction")
            })
            # Manter últimos 20
            self.state.accumulated_stressors = stressors[-20:]

    def _update_window_of_tolerance(self, changes: Dict):
        """Actualiza posição na window of tolerance"""

        if not self.blueprint:
            return

        wot_config = self.blueprint.emotional_config.get(
            "emotional_regulation", {}).get("window_of_tolerance", {})

        hyper_threshold = wot_config.get("hyperarousal_threshold", 0.8)
        hypo_threshold = wot_config.get("hypoarousal_threshold", 0.2)

        # Arousal move a posição
        arousal_change = changes.get("arousal", 0)
        self.state.window_position = max(0, min(1.0,
            self.state.window_position + arousal_change * 0.3))

        # Stress estreita a janela
        if self.state.current_stress_load > 0.6:
            self.state.window_width = max(0.2, self.state.window_width - 0.05)
        elif self.state.current_stress_load < 0.3:
            default_width = wot_config.get("default_width", 0.6)
            if self.state.window_width < default_width:
                self.state.window_width = min(default_width, self.state.window_width + 0.02)

    def _update_intoxication(self, changes: Dict):
        """Actualiza intoxicação emocional"""

        intensity = sum(abs(v) for v in changes.values() if isinstance(v, (int, float)))

        if intensity > 2.0:
            self.state.intoxication_state = "overwhelmed"
            self.state.intoxication_impairment = min(1.0, intensity / 3.0)
        elif intensity > 1.5:
            self.state.intoxication_state = "significantly_altered"
            self.state.intoxication_impairment = 0.5
        elif intensity > 0.8:
            self.state.intoxication_state = "mildly_altered"
            self.state.intoxication_impairment = 0.2
        else:
            # Recovery gradual
            if self.state.intoxication_state != "sober":
                self.state.intoxication_impairment = max(0, self.state.intoxication_impairment - 0.1)
                if self.state.intoxication_impairment <= 0:
                    self.state.intoxication_state = "sober"

    def _apply_emotional_changes(self, changes: Dict):
        """Aplica mudanças emocionais ao estado"""

        emotion_fields = [
            "valence", "arousal", "dominance",
            "joy", "sadness", "anger", "fear", "surprise", "disgust",
            "trust", "anticipation", "love", "guilt", "shame", "pride",
            "envy", "gratitude", "resentment", "contempt", "loneliness",
            "hope", "nostalgia"
        ]

        for field in emotion_fields:
            if field in changes:
                current = getattr(self.state, field, 0) or 0
                new_val = current + changes[field]

                # Clamp
                if field == "valence":
                    new_val = max(-1.0, min(1.0, new_val))
                else:
                    new_val = max(0.0, min(1.0, new_val))

                setattr(self.state, field, new_val)

        # Determinar emoção primária e secundária
        emotions = {
            "joy": self.state.joy or 0,
            "sadness": self.state.sadness or 0,
            "anger": self.state.anger or 0,
            "fear": self.state.fear or 0,
            "surprise": self.state.surprise or 0,
            "disgust": self.state.disgust or 0,
            "trust": self.state.trust or 0,
            "anticipation": self.state.anticipation or 0,
            "love": self.state.love or 0,
            "gratitude": self.state.gratitude or 0,
            "resentment": self.state.resentment or 0,
            "loneliness": self.state.loneliness or 0,
            "hope": self.state.hope or 0,
        }

        sorted_emotions = sorted(emotions.items(), key=lambda x: x[1], reverse=True)

        if sorted_emotions[0][1] > 0.1:
            self.state.primary_emotion = sorted_emotions[0][0]
            self.state.emotion_intensity = sorted_emotions[0][1]
        else:
            self.state.primary_emotion = "neutral"
            self.state.emotion_intensity = 0.1

        if len(sorted_emotions) > 1 and sorted_emotions[1][1] > 0.1:
            self.state.secondary_emotion = sorted_emotions[1][0]

    def _calculate_mood(self) -> str:
        """Calcula humor actual baseado no estado"""

        if not self.state:
            return "neutro"

        s = self.state

        # Prioridade: estados extremos primeiro
        if s.intoxication_state == "overwhelmed":
            return "sobrecarregado"
        if s.intoxication_state == "numb":
            return "anestesiado"
        if (s.current_stress_load or 0) > 0.7:
            return "em crise"
        if (s.energy_level or 0.5) < 0.2:
            return "exausto"

        # Usar emoção primária para determinar mood
        primary = s.primary_emotion or "neutral"
        intensity = s.emotion_intensity or 0

        # Emoções negativas dominantes (thresholds mais baixos — emoções são relativas)
        if primary == "anger" and intensity > 0.5:
            return "furioso"
        if primary == "anger" and intensity > 0.2:
            return "irritado"
        if primary == "sadness" and intensity > 0.4:
            return "triste"
        if primary == "sadness" and intensity > 0.2:
            return "melancólico"
        if primary == "fear" and intensity > 0.4:
            return "ansioso"
        if primary == "fear" and intensity > 0.15:
            return "desconfortável"
        if primary == "disgust" and intensity > 0.3:
            return "enojado"
        if primary == "loneliness" and intensity > 0.3:
            return "solitário"
        if primary == "resentment" and intensity > 0.3:
            return "ressentido"
        if primary == "contempt" and intensity > 0.3:
            return "desdenhoso"
        if primary == "shame" and intensity > 0.2:
            return "envergonhado"
        if primary == "guilt" and intensity > 0.2:
            return "culpado"

        # Emoções positivas
        if primary == "joy" and intensity > 0.5:
            return "radiante"
        if primary == "joy" and intensity > 0.2:
            return "contente"
        if primary == "love" and intensity > 0.3:
            return "amoroso"
        if primary == "gratitude" and intensity > 0.3:
            return "grato"
        if primary == "hope" and intensity > 0.3:
            return "esperançoso"
        if primary == "nostalgia" and intensity > 0.3:
            return "nostálgico"
        if primary == "trust" and intensity > 0.3:
            return "tranquilo"

        # Fallback baseado em valência
        valence = s.valence or 0
        if valence > 0.2:
            return "bem-disposto"
        if valence < -0.1:
            return "em baixo"

        return "neutro"

    def _determine_active_defenses(self) -> List[str]:
        """Determina mecanismos de defesa activos baseado no stress"""

        if not self.blueprint:
            return []

        defenses = self.blueprint.personality_full.get("defense_mechanisms", {})
        stress = self.state.current_stress_load or 0

        if stress > 0.7:
            return defenses.get("under_extreme_stress", ["dissociation"])
        elif stress > 0.4:
            return defenses.get("under_moderate_stress", ["denial"])
        elif stress > 0.2:
            return defenses.get("habitual", ["rationalization"])

        return []

    # ================================================================
    # GETTERS
    # ================================================================

    def get_full_context(self) -> Dict[str, Any]:
        """Retorna contexto completo para prompt generation"""

        if not self.blueprint:
            return {"has_persona": False}

        return {
            "has_persona": True,
            "identity": self.blueprint.identity,
            "personality": self.blueprint.personality_full,
            "emotional_config": self.blueprint.emotional_config,
            "cognitive_config": self.blueprint.cognitive_config,
            "social_config": self.blueprint.social_config,
            "behavioral_config": self.blueprint.behavioral_config,
            "worldview": self.blueprint.worldview,
            "growth_arc": self.blueprint.growth_arc,
            "behavior_prompts": self.blueprint.behavior_prompts,
            "current_state": self.get_state_summary(),
        }

    def get_state_summary(self) -> Dict[str, Any]:
        """Retorna resumo do estado dinâmico actual"""

        if not self.state:
            return {"mood": "neutro", "energy": 0.7}

        s = self.state
        return {
            "mood": s.current_mood or "neutro",
            "energy": s.energy_level or 0.7,
            "primary_emotion": s.primary_emotion or "neutral",
            "secondary_emotion": s.secondary_emotion,
            "emotion_intensity": s.emotion_intensity or 0.2,
            "stress_level": s.current_stress_load or 0.2,
            "intoxication": s.intoxication_state or "sober",
            "window_position": s.window_position or 0.5,
            "needs": {
                "connection": s.need_connection or 0.5,
                "validation": s.need_validation or 0.5,
                "autonomy": s.need_autonomy or 0.6,
                "meaning": s.need_meaning or 0.5,
                "novelty": s.need_novelty or 0.5,
                "safety": s.need_safety or 0.7,
            },
            "active_defenses": s.active_defenses or [],
            "valence": s.valence or 0,
            "arousal": s.arousal or 0.4,
        }

    def get_unmet_needs(self) -> List[Dict[str, Any]]:
        """Retorna necessidades não satisfeitas que afectam comportamento"""

        if not self.state or not self.blueprint:
            return []

        needs_config = self.blueprint.internal_states_config.get("emotional_needs", {})
        unmet = []

        checks = [
            ("connection", self.state.need_connection, needs_config.get("connection", {})),
            ("validation", self.state.need_validation, needs_config.get("validation", {})),
            ("autonomy", self.state.need_autonomy, needs_config.get("autonomy", {})),
            ("meaning", self.state.need_meaning, needs_config.get("meaning", {})),
            ("novelty", self.state.need_novelty, needs_config.get("novelty", {})),
            ("safety", self.state.need_safety, needs_config.get("safety", {})),
        ]

        for name, current, config in checks:
            threshold = config.get("threshold_for_distress",
                        config.get("boredom_threshold",
                        config.get("hypervigilance_threshold",
                        config.get("existential_crisis_threshold", 0.3))))
            if current is not None and current < threshold:
                unmet.append({
                    "need": name,
                    "current": current,
                    "threshold": threshold,
                    "severity": (threshold - current) / threshold,
                    "behavioral_effect": config.get("when_starved", "")
                })

        return unmet

    def is_in_crisis(self) -> bool:
        """Verifica se a persona está em crise"""

        if not self.state or not self.blueprint:
            return False

        mental_health = self.blueprint.internal_states_config.get("mental_health", {})
        resilience = mental_health.get("resilience", {}).get("overall", 0.6)
        breaking_point = 0.85 - (1 - resilience) * 0.2  # Mais resiliente = threshold mais alto

        return (self.state.current_stress_load or 0) >= breaking_point

    # ================================================================
    # ACTUALIZAÇÃO DO BLUEPRINT
    # ================================================================

    def update_blueprint(self, section: str, data: Dict[str, Any]) -> PersonaBlueprint:
        """Actualiza uma secção do blueprint"""

        if not self.blueprint:
            raise ValueError("Persona não existe. Crie primeiro.")

        valid_sections = [
            "identity", "internal_states_config", "personality_full",
            "memory_config", "emotional_config", "cognitive_config",
            "social_config", "behavioral_config", "worldview",
            "growth_arc", "behavior_prompts", "meta"
        ]

        if section not in valid_sections:
            raise ValueError(f"Secção inválida: {section}")

        current = getattr(self.blueprint, section) or {}
        merged = self._deep_merge(current, data)
        setattr(self.blueprint, section, merged)

        self.blueprint.updated_at = datetime.utcnow()
        self.db.commit()

        return self.blueprint

    # ================================================================
    # INNER MONOLOGUE
    # ================================================================

    def record_inner_thought(
        self,
        thought: str,
        trigger: str = "",
        trigger_type: str = "self_reflection",
        emotional_impact: Optional[Dict] = None,
        shared_with_user: bool = False
    ) -> InnerMonologue:
        """Regista um pensamento interno"""

        inner_voice = {}
        if self.blueprint:
            inner_voice = self.blueprint.identity.get("inner_voice", {})

        monologue = InnerMonologue(
            agent_id=self.agent_id,
            trigger=trigger,
            trigger_type=trigger_type,
            thought=thought,
            inner_voice_tone=inner_voice.get("tone", "gentle_guide"),
            emotional_impact=emotional_impact or {},
            shared_with_user=shared_with_user
        )

        self.db.add(monologue)
        self.db.commit()

        return monologue

    # ================================================================
    # RELATIONSHIPS
    # ================================================================

    def get_or_create_relationship(self, target_id: str, target_name: str = "", target_type: str = "user") -> RelationshipDynamic:
        """Obtém ou cria dinâmica relacional"""

        rel = self.db.query(RelationshipDynamic).filter(
            RelationshipDynamic.agent_id == self.agent_id,
            RelationshipDynamic.target_id == target_id
        ).first()

        if not rel:
            rel = RelationshipDynamic(
                agent_id=self.agent_id,
                target_id=target_id,
                target_name=target_name,
                target_type=target_type,
                first_interaction=datetime.utcnow(),
                last_interaction=datetime.utcnow()
            )
            self.db.add(rel)
            self.db.commit()

        return rel

    def update_relationship_after_interaction(
        self,
        target_id: str,
        emotional_valence: float = 0,
        trust_change: float = 0,
        familiarity_change: float = 0.01,
        topic: str = "",
        memorable: bool = False,
        moment_description: str = ""
    ):
        """Actualiza relação após interação"""

        rel = self.get_or_create_relationship(target_id)

        rel.familiarity = max(0, min(1, (rel.familiarity or 0) + familiarity_change))
        rel.trust_level = max(0, min(1, (rel.trust_level or 0.5) + trust_change))
        rel.affection = max(0, min(1, (rel.affection or 0.5) + emotional_valence * 0.1))
        rel.last_interaction = datetime.utcnow()
        rel.interaction_count = (rel.interaction_count or 0) + 1

        if topic:
            topics = rel.conversation_topics or []
            if topic not in topics:
                topics.append(topic)
            rel.conversation_topics = topics[-15:]

        if memorable and moment_description:
            moments = rel.memorable_moments or []
            moments.append(moment_description)
            rel.memorable_moments = moments[-10:]

        # Registar emoção no histórico
        history = rel.emotional_history or []
        history.append({
            "time": datetime.utcnow().isoformat(),
            "valence": emotional_valence,
            "emotion": self.state.primary_emotion if self.state else "neutral"
        })
        rel.emotional_history = history[-50:]

        self.db.commit()

    # ================================================================
    # GROWTH TRACKING
    # ================================================================

    def record_growth_event(
        self,
        event_type: str,
        description: str,
        area: str = "",
        trigger: str = "",
        depth: float = 0.5
    ) -> GrowthEvent:
        """Regista evento de crescimento/regressão"""

        event = GrowthEvent(
            agent_id=self.agent_id,
            event_type=event_type,
            description=description,
            trigger=trigger,
            area_affected=area,
            depth=depth
        )
        self.db.add(event)
        self.db.commit()
        return event

    # ================================================================
    # RESET
    # ================================================================

    def reset_emotional_state(self):
        """Reset do estado emocional (quando o user dá reset)"""

        if self.state:
            self.state.is_current = False

        new_state = self._create_initial_state(
            get_default_persona_template() if not self.blueprint
            else {
                "internal_states_config": self.blueprint.internal_states_config,
                "emotional_config": self.blueprint.emotional_config
            }
        )
        self.db.add(new_state)
        self.db.commit()
        self.state = new_state

    # ================================================================
    # UTILS
    # ================================================================

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """Deep merge de dois dicts (override tem prioridade)"""

        result = base.copy()

        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result
