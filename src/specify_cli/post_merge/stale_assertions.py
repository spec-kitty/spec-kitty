"""Stale-assertion analyzer for post-merge reliability.

Compares two git refs (typically merge-base and HEAD) and emits a structured
report listing test assertions likely invalidated by merged source changes.

Uses stdlib ``ast`` on both source and test files — no regex on test text,
no libcst, no tree-sitter, no test-suite execution (FR-002).

Algorithm overview:
  1. ``git diff base_ref..head_ref -- '*.py'`` → list of changed source files
  2. For each changed file, parse both revisions with ``ast.parse`` and extract
     changed identifiers (function/class names) and changed string literals.
  3. For each test file from ``git ls-files 'tests/**/*.py'``, parse with ``ast``
     and find assertion-bearing nodes that reference changed identifiers.
  4. Assign confidence per FR-003 rules; never produce "definitely_stale".
  5. Populate ``StaleAssertionReport`` with findings + self-monitoring metrics.
"""

from __future__ import annotations

import ast
import re
import subprocess
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from specify_cli.ast_analysis.imports import (
    assignment_lists_dunder_all,
    import_binds_name,
)

# ---------------------------------------------------------------------------
# Public types (re-exported from __init__.py)
# ---------------------------------------------------------------------------

Confidence = Literal["high", "medium", "low", "info"]

# FR-003: never produce this value — it is listed here only to document what
# the analyzer MUST NOT emit.
_FORBIDDEN_CONFIDENCE = "definitely_stale"

FP_CEILING = 5.0  # NFR-002: max findings per 100 LOC of merged change


@dataclass(frozen=True)
class StaleAssertionFinding:
    """A single test assertion that may be invalidated by a source change."""

    test_file: Path       # absolute path to the test file
    test_line: int        # 1-indexed line of the suspect assertion
    source_file: Path     # absolute path to the source file that changed
    source_line: int      # 1-indexed line of the changed source identifier
    changed_symbol: str   # the identifier or literal that changed
    confidence: Confidence  # "high" | "medium" | "low"
    hint: str             # one-line human-readable explanation (no newlines)

    label: str = ""       # optional classifier label (e.g. "message-content-check")

    def __post_init__(self) -> None:
        assert self.confidence in ("high", "medium", "low", "info"), (
            f"confidence must be 'high', 'medium', 'low', or 'info', got {self.confidence!r}"
        )
        assert "\n" not in self.hint, "hint must be a single line"


@dataclass(frozen=True)
class StaleAssertionReport:
    """Aggregated results of a stale-assertion analysis run."""

    base_ref: str
    head_ref: str
    repo_root: Path
    findings: list[StaleAssertionFinding]
    elapsed_seconds: float    # for NFR-001 self-reporting
    files_scanned: int        # count of test files parsed successfully
    findings_per_100_loc: float  # for NFR-002 self-monitoring


# ---------------------------------------------------------------------------
# Internal helper types
# ---------------------------------------------------------------------------

@dataclass
class _SourceSymbol:
    """An identifier or literal that was removed/changed in the source diff."""

    name: str            # function/class name OR literal string value
    kind: Literal["identifier", "literal"]
    source_file: Path    # absolute path
    source_line: int     # 1-indexed line in base_ref version


# ---------------------------------------------------------------------------
# T002 — Source-side AST extraction
# ---------------------------------------------------------------------------

def _git_run(args: list[str], cwd: Path) -> str:
    """Run a git command and return stdout, raising on non-zero exit."""
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed (exit {result.returncode}):\n{result.stderr}"
        )
    return result.stdout


def _parse_safely(source_text: str, filename: str = "<unknown>") -> ast.AST | None:
    """Parse Python source with ast.parse; return None on SyntaxError."""
    try:
        return ast.parse(source_text, filename=filename)
    except SyntaxError as exc:
        warnings.warn(
            f"SyntaxError while parsing {filename}: {exc}",
            stacklevel=2,
        )
        return None


