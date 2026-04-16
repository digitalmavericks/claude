"""Supabase client wrapper using direct REST API calls.

Uses httpx for reliability in sandboxed environments where the Supabase
Python SDK may hit DNS caching issues.
"""

import os
import json
from datetime import datetime, timezone
from typing import Any, Optional
from dotenv import load_dotenv
import httpx

load_dotenv()

_SUPABASE_URL = None
_SUPABASE_KEY = None


def _get_config():
    global _SUPABASE_URL, _SUPABASE_KEY
    if _SUPABASE_URL is None:
        _SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
        _SUPABASE_KEY = os.environ["SUPABASE_SERVICE_KEY"]
    return _SUPABASE_URL, _SUPABASE_KEY


def _headers():
    url, key = _get_config()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _rest_url(table: str) -> str:
    url, _ = _get_config()
    return f"{url}/rest/v1/{table}"


def _get(table: str, params: Optional[dict] = None) -> list[dict]:
    r = httpx.get(_rest_url(table), headers=_headers(), params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()


def _post(table: str, data: dict) -> list[dict]:
    r = httpx.post(_rest_url(table), headers=_headers(), json=data, timeout=30)
    r.raise_for_status()
    return r.json()


def _patch(table: str, data: dict, params: dict) -> list[dict]:
    r = httpx.patch(_rest_url(table), headers=_headers(), json=data, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


# ---- Public Client Interface ----
# We use a simple string "client" for API compatibility with the rest of the codebase.
# All functions that took a Client object now accept Any and ignore it — the real
# connection details come from env vars.

Client = Any


def get_client() -> str:
    _get_config()
    return "rest_client"


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
    result = _post("prompt_population", row)
    return {"data": result}


def get_elite_prompts(client: Client, skill_name: str) -> list:
    params = {
        "select": "*",
        "skill_name": f"eq.{skill_name}",
        "is_elite": "eq.true",
        "order": "score.desc",
    }
    return _get("prompt_population", params)


def get_top_prompts(client: Client, skill_name: str, limit: int = 10) -> list:
    params = {
        "select": "*",
        "skill_name": f"eq.{skill_name}",
        "order": "score.desc",
        "limit": str(limit),
    }
    return _get("prompt_population", params)


def get_prompts_by_niche(
    client: Client,
    skill_name: str,
    task_type: str,
    tone: str = "default",
    model_target: str = "claude-sonnet-4-6",
) -> list:
    niche_key = f"{skill_name}::{task_type}::{tone}::{model_target}"
    params = {
        "select": "*",
        "niche_key": f"eq.{niche_key}",
        "order": "score.desc",
    }
    return _get("prompt_population", params)


def update_elite_status(client: Client, prompt_id: str, is_elite: bool) -> dict:
    result = _patch(
        "prompt_population",
        {"is_elite": is_elite},
        {"id": f"eq.{prompt_id}"},
    )
    return {"data": result}


def insert_selfplay_round(client: Client, round_data: dict) -> dict:
    result = _post("selfplay_rounds", round_data)
    return {"data": result}


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
    result = _post("reflection_events", row)
    return {"data": result}


def get_recent_reflection_events(
    client: Client, hours: int = 168, skill_name: Optional[str] = None
) -> list:
    params = {
        "select": "*",
        "order": "created_at.desc",
        "limit": "100",
    }
    if skill_name:
        params["skill_name"] = f"eq.{skill_name}"
    return _get("reflection_events", params)


def insert_proposal(client: Client, proposal: dict) -> dict:
    result = _post("soul_modification_proposals", proposal)
    return {"data": result}


def get_staged_proposals(client: Client) -> list:
    params = {
        "select": "*",
        "status": "eq.staged",
        "order": "created_at.desc",
    }
    return _get("soul_modification_proposals", params)


def deploy_prompt(
    client: Client,
    skill_name: str,
    prompt_population_id: str,
    prompt_text: str,
    generation: int,
    score_at_deploy: float,
    deployment_reason: str = "",
) -> dict:
    _patch(
        "deployed_prompts",
        {"is_active": False, "retired_at": datetime.now(timezone.utc).isoformat()},
        {"skill_name": f"eq.{skill_name}", "is_active": "eq.true"},
    )
    row = {
        "skill_name": skill_name,
        "prompt_population_id": prompt_population_id,
        "prompt_text": prompt_text,
        "generation": generation,
        "score_at_deploy": score_at_deploy,
        "deployment_reason": deployment_reason,
        "is_active": True,
    }
    result = _post("deployed_prompts", row)
    return {"data": result}


def get_niche_coverage(client: Client) -> list:
    params = {
        "select": "skill_name,task_type,tone,model_target,score,is_elite",
        "is_elite": "eq.true",
    }
    return _get("prompt_population", params)
