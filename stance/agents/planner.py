"""Planner — decomposes a question (with its already-resolved Scope) into
a typed Plan via an LLM call constrained to JSON matching PlanStep's
schema. The plan object IS the audit trail: nothing downstream trusts
free text from this node, only the parsed Plan.
"""
from __future__ import annotations

import json

from stance.contracts import Plan, PlanStep, Scope
from stance.llm import complete

_SYSTEM_PROMPT = """You are a financial-question planner. Decompose the user's \
question into 1-4 sub-questions. For each, output an object with:
- "sub_question": string
- "kind": "narrative" or "numeric" (numeric = requires a figure/computation \
from financial statements; narrative = requires reading filing text, e.g. risk \
factors or MD&A discussion)

Respond with ONLY a JSON array of these objects, no other text."""


def build_plan(question: str, scope: Scope) -> Plan:
    """Calls the planner LLM, parses its JSON array response into typed
    PlanStep objects sharing the already-resolved scope, and wraps them in
    a Plan. Raises ValueError if the model's response isn't valid JSON
    matching the expected shape — a malformed plan must not proceed
    silently into the graph."""
    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": question},
    ]
    raw = complete("planner", messages)
    raw = _strip_markdown_fence(raw)

    try:
        step_dicts = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"planner returned non-JSON output: {raw!r}") from exc

    steps = []
    for d in step_dicts:
        if "sub_question" not in d or d.get("kind") not in ("narrative", "numeric"):
            raise ValueError(f"planner produced a malformed step: {d!r}")
        steps.append(PlanStep(sub_question=d["sub_question"], kind=d["kind"], scope=scope))

    if not steps:
        raise ValueError("planner produced zero steps")

    return Plan(question=question, steps=steps)


def _strip_markdown_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    return text.strip()