def _extract_identifiers(tree: ast.AST) -> set[tuple[str, int]]:
    """Return {(name, lineno)} for all function/class definitions in a tree."""
    names: set[tuple[str, int]] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add((node.name, node.lineno))
    return names


def _extract_string_literals(tree: ast.AST) -> set[tuple[str, int]]:
    """Return {(value, lineno)} for all string Constant nodes in a tree."""
    literals: set[tuple[str, int]] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            literals.add((node.value, node.lineno))
    return literals


# ---------------------------------------------------------------------------
# T001 (#2031) — head-importability suppression for relocated/re-exported
# identifiers.
#
# Keyed on HEAD-IMPORTABILITY of the ORIGIN file, not "the bare name appears
# somewhere else in the diff": the analyzer has no qualname primitive
# (`_extract_identifiers` captures bare `node.name`, and `ast.walk` flattens
# nested scopes), so matching on "same name in another changed file" would
# falsely suppress a genuine deletion of a common name (`run`/`main`/`setup`)
# whenever an unrelated same-name def exists elsewhere in the diff — blinding
# the analyzer (FR-001/SC-003). Head-importability only inspects the ALREADY
# PARSED head AST of the origin file itself (no other files, no repo scan —
# NFR-002), which is exactly where a relocate-and-re-export shim lives.
# ---------------------------------------------------------------------------


def _head_still_exports_name(head_tree: ast.AST | None, name: str) -> bool:
    """Return True when *name* is still importable from the origin file's HEAD.

    Reuses the already-parsed head AST of the SAME origin file — no other
    file is inspected and no additional parsing occurs (NFR-002). Scans
    MODULE-LEVEL statements only (``head_tree.body``, never ``ast.walk``):
    an import buried inside an unrelated function or class body is NOT a
    module-level re-export and must NOT suppress a genuine deletion
    (SC-003) — ``ast.walk`` would wrongly descend into those nested scopes
    and treat them as if they were exported from the module's own
    namespace. Recognises, at module level:
      - ``from <mod> import name`` (direct re-export)
      - ``from <mod> import name as _name`` / ``from <mod> import other as name``
        (aliased shims — FR-002)
      - ``import name`` / ``import <mod> as name``
      - ``name`` listed in a module-level ``__all__`` assignment
      - the equivalent forms when the origin file is a package ``__init__.py``

    A module-level bare ``import name`` (where ``name`` collides with an
    unrelated importable module of the same name) is INTENTIONALLY treated
    as suppressing — the analyzer only sees names, not qualnames, and
    resolving that collision would require inspecting the imported module's
    own contents (out of scope, NFR-002). This is a known, accepted
    precision/recall trade-off distinct from the nested-scope bug above.

    A relocate-**and**-rename (the origin file's head no longer imports the
    OLD name under any form above) correctly returns False — it is a real
    change, not a suppression (FR-002 edge case).
    """
    if head_tree is None:
        return False

    for node in getattr(head_tree, "body", []):
        if isinstance(node, (ast.Import, ast.ImportFrom)) and import_binds_name(node, name):
            return True
        if isinstance(node, ast.Assign) and assignment_lists_dunder_all(node, name):
            return True
    return False


# ---------------------------------------------------------------------------
# T002 (#2343) — generic-literal suppression, keyed on GENUINENESS not length.
#
# A genuinely short literal (an error code like "E001") can be assert-
# critical, and since every literal finding is by construction a literal
# appearing inside an assertion, length alone cannot separate noise from
# signal (FR-004). The pinned token set below is the explicit rule.
# ---------------------------------------------------------------------------

