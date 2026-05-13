# Database Schema - Sistema de Humanos Virtuais

PostgreSQL database com 3 camadas de schema: **Auth**, **Cognitive** e **Persona**.

## Arquitectura

```
users (auth)
  └── agents (cognitive core)
        ├── micro_agent_types / micro_agents (pensamento paralelo)
        ├── memory_types / memories / memory_embeddings (sistema de memória)
        ├── documents / document_chunks / document_embeddings (RAG)
        ├── thought_processes / thought_contributions (registo cognitivo)
        ├── conversation_sessions / conversation_messages (chat persistente)
        ├── personality_profiles (Big Five + facetas)
        ├── relationship_bonds (vínculos com utilizadores)
        ├── learning_events (feedback loop)
        ├── audit_logs
        ├── persona_blueprints (DNA estático - identidade, personalidade, worldview)
        ├── dynamic_states (estado runtime - energia, emoções, necessidades)
        ├── persona_memory_details (memórias expandidas com trauma, sensorial)
        ├── inner_monologues (pensamentos autónomos)
        ├── relationship_dynamics (dinâmicas relacionais profundas)
        └── behavioral_logs (padrões comportamentais)
```

## Tabelas por Camada

### 1. Auth (`schema_auth.py`)

| Tabela | Descrição |
|--------|-----------|
| `users` | Utilizadores com bcrypt passwords, roles (admin/user), OAuth support |

### 2. Cognitive (`schema_cognitive.py`)

| Tabela | Descrição |
|--------|-----------|
| `agents` | Agente principal - identidade, Big Five, thinking_style, estado |
| `micro_agent_types` | Tipos de micro-agente (logical, emotional, creative, critical, ethical, social) |
| `micro_agents` | Instância de micro-agente dentro de um agente |
| `memory_types` | Classificação semântica de memórias (autobiographical, semantic, procedural, emotional) |
| `memories` | Memórias persistentes com valência emocional e importância |
| `memory_embeddings` | Embeddings vectoriais para busca semântica de memórias |
| `documents` | Documentos privados por agente (PDF, TXT, DOCX) |
| `document_chunks` | Chunks de documentos para processamento RAG |
| `document_embeddings` | Embeddings de chunks para busca semântica |
| `thought_processes` | Registo de processos de pensamento (query → debate → resposta) |
| `thought_contributions` | Contribuição de cada micro-agente para o pensamento |
| `audit_logs` | Log de auditoria de ações |
| `personality_profiles` | Big Five com facetas, valores, crenças, estilo de comunicação |
| `relationship_bonds` | Vínculos com utilizadores (familiarity, trust, affection) |
| `learning_events` | Eventos de aprendizagem por feedback |
| `conversation_sessions` | Sessões de conversa com working memory |
| `conversation_messages` | Mensagens individuais (role, content, emoção detectada) |

### 3. Persona (`schema_persona.py`)

| Tabela | Descrição |
|--------|-----------|
| `persona_blueprints` | DNA completo: identity, personality_full, emotional_config, cognitive_config, social_config, behavioral_config, worldview, growth_arc, behavior_prompts, meta (12 colunas JSON) |
| `dynamic_states` | Estado runtime: energia, necessidades (connection, validation, autonomy, meaning, novelty, safety), stress, PAD, Plutchik, emoções complexas, defesas, humor |
| `persona_memory_details` | Extensão de memórias: trauma (tipo, severidade, triggers, crenças formadas), fiabilidade, sensorial, narrativa |
| `inner_monologues` | Pensamentos autónomos internos |
| `relationship_dynamics` | Dinâmicas expandidas: attachment_quality, power_dynamic, transference, segredos |
| `behavioral_logs` | Log de comportamentos para detectar padrões (self-sabotage, avoidance, defesa) |

## PersonaBlueprint - Secções JSON

O `persona_blueprints` é o coração do sistema. Cada coluna JSON contém:

| Secção | Conteúdo |
|--------|----------|
| `identity` | self_concept, inner_voice, languages, impostor_syndrome, gender, pronouns |
| `internal_states_config` | energy (baseline, drain_rate, recovery), emotional_needs (decay, threshold), mental_health |
| `personality_full` | big_five + facets, attachment_style, contradictions, masks (public/private/shadow), humor, defense_mechanisms, values, fears, motivations |
| `memory_config` | memory_biases, core_memories, suppressed_memories, procedural_knowledge |
| `emotional_config` | PAD baseline, triggers, regulation strategies, emotional_intelligence |
| `cognitive_config` | biases, limiting_beliefs, inner_narrative, decision_making, locus_of_control |
| `social_config` | communication_style, apology_style, social_energy, relational_patterns |
| `behavioral_config` | stress_responses, self_sabotage_patterns, coping_mechanisms, avoidance_patterns |
| `worldview` | philosophical_orientation, moral_framework, beliefs_about_world/people/self |
| `growth_arc` | current_life_stage, developmental_tasks, therapy_history, unmet_needs, regrets, secret_hopes |
| `behavior_prompts` | voice, rules, consistency_anchors, emotional_state_modifiers |
| `meta` | version, complexity_level, realism_target, allow_flags |

## DynamicState - O que muda a cada interação

Estado runtime com ~50 colunas que mudam em tempo real:
- **Energia**: `energy_level` (0-1)
- **Necessidades**: connection, validation, autonomy, meaning, novelty, safety (0-1 cada)
- **Stress**: `current_stress_load`, `accumulated_stressors`, `window_position`
- **Emoções PAD**: valence, arousal, dominance
- **Plutchik**: joy, sadness, anger, fear, surprise, disgust, trust, anticipation
- **Complexas**: love, guilt, shame, pride, envy, gratitude, resentment, contempt, loneliness, hope, nostalgia
- **Estado**: primary_emotion, intoxication_state, active_defenses, current_mood

## Setup

```bash
cd /home/falcaide/coding_space/app-backend
python database/setup.py
```

Isto cria todas as tabelas, tipos de memória, tipos de micro-agente, e o utilizador admin.
