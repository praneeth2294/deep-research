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


def _run(topic: str) -> None:
    # Imported lazily so `research` (smoke check) works without heavy deps loading.
    from deep_research.graph.builder import build_graph
    from deep_research.guardrails.budget import BudgetExceededError
    from deep_research.observability.cost import session_cost

    print(f"Researching: {topic}\n")
    try:
        result = build_graph().invoke(
            {"topic": topic}, config={"callbacks": [session_cost.callback]}
        )
    except BudgetExceededError as exc:
        print(f"STOPPED: {exc}")
        print(session_cost.summary())
        return

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

    replanned = [r for r in result.get("research_results", []) if r.attempt >= 2]
    if replanned:
        titles = ", ".join(r.sub_topic.title for r in replanned)
        print(f"Replanned after quality gate: {titles}")
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


def main() -> None:
    from deep_research.net import setup_tls

    setup_tls()
    # Windows consoles default to a legacy codepage (cp1252) that cannot print
    # arbitrary source titles; force UTF-8 instead of crashing on foreign chars.
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    parser = argparse.ArgumentParser(prog="research", description="Deep research agent CLI")
    parser.add_argument("topic", nargs="?", default=None, help="Research topic (quoted)")
    args = parser.parse_args()
    if args.topic:
        _run(args.topic)
    else:
        _smoke_check()


if __name__ == "__main__":
    main()