# Common short English words / status tokens and format fragments that show
# up as leftover literal pieces after a reformat or refactor and are, on
# their own, never assert-critical signal. Pinned explicitly (not "e.g.") —
# FR-004.
_GENERIC_LITERAL_TOKENS: frozenset[str] = frozenset({
    "ok", "true", "false", "none", "null", "yes", "no",
    "error", "warning", "warn", "info", "debug", "trace",
    "test", "tests", "value", "values", "name", "names",
    "type", "types", "data", "result", "results", "status",
    "success", "failure", "fail", "failed", "pass", "passed",
    "id", "key", "keys", "path", "paths", "file", "files",
    "message", "msg", "text", "label", "title", "description",
    "default", "unknown", "empty", "count", "total", "start", "end",
    "{}", "{0}", "{1}", "%s", "%d", "%r", "\n", "\t",
})


def _is_generic_literal(value: str) -> bool:
    """Return True iff *value* is generic noise, not assert-critical signal.

    True when *value*:
      - is empty, or
      - consists solely of punctuation/whitespace (no alphanumeric chars), or
      - matches (case-insensitively, after stripping surrounding whitespace)
        a member of the pinned generic-token set above.

    Deliberately NOT length-based — see module-level rationale (FR-004).
    """
    if value == "":
        return True
    if all(not char.isalnum() for char in value):
        return True
    return value.strip().lower() in _GENERIC_LITERAL_TOKENS


# ---------------------------------------------------------------------------
# #3957 — structural noise-literal gate, closing the #2343 residual.
#
# The #2343 stop-list suppressed pinned generic tokens but was deliberately
# not length-gated, which left two residual noise classes that buried real
# signal in the merge output:
#   - F-60: one-character literals — ``open()`` file-mode strings like
#     ``"a"``/``"r"`` that a diff removes whenever raw ``open(...)`` calls go
#     away. A one-character literal is never assert-critical signal.
#   - F-79: single bare lowercase words like ``"items"``/``"url"``/
#     ``"payload"`` that a large schema-module deletion removes en masse. A
#     removed literal is only emitted when it is symbol-shaped (contains an
#     underscore, an uppercase letter, or a digit — ``"E001"``,
#     ``"old_key"``) or carries ≥ 2 tokens (``"bad request"``).
#
# This EXTENDS the #2343 genuineness rule; it does not replace it. The
# stop-list stays as-is, and genuinely short but symbol-shaped literals
# (error codes) remain signal (FR-004).
# ---------------------------------------------------------------------------

# ``open()`` file-mode strings: any short combination of mode characters
# (including ``+``), e.g. "a", "rb", "w+", "ab+".
_FILE_MODE_LITERAL_PATTERN = re.compile(r"[arwbt+]{1,4}")

# A single bare lowercase word with no symbol shape: "items", "url", ...
_SINGLE_LOWERCASE_WORD_PATTERN = re.compile(r"[a-z]+")


def _is_noise_literal(value: str) -> bool:
    """Return True iff *value* is structural noise, never assert-critical signal.

    True when *value*:
      - is generic per the #2343 stop-list (``_is_generic_literal``), or
      - is shorter than two characters (F-60 one-char literals), or
      - is an ``open()`` file-mode string ("a", "rb", "w+", ...), or
      - is a single bare lowercase word with no symbol shape (F-79).

    Symbol-shaped single tokens survive ("E001", "old_key", "BadRequest"),
    as do multi-token literals ("bad request").
    """
    if _is_generic_literal(value):
        return True
    if len(value) < 2:
        return True
    if _FILE_MODE_LITERAL_PATTERN.fullmatch(value):
        return True
    return bool(_SINGLE_LOWERCASE_WORD_PATTERN.fullmatch(value))


