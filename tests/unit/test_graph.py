"""Graph wiring tests (no LLM, no network - nodes are faked)."""

from deep_research.graph.builder import build_graph
from deep_research.graph.nodes.writer import format_sources
from deep_research.schemas.research import Source


def test_graph_compiles_without_credentials() -> None:
    # build_graph performs no I/O; it must work on a machine with no .env at all.
    graph = build_graph()
    expected = {
        "input_guard",
        "hitl",
        "router",
        "simple_answer",
        "memory_recall",
        "memory_store",
        "planner",
        "researcher",
        "quality_gate",
        "replanner",
        "analyst",
        "synthesizer",
        "writer",
        "reviewer",
    }
    assert expected <= set(graph.get_graph().nodes)


def test_format_sources_numbers_from_one() -> None:
    block = format_sources(
        [
            Source(url="https://a.example/x", title="Alpha", snippet="first"),
            Source(url="https://b.example/y", title="Beta", snippet="second"),
        ]
    )
    assert "[1] Alpha" in block
    assert "[2] Beta" in block
    assert "https://b.example/y" in block
