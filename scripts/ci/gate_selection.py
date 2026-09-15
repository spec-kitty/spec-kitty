"""Single gate-selection authority (FR-016 / #2476).

This module is the one authority for "which shards/gates does a changed-path set
select". It **parses** the two hand-authored routing authorities straight out of
the on-disk ``.github/workflows/ci-router.yml``:

1. the dorny ``changes`` filter block — ``group -> globs[]`` (path -> group), and
2. the job ``if: needs.changes.outputs.<group>`` gates — group -> job.

It never re-encodes the routing as a second hand-maintained map: that duplication
is the very #2476 hazard this module exists to close. It is reused by CI routing,
the WP17 completeness oracle, and WP18 local pre-PR parity — one parser, one
answer, no drift.

Public API:
    ``load_router(path=None) -> Router``   parse the two authorities.
    ``select_gates(changed_paths, *, router=None, mode="pr") -> GateSelection``
                                            answer the selection question.
"""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "DEFAULT_REGISTRY_PATH",
    "DEFAULT_ROUTER_PATH",
    "PROBE_GROUPS",
    "GateSelection",
    "Router",
    "load_router",
    "select_gates",
    "select_modules",
]

_REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ROUTER_PATH = _REPO_ROOT / ".github" / "workflows" / "ci-router.yml"
DEFAULT_REGISTRY_PATH = _REPO_ROOT / ".github" / "ci-module-registry.yml"

# The ``any_src`` filter row is the FR-004 fail-closed PROBE (matches any
# ``src/**``), consumed only by the router's ``unmatched`` step. It is never a
# routing group and is never gated on a job (contract Invariant 1).
PROBE_GROUPS = frozenset({"any_src"})

_GROUP_REF = re.compile(r"needs\.changes\.outputs\.([A-Za-z0-9_]+)")


@dataclass(frozen=True)
class Router:
    """The two parsed routing authorities of ``ci-router.yml``.

    ``filters`` is authority 1 (path -> group); ``job_gates`` is authority 2
    (job -> the groups its ``if:`` references). Everything else below is derived.
    """

    filters: dict[str, tuple[str, ...]]
    job_gates: dict[str, frozenset[str]]

    @property
    def routing_groups(self) -> frozenset[str]:
        """Every filter group except the fail-closed probe."""
        return frozenset(group for group in self.filters if group not in PROBE_GROUPS)

    @property
    def src_backed_groups(self) -> frozenset[str]:
        """Routing groups carrying at least one ``src/`` glob (code, not data)."""
        return frozenset(group for group in self.routing_groups if any(glob.startswith("src/") for glob in self.filters[group]))

    @property
    def always_on_jobs(self) -> frozenset[str]:
        """Jobs with no filter-group gate — they run unconditionally."""
        return frozenset(job for job, groups in self.job_gates.items() if not groups)

    @property
    def code_shard_jobs(self) -> frozenset[str]:
        """Gated jobs whose ``if:`` references at least one src-backed group."""
        src = self.src_backed_groups
        return frozenset(job for job, groups in self.job_gates.items() if groups & src)


@dataclass(frozen=True)
class GateSelection:
    """The answer to "what does this diff select", derived from the two authorities."""

    matched_groups: frozenset[str]
    unmatched_src: bool
    selected_jobs: frozenset[str]
    selected_code_shards: frozenset[str]