def _extract_changed_symbols(
    base_ref: str,
    head_ref: str,
    repo_root: Path,
) -> list[_SourceSymbol]:
    """Compare base_ref..head_ref and return identifiers/literals that were removed.

    "Removed" means present in base_ref but absent in head_ref for a given file.
    These are the symbols that assertions might reference and that may now be stale.
    """
    # Get list of changed Python source files, excluding tests/ directory.
    diff_output = _git_run(
        ["diff", "--name-only", base_ref, head_ref, "--", "*.py"],
        cwd=repo_root,
    )
    changed_files = [
        line.strip()
        for line in diff_output.splitlines()
        if line.strip() and not line.strip().startswith("tests/")
    ]

    symbols: list[_SourceSymbol] = []

    for rel_path in changed_files:
        abs_path = repo_root / rel_path

        # Get file content at both refs; silently skip if not available.
        try:
            base_content = _git_run(["show", f"{base_ref}:{rel_path}"], cwd=repo_root)
        except RuntimeError:
            base_content = ""

        try:
            head_content = _git_run(["show", f"{head_ref}:{rel_path}"], cwd=repo_root)
        except RuntimeError:
            head_content = ""

        base_tree = _parse_safely(base_content, rel_path) if base_content else None
        head_tree = _parse_safely(head_content, rel_path) if head_content else None

        if base_tree is None:
            continue

        # Identifiers present in base but absent in head → renamed/removed.
        base_ids = _extract_identifiers(base_tree)
        head_ids = _extract_identifiers(head_tree) if head_tree else set()
        base_id_names = {name for name, _ in base_ids}
        head_id_names = {name for name, _ in head_ids}
        removed_ids = base_id_names - head_id_names

        for name, lineno in base_ids:
            # FR-001/FR-002: an identifier that vanished from this file's
            # definitions is only a genuine removal if the origin file's own
            # HEAD no longer imports/re-exports it either. Relocated (and
            # re-exported back) symbols are suppressed, not emitted.
            if name in removed_ids and not _head_still_exports_name(head_tree, name):
                symbols.append(
                    _SourceSymbol(
                        name=name,
                        kind="identifier",
                        source_file=abs_path,
                        source_line=lineno,
                    )
                )

        # String literals present in base but absent in head.
        base_lits = _extract_string_literals(base_tree)
        head_lits = _extract_string_literals(head_tree) if head_tree else set()
        base_lit_vals = {val for val, _ in base_lits}
        head_lit_vals = {val for val, _ in head_lits}
        removed_lits = base_lit_vals - head_lit_vals

        for val, lineno in base_lits:
            # FR-004 + #3957: generic/noise literals are suppressed, not
            # emitted — the #2343 stop-list plus the one-char/file-mode/
            # single-lowercase-word rules that closed its residual.
            if val in removed_lits and not _is_noise_literal(val):
                symbols.append(
                    _SourceSymbol(
                        name=val,
                        kind="literal",
                        source_file=abs_path,
                        source_line=lineno,
                    )
                )

    return symbols


# ---------------------------------------------------------------------------
# T003 — Test-side AST scan
# ---------------------------------------------------------------------------

_UNITTEST_ASSERT_PREFIXES = frozenset({
    "assertEqual",
    "assertNotEqual",
    "assertTrue",
    "assertFalse",
    "assertIs",
    "assertIsNot",
    "assertIsNone",
    "assertIsNotNone",
    "assertIn",
    "assertNotIn",
    "assertRaises",
    "assertRaisesRegex",
    "assertWarns",
    "assertWarnsRegex",
    "assertGreater",
    "assertGreaterEqual",
    "assertLess",
    "assertLessEqual",
    "assertRegex",
    "assertNotRegex",
    "assertCountEqual",
    "assertMultiLineEqual",
    "assertSequenceEqual",
    "assertListEqual",
    "assertTupleEqual",
    "assertSetEqual",
    "assertDictEqual",
})


def _node_is_assertion_bearing(node: ast.expr | ast.stmt | ast.AST) -> bool:
    """Return True if the node is an assertion-bearing position.

    An assertion-bearing position is:
    - An ``Assert`` statement
    - A ``Call`` whose func is ``Attribute(attr='assert*')``
    """
    if isinstance(node, ast.Assert):
        return True
    if isinstance(node, ast.Call):
        func = node.func
        if isinstance(func, ast.Attribute) and (
            func.attr in _UNITTEST_ASSERT_PREFIXES or func.attr.startswith("assert")
        ):
            return True
    return False


