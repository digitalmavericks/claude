"""MAP-Elites prompt evolution engine.

Implements a quality-diversity algorithm where prompts are organized into niches
(defined by skill_name × task_type × tone × model_target) and only the best
prompt per niche is retained as an "elite". Evolution proceeds by selecting
parents via UCB (Upper Confidence Bound), mutating them, evaluating offspring,
and updating the archive.
"""

import math
import random
import logging
from typing import Optional
from supabase import Client

from .db_client import (
    get_client,
    insert_prompt,
    get_top_prompts,
    get_prompts_by_niche,
    update_elite_status,
    get_niche_coverage,
    insert_reflection_event,
)
from .llm_utils import evaluate_prompt, judge_output, mutate_prompt

logger = logging.getLogger(__name__)

# UCB exploration constant — controls exploration vs exploitation tradeoff
UCB_C = 1.41


def ucb_score(prompt_score: float, total_selections: int, prompt_selections: int) -> float:
    """Upper Confidence Bound score for parent selection."""
    if prompt_selections == 0:
        return float("inf")
    exploitation = prompt_score
    exploration = UCB_C * math.sqrt(math.log(total_selections + 1) / prompt_selections)
    return exploitation + exploration


def select_parent_ucb(candidates: list[dict]) -> dict:
    """Select a parent prompt using UCB1 from the candidate pool."""
    if not candidates:
        raise ValueError("No candidates for parent selection")
    if len(candidates) == 1:
        return candidates[0]

    total_selections = sum(c.get("metadata", {}).get("selections", 0) for c in candidates)
    scored = []
    for c in candidates:
        s = c.get("metadata", {}).get("selections", 0)
        ucb = ucb_score(c["score"], total_selections, s)
        scored.append((ucb, c))
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[0][1]


def select_parent_tournament(candidates: list[dict], k: int = 3) -> dict:
    """Tournament selection: pick k random candidates, return the best."""
    if not candidates:
        raise ValueError("No candidates for parent selection")
    pool = random.sample(candidates, min(k, len(candidates)))
    return max(pool, key=lambda c: c["score"])


def evolve_step(
    client: Client,
    skill_name: str,
    task_type: str,
    task_description: str,
    tone: str = "default",
    model_target: str = "claude-sonnet-4-6",
    mutation_type: str = "guided",
    selection_method: str = "ucb",
    num_offspring: int = 3,
) -> list[dict]:
    """Run one evolution step: select parent, mutate, evaluate, update archive.

    Returns list of offspring records with their scores.
    """
    niche_prompts = get_prompts_by_niche(client, skill_name, task_type, tone, model_target)
    if not niche_prompts:
        all_skill = get_top_prompts(client, skill_name, limit=20)
        if not all_skill:
            raise ValueError(f"No prompts in population for skill '{skill_name}'. Seed the population first.")
        niche_prompts = all_skill

    if selection_method == "ucb":
        parent = select_parent_ucb(niche_prompts)
    else:
        parent = select_parent_tournament(niche_prompts)

    parent_gen = parent.get("generation", 0)
    parent_id = parent["id"]
    parent_text = parent["prompt_text"]

    logger.info(
        f"Selected parent {parent_id} (gen {parent_gen}, score {parent['score']:.3f}) "
        f"for niche {skill_name}::{task_type}::{tone}"
    )

    offspring_results = []

    for i in range(num_offspring):
        mt = mutation_type
        if mutation_type == "mixed":
            mt = random.choice(["guided", "random", "simplify", "expand", "rephrase"])

        feedback = parent.get("score_breakdown", {}).get("reasoning", "")
        mutation_result = mutate_prompt(
            parent_prompt=parent_text,
            skill_name=skill_name,
            task_type=task_type,
            feedback=feedback,
            mutation_type=mt,
        )

        new_prompt_text = mutation_result.get("prompt_text", parent_text)
        mutation_desc = mutation_result.get("mutation_description", "unknown mutation")

        if new_prompt_text == parent_text:
            logger.warning(f"Offspring {i} is identical to parent — skipping")
            continue

        eval_result = evaluate_prompt(new_prompt_text, task_description, model=model_target)
        score_result = judge_output(
            task_description=task_description,
            output=eval_result["output"],
            skill_name=skill_name,
        )

        new_score = score_result.get("overall", 0.0)
        new_gen = parent_gen + 1

        insert_result = insert_prompt(
            client=client,
            skill_name=skill_name,
            task_type=task_type,
            prompt_text=new_prompt_text,
            score=new_score,
            tone=tone,
            model_target=model_target,
            generation=new_gen,
            parent_id=parent_id,
            mutation_type=mt,
            mutation_description=mutation_desc,
            score_breakdown=score_result,
        )

        offspring_record = {
            "generation": new_gen,
            "score": new_score,
            "mutation_type": mt,
            "mutation_description": mutation_desc,
            "score_breakdown": score_result,
            "parent_score": parent["score"],
            "improved": new_score > parent["score"],
        }
        offspring_results.append(offspring_record)

        logger.info(
            f"  Offspring {i}: score={new_score:.3f} ({'+' if new_score > parent['score'] else ''}"
            f"{new_score - parent['score']:.3f}) via {mt}"
        )

    _update_elites(client, skill_name, task_type, tone, model_target)

    insert_reflection_event(
        client=client,
        event_type="skill_execution",
        source="map_elites_engine",
        summary=f"Evolution step for {skill_name}::{task_type}: {len(offspring_results)} offspring, "
                f"best={max((o['score'] for o in offspring_results), default=0):.3f}",
        skill_name=skill_name,
        details={"offspring": offspring_results, "parent_id": parent_id},
    )

    return offspring_results


def _update_elites(
    client: Client,
    skill_name: str,
    task_type: str,
    tone: str,
    model_target: str,
) -> None:
    """Ensure only the top prompt in each niche is marked as elite."""
    niche_prompts = get_prompts_by_niche(client, skill_name, task_type, tone, model_target)
    if not niche_prompts:
        return

    best = niche_prompts[0]
    for p in niche_prompts:
        should_be_elite = p["id"] == best["id"]
        if p.get("is_elite") != should_be_elite:
            update_elite_status(client, p["id"], should_be_elite)


def run_evolution(
    skill_name: str,
    task_type: str,
    task_description: str,
    num_steps: int = 3,
    num_offspring: int = 3,
    tone: str = "default",
    model_target: str = "claude-sonnet-4-6",
    mutation_type: str = "mixed",
) -> dict:
    """Run multiple evolution steps and return summary."""
    client = get_client()
    all_results = []

    for step in range(num_steps):
        logger.info(f"\n=== Evolution Step {step + 1}/{num_steps} ===")
        results = evolve_step(
            client=client,
            skill_name=skill_name,
            task_type=task_type,
            task_description=task_description,
            tone=tone,
            model_target=model_target,
            mutation_type=mutation_type,
            num_offspring=num_offspring,
        )
        all_results.extend(results)

    best_score = max((r["score"] for r in all_results), default=0)
    improvements = sum(1 for r in all_results if r["improved"])

    summary = {
        "skill_name": skill_name,
        "task_type": task_type,
        "total_offspring": len(all_results),
        "improvements": improvements,
        "best_score": best_score,
        "steps_completed": num_steps,
    }
    logger.info(f"\nEvolution summary: {summary}")
    return summary
