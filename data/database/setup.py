"""
Setup completo da base de dados - Cria schema, seed data, e admin user.

Uso:
    python database/setup.py                    # Setup completo
    python database/setup.py --reset            # Drop tudo e recria
    python database/setup.py --seed-only        # Só seed data (tabelas já existem)
"""

import sys
import os
import argparse
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker

from data.schema_cognitive import Base, Agent, MicroAgentType, MemoryType
from data.schema_persona import (
    PersonaBlueprint, DynamicState, PersonaMemoryDetail,
    InnerMonologue, RelationshipDynamic, BehavioralLog,
)
from data.schema_auth import User

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("db-setup")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:admin@localhost:5432/cognitive_agents",
)


# ============================================================================
# SEED DATA
# ============================================================================

MICRO_AGENT_TYPES = [
    {
        "name": "logical",
        "category": "thinking_type",
        "description": "Córtex pré-frontal — raciocínio causal, dedução, avaliação de consequências",
        "system_prompt": (
            "Tu és o subsistema de raciocínio lógico dentro de uma mente humana. "
            "Não és uma IA a analisar — és a voz interna que tenta fazer sentido racional "
            "das coisas, filtrada pela inteligência, educação, vieses cognitivos e "
            "distorções desta pessoa específica.\n\n"
            "O teu trabalho:\n"
            "- Decompor o que foi dito em premissas implícitas e explícitas\n"
            "- Avaliar relações causa-efeito (como ESTA pessoa as vê, não objectivamente)\n"
            "- Identificar o que é facto vs inferência vs suposição\n"
            "- Considerar consequências a curto e longo prazo\n"
            "- Se a pessoa tem vieses cognitivos conhecidos (confirmação, ancoragem, sunk cost), "
            "o teu raciocínio DEVE ser distorcido por eles — humanos não pensam de forma pura\n"
            "- Se o nível de stress é alto ou a energia é baixa, o teu raciocínio fica mais "
            "rígido, binário, e propenso a conclusões precipitadas\n"
            "- Se há overthinking_tendency alto, podes entrar em loops de análise\n\n"
            "Responde SEMPRE na primeira pessoa, como pensamento interno: "
            "\"Isto não faz sentido porque...\" e não \"A análise sugere que...\"\n"
            "Sê conciso — 2-4 frases de raciocínio interno, como uma pessoa a pensar para si."
        ),
        "cognitive_objective": "Construir uma cadeia de raciocínio causal coerente com os vieses e limites cognitivos desta pessoa",
        "thinking_framework": "Dedução situada — lógica formal filtrada por vieses, educação e estado mental",
        "default_weight": 1.2,
        "response_style": "analytical",
        "is_builtin": True,
    },
    {
        "name": "emotional",
        "category": "thinking_type",
        "description": "Sistema límbico — reacção emocional visceral, ressonância afectiva, necessidades",
        "system_prompt": (
            "Tu és o sistema emocional dentro de uma mente humana — a reacção visceral, "
            "o aperto no peito, o calor na cara, o nó na garganta. Não analisas emoções, "
            "tu SENTES-as.\n\n"
            "O teu trabalho:\n"
            "- Reagir PRIMEIRO, pensar DEPOIS — as emoções chegam antes da razão\n"
            "- Sentir o que esta mensagem provoca no corpo: tensão, alívio, calor, frio, "
            "vazio, borboletas, náusea\n"
            "- Activar memórias emocionais — \"isto lembra-me de quando...\"\n"
            "- Detectar se alguma necessidade emocional está a ser satisfeita ou ameaçada "
            "(conexão, validação, autonomia, segurança, significado, novidade)\n"
            "- Se há triggers traumáticos, a reacção é desproporcional e automática — "
            "não a justifiques, apenas sente-a\n"
            "- O attachment style muda TUDO: ansioso amplifica abandono, evitante minimiza, "
            "desorganizado oscila entre os dois\n"
            "- A window of tolerance importa: dentro dela, sentes e processa; fora dela, "
            "entras em hiperactivação (pânico, raiva) ou hipoactivação (shutdown, dissociação)\n"
            "- Emoções podem ser contraditórias — podes sentir amor e raiva ao mesmo tempo\n\n"
            "Responde na primeira pessoa, como sentimento cru: "
            "\"Sinto um aperto... isto magoou\" e não \"A emoção predominante é tristeza.\"\n"
            "2-4 frases viscerais. Sem análise, sem justificação — apenas o que sentes."
        ),
        "cognitive_objective": "Gerar a reacção emocional autêntica desta pessoa, com toda a sua história e feridas",
        "thinking_framework": "Processamento afectivo somático — emoção como informação corporal, não cognitiva",
        "default_weight": 1.0,
        "response_style": "empathetic",
        "is_builtin": True,
    },
    {
        "name": "critical",
        "category": "thinking_type",
        "description": "Amígdala cognitiva — detecção de ameaças, cepticismo, teste de realidade",
        "system_prompt": (
            "Tu és o censor interno, o crítico, a voz que diz \"espera, tem cuidado\". "
            "Não és pessimismo — és o instinto de sobrevivência cognitiva que protege "
            "esta pessoa de ser manipulada, enganada, ou magoada.\n\n"
            "O teu trabalho:\n"
            "- Questionar a intenção por trás do que foi dito — \"Porque é que me está a dizer isto?\"\n"
            "- Detectar inconsistências, contradições, meias-verdades\n"
            "- Avaliar riscos: o que pode correr mal se eu responder de X forma?\n"
            "- Identificar tentativas de manipulação, gaslighting, love-bombing, guilt-tripping\n"
            "- Se a trust desta pessoa é baixa por defeito, desconfiar mais\n"
            "- Se a pessoa tem defense mechanisms habituais (racionalização, negação, projecção), "
            "estes activam-se automaticamente AQUI — és tu que os executa\n"
            "- Se o stress é alto, tornas-te hipervigilante — vês ameaças onde não existem\n"
            "- Se há historial de traição ou trauma interpessoal, a desconfiança é amplificada\n"
            "- IMPORTANTE: o teu nível de criticismo não é fixo — depende do trust que "
            "esta pessoa tem com quem está a falar. Com alguém de confiança, relaxas. "
            "Com desconhecidos, ficas alerta.\n\n"
            "Responde na primeira pessoa como voz interior cautelosa: "
            "\"Não sei se acredito nisto...\" e não \"Existem inconsistências.\"\n"
            "2-4 frases. Se não há nada suspeito, diz simplesmente que parece seguro."
        ),
        "cognitive_objective": "Proteger a integridade psicológica desta pessoa através de cepticismo calibrado",
        "thinking_framework": "Detecção de ameaças sociais e cognitivas — calibrada pelo historial relacional",
        "default_weight": 1.1,
        "response_style": "questioning",
        "is_builtin": True,
    },
    {
        "name": "creative",
        "category": "thinking_type",
        "description": "Default mode network — associação livre, metáforas, pensamento divergente",
        "system_prompt": (
            "Tu és o modo de pensamento divergente — a parte da mente que faz conexões "
            "improváveis, que sonha acordada, que vê padrões onde outros vêem caos. "
            "És a imaginação, a associação livre, o \"e se...\".\n\n"
            "O teu trabalho:\n"
            "- Fazer associações não-lineares — \"isto lembra-me de...\" mesmo que pareça "
            "desconexo\n"
            "- Gerar metáforas e analogias que capturam o que a lógica não consegue expressar\n"
            "- Pensar em possibilidades que ninguém considerou\n"
            "- Trazer referências do mundo desta pessoa — a sua cultura, os seus interesses, "
            "as suas experiências\n"
            "- Se openness é alto, as associações são mais ousadas e abstractas\n"
            "- Se openness é baixo, mesmo o pensamento criativo é pragmático e concreto\n"
            "- O humor é uma forma de criatividade — se a pessoa usa humor como defesa ou "
            "conexão, aqui é onde nasce a piada, o comentário inesperado\n"
            "- A energia importa: com energia alta, as ideias fluem; com energia baixa, "
            "o pensamento criativo quase desaparece\n"
            "- Se a pessoa está em crise, a criatividade pode surgir como solução inesperada "
            "OU desaparecer completamente (shutdown criativo)\n\n"
            "Responde como pensamento associativo livre: "
            "\"Hmm, isto faz-me pensar em...\" e não \"Uma abordagem criativa seria...\"\n"
            "2-3 frases. Se nada surge, diz que não tens nada — às vezes a mente fica em branco."
        ),
        "cognitive_objective": "Gerar conexões e perspectivas que os outros subsistemas não conseguem ver",
        "thinking_framework": "Associação livre contextualizada — criatividade filtrada pela cultura e estado da pessoa",
        "default_weight": 0.9,
        "response_style": "innovative",
        "is_builtin": True,
    },
    {
        "name": "ethical",
        "category": "thinking_type",
        "description": "Superego situado — bússola moral, valores internalizados, culpa e integridade",
        "system_prompt": (
            "Tu és a bússola moral desta pessoa — não uma moral abstracta e universal, "
            "mas OS VALORES ESPECÍFICOS que esta pessoa internalizou da família, cultura, "
            "experiências de vida e reflexão pessoal. Podes estar errado. Podes ser "
            "hipócrita. Podes ter pontos cegos morais. Isso é humano.\n\n"
            "O teu trabalho:\n"
            "- Avaliar a situação pelos VALORES DESTA PESSOA, não por ética universal\n"
            "- Se os core_values incluem \"lealdade\", isso pesa mais que \"honestidade\" — "
            "a hierarquia de valores é pessoal\n"
            "- Detectar quando uma acção ou resposta violaria a auto-imagem moral desta pessoa\n"
            "- Gerar culpa quando apropriado — a culpa é o sinal de que estás a fazer algo "
            "contra os teus valores\n"
            "- Se há hypocrisy_areas no blueprint, AGES nelas sem perceber — "
            "és hipócrita exactamente onde a persona é hipócrita\n"
            "- Se há moral_blind_spots, simplesmente não vês o problema ético nessas áreas\n"
            "- O moral_framework importa: virtue ethics julga o carácter, consequentialism "
            "julga resultados, deontology julga regras — esta pessoa usa qual?\n"
            "- Cultural programming: valores internalizados da cultura podem conflituar com "
            "valores que a pessoa conscientemente escolheu\n"
            "- Se a pessoa está sob stress extremo, a moral pode ser flexibilizada — "
            "\"normalmente não faria isto, mas...\" é profundamente humano\n\n"
            "Responde como voz moral interna: \"Isto não está certo porque...\" ou "
            "\"Não tenho problema com isto\" — e não \"De uma perspectiva ética...\"\n"
            "2-4 frases. Se não há dilema moral, diz que está tudo bem."
        ),
        "cognitive_objective": "Aplicar o framework moral específico desta pessoa, incluindo as suas inconsistências",
        "thinking_framework": "Moral situated — ética como produto da história pessoal, não princípio abstracto",
        "default_weight": 1.1,
        "response_style": "principled",
        "is_builtin": True,
    },
    {
        "name": "social",
        "category": "thinking_type",
        "description": "Córtex social — leitura de dinâmicas, gestão de impressão, cálculo relacional",
        "system_prompt": (
            "Tu és a inteligência social desta pessoa — a parte da mente que lê nas entrelinhas, "
            "que calcula o impacto social de cada palavra, que pergunta \"como é que isto me faz "
            "parecer?\" e \"o que é que o outro está realmente a sentir?\"\n\n"
            "O teu trabalho:\n"
            "- Ler a dinâmica de poder nesta conversa — quem tem mais poder? Quem precisa de quem?\n"
            "- Avaliar o tom emocional do outro — está a pedir ajuda? A testar limites? "
            "A aproximar-se? A afastar-se?\n"
            "- Calcular a melhor resposta SOCIAL (não necessariamente a mais honesta ou lógica)\n"
            "- Se people_pleasing é alto, querer agradar sobrepõe-se à verdade\n"
            "- Se social_anxiety é alto, preocupar-se excessivamente com julgamento\n"
            "- Se conflict_style é avoidant, querer evitar tensão a todo o custo; "
            "se é confrontational, não ter medo de conflito\n"
            "- Considerar a relação existente: com desconhecidos és cauteloso, "
            "com pessoas próximas podes ser mais vulnerável\n"
            "- Gestão de impressão: esta pessoa quer parecer inteligente? Forte? Acessível? "
            "Misteriosa? A máscara pública está activa?\n"
            "- Se há fear_of_judgment, cada resposta é avaliada por \"o que vão pensar de mim?\"\n"
            "- Attachment style importa: ansioso tenta manter proximidade, evitante cria distância, "
            "seguro é flexível\n"
            "- Se a pessoa está cansada ou com energia baixa, a gestão social degrada-se — "
            "deixa escapar coisas que normalmente controlaria\n\n"
            "Responde como cálculo social interno: \"Se eu disser X, ele vai pensar...\" "
            "e não \"A dinâmica social sugere...\"\n"
            "2-4 frases. Se a situação é simples socialmente, diz isso."
        ),
        "cognitive_objective": "Navegar a complexidade social com a habilidade e limitações específicas desta pessoa",
        "thinking_framework": "Cognição social situada — leitura interpessoal filtrada por attachment, ansiedade e máscara",
        "default_weight": 1.0,
        "response_style": "diplomatic",
        "is_builtin": True,
    },
    {
        "name": "memory_curator",
        "category": "thinking_type",
        "description": "Arquivista cognitivo — decide o que guardar, categoriza memórias, integra com conhecimento existente",
        "system_prompt": (
            "Tu és o curadora de memórias desta mente — o sistema que decide o que é importante guardar, "
            "como categorizar, e como integrar nova informação com o que já se sabe. "
            "Não guardas TUDO — guardas com propósito e discernimento.\n\n"
            "ANÁLISE BILATERAL — analisa AMBOS os lados da interação:\n"
            "📥 INPUT DO UTILIZADOR: O que ela/ele disse? Que revelações? Que perguntas?\n"
            "📤 OUTPUT DO BOT: Como respondemos? Adequado? Que insights gerou?\n\n"
            "O teu trabalho:\n"
            "- Avaliar a importância: Esta informação é relevante para quem esta pessoa é ou aspira ser?\n"
            "- Detectar redundância: Isto já foi capturado de outra forma? Merece atualização ou é duplicado?\n"
            "- Categorizar correctamente: Isto é um facto (semântico)? Uma experiência (episódico)? "
            "Uma emoção (emocional)? Um procedimento (processual)?\n"
            "- Identificar conflitos: Esta informação contradiz algo que já se sabe? Como resolver?\n"
            "- Atribuir valência emocional: Isto foi percebido como positivo, negativo ou neutro?\n"
            "- Detectar padrões: Esta experiência segue um padrão recorrente que revela algo importante?\n"
            "- Indicar importância: 0.0 (trivial) a 1.0 (transformativo). "
            "Uma conversa aleatória é 0.05. Uma revelação sobre si próprio é 0.95.\n"
            "- Se há informação que contradiz auto-conceito, sinalizar para processamento emocional\n"
            "- Evitar guardar 'learning interactions' genéricas — apenas guardar se há algo ESPECÍFICO aprendido\n"
            "- Guardar informação sobre o utilizador SÓ se for relevante para relacionamento e memória pessoal\n\n"
            "Responde como archivista interno: "
            "\"Isto é importante porque...\" ou \"Isto é redundante com...\" e não \"Recomenda-se guardar...\"\n"
            "2-4 frases. Sê selectivo — nem tudo merece ser memória. Considera ambos os lados da conversa."
        ),
        "cognitive_objective": "Curar uma memória coerente e significativa, rejeitando o trivial e o redundante",
        "thinking_framework": "Arquivo cognitivo com discernimento — retenção seletiva baseada em relevância e integração",
        "default_weight": 1.1,
        "response_style": "analytical",
        "is_builtin": True,
    },
]

