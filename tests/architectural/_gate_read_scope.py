"""#7000: the repository paths an architectural battery gate READS, extracted statically.

#6996 declared each gate's scan scope once, in ``.github/ci-module-registry.yml``
(``special_tiers.architectural.scan_scopes``), and ``test_battery_scan_scope_routing.py``
proves the *routing* property over those declarations: a change inside a declared glob
selects the gate. Nothing checked that a declaration was **complete** -- a gate that
started reading ``_REPO_ROOT / "<new root>"`` kept a stale row and routing missed it
again, which is the #6994 defect class (#6988's ``scripts/release/changelog_fragments.py``
was exactly that).

This module extracts the reads and decides coverage; ``test_gate_scan_scope_completeness.py``
is the gate over the live tree and ``test_gate_read_scope_controls.py`` is its mutation
control set.

What a "read" is here
---------------------
A battery gate roots itself at the repository with ``Path(__file__).resolve().parents[2]``
(137 files did on 2026-11-01). The scan follows the names bound to that root -- including
names derived from it (``_SRC = _REPO_ROOT / "src"``) -- and records

* a ``/`` chain rooted at such a name (``_REPO_ROOT / "docs" / "adr"`` -> ``docs/adr``), and
* a traversal call on one (``(_REPO_ROOT / "docs").rglob("*.md")``, ``_REPO_ROOT.glob(...)``).

The longest chain on a source line is the read, so ``_REPO_ROOT / "a" / "b"`` is one read
(``a/b``), not three. A non-constant component (a variable, a call, an f-string slot)
becomes a ``*`` component: the scan cannot know the value, so the read is treated as
spanning that directory (``kitty-specs/*/meta.json`` -> the literal parent
``kitty-specs``), and a read rooted at the repository root itself needs ``**``.

Known limits (fail-open, by design -- inventing a read is worse than missing one)
-------------------------------------------------------------------------------
* A root taken from a pytest parameter (``repo_root``) is not followed: of the ~69 battery
  files naming one, most receive a synthetic ``tmp_path`` tree, and no fixture of that name
  is provided by a conftest, so aliasing it would invent reads.
* A ``git ls-files`` / ``ls-tree -- <paths>`` pathspec counts only when the same call names
  a repository-root name (``cwd=_REPO_ROOT``, ``-C str(_REPO_ROOT)``, ``_git(_REPO_ROOT, ...)``)
  and the paths are literals, f-strings, or a module-level tuple of literals. Pathspecs
  routed through variables, parameters, or a helper that hides the root are not seen.
* ``tests/conftest.py`` (any ``conftest.py``) is pytest plumbing and is not followed, even
  when a gate imports a name from it.
* Anything computed at runtime beyond a ``*`` component (``getattr``, ``os.path.join`` on a
  root string, ``Path(str(root) + ...)``) is invisible.

Ownership
---------
The gate set is ``tests/architectural/test_*.py``. A read inside any ``tests`` module a gate
imports transitively -- ``tests/_support``, ``tests/utils.py``, a relative import -- belongs
to that gate -- the same "battery code" attribution
``scripts.ci.gate_selection.battery_code_helpers()`` uses, and the reason
``test_clock_import_ban.py`` declares the roots its ``_clock_gate_scan`` helper walks.

Coverage
--------
A read is covered when a glob of the owning gate's ``scan_scopes`` row, or a glob of the
battery **code scope**, covers it. Code scope is derived from the router rather than
copied: ``src/**``, ``tests/architectural/**`` and every path group the
``architectural-heavy`` job selects besides ``arch_scan_scope`` (``ci_config``, the module
groups, ...). A diff in any of those already runs the whole battery, so a gate reading
them needs no declaration (the registry comment says the same).

Exemptions
----------
``EXEMPT_READS`` admits a read that is not a repository read at all -- a synthetic path the
gate asserts is absent, or an untracked cache directory it creates. Each entry is an exact
path prefix (never ``**``) with a reason, the gate must exist, and it must still be needed:
a stale entry (the read is gone, or a declaration now covers it) fails the gate.
"""

