"""Shared key-building primitives for architectural ratchets (FR-008 / WP06).

.. note::
   **Promoted to ``src/`` (#2441 / FR-003).** The implementation now lives in
   :mod:`specify_cli.contracts.anchoring` so production code (the Contract
   Registry loader/validator + the retirement absence-sweep driver) can depend
   on the same DIR-041-compliant content-anchoring primitive — ``src/`` cannot
   import from ``tests/``, so the primitive had to move to ``src/``. This module
   is now a thin **re-export shim**: every existing ratchet caller keeps
   importing ``composite_key`` / ``code_tokens_by_line`` / ``enclosing_qualname``
   / ``composite_key_from_file`` from ``tests.architectural._ratchet_keys`` with
   NO behaviour change.

Provides two complementary building blocks that together produce a
``(enclosing_qualname, normalized_token_line)`` composite key for any line in a
Python source file.  The key's **values** are content-derived, but the
**lookup** is line-number-indexed — see :mod:`specify_cli.contracts.anchoring`
for the narrowed drift-resistance contract (#3369): a blank/comment insertion
is survived only when it lands *below* the guarded site, or when ``lineno`` is
re-derived against the same tree (the ratchet-scan case).  A pinned
``lineno`` replayed against a drifted tree with content inserted *above* the
site reads a different line and produces a different key for a site that did
not semantically change.

Usage
-----
::

    from tests.architectural._ratchet_keys import composite_key

    source = Path("src/foo/bar.py").read_text(encoding="utf-8")
    key = composite_key(source, lineno=42)
    # returns (qualname_str, token_line_str)

See :mod:`specify_cli.contracts.anchoring` for the full design notes.

Content-descriptor resolver (IC-DESCRIPTOR, #2469 WP02)
---------------------------------------------------------
The section below adds the **shared content-descriptor resolver** every WS1
ratchet gate (WP03/WP04) consumes: it resolves a
``(rel_path, qualname, token_substring, occurrence, rationale)`` descriptor to
**exactly one** live finding's composite key, and a staleness helper that is
exactly-one + key-equal (never "≥1" — see ``research.md`` D-1). See
``kitty-specs/content-address-ratchet-allowlists-01KX8M4D/contracts/descriptor-resolver.md``
for the authoritative interface contract.

Key shape — reuse, not fork
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
``CompositeKey`` below is **the** declaration of the canonical
**path-qualified 3-tuple** row identity: ``(rel_path, qualname, token_line)``,
built from the canonical :func:`composite_key` primitive (no second
token/qualname algorithm). Consumers import it from here — the
``tests/architectural/_surface_resolution_scan.py`` scanner imports both
``CompositeKey`` and ``composite_key_from_file`` — rather than re-declaring the
alias. This module is the designated home "every WS1 gate imports", which is the
"relocate" half of the plan's "reuse/relocate, do not fork a third key-builder"
instruction.
"""

from __future__ import annotations

from typing import NamedTuple

from specify_cli.contracts.anchoring import _build_qualname_map as build_qualname_map
from specify_cli.contracts.anchoring import (
    code_tokens_by_line,
    composite_key,
    composite_key_from_file,
    enclosing_qualname,
)
from tests.architectural._ast_scan import parse_source

__all__ = [
    "code_tokens_by_line",
    "composite_key",
    "composite_key_from_file",
    "enclosing_qualname",
    "build_qualname_map",
    "ContentDescriptor",
    "CompositeKey",
    "DescriptorResolutionError",
    "resolve_descriptor",
    "descriptor_still_live",
    "assert_descriptor_unique_within_qualname",
]


# ---------------------------------------------------------------------------
# Content-descriptor types
# ---------------------------------------------------------------------------


class ContentDescriptor(NamedTuple):
    """A content-addressed pointer to exactly one finding site.

    ``rel_path``
        Path to the source file, relative to the repo root (e.g.
        ``src/specify_cli/coordination/status_transition.py``).
    ``qualname``
        The enclosing dotted qualname (:func:`enclosing_qualname`'s output)
        the finding must live inside.
    ``token_substring``
        A substring of the finding's **normalized** token line
        (:func:`code_tokens_by_line`'s output) — normalized token space, never
        raw source (see ``descriptor-resolver.md``'s "Authoring rule").
    ``occurrence``
        0-based ordinal to select among multiple same-qualname/same-substring
        candidates (D-2's disambiguator). ``None`` means "the substring MUST be
        unique within the qualname".
    ``rationale``
        Human-readable justification for the allow-list entry.
    """

    rel_path: str
    qualname: str
    token_substring: str
    occurrence: int | None
    rationale: str


#: The path-qualified 3-tuple row identity: ``(rel_path, qualname, token_line)``.
#: The single declaration — see the module docstring's "Key shape — reuse, not
#: fork" note; scanners import it from here.
CompositeKey = tuple[str, str, str]


class DescriptorResolutionError(ValueError):
    """Raised when a :class:`ContentDescriptor` fails to resolve to exactly one finding.

    Covers both the 0-match and (without an ``occurrence``) the >1-match case —
    the D-1 "exactly-one, never ≥1" rule. Callers MUST NOT catch this to silently
    fall back to a partial match; the only sanctioned reaction is
    :func:`descriptor_still_live` translating it to ``False``.
    """


# ---------------------------------------------------------------------------
# Resolution helpers (kept small individually — S3776 / Sonar S3776 ≤15)
# ---------------------------------------------------------------------------


