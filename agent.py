"""
Core Claude conversation agent for Claude-Linux-Helper.
"""

from __future__ import annotations

import anthropic

from config import MODEL, MAX_TOKENS, get_api_key

SYSTEM_PROMPT = """\
You are Claude Linux Helper, a friendly and patient assistant for people who are \
new to Linux (especially Ubuntu) and want to learn how to use Claude AI on their system.

Your goals:
- Help users install, configure, and use the Anthropic Claude API on Ubuntu/Linux.
- Explain Linux concepts and commands in plain language suitable for beginners.
- Provide clear, step-by-step instructions with copy-paste ready commands.
- Warn users about potential risks (e.g. sudo commands, deleting files).
- Encourage best practices: use virtual environments for Python, never hard-code API keys, etc.
- If a user asks something unrelated to Linux or Claude, gently steer them back.

Always format shell commands in code blocks. Keep explanations concise but complete.
"""


class Agent:
    """Stateful multi-turn conversation agent backed by Claude."""

    def __init__(self) -> None:
        self._client = anthropic.Anthropic(api_key=get_api_key())
        self._history: list[dict[str, str]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(self, user_message: str) -> str:
        """Send *user_message*, append to history, return assistant reply."""
        self._history.append({"role": "user", "content": user_message})
        response = self._client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=self._history,
        )
        reply = response.content[0].text
        self._history.append({"role": "assistant", "content": reply})
        return reply

    def reset(self) -> None:
        """Clear conversation history."""
        self._history.clear()

    @property
    def history(self) -> list[dict[str, str]]:
        """Read-only view of the conversation history."""
        return list(self._history)
