-- Migration for Brazil Module & Additional Features - Copa 2026

-- 1. Create table for Brazil scorers/assistants predictions per match
CREATE TABLE IF NOT EXISTS brasil_palpites_goleadores (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    participante_nome TEXT NOT NULL,
    jogo_id TEXT NOT NULL,
    gols_brasil_apostados INTEGER NOT NULL DEFAULT 0,
    goleadores JSONB NOT NULL DEFAULT '[]',
    assistentes JSONB NOT NULL DEFAULT '[]',
    pontos_ganhos INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(participante_nome, jogo_id)
);

-- 2. Create table for Brazil match actual outcomes (scorers, assistants, etc.)
CREATE TABLE IF NOT EXISTS brasil_resultados_goleadores (
    jogo_id TEXT PRIMARY KEY,
    goleadores_reais JSONB DEFAULT '[]',
    assistentes_reais JSONB DEFAULT '[]',
    primeiro_gol_copa TEXT,
    encerrado BOOLEAN DEFAULT FALSE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Create table for Classic predictions of tournament scorers and golden goal
CREATE TABLE IF NOT EXISTS brasil_palpites_classicos (
    participante_nome TEXT PRIMARY KEY,
    artilheiro_brasil_copa TEXT,
    artilheiro_geral_copa TEXT,
    gol_de_ouro TEXT,
    pontos_artilheiro_brasil INTEGER DEFAULT 0,
    pontos_artilheiro_geral INTEGER DEFAULT 0,
    pontos_gol_de_ouro INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Create table for ranking snapshots per round
CREATE TABLE IF NOT EXISTS ranking_snapshots (
    rodada TEXT NOT NULL,
    participante_nome TEXT NOT NULL,
    posicao INTEGER NOT NULL,
    pontos INTEGER NOT NULL,
    captured_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (rodada, participante_nome)
);

-- 5. Create table for real-time match comments
CREATE TABLE IF NOT EXISTS comentarios_jogo (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    jogo_id TEXT NOT NULL,
    participante_nome TEXT NOT NULL,
    texto TEXT NOT NULL,
    deletado BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT texto_max_140 CHECK (char_length(texto) <= 140)
);

-- 6. Add optional fields to existing bolao_matches
ALTER TABLE bolao_matches ADD COLUMN IF NOT EXISTS has_custom_lock BOOLEAN DEFAULT FALSE;
ALTER TABLE bolao_matches ADD COLUMN IF NOT EXISTS stadium TEXT;
ALTER TABLE bolao_matches ADD COLUMN IF NOT EXISTS modo_relampago_ativo BOOLEAN DEFAULT FALSE;
ALTER TABLE bolao_matches ADD COLUMN IF NOT EXISTS placar_intervalo_mandante INTEGER;
ALTER TABLE bolao_matches ADD COLUMN IF NOT EXISTS placar_intervalo_visitante INTEGER;

-- 7. Enable Row Level Security on Brasil module tables
ALTER TABLE brasil_palpites_goleadores ENABLE ROW LEVEL SECURITY;
ALTER TABLE brasil_resultados_goleadores ENABLE ROW LEVEL SECURITY;
ALTER TABLE brasil_palpites_classicos ENABLE ROW LEVEL SECURITY;
ALTER TABLE ranking_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE comentarios_jogo ENABLE ROW LEVEL SECURITY;
