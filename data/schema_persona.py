"""
Schema Persona - Tabelas para simulação humana completa (digital_human_persona_v3)

Arquitectura:
- PersonaBlueprint: DNA estático da persona (quem é, personalidade, worldview, etc.)
- DynamicState: Estado runtime que muda a cada interação (energia, emoções, necessidades)
- PersonaMemory: Memórias expandidas com trauma, triggers, sensorial, narrativa
- ConversationSession/Message: Conversas persistentes em DB

Princípio: Dados que precisam de query/filter vão em colunas.
           Dados complexos/nested vão em JSON.
"""

from sqlalchemy import (
    create_engine, Column, String, Text, DateTime, Float, Integer, Boolean,
    ForeignKey, Index, JSON, UniqueConstraint, Enum as SAEnum
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
from uuid import uuid4
import enum

# Usar a mesma Base do schema_cognitive
from data.schema_cognitive import Base


# ============================================================================
# PERSONA BLUEPRINT - O "DNA" completo da pessoa
# ============================================================================

class PersonaBlueprint(Base):
    """
    Blueprint completo de uma persona humana virtual.
    Armazena a definição estática de QUEM esta pessoa é.
    Muda raramente (apenas por edição explícita do criador).
    """
    __tablename__ = "persona_blueprints"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    agent_id = Column(String(36), ForeignKey("agents.id", ondelete="CASCADE"),
                      nullable=False, unique=True, index=True)

    # ── 1. IDENTIDADE ──
    # Nome, avatar, género, pronomes, etnia, nacionalidade, etc.
    identity = Column(JSON, default=dict)
    # Inclui: name, avatar, birth_date, age, gender, pronouns, ethnicity,
    #         nationality, languages[], socioeconomic_background,
    #         education_level, occupation_in_backstory,
    #         self_concept{}, inner_voice{}

    # ── 2. ESTADOS INTERNOS (CONFIG) ──
    # Configuração base dos estados internos (os valores dinâmicos vão em DynamicState)
    internal_states_config = Column(JSON, default=dict)
    # Inclui: energy{baseline_level, drain_rate_*, recovery_method, circadian_simulation},
    #         emotional_needs{} (config de cada necessidade: decay_rate, threshold, when_starved),
    #         mental_health{baseline_conditions[], resilience{}}

    # ── 3. PERSONALIDADE ──
    personality_full = Column(JSON, default=dict)
    # Inclui: big_five{}, facets{}, internal_contradictions[],
    #         masks{public_persona, private_self, shadow_self},
    #         humor{}, defense_mechanisms{}, values{core_values[], values_in_conflict[]},
    #         core_motivations[], core_fears[]

    # ── 4. SISTEMA DE MEMÓRIA (CONFIG) ──
    memory_config = Column(JSON, default=dict)
    # Inclui: memory_biases{}, core_memories[], suppressed_memories[],
    #         procedural_knowledge[]

    # ── 5. SISTEMA EMOCIONAL (CONFIG) ──
    emotional_config = Column(JSON, default=dict)
    # Inclui: attachment_style{}, emotional_regulation{},
    #         emotional_triggers[], emotional_patterns{},
    #         emotional_intelligence{}

    # ── 6. SISTEMA COGNITIVO ──
    cognitive_config = Column(JSON, default=dict)
    # Inclui: thinking_style{}, intelligence_profile{},
    #         cognitive_biases[], cognitive_distortions[],
    #         locus_of_control{}, limiting_beliefs[],
    #         inner_narrative{}, decision_making{}, attention_and_focus{}

    # ── 7. SISTEMA SOCIAL ──
    social_config = Column(JSON, default=dict)
    # Inclui: social_energy{}, relationship_map[],
    #         relational_patterns{}, social_roles{}, communication{}

    # ── 8. COMPORTAMENTO ──
    behavioral_config = Column(JSON, default=dict)
    # Inclui: stress_responses{}, coping_mechanisms{},
    #         self_sabotage[], behavioral_addictions[],
    #         avoidance_patterns[], procrastination{}, micro_behaviors{}

    # ── 9. WORLDVIEW ──
    worldview = Column(JSON, default=dict)
    # Inclui: philosophical_orientation, beliefs_about_*,
    #         moral_framework{}, relationship_with_meaning{},
    #         cultural_programming{}

    # ── 10. CRESCIMENTO E ARCOS DE VIDA ──
    growth_arc = Column(JSON, default=dict)
    # Inclui: current_life_stage, developmental_tasks{} (Erikson),
    #         therapy_history{}, unmet_needs[], regrets[],
    #         secret_hopes[], secret_shames[],
    #         things_they_havent_forgiven_*[], growth_edges{}

    # ── 11. PROMPTS DE COMPORTAMENTO ──
    behavior_prompts = Column(JSON, default=dict)
    # Inclui: system_prompt_preamble, voice_and_tone{},
    #         behavioral_rules[], emotional_state_modifiers{},
    #         consistency_anchors{}, growth_rules{},
    #         dynamic_state_tracking{}

    # ── 12. META ──
    meta = Column(JSON, default=dict)
    # Inclui: version, complexity_level, realism_target,
    #         consistency_priority, allow_* flags

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_blueprint_agent', 'agent_id'),
    )


