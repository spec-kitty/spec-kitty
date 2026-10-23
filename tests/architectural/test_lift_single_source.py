"""Meta-gate: a ``test_lifted_*`` gate shares its source's code instead of copying it (#5015).

A lift re-runs an out-of-matrix source suite's invariant on every pull request,
while the source itself runs only in the nightly. A hand-copied lift therefore
keeps enforcing the *old* predicate after the source changes: the
``.gitignore`` lift went red on CI over exactly that in #5008, and the
``load_meta`` census drifted the same way before #5138 gave it one home.

The convention this gate holds: the code a lift shares with its source lives
once, in a ``tests/architectural/_lifted_<topic>.py`` (or another shared
module) that BOTH files import -- tests included, since importing a test
function is what makes pytest collect it in the importing module. So, for
every ``tests/architectural/test_lifted_*.py``:

1. **It names its source.** The module docstring names at least one existing
   ``tests/...py`` source in double backticks; that is the pairing every check
   below keys on. A lift whose source is gone is listed, with its reason, in
   :data:`SOURCELESS_LIFTS`.
2. **No name is bound twice.** No module-level name that one file binds by a
   definition (``def``, ``class``, assignment) is bound in the other file at
   all. Two definitions are a hand-copy; a definition on one side shadowing the
   shared import on the other is the same split-brain. Neither file may define
   a name that a shared home (a ``tests.*`` module BOTH import from) defines.
   Only :data:`MODULE_MARKERS` (each file's own markers) are exempt.
3. **No renamed copy.** No function, class or container constant (a literal
   tuple, list, set or dict of two or more elements) in either file copies one
   in the other file or in any ``tests.*`` module either file imports, under
   another name (docstrings and annotations ignored; decorators, bases and
   argument names compared; empty bodies never match). So a copy cannot dodge
   rule 2 by renaming, nor by dropping the shared import.

Rule 3 limit: a copy matches only on an identical body, so a copy that is both renamed AND edited is not
caught by rule 3 (rule 1 still ties the lift to its source).

There is no exemption list for rules 2 and 3: the census of 2026-10-22 drained
every pair, so an intentional difference is a different body under a
different name, and anything shared is imported.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.architectural._ast_scan import parse_file, parse_source

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_LIFT_GLOB = "test_lifted_*.py"
_ARCH_PREFIX = "tests/architectural/"

#: A docstring's source reference: a repository-relative ``tests/...py`` path in double backticks.
_SOURCE_REF = re.compile(r"``(tests/[\w./-]+\.py)``")

#: Module-level names each file legitimately binds for itself.
MODULE_MARKERS: frozenset[str] = frozenset({"pytestmark"})

#: Lifts with no live source, and why. A listed lift that names an existing
#: source again, or no longer exists, fails :func:`test_sourceless_allowlist_is_live`.
SOURCELESS_LIFTS: dict[str, str] = {
    "test_lifted_cli_doctrine_retirement.py": (
        "the doctrine group's source suite was retired with the group in mission charter-pack-cutover-01M491G6 (#3732); this gate is the invariant's only home"
    ),
}

#: Non-vacuity floors (the census of 2026-10-22): a glob or docstring regression
#: that silently drops lifts or pairs fails instead of passing on nothing.
_LIFT_FLOOR = 24
_PAIR_FLOOR = 23


@dataclass(frozen=True)
class Pair:
    """One lift and one source it names."""

    lift: Path
    source: Path

    @property
    def label(self) -> str:
        return f"{self.lift.name} <- {self.source.relative_to(_REPO_ROOT).as_posix()}"


def lift_paths(root: Path = _REPO_ROOT) -> list[Path]:
    return sorted((root / "tests" / "architectural").glob(_LIFT_GLOB))


def named_sources(tree: ast.Module) -> list[str]:
    """The ``tests/...py`` paths the module docstring names, in order, deduplicated.

    Paths under ``tests/architectural/`` are not sources: a lift may cite its own
    shared home or a sibling gate, and neither is the suite it lifts.
    """
    refs = _SOURCE_REF.findall(ast.get_docstring(tree) or "")
    return list(dict.fromkeys(ref for ref in refs if not ref.startswith(_ARCH_PREFIX)))


def names_live_source(lift: Path, root: Path = _REPO_ROOT) -> bool:
    return any((root / ref).is_file() for ref in named_sources(parse_file(lift)))


def lift_pairs(root: Path = _REPO_ROOT) -> list[Pair]:
    pairs: list[Pair] = []
    for lift in lift_paths(root):
        for ref in named_sources(parse_file(lift)):
            source = root / ref
            if source.is_file():
                pairs.append(Pair(lift, source))
    return pairs


def _assign_targets(node: ast.stmt) -> Iterator[ast.expr]:
    if isinstance(node, ast.Assign):
        yield from node.targets
    elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        yield node.target


def _target_names(target: ast.expr) -> Iterator[str]:
    if isinstance(target, ast.Name):
        yield target.id
    elif isinstance(target, (ast.Tuple, ast.List)):
        for element in target.elts:
            yield from _target_names(element)


def defined_names(tree: ast.Module) -> set[str]:
    """Module-level names bound by a definition (not by an import)."""
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        for target in _assign_targets(node):
            names.update(_target_names(target))
    return names


def imported_names(tree: ast.Module) -> set[str]:
    """Module-level names bound by an import (the alias when there is one)."""
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((alias.asname or alias.name).split(".")[0] for alias in node.names)
    return names


def double_bound(lift: ast.Module, source: ast.Module) -> set[str]:
    """Rule 2: names one side defines and the other side binds at all."""
    lift_defined, source_defined = defined_names(lift), defined_names(source)
    lift_bound = lift_defined | imported_names(lift)
    source_bound = source_defined | imported_names(source)
    return ((lift_defined & source_bound) | (source_defined & lift_bound)) - MODULE_MARKERS


def _is_trivial(body: list[ast.stmt]) -> bool:
    """An empty, ``pass`` or ``...`` body: two of those are not a copy of anything."""
    return all(isinstance(stmt, ast.Pass) or (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)) for stmt in body)


def _body_key(node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> str | None:
    """The node with its name, docstrings and annotations stripped, so a renamed copy compares equal.

    Decorators, bases and argument names stay in the key; a trivial body has no key.
    """
    clone = parse_source(ast.unparse(node), display="<lifted-body>").body[0]
    for sub in ast.walk(clone):
        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
            sub.returns = None
            for arg in (*sub.args.posonlyargs, *sub.args.args, *sub.args.kwonlyargs, sub.args.vararg, sub.args.kwarg):
                if arg is not None:
                    arg.annotation = None
        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and ast.get_docstring(sub) is not None:
            sub.body = sub.body[1:] or [ast.Pass()]
    assert isinstance(clone, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    if _is_trivial(clone.body):
        return None
    clone.name = "_"
    return ast.dump(clone)


def _value_key(node: ast.stmt) -> str | None:
    """A module-level container literal of two or more elements, the shape of a hand-copied allowlist or table."""
    value = node.value if isinstance(node, (ast.Assign, ast.AnnAssign)) else None
    if isinstance(value, (ast.Tuple, ast.List, ast.Set)) and len(value.elts) >= 2:
        return ast.dump(value)
    if isinstance(value, ast.Dict) and len(value.keys) >= 2:
        return ast.dump(value)
    return None


def _bodies(tree: ast.Module) -> dict[str, str]:
    keys: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if (key := _body_key(node)) is not None:
                keys[node.name] = key
        elif (key := _value_key(node)) is not None:
            for target in _assign_targets(node):
                keys.update(dict.fromkeys(_target_names(target), key))
    return keys


def renamed_copies(lift: ast.Module, source: ast.Module) -> set[tuple[str, str]]:
    """Rule 3: ``(lift name, source name)`` for each function, class or container constant copied under another name."""
    by_body: dict[str, list[str]] = {}
    for name, key in _bodies(source).items():
        by_body.setdefault(key, []).append(name)
    return {(name, other) for name, key in _bodies(lift).items() for other in by_body.get(key, []) if other != name}


def imported_tests_modules(tree: ast.Module) -> set[str]:
    """The ``tests.*`` modules a file imports from at module level."""
    modules: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "tests":
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names if alias.name.split(".")[0] == "tests")
    return modules


def _parse_modules(modules: set[str], root: Path) -> dict[str, ast.Module]:
    homes: dict[str, ast.Module] = {}
    for module in sorted(modules):
        base = root.joinpath(*module.split("."))
        for path in (base.with_suffix(".py"), base / "__init__.py"):
            if path.is_file():
                homes[module] = parse_file(path)
                break
    return homes


def shared_homes(lift: ast.Module, source: ast.Module, root: Path = _REPO_ROOT) -> dict[str, ast.Module]:
    """The ``tests.*`` modules BOTH files import from: the pair's shared homes, parsed."""
    return _parse_modules(imported_tests_modules(lift) & imported_tests_modules(source), root)


