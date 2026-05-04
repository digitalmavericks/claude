-- pg_cron schedule for autonomous self-improving pipeline
-- These are already deployed to the production database.
-- This file is for reference/re-deployment only.

-- Requires: pg_cron and pg_net extensions (both enabled on Supabase Pro)
CREATE EXTENSION IF NOT EXISTS pg_net WITH SCHEMA extensions;

-- Nightly self-play: every night at 2:00 AM UTC
SELECT cron.schedule(
    'selfplay-nightly',
    '0 2 * * *',
    $$
    SELECT net.http_post(
        url := 'https://wovoashhorgdzydlnpzr.supabase.co/functions/v1/selfplay-nightly',
        headers := jsonb_build_object(
            'Authorization', 'Bearer ' || current_setting('app.settings.service_role_key', true),
            'Content-Type', 'application/json'
        ),
        body := '{}'::jsonb
    );
    $$
);

-- Evolution (video-script): every 6 hours
SELECT cron.schedule(
    'evolve-step-video',
    '0 */6 * * *',
    $$
    SELECT net.http_post(
        url := 'https://wovoashhorgdzydlnpzr.supabase.co/functions/v1/evolve-step',
        headers := jsonb_build_object(
            'Authorization', 'Bearer ' || current_setting('app.settings.service_role_key', true),
            'Content-Type', 'application/json'
        ),
        body := '{"skill": "video-script", "task_type": "brand_story", "num_offspring": 2}'::jsonb
    );
    $$
);

-- Evolution (ad-copy): every 6 hours, offset by 3h
SELECT cron.schedule(
    'evolve-step-adcopy',
    '0 3,9,15,21 * * *',
    $$
    SELECT net.http_post(
        url := 'https://wovoashhorgdzydlnpzr.supabase.co/functions/v1/evolve-step',
        headers := jsonb_build_object(
            'Authorization', 'Bearer ' || current_setting('app.settings.service_role_key', true),
            'Content-Type', 'application/json'
        ),
        body := '{"skill": "ad-copy", "task_type": "linkedin_ads", "num_offspring": 2}'::jsonb
    );
    $$
);

-- Weekly reflection: Monday at 3:00 AM UTC
SELECT cron.schedule(
    'weekly-reflect',
    '0 3 * * 1',
    $$
    SELECT net.http_post(
        url := 'https://wovoashhorgdzydlnpzr.supabase.co/functions/v1/reflect',
        headers := jsonb_build_object(
            'Authorization', 'Bearer ' || current_setting('app.settings.service_role_key', true),
            'Content-Type', 'application/json'
        ),
        body := '{"lookback_hours": 168}'::jsonb
    );
    $$
);
