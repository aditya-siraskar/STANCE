"""LiteLLM gateway: one place that knows which model handles which node.
Swapping a model is a policy-dict edit, never a change to agent code.
Requires the `agents` extra (`pip install -e ".[agents]"`).

Each model string is "<provider>/<model-name>"; LiteLLM reads that
provider's API key from its own env var (GROQ_API_KEY, DEEPSEEK_API_KEY,
GEMINI_API_KEY, ...) automatically — stance.config sets those on import.
Do NOT set litellm.api_key globally: that applies one key to every
provider's calls and breaks any node not using that provider.
"""
from __future__ import annotations

# Per-node routing policy — cheap model for high-volume/low-stakes nodes,
# a stronger model for planning/drafting where decomposition quality
# matters. Groq is free-tier and fast, so it's the default everywhere.
#
# Model availability on Groq's free tier changes over time (this project
# originally targeted llama-3.3-70b-versatile / llama-3.1-8b-instant,
# both since retired from the catalog). Verify what's currently available
# to your key with:
#   curl -s https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_API_KEY"
# gpt-oss models are reasoning models — give them real max_tokens headroom
# (200 was observed to be enough for short structured replies); an
# unexpectedly empty response with finish_reason="length" means reasoning
# tokens ate the whole budget before any visible output, not a broken key.
#
# To use a DeepSeek key instead for a given node (e.g. R1's reasoning suits
# the planner's decomposition task), just change that entry's "model":
#   "planner": {"model": "deepseek/deepseek-reasoner", "temperature": 0.0, "max_tokens": 800},
# No other code changes — stance.config already exports DEEPSEEK_API_KEY
# for LiteLLM to pick up.
NODE_POLICY: dict[str, dict] = {
    "planner": {"model": "groq/openai/gpt-oss-120b", "temperature": 0.0, "max_tokens": 800},
    "writer": {"model": "groq/openai/gpt-oss-120b", "temperature": 0.2, "max_tokens": 1000},
    "verifier_nli": {"model": "groq/openai/gpt-oss-20b", "temperature": 0.0, "max_tokens": 200},
}


def complete(node: str, messages: list[dict]) -> str:
    """Runs a chat completion for the given graph node using its configured
    model. Raises KeyError if the node has no policy entry — a new node
    must be registered here explicitly, not silently default anywhere."""
    import litellm  # deferred import — only needed when this is actually called

    policy = NODE_POLICY[node]
    response = litellm.completion(
        model=policy["model"],
        messages=messages,
        temperature=policy["temperature"],
        max_tokens=policy["max_tokens"],
    )
    return response["choices"][0]["message"]["content"]