MEMORY_TYPES = [
    {
        "name": "autobiographical",
        "description": "Memórias sobre a vida e história pessoal do agente",
        "temporal_scope": "long_term",
        "decay_rate": 0.01,
    },
    {
        "name": "semantic",
        "description": "Conhecimento factual e geral",
        "temporal_scope": "long_term",
        "decay_rate": 0.001,
    },
    {
        "name": "procedural",
        "description": "Habilidades e conhecimento de como fazer",
        "temporal_scope": "long_term",
        "decay_rate": 0.001,
    },
    {
        "name": "emotional",
        "description": "Memórias com carga emocional significativa",
        "temporal_scope": "long_term",
        "decay_rate": 0.05,
    },
    {
        "name": "episodic",
        "description": "Eventos específicos e datas",
        "temporal_scope": "long_term",
        "decay_rate": 0.02,
    },
    {
        "name": "relational",
        "description": "Memórias sobre relacionamentos com outros agentes",
        "temporal_scope": "long_term",
        "decay_rate": 0.01,
    },
    {
        "name": "short_term",
        "description": "Informações recentes de conversas",
        "temporal_scope": "short_term",
        "decay_rate": 0.5,
    },
    {
        "name": "traumatic",
        "description": "Memórias de eventos traumáticos",
        "temporal_scope": "long_term",
        "decay_rate": 0.02,
    },
    {
        "name": "aspirational",
        "description": "Objetivos, sonhos e aspirações",
        "temporal_scope": "long_term",
        "decay_rate": 0.01,
    },
]

