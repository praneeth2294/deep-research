"""Quality gate — pure Python, zero LLM calls (deck: Gate / cost engineering).

Scores each researcher's result on evidence quality. Results below the
threshold are flagged for replanning — but only once per sub-topic (attempt 1
only), so the replan loop is bounded by construction.

Scoring (0..1):
- 50% mean domain trust  (curated weights; unknown domains get a neutral 0.6)
- 25% snippet substance  (share of sources with a meaningfully long snippet)
- 25% source count       (3+ sources = full marks)
"""

from urllib.parse import urlparse

from deep_research.config import get_settings
from deep_research.graph.state import ResearchState
from deep_research.schemas.planner import SubTopic
from deep_research.schemas.research import ResearchResult

# Curated trust weights. Not exhaustive - unknown domains score neutral.
_DOMAIN_TRUST: dict[str, float] = {
    "wikipedia.org": 1.0,
    "arxiv.org": 1.0,
    "github.com": 0.9,
    "ibm.com": 0.9,
    "microsoft.com": 0.9,
    "google.com": 0.9,
    "langchain.com": 0.9,
    "medium.com": 0.5,
    "dev.to": 0.5,
    "linkedin.com": 0.4,
    "youtube.com": 0.3,
    "facebook.com": 0.2,
    "reddit.com": 0.4,
}
_NEUTRAL_TRUST = 0.6
_MIN_SNIPPET_CHARS = 200
_FULL_MARKS_SOURCE_COUNT = 3


def domain_trust(url: str) -> float:
    """Trust weight for a URL's registered domain (suffix match, e.g. docs.x.com -> x.com)."""
    host = urlparse(url).netloc.lower().removeprefix("www.")
    for domain, weight in _DOMAIN_TRUST.items():
        if host == domain or host.endswith("." + domain):
            return weight
    # .gov / .edu are trustworthy as a class
    if host.endswith((".gov", ".edu")):
        return 1.0
    return _NEUTRAL_TRUST


def score_result(result: ResearchResult) -> float:
    """Deterministic evidence-quality score in [0, 1]."""
    if not result.sources:
        return 0.0
    trust = sum(domain_trust(s.url) for s in result.sources) / len(result.sources)
    substance = sum(len(s.snippet) >= _MIN_SNIPPET_CHARS for s in result.sources) / len(
        result.sources
    )
    count = min(len(result.sources) / _FULL_MARKS_SOURCE_COUNT, 1.0)
    return 0.5 * trust + 0.25 * substance + 0.25 * count


def quality_gate_node(state: ResearchState) -> ResearchState:
    threshold = get_settings().gate_quality_threshold
    results = state.get("research_results", [])
    # Titles that already went through a replanned attempt must not loop again.
    replanned_titles = {r.sub_topic.title for r in results if r.attempt >= 2}
    needs_replan: list[SubTopic] = [
        r.sub_topic
        for r in results
        if r.attempt == 1
        and r.sub_topic.title not in replanned_titles
        and score_result(r) < threshold
    ]
    return {"needs_replan": needs_replan}
