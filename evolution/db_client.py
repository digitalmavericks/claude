"""Supabase client wrapper for the self-improving prompting system."""

import os
import json
from datetime import datetime, timezone
from typing import Optional
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()


def get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)


def insert_prompt(
    client: Client,
    skill_name: str,
    task_type: str,
    prompt_text: str,
    score: float = 0.0,
    tone: str = "default",
    model_target: str = "claude-sonnet-4-6",
    generation: int = 0,
    parent_id: Optional[str] = None,
    mutation_type: Optional[str] = None,
    mutation_description: Optional[str] = None,
    score_breakdown: Optional[dict] = None,
    is_elite: bool = False,
) -> dict:
    row = {
        "skill_name": skill_name,
        "task_type": task_type,
        "prompt_text": prompt_text,
        "score": score,
        "tone": tone,
        "model_target": model_target,
        "generation": generation,
        "parent_id": parent_id,
        "mutation_type": mutation_type,
        "mutation_description": mutation_description,
        "score_breakdown": score_breakdown or {},
        "is_elite": is_elite,
    }
    return client.table("prompt_population").insert(row).execute()


def get_elite_prompts(client: Client, skill_name: str) -> list:
    return (
        client.table("prompt_population")
        .select("*")
        .eq("skill_name", skill_name)
        .eq("is_elite", True)
        .order("score", desc=True)
        .execute()
        .data
    )


def get_top_prompts(
    client: Client, skill_name: str, limit: int = 10
) -> list:
    return (
        client.table("prompt_population")
        .select("*")
        .eq("skill_name", skill_name)
        .order("score", desc=True)
        .limit(limit)
        .execute()
        .data
    )


def get_prompts_by_niche(
    client: Client,
    skill_name: str,
    task_type: str,
    tone: str = "default",
    model_target: str = "claude-sonnet-4-6",
) -> list:
    niche_key = f"{skill_name}::{task_type}::{tone}::{model_target}"
    return (
        client.table("prompt_population")
        .select("*")
        .eq("niche_key", niche_key)
        .order("score", desc=True)
        .execute()
        .data
    )


def update_elite_status(client: Client, prompt_id: str, is_elite: bool) -> dict:
    return (
        client.table("prompt_population")
        .update({"is_elite": is_elite})
        .eq("id", prompt_id)
        .execute()
    )


def insert_selfplay_round(client: Client, round_data: dict) -> dict:
    return client.table("selfplay_rounds").insert(round_data).execute()


def insert_reflection_event(
    client: Client,
    event_type: str,
    source: str,
    summary: str,
    skill_name: Optional[str] = None,
    severity: str = "info",
    details: Optional[dict] = None,
    metadata: Optional[dict] = None,
    lookback_window_hours: Optional[int] = None,
) -> dict:
    row = {
        "event_type": event_type,
        "source": source,
        "summary": summary,
        "skill_name": skill_name,
        "severity": severity,
        "details": details or {},
        "metadata": metadata or {},
        "lookback_window_hours": lookback_window_hours,
    }
    return client.table("reflection_events").insert(row).execute()


def get_recent_reflection_events(
    client: Client, hours: int = 168, skill_name: Optional[str] = None
) -> list:
    cutoff = datetime.now(timezone.utc).isoformat()
    query = (
        client.table("reflection_events")
        .select("*")
        .order("created_at", desc=True)
    )
    if skill_name:
        query = query.eq("skill_name", skill_name)
    return query.limit(100).execute().data


def insert_proposal(client: Client, proposal: dict) -> dict:
    return client.table("soul_modification_proposals").insert(proposal).execute()


def get_staged_proposals(client: Client) -> list:
    return (
        client.table("soul_modification_proposals")
        .select("*")
        .eq("status", "staged")
        .order("created_at", desc=True)
        .execute()
        .data
    )


def deploy_prompt(
    client: Client,
    skill_name: str,
    prompt_population_id: str,
    prompt_text: str,
    generation: int,
    score_at_deploy: float,
    deployment_reason: str = "",
) -> dict:
    # Retire currently active deployment for this skill
    client.table("deployed_prompts").update(
        {"is_active": False, "retired_at": datetime.now(timezone.utc).isoformat()}
    ).eq("skill_name", skill_name).eq("is_active", True).execute()

    row = {
        "skill_name": skill_name,
        "prompt_population_id": prompt_population_id,
        "prompt_text": prompt_text,
        "generation": generation,
        "score_at_deploy": score_at_deploy,
        "deployment_reason": deployment_reason,
        "is_active": True,
    }
    return client.table("deployed_prompts").insert(row).execute()


def get_niche_coverage(client: Client) -> list:
    return (
        client.table("prompt_population")
        .select("skill_name, task_type, tone, model_target, score, is_elite")
        .eq("is_elite", True)
        .execute()
        .data
    )
