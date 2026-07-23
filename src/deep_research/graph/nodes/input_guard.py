"""Input-guard node — first node of every run (pure Python, no LLM).

Three jobs, in order:
1. Refuse degenerate input (too short / too long) with an explanation.
2. Refuse topics that are prompt-injection attempts aimed at the system —
   the pipeline researches subjects, it does not execute instructions.
3. Scrub PII from the topic before it reaches any third party (LLM provider,
   search APIs); the run continues with the scrubbed topic, and the user is
   told what kinds of data were removed.

A refusal sets `refusal` (and mirrors it into `report`) and the graph ends
without spending a single LLM call.
"""

from deep_research.graph.state import ResearchState
from deep_research.guardrails.injection import contains_injection
from deep_research.guardrails.pii import scrub_pii

_MIN_TOPIC_CHARS = 8
_MAX_TOPIC_CHARS = 1000


def input_guard_node(state: ResearchState) -> ResearchState:
    topic = state.get("topic", "").strip()

    if len(topic) < _MIN_TOPIC_CHARS:
        message = (
            "Cannot research this input: the topic is empty or too short. "
            "Please provide a research question or subject (at least a few words)."
        )
        return {"refusal": message, "report": message}

    if len(topic) > _MAX_TOPIC_CHARS:
        message = (
            f"Cannot research this input: the topic exceeds {_MAX_TOPIC_CHARS} characters. "
            "Please condense it to the actual question."
        )
        return {"refusal": message, "report": message}

    if contains_injection(topic):
        message = (
            "Cannot research this input: it contains instructions directed at the "
            "assistant (e.g. attempts to override system behavior). This system "
            "researches subjects; it does not execute instructions embedded in topics. "
            "Please rephrase as a research question."
        )
        return {"refusal": message, "report": message}

    scrubbed, findings = scrub_pii(topic)
    notes = [f"Removed {kind} from the topic before processing." for kind in findings]
    return {"topic": scrubbed, "input_notes": notes}
