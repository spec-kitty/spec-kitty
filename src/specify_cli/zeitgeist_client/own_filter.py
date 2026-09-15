"""Relay-owned own-session filtering using cached issuer identity (#295)."""

from __future__ import annotations

import re
from typing import Any

from .credentials import StoredCredential

_IDENTITY = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")


def identity_header(stored: StoredCredential) -> str:
    """Forward both cached publisher identities; never derive relay references."""
    if stored.session_ref is None:
        raise ValueError("Own filtering requires cached publisher identity; run a publishing command in this logical session first")
    if getattr(stored, "focus_capability_credential", None) and stored.focus_session_ref is None:
        raise ValueError("Own filtering requires cached focus publisher identity; renew the focus lease")
    refs = []
    for value in (stored.session_ref, stored.focus_session_ref):
        if value is None:
            continue
        if not isinstance(value, str) or not _IDENTITY.fullmatch(value):
            raise ValueError("Malformed cached Zeitgeist publisher identity; renew checkout")
        if value not in refs:
            refs.append(value)
    if not refs:
        raise ValueError("Own filtering requires cached publisher identity; run a publishing command in this logical session first")
    return ",".join(refs)


def require_ack(headers: Any) -> None:
    """Fail before consuming a response unless the relay confirms filtering."""
    if headers.get("X-Zeitgeist-Filter-Own") != "true":
        raise ValueError("Zeitgeist relay did not confirm own filtering; upgrade the relay or explicitly request a raw feed")
