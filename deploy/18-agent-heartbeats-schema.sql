-- ============================================================================
-- ECHO Agent Heartbeats Table - Schema v1.0
-- Effective: 2026-06-07
-- Purpose: Store heartbeat records from ECHO agent for health monitoring.
-- Fixes: PGRST204 error - missing 'active_task' column in agent_heartbeats
-- ============================================================================

BEGIN;

-- Create agent_heartbeats table if it doesn't exist
CREATE TABLE IF NOT EXISTS agent_heartbeats (
    id              BIGSERIAL PRIMARY KEY,

    -- Agent identification
    agent_id        TEXT NOT NULL DEFAULT 'echo',

    -- Heartbeat metadata
    session_id      TEXT,
    status          TEXT NOT NULL DEFAULT 'alive'
                      CHECK (status IN ('alive', 'busy', 'idle', 'degraded', 'offline')),

    -- Current task tracking (the missing column that caused PGRST204)
    active_task     TEXT,
    active_task_id  UUID,

    -- Health metrics
    cpu_usage       NUMERIC,
    memory_usage    NUMERIC,
    queue_depth     INT DEFAULT 0,

    -- Timestamps
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at      TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '10 minutes'),

    -- Additional context
    metadata        JSONB DEFAULT '{}'::jsonb
);

-- Index for querying recent heartbeats by agent
CREATE INDEX IF NOT EXISTS idx_agent_heartbeats_agent_created
    ON agent_heartbeats (agent_id, created_at DESC);

-- Index for cleanup of expired heartbeats
CREATE INDEX IF NOT EXISTS idx_agent_heartbeats_expires
    ON agent_heartbeats (expires_at)
    WHERE expires_at < now();

-- Index for active task lookups
CREATE INDEX IF NOT EXISTS idx_agent_heartbeats_active_task
    ON agent_heartbeats (active_task)
    WHERE active_task IS NOT NULL;

-- If table already exists but is missing the active_task column, add it
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'agent_heartbeats'
        AND column_name = 'active_task'
    ) THEN
        ALTER TABLE agent_heartbeats ADD COLUMN active_task TEXT;
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'agent_heartbeats'
        AND column_name = 'active_task_id'
    ) THEN
        ALTER TABLE agent_heartbeats ADD COLUMN active_task_id UUID;
    END IF;
END$$;

-- Row-level security (match pattern from agent_messages)
ALTER TABLE agent_heartbeats ENABLE ROW LEVEL SECURITY;

-- Allow service role full access (for cron jobs)
DROP POLICY IF EXISTS agent_heartbeats_service_all ON agent_heartbeats;
CREATE POLICY agent_heartbeats_service_all ON agent_heartbeats
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Allow authenticated users to read heartbeats
DROP POLICY IF EXISTS agent_heartbeats_authenticated_select ON agent_heartbeats;
CREATE POLICY agent_heartbeats_authenticated_select ON agent_heartbeats
    FOR SELECT
    TO authenticated
    USING (true);

-- Allow anon to insert heartbeats (for external health checks)
DROP POLICY IF EXISTS agent_heartbeats_anon_insert ON agent_heartbeats;
CREATE POLICY agent_heartbeats_anon_insert ON agent_heartbeats
    FOR INSERT
    TO anon
    WITH CHECK (true);

-- Cleanup function to remove old heartbeats (run via pg_cron)
CREATE OR REPLACE FUNCTION agent_heartbeats_cleanup() RETURNS INT AS $$
DECLARE
    deleted_count INT;
BEGIN
    WITH deleted AS (
        DELETE FROM agent_heartbeats
        WHERE expires_at < now()
        RETURNING id
    )
    SELECT COUNT(*) INTO deleted_count FROM deleted;

    IF deleted_count > 0 THEN
        INSERT INTO blueprint_audit_log (actor, action, subject, payload, at)
        VALUES (
            'heartbeat_cleanup',
            'delete_expired',
            'agent_heartbeats',
            jsonb_build_object('count', deleted_count),
            now()
        );
    END IF;

    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- View for monitoring heartbeat health
CREATE OR REPLACE VIEW agent_heartbeats_health AS
SELECT
    agent_id,
    MAX(created_at) AS last_heartbeat,
    EXTRACT(EPOCH FROM (now() - MAX(created_at))) AS seconds_since_last,
    COUNT(*) FILTER (WHERE created_at > now() - INTERVAL '1 hour') AS heartbeats_last_hour,
    mode() WITHIN GROUP (ORDER BY status) AS most_common_status,
    MAX(active_task) AS current_task
FROM agent_heartbeats
WHERE created_at > now() - INTERVAL '24 hours'
GROUP BY agent_id;

COMMIT;

-- Verification
SELECT
    'agent_heartbeats' AS tbl,
    COUNT(*) FILTER (WHERE column_name = 'active_task') AS has_active_task,
    COUNT(*) FILTER (WHERE column_name = 'active_task_id') AS has_active_task_id
FROM information_schema.columns
WHERE table_name = 'agent_heartbeats';
