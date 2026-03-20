-- Script SQL para migrar a base de dados
-- Adiciona as novas colunas micro_agent_prompts e initial_memories

-- Adiciona coluna micro_agent_prompts se não existir
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='agents' AND column_name='micro_agent_prompts'
    ) THEN
        ALTER TABLE agents ADD COLUMN micro_agent_prompts TEXT;
    END IF;
END $$;

-- Adiciona coluna initial_memories se não existir
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='agents' AND column_name='initial_memories'
    ) THEN
        ALTER TABLE agents ADD COLUMN initial_memories TEXT;
    END IF;
END $$;
