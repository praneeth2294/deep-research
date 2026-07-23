"""Network/TLS setup.

Python HTTP clients bundle their own CA list (certifi) and ignore the OS
certificate store. On machines behind a TLS-intercepting proxy (Zscaler,
Netskope, corporate AV), every HTTPS call then fails with
CERTIFICATE_VERIFY_FAILED because the proxy's CA lives only in the OS store.

`truststore` patches Python's SSL to validate against the OS store instead —
the same approach pip uses. Call `setup_tls()` once at every process entry
point (CLI, API, test session) BEFORE any HTTPS connection is created.
"""

import truststore

_installed = False


def setup_tls() -> None:
    """Make Python trust the operating-system certificate store (idempotent)."""
    global _installed
    if not _installed:
        truststore.inject_into_ssl()
        _installed = True
