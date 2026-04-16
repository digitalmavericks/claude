# Self-Improving Prompting System

A MAP-Elites based prompt evolution engine with self-play evaluation and hyperagent reflection for the ECHO/OpenClaw content creation system.

## Architecture

```
evolution/
  db_client.py              # Supabase client wrapper
  llm_utils.py              # LLM evaluation, mutation, and judging
  map_elites_engine.py      # MAP-Elites prompt evolution (UCB selection)
  selfplay.py               # Head-to-head self-play evaluation
  selfplay_nightly.py       # Nightly self-play runner (LaunchAgent target)
  openclaw_hyperagent_reflection.py  # Reflection & SOUL.md proposal generation
  seed_population.py        # Population seeder from SKILL.md baselines

skills/
  video-script/SKILL.md     # Video script generation skill
  ad-copy/SKILL.md          # Ad copy generation skill
  self-improving-agent/SKILL.md  # Meta-cognitive agent skill

schema/
  supabase_schema.sql       # Full Supabase schema (5 tables)

config/
  .env.example              # Environment configuration template
  ai.openclaw.selfplay.plist  # macOS LaunchAgent for nightly self-play

scripts/
  cli.py                    # Unified CLI entry point
```

## Setup

1. **Deploy Supabase schema**: Paste `schema/supabase_schema.sql` into your Supabase SQL Editor
2. **Configure environment**: `cp config/.env.example .env` and fill in your keys
3. **Install dependencies**: `pip install -r requirements.txt`

## Usage

```bash
# Seed the population with SKILL.md baselines
python3 scripts/cli.py seed --all

# Run 3 evolution steps on video-script
python3 scripts/cli.py evolve --skill video-script --task-type brand_story --steps 3

# Run self-play evaluation
python3 scripts/cli.py selfplay --skill video-script --rounds 5

# Run reflection pass (dry-run first)
python3 scripts/cli.py reflect --lookback-hours 168 --dry-run

# View niche coverage
python3 scripts/cli.py coverage

# Review staged proposals
python3 scripts/cli.py proposals

# Run nightly self-play for all skills
python3 scripts/cli.py nightly
```

## Supabase Tables

| Table | Purpose |
|-------|---------|
| `prompt_population` | MAP-Elites archive of prompt variants per niche |
| `selfplay_rounds` | Head-to-head comparison results |
| `reflection_events` | Execution logs, feedback, metrics |
| `soul_modification_proposals` | Staged SOUL.md/SKILL.md change proposals |
| `deployed_prompts` | Production prompt deployment tracking |

## LaunchAgent (macOS)

To install the nightly self-play schedule:

```bash
cp config/ai.openclaw.selfplay.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/ai.openclaw.selfplay.plist
```

Runs at 2:00 AM daily. Logs to `logs/selfplay.log`.
