"""Eval judges: deterministic citation checks + LLM-as-judge scoring."""

import re
from typing import cast

from pydantic import BaseModel, Field

from deep_research.llm.tiering import structured_llm
from deep_research.prompts import load_prompt
from deep_research.schemas.research import Source

_CITATION = re.compile(r"\[(\d{1,3})\]")


class CitationCheck(BaseModel):
    """Deterministic (free, offline) citation validation."""

    cited: list[int]
    invalid: list[int]

    @property
    def has_citations(self) -> bool:
        return bool(self.cited)

    @property
    def all_valid(self) -> bool:
        return bool(self.cited) and not self.invalid


def check_citations(report: str, source_count: int) -> CitationCheck:
    """Every [n] in the report must resolve to an existing source number."""
    cited = sorted({int(match) for match in _CITATION.findall(report)})
    invalid = [n for n in cited if n < 1 or n > source_count]
    return CitationCheck(cited=cited, invalid=invalid)


class JudgeVerdict(BaseModel):
    faithfulness: int = Field(ge=0, le=10)
    coverage: int = Field(ge=0, le=10)
    citation_quality: int = Field(ge=0, le=10)
    passed: bool
    issues: list[str] = Field(default_factory=list)


def judge_report(topic: str, report: str, sources: list[Source]) -> JudgeVerdict:
    """LLM-as-judge scoring against the actual sources (cheap model)."""
    numbered = "\n\n".join(
        f"[{i}] {s.title}\nURL: {s.url}\nContent: {s.snippet[:800]}"
        for i, s in enumerate(sources, start=1)
    )
    return cast(
        "JudgeVerdict",
        structured_llm(JudgeVerdict, tier="cheap").invoke(
            [
                ("system", load_prompt("judge")),
                (
                    "human",
                    f"Topic: {topic}\n\nReport:\n{report}\n\nNumbered sources:\n\n{numbered}",
                ),
            ]
        ),
    )
