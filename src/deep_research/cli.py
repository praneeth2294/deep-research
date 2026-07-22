"""Command-line entry point.

Phase 0: placeholder that proves the package imports and config loads.
Phase 1 replaces this with `research "<topic>"` running the real graph.
"""

from deep_research import __version__
from deep_research.config import get_settings


def main() -> None:
    settings = get_settings()
    print(f"deep-research v{__version__} — scaffolding OK (environment: {settings.environment})")
    print("The research pipeline arrives in Phase 1. See RUNBOOK.md.")


if __name__ == "__main__":
    main()
