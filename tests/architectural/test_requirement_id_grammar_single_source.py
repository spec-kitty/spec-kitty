"""C-001 architectural gate: the requirement-ID grammar has exactly one home.

Mission ``requirement-id-grammar-01M3NRCA`` / WP01 / T006.

Product code has exactly one definition of the requirement-ID grammar, one
canonicalisation of IDs and one tokenisation of ``requirement_refs`` values
(C-001). This module fails CI when a NEW requirement-ID pattern literal
appears anywhere under ``src/`` outside
:data:`GRAMMAR_REL_PATH` (``src/specify_cli/requirement_mapping/grammar.py``)
and is not named on the shrink-only allow-list
(``requirement_id_pattern_allowlist.yaml``).

Detector (binding; scope stated here per the WP01 prompt)
-----------------------------------------------------------
A string literal counts as a requirement-ID pattern when its value has regex
shape over a kind: an alternation containing ``FR|NFR`` / ``NFR|`` / ``SC|``,
or a kind immediately followed by ``-\\d`` (e.g. ``FR-\\d``, ``NFR-\\d``,
``C-\\d``, ``SC-\\d``), where the kind token is preceded by the start of the
string or a non-letter character -- so ``IC-\\d`` (the concern-ID grammar,
C-004) never counts, and a plain prose id like ``FR-005`` or a placeholder
like ``FR-NNN`` never matches (no ``\\d`` follows).

**Scan context**: every string ``ast.Constant`` under ``src/``, including
``JoinedStr`` (f-string) parts, EXCEPT docstrings -- the first-statement
``Expr`` of a module, class or function body. This is the FULL scope (not a
``re.*``-call-argument-only fallback); the docstring exclusion is what keeps
prose mentions like this module's own paragraph above, or
``validate_ref_format``'s retired ``"Check refs match FR|NFR|C-\\d+ format."``
docstring, from tripping the gate.

**Canonicalisation and tokenisation are NOT visible to this gate.** It is a
pattern-literal detector only -- it cannot see a stray ``.upper()`` call on a
requirement ref or a ``split(",")`` on ``requirement_refs``. Those two halves
of C-001 are enforced by code review (see the WP01 prompt's Review Guidance),
not by this AST scan.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import pytest
import yaml

from specify_cli.requirement_mapping import grammar
from tests.architectural._ast_scan import read_and_parse

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[2]
SRC_ROOT = _REPO_ROOT / "src"
ALLOWLIST_PATH = _THIS.parent / "requirement_id_pattern_allowlist.yaml"

#: The ONE module entitled to define a requirement-ID pattern literal.
GRAMMAR_REL_PATH = "src/specify_cli/requirement_mapping/grammar.py"

#: The four kinds the gate's detector recognises (C-001's grammar vocabulary).
_KINDS: tuple[str, ...] = ("FR", "NFR", "SC", "C")


class AllowlistEntryError(ValueError):
    """Raised when a YAML allow-list entry is malformed, glob-shaped, or unjustified."""


# --------------------------------------------------------------------------- #
# Composite key + allow-list machinery.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class RequirementIdPatternKey:
    """Composite allow-list key: exact file, enclosing scope, constant name, literal."""

    rel_path: str
    qualname: str
    constant: str
    literal: str


def _require_str(mapping: dict[str, object], key: str, context: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise AllowlistEntryError(f"allow-list entry {context} is missing a non-empty {key!r} field (got {value!r})")
    return value


def _reject_glob_shaped(rel_path: str, context: str) -> None:
    """Refuse directory-glob allow-list entries -- each entry names one real module."""
    if "*" in rel_path or "?" in rel_path or rel_path.endswith("/"):
        raise AllowlistEntryError(f"allow-list entry {context} has a glob/directory-shaped file {rel_path!r}; entries must name exactly one module")
    if not rel_path.endswith(".py"):
        raise AllowlistEntryError(f"allow-list entry {context} file {rel_path!r} is not a .py module path")


def _validate_disposition(entry: dict[str, object], context: str) -> None:
    """Every entry is either frozen (with followup+rationale) or transitional (with rationale)."""
    is_frozen = bool(entry.get("frozen", False))
    is_transitional = "transitional" in entry
    if is_frozen == is_transitional:
        raise AllowlistEntryError(
            f"{context} must be exactly one of frozen: true OR a transitional: <note> (got frozen={is_frozen}, transitional={is_transitional})"
        )
    if is_frozen:
        _require_str(entry, "followup", context)
    else:
        _require_str(entry, "transitional", context)
    _require_str(entry, "rationale", context)


def load_allowlist(path: Path) -> list[RequirementIdPatternKey]:
    """Load the ``requirement_id_pattern_literals`` entries from *path*."""
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = raw.get("requirement_id_pattern_literals") or []
    keys: list[RequirementIdPatternKey] = []
    for idx, entry in enumerate(entries):
        context = f"requirement_id_pattern_literals[{idx}]"
        if not isinstance(entry, dict):
            raise AllowlistEntryError(f"{context} is not a mapping (got {entry!r})")
        rel_path = _require_str(entry, "file", context)
        _reject_glob_shaped(rel_path, context)
        qualname = _require_str(entry, "qualname", context)
        literal = _require_str(entry, "literal", context)
        constant_raw = entry.get("constant")
        constant = constant_raw if isinstance(constant_raw, str) else ""
        _validate_disposition(entry, context)
        keys.append(RequirementIdPatternKey(rel_path, qualname, constant, literal))
    return keys


def load_baseline(path: Path) -> int:
    """Return the frozen shrink-only baseline scalar."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    value = raw.get("baseline")
    if not isinstance(value, int):
        raise AllowlistEntryError(f"baseline scalar missing or non-integer in {path.name}")
    return value