def _dorny_filters(workflow: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    changes = workflow["jobs"]["changes"]
    for step in changes["steps"]:
        if "dorny/paths-filter" in str(step.get("uses", "")):
            raw = step["with"]["filters"]
            parsed = yaml.safe_load(raw) if isinstance(raw, str) else raw
            return {group: tuple(str(g) for g in (globs or ())) for group, globs in parsed.items()}
    raise ValueError("ci-router.yml `changes` job has no dorny/paths-filter step")


def _job_gates(workflow: dict[str, Any]) -> dict[str, frozenset[str]]:
    gates: dict[str, frozenset[str]] = {}
    for name, job in workflow["jobs"].items():
        if name == "changes" or not isinstance(job, dict):
            continue
        condition = job.get("if")
        gates[name] = frozenset(_GROUP_REF.findall(str(condition))) if condition else frozenset()
    return gates


def load_router(path: Path | None = None) -> Router:
    """Parse the two routing authorities out of ``ci-router.yml``."""
    workflow = yaml.safe_load((path or DEFAULT_ROUTER_PATH).read_text(encoding="utf-8"))
    return Router(filters=_dorny_filters(workflow), job_gates=_job_gates(workflow))


def _match_groups(paths: list[str], router: Router) -> frozenset[str]:
    hit: set[str] = set()
    for group, globs in router.filters.items():
        if group in PROBE_GROUPS:
            continue
        if any(fnmatch.fnmatch(path, pattern) for pattern in globs for path in paths):
            hit.add(group)
    return frozenset(hit)


def select_gates(
    changed_paths: Iterable[str | Path],
    *,
    router: Router | None = None,
    mode: str = "pr",
) -> GateSelection:
    """Return which jobs / code shards a changed-path set selects.

    ``mode="full"`` (or an unmapped ``src/**`` change — the FR-004 fail-closed
    catch-all) forces run-all: every routing group is selected. Otherwise only
    the groups the paths matched are selected. Always-on jobs (no filter group)
    are always included; ``selected_code_shards`` is the src-backed subset.
    """
    router = router or load_router()
    paths = [str(path) for path in changed_paths]
    matched = _match_groups(paths, router)

    any_src = any(path.startswith("src/") for path in paths)
    unmatched_src = any_src and not (matched & router.src_backed_groups)

    run_all = mode == "full" or unmatched_src
    selected_groups = router.routing_groups if run_all else matched

    gated_selected = frozenset(job for job, groups in router.job_gates.items() if groups and (groups & selected_groups))
    return GateSelection(
        matched_groups=matched,
        unmatched_src=unmatched_src,
        selected_jobs=router.always_on_jobs | gated_selected,
        selected_code_shards=gated_selected & router.code_shard_jobs,
    )


def _registry_rows(path: Path | None = None) -> list[dict[str, Any]]:
    """The ``modules[]`` rows from ``.github/ci-module-registry.yml`` (WP08).

    The registry is the single data source for the module set; reading its
    inventory (``module`` names, ``roots``, ``test_dirs``) here is not a second
    routing map (the #2476 hazard is re-encoding the path->group filter, which
    this does not do — src routing still comes from the parsed router)."""
    registry = yaml.safe_load((path or DEFAULT_REGISTRY_PATH).read_text(encoding="utf-8"))
    return [dict(row) for row in registry["modules"]]


def _registry_module_names(path: Path | None = None) -> frozenset[str]:
    """The module inventory (``modules[].module``) from the registry."""
    return frozenset(str(row["module"]) for row in _registry_rows(path))


def _within(path: str, directory: str) -> bool:
    """Whether ``path`` is ``directory`` itself or a descendant of it."""
    directory = directory.rstrip("/")
    return path == directory or path.startswith(f"{directory}/")


def _canonical_test_mirror(root: str) -> str:
    """The canonical ``tests/`` mirror directory of a registry ``roots`` glob.

    Deterministic transform (the "canonical test mirror"): the mirror of a
    directory glob ``<prefix>/<leaf>/**`` is ``tests/<leaf>``; the mirror of a
    single-file root ``<prefix>/<name>.py`` is ``tests/<name>``. This is how a
    module *without* an explicit ``test_dirs`` declares its test tree — the
    authority stays the registry (its own ``roots``), never a hand-authored
    test-dir->module table (the #2476 hazard).
    """
    root = root.rstrip("/")
    if root.endswith("/**"):
        leaf = root[:-3].rstrip("/").rsplit("/", 1)[-1]
        return f"tests/{leaf}"
    name = root.rsplit("/", 1)[-1]
    stem = name.split("*", 1)[0].rsplit(".", 1)[0]
    return f"tests/{stem}"


def _probe_path(root: str) -> str:
    """A representative concrete path under a registry ``roots`` glob.

    The probe is fed back through the parsed router (:func:`select_gates`) so
    the src-routing answer for a test tree is computed by the ONE routing
    authority, not re-derived here. A directory glob yields a file under it; a
    single-file root yields the file itself.
    """
    root = root.rstrip("/")
    if root.endswith("/**"):
        return f"{root[:-3].rstrip('/')}/__ci_probe__.py"
    return root


def _modules_for_test_paths(
    paths: list[str],
    *,
    router: Router,
    registry_path: Path | None,
    modules: frozenset[str],
) -> frozenset[str]:
    """Modules a tests-only change selects, derived from the registry (#4454).

    ``select_gates`` only matches ``src/`` (and other router) globs, so a diff
    confined to ``tests/<dir>/**`` matches no routing group and selects nothing
    — a false green (the test files run in no per-PR shard). This maps each
    changed test path back to its owning module(s) using the registry, then
    mirrors that back to the SAME module set the corresponding src change would
    select, so a tests-only diff is never narrowed relative to its src twin:

    * **explicit ``test_dirs``** — a module that declares its test directories
      owns any changed path within them (preferred, per the registry);
    * **canonical mirror** — every module ``root`` also declares its test tree
      via :func:`_canonical_test_mirror`, so a module without explicit
      ``test_dirs`` still owns ``tests/<leaf>`` for each ``src/<...>/<leaf>/**``
      root. The matched roots are probed through the router (:func:`select_gates`)
      so the resulting module set equals the src change's set exactly.

    A test path with no derivable owning module contributes nothing (it falls
    through to the caller's src/full behavior) — no module is fabricated.
    """
    test_paths = [path for path in paths if _within(path, "tests")]
    if not test_paths:
        return frozenset()

    owners: set[str] = set()
    probes: set[str] = set()
    for row in _registry_rows(registry_path):
        name = str(row["module"])
        for test_dir in row.get("test_dirs") or ():
            if any(_within(path, str(test_dir)) for path in test_paths):
                owners.add(name)
        for root in row.get("roots") or ():
            mirror = _canonical_test_mirror(str(root))
            if any(_within(path, mirror) for path in test_paths):
                probes.add(_probe_path(str(root)))

    if probes:
        mirrored = select_gates(sorted(probes), router=router).matched_groups & modules
        owners |= mirrored
    return frozenset(owners & modules)


def select_modules(
    changed_paths: Iterable[str | Path],
    *,
    router: Router | None = None,
    registry_path: Path | None = None,
    mode: str = "pr",
) -> frozenset[str]:
    """Return which module-registry rows (``.github/ci-module-registry.yml``
    ``modules[].module``) a changed-path set selects.

    The module universe is the registry's own ``modules[].module`` set — NOT
    ``router.src_backed_groups``. Most registry modules are 1:1 with a
    src-backed routing group, but spec-kitty#4386 added the ``ci`` module,
    whose routing group (``scripts/ci/**`` + ``.github/workflows/**``) carries
    no ``src/`` glob and so is NOT src-backed. Intersecting against
    ``src_backed_groups`` would therefore silently drop the ``ci`` module on
    every scoped PR (including one that changes CI infra — the exact diff that
    should run ``tests/ci``). We intersect the router's matched groups against
    the registry inventory instead. Routing still comes from the parsed router
    via :func:`select_gates` — the registry supplies only the module list, so
    no second path->group map is introduced (the #2476 hazard stays closed).
    ``docs``/``corpus``/``e2e`` are non-src routing groups with no registry
    row and are excluded by the intersection.

    ``mode="full"`` or a fail-closed unmatched ``src/**`` diff (FR-004) selects
    every module — run-all, never a silent narrowing of the matrix. Otherwise
    only the matched groups that are registry modules are selected (a docs-only
    diff selects zero modules; overlapping glob ownership between groups, e.g.
    ``core_misc``/``unit``/``execution_context`` each also owning
    ``src/specify_cli/status/**``, is preserved exactly as the router already
    encodes it — never narrowed to a single "owning" module).

    A diff confined to ``tests/<dir>/**`` matches no router glob and would
    otherwise select nothing (spec-kitty#4454 — the test files run in no per-PR
    shard, a false green). Such paths are mapped back to their owning modules
    from the registry (:func:`_modules_for_test_paths`) and unioned in, so a
    tests-only diff selects the SAME module set the corresponding src change
    selects (mirror, never narrow).
    """
    router = router or load_router()
    modules = _registry_module_names(registry_path)
    paths = [str(path) for path in changed_paths]
    selection = select_gates(paths, router=router, mode=mode)
    if mode == "full" or selection.unmatched_src:
        return modules
    src_selected = selection.matched_groups & modules
    test_selected = _modules_for_test_paths(paths, router=router, registry_path=registry_path, modules=modules)
    return src_selected | test_selected
