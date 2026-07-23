"""Writer helpers: model-content normalization across provider formats."""

from langchain_core.messages import AIMessage

from deep_research.llm.content import extract_text


def test_extract_text_plain_string() -> None:
    assert extract_text(AIMessage(content="hello [1]")) == "hello [1]"


def test_extract_text_gemini3_parts() -> None:
    message = AIMessage(
        content=[
            {"type": "text", "text": "para one [1]", "extras": {"signature": "opaque-blob"}},
            {"type": "thinking", "thinking": "internal reasoning - must not leak"},
            {"type": "text", "text": "para two [2]"},
        ]
    )
    text = extract_text(message)
    assert text == "para one [1]\npara two [2]"
    assert "opaque-blob" not in text
    assert "internal reasoning" not in text
