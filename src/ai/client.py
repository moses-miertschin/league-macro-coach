"""Thin wrapper around the Anthropic API.

No prompt construction, no grounding checks — those live in
prompt_builder.py and validator.py. Mirrors src/riot/client.py: a small
function per API need, no business logic.
"""

from anthropic import Anthropic

MODEL = "claude-opus-5"


def generate(prompt: str, schema: dict | None = None) -> str:
    client = Anthropic()
    kwargs = {}
    if schema is not None:
        kwargs["output_config"] = {"format": {"type": "json_schema", "schema": schema}}

    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    )
    return next(b.text for b in response.content if b.type == "text")