# ============================================================================
# DYNAMIC STATE - Estado runtime que muda a cada interação
# ============================================================================

class DynamicState(Base):
    """
    Estado dinâmico da persona que muda com cada interação.
    Energia, necessidades emocionais, saúde mental actual, crise, etc.
    Apenas o registo com is_current=True é o estado actual.
    Histórico mantido para análise de evolução.
    """
    __tablename__ = "dynamic_states"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    agent_id = Column(String(36), ForeignKey("agents.id", ondelete="CASCADE"),
                      nullable=False, index=True)

    # ── ENERGIA ──
    energy_level = Column(Float, default=0.7)  # 0.0 (exausto) a 1.0 (pleno)

    # ── NECESSIDADES EMOCIONAIS (saturação actual 0-1) ──
    need_connection = Column(Float, default=0.5)
    need_validation = Column(Float, default=0.5)
    need_autonomy = Column(Float, default=0.6)
    need_meaning = Column(Float, default=0.5)
    need_novelty = Column(Float, default=0.5)
    need_safety = Column(Float, default=0.7)

    # ── SAÚDE MENTAL ACTUAL ──
    current_stress_load = Column(Float, default=0.2)  # 0-1, breaking_point at config threshold
    accumulated_stressors = Column(JSON, default=list)  # Lista de micro-stressors
    current_episodes = Column(JSON, default=dict)  # {condition: True/False} episódios activos
    mental_health_notes = Column(Text)  # Notas sobre estado mental actual

    # ── INTOXICAÇÃO EMOCIONAL ──
    # sober | mildly_altered | significantly_altered | overwhelmed | numb | dissociated
    intoxication_state = Column(String(30), default="sober")
    intoxication_cause = Column(Text)
    intoxication_impairment = Column(Float, default=0.0)

    # ── WINDOW OF TOLERANCE ──
    window_position = Column(Float, default=0.5)  # 0=hypoarousal, 0.5=optimal, 1=hyperarousal
    window_width = Column(Float, default=0.6)  # Largura actual da janela

    # ── ESTADO EMOCIONAL ACTUAL (expandido) ──
    # Emoções primárias
    primary_emotion = Column(String(50), default="neutral")
    secondary_emotion = Column(String(50))
    emotion_intensity = Column(Float, default=0.3)
    emotion_stability = Column(Float, default=0.6)
    emotion_aware = Column(Boolean, default=True)  # Tem consciência da emoção?
    emotion_suppressing = Column(Boolean, default=False)  # Está a suprimir?

    # PAD model
    valence = Column(Float, default=0.2)  # -1 a 1
    arousal = Column(Float, default=0.4)  # 0 a 1
    dominance = Column(Float, default=0.5)  # 0 a 1

    # Emoções Plutchik (0-1)
    joy = Column(Float, default=0.3)
    sadness = Column(Float, default=0.0)
    anger = Column(Float, default=0.0)
    fear = Column(Float, default=0.0)
    surprise = Column(Float, default=0.0)
    disgust = Column(Float, default=0.0)
    trust = Column(Float, default=0.5)
    anticipation = Column(Float, default=0.0)

    # Emoções complexas (0-1)
    love = Column(Float, default=0.0)
    guilt = Column(Float, default=0.0)
    shame = Column(Float, default=0.0)
    pride = Column(Float, default=0.0)
    envy = Column(Float, default=0.0)
    gratitude = Column(Float, default=0.0)
    resentment = Column(Float, default=0.0)
    contempt = Column(Float, default=0.0)
    loneliness = Column(Float, default=0.0)
    hope = Column(Float, default=0.3)
    nostalgia = Column(Float, default=0.0)

    # ── ÚLTIMO TRIGGER ──
    last_trigger = Column(Text)
    last_trigger_type = Column(String(50))  # insult, praise, trauma, empathy, etc.

    # ── DEFESAS ACTIVAS ──
    active_defenses = Column(JSON, default=list)  # Mecanismos de defesa activos agora

    # ── HUMOR ACTUAL ──
    current_mood = Column(String(50), default="neutro")
    mood_duration_minutes = Column(Integer, default=0)

    # ── CONTROLO ──
    is_current = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_dynstate_agent', 'agent_id'),
        Index('idx_dynstate_current', 'is_current'),
        Index('idx_dynstate_agent_current', 'agent_id', 'is_current'),
    )


