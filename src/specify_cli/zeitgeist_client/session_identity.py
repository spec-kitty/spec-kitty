"""Logical publisher identity shared by command and reader processes.

A harness can export SPEC_KITTY_ZEITGEIST_SESSION_ID to join its subprocesses
into one logical agent, or to keep two genuinely concurrent agents distinct.
Codex's thread identifier provides that boundary automatically. Unidentified
processes — no override, no harness thread — share one stable default
logical session, because the credential store and every reader surface
(``spec-kitty zeitgeist watch``/``status``, the MCP stdio tools) are keyed by
this selector: a per-process value would partition the cache so a credential
stored by one command could never be loaded by the next (#4217 squad MAJOR).
The default is deliberately not derived from any authenticated account
identity — that would be circular (the store path is needed to load the
credential that identifies the account) — and the runtime state root it
lives under is already per-user (``SPEC_KITTY_HOME`` / ``~/.spec-kitty``),
so one human's processes are one logical agent by default and only genuinely
concurrent agents need the env override. This selector is not the relay's
opaque session_ref: publication uses the raw session reference returned by
the SaaS lease issuer.
"""

from __future__ import annotations

import hashlib
import os
import re

_SESSION_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}")

#: The stable selector every unidentified process shares. Not a secret and
#: never sent anywhere by itself — it only names the local credential-store
#: partition and the SaaS-side logical grouping, so a constant is correct.
DEFAULT_SESSION_ID = "default"


def logical_session_id() -> str:
    """Return the current logical agent selector, refusing malformed overrides."""
    explicit = os.environ.get("SPEC_KITTY_ZEITGEIST_SESSION_ID")
    if explicit is not None:
        if not _SESSION_PATTERN.fullmatch(explicit):
            raise ValueError("SPEC_KITTY_ZEITGEIST_SESSION_ID must be a 1-128 character ASCII identifier")
        return explicit
    thread = os.environ.get("CODEX_THREAD_ID")
    if thread:
        # Namespace a harness-local selector; never derive a relay egress ref.
        return "codex-" + hashlib.sha256(thread.encode()).hexdigest()  # noqa: TID251 -- harness identity, not charter hashing
    return DEFAULT_SESSION_ID