def check_allowlist_ratchet(path: Path) -> list[str]:
    """Shrink-only, two-sided allow-list ratchet: entry count must equal baseline.

    Growth (more entries than baseline) and an un-lowered drop (fewer entries
    than a stale baseline) are both violations. Shared by the live gate test
    and the synthetic growth/drop tests below, so a future WP (e.g. WP04's
    transitional-entry drain) edits only the YAML -- never this test file --
    to keep the live check passing.
    """
    keys = load_allowlist(path)
    baseline = load_baseline(path)
    if len(keys) != baseline:
        return [
            f"allow-list entry count ({len(keys)}) != baseline ({baseline}) in {path.name} -- "
            "a growth must raise baseline in the same edit; a drop must lower it in the same edit"
        ]
    return []


def staleness_twin_guard(allowlist_keys: set[RequirementIdPatternKey], live_keys: set[RequirementIdPatternKey]) -> list[RequirementIdPatternKey]:
    """Allow-list keys with no matching live site (a masking or speculative entry)."""
    return sorted(allowlist_keys - live_keys, key=lambda k: (k.rel_path, k.qualname, k.constant, k.literal))


# --------------------------------------------------------------------------- #
# Detector.
# --------------------------------------------------------------------------- #
def _looks_like_requirement_id_pattern(value: str) -> bool:
    """True when *value* has regex shape over a requirement-ID kind.

    An alternation containing ``FR|NFR`` / ``NFR|`` / ``SC|``, or a kind
    immediately followed by the two literal characters ``\\d`` (a compiled
    digit-class marker), where the kind is preceded by the start of the
    string or a non-letter character -- so ``IC-\\d`` never counts (the kind
    token there is ``C``, immediately preceded by the letter ``I``).
    """
    if "FR|NFR" in value or "NFR|" in value or "SC|" in value:
        return True
    for kind in _KINDS:
        needle = f"{kind}-\\d"
        start = 0
        while True:
            idx = value.find(needle, start)
            if idx == -1:
                break
            prefix = value[idx - 1] if idx > 0 else ""
            if prefix == "" or not prefix.isalpha():
                return True
            start = idx + 1
    return False


# --------------------------------------------------------------------------- #
# AST helpers.
# --------------------------------------------------------------------------- #
def _parent_map(tree: ast.Module) -> dict[int, ast.AST]:
    parents: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
    return parents


def _qualname_from_parents(parents: dict[int, ast.AST], target: ast.AST) -> str:
    chain: list[str] = []
    cur: ast.AST | None = target
    while cur is not None:
        cur = parents.get(id(cur))
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            chain.append(cur.name)
    return ".".join(reversed(chain)) if chain else "<module>"


