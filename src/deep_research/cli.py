"""Command-line entry point.

Usage:
    research "impact of EU AI Act on startups"
    research            # no topic -> environment/config smoke check
"""

import argparse
import sys

from deep_research import __version__
from deep_research.config import get_settings


def _smoke_check() -> None:
    settings = get_settings()
    print(f"deep-research v{__version__} (environment: {settings.environment})")
    print(f"  google key: {'set' if settings.google_api_key else 'MISSING'}")
    print(f"  tavily key: {'set' if settings.tavily_api_key else 'MISSING'}")
    print('Run:  research "your topic"')


def _print_partial(graph: object, config: object) -> None:
    """Partial-results report from the checkpoint (what a stopped run already has)."""
    from typing import Any, cast

    try:
        snapshot = cast("Any", graph).get_state(cast("Any", config))
        state = snapshot.values or {}
    except Exception:
        print("(no checkpointed progress found)")
        return
    sub_topics = state.get("sub_topics") or []
    results = state.get("research_results") or []
    print("Partial progress so far:")
    print(f"  route: {state.get('route', '(not decided)')}")
    if sub_topics:
        print(f"  plan: {len(sub_topics)} sub-topic(s): " + "; ".join(s.title for s in sub_topics))
    if results:
        total = sum(len(r.sources) for r in results)
        print(f"  research: {len(results)} result(s), {total} sources gathered")
    if state.get("report"):
        print("  draft report: present (awaiting review)")


def _plan_decision(payload: dict[str, object], auto_approve: bool) -> dict[str, object]:
    """Show the plan and collect the human decision (or auto-approve)."""
    sub_topics = payload.get("sub_topics", [])
    print("\nPlan awaiting approval:")
    if isinstance(sub_topics, list):
        for i, st in enumerate(sub_topics, start=1):
            if isinstance(st, dict):
                print(f"  {i}. {st.get('title')}  [query: {st.get('search_query')}]")
    if auto_approve or not sys.stdin.isatty():
        print("Auto-approving plan.")
        return {"decision": "approve"}
    choice = input("Approve [a] / Edit queries [e] / Cancel [c]? ").strip().lower()
    if choice == "c":
        return {"decision": "cancel"}
    if choice == "e" and isinstance(sub_topics, list):
        edited: list[dict[str, object]] = []
        for st in sub_topics:
            if not isinstance(st, dict):
                continue
            new_query = input(f"  Query for '{st.get('title')}' (enter = keep): ").strip()
            edited.append({**st, "search_query": new_query or st.get("search_query")})
        return {"decision": "edit", "sub_topics": edited}
    return {"decision": "approve"}


def _run(topic: str | None, thread: str | None, auto_approve: bool = False) -> None:
    # Imported lazily so `research` (smoke check) works without heavy deps loading.
    from uuid import uuid4

    from langgraph.types import Command

    from deep_research.graph.builder import build_graph
    from deep_research.guardrails.budget import BudgetExceededError
    from deep_research.memory.checkpointing import sqlite_checkpointer
    from deep_research.observability.cost import session_cost

    thread_id = thread or uuid4().hex[:12]
    if thread:
        print(f"Resuming thread: {thread_id}\n")
        payload = None  # None input = continue from the last checkpoint
    else:
        print(f"Researching: {topic}\nThread: {thread_id}  (resume with --thread {thread_id})\n")
        payload = {"topic": topic}

    from typing import Any, cast

    from deep_research.observability.tracing import TraceRecorder, langfuse_handler

    recorder = TraceRecorder(thread_id)
    callbacks: list[Any] = [session_cost.callback, recorder]
    langfuse = langfuse_handler()
    if langfuse is not None:
        callbacks.append(langfuse)

    graph = build_graph(checkpointer=sqlite_checkpointer())
    config = cast(
        "Any",
        {
            "configurable": {"thread_id": thread_id},
            "callbacks": callbacks,
        },
    )
    try:
        result = graph.invoke(cast("Any", payload), config=config)
        # Human-in-the-loop: the graph pauses at plan approval; loop until done.
        while "__interrupt__" in result:
            intr = result["__interrupt__"][0]
            decision = _plan_decision(dict(intr.value), auto_approve)
            result = graph.invoke(Command(resume=decision), config=config)
    except BudgetExceededError as exc:
        print(f"STOPPED: {exc}\n")
        _print_partial(graph, config)
        print(f"\nResume once ready with: research --thread {thread_id}")
        print(session_cost.summary())
        return
    finally:
        recorder.flush()

    if result.get("refusal"):
        print("REFUSED:")
        print(result["refusal"])
        return
    for note in result.get("input_notes", []):
        print(f"Note: {note}")

    if result.get("prior_context"):
        print("Episodic memory recalled related past research:")
        print(result["prior_context"] + "\n")

    route = result.get("route")
    if route:
        print(f"Route: {route}")
    if route == "simple_lookup":
        print("\n" + "=" * 72)
        print(result.get("report", "(no answer produced)"))
        print("=" * 72 + "\nSources:")
        for i, source in enumerate(result.get("sources", []), start=1):
            print(f"  [{i}] {source.title} — {source.url}")
        print("\n" + session_cost.summary())
        return

    sub_topics = result.get("sub_topics", [])
    print(f"Plan ({len(sub_topics)} sub-topic{'s' if len(sub_topics) != 1 else ''}):")
    for sub_topic in sub_topics:
        print(f"  - {sub_topic.title}  [query: {sub_topic.search_query}]")

    for research in result.get("research_results", []):
        tools_used = sorted(
            {
                line.split("(", 1)[0].removeprefix("Action: ")
                for line in research.history
                if line.startswith("Action: ")
            }
        )
        suffix = " (replanned)" if research.attempt >= 2 else ""
        print(
            f"  {research.sub_topic.title}{suffix}: {len(research.sources)} sources "
            f"via {', '.join(tools_used) or 'no tools'}"
        )
    review = result.get("review")
    if review is not None:
        revisions = result.get("revision_count", 0)
        print(f"Review: {review.score}/10 after {revisions} revision(s)")

    print("\n" + "=" * 72)
    print(result.get("report", "(no report produced)"))
    print("=" * 72 + "\nSources:")
    for i, source in enumerate(result.get("sources", []), start=1):
        print(f"  [{i}] {source.title} — {source.url}")
    print("\n" + session_cost.summary())
    print(f"Trace: research --show-trace {thread_id}")


def main() -> None:
    from deep_research.net import setup_tls

    setup_tls()
    # Windows consoles default to a legacy codepage (cp1252) that cannot print
    # arbitrary source titles; force UTF-8 instead of crashing on foreign chars.
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(prog="research", description="Deep research agent CLI")
    parser.add_argument("topic", nargs="?", default=None, help="Research topic (quoted)")
    parser.add_argument(
        "--thread",
        default=None,
        help="Resume a previous run from its checkpoint (thread id printed at start)",
    )
    parser.add_argument(
        "--auto-approve",
        action="store_true",
        help="Skip the plan-approval prompt (for demos/scripts)",
    )
    parser.add_argument(
        "--show-trace",
        default=None,
        metavar="THREAD_ID",
        help="Print the span timeline of a past run and exit",
    )
    args = parser.parse_args()
    if args.show_trace:
        from deep_research.observability.tracing import format_trace

        print(format_trace(args.show_trace))
    elif args.topic or args.thread:
        _run(args.topic, args.thread, auto_approve=args.auto_approve)
    else:
        _smoke_check()


if __name__ == "__main__":
    main()