def _collect_assertion_nodes(tree: ast.AST) -> list[ast.AST]:
    """Return all AST nodes that are in assertion-bearing positions."""
    result: list[ast.AST] = []
    for node in ast.walk(tree):
        if _node_is_assertion_bearing(node):
            result.append(node)
    return result


def _names_in_subtree(node: ast.AST) -> set[str]:
    """Return all Name.id and Attribute.attr values in a subtree."""
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Name):
            names.add(child.id)
        elif isinstance(child, ast.Attribute):
            names.add(child.attr)
    return names


def _constants_in_subtree(node: ast.AST) -> set[str]:
    """Return all string Constant values in a subtree."""
    values: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Constant) and isinstance(child.value, str):
            values.add(child.value)
    return values


def _assertion_negatively_checks_literal_absence(assertion: ast.AST, literal: str) -> bool:
    """Return True for assertions that intentionally require a removed literal to be absent."""
    if isinstance(assertion, ast.Assert):
        return _assert_test_checks_literal_absence(assertion.test, literal)

    if isinstance(assertion, ast.Call):
        return _assert_call_checks_literal_absence(assertion, literal)

    return False


def _assert_test_checks_literal_absence(test: ast.AST, literal: str) -> bool:
    """Return True when an ``assert`` test checks that *literal* is absent."""
    for node in ast.walk(test):
        if not isinstance(node, ast.Compare):
            continue
        if _compare_checks_literal_absence(node, literal):
            return True
    return False


def _compare_checks_literal_absence(node: ast.Compare, literal: str) -> bool:
    """Return True when a comparison uses ``not in`` with *literal*."""
    for op, comparator in zip(node.ops, node.comparators, strict=False):
        if not isinstance(op, ast.NotIn):
            continue
        if _node_contains_literal(node.left, literal) or _node_contains_literal(
            comparator, literal
        ):
            return True
    return False


def _assert_call_checks_literal_absence(assertion: ast.Call, literal: str) -> bool:
    """Return True when an ``assertNotIn`` call checks that *literal* is absent."""
    func = assertion.func
    if not isinstance(func, ast.Attribute) or func.attr != "assertNotIn":
        return False
    return any(_node_contains_literal(arg, literal) for arg in assertion.args)


def _node_contains_literal(node: ast.AST, literal: str) -> bool:
    """Return True when *node* contains the exact string literal."""
    return any(
        isinstance(child, ast.Constant) and child.value == literal
        for child in ast.walk(node)
    )


def _is_message_capture_expr(node: ast.expr) -> bool:
    """Return True if *node* is a message-capture expression.

    A message-capture expression is one whose value is the text of an
    exception message, output stream, or similar diagnostic channel.
    When a removed literal appears as the *right-hand* operand of an ``in``
    comparison whose *left-hand* operand is a message-capture expression,
    the assertion is checking diagnostic text — not a stale constant — so
    the finding should be downgraded to ``info`` grade.

    Recognised patterns:
    - ``str(<expr>)`` / ``repr(<expr>)``
    - ``<expr>.message`` / ``.stderr`` / ``.stdout`` / ``.output`` / ``.value``
    - ``capsys.readouterr().out`` / ``capsys.readouterr().err``
    """
    # str(...) or repr(...)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("str", "repr"):
        return True

    # <expr>.message / .stderr / .stdout / .output / .value
    if isinstance(node, ast.Attribute) and node.attr in ("message", "stderr", "stdout", "output", "value"):
        return True

    # capsys.readouterr().out or capsys.readouterr().err
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Call):
        call = node.value
        if isinstance(call.func, ast.Attribute) and call.func.attr == "readouterr":
            return True

    return False