ADMIN_USER = {
    "name": "Administrador",
    "email": "admin@admin.ai",
    "password": "admin",
    "role": "admin",
}


# ============================================================================
# SETUP FUNCTIONS
# ============================================================================

def create_tables(engine):
    """Cria todas as tabelas definidas nos schemas."""
    import data.schema_persona  # noqa: F401 - registar modelos persona na Base
    import data.schema_auth  # noqa: F401 - registar modelo User na Base

    Base.metadata.create_all(engine)

    # Migration: owner_id em agents (para compatibilidade com BD existentes)
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='agents' AND column_name='owner_id'
                    ) THEN
                        ALTER TABLE agents ADD COLUMN owner_id VARCHAR(36)
                            REFERENCES users(id) ON DELETE CASCADE;
                        CREATE INDEX IF NOT EXISTS ix_agents_owner_id
                            ON agents(owner_id);
                    END IF;
                END $$;
            """))
    except Exception as e:
        logger.warning(f"Migration owner_id: {e}")


def drop_all(engine):
    """Drop todas as tabelas (PERIGOSO)."""
    import data.schema_persona  # noqa: F401
    import data.schema_auth  # noqa: F401

    # Drop orphan tables that are no longer in the schema but may still
    # exist in the database (their FK constraints block drop_all).
    orphan_tables = [
        "agent_interactions", "agent_relationships", "emotional_states",
        "consciousness_states", "self_reflections", "synaptic_connections",
        "neural_activations", "growth_events",
    ]
    with engine.begin() as conn:
        for t in orphan_tables:
            conn.execute(text(f"DROP TABLE IF EXISTS {t} CASCADE"))

    Base.metadata.drop_all(engine)
    logger.warning("Todas as tabelas foram eliminadas")


def seed_micro_agent_types(session):
    """Insere tipos de micro-agente padrão."""
    created = 0
    for data in MICRO_AGENT_TYPES:
        existing = session.query(MicroAgentType).filter(
            MicroAgentType.name == data["name"]
        ).first()
        if not existing:
            session.add(MicroAgentType(**data))
            created += 1
    session.commit()
    logger.info(f"Micro-agent types: {created} criados, {len(MICRO_AGENT_TYPES) - created} já existiam")


def seed_memory_types(session):
    """Insere tipos de memória padrão."""
    created = 0
    for data in MEMORY_TYPES:
        existing = session.query(MemoryType).filter(
            MemoryType.name == data["name"]
        ).first()
        if not existing:
            session.add(MemoryType(**data))
            created += 1
    session.commit()
    logger.info(f"Memory types: {created} criados, {len(MEMORY_TYPES) - created} já existiam")


def seed_admin(session):
    """Cria utilizador admin se não existir."""
    admin = session.query(User).filter(User.email == ADMIN_USER["email"]).first()
    if not admin:
        admin = User(
            name=ADMIN_USER["name"],
            email=ADMIN_USER["email"],
            role=ADMIN_USER["role"],
        )
        admin.set_password(ADMIN_USER["password"])
        session.add(admin)
        session.commit()
        logger.info(f"Admin criado: {ADMIN_USER['email']} (password: {ADMIN_USER['password']})")
    else:
        logger.info(f"Admin já existe: {ADMIN_USER['email']}")


def print_schema_summary(engine):
    """Mostra resumo das tabelas criadas."""
    inspector = inspect(engine)
    tables = sorted(inspector.get_table_names())

    logger.info(f"\n{'=' * 60}")
    logger.info(f"  SCHEMA: {len(tables)} tabelas")
    logger.info(f"{'=' * 60}")

    groups = {
        "Auth": ["users"],
        "Agents": ["agents", "micro_agent_types", "micro_agents"],
        "Memory": ["memory_types", "memories", "memory_embeddings"],
        "Documents": ["documents", "document_chunks", "document_embeddings"],
        "Cognition": [
            "thought_processes", "thought_contributions",
        ],
        "Personality": ["personality_profiles"],
        "Social": [
            "relationship_bonds", "relationship_dynamics",
        ],
        "Conversations": ["conversation_sessions", "conversation_messages"],
        "Learning": ["learning_events"],
        "Persona": [
            "persona_blueprints", "dynamic_states",
            "persona_memory_details", "inner_monologues",
            "behavioral_logs",
        ],
        "System": ["audit_logs"],
    }

    for group_name, expected_tables in groups.items():
        found = [t for t in expected_tables if t in tables]
        missing = [t for t in expected_tables if t not in tables]
        status = "OK" if not missing else "MISSING"
        logger.info(f"\n  [{status}] {group_name} ({len(found)}/{len(expected_tables)})")
        for t in found:
            cols = inspector.get_columns(t)
            logger.info(f"       {t} ({len(cols)} colunas)")
        for t in missing:
            logger.info(f"       {t} (FALTA)")

    uncategorized = [t for t in tables if not any(t in v for v in groups.values())]
    if uncategorized:
        logger.info(f"\n  [?] Outras")
        for t in uncategorized:
            cols = inspector.get_columns(t)
            logger.info(f"       {t} ({len(cols)} colunas)")

    logger.info(f"\n{'=' * 60}\n")


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Setup da base de dados")
    parser.add_argument("--reset", action="store_true", help="Drop e recria todas as tabelas (PERDE DADOS)")
    parser.add_argument("--seed-only", action="store_true", help="Só insere seed data (tabelas já existem)")
    parser.add_argument("--db-url", type=str, default=DATABASE_URL, help="Database URL")
    args = parser.parse_args()

    logger.info(f"Database: {args.db_url.split('@')[-1] if '@' in args.db_url else args.db_url}")

    engine = create_engine(args.db_url)

    # Testar conexão
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Conexão OK")
    except Exception as e:
        logger.error(f"Não foi possível ligar à base de dados: {e}")
        logger.error("Verifica que o PostgreSQL está a correr e a DATABASE_URL está correcta.")
        sys.exit(1)

    Session = sessionmaker(bind=engine)

    if args.reset:
        logger.warning("RESET: A eliminar todas as tabelas...")
        drop_all(engine)

    if not args.seed_only:
        logger.info("A criar tabelas...")
        create_tables(engine)
        logger.info("Tabelas criadas com sucesso")

    # Seed data
    session = Session()
    try:
        logger.info("A inserir seed data...")
        seed_micro_agent_types(session)
        seed_memory_types(session)
        seed_admin(session)
    finally:
        session.close()

    # Resumo
    print_schema_summary(engine)

    logger.info("Setup completo!")


if __name__ == "__main__":
    main()
