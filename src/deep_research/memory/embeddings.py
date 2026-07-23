"""Text embeddings for memory (episodic + semantic).

Uses the Google embedding API — a separate quota pool from generation models.
Fails fast with a setup hint when no key is configured; memory callers treat
that as "memory unavailable" and degrade gracefully.
"""

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from deep_research.config import get_settings


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts (one vector per text)."""
    settings = get_settings()
    if settings.google_api_key is None:
        raise RuntimeError("GOOGLE_API_KEY is not set - memory embeddings unavailable.")
    client = GoogleGenerativeAIEmbeddings(
        model=settings.embedding_model,
        google_api_key=settings.google_api_key,
    )
    return client.embed_documents(texts)