def _ordered_removal_sites(syms: list[_SourceSymbol]) -> list[_SourceSymbol]:
    """Return removal sites sorted by (file name, line) for deterministic output.

    ``_extract_changed_symbols`` iterates a ``set`` of ``(value, lineno)``
    pairs, so the incoming order is nondeterministic across processes; the
    collapsed hint must name sites in a stable order.
    """
    return sorted(syms, key=lambda sym: (sym.source_file.name, sym.source_line))


# Primary site plus at most three named extras in a collapsed hint; further
# sites are summarised as a count so the hint stays on one line (#3957).
_MAX_NAMED_REMOVAL_SITES = 4


def _collapsed_literal_hint(lit_val: str, sites: list[_SourceSymbol]) -> str:
    """Build the one-line hint for a removed literal, naming every removal site.

    #3957: the same literal removed from N source sites previously produced N
    findings per test line — a wall of repeats that buried real signal (F-79).
    One collapsed finding now names the primary site plus the extras.
    """
    primary, extras = sites[0], sites[1:]
    hint = (
        f"Assertion contains string literal {lit_val!r} which was "
        f"removed from {primary.source_file.name}:{primary.source_line}"
    )
    if not extras:
        return hint
    named = extras[: _MAX_NAMED_REMOVAL_SITES - 1]
    hidden = len(extras) - len(named)
    site_text = ", ".join(f"{sym.source_file.name}:{sym.source_line}" for sym in named)
    if hidden > 0:
        site_text += f", +{hidden} more"
    return f"{hint} (+{len(extras)} more removal site(s): {site_text})"


def _literal_findings_for_assertion(
    assertion: ast.AST,
    line: int,
    changed_literals: dict[str, list[_SourceSymbol]],
    test_path: Path,
) -> list[StaleAssertionFinding]:
    """Return findings for changed literals in one assertion.

    Most findings are emitted at ``low`` confidence.  When the removed literal
    is the right-hand operand of an ``in``/``not in`` comparison whose
    left-hand operand is a message-capture expression (FR-009), the finding is
    downgraded to ``info`` grade with label ``message-content-check`` so it
    does not trigger CI noise while still being auditable.

    #3957: one finding per (assertion, literal) — every removal site is named
    in the collapsed hint instead of emitting one repeat finding per site.
    """
    findings: list[StaleAssertionFinding] = []
    constants_in_assertion = _constants_in_subtree(assertion)
    for lit_val, syms in changed_literals.items():
        if _assertion_negatively_checks_literal_absence(assertion, lit_val):
            continue
        if lit_val not in constants_in_assertion:
            continue

        # Determine whether this is a message-content check (FR-009).
        grade: Confidence = "low"
        label = ""
        if _assertion_checks_literal_in_message_expr(assertion, lit_val):
            grade = "info"
            label = "message-content-check"

        sites = _ordered_removal_sites(syms)
        findings.append(
            StaleAssertionFinding(
                test_file=test_path,
                test_line=line,
                source_file=sites[0].source_file,
                source_line=sites[0].source_line,
                changed_symbol=lit_val,
                confidence=grade,
                hint=_collapsed_literal_hint(lit_val, sites),
                label=label,
            )
        )
    return findings


def _assertion_checks_literal_in_message_expr(
    assertion: ast.AST, literal: str
) -> bool:
    """Return True when the assertion checks *literal* membership in a message-capture expression.

    Handles both orientations of the ``in`` operator:

    - ``assert "literal" in str(exc)``   → left=literal, comparator=message-capture
    - ``assert "literal" in result.stderr`` → same pattern

    Walks all ``ast.Compare`` nodes inside *assertion* and checks whether any
    ``in``/``not in`` comparison involves *literal* on one side and a
    message-capture expression on the other.
    """
    for node in ast.walk(assertion):
        if not isinstance(node, ast.Compare):
            continue
        for op, comparator in zip(node.ops, node.comparators, strict=False):
            if not isinstance(op, (ast.In, ast.NotIn)):
                continue
            # Pattern: "literal" in <message-capture>
            # AST: left="literal", comparator=message-capture
            if _node_contains_literal(node.left, literal) and _is_message_capture_expr(comparator):
                return True
            # Pattern: <message-capture> in "literal"  (unusual but possible)
            # AST: left=message-capture, comparator="literal"
            if _node_contains_literal(comparator, literal) and _is_message_capture_expr(node.left):
                return True
    return False


