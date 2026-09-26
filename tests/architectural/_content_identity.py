"""The matching authority for content-keyed ratchet allowlists (D-OP-9).

This module is **the** resolve/partition authority for allowlists whose entries
are :class:`~tests.architectural._ratchet_keys.ContentDescriptor` values rather
than ``(file, lineno)`` pins. A gate that suppresses findings by content
identity resolves its descriptors with :func:`resolve_allowlist` and splits its
findings with :func:`partition_findings`; it does not hand-roll an eighth
matcher. The descriptor substrate (``ContentDescriptor``, ``CompositeKey``,
``resolve_descriptor`` and its exactly-one rule) stays in
:mod:`tests.architectural._ratchet_keys`; this module only composes it.

Multiset semantics
------------------
:func:`partition_findings` treats the allowlist as a **multiset**: one resolved
entry suppresses at most one finding, and the key always carries ``rel_path``,
so an entry in one file never blesses a finding in another. A set match is not
enough because :func:`~tests.architectural._ratchet_keys.composite_key` strips
string literals. In ``src/charter/activation/neutrality/lint.py`` the two
statements at lines 379 and 380 of ``_default_scan_roots`` both tokenize to
``roots . extend ( _iter_mission_scan_roots ( repo_root / / / ) )``. Only the
first is a built-in join today; under set semantics its single allowlist entry
would also bless a future built-in join on the second line. With a
``collections.Counter`` the second finding is reported.

Stale entries are a caller policy
---------------------------------
:func:`resolve_allowlist` reports descriptors that fail the exactly-one rule
and :func:`partition_findings` reports ``unused`` keys; what to do with them is
the caller's decision (D-OP-8). Hand-curated allowlists fail on either; the
census baseline warns. Neither helper raises for a stale entry, so a stale
entry never becomes a collection error that takes out a whole module.

Drift mutators
--------------
:func:`with_blank_line_at_top` and :func:`with_probe_above_statement` produce
line-drifted copies of a source so a gate can prove its allowlist survives
drift (NFR-001): the ``(unexpected, suppressed)`` identities must be unchanged.

Text serialisation
------------------
:func:`render_descriptor_line` / :func:`parse_descriptor_line` are the one
text form of a descriptor for file-backed allowlists:
``<repo-rel path>::<qualname>::<token_substring>[::<occurrence>]``.

Known non-adopters (follow-up FR-019(d))
----------------------------------------
These matchers predate this module and still hand-roll their own matching.
Adopting this module changes their semantics (set to multiset, 2-tuple to
3-tuple keys), so each needs its own red-first change:

* ``tests/architectural/_sole_door_scan.py`` (``resolve_exclusion_keys``)
* ``tests/architectural/test_trio_seam_only.py`` (import-time descriptor block)
* ``tests/architectural/test_single_mission_surface_resolver.py``
* ``tests/architectural/test_no_read_side_bypass.py``
* ``tests/architectural/test_no_write_side_rederivation.py``
* ``tests/architectural/untrusted_path_audit/audit.py``
  (``check_undercount`` / ``check_overcount``)

Where the tests live
--------------------
The unit tests are in ``tests/architectural/test_content_identity.py``, next to
the consumers and collected under the ``architectural`` marker with them. The
resolver's own tests stay in ``tests/unit/test_descriptor_resolver.py``.
"""

from __future__ import annotations

import ast
from collections import Counter
from collections.abc import Callable, Hashable, Iterable
from typing import TypeVar

from tests.architectural._ratchet_keys import (
    CompositeKey,
    ContentDescriptor,
    DescriptorResolutionError,
    resolve_descriptor,
)

__all__ = [
    "parse_descriptor_line",
    "partition_findings",
    "render_descriptor_line",
    "resolve_allowlist",
    "with_blank_line_at_top",
    "with_probe_above_statement",
]

K = TypeVar("K", bound=Hashable)
T = TypeVar("T")

_FIELD_SEP = "::"
_PROBE_COMMENT = "# drift-probe"


# ---------------------------------------------------------------------------
# Resolve + partition
# ---------------------------------------------------------------------------


def resolve_allowlist(
    descriptors: Iterable[ContentDescriptor], source_for: Callable[[str], str]
) -> tuple[Counter[CompositeKey], list[tuple[ContentDescriptor, str]]]:
    """Resolve *descriptors* against ``source_for(rel_path)``.

    Returns the resolved keys as a multiset and ``(descriptor, reason)`` for
    every descriptor that did not resolve to exactly one site, or whose source
    could not be read. Never raises for a stale descriptor.
    """
    allowed: Counter[CompositeKey] = Counter()
    errors: list[tuple[ContentDescriptor, str]] = []
    for descriptor in descriptors:
        try:
            source = source_for(descriptor.rel_path)
        except (KeyError, OSError) as exc:
            errors.append((descriptor, f"source unavailable for {descriptor.rel_path}: {exc!r}"))
            continue
        try:
            allowed[resolve_descriptor(source, descriptor)] += 1
        except DescriptorResolutionError as exc:
            errors.append((descriptor, str(exc)))
    return allowed, errors


def partition_findings(findings: Iterable[tuple[K, T]], allowed: Counter[K]) -> tuple[list[T], Counter[K]]:
    """Split ``(key, item)`` findings into ``(unexpected, unused)``.

    MULTISET: each allowed key suppresses at most as many findings as its
    count. ``unexpected`` keeps finding order; ``unused`` is what remains of
    ``allowed`` after consumption (positive counts only).
    """
    remaining: Counter[K] = Counter(allowed)
    unexpected: list[T] = []
    for key, item in findings:
        if remaining[key] > 0:
            remaining[key] -= 1
        else:
            unexpected.append(item)
    return unexpected, Counter({key: count for key, count in remaining.items() if count > 0})


