"""Tracing + feedback + citation checker (all offline)."""

from collections.abc import Generator
from pathlib import Path
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from deep_research.config import get_settings
from deep_research.observability.feedback import record_feedback
from deep_research.observability.tracing import TraceRecorder, format_trace
from tests.evals.judges import check_citations


@pytest.fixture(autouse=True)
def _tmp_observability(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Generator[None]:
    monkeypatch.setenv("TRACES_PATH", str(tmp_path / "traces"))
    monkeypatch.setenv("FEEDBACK_PATH", str(tmp_path / "feedback.jsonl"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _simulate_run(recorder: TraceRecorder) -> None:
    node_run = uuid4()
    recorder.on_chain_start(
        {"name": "planner"},
        {},
        run_id=node_run,
        metadata={"langgraph_node": "planner"},
        name="planner",
    )
    llm_run = uuid4()
    recorder.on_chat_model_start(
        {"name": "ChatGoogleGenerativeAI"},
        [],
        run_id=llm_run,
        metadata={"ls_model_name": "gemini-flash-lite-latest"},
    )
    message = AIMessage(
        content="plan",
        usage_metadata={"input_tokens": 1000, "output_tokens": 200, "total_tokens": 1200},
    )
    recorder.on_llm_end(LLMResult(generations=[[ChatGeneration(message=message)]]), run_id=llm_run)
    recorder.on_chain_end({}, run_id=node_run)
    # a nested runnable with a non-node name must NOT create a span
    noise_run = uuid4()
    recorder.on_chain_start({"name": "RunnableSequence"}, {}, run_id=noise_run, metadata={})
    recorder.on_chain_end({}, run_id=noise_run)


def test_recorder_captures_node_and_llm_spans() -> None:
    recorder = TraceRecorder("trace-abc")
    _simulate_run(recorder)
    path = recorder.flush()
    text = format_trace("trace-abc")
    assert path.exists()
    assert "node  planner" in text
    assert "llm   gemini-flash-lite-latest" in text
    assert "1000/200 tok" in text
    assert "1,000 in / 200 out" in text  # totals rollup
    assert "2 spans" in text


def test_flush_appends_across_resumes_without_duplicates() -> None:
    recorder = TraceRecorder("trace-resume")
    _simulate_run(recorder)
    recorder.flush()
    _simulate_run(recorder)  # "after the resume"
    recorder.flush()
    assert "4 spans" in format_trace("trace-resume")


def test_feedback_ties_to_trace() -> None:
    recorder = TraceRecorder("trace-fb")
    _simulate_run(recorder)
    recorder.flush()
    record_feedback("trace-fb", "down", "missed the pricing angle")
    text = format_trace("trace-fb")
    assert "Feedback: down 'missed the pricing angle'" in text
    feedback_file = Path(get_settings().feedback_path)
    assert "trace-fb" in feedback_file.read_text(encoding="utf-8")


def test_recorder_never_breaks_the_run() -> None:
    recorder = TraceRecorder("trace-broken")
    recorder.on_llm_end(object(), run_id=uuid4())  # garbage response, unknown run
    recorder.on_chain_end({}, run_id=uuid4())  # end without start
    assert recorder.flush().exists()


# ---------------------------------------------------------------- citations


def test_citation_checker_accepts_valid() -> None:
    check = check_citations("A claim [1]. Another [2][3].", source_count=3)
    assert check.cited == [1, 2, 3]
    assert check.all_valid


def test_citation_checker_flags_hallucinated_ids() -> None:
    """The deterministic eval gate: a broken report FAILS (DoD)."""
    check = check_citations("Solid claim [1]. Fabricated citation [99].", source_count=5)
    assert check.invalid == [99]
    assert not check.all_valid


def test_citation_checker_flags_citation_free_reports() -> None:
    check = check_citations("Plenty of claims, zero citations.", source_count=5)
    assert not check.has_citations
    assert not check.all_valid
