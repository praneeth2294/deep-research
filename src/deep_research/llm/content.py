"""Model-response content normalization (provider-format differences)."""

from langchain_core.messages import BaseMessage


def extract_text(message: BaseMessage) -> str:
    """Return only the text of a model response.

    Gemini 3 returns `content` as a list of typed parts (text blocks plus
    reasoning-signature blobs); older models return a plain string. Never
    `str()` the raw content — normalize here.
    """
    content = message.content
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for part in content:
        if isinstance(part, str):
            parts.append(part)
        elif isinstance(part, dict) and part.get("type") == "text":
            parts.append(str(part.get("text", "")))
    return "\n".join(parts).strip()
