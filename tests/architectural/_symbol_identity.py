"""WP06 (IC-WS2-SPIKE) — relocation-tolerant dead-symbol identity prototype.

.. warning::
   **Design-spike scaffolding, NOT wired into any gate.** This module is
   ``_``-prefixed and lives under ``tests/architectural/`` (never
   ``src/``) exactly like ``_ratchet_keys.py``: a ``src/`` module imported only
   by a test would RED ``test_no_dead_modules`` (zero non-test callers, not
   allow-listed), and WP06 owns none of the gate files needed to wire an
   allow-list entry out. Nothing here is collected by pytest and nothing here
   is imported by ``test_no_dead_symbols.py`` (the 343-entry allow-list is
   UNTOUCHED by this WP — see ``tests/unit/test_symbol_identity_spike.py`` for
   the carve/continue recommendation this prototype exists to inform).

Context (spec.md WS2 / C-004 / C-005; research.md D-4/D-5/D-6)
----------------------------------------------------------------
The dead-symbol allow-list in ``test_no_dead_symbols.py`` keys each sanctioned
exception on a bare ``module::Name`` string. That key breaks (needs a manual
re-anchor) whenever a module is renamed or a symbol relocates file-to-file —
the "relocation tax" WS2 exists to retire. The naive fix — drop the module
qualifier and key on the bare name alone — reopens the T004 no-false-negative
regression the ``known_modules`` guard in ``test_no_dead_symbols.py`` exists to
prevent: several *distinct* symbols share a bare name across modules today
(``ArtifactKind`` re-exported into ``charter.offering.directives`` /
``charter.offering.procedures`` / ``charter.offering.tactics``; two independently-defined
``GateDecision`` dataclasses; ``ResolutionResult`` / ``ResolutionTier``
re-exported via both a plain import alias and a lazy ``__getattr__`` facade
dict). A bare-name key would let a live sibling "rescue" a genuinely dead
same-named symbol.

This module prototypes and tests **two candidate keys** against those real
fixtures so the WP06 carve/continue decision is evidence-based rather than
speculative:

* :func:`relocation_only_identity` — ``(bare_name, body_hash)``. No module
  component at all — maximally relocation-tolerant, but (per T026) this
  candidate is proven to COLLIDE for re-export/facade fan-out, because the
  local definition-site text for a bare re-export (``from X import Name``) is
  byte-identical across every module that re-exports the same name under the
  same statement shape. That collision silently reproduces bare-name-alone
  re-blinding via a different route.
* :func:`hybrid_identity` — ``(bare_name, module_path, body_hash)``. Restores
  correctness for the fan-out fixtures (module_path breaks the tie) but,
  for exactly that fan-out subset, forfeits genuine cross-file relocation
  tolerance — moving the re-exporting statement to a new module changes the
  key just like the current ``module::Name`` scheme does today.

Both candidates share one body-hash primitive
(:func:`body_hash_for_definition` / :func:`_hash_token_span`), which isolates
the normalization step (S3776 split per T025) and reuses
``specify_cli.contracts.anchoring.code_tokens_by_line`` for its already-proven
interpreter-independent (3.11/3.12 PEP 701 f-string) token normalization,
rather than forking a second normalizer.
"""

from __future__ import annotations

import ast
import hashlib
from dataclasses import dataclass

from specify_cli.contracts.anchoring import code_tokens_by_line
from tests.architectural._ast_scan import parse_source

__all__ = [
    "ModuleQualifiedSymbolIdentity",
    "SymbolIdentity",
    "body_hash_for_definition",
    "definition_span",
    "hybrid_identity",
    "relocation_only_identity",
]


@dataclass(frozen=True)
class SymbolIdentity:
    """CANDIDATE A key components: bare name + content body-hash only.

    NOT bare-name-alone (it always carries a body disambiguator), but proven
    (T026) insufficient to keep re-export/facade fan-out fixtures distinct.
    """

    bare_name: str
    body_hash: str

    def as_key(self) -> tuple[str, str]:
        return (self.bare_name, self.body_hash)


@dataclass(frozen=True)
class ModuleQualifiedSymbolIdentity:
    """CANDIDATE B key components: bare name + module tiebreak + body-hash."""

    bare_name: str
    module_path: str
    body_hash: str

    def as_key(self) -> tuple[str, str, str]:
        return (self.bare_name, self.module_path, self.body_hash)