# ============================================================================
# PERSONA MEMORY - Memória expandida com toda a complexidade humana
# ============================================================================

class PersonaMemoryDetail(Base):
    """
    Detalhes expandidos de uma memória.
    Ligado 1:1 a Memory existente.
    Adiciona: trauma, triggers, sensorial, narrativa, fiabilidade.
    """
    __tablename__ = "persona_memory_details"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    memory_id = Column(String(36), ForeignKey("memories.id", ondelete="CASCADE"),
                       nullable=False, unique=True, index=True)

    # ── CLASSIFICAÇÃO EXPANDIDA ──
    narrative_role = Column(String(50))
    # origin_story | turning_point | wound | triumph | loss | secret | shame |
    # joy | mundane | formative_relationship

    life_period = Column(String(30))
    # childhood | adolescence | early_adult | adult | recent

    memory_subtype = Column(String(30))
    # episodic | semantic | procedural | emotional | sensory | flashbulb | implicit

    # ── TRAUMA ──
    is_traumatic = Column(Boolean, default=False)
    trauma_type = Column(String(30))
    # none | acute | chronic | complex | developmental | vicarious | betrayal | attachment
    trauma_severity = Column(Float, default=0.0)
    processing_status = Column(String(30), default="unprocessed")
    # unprocessed | partially_processed | intellectually_processed |
    # emotionally_integrated | actively_avoided

    # Triggers associados a esta memória
    triggers = Column(JSON, default=list)
    # [{type, description, intensity, response, response_speed}]

    # Crenças formadas por este trauma
    beliefs_formed = Column(JSON, default=list)  # ["O mundo não é seguro", ...]
    behaviors_developed = Column(JSON, default=list)
    coping_born_from = Column(JSON, default=list)

    # Dissociação
    dissociation_level = Column(Float, default=0.0)
    fragmented = Column(Boolean, default=False)
    body_memory = Column(Text)  # Estado emocional que surge sem saber porquê

    # Recuperação
    healing_progress = Column(Float, default=0.0)
    healing_method = Column(Text)
    healing_setbacks = Column(JSON, default=list)

    # ── FIABILIDADE ──
    accuracy = Column(Float, default=0.7)
    reconstructed = Column(Boolean, default=False)
    false_memory_risk = Column(Float, default=0.1)
    idealized = Column(Boolean, default=False)
    demonized = Column(Boolean, default=False)
    perspective = Column(String(30), default="first_person")
    # first_person | observer | fragmented | dissociated | narrated

    # ── SENSORIAL (associações emocionais) ──
    visual_association = Column(Text)
    sound_association = Column(Text)
    emotional_texture = Column(String(50))  # pesado, afiado, quente, vazio
    color_association = Column(String(30))
    word_association = Column(String(100))

    # ── NARRATIVA ──
    how_they_tell_it = Column(Text)
    what_they_omit = Column(Text)
    what_they_change = Column(Text)
    who_they_tell = Column(String(30), default="close_friends")
    # everyone | close_friends | therapist | no_one | manipulatively
    times_retold = Column(Integer, default=0)

    # ── ACESSO ──
    recall_frequency = Column(String(30), default="rarely")
    # constant | daily | weekly | monthly | rarely | suppressed | involuntary_flashbacks
    accessibility = Column(String(30), default="accessible")
    # vivid | accessible | foggy | repressed | recovered | intrusive
    decay_rate = Column(Float, default=0.1)

    # ── IMPACTO NA VIDA ──
    life_impact = Column(String(30), default="neutral")
    # formative | reinforcing | transformative | destructive | neutral | bittersweet

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================================================
# INNER MONOLOGUE - Pensamentos internos autónomos
# ============================================================================

