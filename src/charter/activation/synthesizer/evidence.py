"""Evidence bundle dataclasses for Phase 3 charter synthesis.

These frozen dataclasses transport structured evidence inputs (code signals,
URL lists, corpus snapshots) into the synthesis pipeline without modifying
the adapter interface.  Only ``EvidenceBundle`` is attached to
``SynthesisRequest``; all other types are nested inside it.

Timestamps (``detected_at``, ``loaded_at``, ``collected_at``) are excluded
from hash computation so that re-collecting the same evidence at different
times produces identical fixture hashes.

See data-model.md §E-5 for authoritative field documentation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

__all__ = [
    "CodeSignals",
    "CorpusEntry",
    "CorpusSnapshot",
    "EvidenceBundle",
]


_STACK_ID_RE = re.compile(r"^[a-z][a-z0-9+]*$")
_SNAPSHOT_ID_RE = re.compile(r"^[a-z][a-z0-9-]+-v\d+\.\d+\.\d+$")


@dataclass(frozen=True)
class CodeSignals:
    """Structured stack signals from the code-reading collector.

    Invariants enforced in ``__post_init__``:

    - ``scope_tag`` must equal ``primary_language`` (used by neutrality gate).
    - ``languages``, when non-empty, starts with ``primary_language`` (FR-010).
    - ``stack_id`` must match ``^[a-z][a-z0-9+]*$``.
    - Every path in ``representative_files`` must be a non-empty repo-relative
      forward-slash path (no leading ``/``).

    ``detected_at`` is an ISO 8601 UTC string that is intentionally excluded
    from hash computation.
    """

    stack_id: str
    primary_language: str
    frameworks: tuple[str, ...]
    test_frameworks: tuple[str, ...]
    scope_tag: str  # equals primary_language; used by neutrality gate
    representative_files: tuple[str, ...]  # repo-relative forward-slash paths
    detected_at: str  # ISO 8601 UTC — excluded from hash
    #: Every observed language, primary first. Empty when none was observed. It enters
    #: the evidence hash only when it holds more than one language (FR-012).
    languages: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.scope_tag != self.primary_language:
            raise ValueError(
                f"scope_tag must equal primary_language, "
                f"got {self.scope_tag!r} != {self.primary_language!r}"
            )
        if self.languages and self.languages[0] != self.primary_language:
            raise ValueError(
                f"languages must start with primary_language, "
                f"got {self.languages!r} for {self.primary_language!r}"
            )
        if not _STACK_ID_RE.match(self.stack_id):
            raise ValueError(f"Invalid stack_id format: {self.stack_id!r}")
        for f in self.representative_files:
            if not f or f.startswith("/"):
                raise ValueError(
                    "representative_files must be non-empty repo-relative paths "
                    f"without leading slash: {f!r}"
                )


@dataclass(frozen=True)
class CorpusEntry:
    """One best-practice entry within a corpus snapshot."""

    topic: str
    tags: tuple[str, ...]
    guidance: str


@dataclass(frozen=True)
class CorpusSnapshot:
    """Profile-keyed best-practice corpus snapshot.

    Invariants enforced in ``__post_init__``:

    - ``snapshot_id`` must match ``^[a-z][a-z0-9-]+-v[0-9]+\\.[0-9]+\\.[0-9]+$``
      (e.g. ``python-v1.0.0``).

    ``loaded_at`` is an ISO 8601 UTC string that is intentionally excluded
    from hash computation.
    """

    snapshot_id: str  # e.g. "python-v1.0.0" — recorded in provenance
    profile_key: str
    entries: tuple[CorpusEntry, ...]
    loaded_at: str  # ISO 8601 UTC — excluded from hash

    def __post_init__(self) -> None:
        if not _SNAPSHOT_ID_RE.match(self.snapshot_id):
            raise ValueError(f"Invalid snapshot_id format: {self.snapshot_id!r}")


@dataclass(frozen=True)
class EvidenceBundle:
    """Aggregated evidence inputs for one synthesis run.

    This is the ONLY transport for evidence into the synthesis pipeline.
    ``adapter_hints`` is NOT used for evidence.

    Invariants enforced in ``__post_init__``:

    - No empty strings in ``url_list``.

    ``collected_at`` is an ISO 8601 UTC string that is intentionally excluded
    from hash computation.

    The ``is_empty`` property returns ``True`` when no evidence has been
    populated (all fields at their defaults).  When ``is_empty`` is ``True``,
    ``normalize_request_for_hash`` produces byte-for-byte identical output to
    the pre-evidence code path.
    """

    code_signals: CodeSignals | None = None
    url_list: tuple[str, ...] = ()  # bare URLs; production adapter reads them natively
    corpus_snapshot: CorpusSnapshot | None = None
    collected_at: str = ""  # ISO 8601 UTC — excluded from hash

    def __post_init__(self) -> None:
        for u in self.url_list:
            if not u:
                raise ValueError("url_list must not contain empty strings")

    @property
    def is_empty(self) -> bool:
        """Return True when no evidence has been populated."""
        return (
            self.code_signals is None
            and not self.url_list
            and self.corpus_snapshot is None
        )
