"""P1 dead-code census oracle (E3) — the bidirectional machine guardrail.

Contract: ``kitty-specs/ci-pipeline-reinstatement-01M1X35E/contracts/p1-census-oracle.md``
(FR-013 census / C-006 / NFR-006). Consumed by WP03 (base-red drops), WP05
(shard/``--cov`` exclusion) and WP15 (denominator exclusion).

Public API (the surface WP03/WP05/WP15 import):

* :func:`is_dead` — ``(surface) -> (bool, evidence)``.
* :func:`census_dead_surfaces` — the validated set of census-``dead`` surfaces
  (non-vacuous per DIR-043; raises :class:`VacuousCensusError` on an empty set).
* :func:`authorize_drop` — the false-negative guard: authorize a base-red drop
  only with independent evidence about the *src surface under test*.
* :func:`denominator_excluded_surfaces` — census-``dead`` surfaces excluded from
  the coverage denominator (never the always-on enforcement allowlists).

Load-bearing distinctions this oracle encodes as machine checks, not prose:

* **Subject rule** — the census judges a *src surface*, never a test file's own
  (always-zero) importer count. :func:`authorize_drop` refuses a ``tests.*``
  subject outright (:class:`SubjectNotSrcSurfaceError`).
* **False-negative guard** — a drop needs independent, reviewer-checkable
  evidence about the src surface (a retirement gate, an ADR, or
  zero-importer-AND-not-dynamically-reached). A bare label
  (:class:`UnevidencedDeadError`) or a live src surface
  (:class:`LiveSurfaceNotDroppableError`) is refused.
* **False-positive guard** — "known live is never dead": a surface reachable
  only dynamically (entry points, plugin/registry dispatch, ``getattr``/
  import-string, CLI wiring) with a static importer-count of 0 is not marked
  ``dead`` (:class:`KnownLiveNotDeadError`).

Importer-graph resolution reuses the canonical
``specify_cli.ast_analysis.imports.module_of_import_from`` (SO#6: shared with
``test_no_dead_modules`` / ``test_no_dead_symbols``); retirement evidence reuses
``test_no_retired_subsystems`` — this oracle never forks a second census.
"""

from __future__ import annotations

import ast
import json
import tomllib
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path

from specify_cli.ast_analysis.imports import module_of_import_from
from tests.architectural._ast_scan import parse_file

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CENSUS_PATH = Path(__file__).resolve().parent / "p1_census" / "census.json"

# Roots scanned for the static importer graph. The census subject is a *src*
# surface; ``tests`` is scanned so an importer that lives in a test still
# counts toward "known live" (a surface exercised by a real test is not dead).
_IMPORT_ROOTS: tuple[str, ...] = ("src", "tests")
_SRC_ROOT_NAME = "src"

# The always-on enforcement allowlists that *quote* dead surfaces as banned
# strings. They are out of scope of census exclusion (C-006 boundary) and must
# never be excluded from CI or the coverage denominator.
_ENFORCEMENT_ALLOWLIST_GATES: frozenset[str] = frozenset(
    {
        "test_no_dead_symbols",
        "test_no_dead_modules",
        "test_no_retired_subsystems",
    }
)

_RETIREMENT_EVIDENCE = "retirement-gate:test_no_retired_subsystems"


class CensusError(Exception):
    """Base class for census-oracle refusals."""


class VacuousCensusError(CensusError):
    """The oracle evaluated an empty set of dead surfaces (DIR-043 / SO#5)."""


class UnevidencedDeadError(CensusError):
    """A ``dead`` entry lacks valid, independent evidence (false-negative guard)."""


class LiveSurfaceNotDroppableError(CensusError):
    """A drop was requested for a live src surface (false-negative guard)."""


class KnownLiveNotDeadError(CensusError):
    """A dynamically-reached, importer-0 surface was marked dead (false-positive guard)."""


class SubjectNotSrcSurfaceError(CensusError):
    """The census subject is a test module, not a src surface (subject rule)."""


@dataclass(frozen=True)
class CensusEntry:
    """One census ledger row (E3 schema)."""

    surface: str
    status: str
    evidence: str
    authorizes: str | None = None
    note: str = ""


@dataclass(frozen=True)
class Verdict:
    """The oracle's independent status determination for a surface."""

    surface: str
    dead: bool
    evidence: str