# ---------------------------------------------------------------------------
# Drift mutators
# ---------------------------------------------------------------------------


def with_blank_line_at_top(source: str) -> str:
    """Return *source* with one blank line prepended (every line shifts by 1)."""
    return "\n" + source


def _stmt_start(node: ast.stmt) -> int:
    """First line of *node*, counting decorators as part of the statement."""
    decorators: list[ast.expr] = getattr(node, "decorator_list", [])
    return min([node.lineno, *(decorator.lineno for decorator in decorators)])


def _innermost_stmt(tree: ast.AST, lineno: int) -> tuple[ast.stmt, dict[ast.stmt, ast.stmt]]:
    """The smallest statement spanning *lineno*, plus a child-to-parent statement map."""
    parents: dict[ast.stmt, ast.stmt] = {}
    best: ast.stmt | None = None
    for node in ast.walk(tree):
        if not isinstance(node, ast.stmt):
            continue
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.stmt):
                parents[child] = node
        end = node.end_lineno if node.end_lineno is not None else node.lineno
        if _stmt_start(node) <= lineno <= end and (best is None or _span(node) < _span(best)):
            best = node
    if best is None:
        raise ValueError(f"line {lineno} is not inside any statement")
    return best, parents


def _span(node: ast.stmt) -> int:
    end = node.end_lineno if node.end_lineno is not None else node.lineno
    return end - _stmt_start(node)


def _is_elif(node: ast.stmt, parents: dict[ast.stmt, ast.stmt], lines: list[str]) -> bool:
    """Whether *node* is the ``If`` an ``elif`` clause parses to."""
    parent = parents.get(node)
    return isinstance(node, ast.If) and isinstance(parent, ast.If) and node in parent.orelse and lines[node.lineno - 1].lstrip().startswith("elif")


def with_probe_above_statement(source: str, lineno: int) -> str:
    """Insert ``# drift-probe`` + ``pass`` above the statement containing *lineno*.

    The probe lands above the innermost ``ast.stmt`` spanning *lineno*, at that
    statement's indentation, so it is safe inside multi-line expressions and
    nested functions. Two cases would break syntax and are climbed out of: an
    ``elif`` line inserts above the enclosing ``if``, and a decorated
    definition inserts above its first decorator.
    """
    lines = source.splitlines(keepends=True)
    node, parents = _innermost_stmt(ast.parse(source), lineno)
    while _is_elif(node, parents, lines):
        node = parents[node]
    start = _stmt_start(node)
    anchor = lines[start - 1]
    indent = anchor[: len(anchor) - len(anchor.lstrip())]
    probe = f"{indent}{_PROBE_COMMENT}\n{indent}pass\n"
    return "".join([*lines[: start - 1], probe, *lines[start - 1 :]])


# ---------------------------------------------------------------------------
# Text serialisation
# ---------------------------------------------------------------------------


def render_descriptor_line(descriptor: ContentDescriptor) -> str:
    """Render ``<rel_path>::<qualname>::<token_substring>[::<occurrence>]``.

    Raises ``ValueError`` if a field contains ``::`` (the form could not be
    parsed back).
    """
    fields = [descriptor.rel_path, descriptor.qualname, descriptor.token_substring]
    if any(_FIELD_SEP in field for field in fields):
        raise ValueError(f"descriptor field contains {_FIELD_SEP!r}; cannot render {descriptor!r}")
    if descriptor.occurrence is not None:
        fields.append(str(descriptor.occurrence))
    return _FIELD_SEP.join(fields)


def _parse_occurrence(raw: str, line: str) -> int:
    try:
        occurrence = int(raw)
    except ValueError:
        raise ValueError(f"descriptor line {line!r}: occurrence {raw!r} is not an integer") from None
    if occurrence < 0:
        raise ValueError(f"descriptor line {line!r}: occurrence {occurrence} is negative")
    return occurrence


def _split_fields(text: str) -> list[str]:
    """Split *text* into its ``::`` fields, tolerating tokens that end in ``:``.

    Path and qualname are split from the left; the optional occurrence from the
    right, so a token ending in ``:`` followed by ``::<occurrence>`` (``== :::2``)
    splits as ``== :`` / ``2`` rather than ``== `` / ``:2``.
    """
    fields = text.split(_FIELD_SEP, 2)
    if len(fields) == 3 and _FIELD_SEP in fields[2]:
        fields[2:] = fields[2].rsplit(_FIELD_SEP, 1)
    return fields


def parse_descriptor_line(line: str, rationale: str) -> ContentDescriptor:
    """Parse the text form produced by :func:`render_descriptor_line`.

    Token substrings may contain ``:`` (also as their last character) but never
    ``::``. Raises ``ValueError`` naming *line* for anything other than 3 or 4
    non-empty fields, or a non-integer / negative occurrence.
    """
    fields = _split_fields(line.rstrip("\r\n"))
    if len(fields) < 3 or _FIELD_SEP in fields[2]:
        raise ValueError(f"descriptor line {line!r}: expected 3 or 4 '::'-separated fields")
    if any(not field for field in fields):
        raise ValueError(f"descriptor line {line!r}: empty field")
    occurrence = _parse_occurrence(fields[3], line) if len(fields) == 4 else None
    return ContentDescriptor(fields[0], fields[1], fields[2], occurrence, rationale)