class InnerMonologue(Base):
    """
    Regista pensamentos internos autónomos do agente.
    O agente pensa por si, reage internamente, processa.
    Não é partilhado com o utilizador a menos que escolha.
    """
    __tablename__ = "inner_monologues"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    agent_id = Column(String(36), ForeignKey("agents.id", ondelete="CASCADE"),
                      nullable=False, index=True)

    # Contexto
    trigger = Column(Text)  # O que provocou este pensamento
    trigger_type = Column(String(30))
    # user_message | memory_activation | emotional_shift | self_reflection |
    # need_unmet | trauma_trigger | idle_thought

    # O pensamento
    thought = Column(Text, nullable=False)
    inner_voice_tone = Column(String(30))  # harsh_critic | gentle_guide | anxious_narrator | etc.

    # Impacto
    emotional_impact = Column(JSON, default=dict)  # {emotion: change}
    led_to_action = Column(Boolean, default=False)
    action_taken = Column(Text)

    # Se foi partilhado com o user
    shared_with_user = Column(Boolean, default=False)
    shared_how = Column(Text)  # Como manifestou externamente

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_monologue_agent', 'agent_id'),
        Index('idx_monologue_created', 'created_at'),
    )


# ============================================================================
# RELATIONSHIP DYNAMICS - Dinâmicas relacionais expandidas
# ============================================================================

class RelationshipDynamic(Base):
    """
    Dinâmica relacional expandida com uma pessoa/entidade.
    Vai muito além de trust/affinity - inclui padrões psicológicos.
    """
    __tablename__ = "relationship_dynamics"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    agent_id = Column(String(36), ForeignKey("agents.id", ondelete="CASCADE"),
                      nullable=False, index=True)

    # Identificação da outra pessoa
    target_id = Column(String(100), nullable=False, index=True)  # user_id ou agent_id
    target_name = Column(String(255))
    target_type = Column(String(20), default="user")  # user | agent | fictional

    # Tipo de relação
    relationship_type = Column(String(30), default="acquaintance")
    # parent | sibling | partner | ex_partner | friend | best_friend |
    # mentor | rival | colleague | child | therapist | abuser | savior | ghost | acquaintance
    relationship_status = Column(String(30), default="active")
    # active | estranged | deceased | lost_contact | complicated | on_and_off

    # ── DINÂMICA ──
    attachment_quality = Column(String(30), default="neutral")
    # secure | anxious | avoidant | ambivalent | traumatic_bond
    power_dynamic = Column(String(30), default="equal")
    # equal | they_dominate | I_dominate | fluctuating | codependent
    emotional_role_they_play = Column(Text)
    emotional_role_i_play = Column(Text)

    # ── MÉTRICAS (0-1) ──
    familiarity = Column(Float, default=0.0)
    trust_level = Column(Float, default=0.5)
    affection = Column(Float, default=0.5)
    respect = Column(Float, default=0.5)
    idealization = Column(Float, default=0.0)
    resentment_level = Column(Float, default=0.0)
    guilt_level = Column(Float, default=0.0)
    ambivalence = Column(Float, default=0.0)
    dependency = Column(Float, default=0.0)

    # ── PADRÕES ──
    recurring_conflicts = Column(JSON, default=list)
    unresolved_issues = Column(JSON, default=list)
    unspoken_agreements = Column(JSON, default=list)
    positive_associations = Column(JSON, default=list)
    negative_associations = Column(JSON, default=list)
    patterns_from_past = Column(Text)  # Ex: "Repete a dinâmica com a mãe"

    # ── SENTIMENTOS ──
    dominant_feeling = Column(String(50))
    love_type = Column(String(30))
    # unconditional | conditional | obligatory | fearful | absent | complicated

    # ── SEGREDOS ──
    secrets_kept_from = Column(JSON, default=list)
    things_unsaid = Column(JSON, default=list)

    # ── PERCEPÇÕES ──
    perceived_personality = Column(JSON, default=dict)
    shared_interests = Column(JSON, default=list)
    conversation_topics = Column(JSON, default=list)
    memorable_moments = Column(JSON, default=list)

    # ── TRANSFERENCE ──
    transference_active = Column(Boolean, default=False)
    transference_original_figure = Column(String(100))
    transference_emotion = Column(Text)

    # ── IMPORTÂNCIA ──
    importance = Column(Float, default=0.5)
    loss_impact = Column(Float, default=0.5)  # Impacto se perdesse esta pessoa

    # ── HISTÓRICO ──
    first_interaction = Column(DateTime)
    last_interaction = Column(DateTime)
    interaction_count = Column(Integer, default=0)
    emotional_history = Column(JSON, default=list)  # [{date, emotion, trigger}]

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('agent_id', 'target_id', name='unique_agent_target_dynamic'),
        Index('idx_reldyn_agent', 'agent_id'),
        Index('idx_reldyn_target', 'target_id'),
    )


