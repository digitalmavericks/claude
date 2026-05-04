#!/usr/bin/env python3
"""Seed the prompt population with generation-0 skill prompts.

Reads SKILL.md files and inserts them as baseline prompts in the population
database. These seeds establish the score floor that all evolved prompts must beat.

Usage:
    python3 -m evolution.seed_population --skill video-script
    python3 -m evolution.seed_population --all
"""

import argparse
import json
import os
import sys
import logging
from pathlib import Path

from .db_client import get_client, insert_prompt, get_top_prompts
from .llm_utils import evaluate_prompt, judge_output

logger = logging.getLogger(__name__)

SKILLS_DIR = os.path.join(os.path.dirname(__file__), "..", "skills")

SKILL_TASK_TYPES = {
    "video-script": ["brand_story", "product_launch", "explainer", "testimonial", "social_short"],
    "ad-copy": ["google_ads", "facebook_ads", "instagram_ads", "linkedin_ads", "youtube_preroll"],
    "self-improving-agent": ["reflection", "evolution", "evaluation"],
}

SEED_EVAL_TASKS = {
    "video-script": "Write a 60-second video script for a tech startup launching an AI productivity tool. Target audience: busy professionals aged 28-45.",
    "ad-copy": "Write Google Ads copy (3 headlines, 2 descriptions) for a B2B SaaS project management tool targeting remote engineering teams.",
}


def load_skill_prompt(skill_name: str) -> str:
    """Load the SKILL.md content as the seed prompt."""
    skill_path = os.path.join(SKILLS_DIR, skill_name, "SKILL.md")
    if not os.path.exists(skill_path):
        raise FileNotFoundError(f"No SKILL.md found at {skill_path}")
    with open(skill_path) as f:
        return f.read()


def seed_skill(
    skill_name: str,
    evaluate: bool = True,
    model_target: str = "claude-sonnet-4-6",
) -> dict:
    """Seed a single skill into the population database."""
    client = get_client()

    prompt_text = load_skill_prompt(skill_name)
    task_types = SKILL_TASK_TYPES.get(skill_name, ["general"])

    existing = get_top_prompts(client, skill_name, limit=100)
    existing_task_types = {p["task_type"] for p in existing}
    remaining = [t for t in task_types if t not in existing_task_types]

    if not remaining:
        logger.info(f"Skill '{skill_name}' fully seeded ({len(existing)} prompts) — skipping")
        return {"skill": skill_name, "action": "skipped", "existing_count": len(existing)}

    if existing_task_types:
        logger.info(f"Skill '{skill_name}' partially seeded ({len(existing_task_types)}/{len(task_types)}), seeding {len(remaining)} remaining")

    results = []
    for task_type in remaining:
        score = 0.0
        score_breakdown = {}

        if evaluate and skill_name in SEED_EVAL_TASKS:
            logger.info(f"Evaluating seed for {skill_name}::{task_type}...")
            eval_task = SEED_EVAL_TASKS[skill_name]
            eval_result = evaluate_prompt(prompt_text, eval_task, model=model_target)
            score_result = judge_output(
                task_description=eval_task,
                output=eval_result["output"],
                skill_name=skill_name,
            )
            score = score_result.get("overall", 0.0)
            score_breakdown = score_result
            logger.info(f"  Seed score: {score:.3f}")

        insert_prompt(
            client=client,
            skill_name=skill_name,
            task_type=task_type,
            prompt_text=prompt_text,
            score=score,
            model_target=model_target,
            generation=0,
            mutation_type="seed",
            mutation_description=f"Generation-0 seed from {skill_name}/SKILL.md",
            score_breakdown=score_breakdown,
            is_elite=True,
        )

        results.append({"task_type": task_type, "score": score})

    summary = {
        "skill": skill_name,
        "action": "seeded",
        "task_types": len(task_types),
        "results": results,
    }
    logger.info(f"Seeded {skill_name}: {json.dumps(summary, indent=2)}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Seed prompt population with SKILL.md baselines")
    parser.add_argument("--skill", type=str, help="Specific skill to seed")
    parser.add_argument("--all", action="store_true", help="Seed all available skills")
    parser.add_argument("--no-evaluate", action="store_true", help="Skip baseline evaluation")
    parser.add_argument("--model", type=str, default="claude-sonnet-4-6")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if args.all:
        skills_path = Path(SKILLS_DIR)
        if not skills_path.exists():
            logger.error(f"Skills directory not found: {SKILLS_DIR}")
            sys.exit(1)
        for skill_dir in sorted(skills_path.iterdir()):
            if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                seed_skill(skill_dir.name, evaluate=not args.no_evaluate, model_target=args.model)
    elif args.skill:
        seed_skill(args.skill, evaluate=not args.no_evaluate, model_target=args.model)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