def imported_homes(lift: ast.Module, source: ast.Module, root: Path = _REPO_ROOT) -> dict[str, ast.Module]:
    """Every ``tests.*`` module EITHER file imports from, parsed.

    Rule 3 checks against these, so a lift that drops the shared import and pastes
    the home's tests under new names is still caught against the home its source
    keeps importing.
    """
    return _parse_modules(imported_tests_modules(lift) | imported_tests_modules(source), root)


def redefined_from(tree: ast.Module, home: ast.Module) -> set[tuple[str, str]]:
    """``(name, name)`` for each definition in ``tree`` that re-defines one of ``home``'s names."""
    return {(name, name) for name in (defined_names(tree) & defined_names(home)) - MODULE_MARKERS}


def pair_violations(
    lift: ast.Module,
    source: ast.Module,
    shared: dict[str, ast.Module] | None = None,
    imported: dict[str, ast.Module] | None = None,
) -> list[str]:
    """Every rule-2 and rule-3 finding for one pair.

    ``shared`` are the homes both files import (rule 2 by name); ``imported`` are
    the ``tests.*`` modules either file imports (rule 3 by body). Each defaults to
    none, which checks the two files against each other only.
    """
    found = [f"{name} is bound in both files and defined in at least one" for name in sorted(double_bound(lift, source))]
    found += [f"{name} copies the body of {other}" for name, other in sorted(renamed_copies(lift, source))]
    for side, tree in (("lift", lift), ("source", source)):
        copies: set[tuple[str, str, str]] = set()
        for module, home in (shared or {}).items():
            copies.update((name, module, other) for name, other in redefined_from(tree, home))
        for module, home in (imported or {}).items():
            copies.update((name, module, other) for name, other in renamed_copies(tree, home))
        found += [f"the {side}'s {name} copies {module}.{other}" for name, module, other in sorted(copies)]
    return found


