"""Smoke test: the package and every subpackage import cleanly."""

import importlib

import pytest

SUBPACKAGES = [
    "deep_research",
    "deep_research.config",
    "deep_research.cli",
    "deep_research.schemas",
    "deep_research.llm",
    "deep_research.graph",
    "deep_research.graph.nodes",
    "deep_research.tools",
    "deep_research.memory",
    "deep_research.guardrails",
    "deep_research.observability",
    "deep_research.api",
]


@pytest.mark.parametrize("module", SUBPACKAGES)
def test_imports(module: str) -> None:
    importlib.import_module(module)
