"""LiteLLM gateway: one place that knows which model handles which node.
Swapping a model is a policy-dict edit, never a change to agent code.
Requires the `agents` extra (`pip install -e ".[agents]"`).
"""
from __future__ import annotations

from stance.config import settings

# Per-node routing policy — cheap model for high-volume/low-stakes nodes,
# a stronger model for planning/drafting where decomposition quality matters.
# Groq is free-tier and fast; swap the model string to A/B without touching
# any agent code.
NODE_POLICY: dict[str, dict] = {
    "planner": {"model": "groq/llama-3.3-70b-versatile", "temperature": 0.0, "max_tokens": 800},
    "writer": {"model": "groq/llama-3.3-70b-versatile", "temperature": 0.2, "max_tokens": 1000},
    "verifier_nli": {"model": "groq/llama-3.1-8b-instant", "temperature": 0.0, "max_tokens": 200},
}


def complete(node: str, messages: list[dict]) -> str:
    """Runs a chat completion for the given graph node using its configured
    model. Raises KeyError if the node has no policy entry — a new node
    must be registered here explicitly, not silently default anywhere."""
    import litellm  # deferred import — only needed when this is actually called

    policy = NODE_POLICY[node]
    litellm.api_key = settings.groq_api_key or None
    response = litellm.completion(
        model=policy["model"],
        messages=messages,
        temperature=policy["temperature"],
        max_tokens=policy["max_tokens"],
    )
    return response["choices"][0]["message"]["content"]
