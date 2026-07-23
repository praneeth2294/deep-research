"""Prompt registry loader (procedural memory).

Prompts live as versioned .md files next to this module and are loaded by
name. Keeping them out of Python strings means they are diff-reviewed like
code and can be swapped/versioned without touching logic.

Usage:
    from deep_research.prompts import load_prompt
    system = load_prompt("planner")
"""

from functools import cache
from importlib import resources


@cache
def load_prompt(name: str) -> str:
    """Return the prompt text for ``name`` (e.g. "planner" -> planner.md)."""
    path = resources.files("deep_research.prompts") / f"{name}.md"
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError(f"Prompt file '{name}.md' is empty")
    return text
