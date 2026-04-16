"""
claude_client.py — Thin wrapper around the Anthropic SDK.

Design principles:
- One entry point: ClaudeClient.complete()
- JSON mode supported via response_format="json"
- Prompt caching via cache_control on system prompts (reduces cost on long skills)
- Model can be overridden per-call for cheap parsing tasks (use haiku)
- Usage stats returned alongside content for cost tracking in the eval harness
"""

from __future__ import annotations

import json
import logging
from typing import Any

import anthropic

from app.config import settings

logger = logging.getLogger(__name__)


class ClaudeClient:
    def __init__(self, api_key: str | None = None, default_model: str | None = None):
        self._client = anthropic.Anthropic(
            api_key=api_key or settings.anthropic_api_key
        )
        self.default_model = default_model or settings.anthropic_model

    def complete(
        self,
        system: str,
        messages: list[dict[str, Any]],
        response_format: str | None = None,
        model: str | None = None,
        max_tokens: int = 8192,
        cache_system: bool = True,
    ) -> tuple[str, dict]:
        """
        Call the Claude API and return (content_text, usage_dict).

        Args:
            system: System prompt text (will be cached if cache_system=True).
            messages: List of {"role": "user"|"assistant", "content": str} dicts.
            response_format: Pass "json" to request JSON output. Claude will be
                             instructed to return valid JSON only.
            model: Override the default model for this call.
            max_tokens: Maximum tokens in the response.
            cache_system: Whether to attach cache_control to the system prompt.
                          Set False for one-off or short prompts.

        Returns:
            (content_text, usage) where usage = {"input_tokens": int, "output_tokens": int, ...}
        """
        resolved_model = model or self.default_model

        # Build system block — optionally with prompt caching
        system_block: list[dict] | str
        if cache_system:
            system_block = [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        else:
            system_block = system

        # If JSON mode requested, append instruction to the last user message
        if response_format == "json":
            messages = _inject_json_instruction(messages)

        logger.debug(
            "Calling Claude [model=%s, cache=%s, json=%s]",
            resolved_model,
            cache_system,
            response_format == "json",
        )

        response = self._client.messages.create(
            model=resolved_model,
            max_tokens=max_tokens,
            system=system_block,
            messages=messages,
        )

        content = response.content[0].text
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "model": resolved_model,
        }

        logger.debug(
            "Claude response received [in=%d, out=%d]",
            usage["input_tokens"],
            usage["output_tokens"],
        )

        # Validate JSON if requested
        if response_format == "json":
            content = _extract_json(content)

        return content, usage

    def complete_json(
        self,
        system: str,
        messages: list[dict[str, Any]],
        model: str | None = None,
        max_tokens: int = 8192,
        cache_system: bool = True,
    ) -> tuple[dict, dict]:
        """
        Convenience wrapper that calls complete() with JSON mode and parses the result.

        Returns:
            (parsed_dict, usage_dict)
        """
        raw, usage = self.complete(
            system=system,
            messages=messages,
            response_format="json",
            model=model,
            max_tokens=max_tokens,
            cache_system=cache_system,
        )
        return json.loads(raw), usage


def _inject_json_instruction(messages: list[dict]) -> list[dict]:
    """Append a JSON-mode reminder to the last user turn."""
    messages = list(messages)  # shallow copy to avoid mutation
    if messages and messages[-1]["role"] == "user":
        original = messages[-1]["content"]
        messages[-1] = {
            "role": "user",
            "content": (
                f"{original}\n\n"
                "IMPORTANT: Your entire response must be valid JSON only. "
                "Do not include markdown fences, commentary, or any text outside the JSON object."
            ),
        }
    return messages


def _extract_json(text: str) -> str:
    """
    Strip markdown fences if Claude wrapped the JSON in ```json ... ``` anyway.
    Returns the raw JSON string (still needs json.loads by the caller).
    """
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Drop first line (```json or ```) and last line (```)
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner).strip()
    return text