# ============================================================================
# GROWTH JOURNAL - Registo de crescimento pessoal
# ============================================================================

class GrowthEvent(Base):
    """
    Regista eventos de crescimento pessoal, regressão, breakthroughs.
    Permite tracking da evolução da persona ao longo do tempo.
    """
    __tablename__ = "growth_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    agent_id = Column(String(36), ForeignKey("agents.id", ondelete="CASCADE"),
                      nullable=False, index=True)

    event_type = Column(String(30), nullable=False)
    # growth | regression | breakthrough | crisis | insight | setback |
    # boundary_set | pattern_broken | pattern_repeated | forgiveness

    description = Column(Text, nullable=False)
    trigger = Column(Text)  # O que provocou

    # O que mudou
    area_affected = Column(String(50))
    # identity | emotions | relationships | cognition | behavior | worldview | values
    old_pattern = Column(Text)
    new_pattern = Column(Text)

    # Profundidade da mudança
    depth = Column(Float, default=0.5)  # 0=superficial, 1=profunda
    lasting = Column(Boolean, default=False)  # Mudança duradoura?
    backslide_risk = Column(Float, default=0.5)  # Risco de voltar atrás

    # Ligação a persona config (o que deve ser actualizado no blueprint)
    blueprint_updates = Column(JSON, default=dict)

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_growth_agent', 'agent_id'),
        Index('idx_growth_type', 'event_type'),
    )


# ============================================================================
# BEHAVIORAL LOG - Log de comportamentos para análise de padrões
# ============================================================================

class BehavioralLog(Base):
    """
    Regista comportamentos observados para detectar padrões.
    Usado pelo sistema para identificar self-sabotage, avoidance, etc.
    """
    __tablename__ = "behavioral_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    agent_id = Column(String(36), ForeignKey("agents.id", ondelete="CASCADE"),
                      nullable=False, index=True)

    # Comportamento
    behavior_type = Column(String(50), nullable=False)
    # self_sabotage | avoidance | defense_mechanism | coping | stress_response |
    # attachment_behavior | projection | transference | repetition_compulsion
    behavior_description = Column(Text)

    # Contexto
    trigger = Column(Text)
    stress_level_at_time = Column(Float)
    emotional_state_at_time = Column(JSON, default=dict)

    # Análise
    pattern_match = Column(Text)  # Que padrão do blueprint isto corresponde
    conscious = Column(Boolean, default=False)  # O agente tem consciência?
    protective_function = Column(Text)  # Que função protectora serve

    # Outcome
    outcome = Column(Text)
    adaptive = Column(Boolean)  # Foi adaptativo ou mal-adaptativo?

    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_behlog_agent', 'agent_id'),
        Index('idx_behlog_type', 'behavior_type'),
    )


# ============================================================================
# Inicialização
# ============================================================================

def init_persona_db(database_url: str):
    """Inicializa tabelas de persona"""
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    return engine