# ---------------------------------------------------------------------------
# The gate over the live tree
# ---------------------------------------------------------------------------


def test_every_lift_names_an_existing_source() -> None:
    lifts = lift_paths()
    assert len(lifts) >= _LIFT_FLOOR, f"only {len(lifts)} lifts found (floor {_LIFT_FLOOR}); if a lift was retired on purpose, lower _LIFT_FLOOR to match"
    unnamed = [lift.name for lift in lifts if lift.name not in SOURCELESS_LIFTS and not names_live_source(lift)]
    assert not unnamed, (
        "these lifts name no existing ``tests/...py`` source in their docstring; name the source the lift re-runs, "
        f"or list the lift in SOURCELESS_LIFTS with the reason it has none: {unnamed}"
    )


def test_sourceless_allowlist_is_live() -> None:
    present = {lift.name: lift for lift in lift_paths()}
    stale = {name for name in SOURCELESS_LIFTS if name not in present or names_live_source(present[name])}
    assert not stale, f"SOURCELESS_LIFTS entries that are gone or name a live source again; remove them: {sorted(stale)}"


def test_no_lift_copies_its_source() -> None:
    pairs = lift_pairs()
    assert len(pairs) >= _PAIR_FLOOR, (
        f"only {len(pairs)} lift/source pairs found (floor {_PAIR_FLOOR}); if a lift was retired on purpose, lower _PAIR_FLOOR to match"
    )
    offenders: dict[str, list[str]] = {}
    for pair in pairs:
        lift, source = parse_file(pair.lift), parse_file(pair.source)
        if found := pair_violations(lift, source, shared_homes(lift, source), imported_homes(lift, source)):
            offenders[pair.label] = found
    assert not offenders, (
        "a lift and its source define the same code twice, so the per-PR gate can drift from the source it lifts (#5015). "
        "Move the shared code into one tests/architectural/_lifted_<topic>.py module and import it from both files "
        "(import a test with `from <home> import test_x as test_x` so pytest collects it):\n"
        + "\n".join(f"  {label}: {'; '.join(found)}" for label, found in sorted(offenders.items()))
    )