from __future__ import annotations

import ast
import fnmatch
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Final

from scripts.ci import gate_selection as gs

#: The battery tree; the gate set is its ``test_*.py`` files and its helper modules carry
#: reads on behalf of the gates that import them.
BATTERY_TREE: Final = "tests/architectural"
#: Code scope the registry comment names explicitly; the rest comes from the router.
CODE_SCOPE_EXTRA: Final[tuple[str, ...]] = ("src/**", "tests/architectural/**")
#: Traversal calls that read a directory tree; the chain they are called on is the read.
_TRAVERSALS: Final = frozenset({"glob", "rglob", "iterdir", "walk"})
#: Wildcard component a non-constant chain step becomes.
DYNAMIC: Final = "*"
#: Characters that make a path component a glob pattern.
_GLOB_CHARS: Final = frozenset("*?[")
#: Floor for the scan itself: a scanner that silently finds nothing must not pass.
MIN_GATES: Final = 90
MIN_READS: Final = 300

#: Reads that are not repository reads. Gate file -> exact path prefix -> why.
#: Deliberately tiny: a declaration is the right answer for a tracked path, even a small
#: config file, because routing must run the gate when that file changes.
EXEMPT_READS: Final[Mapping[str, Mapping[str, str]]] = {
    "tests/architectural/test_help_startup_third_party_imports.py": {
        ".nonexistent-home": (
            "The gate runs ``python -c`` with HOME pointed at this path *because* it must not exist "
            "(it proves ``--help`` loads no third-party module from a home directory). Nothing is ever "
            "tracked there, so no diff can invalidate the gate."
        ),
    },
    "tests/architectural/test_real_home_isolation_guard.py": {
        ".pytest_cache/home-isolation-probes": (
            "The gate creates this untracked pytest-cache directory and collects a probe module from a "
            "throwaway temp dir inside it, so the repo conftest applies. It is runtime scratch, never "
            "tracked and never in a diff; a ``.pytest_cache/**`` declaration would be a dead router glob."
        ),
    },
}


@dataclass(frozen=True)
class Read:
    """One repository-rooted path expression in a battery file."""

    file: str
    """Repo-relative file the expression is written in (gate or helper)."""
    lineno: int
    prefix: str
    """Repo-relative path prefix; ``""`` is the repository root, ``*`` a dynamic component."""

    @property
    def dynamic(self) -> bool:
        return DYNAMIC in self.prefix

    @property
    def target(self) -> str:
        """The path a declaration must cover: the read itself, or a dynamic read's parent."""
        if not self.dynamic:
            return self.prefix
        head = self.prefix.split(DYNAMIC, 1)[0].rstrip("/")
        return head or DYNAMIC


@dataclass(frozen=True)
class Finding:
    """An uncovered read: the owning gate and what a declaration would have to cover."""

    gate: str
    file: str
    lineno: int
    prefix: str
    target: str
    declared: tuple[str, ...]

    def describe(self) -> str:
        where = f"{self.file}:{self.lineno}"
        return f"{self.gate} reads {self.prefix!r} ({where}), not covered by scan_scopes {list(self.declared)}: declare {self.target!r}"


@dataclass(frozen=True)
class Scan:
    """The whole-tree result: what was looked at, and what is uncovered."""

    gates: tuple[str, ...]
    reads: tuple[Read, ...]
    findings: tuple[Finding, ...]
    code_scope: tuple[str, ...]
    indirections: tuple[Read, ...]
    """Reads whose whole path is computed (``_REPO_ROOT / rel``): they name no repository path,
    so there is nothing to declare; the scan records them instead of pretending to resolve them."""


# --- read extraction ------------------------------------------------------------------------


def _is_file_ref(node: ast.AST, file_names: set[str]) -> bool:
    """``__file__``, ``Path(__file__)``, ``.resolve()``/``.absolute()``/``.parent`` of one."""
    if isinstance(node, ast.Name):
        return node.id in file_names
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id == "Path":
            return bool(node.args) and isinstance(node.args[0], ast.Name) and node.args[0].id in file_names
        if isinstance(node.func, ast.Attribute) and node.func.attr in {"resolve", "absolute", "expanduser"}:
            return _is_file_ref(node.func.value, file_names)
    if isinstance(node, ast.Attribute) and node.attr == "parent":
        return _is_file_ref(node.value, file_names)
    return False


