"""Gate 3 (FR-003/FR-007, WP09): no module outside ``src/charter/**`` or
``src/charter/offering/**`` imports ``charter.offering.resolver`` directly.

Mission ``charter-sole-door-bypass-closure-01KZ3WAA``, WP09 / T039. Third of the
three mission-wide durability gates this work package ships.

**This gate is a forward-looking regression guard, NOT proof of a closure.**
The WP09 prompt is explicit about this, and so is the post-tasks squad
correction that produced it: an earlier draft claimed "WP05 closed the one real
consumer", which is false — *nothing* outside ``src/charter/**`` ever imported
``charter.offering.resolver``. There was no violation to close, so this module must not
be read, cited, or summarised as evidence that this mission eliminated a bypass.
What it does is make the currently-clean state *durable*: the moment a future
consumer starts reaching around
:class:`charter.activation.resolver.DoctrineService` into ``charter.offering.resolver``'s tier
functions, this test reds.

Why the boundary matters
------------------------
``doctrine/resolver.py`` owns the 5-tier resolution chain (OVERRIDE > LEGACY >
GLOBAL_MISSION > GLOBAL > PACKAGE_DEFAULT) plus ``resolve_mission``. The mission
contract (``contracts/charter-doctrine-service-contract.md``) pins that every
tier and the mission-config resolution "remains reachable ONLY via a method on
[``charter.activation.resolver.DoctrineService``] from outside ``src/charter/**``".
``doctrine/resolver.py``'s functions are the implementation those methods
delegate to. A direct import from a consumer re-opens exactly the second,
ungated resolution path FR-003 exists to prevent — ``charter/resolver.py``'s own
comment marks its import as "the ONLY import of ``charter.offering.resolver``'s tier
functions".

Consumers that need the resolution *types* (``ResolutionResult`` /
``ResolutionTier``) already have a sanctioned route: the
``charter.resolution`` facade, which re-exports them by identity (proven by
``test_charter_facades_reexport_doctrine.py``). ``specify_cli/runtime/resolver.py``
is the live example, and its module docstring records why identity-preserving
re-export matters (~30 CI failures when a duplicate enum existed). So the
zero-tolerance stance costs a consumer nothing.

Zero-tolerance, no exclusions
-----------------------------
There is no allow-list (C-002) and none is expected: the live census outside the
two owning layers is empty. Adding an entry here to green a new violation is a
policy change, not a fix — route the consumer through
``charter.activation.resolver.DoctrineService`` or the ``charter.resolution`` facade
instead.

Why this is not a duplicate of ``test_runtime_charter_doctrine_boundary.py``
----------------------------------------------------------------------------
That gate is deliberately narrower on all three axes, and the WP09 prompt
directs not re-asserting what an adjacent gate already proves:

* **Scope** — it audits ``src/specify_cli/**`` and ``src/runtime/**``;
  this one audits *all* of ``src/`` outside the two owning layers.
* **Depth** — its ``_module_imports_doctrine_directly`` inspects **module-level**
  imports only (its own docstring says so). This gate walks every scope, so a
  function-local or ``try``/``except``-nested import is caught. spec.md FR-001
  notes that same module-level-only limitation is why the "boundary ratchet"
  concern at the ``tasks_status_cmd.py`` sites was a red herring — the real
  violations in this codebase are function-local.
* **Tolerance** — it carries a shrink-only allow-list of pre-existing sites;
  this gate has none.
* **Target** — it bans ``doctrine.*`` broadly for runtime modules; this one bans
  the single ``charter.offering.resolver`` module for everyone, including
  ``specify_cli`` modules that the other gate does not audit at all.

A5 fix: ``from package import module`` also binds the guarded module
------------------------------------------------------------------------
Adversarial-review injection probes measured this gate at a 4/9 real catch
rate. The dominant miss: ``from charter.offering import resolver`` — in all three
spellings (plain, aliased, function-local) — fully evaded the ban. For an
``ast.ImportFrom`` the detector tested only ``node.module`` (``"doctrine"``);
it never tried ``node.module + "." + alias.name``. But ``from charter.offering import
resolver`` binds the IDENTICAL module object as ``import charter.offering.resolver``,
and ``resolver.resolve_template(...)`` then re-opens the exact ungated second
resolution path this gate exists to forbid. :func:`scan_file_resolver_imports`
now extends its candidate dotted-name list with the package-qualified form for
every ``ImportFrom`` name, closing all three spellings in one change (see
:func:`test_injected_from_package_import_module_is_flagged` and
:func:`test_injected_aliased_from_package_import_is_flagged`).
"""

