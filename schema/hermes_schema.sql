-- ============================================
-- HERMES SCHEMA
-- Operational hands layer for ECHO/AICOS
-- ============================================

CREATE SCHEMA IF NOT EXISTS hermes;

-- ============================================
-- JOB QUEUE
-- Three inboxes: Slack, Asana, local file drop
-- ============================================
CREATE TABLE IF NOT EXISTS hermes.jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id TEXT UNIQUE NOT NULL DEFAULT 'HRM-' || to_char(now(), 'YYYYMMDD-HH24MISS') || '-' || substr(gen_random_uuid()::text, 1, 4),
    source TEXT NOT NULL CHECK (source IN ('slack', 'asana', 'file_drop', 'api', 'manual')),
    source_ref TEXT,
    title TEXT NOT NULL,
    description TEXT,
    priority TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('critical', 'high', 'normal', 'low')),
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued', 'claimed', 'running', 'blocked', 'completed', 'failed', 'cancelled')),
    execution_mode TEXT CHECK (execution_mode IN ('api', 'chrome', 'computer_use')),
    skill_used TEXT,
    input_payload JSONB DEFAULT '{}',
    output_payload JSONB DEFAULT '{}',
    error_detail TEXT,
    spend_usd NUMERIC(10,4) DEFAULT 0,
    spend_cap_usd NUMERIC(10,4) DEFAULT 5.00,
    claimed_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================
-- AUDIT LOG
-- Every Hermes action logged here
-- ============================================
CREATE TABLE IF NOT EXISTS hermes.audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES hermes.jobs(id),
    action_type TEXT NOT NULL,
    target_system TEXT,
    target_url TEXT,
    action_detail JSONB DEFAULT '{}',
    snapshot_path TEXT,
    success BOOLEAN,
    error_message TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================
-- SNAPSHOTS
-- Pre-change state captures for rollback
-- ============================================
CREATE TABLE IF NOT EXISTS hermes.snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES hermes.jobs(id),
    target_system TEXT NOT NULL,
    target_identifier TEXT NOT NULL,
    snapshot_type TEXT NOT NULL CHECK (snapshot_type IN ('pre_change', 'post_change', 'rollback')),
    content_hash TEXT,
    content JSONB,
    local_path TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================
-- REFLECTION EVENTS (hermes-scoped)
-- Same pattern as public.reflection_events, workflow=hermes_ops
-- ============================================
CREATE TABLE IF NOT EXISTS hermes.reflection_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES hermes.jobs(id),
    event_type TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'hermes',
    workflow TEXT NOT NULL DEFAULT 'hermes_ops',
    summary TEXT,
    severity TEXT DEFAULT 'info' CHECK (severity IN ('info', 'warning', 'error', 'critical')),
    skill_name TEXT,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================
-- SKILL RECIPES
-- Extracted from successful jobs for reuse
-- ============================================
CREATE TABLE IF NOT EXISTS hermes.skill_recipes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    skill_name TEXT NOT NULL,
    recipe_name TEXT NOT NULL,
    description TEXT,
    steps JSONB NOT NULL DEFAULT '[]',
    prerequisites JSONB DEFAULT '[]',
    success_criteria JSONB DEFAULT '[]',
    extracted_from_job UUID REFERENCES hermes.jobs(id),
    times_used INTEGER DEFAULT 0,
    success_rate NUMERIC(5,4) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================
-- GUARDRAILS
-- Hard limits enforced at runtime
-- ============================================
CREATE TABLE IF NOT EXISTS hermes.guardrails (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name TEXT UNIQUE NOT NULL,
    rule_type TEXT NOT NULL CHECK (rule_type IN ('deny', 'require_approval', 'allow')),
    description TEXT NOT NULL,
    pattern JSONB,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);
