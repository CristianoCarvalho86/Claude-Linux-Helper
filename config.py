"""
Configuration for Claude-Linux-Helper.
Reads the ANTHROPIC_API_KEY from the environment.
"""

import os
import sys


MODEL = "claude-opus-4-5"
MAX_TOKENS = 1024


def get_api_key() -> str:
    """Return the Anthropic API key, exiting with a helpful message if absent."""
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        print(
            "\n[Error] ANTHROPIC_API_KEY environment variable is not set.\n"
            "To fix this:\n"
            "  1. Get your free API key at https://console.anthropic.com/\n"
            "  2. Export it before running this tool:\n"
            "       export ANTHROPIC_API_KEY='your-key-here'\n"
            "  3. To make it permanent, add that line to your ~/.bashrc or ~/.profile\n"
        )
        sys.exit(1)
    return key
