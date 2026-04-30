#!/usr/bin/env python3
"""Hyperagent reflection system.

Analyzes recent execution events, self-play results, and performance metrics
to generate SOUL.md modification proposals. Proposals are staged for human
review — never auto-applied.

Usage:
    python3 -m evolution.openclaw_hyperagent_reflection --lookback-hours 168
    python3 -m evolution.openclaw_hyperagent_reflection --lookback-hours 24 --skill video-script
"""

import argparse
import json
import os
import sys
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .db_client import (
    get_client,
    get_recent_reflection_events,
    get_staged_proposals,
    insert_proposal,
    get_elite_prompts,
    get_niche_coverage,
)
from .llm_utils import llm_call

logger = logging.getLogger(__name__)

DEFAULT_PROPOSALS_DIR = os.getenv(
    "SOUL_PROPOSALS_DIR",
    os.path.join(os.path.dirname(__file__), "..", "soul_proposals"),
)


def gather_evidence(
    lookback_hours: int = 168,
    skill_name: Optional[str] = None,
) -> dict:
    """Gather all reflection evidence from the lookback window."""
    client = get_client()
    events = get_recent_reflection_events(client, hours=lookback_hours, skill_name=skill_name)
    elites = get_elite_prompts(client, skill_name) if skill_name else []
    coverage = get_niche_coverage(client)

    by_type: dict[str, list] = {}
    for e in events:
        t = e.get("event_type", "unknown")
        by_type.setdefault(t, []).append(e)

    return {
        "lookback_hours": lookback_hours,
        "total_events": len(events),
        "events_by_type": {k: len(v) for k, v in by_type.items()},
        "event_summaries": [
            {"type": e["event_type"], "summary": e["summary"], "severity": e.get("severity", "info")}
            for e in events[:50]
        ],
        "elite_prompts": [
            {"skill": e["skill_name"], "score": e["score"], "generation": e["generation"]}
            for e in elites[:10]
        ],
        "niche_coverage": _summarize_coverage(coverage),
        "skill_filter": skill_name,
    }


def _summarize_coverage(coverage: list) -> dict:
    """Summarize niche coverage into a readable format."""
    niches: dict[str, dict] = {}
    for c in coverage:
        key = f"{c['skill_name']}::{c['task_type']}::{c['tone']}"
        if key not in niches:
            niches[key] = {"count": 0, "best_score": 0.0}
        niches[key]["count"] += 1
        niches[key]["best_score"] = max(niches[key]["best_score"], c.get("score", 0.0))
    return {
        "total_niches": len(niches),
        "niches": niches,
    }


def generate_proposals(evidence: dict) -> list[dict]:
    """Use LLM to analyze evidence and generate modification proposals."""
    if evidence["total_events"] == 0:
        logger.info("No events in lookback window — nothing to reflect on.")
        return []

    reflection_prompt = f"""You are a meta-cognitive reflection agent for an AI content creation system called ECHO/OpenClaw.

Your job is to analyze recent system activity and propose targeted improvements to the system's core configuration (SOUL.md) or individual skill prompts.

Here is the evidence from the last {evidence['lookback_hours']} hours:

Events summary: {json.dumps(evidence['events_by_type'], indent=2)}

Recent event details:
{json.dumps(evidence['event_summaries'][:30], indent=2)}

Elite prompts:
{json.dumps(evidence['elite_prompts'], indent=2)}

Niche coverage:
{json.dumps(evidence['niche_coverage'], indent=2)}

Based on this evidence, propose 0-3 concrete modifications. Each proposal should:
1. Address a specific, observed pattern (not a hypothetical)
2. Include the exact diff/change to make
3. Have a clear rationale grounded in the evidence
4. Include a risk rating

Respond with a JSON array of proposals (or empty array if no changes warranted):
[{{
    "proposal_type": "soul_edit" | "skill_edit" | "parameter_tune",
    "target_file": "SOUL.md or skills/skill-name/SKILL.md",
    "diff_text": "the specific text change (old → new)",
    "rationale": "why this change, citing specific evidence",
    "risk_rating": "LOW" | "MEDIUM" | "HIGH",
    "supporting_evidence": ["event summary 1", "event summary 2"]
}}]

Be conservative. If the evidence is ambiguous or insufficient, propose nothing.
An empty array [] is a valid and often correct response."""

    response = llm_call(reflection_prompt, temperature=0.3)

    try:
        json_match = None
        # Find JSON array in response
        for i, ch in enumerate(response):
            if ch == '[':
                depth = 0
                for j in range(i, len(response)):
                    if response[j] == '[':
                        depth += 1
                    elif response[j] == ']':
                        depth -= 1
                    if depth == 0:
                        json_match = response[i:j+1]
                        break
                break
        if json_match:
            proposals = json.loads(json_match)
            if isinstance(proposals, list):
                return proposals
    except (json.JSONDecodeError, TypeError):
        pass

    logger.warning(f"Failed to parse reflection response: {response[:300]}")
    return []