def definition_span(tree: ast.Module, bare_name: str) -> tuple[int, int] | None:
    """Return the ``(start_line, end_line)`` of the top-level statement that
    binds ``bare_name`` in this module, or ``None`` if not found.

    Handles the three definition shapes present in the real T026 fixtures:

    * ``class Name: ...`` / ``def Name(): ...`` (a real definition site).
    * ``import X as Name`` / ``from M import X as Name`` / bare
      ``from M import Name`` (an import-alias re-export site).
    * a plain module-level ``Name = ...`` assignment (an alias re-export).

    Deliberately does **not** resolve a lazy ``__getattr__`` facade-dict entry
    (e.g. ``specify_cli.runtime``'s ``_EXPORT_MODULES`` table) — the bound
    name there is a *dict key string*, not an AST-visible binding, and
    ``test_symbol_identity_spike.py`` treats that ``None`` result as a T026
    finding in its own right (a third structural shape the eventual gate
    would need to handle, not a bug in this span-finder).
    """
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == bare_name:
                return (node.lineno, node.end_lineno or node.lineno)
            continue
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bound = alias.asname or alias.name.split(".")[-1]
                if bound == bare_name:
                    return (node.lineno, node.end_lineno or node.lineno)
            continue
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == bare_name:
                    return (node.lineno, node.end_lineno or node.lineno)
    return None


def _hash_token_span(source: str, span: tuple[int, int]) -> str:
    """Body-hash normalization helper (T025 S3776 split).

    Isolated from :func:`body_hash_for_definition` so the token-normalization
    step is independently testable (T027's motion-battery / interpreter probe
    exercises this function directly). Reuses
    ``anchoring.code_tokens_by_line`` rather than forking a second
    tokenizer-based normalizer: blank lines and comment-only lines produce no
    bucket entry in ``code_tokens_by_line``'s output, so they are silently
    skipped by the ``if ln in tokens_by_line`` filter below — insertion of
    either is absorbed for free. Inter-token whitespace is never part of the
    hashed material either, because ``code_tokens_by_line`` re-joins each
    line's token *strings* with a single space, discarding the original
    original inter-token spacing.
    """
    start, end = span
    tokens_by_line = code_tokens_by_line(source)
    ordered_lines = [tokens_by_line[ln] for ln in range(start, end + 1) if ln in tokens_by_line]
    normalized = "\n".join(ordered_lines)
    # noqa: TID251 justification -- this is a body-checksum use case (T025),
    # not charter content: `charter.hasher.hash_content` is charter-markdown
    # specific (BOM/CRLF normalization, "sha256:" prefix format) and is the
    # wrong domain for a source-code token-span digest. TID251's own message
    # names "body checksums" as a sanctioned non-charter exception.
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()  # noqa: TID251


def body_hash_for_definition(source: str, bare_name: str) -> str | None:
    """Return the normalized body-hash for ``bare_name``'s definition site in
    ``source``, or ``None`` if no definition/re-export binding is found.

    Unparseable ``source`` fails closed (``UnparseableSourceError``, #5139).
    """
    tree = parse_source(source, display="<symbol-identity source>")
    span = definition_span(tree, bare_name)
    if span is None:
        return None
    return _hash_token_span(source, span)


def relocation_only_identity(source: str, bare_name: str) -> SymbolIdentity | None:
    """CANDIDATE A: ``(bare_name, body_hash)`` — no module component at all."""
    body_hash = body_hash_for_definition(source, bare_name)
    if body_hash is None:
        return None
    return SymbolIdentity(bare_name=bare_name, body_hash=body_hash)


def hybrid_identity(
    source: str, module_path: str, bare_name: str
) -> ModuleQualifiedSymbolIdentity | None:
    """CANDIDATE B: ``(bare_name, module_path, body_hash)`` — module tiebreak
    restores fan-out correctness at the cost of full relocation tolerance for
    the re-export/facade subset (see module docstring)."""
    body_hash = body_hash_for_definition(source, bare_name)
    if body_hash is None:
        return None
    return ModuleQualifiedSymbolIdentity(
        bare_name=bare_name, module_path=module_path, body_hash=body_hash
    )
