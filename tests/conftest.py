"""Session-wide test setup: OS trust store for any test that touches HTTPS."""

from deep_research.net import setup_tls

setup_tls()
