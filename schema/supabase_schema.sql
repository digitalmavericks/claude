-- Self-Improving Prompting System - Supabase Schema
-- Deploy via: Supabase Dashboard → SQL Editor → paste and run

-- 1. Prompt Population (MAP-Elites archive)
CREATE TABLE IF NOT EXISTS prompt_population (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_name TEXT NOT NULL,
    task_type TEXT NOT NULL,
    tone TEXT NOT NULL DEFAULT 'default',
    model_target TEXT NOT NULL DEFAULT 'claude-sonnet-4-6',
    generation INTEGER NOT NULL DEFAULT 0,
    prompt_text TEXT NOT NULL,
    score FLOAT NOT NULL DEFAULT 0.0,
    score_breakdown JSONB DEFAULT '{}'::jsonb,
    parent_id UUID REFERENCES prompt_population(id),
    mutation_type TEXT,
    mutation_description TEXT,
    niche_key TEXT GENERATED ALWAYS AS (skill_name || '::' || task_type || '::' || tone || '::' || model_target) STORED,
    is_elite BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_prompt_population_niche ON prompt_population(niche_key);
CREATE INDEX idx_prompt_population_skill ON prompt_population(skill_name);
CREATE INDEX idx_prompt_population_elite ON prompt_population(is_elite) WHERE is_elite = TRUE;
CREATE INDEX idx_prompt_population_score ON prompt_population(score DESC);

-- 2. Self-Play Rounds
CREATE TABLE IF NOT EXISTS selfplay_rounds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_name TEXT NOT NULL,
    round_number INTEGER NOT NULL,
    strategy_a TEXT NOT NULL,
    strategy_b TEXT NOT NULL,
    prompt_a_id UUID REFERENCES prompt_population(id),
    prompt_b_id UUID REFERENCES prompt_population(id),
    output_a TEXT,
    output_b TEXT,
    winner TEXT CHECK (winner IN ('a', 'b', 'tie')),
    judge_reasoning TEXT,
    judge_model TEXT NOT NULL DEFAULT 'claude-sonnet-4-6',
    quality_dimensions JSONB DEFAULT '{}'::jsonb,
    weakest_strategy TEXT,
    improvement_suggestion TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_selfplay_skill ON selfplay_rounds(skill_name);
CREATE INDEX idx_selfplay_round ON selfplay_rounds(round_number);

-- 3. Reflection Events
CREATE TABLE IF NOT EXISTS reflection_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL CHECK (event_type IN (
        'skill_execution', 'user_feedback', 'self_play_result',
        'performance_metric', 'error', 'quality_check'
    )),
    skill_name TEXT,
    source TEXT NOT NULL,
    severity TEXT CHECK (severity IN ('info', 'warning', 'critical')),
    summary TEXT NOT NULL,
    details JSONB DEFAULT '{}'::jsonb,
    metadata JSONB DEFAULT '{}'::jsonb,
    lookback_window_hours INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_reflection_type ON reflection_events(event_type);
CREATE INDEX idx_reflection_skill ON reflection_events(skill_name);
CREATE INDEX idx_reflection_created ON reflection_events(created_at DESC);

-- 4. Soul Modification Proposals
CREATE TABLE IF NOT EXISTS soul_modification_proposals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    proposal_type TEXT NOT NULL CHECK (proposal_type IN (
        'soul_edit', 'skill_edit', 'new_skill', 'deprecate_skill',
        'parameter_tune', 'workflow_change'
    )),
    target_file TEXT NOT NULL,
    diff_text TEXT NOT NULL,
    rationale TEXT NOT NULL,
    risk_rating TEXT NOT NULL CHECK (risk_rating IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    supporting_evidence JSONB DEFAULT '[]'::jsonb,
    status TEXT NOT NULL DEFAULT 'staged' CHECK (status IN (
        'staged', 'approved', 'applied', 'rejected', 'rolled_back'
    )),
    applied_at TIMESTAMPTZ,
    applied_by TEXT,
    rollback_diff TEXT,
    review_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_proposals_status ON soul_modification_proposals(status);
CREATE INDEX idx_proposals_risk ON soul_modification_proposals(risk_rating);

-- 5. Deployed Prompts (production tracking)
CREATE TABLE IF NOT EXISTS deployed_prompts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_name TEXT NOT NULL,
    prompt_population_id UUID REFERENCES prompt_population(id),
    prompt_text TEXT NOT NULL,
    generation INTEGER NOT NULL,
    score_at_deploy FLOAT NOT NULL,
    deployment_reason TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    performance_after_deploy JSONB DEFAULT '{}'::jsonb,
    deployed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    retired_at TIMESTAMPTZ
);

CREATE INDEX idx_deployed_skill ON deployed_prompts(skill_name);
CREATE INDEX idx_deployed_active ON deployed_prompts(is_active) WHERE is_active = TRUE;

-- Row Level Security (enable for all tables)
ALTER TABLE prompt_population ENABLE ROW LEVEL SECURITY;
ALTER TABLE selfplay_rounds ENABLE ROW LEVEL SECURITY;
ALTER TABLE reflection_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE soul_modification_proposals ENABLE ROW LEVEL SECURITY;
ALTER TABLE deployed_prompts ENABLE ROW LEVEL SECURITY;

-- Service role policy (for backend scripts)
CREATE POLICY "Service role full access" ON prompt_population FOR ALL USING (TRUE);
CREATE POLICY "Service role full access" ON selfplay_rounds FOR ALL USING (TRUE);
CREATE POLICY "Service role full access" ON reflection_events FOR ALL USING (TRUE);
CREATE POLICY "Service role full access" ON soul_modification_proposals FOR ALL USING (TRUE);
CREATE POLICY "Service role full access" ON deployed_prompts FOR ALL USING (TRUE);

-- Updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_prompt_population_updated_at
    BEFORE UPDATE ON prompt_population
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_proposals_updated_at
    BEFORE UPDATE ON soul_modification_proposals
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