def stage_proposals(proposals: list[dict], proposals_dir: str = DEFAULT_PROPOSALS_DIR) -> list[str]:
    """Write proposals to the staging directory and database for human review."""
    client = get_client()
    Path(proposals_dir).mkdir(parents=True, exist_ok=True)
    staged_files = []

    for i, proposal in enumerate(proposals):
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"proposal_{timestamp}_{i}.json"
        filepath = os.path.join(proposals_dir, filename)

        proposal_record = {
            "proposal_type": proposal.get("proposal_type", "soul_edit"),
            "target_file": proposal.get("target_file", "unknown"),
            "diff_text": proposal.get("diff_text", ""),
            "rationale": proposal.get("rationale", ""),
            "risk_rating": proposal.get("risk_rating", "MEDIUM"),
            "supporting_evidence": proposal.get("supporting_evidence", []),
            "status": "staged",
        }

        insert_proposal(client, proposal_record)

        with open(filepath, "w") as f:
            json.dump(proposal_record, f, indent=2)

        staged_files.append(filepath)
        logger.info(f"Staged proposal: {filepath}")
        logger.info(f"  Type: {proposal_record['proposal_type']}")
        logger.info(f"  Target: {proposal_record['target_file']}")
        logger.info(f"  Risk: {proposal_record['risk_rating']}")
        logger.info(f"  Rationale: {proposal_record['rationale'][:100]}")

    return staged_files


def run_reflection(
    lookback_hours: int = 168,
    skill_name: Optional[str] = None,
    proposals_dir: str = DEFAULT_PROPOSALS_DIR,
    dry_run: bool = False,
) -> dict:
    """Run a complete reflection pass."""
    logger.info(f"Starting reflection pass (lookback={lookback_hours}h, skill={skill_name or 'all'})")

    evidence = gather_evidence(lookback_hours=lookback_hours, skill_name=skill_name)
    logger.info(f"Gathered {evidence['total_events']} events across {evidence['events_by_type']}")

    proposals = generate_proposals(evidence)
    logger.info(f"Generated {len(proposals)} proposals")

    if dry_run:
        logger.info("DRY RUN — proposals not staged")
        for p in proposals:
            logger.info(f"  [{p.get('risk_rating', '?')}] {p.get('proposal_type', '?')}: "
                       f"{p.get('rationale', '')[:100]}")
        return {"proposals": proposals, "staged": False, "files": []}

    staged_files = stage_proposals(proposals, proposals_dir)

    return {
        "proposals": proposals,
        "staged": True,
        "files": staged_files,
        "evidence_summary": {
            "total_events": evidence["total_events"],
            "events_by_type": evidence["events_by_type"],
        },
    }


def main():
    parser = argparse.ArgumentParser(description="OpenClaw Hyperagent Reflection System")
    parser.add_argument("--lookback-hours", type=int, default=168, help="Hours to look back for events")
    parser.add_argument("--skill", type=str, default=None, help="Filter to a specific skill")
    parser.add_argument("--dry-run", action="store_true", help="Generate proposals without staging them")
    parser.add_argument("--proposals-dir", type=str, default=DEFAULT_PROPOSALS_DIR)
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    result = run_reflection(
        lookback_hours=args.lookback_hours,
        skill_name=args.skill,
        proposals_dir=args.proposals_dir,
        dry_run=args.dry_run,
    )

    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