# ---------------------------------------------------------------------------
# Planted violations: each relation goes red on the shape it exists to catch
# ---------------------------------------------------------------------------

_SHARED_IMPORT = "from tests.architectural._lifted_demo import ALLOWED, test_scan as test_scan\n"


def _tree(source: str) -> ast.Module:
    return parse_source(source, display="<planted>")


@pytest.mark.parametrize(
    ("lift", "source", "expected"),
    [
        pytest.param(
            "ALLOWED = ('a/',)\n",
            "ALLOWED = ('a/', 'b/')\n",
            {"ALLOWED"},
            id="hand-copied-constant-that-drifted",
        ),
        pytest.param(
            "def test_scan():\n    assert True\n",
            "def test_scan():\n    '''Documented.'''\n    assert True\n",
            {"test_scan"},
            id="hand-copied-test",
        ),
        pytest.param(
            _SHARED_IMPORT,
            "ALLOWED = ('a/',)\n" + _SHARED_IMPORT.replace("ALLOWED, ", ""),
            {"ALLOWED"},
            id="source-shadows-the-shared-import",
        ),
        pytest.param(
            "def _helper(x: int) -> int:\n    return x\n",
            "from tests.architectural._lifted_demo import _helper\n",
            {"_helper"},
            id="lift-redefines-what-the-source-imports",
        ),
        pytest.param(
            "(A, B) = (1, 2)\n",
            "B = 2\n",
            {"B"},
            id="tuple-target",
        ),
    ],
)
def test_double_bound_catches(lift: str, source: str, expected: set[str]) -> None:
    assert double_bound(_tree(lift), _tree(source)) == expected


def test_double_bound_passes_the_shared_shape() -> None:
    marker = "import pytest\npytestmark = [pytest.mark.architectural]\n"
    assert double_bound(_tree(_SHARED_IMPORT + marker), _tree(_SHARED_IMPORT + marker)) == set()


def test_renamed_copy_is_caught_and_a_narrowing_is_not() -> None:
    source = _tree("def test_hidden(x: int) -> None:\n    '''Source doc.'''\n    assert x == 1\n")
    renamed = _tree("def test_still_hidden(x):\n    assert x == 1\n")
    narrowed = _tree("def test_still_hidden(x):\n    assert x\n")
    assert renamed_copies(renamed, source) == {("test_still_hidden", "test_hidden")}
    assert renamed_copies(narrowed, source) == set()


def test_a_renamed_container_constant_is_a_copy() -> None:
    source = _tree("ALLOWLIST_PREFIXES = ('kitty-specs/', 'docs/changelog/')\n")
    assert renamed_copies(_tree("_PREFIXES = ('kitty-specs/', 'docs/changelog/')\n"), source) == {("_PREFIXES", "ALLOWLIST_PREFIXES")}