def _enclosing_constant_name(parents: dict[int, ast.AST], target: ast.AST) -> str:
    """Nearest enclosing simple-name ``Assign``/``AnnAssign`` target, walking up from *target*.

    Covers both plain assignment (``_KIND_ALT = "..."``) and the annotated
    form (``_KIND_ALT: str = "..."``) -- grammar.py's own core constant uses
    the annotated form.
    """
    cur: ast.AST | None = target
    while cur is not None:
        parent = parents.get(id(cur))
        if isinstance(parent, ast.Assign) and len(parent.targets) == 1 and isinstance(parent.targets[0], ast.Name):
            return parent.targets[0].id
        if isinstance(parent, ast.AnnAssign) and isinstance(parent.target, ast.Name):
            return parent.target.id
        cur = parent
    return ""


def _docstring_constant_ids(tree: ast.Module) -> set[int]:
    """``id()``s of every ``ast.Constant`` that IS a docstring.

    A docstring is the first statement of a module, class or function body,
    when that statement is an ``Expr`` wrapping a string ``Constant``.
    """
    ids: set[int] = set()
    scopes: list[ast.AST] = [tree]
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            scopes.append(node)
    for scope in scopes:
        body = getattr(scope, "body", None)
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            ids.add(id(first.value))
    return ids


@dataclass(frozen=True)
class RequirementIdPatternSite:
    """One discovered requirement-ID pattern literal. ``lineno`` is a diagnostics locator ONLY."""

    rel_path: str
    key: RequirementIdPatternKey
    lineno: int


