#!/usr/bin/env python3
"""CLI entry point for the self-improving prompting system.

Usage:
    python3 scripts/cli.py seed --skill video-script
    python3 scripts/cli.py seed --all
    python3 scripts/cli.py evolve --skill video-script --task-type brand_story --steps 3
    python3 scripts/cli.py selfplay --skill video-script --rounds 5
    python3 scripts/cli.py reflect --lookback-hours 168
    python3 scripts/cli.py reflect --lookback-hours 24 --skill video-script --dry-run
    python3 scripts/cli.py nightly
    python3 scripts/cli.py coverage
"""

import argparse
import json
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from evolution.db_client import get_client, get_niche_coverage, get_staged_proposals
from evolution.seed_population import seed_skill, SKILL_TASK_TYPES, SKILLS_DIR
from evolution.map_elites_engine import run_evolution
from evolution.selfplay import selfplay_improvement_round
from evolution.openclaw_hyperagent_reflection import run_reflection
from evolution.selfplay_nightly import run_nightly


def cmd_seed(args):
    if args.all:
        from pathlib import Path
        skills_path = Path(SKILLS_DIR)
        for skill_dir in sorted(skills_path.iterdir()):
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                result = seed_skill(skill_dir.name, evaluate=not args.no_evaluate, model_target=args.model)
                print(json.dumps(result, indent=2))
    elif args.skill:
        result = seed_skill(args.skill, evaluate=not args.no_evaluate, model_target=args.model)
        print(json.dumps(result, indent=2))
    else:
        print("Specify --skill NAME or --all")
        sys.exit(1)


SEED_EVAL_TASKS = {
    "video-script": {
        "brand_story": "Write a 60-second brand story video for a sustainable fashion company targeting eco-conscious millennials.",
        "product_launch": "Write a 60-second video script for a SaaS product launch targeting startup founders.",
        "explainer": "Write a 90-second explainer video about how AI transforms small business operations.",
        "testimonial": "Create a 45-second testimonial-style video script for a premium coffee brand.",
        "social_short": "Create a 30-second social media video promoting a summer fitness challenge.",
    },
    "ad-copy": {
        "google_ads": "Write Google Ads copy for a B2B project management tool targeting remote teams.",
        "facebook_ads": "Create Facebook ad copy for a new meal delivery service in a competitive market.",
        "instagram_ads": "Write Instagram ad copy for a luxury skincare brand launching a new serum.",
        "linkedin_ads": "Create LinkedIn ad copy for an executive coaching program.",
        "youtube_preroll": "Write YouTube pre-roll ad copy for a personal finance app targeting millennials.",
    },
}


def cmd_evolve(args):
    task_desc = args.task_description
    if not task_desc:
        skill_tasks = SEED_EVAL_TASKS.get(args.skill, {})
        task_desc = skill_tasks.get(args.task_type, f"Create high-quality {args.task_type} output for {args.skill}.")

    result = run_evolution(
        skill_name=args.skill,
        task_type=args.task_type,
        task_description=task_desc,
        num_steps=args.steps,
        num_offspring=args.offspring,
        model_target=args.model,
        mutation_type=args.mutation,
    )
    print(json.dumps(result, indent=2))


def cmd_selfplay(args):
    result = selfplay_improvement_round(
        skill_name=args.skill,
        num_rounds=args.rounds,
        model_target=args.model,
    )
    print(json.dumps(result, indent=2, default=str))


def cmd_reflect(args):
    result = run_reflection(
        lookback_hours=args.lookback_hours,
        skill_name=args.skill,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, indent=2, default=str))


def cmd_nightly(args):
    skills = [s.strip() for s in args.skills.split(",") if s.strip()]
    result = run_nightly(skills, rounds_per_skill=args.rounds)
    print(json.dumps(result, indent=2, default=str))


def cmd_coverage(args):
    client = get_client()
    coverage = get_niche_coverage(client)

    niches = {}
    for c in coverage:
        key = f"{c['skill_name']}::{c['task_type']}::{c['tone']}"
        if key not in niches:
            niches[key] = {"count": 0, "best_score": 0.0}
        niches[key]["count"] += 1
        niches[key]["best_score"] = max(niches[key]["best_score"], c.get("score", 0.0))

    print(f"\nNiche Coverage ({len(niches)} niches):")
    print("-" * 60)
    for niche, data in sorted(niches.items()):
        print(f"  {niche}: {data['count']} elites, best={data['best_score']:.3f}")

    print(f"\nStaged proposals: {len(get_staged_proposals(client))}")


def cmd_proposals(args):
    client = get_client()
    proposals = get_staged_proposals(client)
    if not proposals:
        print("No staged proposals.")
        return
    for p in proposals:
        print(f"\n{'='*60}")
        print(f"[{p['risk_rating']}] {p['proposal_type']} → {p['target_file']}")
        print(f"Rationale: {p['rationale']}")
        print(f"Diff: {p['diff_text'][:200]}")
        print(f"Created: {p['created_at']}")


def main():
    parser = argparse.ArgumentParser(description="Self-Improving Prompting System CLI")
    parser.add_argument("--verbose", "-v", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)

    # seed
    p_seed = sub.add_parser("seed", help="Seed population with SKILL.md baselines")
    p_seed.add_argument("--skill", type=str)
    p_seed.add_argument("--all", action="store_true")
    p_seed.add_argument("--no-evaluate", action="store_true")
    p_seed.add_argument("--model", default="claude-sonnet-4-6")

    # evolve
    p_evolve = sub.add_parser("evolve", help="Run evolution steps")
    p_evolve.add_argument("--skill", required=True)
    p_evolve.add_argument("--task-type", required=True)
    p_evolve.add_argument("--task-description", type=str, default=None)
    p_evolve.add_argument("--steps", type=int, default=3)
    p_evolve.add_argument("--offspring", type=int, default=3)
    p_evolve.add_argument("--mutation", default="mixed", choices=["guided", "random", "mixed", "simplify", "expand", "rephrase"])
    p_evolve.add_argument("--model", default="claude-sonnet-4-6")

    # selfplay
    p_sp = sub.add_parser("selfplay", help="Run self-play evaluation")
    p_sp.add_argument("--skill", required=True)
    p_sp.add_argument("--rounds", type=int, default=5)
    p_sp.add_argument("--model", default="claude-sonnet-4-6")

    # reflect
    p_ref = sub.add_parser("reflect", help="Run hyperagent reflection")
    p_ref.add_argument("--lookback-hours", type=int, default=168)
    p_ref.add_argument("--skill", type=str, default=None)
    p_ref.add_argument("--dry-run", action="store_true")

    # nightly
    p_night = sub.add_parser("nightly", help="Run nightly self-play for all skills")
    p_night.add_argument("--skills", default="video-script,ad-copy")
    p_night.add_argument("--rounds", type=int, default=5)

    # coverage
    sub.add_parser("coverage", help="Show MAP-Elites niche coverage")

    # proposals
    sub.add_parser("proposals", help="Review staged SOUL.md proposals")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    commands = {
        "seed": cmd_seed,
        "evolve": cmd_evolve,
        "selfplay": cmd_selfplay,
        "reflect": cmd_reflect,
        "nightly": cmd_nightly,
        "coverage": cmd_coverage,
        "proposals": cmd_proposals,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
