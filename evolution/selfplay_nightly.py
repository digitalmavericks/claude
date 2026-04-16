#!/usr/bin/env python3
"""Nightly self-play runner.

Intended to be triggered by a LaunchAgent (macOS) or cron job. Runs self-play
rounds for all seeded skills and logs results.

Usage:
    python3 -m evolution.selfplay_nightly
    python3 -m evolution.selfplay_nightly --skills video-script,ad-copy --rounds 5
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone

from .db_client import get_client
from .selfplay import selfplay_improvement_round

logger = logging.getLogger(__name__)

DEFAULT_SKILLS = ["video-script", "ad-copy"]


def run_nightly(skills: list[str], rounds_per_skill: int = 5) -> dict:
    """Run nightly self-play for all specified skills."""
    timestamp = datetime.now(timezone.utc).isoformat()
    results = {}

    for skill in skills:
        logger.info(f"\n{'='*60}")
        logger.info(f"Self-play session: {skill} ({rounds_per_skill} rounds)")
        logger.info(f"{'='*60}")

        try:
            result = selfplay_improvement_round(
                skill_name=skill,
                num_rounds=rounds_per_skill,
            )
            results[skill] = result
            logger.info(f"Completed {skill}: {json.dumps(result, indent=2, default=str)}")
        except Exception as e:
            logger.error(f"Failed self-play for {skill}: {e}", exc_info=True)
            results[skill] = {"error": str(e)}

    summary = {
        "timestamp": timestamp,
        "skills_run": len(skills),
        "results": results,
    }

    log_dir = os.getenv("LOGS_DIR", os.path.join(os.path.dirname(__file__), "..", "logs"))
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"selfplay_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(log_file, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    logger.info(f"\nNightly self-play complete. Log: {log_file}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Nightly Self-Play Runner")
    parser.add_argument("--skills", type=str, default=",".join(DEFAULT_SKILLS),
                        help="Comma-separated skill names")
    parser.add_argument("--rounds", type=int, default=5, help="Rounds per skill")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    skills = [s.strip() for s in args.skills.split(",") if s.strip()]
    result = run_nightly(skills, rounds_per_skill=args.rounds)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
