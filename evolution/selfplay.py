"""Self-play evaluation system.

Implements head-to-head competition between prompt variants. Each round selects
two strategies (prompt variants), generates outputs for the same task, and uses
an LLM judge to determine the winner. Results feed back into the evolution
pipeline and identify the weakest quality dimensions.
"""

import random
import logging
from typing import Optional
from supabase import Client

from .db_client import (
    get_client,
    get_top_prompts,
    insert_selfplay_round,
    insert_reflection_event,
)
from .llm_utils import evaluate_prompt, judge_comparison

logger = logging.getLogger(__name__)

SAMPLE_TASKS = {
    "video-script": [
        "Write a 60-second video script for a SaaS product launch targeting startup founders.",
        "Create a 30-second social media video script promoting a summer fitness challenge.",
        "Write a 90-second explainer video script about how AI transforms small business operations.",
        "Create a 45-second testimonial-style video script for a premium coffee brand.",
        "Write a 60-second brand story video for a sustainable fashion company.",
    ],
    "ad-copy": [
        "Write Google Ads copy for a B2B project management tool targeting remote teams.",
        "Create Facebook ad copy for a new meal delivery service in a competitive market.",
        "Write Instagram ad copy for a luxury skincare brand launching a new serum.",
        "Create LinkedIn ad copy for an executive coaching program.",
        "Write YouTube pre-roll ad copy for a personal finance app targeting millennials.",
    ],
}


def get_sample_task(skill_name: str) -> str:
    """Get a random evaluation task for the given skill."""
    tasks = SAMPLE_TASKS.get(skill_name, [])
    if not tasks:
        return f"Create high-quality output for the '{skill_name}' skill that demonstrates expertise."
    return random.choice(tasks)


def selfplay_round(
    client: Client,
    skill_name: str,
    round_number: int,
    task_description: Optional[str] = None,
    model_target: str = "claude-sonnet-4-6",
) -> dict:
    """Execute one self-play round between two prompt variants.

    Selects two prompts from the population, generates outputs for the same task,
    judges them head-to-head, and records the result.
    """
    task = task_description or get_sample_task(skill_name)
    candidates = get_top_prompts(client, skill_name, limit=20)

    if len(candidates) < 2:
        logger.warning(f"Need at least 2 prompts for self-play, found {len(candidates)}")
        return {"error": "insufficient_population", "count": len(candidates)}

    prompt_a, prompt_b = random.sample(candidates[:min(10, len(candidates))], 2)

    strategy_a = f"gen{prompt_a.get('generation', '?')}-{prompt_a.get('mutation_type', 'seed')}"
    strategy_b = f"gen{prompt_b.get('generation', '?')}-{prompt_b.get('mutation_type', 'seed')}"

    logger.info(f"Self-play round {round_number}: {strategy_a} vs {strategy_b}")
    logger.info(f"Task: {task[:80]}...")

    eval_a = evaluate_prompt(prompt_a["prompt_text"], task, model=model_target)
    eval_b = evaluate_prompt(prompt_b["prompt_text"], task, model=model_target)

    judgment = judge_comparison(
        task_description=task,
        output_a=eval_a["output"],
        output_b=eval_b["output"],
        strategy_a=strategy_a,
        strategy_b=strategy_b,
        skill_name=skill_name,
    )

    round_data = {
        "skill_name": skill_name,
        "round_number": round_number,
        "strategy_a": strategy_a,
        "strategy_b": strategy_b,
        "prompt_a_id": prompt_a["id"],
        "prompt_b_id": prompt_b["id"],
        "output_a": eval_a["output"][:5000],
        "output_b": eval_b["output"][:5000],
        "winner": judgment.get("winner", "tie"),
        "judge_reasoning": judgment.get("reasoning", ""),
        "quality_dimensions": judgment.get("quality_dimensions", {}),
        "weakest_strategy": judgment.get("weakest_strategy", ""),
        "improvement_suggestion": judgment.get("improvement_suggestion", ""),
    }
    insert_selfplay_round(client, round_data)

    logger.info(f"  Winner: {judgment.get('winner', 'tie')} | Weakest: {judgment.get('weakest_strategy', '?')}")

    return round_data


def selfplay_improvement_round(
    skill_name: str,
    num_rounds: int = 5,
    model_target: str = "claude-sonnet-4-6",
) -> dict:
    """Run a complete self-play improvement session.

    Executes multiple rounds, aggregates results, and identifies the weakest
    quality dimensions across all rounds. Returns a summary with actionable
    improvement suggestions.
    """
    client = get_client()
    results = []
    weakness_counts: dict[str, int] = {}
    suggestions: list[str] = []

    for i in range(num_rounds):
        result = selfplay_round(
            client=client,
            skill_name=skill_name,
            round_number=i + 1,
            model_target=model_target,
        )
        if "error" in result:
            return result
        results.append(result)

        weakest = result.get("weakest_strategy", "")
        if weakest:
            weakness_counts[weakest] = weakness_counts.get(weakest, 0) + 1

        suggestion = result.get("improvement_suggestion", "")
        if suggestion:
            suggestions.append(suggestion)

    dimension_scores: dict[str, dict[str, list[float]]] = {}
    for r in results:
        for dim, scores in r.get("quality_dimensions", {}).items():
            if dim not in dimension_scores:
                dimension_scores[dim] = {"a": [], "b": []}
            if isinstance(scores, dict):
                for side in ("a", "b"):
                    if side in scores:
                        dimension_scores[dim][side].append(float(scores[side]))

    weakest_dimensions = []
    for dim, sides in dimension_scores.items():
        all_scores = sides.get("a", []) + sides.get("b", [])
        if all_scores:
            avg = sum(all_scores) / len(all_scores)
            weakest_dimensions.append((dim, avg))
    weakest_dimensions.sort(key=lambda x: x[1])

    summary = {
        "skill_name": skill_name,
        "rounds_completed": len(results),
        "win_distribution": {
            "a": sum(1 for r in results if r.get("winner") == "a"),
            "b": sum(1 for r in results if r.get("winner") == "b"),
            "tie": sum(1 for r in results if r.get("winner") == "tie"),
        },
        "most_common_weakness": max(weakness_counts, key=weakness_counts.get) if weakness_counts else "none",
        "weakest_dimensions": weakest_dimensions[:3],
        "improvement_suggestions": suggestions,
    }

    insert_reflection_event(
        client=client,
        event_type="self_play_result",
        source="selfplay",
        summary=f"Self-play session for {skill_name}: {len(results)} rounds, "
                f"weakest dimension: {weakest_dimensions[0][0] if weakest_dimensions else 'N/A'}",
        skill_name=skill_name,
        details=summary,
    )

    logger.info(f"\nSelf-play summary for {skill_name}:")
    logger.info(f"  Rounds: {len(results)}")
    logger.info(f"  Weakest dimensions: {weakest_dimensions[:3]}")
    logger.info(f"  Top suggestion: {suggestions[0] if suggestions else 'none'}")

    return summary