def _get_node_line(node: ast.AST) -> int:
    """Return the line number of an AST node, defaulting to 0 if unavailable."""
    return getattr(node, "lineno", 0)


def _is_directly_inside_assert(
    node: ast.AST, assertion: ast.AST
) -> bool:
    """Return True if node appears as a direct child of an Assert.test or assertEqual call.

    Used to distinguish high vs. medium confidence.
    """
    if isinstance(assertion, ast.Assert):
        test = assertion.test
        # Direct Name or Attribute in the test expression.
        if isinstance(test, ast.Name) and isinstance(node, ast.Name):
            return test.id == node.id
        if isinstance(test, ast.Attribute) and isinstance(node, ast.Attribute):
            return test.attr == node.attr
        # Walk one level: Compare, BoolOp, etc.
        for direct_child in ast.iter_child_nodes(test):
            if isinstance(direct_child, ast.Name) and isinstance(node, ast.Name) and direct_child.id == node.id:
                return True
            if isinstance(direct_child, ast.Attribute) and isinstance(node, ast.Attribute) and direct_child.attr == node.attr:
                return True
    return False


def _scan_test_file(
    test_path: Path,
    changed_symbols: list[_SourceSymbol],
) -> list[StaleAssertionFinding]:
    """Parse a single test file and return findings for changed symbols.

    Uses ast.parse only — never reads the file as raw text or executes it.
    """
    findings: list[StaleAssertionFinding] = []

    try:
        source = test_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return findings

    tree = _parse_safely(source, str(test_path))
    if tree is None:
        return findings

    assertion_nodes = _collect_assertion_nodes(tree)

    # Build lookup sets for efficiency.
    # changed_identifiers: last-wins is acceptable because identifiers are
    # deduplicated by name (a renamed function has a single canonical removal).
    changed_identifiers = {
        sym.name: sym for sym in changed_symbols if sym.kind == "identifier"
    }
    # changed_literals: collect ALL removal sites so multi-file removals are
    # fully reported (fixes last-wins dict bug — T022).
    changed_literals: dict[str, list[_SourceSymbol]] = {}
    for sym in changed_symbols:
        if sym.kind == "literal":
            changed_literals.setdefault(sym.name, []).append(sym)

    for assertion in assertion_nodes:
        line = _get_node_line(assertion)

        # --- Identifier matches ---
        names_in_assertion = _names_in_subtree(assertion)
        for sym_name, sym in changed_identifiers.items():
            if sym_name in names_in_assertion:
                # Determine confidence: high if directly inside Assert/assert*,
                # medium otherwise.
                confidence: Confidence = "medium"
                if isinstance(assertion, ast.Assert):
                    # Check whether the identifier appears directly in test.test
                    test_node = assertion.test
                    direct_names = _names_in_subtree(test_node)
                    if sym_name in direct_names:
                        # Treat as "directly inside assert" → high
                        confidence = "high"
                elif isinstance(assertion, ast.Call):
                    # Direct arg reference → high
                    for arg in assertion.args:
                        if sym_name in _names_in_subtree(arg):
                            confidence = "high"
                            break
                    else:
                        for kw in assertion.keywords:
                            if sym_name in _names_in_subtree(kw.value):
                                confidence = "high"
                                break

                findings.append(
                    StaleAssertionFinding(
                        test_file=test_path,
                        test_line=line,
                        source_file=sym.source_file,
                        source_line=sym.source_line,
                        changed_symbol=sym_name,
                        confidence=confidence,
                        hint=(
                            f"Assertion references '{sym_name}' which was renamed/removed "
                            f"in {sym.source_file.name}:{sym.source_line}"
                        ),
                    )
                )

        # --- Literal matches ---
        findings.extend(
            _literal_findings_for_assertion(
                assertion, line, changed_literals, test_path
            )
        )

    return findings