def _parents_index(node: ast.AST) -> int | None:
    if not isinstance(node, ast.Subscript):
        return None
    owner = node.value
    if not (isinstance(owner, ast.Attribute) and owner.attr == "parents"):
        return None
    index = node.slice
    if isinstance(index, ast.Constant) and isinstance(index.value, int):
        return index.value
    return None


def _literal_parts(node: ast.AST, constants: Mapping[str, str]) -> list[str] | None:
    """The path components a chain step names, or ``None`` when the value is computed.

    A string constant, a module/local name bound to one (``_MAKEFILE = "Makefile"``) and an
    f-string whose constant parts are path segments all name a component; anything else is
    ``*`` -- the scan cannot know the value, so the read spans that directory.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [part for part in node.value.strip("/").split("/") if part]
    if isinstance(node, ast.Name) and node.id in constants:
        return [part for part in constants[node.id].strip("/").split("/") if part]
    if isinstance(node, ast.JoinedStr):
        text = "".join(value.value for value in node.values if isinstance(value, ast.Constant) and isinstance(value.value, str))
        parts = [part for part in text.strip("/").split("/") if part]
        return parts + [DYNAMIC]
    return None


def _chain(node: ast.AST, roots: Mapping[str, str], constants: Mapping[str, str] | None = None) -> list[str] | None:
    """The components of a ``/`` chain rooted at a repo-root name, ``None`` when not rooted."""
    constants = constants or {}
    if isinstance(node, ast.Name) and node.id in roots:
        return [part for part in roots[node.id].split("/") if part]
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _chain(node.left, roots, constants)
        if left is None:
            return None
        right = node.right
        if isinstance(right, ast.Name) and right.id in roots:
            return left + [part for part in roots[right.id].split("/") if part]
        return left + (_literal_parts(right, constants) or [DYNAMIC])
    return None


def _traversal_root(node: ast.AST, roots: Mapping[str, str], constants: Mapping[str, str]) -> list[str] | None:
    """The chain a ``glob``/``rglob``/``iterdir``/``walk`` call traverses, ``None`` when not rooted."""
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
        return None
    if node.func.attr not in _TRAVERSALS:
        return None
    chain = _chain(node.func.value, roots, constants)
    if chain is not None and node.func.attr == "glob" and node.args:
        pattern = _literal_parts(node.args[0], constants)
        if pattern and not _GLOB_CHARS & set(pattern[0]):
            # ``root.glob("kitty-specs/*/spec.md")`` reads under kitty-specs, not the whole root.
            chain = chain + [DYNAMIC if _GLOB_CHARS & set(part) else part for part in pattern]
    return chain


def _assignments(tree: ast.AST) -> dict[str, list[ast.AST]]:
    """Every value a bare name is assigned, at module level or inside a function."""
    values: dict[str, list[ast.AST]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                values.setdefault(target.id, []).append(value)
    return values


def _resolve_root_value(value: ast.AST, file_names: set[str], roots: Mapping[str, str], root_index: int = 2) -> tuple[bool, str]:
    """``(is_root, prefix)`` for the value assigned to a name.

    ``is_root`` is False when the value is neither a file-path reference, nor
    ``<file-path>.parents[2]``, nor a chain rooted at a name already known to be a root.
    """
    parent_index = _parents_index(value)
    if parent_index == root_index and _is_file_ref(value.value.value, file_names):
        return True, ""
    if parent_index is not None and _is_file_ref(value.value.value, file_names):
        return False, ""
    parts = _chain(value, roots)
    if parts is not None:
        return True, "/".join(parts)
    return False, ""


def repo_root_names(tree: ast.AST, root_index: int = 2, imported: Mapping[str, str] | None = None) -> dict[str, str]:
    """Names bound to a repository-root path, and the prefix each one denotes.

    A name is a repository root when every value assigned to it is
    ``Path(__file__).resolve().parents[2]`` (or ``<file-path-name>.parents[2]``) or a chain
    rooted at one (``_SRC = _REPO_ROOT / "src"``). A name that is ever reassigned to
    something else -- a fixture shadowing ``repo_root`` with a ``tmp_path``, a walk variable
    advanced in a loop -- is *not* a repository root: treating it as one would invent reads
    the gate never makes.

    ``root_index`` is the ``parents[...]`` index that reaches the repository from the file
    (2 under ``tests/architectural``, 2 under ``tests/_support``, 1 for ``tests/utils.py``).
    ``imported`` seeds names a ``from tests.<module> import REPO_ROOT`` brings in from a
    module whose own root is known, unless this file also assigns them.
    """
    assignments = _assignments(tree)
    file_names: set[str] = {"__file__"}
    roots: dict[str, str] = {name: prefix for name, prefix in (imported or {}).items() if name not in assignments}
    poisoned: set[str] = set()
    changed = True
    while changed:
        changed = False
        for name, values in assignments.items():
            if name in roots or name in poisoned:
                continue
            if all(isinstance(value, ast.Call) and _is_file_ref(value, file_names) for value in values):
                file_names.add(name)
                continue
            resolved = [_resolve_root_value(value, file_names, roots, root_index) for value in values]
            if not all(is_root for is_root, _ in resolved):
                poisoned.add(name)
                continue
            prefixes = {prefix for _, prefix in resolved}
            if len(prefixes) != 1:
                poisoned.add(name)
                continue
            roots[name] = prefixes.pop()
            changed = True
    return roots


def string_constants(tree: ast.AST) -> dict[str, str]:
    """Module-level names bound to a string literal: ``_MAKEFILE = "Makefile"``.

    Only module scope, and never a name that is also a function parameter or assigned
    inside a function: a local ``relpath = "tests/example/x.py"`` in one test says nothing
    about the ``relpath`` a different function receives.
    """
    local_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            arguments = node.args
            for argument in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs):
                local_names.add(argument.arg)
            for inner in ast.walk(node):
                if isinstance(inner, ast.Name) and isinstance(inner.ctx, ast.Store):
                    local_names.add(inner.id)
    constants: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            value = node.value
            name = node.targets[0].id
            if isinstance(value, ast.Constant) and isinstance(value.value, str) and name not in local_names:
                constants[name] = value.value
    return constants


def sequence_constants(tree: ast.Module) -> dict[str, tuple[str, ...]]:
    """Module-level names bound to a tuple/list of string literals: ``_PACK_PATHS = ("a", "b")``."""
    found: dict[str, tuple[str, ...]] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            value = node.value
            if isinstance(value, (ast.Tuple, ast.List)) and value.elts:
                items = [element.value for element in value.elts if isinstance(element, ast.Constant) and isinstance(element.value, str)]
                if len(items) == len(value.elts):
                    found[node.targets[0].id] = tuple(items)
    return found


_LISTING_VERBS: Final = frozenset({"ls-files", "ls-tree"})


def _call_elements(node: ast.Call, sequences: Mapping[str, tuple[str, ...]]) -> list[ast.AST]:
    """The flat argument list of a call: positional args, one level of list/tuple, ``*CONSTANT``."""
    elements: list[ast.AST] = []
    for argument in node.args:
        if isinstance(argument, (ast.List, ast.Tuple)):
            elements.extend(argument.elts)
        elif isinstance(argument, ast.Starred) and isinstance(argument.value, ast.Name) and argument.value.id in sequences:
            elements.extend(ast.Constant(value=item) for item in sequences[argument.value.id])
        else:
            elements.append(argument)
    return elements


def _pathspec_chain(element: ast.AST, constants: Mapping[str, str]) -> list[str] | None:
    """The components a literal pathspec names, ``None`` for an option, a bare variable or ``.``."""
    if isinstance(element, ast.Constant) and not isinstance(element.value, str):
        return None
    literal = _literal_parts(element, constants)
    if literal is None:
        return None
    if isinstance(element, ast.Constant) and (str(element.value).startswith("-") or not literal):
        return None
    return [DYNAMIC if _GLOB_CHARS & set(part) else part for part in literal if part != "."] or None


def _pathspec_reads(node: ast.Call, roots: Mapping[str, str], constants: Mapping[str, str], sequences: Mapping[str, tuple[str, ...]]) -> list[list[str]]:
    """Literal ``git ls-files`` / ``git ls-tree -- <paths>`` pathspecs in a call that names the repo root.

    Git resolves a pathspec against its working directory, so the paths are repository reads
    only when the call itself shows the repository is that directory -- a repo-root name
    anywhere in the call (``cwd=_REPO_ROOT``, ``-C str(_REPO_ROOT)``, ``_git(_REPO_ROOT, ...)``).
    A call that never mentions the root (``_git("ls-files", "src")`` through a helper that
    hides it, or a ``tmp_path`` repo) is not seen, which is the sound direction to err in.
    """
    if not any(isinstance(inner, ast.Name) and inner.id in roots for inner in ast.walk(node)):
        return []
    elements = _call_elements(node, sequences)
    words = [element.value for element in elements if isinstance(element, ast.Constant) and isinstance(element.value, str)]
    verbs = _LISTING_VERBS & set(words)
    if not verbs:
        return []
    start = next(index for index, element in enumerate(elements) if isinstance(element, ast.Constant) and element.value in verbs)
    tail = elements[start + 1 :]
    if "ls-tree" in verbs:  # the first non-option word is a tree-ish; only ``--`` introduces paths
        marker = next((index for index, element in enumerate(tail) if isinstance(element, ast.Constant) and element.value == "--"), None)
        if marker is None:
            return []
        tail = tail[marker + 1 :]
    chains = (_pathspec_chain(element, constants) for element in tail)
    return [chain for chain in chains if chain]


def _imported_roots(tree: ast.Module, path: Path, root: Path) -> dict[str, str]:
    """Repo-root names a file imports from another ``tests`` module (``from tests.utils import REPO_ROOT``)."""
    imported: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        module = _resolve_import(node, path, root)
        found = _module_file(module, root) if module else None
        if found is None or not found.is_relative_to(root / "tests") or found == path:
            continue
        theirs = _module_roots(found, root)
        for alias in node.names:
            if alias.name in theirs:
                imported[alias.asname or alias.name] = theirs[alias.name]
    return imported


@cache
def _module_roots(path: Path, root: Path) -> dict[str, str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return repo_root_names(tree, len(path.relative_to(root).parts) - 1)


def repo_root_reads(path: Path, root: Path) -> tuple[Read, ...]:
    """Every repository-rooted read in ``path``, one per source line (the longest chain)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots = repo_root_names(tree, len(path.relative_to(root).parts) - 1, _imported_roots(tree, path, root))
    if not roots:
        return ()
    constants = string_constants(tree)
    sequences = sequence_constants(tree)
    relative = path.relative_to(root).as_posix()
    found: list[tuple[int, list[str]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.BinOp):
            chain = _chain(node, roots, constants)
        elif isinstance(node, ast.Call):
            chain = _traversal_root(node, roots, constants)
            found.extend((getattr(node, "lineno", 0), spec) for spec in _pathspec_reads(node, roots, constants, sequences))
        else:
            continue
        if chain is not None:
            found.append((getattr(node, "lineno", 0), chain))
    longest: dict[int, int] = {}
    for lineno, chain in found:
        longest[lineno] = max(longest.get(lineno, 0), len(chain))
    reads: list[Read] = []
    seen: set[tuple[int, str]] = set()
    for lineno, chain in found:
        if len(chain) != longest[lineno]:
            continue
        prefix = "/".join(chain)
        if (lineno, prefix) not in seen:
            seen.add((lineno, prefix))
            reads.append(Read(relative, lineno, prefix))
    return tuple(sorted(reads, key=lambda read: (read.lineno, read.prefix)))


# --- ownership ------------------------------------------------------------------------------


def _module_file(module: str, root: Path) -> Path | None:
    base = root.joinpath(*module.split("."))
    for candidate in (base.with_suffix(".py"), base / "__init__.py"):
        if candidate.is_file():
            return candidate
    return None


def imported_battery_modules(path: Path, root: Path | None = None) -> frozenset[str]:
    """The ``tests`` files ``path`` reaches through imports, itself included.

    Imports are followed wherever they point under ``tests/`` -- ``tests/_support``,
    ``tests/utils.py``, a sibling reached by a relative import -- not only inside
    ``tests/architectural``: a helper's reads belong to every gate that imports it.
    """
    root = root or _repo_root()
    gate = (root / path).resolve() if not path.is_absolute() else path
    pending = [gate]
    seen: set[str] = set()
    while pending:
        current = pending.pop()
        relative = current.relative_to(root).as_posix()
        if relative in seen:
            continue
        seen.add(relative)
        pending.extend((root / imported).resolve() for imported in _imported_files(current, root) - seen)
    return frozenset(seen)


def _resolve_import(node: ast.ImportFrom, path: Path, root: Path) -> str | None:
    """The dotted module an ``ImportFrom`` names, resolving relative levels against ``path``."""
    if node.level == 0:
        return node.module
    package = list(path.relative_to(root).parent.parts)
    keep = len(package) - (node.level - 1)
    if keep < 0:
        return None
    return ".".join([*package[:keep], *([node.module] if node.module else [])])


def _imported_files(path: Path, root: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = _resolve_import(node, path, root)
            if module:
                modules.add(module)
                modules.update(f"{module}.{alias.name}" for alias in node.names)
    files: set[str] = set()
    for module in modules:
        if module.split(".")[0] != "tests":
            continue
        found = _module_file(module, root)
        if found is None or not found.is_relative_to(root / "tests") or found.name == "conftest.py":
            continue  # a conftest is pytest-wide fixture plumbing: importing one name does not make a gate read all of it
        files.add(found.relative_to(root).as_posix())
    return files


def _repo_root() -> Path:
    """The checkout this package lives in."""
    return Path(__file__).resolve().parents[2]


def declared_scan_scopes(registry_path: Path | None = None) -> dict[str, tuple[str, ...]]:
    """Gate file -> its declared ``scan_scopes`` globs (the registry is the single source)."""
    return gs.battery_scan_scopes(registry_path)


# --- coverage -------------------------------------------------------------------------------


def code_scope(router: gs.Router | None = None) -> tuple[str, ...]:
    """The globs whose change already runs the whole battery: the router's code groups.

    A group the ``architectural-heavy`` job selects *besides* ``arch_scan_scope`` is code
    scope by construction: a diff matching it selects the battery in full, so a gate that
    reads it needs no declaration. Read from the router, never re-listed here.
    """
    router = router or gs.load_router()
    groups = router.job_gates.get(gs.HEAVY_BATTERY_JOB, frozenset()) - {gs.BATTERY_SCOPE_GROUP}
    derived = {glob for group in groups for glob in router.filters.get(group, ())}
    return (*CODE_SCOPE_EXTRA, *sorted(derived - set(CODE_SCOPE_EXTRA)))


def covers(glob: str, target: str) -> bool:
    """True when a diff matching ``glob`` can change the path ``target`` names.

    ``target`` is a repo-relative path, or a directory whose children are read (a dynamic
    read's literal parent). ``docs/**`` covers ``docs/adr``; ``docs/adr/**`` covers
    ``docs/adr`` but not ``docs/other``; ``**`` covers everything but a bare root read.
    """
    if not target or target == DYNAMIC:
        return glob == "**"
    return fnmatch.fnmatch(target, glob) or fnmatch.fnmatch(f"{target}/__probe__", glob)


def _covered(target: str, declared: Iterable[str], scope: Iterable[str]) -> bool:
    return any(covers(glob, target) for glob in (*declared, *scope))


def _exempted(gate: str, target: str, exemptions: Mapping[str, Mapping[str, str]]) -> bool:
    return any(target == prefix or target.startswith(f"{prefix}/") for prefix in exemptions.get(gate, ()))


def all_reads(root: Path | None = None) -> tuple[Read, ...]:
    """Every read written in a gate or in any ``tests`` module a gate reaches, cached per file."""
    root = root or _repo_root()
    files: set[str] = set()
    for gate in gate_files(root):
        files |= imported_battery_modules(root / gate, root)
    files.update(path.relative_to(root).as_posix() for path in (root / BATTERY_TREE).rglob("*.py"))
    reads: list[Read] = []
    for relative in sorted(files):
        reads.extend(_cached_reads(root / relative, root))
    return tuple(reads)


@cache
def _cached_reads(path: Path, root: Path) -> tuple[Read, ...]:
    return repo_root_reads(path, root)


def gate_files(root: Path | None = None) -> tuple[str, ...]:
    """The gate set: every ``tests/architectural/test_*.py`` file, repo-relative and sorted."""
    root = root or _repo_root()
    return tuple(sorted(path.relative_to(root).as_posix() for path in (root / BATTERY_TREE).glob("test_*.py")))


def scan(
    *,
    root: Path | None = None,
    registry_path: Path | None = None,
    router: gs.Router | None = None,
    exemptions: Mapping[str, Mapping[str, str]] | None = None,
) -> Scan:
    """Extract every gate's reads and report the ones no declaration and no code scope covers."""
    root = root or _repo_root()
    exemptions = EXEMPT_READS if exemptions is None else exemptions
    declared = declared_scan_scopes(registry_path)
    scope = code_scope(router)
    reads = all_reads(root)
    findings: list[Finding] = []
    indirections: list[Read] = []
    for gate in gate_files(root):
        closure = imported_battery_modules(root / gate, root)
        gate_declared = declared.get(gate, ())
        for read in reads:
            if read.file not in closure:
                continue
            if read.target == DYNAMIC:
                indirections.append(read)
                continue
            if _covered(read.target, gate_declared, scope) or _exempted(gate, read.target, exemptions):
                continue
            findings.append(Finding(gate, read.file, read.lineno, read.prefix, read.target, gate_declared))
    findings.sort(key=lambda finding: (finding.gate, finding.file, finding.lineno, finding.prefix))
    return Scan(gate_files(root), reads, tuple(findings), scope, tuple(indirections))


def validate_exemptions(
    *,
    root: Path | None = None,
    registry_path: Path | None = None,
    router: gs.Router | None = None,
    exemptions: Mapping[str, Mapping[str, str]] | None = None,
) -> tuple[str, ...]:
    """Problems with the exemption table: unexplained, too wide, unknown, or no longer needed."""
    root = root or _repo_root()
    exemptions = EXEMPT_READS if exemptions is None else exemptions
    declared = declared_scan_scopes(registry_path)
    scope = code_scope(router)
    gates = set(gate_files(root))
    problems: list[str] = []
    still_needed: set[tuple[str, str]] = set()
    reads_by_file: dict[str, list[Read]] = {}
    for read in all_reads(root):
        reads_by_file.setdefault(read.file, []).append(read)
    for gate in sorted(gates):
        closure = imported_battery_modules(root / gate, root)
        candidates = [read for member in sorted(closure) for read in reads_by_file.get(member, [])]
        for read in candidates:
            if read.target != DYNAMIC and not _covered(read.target, declared.get(gate, ()), scope):
                still_needed.add((gate, read.target))
    for gate in sorted(exemptions):
        entries = exemptions[gate]
        if gate not in gates:
            problems.append(f"{gate}: exemption for a file that is not a battery gate")
        for prefix, reason in sorted(entries.items()):
            if not reason.strip():
                problems.append(f"{gate}: exemption {prefix!r} has no reason")
            if DYNAMIC in prefix:
                problems.append(f"{gate}: exemption {prefix!r} uses a wildcard; name the exact path or declare it")
            if (gate, prefix) not in still_needed:
                problems.append(f"{gate}: exemption {prefix!r} is stale -- the read is gone or a declaration now covers it")
    return tuple(problems)
