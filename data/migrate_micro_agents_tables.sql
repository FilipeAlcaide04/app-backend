-- ============================================================================
-- MIGRAÇÃO: Criar tabelas para cada micro agente seguindo padrão logic_agent
-- ============================================================================
-- Cada micro agente terá sua própria tabela linkada ao utilizador (user_id)
-- Objetivo: Criar agentes com memórias que funcionem como uma verdadeira pessoa
-- ============================================================================

-- Tabela: thinking_agent
CREATE TABLE IF NOT EXISTS public.thinking_agent (
    id SERIAL PRIMARY KEY,
    persona_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    agent_name VARCHAR(255) NOT NULL DEFAULT 'thinking',
    prompt TEXT NOT NULL,
    temperature DOUBLE PRECISION DEFAULT 0.5 NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT thinking_agent_persona_user_unique UNIQUE (persona_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_thinking_agent_persona_id ON public.thinking_agent(persona_id);
CREATE INDEX IF NOT EXISTS idx_thinking_agent_user_id ON public.thinking_agent(user_id);
CREATE INDEX IF NOT EXISTS idx_thinking_agent_agent_name ON public.thinking_agent(agent_name);

-- Tabela: knowledge_agent
CREATE TABLE IF NOT EXISTS public.knowledge_agent (
    id SERIAL PRIMARY KEY,
    persona_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    agent_name VARCHAR(255) NOT NULL DEFAULT 'knowledge',
    prompt TEXT NOT NULL,
    temperature DOUBLE PRECISION DEFAULT 0.3 NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT knowledge_agent_persona_user_unique UNIQUE (persona_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_knowledge_agent_persona_id ON public.knowledge_agent(persona_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_agent_user_id ON public.knowledge_agent(user_id);
CREATE INDEX IF NOT EXISTS idx_knowledge_agent_agent_name ON public.knowledge_agent(agent_name);

-- Tabela: expression_agent
CREATE TABLE IF NOT EXISTS public.expression_agent (
    id SERIAL PRIMARY KEY,
    persona_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    agent_name VARCHAR(255) NOT NULL DEFAULT 'expression',
    prompt TEXT NOT NULL,
    temperature DOUBLE PRECISION DEFAULT 0.2 NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT expression_agent_persona_user_unique UNIQUE (persona_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_expression_agent_persona_id ON public.expression_agent(persona_id);
CREATE INDEX IF NOT EXISTS idx_expression_agent_user_id ON public.expression_agent(user_id);
CREATE INDEX IF NOT EXISTS idx_expression_agent_agent_name ON public.expression_agent(agent_name);

-- Tabela: planner_agent
CREATE TABLE IF NOT EXISTS public.planner_agent (
    id SERIAL PRIMARY KEY,
    persona_id VARCHAR(255) NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    agent_name VARCHAR(255) NOT NULL DEFAULT 'planner',
    prompt TEXT NOT NULL,
    temperature DOUBLE PRECISION DEFAULT 0.4 NOT NULL,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT now() NOT NULL,
    CONSTRAINT planner_agent_persona_user_unique UNIQUE (persona_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_planner_agent_persona_id ON public.planner_agent(persona_id);
CREATE INDEX IF NOT EXISTS idx_planner_agent_user_id ON public.planner_agent(user_id);
CREATE INDEX IF NOT EXISTS idx_planner_agent_agent_name ON public.planner_agent(agent_name);

-- Atualizar tabela logic_agent para incluir user_id (se ainda não existir)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'logic_agent' AND column_name = 'user_id'
    ) THEN
        ALTER TABLE public.logic_agent ADD COLUMN user_id VARCHAR(255);
        CREATE INDEX IF NOT EXISTS idx_logic_agent_user_id ON public.logic_agent(user_id);
    END IF;
END $$;

-- Criar sequências se não existirem
CREATE SEQUENCE IF NOT EXISTS public.thinking_agent_id_seq OWNED BY public.thinking_agent.id;
CREATE SEQUENCE IF NOT EXISTS public.knowledge_agent_id_seq OWNED BY public.knowledge_agent.id;
CREATE SEQUENCE IF NOT EXISTS public.expression_agent_id_seq OWNED BY public.expression_agent.id;
CREATE SEQUENCE IF NOT EXISTS public.planner_agent_id_seq OWNED BY public.planner_agent.id;

-- ============================================================================
-- COMENTÁRIOS
-- ============================================================================
COMMENT ON TABLE public.thinking_agent IS 'Micro agente de pensamento profundo e reflexão - linkado ao utilizador';
COMMENT ON TABLE public.knowledge_agent IS 'Micro agente de conhecimento e busca de informação - linkado ao utilizador';
COMMENT ON TABLE public.expression_agent IS 'Micro agente de análise de expressões emocionais - linkado ao utilizador';
COMMENT ON TABLE public.planner_agent IS 'Micro agente de planeamento e organização - linkado ao utilizador';