def _rel(path: Path) -> str:
    try:
        return path.relative_to(_REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _iter_source_files(src_root: Path) -> list[Path]:
    return [p for p in sorted(src_root.rglob("*.py")) if "__pycache__" not in p.parts]


def _scan_file(path: Path, rel: str) -> list[RequirementIdPatternSite]:
    source, tree = read_and_parse(path, display=rel)
    parents = _parent_map(tree)
    docstring_ids = _docstring_constant_ids(tree)
    found: list[RequirementIdPatternSite] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        if id(node) in docstring_ids:
            continue
        if not _looks_like_requirement_id_pattern(node.value):
            continue
        key = RequirementIdPatternKey(
            rel,
            _qualname_from_parents(parents, node),
            _enclosing_constant_name(parents, node),
            node.value,
        )
        found.append(RequirementIdPatternSite(rel, key, node.lineno))
    return found


def scan_requirement_id_pattern_literals(src_root: Path) -> list[RequirementIdPatternSite]:
    """AST-walk ``<src_root>/**/*.py`` for requirement-ID pattern literals."""
    sites: list[RequirementIdPatternSite] = []
    for path in _iter_source_files(src_root):
        sites.extend(_scan_file(path, _rel(path)))
    return sites


def check_requirement_id_pattern_gate(src_root: Path, allowlist: set[RequirementIdPatternKey]) -> list[str]:
    """Return violation strings for un-allowlisted requirement-ID pattern literals."""
    violations: list[str] = []
    for site in scan_requirement_id_pattern_literals(src_root):
        if site.rel_path == GRAMMAR_REL_PATH:
            continue
        if site.key in allowlist:
            continue
        constant_suffix = f".{site.key.constant}" if site.key.constant else ""
        violations.append(
            f"{site.rel_path}:{site.lineno} ({site.key.qualname}{constant_suffix}) defines a requirement-ID pattern literal "
            f"{site.key.literal!r} outside grammar.py -- route it through "
            "specify_cli.requirement_mapping.grammar or allow-list it with a one-line rationale (C-001)"
        )
    return sorted(violations)


@lru_cache(maxsize=1)
def live_sites() -> tuple[RequirementIdPatternSite, ...]:
    """Cached census of the real ``src/`` tree (excludes grammar.py itself)."""
    return tuple(site for site in scan_requirement_id_pattern_literals(SRC_ROOT) if site.rel_path != GRAMMAR_REL_PATH)


def _live_keys() -> set[RequirementIdPatternKey]:
    return {site.key for site in live_sites()}


# =========================================================================== #
# TESTS
# =========================================================================== #


#: The one named core constant grammar.py is entitled to declare (C-001):
#: every pattern in the module -- MALFORMED_DECLARED_LEAD included -- is
#: generated from this one literal, so it is the only site the gate may find
#: there. Non-vacuity: the floor test below asserts the detected site IS this
#: constant by name, not merely "some site" (a hand-written second
#: alternation elsewhere in the module would be a DIFFERENT, un-named site
#: and must not silently satisfy this floor).
GRAMMAR_CORE_CONSTANT = "_KIND_ALT"


def test_floor_grammar_py_has_at_least_one_site() -> None:
    """Non-vacuity: the live scan finds >= 1 site in grammar.py, and it IS the named core."""
    all_sites = scan_requirement_id_pattern_literals(SRC_ROOT)
    grammar_sites = [s for s in all_sites if s.rel_path == GRAMMAR_REL_PATH]
    assert grammar_sites, "vacuous gate: no requirement-ID pattern literal detected in grammar.py"
    assert any(site.key.constant == GRAMMAR_CORE_CONSTANT for site in grammar_sites), (
        f"grammar.py's detected site(s) {[s.key.constant for s in grammar_sites]!r} do not include "
        f"the named core constant {GRAMMAR_CORE_CONSTANT!r} -- the floor would otherwise be satisfied "
        "by accident (e.g. a second, un-named hand-written alternation)"
    )


def test_gate_green_against_seeded_allowlist() -> None:
    """Single source: every live site outside grammar.py is allow-listed."""
    allowlist = set(load_allowlist(ALLOWLIST_PATH))
    violations = check_requirement_id_pattern_gate(SRC_ROOT, allowlist)
    assert violations == [], "\n".join(violations)


def test_self_mutation_injected_pattern_is_flagged(tmp_path: Path) -> None:
    """Self-mutation proof: a re-introduced requirement-ID pattern literal goes RED.

    Both an ``re.compile`` argument and a module-level constant assignment
    are exercised on the same fixture.
    """
    pkg = tmp_path / "src" / "scratch_pkg"
    pkg.mkdir(parents=True)
    content = r'''import re

_BAD = re.compile(r"\b(?:FR|NFR)-\d+\b")


def f(x):
    """See FR-005 in the docs -- a docstring mention must not trip the gate."""
    return _BAD.match(x)
'''
    (pkg / "regressed.py").write_text(content, encoding="utf-8")
    scratch_src = tmp_path / "src"

    violations = check_requirement_id_pattern_gate(scratch_src, set())
    assert violations, "self-mutation: a re-introduced requirement-ID pattern literal must be flagged"
    assert any("_BAD" in v for v in violations)


def test_self_mutation_clean_control_with_prose_and_docstring_is_not_flagged(tmp_path: Path) -> None:
    """Same-fixture clean control: prose ``FR-005`` and a docstring pattern never trip the gate.

    The docstring text is exactly the false positive the docstring
    exclusion must drop (WP01 prompt census note): ``"Check refs match
    FR|NFR|C-\\d+ format."``.
    """
    pkg = tmp_path / "src" / "scratch_pkg2"
    pkg.mkdir(parents=True)
    content = r'''def f(x):
    r"""Check refs match FR|NFR|C-\d+ format."""
    return "see FR-005 for context, and a placeholder FR-NNN too"
'''
    (pkg / "clean.py").write_text(content, encoding="utf-8")
    scratch_src = tmp_path / "src"

    assert check_requirement_id_pattern_gate(scratch_src, set()) == []


def test_concern_id_negative_control_ic_not_flagged_c_is(tmp_path: Path) -> None:
    """``IC-\\d`` (the concern-ID grammar, C-004) is never flagged; ``C-\\d`` is."""
    pkg = tmp_path / "src" / "scratch_pkg3"
    pkg.mkdir(parents=True)
    concern_file = pkg / "concern.py"

    concern_file.write_text('import re\n\n_IC_PATTERN = re.compile(r"^IC-\\d{2}$")\n', encoding="utf-8")
    scratch_src = tmp_path / "src"
    assert check_requirement_id_pattern_gate(scratch_src, set()) == []

    concern_file.write_text('import re\n\n_C_PATTERN = re.compile(r"^C-\\d{2}$")\n', encoding="utf-8")
    violations = check_requirement_id_pattern_gate(scratch_src, set())
    assert violations, "a genuine C-\\d pattern literal must be flagged"


def test_stale_allowlist_entry_has_no_live_site() -> None:
    """A speculative or leftover entry with no matching live site fails, naming the entry."""
    speculative = RequirementIdPatternKey("src/specify_cli/future_ghost.py", "<module>", "_GHOST_PATTERN", "FR-\\d+")
    stale = staleness_twin_guard({speculative}, _live_keys())
    assert stale == [speculative]


def test_allowlist_entries_are_still_live() -> None:
    """Twin-guard: every seeded entry matches a live site."""
    stale = staleness_twin_guard(set(load_allowlist(ALLOWLIST_PATH)), _live_keys())
    assert stale == [], f"stale requirement-ID pattern allow-list entries: {stale}"


def test_allowlist_entry_count_equals_baseline() -> None:
    """Shrink-only, two-sided ratchet: entry count must equal baseline.

    Uses :func:`check_allowlist_ratchet` rather than a hard-coded number, so
    a future WP (e.g. WP04 draining the transitional entry) edits only the
    YAML -- never this test -- to keep this passing.
    """
    assert check_allowlist_ratchet(ALLOWLIST_PATH) == []


def test_allowlist_accounts_for_every_live_site_two_sided() -> None:
    """The allow-list size EQUALS the live census -- every literal outside grammar.py is justified."""
    assert len(load_allowlist(ALLOWLIST_PATH)) == len(live_sites())


def test_allowlist_growth_beyond_a_smaller_baseline_is_detectable(tmp_path: Path) -> None:
    """A synthetic allow-list with more entries than its baseline is caught (growth side)."""
    grown = tmp_path / "grown.yaml"
    grown.write_text(
        "baseline: 1\n"
        "requirement_id_pattern_literals:\n"
        "  - file: src/a.py\n    qualname: \"<module>\"\n    literal: 'FR-\\d'\n    frozen: true\n    followup: x\n    rationale: y\n"
        "  - file: src/b.py\n    qualname: \"<module>\"\n    literal: 'NFR-\\d'\n    frozen: true\n    followup: x\n    rationale: y\n",
        encoding="utf-8",
    )
    violations = check_allowlist_ratchet(grown)
    assert violations != [], "a synthetic allow-list with more entries than baseline must be caught"


def test_allowlist_drop_without_lowering_baseline_is_detectable(tmp_path: Path) -> None:
    """A synthetic allow-list with fewer entries than a stale baseline is caught (drop side)."""
    shrunk = tmp_path / "shrunk.yaml"
    shrunk.write_text(
        "baseline: 3\n"
        "requirement_id_pattern_literals:\n"
        "  - file: src/a.py\n"
        '    qualname: "<module>"\n'
        "    literal: 'FR-\\d'\n"
        "    frozen: true\n"
        "    followup: x\n"
        "    rationale: y\n",
        encoding="utf-8",
    )
    violations = check_allowlist_ratchet(shrunk)
    assert violations != [], "a synthetic allow-list with fewer entries than a stale baseline must be caught"


def test_glob_shaped_allowlist_entry_is_refused(tmp_path: Path) -> None:
    """Glob/directory-shaped ``file`` fields are refused at load time (no category waivers)."""
    bad = tmp_path / "bad_allowlist.yaml"
    bad.write_text(
        "baseline: 1\n"
        "requirement_id_pattern_literals:\n"
        "  - file: 'src/specify_cli/**'\n"
        '    qualname: "<module>"\n'
        "    literal: 'FR-\\d'\n"
        "    frozen: true\n"
        "    followup: x\n"
        "    rationale: y\n",
        encoding="utf-8",
    )
    with pytest.raises(AllowlistEntryError):
        load_allowlist(bad)


def test_consolidation_retention_is_not_allowlisted() -> None:
    """The T005-migrated consumer holds no requirement-ID literal and is NOT allow-listed."""
    assert all(key.rel_path != "src/specify_cli/consolidation/retention.py" for key in load_allowlist(ALLOWLIST_PATH))
    assert all(site.rel_path != "src/specify_cli/consolidation/retention.py" for site in live_sites())


def test_rule_text_constant_is_not_flagged() -> None:
    """RULE_TEXT (T003) has no ``-\\d`` shape and must not read as a pattern literal."""
    assert not _looks_like_requirement_id_pattern(grammar.RULE_TEXT)