from __future__ import annotations

import ast
import functools
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.architectural._ast_scan import read_and_parse
from tests.architectural._sole_door_scan import (
    SRC_ROOT,
    iter_source_files,
    rel_to_repo,
)

pytestmark = pytest.mark.architectural

#: The guarded module. ``charter.offering.resolver`` itself and its submodules.
GUARDED_MODULE = "charter.offering.resolver"

#: The two layers entitled to import it: the charter layer (which owns the sole
#: door and its facades) and the doctrine layer (which owns the module).
#: Directory-prefix keyed, never per-file and never per-line.
OWNING_LAYER_PREFIXES = ("src/charter/", "src/charter/offering/")

#: The sanctioned route for a consumer that needs the resolution *types*.
FACADE_MODULE = "charter.resolution"


@dataclass(frozen=True)
class ResolverImportSite:
    """One direct import of ``charter.offering.resolver`` outside the owning layers."""

    rel_path: str
    qualname: str
    lineno: int
    statement: str

    def describe(self) -> str:
        return f"{self.rel_path}:{self.lineno} ({self.qualname}) {self.statement}"


def _targets_guarded_module(dotted: str) -> bool:
    """True for ``charter.offering.resolver`` itself or anything beneath it."""
    return dotted == GUARDED_MODULE or dotted.startswith(f"{GUARDED_MODULE}.")


