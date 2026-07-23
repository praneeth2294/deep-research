"""The prompt registry loads real, non-empty prompt files."""

import pytest

from deep_research.prompts import load_prompt


@pytest.mark.parametrize("name", ["planner", "writer"])
def test_prompts_load(name: str) -> None:
    text = load_prompt(name)
    assert len(text) > 50


def test_missing_prompt_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_prompt("does-not-exist")