# ---------------------------------------------------------------------------
# T004 — run_check() orchestration
# ---------------------------------------------------------------------------

def _count_diff_loc(base_ref: str, head_ref: str, repo_root: Path) -> int:
    """Return the number of lines added+removed in the diff (for NFR-002)."""
    try:
        output = _git_run(
            ["diff", "--shortstat", base_ref, head_ref, "--", "*.py"],
            cwd=repo_root,
        )
        # Example: " 3 files changed, 42 insertions(+), 7 deletions(-)"
        insertions = 0
        deletions = 0
        for token in output.split(","):
            token = token.strip()
            if "insertion" in token:
                insertions = int(token.split()[0])
            elif "deletion" in token:
                deletions = int(token.split()[0])
        return insertions + deletions
    except (RuntimeError, ValueError):
        return 0


def run_check(
    base_ref: str,
    head_ref: str,
    repo_root: Path,
) -> StaleAssertionReport:
    """Compare base_ref..head_ref and return likely-stale test assertions.

    Algorithm:
      1. git diff base_ref..head_ref -- '*.py' → list of changed source files
      2. For each changed file, parse both revisions with ast and extract
         changed identifiers (function/class names) and changed string literals.
      3. For each test file from ``git ls-files 'tests/**/*.py'``, parse with ast
         and walk for assertion-bearing nodes referencing changed identifiers.
      4. Assign confidence per FR-003 rules (never "definitely_stale").
      5. Compute findings_per_100_loc against the changed-line count.

    Args:
        base_ref: Git ref for the base (e.g., merge-base SHA or "HEAD~1").
        head_ref: Git ref for the head (e.g., "HEAD").
        repo_root: Absolute path to the repository root.

    Returns:
        StaleAssertionReport with findings list, elapsed_seconds,
        files_scanned, and findings_per_100_loc populated.
    """
    start_time = time.monotonic()

    # Step 1+2: extract changed symbols from source side.
    changed_symbols = _extract_changed_symbols(base_ref, head_ref, repo_root)

    # Step 3: enumerate test files.
    try:
        ls_output = _git_run(
            ["ls-files", "tests/"],
            cwd=repo_root,
        )
        test_files = [
            repo_root / line.strip()
            for line in ls_output.splitlines()
            if line.strip().endswith(".py")
        ]
    except RuntimeError:
        test_files = []

    # Step 4: scan each test file.
    all_findings: list[StaleAssertionFinding] = []
    files_scanned = 0

    if changed_symbols:
        for tf in test_files:
            file_findings = _scan_test_file(tf, changed_symbols)
            all_findings.extend(file_findings)
            files_scanned += 1
    else:
        # No changed symbols → nothing to scan; still count files.
        files_scanned = len(test_files)

    # Step 5: compute metrics.
    elapsed_seconds = time.monotonic() - start_time
    loc_changed = _count_diff_loc(base_ref, head_ref, repo_root)
    findings_per_100_loc: float = (
        (len(all_findings) / loc_changed * 100.0) if loc_changed > 0 else 0.0
    )

    # FR-022: self-monitoring warning if FP ceiling exceeded.
    if findings_per_100_loc > FP_CEILING:
        warnings.warn(
            f"stale-assertion analyzer: findings_per_100_loc={findings_per_100_loc:.1f} "
            f"exceeds NFR-002 ceiling of {FP_CEILING}. "
            "Consider narrowing scope to function-rename detection only (FR-022).",
            UserWarning,
            stacklevel=2,
        )

    return StaleAssertionReport(
        base_ref=base_ref,
        head_ref=head_ref,
        repo_root=repo_root,
        findings=all_findings,
        elapsed_seconds=elapsed_seconds,
        files_scanned=files_scanned,
        findings_per_100_loc=findings_per_100_loc,
    )