# ---------------------------------------------------------------------------
# Census loading
# ---------------------------------------------------------------------------
def load_census(path: Path = _CENSUS_PATH) -> tuple[CensusEntry, ...]:
    """Load the census ledger from *path* into typed entries."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return tuple(
        CensusEntry(
            surface=row["surface"],
            status=row["status"],
            evidence=row.get("evidence", ""),
            authorizes=row.get("authorizes"),
            note=row.get("note", ""),
        )
        for row in payload["surfaces"]
    )


def _resolve_census(census: Sequence[CensusEntry] | None) -> tuple[CensusEntry, ...]:
    return tuple(census) if census is not None else load_census()


def _entry_for(census: Sequence[CensusEntry], surface: str) -> CensusEntry | None:
    for entry in census:
        if entry.surface == surface:
            return entry
    return None


# ---------------------------------------------------------------------------
# Static importer graph (reuses the canonical import resolver)
# ---------------------------------------------------------------------------
def _iter_python_files(root: Path, roots: Sequence[str]) -> Iterator[Path]:
    for name in roots:
        base = root / name
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.py")):
            if "__pycache__" not in path.parts:
                yield path


def _containing_pkg(path: Path, root: Path) -> str:
    """Dotted package of *path* for relative-import resolution.

    ``src/`` modules are dotted relative to ``src/`` (``specify_cli.foo``);
    every other root is dotted relative to the repo root (``tests.architectural``).
    """
    relative = path.relative_to(root)
    parts = relative.with_suffix("").parts
    if parts and parts[0] == _SRC_ROOT_NAME:
        parts = parts[1:]
    return ".".join(parts[:-1])


def _file_imports_surface(tree: ast.Module, surface: str, containing_pkg: str) -> bool:
    prefix = surface + "."
    parts = surface.split(".")
    parent = ".".join(parts[:-1])
    leaf = parts[-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = module_of_import_from(node, containing_pkg)
            if module == surface or module.startswith(prefix):
                return True
            if module == parent and any(alias.name == leaf for alias in node.names):
                return True
        elif isinstance(node, ast.Import):
            if any(alias.name == surface or alias.name.startswith(prefix) for alias in node.names):
                return True
    return False


def static_importer_count(
    surface: str,
    *,
    root: Path = _REPO_ROOT,
    roots: Sequence[str] = _IMPORT_ROOTS,
) -> int:
    """Count files under *roots* that statically import *surface*.

    Measured over the **src surface**, per the subject rule — never a test
    file's own (always-zero) importer count.
    """
    count = 0
    for path in _iter_python_files(root, roots):
        tree = parse_file(path)
        if _file_imports_surface(tree, surface, _containing_pkg(path, root)):
            count += 1
    return count


# ---------------------------------------------------------------------------
# Retirement evidence (reuses test_no_retired_subsystems)
# ---------------------------------------------------------------------------
def retirement_evidence(surface: str) -> str | None:
    """Return the retirement-gate evidence string iff *surface* is retired.

    Reuses the canonical ``test_no_retired_subsystems`` data (imported lazily so
    a consumer importing this oracle does not pay that module's import cost).
    """
    from tests.architectural.test_no_retired_subsystems import (
        _RETIRED_PATHS,
        _has_banned_prefix,
    )

    if _has_banned_prefix(surface):
        return _RETIREMENT_EVIDENCE
    if surface in _RETIRED_PATHS or f"src/{surface.replace('.', '/')}" in _RETIRED_PATHS:
        return _RETIREMENT_EVIDENCE
    return None


# ---------------------------------------------------------------------------
# Dynamic reachability (the "known live is never dead" signals)
# ---------------------------------------------------------------------------
# A surface with a static importer-count of 0 is NOT dead if it is reached at
# runtime through a dynamic path: an import-string / getattr dispatch, a plugin
# or registry lookup, CLI wiring, or a pyproject entry point. Under-enumerating
# these signals is the false-positive that wrongly drops live code, so the set
# is explicit and each signal is checkable.
_DYNAMIC_DISPATCH_CALLS: frozenset[str] = frozenset({"import_module", "__import__", "getattr", "setattr", "patch"})


def _string_dispatch_target(node: ast.AST) -> str | None:
    """Return the dotted string a dynamic-dispatch call names, if any.

    Recognizes ``import_module("a.b")`` / ``getattr``/``setattr``/``patch`` and
    ``__import__`` — the import-string, plugin/registry and CLI-wiring dispatch
    forms whose target is a module string literal.
    """
    if not isinstance(node, ast.Call) or not node.args:
        return None
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else func.id if isinstance(func, ast.Name) else ""
    if name not in _DYNAMIC_DISPATCH_CALLS:
        return None
    argument = node.args[0]
    if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
        return argument.value
    return None


def dynamic_reach_signals(
    surface: str,
    *,
    root: Path = _REPO_ROOT,
    roots: Sequence[str] = _IMPORT_ROOTS,
) -> tuple[str, ...]:
    """Return the dynamic-reachability signals that keep *surface* live.

    Signals: an import-string / registry / getattr dispatch naming the surface
    (or a submodule of it), and a pyproject ``[project.scripts]`` entry point.
    """
    prefix = surface + "."
    signals: list[str] = []
    for path in _iter_python_files(root, roots):
        tree = parse_file(path)
        for node in ast.walk(tree):
            target = _string_dispatch_target(node)
            if target is not None and (target == surface or target.startswith(prefix)):
                signals.append(f"import-string:{path.relative_to(root).as_posix()}")
                break
    if any(module == surface or module.startswith(prefix) for module in _entry_point_modules(root)):
        signals.append("entry-point:pyproject.toml")
    return tuple(sorted(set(signals)))


def is_dynamically_reached(surface: str, *, root: Path = _REPO_ROOT) -> bool:
    """True iff *surface* is reachable through any honored dynamic-reach signal."""
    return bool(dynamic_reach_signals(surface, root=root))


# ---------------------------------------------------------------------------
# Status resolution
# ---------------------------------------------------------------------------
def is_known_live(surface: str, *, root: Path = _REPO_ROOT) -> bool:
    """True iff *surface* has a live reason to exist.

    Live means a static importer OR a dynamic-reach signal — the false-positive
    guard: a surface reached only dynamically (importer-count 0) is still live.
    """
    return static_importer_count(surface, root=root) > 0 or is_dynamically_reached(surface, root=root)


def _resolve(surface: str, root: Path) -> Verdict:
    retired = retirement_evidence(surface)
    if retired is not None:
        return Verdict(surface, True, retired)
    if is_known_live(surface, root=root):
        return Verdict(surface, False, "known-live")
    return Verdict(surface, True, "importer-count:0")


def _is_valid_evidence(evidence: str, surface: str, root: Path) -> bool:
    if evidence.startswith("retirement-gate:"):
        return retirement_evidence(surface) is not None
    if evidence.startswith("adr:"):
        return (root / evidence.split(":", 1)[1]).exists()
    if evidence.startswith("importer-count:"):
        return not is_known_live(surface, root=root)
    return False


def validate_entry(entry: CensusEntry, root: Path) -> None:
    """Refuse a ``dead`` entry whose evidence is not valid, independent evidence."""
    if entry.status != "dead":
        return
    if not _is_valid_evidence(entry.evidence, entry.surface, root):
        raise UnevidencedDeadError(f"census surface {entry.surface!r} is marked dead but its evidence {entry.evidence!r} is not independently verifiable")


def is_dead(
    surface: str,
    *,
    root: Path = _REPO_ROOT,
    census: Sequence[CensusEntry] | None = None,
) -> tuple[bool, str]:
    """Return ``(dead, evidence)`` for *surface*, reconciled with the census."""
    entries = _resolve_census(census)
    entry = _entry_for(entries, surface)
    verdict = _resolve(surface, root)
    if entry is not None and entry.status == "dead" and not verdict.dead:
        if is_known_live(surface, root=root):
            raise KnownLiveNotDeadError(
                f"census marks {surface!r} dead but it is known live (reached via {verdict.evidence}); a dynamically-reached, importer-0 surface is never dead"
            )
        raise UnevidencedDeadError(f"census marks {surface!r} dead but the oracle cannot substantiate it (evidence: {verdict.evidence})")
    return verdict.dead, verdict.evidence


def census_dead_surfaces(
    *,
    root: Path = _REPO_ROOT,
    census: Sequence[CensusEntry] | None = None,
) -> tuple[str, ...]:
    """Return the validated census-``dead`` surfaces (non-vacuous, DIR-043)."""
    entries = _resolve_census(census)
    for entry in entries:
        validate_entry(entry, root)
    dead = tuple(entry.surface for entry in entries if entry.status == "dead")
    if not dead:
        raise VacuousCensusError("census evaluated an empty set of dead surfaces (DIR-043)")
    return dead


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------
def _is_test_surface(surface: str) -> bool:
    return surface.split(".")[0] == "tests"


def authorize_drop(
    surface: str,
    *,
    root: Path = _REPO_ROOT,
    census: Sequence[CensusEntry] | None = None,
) -> tuple[bool, str]:
    """Authorize a base-red drop of *surface* — false-negative guard.

    The subject must be a src surface (never a test module); the census must
    record it ``dead``; the src surface must not be live; and the evidence must
    be independently valid. Any failure raises.
    """
    if _is_test_surface(surface):
        raise SubjectNotSrcSurfaceError(
            f"{surface!r} is a test module; the census subject is the src surface under test, never the test file's own (always-zero) importer count"
        )
    entries = _resolve_census(census)
    entry = _entry_for(entries, surface)
    if entry is None or entry.status != "dead":
        raise UnevidencedDeadError(f"{surface!r} is not recorded dead in the census")
    if is_known_live(surface, root=root):
        raise LiveSurfaceNotDroppableError(f"{surface!r} is live (static importer-count > 0); a live regression cannot be dropped as a dead-code test")
    validate_entry(entry, root)
    return True, entry.evidence


def denominator_excluded_surfaces(
    *,
    root: Path = _REPO_ROOT,
    census: Sequence[CensusEntry] | None = None,
) -> tuple[str, ...]:
    """Census-``dead`` surfaces excluded from the coverage denominator.

    The always-on enforcement allowlists are never excluded (C-006 boundary).
    """
    dead = census_dead_surfaces(root=root, census=census)
    return tuple(surface for surface in dead if not is_enforcement_allowlist_gate(surface))


def is_enforcement_allowlist_gate(surface: str) -> bool:
    """True iff *surface* is one of the always-on enforcement allowlists (C-006)."""
    return surface in _ENFORCEMENT_ALLOWLIST_GATES


def _entry_point_modules(root: Path) -> frozenset[str]:
    """Dotted modules named by pyproject ``[project.scripts]`` entry points."""
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return frozenset()
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    scripts = data.get("project", {}).get("scripts", {})
    return frozenset(value.split(":", 1)[0] for value in scripts.values())