def _qualname_for_line(qualname_map: dict[tuple[int, int], str], lineno: int) -> str:
    """Innermost enclosing qualname for ``lineno`` given a pre-built qualname map.

    Mirrors :func:`enclosing_qualname`'s smallest-span selection, but operates on
    an already-built map so a file-wide scan (as :func:`_candidate_lines`
    performs) pays for a single AST parse rather than one parse per candidate
    line (GAP-2 — build the qualname map ONCE per file).
    """
    candidates = [
        (end - start, qn) for (start, end), qn in qualname_map.items() if start <= lineno <= end
    ]
    if not candidates:
        return "<module>"
    _, qn = min(candidates)
    return qn


def _candidate_lines(
    source: str, qualname: str, token_substring: str, *, display: str = "<descriptor source>"
) -> list[int]:
    """Return line numbers (1-based, file order) inside ``qualname`` whose
    normalized token line contains ``token_substring``.

    Builds the AST + qualname map exactly once (GAP-2), then scans
    :func:`code_tokens_by_line`'s NORMALIZED output — never raw source, per the
    descriptor-resolver contract's authoring rule. Unparseable ``source`` fails
    closed (``UnparseableSourceError`` naming ``display``, #5139) instead of
    reading as zero candidates.
    """
    tree = parse_source(source, display=display)
    qualname_map = build_qualname_map(tree)
    tokens = code_tokens_by_line(source)
    return [
        lineno
        for lineno in sorted(tokens)
        if token_substring in tokens[lineno] and _qualname_for_line(qualname_map, lineno) == qualname
    ]


def _assert_exactly_one(candidates: list[int], descriptor: ContentDescriptor) -> None:
    """RAISE (RED) unless ``candidates`` resolves unambiguously to one finding.

    - No ``occurrence``: exactly one candidate is required — 0 or >1 both RED.
      This is the D-1 "exactly-one, never ≥1" rule: silently picking the first
      of several candidates would let a routed-away allowance mask a sibling
      offender.
    - With an ``occurrence``: the ordinal must be a valid index into
      ``candidates`` — 0 candidates, or an out-of-range ordinal, is RED.
    """
    if descriptor.occurrence is None:
        if len(candidates) != 1:
            raise DescriptorResolutionError(
                f"descriptor {descriptor!r} resolved to {len(candidates)} finding(s) "
                f"(need exactly 1) at lines {candidates!r}. Never silently pick the "
                "first — either tighten `token_substring` to the unique finding line, "
                "or add an explicit `occurrence` ordinal to disambiguate."
            )
        return
    if not (0 <= descriptor.occurrence < len(candidates)):
        raise DescriptorResolutionError(
            f"descriptor {descriptor!r} occurrence={descriptor.occurrence} is out of "
            f"range for {len(candidates)} candidate(s) at lines {candidates!r}."
        )


def _select_occurrence(candidates: list[int], occurrence: int | None) -> int:
    """Return the candidate index selected by ``occurrence`` (0 when unset).

    Callers MUST run :func:`_assert_exactly_one` first — this helper assumes the
    index is already known-valid and performs no bounds checking of its own.
    """
    return occurrence if occurrence is not None else 0


# ---------------------------------------------------------------------------
# Public resolver surface
# ---------------------------------------------------------------------------


def resolve_descriptor(source: str, descriptor: ContentDescriptor) -> CompositeKey:
    """Resolve ``descriptor`` to the **exactly one** live finding's composite key.

    RAISES :class:`DescriptorResolutionError` (RED) if the match count is 0, or
    (with no ``occurrence``) >1 — never silently picks the first (D-1). See
    ``descriptor-resolver.md`` for the full contract.
    """
    candidates = _candidate_lines(
        source, descriptor.qualname, descriptor.token_substring, display=descriptor.rel_path
    )
    _assert_exactly_one(candidates, descriptor)
    lineno = candidates[_select_occurrence(candidates, descriptor.occurrence)]
    qualname, token_line = composite_key(source, lineno)
    return (descriptor.rel_path, qualname, token_line)


def descriptor_still_live(
    source: str, descriptor: ContentDescriptor, seeded_key: CompositeKey
) -> bool:
    """``True`` iff ``descriptor`` resolves to exactly one finding equal to ``seeded_key``.

    Exactly-one AND key-equal — never "≥1 finding matches" (the D-1 bite hole: a
    sanctioned site routed away while a NEW offender lands in the same qualname
    must RED, not stay silently green because "a" match still exists). Any
    deviation — 0 matches, >1 matches, or a matching-but-different key — returns
    ``False``, and the caller's twin-guard must RED.
    """
    try:
        return resolve_descriptor(source, descriptor) == seeded_key
    except DescriptorResolutionError:
        return False


def assert_descriptor_unique_within_qualname(source: str, descriptor: ContentDescriptor) -> None:
    """Import-time guard (GAP-1): RAISE unless ``descriptor`` resolves unambiguously.

    The highest-risk authoring foot-gun: a ``token_substring`` copied from a
    *non-finding* line (e.g. a ``def`` line, or a docstring quoting the pattern)
    can resolve to the wrong line, or to zero/multiple lines, producing a
    spurious RED (or worse, a silently wrong key) far from the authoring site.
    Consuming gates call this for every seeded descriptor at **import time** so
    the mistake surfaces immediately, not at review time.

    Equivalent to calling :func:`resolve_descriptor` and discarding the result,
    but named for its standalone import-time-assertion purpose.
    """
    candidates = _candidate_lines(
        source, descriptor.qualname, descriptor.token_substring, display=descriptor.rel_path
    )
    _assert_exactly_one(candidates, descriptor)
