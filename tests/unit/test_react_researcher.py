"""ReAct researcher: tool choice, history trail, error resilience, and the hard cap."""

from typing import Any

import pytest

from deep_research.graph.nodes import researcher
from deep_research.schemas.planner import SubTopic
from deep_research.schemas.research import ReactStep, Source
from deep_research.tools.registry import ToolSpec


def _sub() -> SubTopic:
    return SubTopic(title="Vector DBs", search_query="vector database comparison", rationale="core")


def _sources(tag: str, n: int = 2) -> list[Source]:
    return [
        Source(url=f"https://{tag}.example/{i}", title=f"{tag}-{i}", snippet="x" * 250)
        for i in range(n)
    ]


def _fake_structured(sequence: list[ReactStep]) -> Any:
    queue = list(sequence)

    class _Invoker:
        def invoke(self, _messages: Any) -> ReactStep:
            return queue.pop(0)

    def factory(_schema: Any, **_kwargs: Any) -> _Invoker:
        return _Invoker()

    return factory


def _fake_tools(monkeypatch: pytest.MonkeyPatch, calls: list[tuple[str, str]]) -> None:
    def fake_get_tool(name: str) -> ToolSpec:
        def run(argument: str) -> list[Source]:
            calls.append((name, argument))
            if name == "broken_tool":
                raise RuntimeError("tool exploded")
            return _sources(name)

        return ToolSpec(name=name, description="fake", run=run)

    monkeypatch.setattr(researcher, "get_tool", fake_get_tool)


def test_agent_chooses_tools_and_finishes(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []
    _fake_tools(monkeypatch, calls)
    monkeypatch.setattr(
        researcher,
        "structured_llm",
        _fake_structured(
            [
                ReactStep(
                    reasoning="Need background", action="wikipedia", action_input="vector database"
                ),
                ReactStep(
                    reasoning="Deep-dive a result",
                    action="fetch_url",
                    action_input="https://tavily_search.example/0",
                ),
                ReactStep(reasoning="Enough evidence gathered", action="finish"),
            ]
        ),
    )

    update = researcher.researcher_node({"sub_topic": _sub(), "attempt": 1})
    [result] = update["research_results"]

    # seeded search + two agent-chosen tools, then finish
    assert [name for name, _ in calls] == ["tavily_search", "wikipedia", "fetch_url"]
    assert calls[0][1] == "vector database comparison"  # seed uses the planned query
    assert len(result.sources) == 6  # 2 per tool, all unique
    assert result.history[0].startswith("Action: tavily_search")
    assert result.history[-1] == "Finish: Enough evidence gathered"
    assert any(line.startswith("Thought: ") for line in result.history)


def test_hard_iteration_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    """An agent that never finishes stops at max_react_iterations. Always."""
    calls: list[tuple[str, str]] = []
    _fake_tools(monkeypatch, calls)
    never_stop = [
        ReactStep(reasoning="just one more search", action="tavily_search", action_input=f"q{i}")
        for i in range(50)
    ]
    monkeypatch.setattr(researcher, "structured_llm", _fake_structured(never_stop))

    update = researcher.researcher_node({"sub_topic": _sub(), "attempt": 1})
    [result] = update["research_results"]

    # default max_react_iterations = 5 -> 1 seeded + 5 agent actions, no more
    assert len(calls) == 6
    assert not any(line.startswith("Finish") for line in result.history)


def test_tool_error_becomes_observation_not_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str]] = []
    _fake_tools(monkeypatch, calls)
    monkeypatch.setattr(
        researcher,
        "structured_llm",
        _fake_structured(
            [
                ReactStep(reasoning="try it", action="fetch_url", action_input="https://x.example"),
                ReactStep(reasoning="done here", action="finish"),
            ]
        ),
    )
    # make fetch_url explode (delegate other tools to the fake installed above)
    original = researcher.get_tool  # type: ignore[attr-defined]

    def exploding_get_tool(name: str) -> ToolSpec:
        if name == "fetch_url":
            return ToolSpec(name, "fake", lambda _a: (_ for _ in ()).throw(RuntimeError("boom")))
        return original(name)

    monkeypatch.setattr(researcher, "get_tool", exploding_get_tool)

    update = researcher.researcher_node({"sub_topic": _sub(), "attempt": 1})
    [result] = update["research_results"]
    assert any("ERROR: boom" in line for line in result.history)  # observed, survived
    assert result.history[-1].startswith("Finish")