def _qualname_map(tree: ast.Module) -> dict[int, str]:
    """``id(node) -> enclosing dotted qualname`` for every node in *tree*.

    Built by descent rather than by line lookup so a nested ``def``/``class``
    inside a ``try`` block still resolves to its true qualname.
    """
    out: dict[int, str] = {}

    def _walk(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                child_prefix = f"{prefix}.{child.name}" if prefix else child.name
                out[id(child)] = child_prefix
                _walk(child, child_prefix)
            else:
                out[id(child)] = prefix or "<module>"
                _walk(child, prefix)

    _walk(tree, "")
    return out


def scan_file_resolver_imports(path: Path, rel_path: str) -> list[ResolverImportSite]:
    """Every direct ``charter.offering.resolver`` import in one file, at any scope.

    Walks the whole AST, so ``from charter.offering.resolver import X`` and
    ``import charter.offering.resolver`` are caught at module level, inside a function
    body, and inside a nested ``try``/``except`` — the three scopes the real
    imports in this codebase actually use. Relative imports (``level > 0``) are
    skipped: they can never name the absolute ``charter.offering.resolver`` module.
    """
    source, tree = read_and_parse(path, display=rel_path)

    qualnames = _qualname_map(tree)
    lines = source.splitlines()
    found: list[ResolverImportSite] = []
    for node in ast.walk(tree):
        dotted_names: list[str] = []
        if isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                dotted_names.append(node.module)
                # A5 fix: ``from charter.offering import resolver`` binds the
                # identical module object as ``import charter.offering.resolver`` —
                # node.module alone ("doctrine") never matches the guarded
                # "charter.offering.resolver" target, so the imported NAME must also
                # be tried as a dotted extension of the package it came from.
                dotted_names.extend(f"{node.module}.{alias.name}" for alias in node.names)
        elif isinstance(node, ast.Import):
            dotted_names.extend(alias.name for alias in node.names)
        else:
            continue
        if not any(_targets_guarded_module(name) for name in dotted_names):
            continue
        statement = lines[node.lineno - 1].strip() if node.lineno <= len(lines) else ""
        found.append(
            ResolverImportSite(
                rel_path,
                qualnames.get(id(node), "<module>"),
                node.lineno,
                statement,
            )
        )
    return found


def in_owning_layer(rel_path: str) -> bool:
    return rel_path.startswith(OWNING_LAYER_PREFIXES)


@functools.cache
def resolver_import_census() -> tuple[tuple[ResolverImportSite, ...], ...]:
    """``(outside_owning_layers, inside_owning_layers)`` import censuses.

    Memoised for the test session; a pure function of an unchanging tree.
    """
    outside: list[ResolverImportSite] = []
    inside: list[ResolverImportSite] = []
    for path in iter_source_files(SRC_ROOT):
        rel_path = rel_to_repo(path)
        bucket = inside if in_owning_layer(rel_path) else outside
        bucket.extend(scan_file_resolver_imports(path, rel_path))
    return tuple(outside), tuple(inside)


def check_resolver_import_gate(sites: tuple[ResolverImportSite, ...]) -> list[str]:
    """Violations — zero-tolerance, no allow-list of any kind (C-002)."""
    return [
        f"{site.describe()} imports {GUARDED_MODULE} directly from outside "
        f"src/charter/** and src/charter/offering/** — reach the 5 resolver tiers "
        f"through a charter.activation.resolver.DoctrineService method, or import the "
        f"resolution types from the {FACADE_MODULE} facade"
        for site in sites
    ]


# =========================================================================== #
# Anti-vacuity: the walker really scans the tree and really sees real imports
# =========================================================================== #


def test_detector_finds_the_real_sanctioned_imports() -> None:
    """The owning layers DO import ``charter.offering.resolver`` — the detector sees them.

    Without this, a detector that silently matched nothing at all would make the
    zero-violation assertion below meaningless. ``charter/resolver.py`` carries
    the mission's one sanctioned tier-function import and ``charter/resolution.py``
    the facade type re-export, so both must appear in the inside-layer census.
    """
    _, inside = resolver_import_census()
    inside_files = {site.rel_path for site in inside}
    assert "src/charter/activation/resolver.py" in inside_files, sorted(inside_files)
    assert "src/charter/resolution.py" in inside_files, sorted(inside_files)


# =========================================================================== #
# The gate
# =========================================================================== #


def test_no_direct_doctrine_resolver_import_outside_the_owning_layers() -> None:
    """Zero-tolerance forward-looking guard — no allow-list (C-002).

    Reminder for anyone citing this test: it proves the boundary is *currently*
    clean and stays clean, NOT that this mission closed a violation here. There
    was never one to close (see module docstring).
    """
    outside, _ = resolver_import_census()
    violations = check_resolver_import_gate(outside)
    assert violations == [], "\n".join(violations)


# =========================================================================== #
# NFR-003 self-mutation proofs — function-local and nested scope injection.
# =========================================================================== #


def _scratch(tmp_path: Path, rel_path: str, source: str) -> list[ResolverImportSite]:
    module = tmp_path / Path(rel_path).name
    module.write_text(source, encoding="utf-8")
    return scan_file_resolver_imports(module, rel_path)


def test_injected_function_local_import_is_flagged(tmp_path: Path) -> None:
    """A **function-local** direct import is caught, naming the exact site.

    Injected at function-local scope specifically (NFR-003): a module-level-only
    detector would pass this vacuously, which is precisely the limitation the
    adjacent ``test_runtime_charter_doctrine_boundary.py`` has and this gate must
    not.
    """
    sites = _scratch(
        tmp_path,
        "src/specify_cli/regressed_local.py",
        "def resolve(mission):\n    from charter.offering.resolver import resolve_template\n\n    return resolve_template(mission)\n",
    )
    assert [s.qualname for s in sites] == ["resolve"], [s.describe() for s in sites]
    assert sites[0].qualname == "resolve"
    assert sites[0].lineno == 2
    violations = check_resolver_import_gate(tuple(sites))
    assert violations
    assert "regressed_local.py" in violations[0]
    assert "resolve" in violations[0]


def test_detector_ignores_the_sanctioned_facade_import(tmp_path: Path) -> None:
    """True negative: importing from ``charter.resolution`` is never flagged."""
    sites = _scratch(
        tmp_path,
        "src/specify_cli/compliant_consumer.py",
        "from charter.resolution import ResolutionResult, ResolutionTier\n\n\ndef resolve(service, mission):\n    return service.resolve_mission(mission)\n",
    )
    assert sites == []