@pytest.mark.parametrize(
    ("lift", "source"),
    [
        pytest.param("def _a(x):\n    pass\n", "def _b(y, z):\n    pass\n", id="empty-stubs"),
        pytest.param("class LiftErr(ValueError):\n    '''Doc.'''\n", "class SourceErr(RuntimeError):\n    '''Doc.'''\n", id="docstring-only-classes"),
        pytest.param("def _a(x):\n    return x\n", "def _b(y):\n    return y\n", id="different-arguments"),
        pytest.param("class A(ValueError):\n    code = 1\n", "class B(RuntimeError):\n    code = 1\n", id="different-bases"),
        pytest.param(
            "_ONE = ('kitty-specs/',)\n_ROOT = 'kitty-specs/'\n",
            "ALLOWLIST_PREFIXES = ('kitty-specs/', 'docs/changelog/')\n",
            id="single-element-container-or-scalar",
        ),
    ],
)
def test_rule_three_ignores_what_is_not_a_copy(lift: str, source: str) -> None:
    assert renamed_copies(_tree(lift), _tree(source)) == set()


def _write_home(root: Path) -> None:
    home_dir = root / "tests" / "architectural"
    home_dir.mkdir(parents=True)
    (home_dir / "_lifted_demo.py").write_text(
        "ALLOWED = ('a/',)\n\ndef test_scan(x: int) -> None:\n    assert x\n",
        encoding="utf-8",
    )


def test_a_copy_of_the_shared_home_is_caught(tmp_path: Path) -> None:
    _write_home(tmp_path)
    only_the_test = _SHARED_IMPORT.replace("ALLOWED, ", "")
    lift = _tree(only_the_test + "ALLOWED = ('a/', 'b/')\n")
    source = _tree(only_the_test + "def test_scan_again(x):\n    assert x\n")
    shared, imported = shared_homes(lift, source, tmp_path), imported_homes(lift, source, tmp_path)
    assert list(shared) == list(imported) == ["tests.architectural._lifted_demo"]
    assert pair_violations(lift, source, shared, imported) == [
        "the lift's ALLOWED copies tests.architectural._lifted_demo.ALLOWED",
        "the source's test_scan_again copies tests.architectural._lifted_demo.test_scan",
    ]
    clean = _tree(_SHARED_IMPORT)
    assert pair_violations(clean, clean, shared_homes(clean, clean, tmp_path), imported_homes(clean, clean, tmp_path)) == []


def test_a_lift_that_drops_the_shared_import_is_still_checked_against_it(tmp_path: Path) -> None:
    _write_home(tmp_path)
    lift = _tree("import pytest\n\ndef test_lifted_scan(x):\n    assert x\n")
    source = _tree(_SHARED_IMPORT)
    assert shared_homes(lift, source, tmp_path) == {}
    assert pair_violations(lift, source, shared_homes(lift, source, tmp_path), imported_homes(lift, source, tmp_path)) == [
        "the lift's test_lifted_scan copies tests.architectural._lifted_demo.test_scan",
    ]


def test_pair_discovery_reads_docstring_sources(tmp_path: Path) -> None:
    arch = tmp_path / "tests" / "architectural"
    arch.mkdir(parents=True)
    (tmp_path / "tests" / "src_suite.py").write_text("X = 1\n", encoding="utf-8")
    (arch / "_lifted_demo.py").write_text("Y = 2\n", encoding="utf-8")
    (arch / "test_lifted_demo.py").write_text(
        '"""Lifted from ``tests/src_suite.py`` and ``tests/gone.py``; shared code in ``tests/architectural/_lifted_demo.py``."""\nX = 1\n',
        encoding="utf-8",
    )
    pairs = lift_pairs(tmp_path)
    assert [(pair.lift.name, pair.source.name) for pair in pairs] == [("test_lifted_demo.py", "src_suite.py")]
    assert pair_violations(parse_file(pairs[0].lift), parse_file(pairs[0].source)) == ["X is bound in both files and defined in at least one"]
