"""LLM utility functions for evaluation, mutation, and judging."""

import os
import json
import re
from typing import Optional
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

_client: Optional[Anthropic] = None


def get_anthropic_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def llm_call(
    prompt: str,
    system: str = "",
    model: Optional[str] = None,
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> str:
    model = model or os.getenv("DEFAULT_MUTATION_MODEL", "claude-sonnet-4-6")
    client = get_anthropic_client()
    messages = [{"role": "user", "content": prompt}]
    kwargs = dict(model=model, max_tokens=max_tokens, messages=messages, temperature=temperature)
    if system:
        kwargs["system"] = system
    response = client.messages.create(**kwargs)
    return response.content[0].text


def evaluate_prompt(
    prompt_text: str,
    task_description: str,
    model: Optional[str] = None,
) -> dict:
    """Run a prompt against a task and return the output."""
    model = model or os.getenv("DEFAULT_MUTATION_MODEL", "claude-sonnet-4-6")
    output = llm_call(
        prompt=task_description,
        system=prompt_text,
        model=model,
        temperature=0.7,
    )
    return {"output": output, "model": model}


def judge_output(
    task_description: str,
    output: str,
    skill_name: str,
    model: Optional[str] = None,
) -> dict:
    """LLM-as-judge scoring of a single output. Returns score and breakdown."""
    model = model or os.getenv("DEFAULT_JUDGE_MODEL", "claude-sonnet-4-6")
    judge_prompt = f"""You are an expert quality evaluator for AI-generated content.

Evaluate the following output for the skill "{skill_name}".

Task: {task_description}

Output to evaluate:
---
{output}
---

Score the output on these dimensions (each 0.0-1.0):
1. relevance: Does it address the task correctly?
2. quality: Is the writing/content high quality?
3. creativity: Does it show creative thinking?
4. specificity: Is it specific rather than generic?
5. actionability: Can it be used as-is or with minimal edits?

Respond with ONLY a JSON object:
{{"relevance": 0.0, "quality": 0.0, "creativity": 0.0, "specificity": 0.0, "actionability": 0.0, "overall": 0.0, "reasoning": "brief explanation"}}

The "overall" score should be a weighted average: quality(0.3) + relevance(0.25) + specificity(0.2) + creativity(0.15) + actionability(0.1)."""

    response = llm_call(judge_prompt, model=model, temperature=0.2)
    try:
        json_match = re.search(r'\{[^{}]*\}', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except (json.JSONDecodeError, AttributeError):
        pass
    return {
        "relevance": 0.0, "quality": 0.0, "creativity": 0.0,
        "specificity": 0.0, "actionability": 0.0, "overall": 0.0,
        "reasoning": f"Failed to parse judge response: {response[:200]}",
    }


def judge_comparison(
    task_description: str,
    output_a: str,
    output_b: str,
    strategy_a: str,
    strategy_b: str,
    skill_name: str,
    model: Optional[str] = None,
) -> dict:
    """Head-to-head comparison of two outputs. Returns winner and reasoning."""
    model = model or os.getenv("DEFAULT_JUDGE_MODEL", "claude-sonnet-4-6")
    judge_prompt = f"""You are an expert evaluator comparing two AI-generated outputs for the skill "{skill_name}".

Task: {task_description}

Strategy A ({strategy_a}):
---
{output_a}
---

Strategy B ({strategy_b}):
---
{output_b}
---

Compare these outputs on: hook strength, emotional resonance, specificity, structure, and overall effectiveness.

Respond with ONLY a JSON object:
{{"winner": "a" or "b" or "tie", "reasoning": "explanation", "quality_dimensions": {{"hook_strength": {{"a": 0.0, "b": 0.0}}, "emotional_resonance": {{"a": 0.0, "b": 0.0}}, "specificity": {{"a": 0.0, "b": 0.0}}, "structure": {{"a": 0.0, "b": 0.0}}, "effectiveness": {{"a": 0.0, "b": 0.0}}}}, "weakest_strategy": "the strategy name that performed worst", "improvement_suggestion": "specific suggestion for the weaker output"}}"""

    response = llm_call(judge_prompt, model=model, temperature=0.2)
    try:
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except (json.JSONDecodeError, AttributeError):
        pass
    return {
        "winner": "tie",
        "reasoning": f"Failed to parse: {response[:200]}",
        "quality_dimensions": {},
        "weakest_strategy": "unknown",
        "improvement_suggestion": "retry evaluation",
    }


def mutate_prompt(
    parent_prompt: str,
    skill_name: str,
    task_type: str,
    feedback: str = "",
    mutation_type: str = "guided",
    model: Optional[str] = None,
) -> dict:
    """Generate a mutated variant of a prompt. Returns new prompt text and description."""
    model = model or os.getenv("DEFAULT_MUTATION_MODEL", "claude-sonnet-4-6")

    mutation_strategies = {
        "guided": "Make a targeted improvement based on the feedback provided.",
        "random": "Make a creative, unexpected change to the prompt structure or approach.",
        "crossover": "Combine elements from different successful prompt patterns.",
        "simplify": "Simplify the prompt while preserving its effectiveness.",
        "expand": "Add more detail, examples, or constraints to improve output quality.",
        "rephrase": "Rephrase the core instructions using different language and framing.",
    }

    strategy_instruction = mutation_strategies.get(mutation_type, mutation_strategies["guided"])

    mutate_prompt_text = f"""You are a prompt engineer improving prompts for the "{skill_name}" skill (task type: {task_type}).

Current prompt:
---
{parent_prompt}
---

{"Feedback from evaluation: " + feedback if feedback else "No specific feedback — make a general improvement."}

Mutation strategy: {mutation_type}
{strategy_instruction}

Generate an improved version of this prompt. The new prompt should:
- Maintain the core purpose and skill identity
- Be a meaningful improvement, not just cosmetic rewording
- Be self-contained (a complete system prompt)

Respond with ONLY a JSON object:
{{"prompt_text": "the complete new prompt text", "mutation_description": "brief description of what changed and why"}}"""

    response = llm_call(mutate_prompt_text, model=model, temperature=0.8)
    try:
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
    except (json.JSONDecodeError, AttributeError):
        pass
    return {"prompt_text": parent_prompt, "mutation_description": "mutation failed — returned parent unchanged"}
