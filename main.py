#!/usr/bin/env python3
"""
Claude-Linux-Helper – CLI entry point.

Usage:
    python3 main.py

Special slash commands (type at the prompt):
    /help           Show all built-in Linux tips
    /tips <cat>     Show tips for a specific category
    /categories     List available tip categories
    /reset          Clear the conversation history
    /exit  or  /quit  Leave the program
"""

import sys

import anthropic
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from agent import Agent
from linux_tips import CATEGORIES, get_all_tips, get_category_tips

console = Console()

BANNER = """\
╔══════════════════════════════════════════════════════╗
║         🐧  Claude Linux Helper  🤖                 ║
║   Your friendly assistant for Linux & Claude AI     ║
╚══════════════════════════════════════════════════════╝

Type your question, or use a slash command:
  /help           – Built-in Linux quick-reference
  /tips <cat>     – Tips for a category (e.g. /tips packages)
  /categories     – List tip categories
  /reset          – Start a fresh conversation
  /exit           – Quit
"""


def handle_slash_command(command: str) -> bool:
    """
    Process a slash command.

    Returns True if the command was handled (loop should continue),
    False if the program should exit.
    """
    parts = command.strip().split(None, 1)
    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""

    if cmd in ("/exit", "/quit"):
        console.print("\n👋  Goodbye! Happy Linux-ing!\n", style="bold green")
        return False

    if cmd == "/help":
        console.print(get_all_tips())
        return True

    if cmd == "/categories":
        cats = "  ".join(CATEGORIES.keys())
        console.print(f"\nAvailable categories: [bold cyan]{cats}[/bold cyan]\n")
        return True

    if cmd == "/tips":
        if not arg:
            console.print(
                "[yellow]Usage: /tips <category>  (e.g. /tips packages)[/yellow]"
            )
        else:
            console.print(get_category_tips(arg))
        return True

    if cmd == "/reset":
        return None  # signal caller to reset

    console.print(
        f"[yellow]Unknown command '{cmd}'. Type /help for available commands.[/yellow]"
    )
    return True


def run() -> None:
    console.print(Panel(BANNER, border_style="cyan", expand=False))

    agent = Agent()

    while True:
        try:
            user_input = Prompt.ask("\n[bold green]You[/bold green]").strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n👋  Goodbye!\n", style="bold green")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            result = handle_slash_command(user_input)
            if result is False:
                break
            if result is None:
                agent.reset()
                console.print("[italic]Conversation history cleared.[/italic]")
            continue

        # Regular chat message → send to Claude
        try:
            with console.status("[cyan]Thinking…[/cyan]"):
                reply = agent.chat(user_input)
        except (anthropic.APIError, anthropic.APIConnectionError) as exc:
            console.print(f"[red]Error communicating with Claude: {exc}[/red]")
            continue

        console.print("\n[bold blue]Claude[/bold blue]")
        console.print(Markdown(reply))


if __name__ == "__main__":
    run()
