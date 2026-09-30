"""Data models for ticket-first mission origin binding.

Provides :class:`OriginCandidate`, the external issue a mission's origin is
bound to.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class OriginCandidate:
    """A candidate external issue returned by ticket search.

    All fields are non-empty strings.  ``match_type`` is ``"exact"`` when
    the candidate matched by ID/key, or ``"text"`` when matched by title
    similarity.
    """

    external_issue_id: str
    external_issue_key: str
    title: str
    status: str
    url: str
    match_type: str  # "exact" or "text"
    body: str | None = None
