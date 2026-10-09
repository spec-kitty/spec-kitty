"""Issue-matrix partition regression guard (FR-008 / NFR-001 / SC-005, WP05).

Mission ``issue-matrix-partition-integrity-01M3H10A`` (#5171, #4943) closed a
two-partition conflation: gating-reference discovery must read the PRIMARY
partition, while authored matrix verdicts must read the coordination partition
(or its retained branch-ref content post-consolidation). Both halves are
resolved by ONE shared helper,
:func:`mission_runtime.issue_matrix_partition.resolve_issue_matrix_partition`.

This gate keeps the class shut in every guarded consumer:

* the mission-review gate (``review/__init__.py``),
* the merge completeness + terminal-verdict gates (``policy/merge_gates.py``),
* the Gate-4 doctrine (``spec-kitty-mission-review/SKILL.md``).

Rules (count of violations must be 0 — NFR-001):

* **Python, raw path** — no ``<dir> / "issue-matrix.{json,md}"`` (or
  ``.joinpath``) unless ``<dir>`` is a matrix source already resolved by the
  helper; no string literal hand-reconstructing ``kitty-specs/.../issue-matrix``.
* **Python, discovery dir fed to the matrix read** — the issue-matrix readers
  are never handed ``feature_dir`` (the primary discovery dir).
* **Python, split bypass** — every guarded gate function calls the helper.
* **Python, helper unpack** — every helper call is unpacked positionally as
  ``<discovery_dir>, <matrix_source> = ...``; a swapped or indexed result trips.
* **Python, taint** — values derived from the discovery dir (a discovery
  name, ``<obj>.feature_dir``, or a hand-built ``"kitty-specs"`` path) never
  reach a matrix sink or a matrix-location local, except the two sites pinned
  in ``ALLOWED_TAINTS``. Known, accepted limitation: loop targets
  (``for matrix_dir in ...``) are not tracked.
* **Doctrine** — no executable raw read (``cat``/``jq``/``head``/... of an
  ``issue-matrix`` file) in a fenced block, and an inline raw-read span only
  inside an explicit prohibition ("Do NOT ...").

Non-vacuity: every rule is re-run against a mutated copy of the real source
(:class:`TestSelfMutation`) and must trip. Fail-closed: a missing or
unreadable guarded file, or a guarded function that no longer exists, FAILs.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[2]

HELPER_NAME = "resolve_issue_matrix_partition"

REVIEW_GATE = "src/specify_cli/cli/commands/review/__init__.py"
MERGE_GATES = "src/specify_cli/policy/merge_gates.py"
GATE4_SKILL = "src/charter/offering/skills/spec-kitty-mission-review/SKILL.md"

# Guarded gate functions that must resolve the partition through the helper.
HELPER_CALLERS: dict[str, tuple[str, ...]] = {
    REVIEW_GATE: ("review_mission",),
    MERGE_GATES: (
        "_evaluate_issue_matrix_completeness_gate",
        "_evaluate_issue_matrix_verdict_terminality_gate",
    ),
}

# Local names that may hold a helper-resolved matrix source. A name here is
# only trusted while it is not tainted by the primary discovery dir (below).
RESOLVED_MATRIX_NAMES = frozenset({"resolved_matrix_dir", "matrix_dir", "coord_matrix_source"})

# Names that hold the PRIMARY discovery dir. Any value derived from one of them
# is "tainted": it must never reach a matrix-location argument.
DISCOVERY_DIR_NAMES = frozenset({"feature_dir", "primary_discovery_dir", "_primary_discovery_dir"})

# Matrix sinks: callable name -> (positional index, keyword) of the argument
# that selects WHERE the matrix is read from. Covers the canonical readers and
# the gate-local wrappers the fixed consumers reach them through.
MATRIX_SINKS: dict[str, tuple[int | None, str | None]] = {
    "load_issue_matrix": (0, "feature_dir"),
    "issue_matrix_artifact_present": (0, "feature_dir"),
    "validate_issue_matrix": (0, "path"),
    "_load_issue_matrix_rows": (0, "coord_matrix_source"),
    "_issue_matrix_approval_blocker": (0, "feature_dir"),
    "_evaluate_issue_matrix": (None, "matrix_dir"),
}


@dataclass(frozen=True)
class AllowedTaint:
    """A pinned, documented assignment of a discovery-dir value to a local.

    ``guard`` is the unparsed test of the enclosing ``if`` whose body must
    contain the assignment (``None`` when the value expression carries its own
    guard). The allow-list cannot widen silently: an entry must match exactly,
    and an entry that no longer matches any site FAILs (stale pin).
    """

    path: str
    function: str
    target: str
    value: str
    guard: str | None


ALLOWED_TAINTS: tuple[AllowedTaint, ...] = (
    # Legacy parity: no split was resolved (lightweight mode), so the primary
    # dir IS the only matrix location. Guarded inline by ``matrix_dir is not None``.
    AllowedTaint(REVIEW_GATE, "_evaluate_issue_matrix", "resolved_matrix_dir", "matrix_dir if matrix_dir is not None else feature_dir", None),
    # Post-consolidation ref-content arm: the dir is only an error-message
    # prefix; ``matrix_content`` drives the evaluation.
    AllowedTaint(
        MERGE_GATES,
        "_evaluate_issue_matrix_verdict_terminality_gate",
        "feature_dir_for_blocker",
        "primary_discovery_dir",
        "isinstance(coord_matrix_source, str)",
    ),
)

_MATRIX_FILE_RE = re.compile(r"issue-matrix\.(?:json|md)")
_HAND_BUILT_PATH_RE = re.compile(r"kitty-specs/[^\s\"'`]*issue-matrix")
_RAW_READ_RE = re.compile(r"\b(?:cat|less|more|head|tail|jq|bat|yq|sed|awk|grep|open)\b[^`\n]*issue-matrix\.(?:json|md)")
# The prohibition must govern the command directly: "Do NOT `cat ...`",
# "never run `cat ...`" -- not "Don't forget to `cat ...`".
_PROHIBITION_CLAUSE_RE = re.compile(r"^\s*(?:do not|don't|never)\s+(?:run\s+|use\s+|call\s+)?$", re.IGNORECASE)
# A path segment that hand-rebuilds a mission dir instead of asking the helper.
_MISSION_ROOT_SEGMENT = "kitty-specs"
_FENCE_RE = re.compile(r"^```[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")


@dataclass(frozen=True)
class Violation:
    path: str
    line: int
    rule: str
    detail: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: [{self.rule}] {self.detail}"


def _read_guarded(rel: str) -> str:
    """Read a guarded file; FAIL (never skip) if it is gone or unreadable."""
    path = REPO_ROOT / rel
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        pytest.fail(f"guarded issue-matrix consumer {rel} is missing/unreadable ({exc}); update this guard, do not skip it")


def _is_matrix_filename(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, str) and bool(_MATRIX_FILE_RE.fullmatch(node.value))


def _base_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ast.unparse(node)


def _call_name(node: ast.Call) -> str:
    return _base_name(node.func)


# Locals that carry a matrix LOCATION into a sink; a tainted value landing in
# one of these is the #4943/#5171 partition swap even before any sink runs.
_MATRIX_LOCATION_TARGETS = RESOLVED_MATRIX_NAMES | {"feature_dir_for_blocker", "matrix_content"}


@dataclass(frozen=True)
class _Assignment:
    node: ast.stmt
    target: str
    value: ast.expr | None
    guards: tuple[str, ...]


def _pair_targets(stmt: ast.stmt, target: ast.expr, value: ast.expr, guards: tuple[str, ...]) -> list[_Assignment]:
    """Name targets paired with their value; ``a, b = x, y`` pairs elementwise.

    Any other tuple unpack (``a, b = f()``) gives every name the whole value,
    so taint spreads conservatively. The helper's own unpack is policed
    positionally by :func:`_helper_unpack_violations`.
    """
    if isinstance(target, ast.Name):
        return [_Assignment(stmt, target.id, value, guards)]
    if not isinstance(target, (ast.Tuple, ast.List)):
        return []
    if isinstance(value, (ast.Tuple, ast.List)) and len(value.elts) == len(target.elts):
        return [a for t, v in zip(target.elts, value.elts, strict=True) for a in _pair_targets(stmt, t, v, guards)]
    return [a for t in target.elts for a in _pair_targets(stmt, t, value, guards)]


def _collect_assignments(stmts: list[ast.stmt], guards: tuple[str, ...] = ()) -> list[_Assignment]:
    """Single-Name assignments in a function body, with their enclosing ``if`` guards."""
    found: list[_Assignment] = []
    for stmt in stmts:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue  # scanned as its own scope
        if isinstance(stmt, ast.If):
            test = ast.unparse(stmt.test)
            found += _collect_assignments(stmt.body, (*guards, test))
            found += _collect_assignments(stmt.orelse, (*guards, f"not ({test})"))
            continue
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1:
            found += _pair_targets(stmt, stmt.targets[0], stmt.value, guards)
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None and isinstance(stmt.target, ast.Name):
            found.append(_Assignment(stmt, stmt.target.id, stmt.value, guards))
        for field in ("body", "orelse", "finalbody"):
            found += _collect_assignments(getattr(stmt, field, None) or [], guards)
        for handler in getattr(stmt, "handlers", None) or []:
            found += _collect_assignments(handler.body, guards)
    return found


def _is_tainting(node: ast.AST, names: set[str]) -> bool:
    """A single node that carries the primary partition into an expression."""
    if isinstance(node, ast.Name):
        return node.id in names
    if isinstance(node, ast.Attribute):  # ``resolved.feature_dir``
        return node.attr in DISCOVERY_DIR_NAMES
    if isinstance(node, ast.Constant) and isinstance(node.value, str):  # ``repo_root / "kitty-specs" / slug``
        return node.value == _MISSION_ROOT_SEGMENT or node.value.startswith(f"{_MISSION_ROOT_SEGMENT}/")
    return False


def _mentions(node: ast.AST | None, names: set[str]) -> bool:
    return node is not None and any(_is_tainting(n, names) for n in ast.walk(node))


def _value_src(assignment: _Assignment) -> str:
    return ast.unparse(assignment.value) if assignment.value is not None else ""


def _allowed_taint(rel: str, function: str, assignment: _Assignment) -> AllowedTaint | None:
    value = _value_src(assignment)
    for entry in ALLOWED_TAINTS:
        if (entry.path, entry.function, entry.target, entry.value) != (rel, function, assignment.target, value):
            continue
        if entry.guard is None or entry.guard in assignment.guards:
            return entry
    return None


def _scopes(tree: ast.Module) -> list[tuple[str, list[ast.stmt]]]:
    """Module body plus every function (top-level, method or nested) as its own scope."""
    scopes: list[tuple[str, list[ast.stmt]]] = [("<module>", tree.body)]
    scopes += [(n.name, n.body) for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return scopes


def _scope_nodes(stmts: list[ast.stmt]) -> list[ast.AST]:
    """Every node of a scope, excluding nested function/class bodies."""
    nodes: list[ast.AST] = []
    stack: list[ast.AST] = list(stmts)
    while stack:
        node = stack.pop()
        nodes.append(node)
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            stack.extend(ast.iter_child_nodes(node))
    return nodes


def _taint(rel: str, function: str, assignments: list[_Assignment], used: set[AllowedTaint]) -> set[str]:
    """Names in a scope whose value derives from the primary discovery dir (fixpoint)."""
    tainted = set(DISCOVERY_DIR_NAMES)
    changed = True
    while changed:
        changed = False
        for assignment in assignments:
            if assignment.target in tainted or not _mentions(assignment.value, tainted):
                continue
            entry = _allowed_taint(rel, function, assignment)
            if entry is not None:
                used.add(entry)
                continue
            tainted.add(assignment.target)
            changed = True
    return tainted


def _sink_arg(call: ast.Call) -> ast.AST | None:
    position, keyword = MATRIX_SINKS[_call_name(call)]
    if position is not None and len(call.args) > position:
        return call.args[position]
    return next((kw.value for kw in call.keywords if kw.arg == keyword), None)


def _path_join_base(node: ast.AST) -> ast.AST | None:
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div) and _is_matrix_filename(node.right):
        return node.left
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "joinpath" and any(_is_matrix_filename(a) for a in node.args):
        return node.func.value
    return None


def _scope_violations(rel: str, function: str, stmts: list[ast.stmt], used: set[AllowedTaint]) -> list[Violation]:
    assignments = _collect_assignments(stmts)
    tainted = _taint(rel, function, assignments, used)
    found = [
        Violation(rel, a.node.lineno, "partition-swap", f"{function}(): {a.target} = {_value_src(a)} puts the primary discovery dir in a matrix-location name")
        for a in assignments
        if a.target in _MATRIX_LOCATION_TARGETS and a.target in tainted and _mentions(a.value, tainted)
    ]
    docstrings = _docstring_ids(stmts)
    for node in _scope_nodes(stmts):
        base = _path_join_base(node)
        if isinstance(node, (ast.BinOp, ast.Call)) and base is not None and (_base_name(base) not in RESOLVED_MATRIX_NAMES or _mentions(base, tainted)):
            found.append(Violation(rel, node.lineno, "raw-path", f"{ast.unparse(node)} joins the matrix file onto a non-resolved dir"))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings and _HAND_BUILT_PATH_RE.search(node.value):
            found.append(Violation(rel, node.lineno, "raw-path", f"string literal hand-builds an issue-matrix path: {node.value[:80]!r}"))
        elif isinstance(node, ast.Call) and _call_name(node) in MATRIX_SINKS and _mentions(_sink_arg(node), tainted):
            found.append(Violation(rel, node.lineno, "discovery-dir-read", f"{ast.unparse(node)} reads the matrix from the primary discovery dir"))
    return found


def _docstring_ids(stmts: list[ast.stmt]) -> set[int]:
    """Docstring constants of a scope and its classes (prose, not path reads)."""
    ids: set[int] = set()
    for stmt in stmts:
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str):
            ids.add(id(stmt.value))
        if isinstance(stmt, ast.ClassDef):
            ids |= _docstring_ids(stmt.body)
    return ids


def _helper_unpack_violations(rel: str, tree: ast.AST) -> list[Violation]:
    """Every helper call is unpacked positionally as ``<discovery>, <matrix> = ...``.

    This pins the split's ORDER, so swapping the destructure (the likeliest
    re-entry of #4943/#5171) or indexing into the result is a violation.
    """
    unpacked: set[int] = set()
    found: list[Violation] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and _call_name(node.value) == HELPER_NAME):
            continue
        unpacked.add(id(node.value))
        target = node.targets[0]
        names = [e.id for e in target.elts if isinstance(e, ast.Name)] if isinstance(target, ast.Tuple) else []
        if len(node.targets) != 1 or len(names) != 2 or names[0] not in DISCOVERY_DIR_NAMES or names[1] in DISCOVERY_DIR_NAMES:
            found.append(
                Violation(rel, node.lineno, "partition-swap", f"{ast.unparse(target)} = {HELPER_NAME}(...) must unpack as <discovery_dir>, <matrix_source>")
            )
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _call_name(node) == HELPER_NAME and id(node) not in unpacked:
            found.append(Violation(rel, node.lineno, "partition-swap", f"{ast.unparse(node)} result used without the positional unpack"))
    return found


def _bypass_violations(rel: str, tree: ast.AST, functions: tuple[str, ...]) -> list[Violation]:
    defs = {n.name: n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    found: list[Violation] = []
    for name in functions:
        fn = defs.get(name)
        if fn is None:
            found.append(Violation(rel, 0, "bypass", f"guarded function {name}() not found — update HELPER_CALLERS, do not drop it"))
            continue
        if not any(isinstance(n, ast.Call) and _call_name(n) == HELPER_NAME for n in ast.walk(fn)):
            found.append(Violation(rel, fn.lineno, "bypass", f"{name}() does not resolve the partition via {HELPER_NAME}()"))
    return found


def scan_python(rel: str, source: str) -> list[Violation]:
    tree = ast.parse(source, filename=rel)
    used: set[AllowedTaint] = set()
    found: list[Violation] = []
    for function, stmts in _scopes(tree):
        found += _scope_violations(rel, function, stmts, used)
    found += _helper_unpack_violations(rel, tree)
    found += _bypass_violations(rel, tree, HELPER_CALLERS.get(rel, ()))
    found += [
        Violation(rel, 0, "stale-allowlist", f"ALLOWED_TAINTS pin {entry} matches no site — remove it or restore the guarded site")
        for entry in ALLOWED_TAINTS
        if entry.path == rel and entry not in used
    ]
    return found


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _is_prohibited_span(line: str, span_start: int) -> bool:
    """True only when a prohibition directly governs the span ("Do NOT `cat ...`").

    The clause text before the span must be exactly the prohibition (plus an
    optional run/use/call), so "Never skip `cat ...`" and "Don't forget to
    `cat ...`" are still violations.
    """
    clause = re.split(r"[.:;!?]", line[:span_start])[-1]
    return bool(_PROHIBITION_CLAUSE_RE.match(clause))


def scan_skill(rel: str, text: str) -> list[Violation]:
    found: list[Violation] = []
    fenced_spans: list[tuple[int, int]] = []
    for fence in _FENCE_RE.finditer(text):
        fenced_spans.append(fence.span())
        for hit in _RAW_READ_RE.finditer(fence.group(1)):
            found.append(Violation(rel, _line_of(text, fence.start(1) + hit.start()), "doctrine-raw-read", hit.group(0)))
    offset = 0
    for lineno, line in enumerate(text.split("\n"), start=1):
        line_start, offset = offset, offset + len(line) + 1
        if any(start <= line_start < end for start, end in fenced_spans):
            continue
        for span in _INLINE_CODE_RE.finditer(line):
            if _RAW_READ_RE.search(span.group(1)) and not _is_prohibited_span(line, span.start()):
                found.append(Violation(rel, lineno, "doctrine-raw-read", span.group(1)))
    return found


def _gate4_section(text: str) -> str:
    match = re.search(r"^### Gate 4: Issue matrix.*?(?=^### )", text, re.MULTILINE | re.DOTALL)
    if match is None:
        pytest.fail(f"{GATE4_SKILL}: '### Gate 4: Issue matrix' section not found — the guard would be vacuous")
    return match.group(0)


# --------------------------------------------------------------------------- #
# The guard on the real tree
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("rel", [REVIEW_GATE, MERGE_GATES])
def test_python_consumers_have_zero_raw_issue_matrix_reads(rel: str) -> None:
    violations = scan_python(rel, _read_guarded(rel))
    assert violations == [], "issue-matrix partition bypass (route through resolve_issue_matrix_partition):\n" + "\n".join(map(str, violations))


def test_gate4_skill_has_zero_raw_issue_matrix_reads() -> None:
    text = _read_guarded(GATE4_SKILL)
    _gate4_section(text)  # fail-closed: the guarded section must exist
    violations = scan_skill(GATE4_SKILL, text)
    assert violations == [], "Gate-4 doctrine reads the issue-matrix raw:\n" + "\n".join(map(str, violations))


def test_gate4_skill_routes_through_the_resolver() -> None:
    section = _gate4_section(_read_guarded(GATE4_SKILL))
    assert "spec-kitty review" in section
    assert HELPER_NAME in section


# --------------------------------------------------------------------------- #
# Self-mutation: each rule must trip on an injected regression (non-vacuity)
# --------------------------------------------------------------------------- #

_INJECTED_RAW_PATH = '\n\ndef _injected(feature_dir):\n    return (feature_dir / "issue-matrix.json").read_text()\n'
_INJECTED_JOINPATH = '\n\ndef _injected(feature_dir):\n    return feature_dir.joinpath("issue-matrix.md").read_text()\n'
_INJECTED_LITERAL = '\n\n_INJECTED = "kitty-specs/demo/issue-matrix.json"\n'
_INJECTED_DISCOVERY_READ = "\n\ndef _injected(feature_dir):\n    return load_issue_matrix(feature_dir)\n"


class TestSelfMutation:
    @pytest.mark.parametrize("rel", [REVIEW_GATE, MERGE_GATES])
    @pytest.mark.parametrize(
        ("injection", "rule"),
        [
            (_INJECTED_RAW_PATH, "raw-path"),
            (_INJECTED_JOINPATH, "raw-path"),
            (_INJECTED_LITERAL, "raw-path"),
            (_INJECTED_DISCOVERY_READ, "discovery-dir-read"),
        ],
    )
    def test_injected_raw_read_trips(self, rel: str, injection: str, rule: str) -> None:
        source = _read_guarded(rel)
        assert not [v for v in scan_python(rel, source) if v.rule == rule]
        mutated = [v for v in scan_python(rel, source + injection) if v.rule == rule]
        assert mutated, f"{rule} did not trip on an injected regression in {rel}"

    # In-place partition swaps on the FIXED code (review cycle 1): the helper is
    # still called, but the primary discovery dir is routed into the matrix read.
    @pytest.mark.parametrize(
        ("rel", "old", "new"),
        [
            (MERGE_GATES, "feature_dir_for_blocker = coord_matrix_source", "feature_dir_for_blocker = primary_discovery_dir"),
            (MERGE_GATES, "_load_issue_matrix_rows(coord_matrix_source)", "_load_issue_matrix_rows(primary_discovery_dir)"),
            (REVIEW_GATE, "matrix_dir = matrix_source", "matrix_dir = _primary_discovery_dir"),
            (REVIEW_GATE, "matrix_dir=matrix_dir,", "matrix_dir=feature_dir,"),
            (REVIEW_GATE, "issue_matrix_artifact_present(resolved_matrix_dir", "issue_matrix_artifact_present(feature_dir"),
            (REVIEW_GATE, 'issue_matrix_path = resolved_matrix_dir / "issue-matrix.md"', 'issue_matrix_path = feature_dir / "issue-matrix.md"'),
            # Review cycle 2: attribute-held discovery dir and a hand-rebuilt mission dir.
            (REVIEW_GATE, "matrix_dir=matrix_dir,", "matrix_dir=resolved.feature_dir,"),
            (MERGE_GATES, "_load_issue_matrix_rows(coord_matrix_source)", '_load_issue_matrix_rows(repo_root / "kitty-specs" / mission_slug)'),
            (REVIEW_GATE, "matrix_dir = matrix_source", 'matrix_dir = repo_root / "kitty-specs" / mission_slug'),
            (REVIEW_GATE, "matrix_dir = matrix_source", "matrix_dir, _unused = _primary_discovery_dir, None"),
        ],
    )
    def test_partition_swap_in_fixed_code_trips(self, rel: str, old: str, new: str) -> None:
        source = _read_guarded(rel)
        assert source.count(old) == 1, f"mutation anchor {old!r} drifted in {rel}; re-pin it"
        assert scan_python(rel, source) == []
        mutated = scan_python(rel, source.replace(old, new))
        assert [v for v in mutated if v.rule in {"partition-swap", "discovery-dir-read", "raw-path"}], f"partition swap {new!r} passed the guard in {rel}"

    @pytest.mark.parametrize(
        ("rel", "old", "new", "count"),
        [
            (
                MERGE_GATES,
                "primary_discovery_dir, coord_matrix_source = resolve_issue_matrix_partition(",
                "coord_matrix_source, primary_discovery_dir = resolve_issue_matrix_partition(",
                2,
            ),
            (
                REVIEW_GATE,
                "_primary_discovery_dir, matrix_source = resolve_issue_matrix_partition(",
                "matrix_source, _primary_discovery_dir = resolve_issue_matrix_partition(",
                1,
            ),
            (
                REVIEW_GATE,
                "_primary_discovery_dir, matrix_source = resolve_issue_matrix_partition(repo_root, mission_slug)",
                "_primary_discovery_dir, matrix_source = resolve_issue_matrix_partition(repo_root, mission_slug)[::-1]",
                1,
            ),
        ],
    )
    def test_swapped_helper_unpack_trips(self, rel: str, old: str, new: str, count: int) -> None:
        # Review cycle 2: reversing the helper's (discovery, matrix) destructure
        # is the likeliest way the partition swap comes back.
        source = _read_guarded(rel)
        assert source.count(old) == count, f"mutation anchor {old!r} drifted in {rel}; re-pin it"
        swaps = [v for v in scan_python(rel, source.replace(old, new)) if v.rule == "partition-swap"]
        assert len(swaps) >= count, f"swapped unpack passed the guard in {rel}"

    def test_indexed_helper_result_trips(self) -> None:
        source = (
            _read_guarded(MERGE_GATES)
            + "\n\ndef _injected(repo_root, mission_slug):\n    return _load_issue_matrix_rows(resolve_issue_matrix_partition(repo_root, mission_slug)[0])\n"
        )
        assert any(v.rule == "partition-swap" for v in scan_python(MERGE_GATES, source))

    def test_docstring_mentioning_the_raw_path_is_not_a_violation(self) -> None:
        # False-red guard: prose that warns against the raw read is not a read.
        source = '"""Never read kitty-specs/<slug>/issue-matrix.json directly."""\n\n\ndef f():\n    """Nor kitty-specs/<slug>/issue-matrix.md."""\n'
        assert scan_python("x.py", source) == []
        assert scan_python("x.py", source + '\n_P = "kitty-specs/<slug>/issue-matrix.json"\n')

    def test_clean_reassignment_of_a_tainted_name_is_not_reported(self) -> None:
        source = "def f(feature_dir, matrix_source):\n    matrix_dir = feature_dir\n    matrix_dir = None\n    matrix_dir = matrix_source\n"
        swaps = [v for v in scan_python("x.py", source) if v.rule == "partition-swap"]
        assert [v.line for v in swaps] == [2]

    def test_allowlisted_taint_outside_its_guard_trips(self) -> None:
        # The pinned ``feature_dir_for_blocker = primary_discovery_dir`` is only
        # allowed inside the ref-content arm; the same line elsewhere is a swap.
        source = _read_guarded(MERGE_GATES).replace(
            "        blocker_message = _issue_matrix_approval_blocker(",
            "        feature_dir_for_blocker = primary_discovery_dir\n        blocker_message = _issue_matrix_approval_blocker(",
        )
        assert any(v.rule == "partition-swap" for v in scan_python(MERGE_GATES, source))

    @pytest.mark.parametrize("entry", ALLOWED_TAINTS, ids=lambda e: f"{e.function}:{e.target}")
    def test_stale_allowlist_pin_fails(self, entry: AllowedTaint) -> None:
        source = _read_guarded(entry.path)
        assert source.count(entry.value) >= 1
        mutated = scan_python(entry.path, source.replace(f"{entry.target} = {entry.value}", f"{entry.target} = None"))
        assert any(v.rule == "stale-allowlist" for v in mutated)

    @pytest.mark.parametrize("rel", [REVIEW_GATE, MERGE_GATES])
    def test_removed_helper_call_trips_bypass(self, rel: str) -> None:
        source = _read_guarded(rel)
        assert f"{HELPER_NAME}(" in source
        mutated = scan_python(rel, source.replace(f"{HELPER_NAME}(", "_bypassed_split("))
        tripped = {v.detail.split("(")[0] for v in mutated if v.rule == "bypass"}
        assert tripped == set(HELPER_CALLERS[rel])

    def test_renamed_guarded_function_fails_closed(self) -> None:
        source = _read_guarded(MERGE_GATES).replace("def _evaluate_issue_matrix_completeness_gate(", "def _renamed_gate(")
        assert any(v.rule == "bypass" and "not found" in v.detail for v in scan_python(MERGE_GATES, source))

    @pytest.mark.parametrize(
        "injection",
        [
            "\n```bash\ncat kitty-specs/<slug>/issue-matrix.json\n```\n",
            "\n```bash\njq '.rows' kitty-specs/<slug>/issue-matrix.json\n```\n",
            "\nRead the verdicts with `cat kitty-specs/<slug>/issue-matrix.json`.\n",
        ],
    )
    def test_injected_skill_raw_read_trips(self, injection: str) -> None:
        text = _read_guarded(GATE4_SKILL)
        assert scan_skill(GATE4_SKILL, text) == []
        assert scan_skill(GATE4_SKILL, text + injection), "doctrine raw-read rule did not trip"

    def test_prohibition_span_is_not_a_violation(self) -> None:
        # Pins the one carve-out so it cannot silently widen: an explicit
        # "Do NOT" ahead of the span is allowed, the same span without it is not.
        assert scan_skill("x.md", "Do NOT `cat kitty-specs/s/issue-matrix.json` directly.\n") == []
        assert scan_skill("x.md", "Then `cat kitty-specs/s/issue-matrix.json` directly.\n")
        assert scan_skill("x.md", "Never skip this step: run `cat kitty-specs/s/issue-matrix.json` first.\n")
        assert scan_skill("x.md", "Do not forget to always run `cat kitty-specs/s/issue-matrix.json` first.\n")
        assert scan_skill("x.md", "Don't forget to `cat kitty-specs/s/issue-matrix.json`.\n")
        assert scan_skill("x.md", "Never skip `cat kitty-specs/s/issue-matrix.json`.\n")
        assert scan_skill("x.md", "Never run `cat kitty-specs/s/issue-matrix.json` by hand.\n") == []

    def test_missing_gate4_section_fails_closed(self) -> None:
        with pytest.raises(pytest.fail.Exception):
            _gate4_section("# no gate here\n")

    def test_missing_guarded_file_fails_closed(self) -> None:
        with pytest.raises(pytest.fail.Exception):
            _read_guarded("src/does/not/exist.py")
