"""2.x package boundary invariants.

These tests enforce the dependency direction documented in
docs/architecture/00_landscape/README.md:

    kernel (root) <- charter <- glossary/runtime/mission_runtime <- specify_cli

A violation here means a package imports from a package it should not.
See ADR 2026-03-27-1 for rationale.

Note (charter-code-topology-01M152G1, S5): the former top-level ``doctrine``
layer was dropped from the landscape. ``src/doctrine`` relocated to
``src/charter/offering`` (S2a); the offering/activation split is an
intra-``charter`` sub-package boundary now, not a separate landscape layer.

---

FR-012 audit verdict (#2548 ratio=1.00 audit, WP01 of mission
content-address-ratchet-allowlists-01KX8M4D — see research.md D-context and
the post-spec adversarial squad classification referenced there):

The post-spec squad classified all thirteen ratio=1.00 architectural tests.
Two of the thirteen (``test_unified_model_resolves_at_new_location`` and
``test_legacy_contract_types_resolve_at_new_location``, both below) were
positive-literal ``__module__ == "..."`` re-pins and were converted to
behavioural assertions by this WP (FR-011). The remaining **ten** were
audited and validated as legitimate KEEP — behavioural, negative, or
import-layer invariants that do not re-pin a literal path — and were left
UNCHANGED:

    test_no_raw_mission_spec_paths
    test_safe_commit_import_boundary
    test_pytest_marker_convention
    test_auth_transport_singleton
    test_status_module_boundary
    test_tid251_enforcement
    test_guard_capability_call_sites
    test_pytest_marker_correctness
    test_charter_facades_reexport_doctrine
    (plus the shared architectural ``conftest`` infra)

This closes the #2548 audit obligation. Do NOT re-open or re-classify these
ten without a fresh audit — see spec.md WS3 (FR-010/FR-011/FR-012).
"""
from __future__ import annotations

import ast
import importlib.util
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pytest
from pytestarch import LayerRule

from specify_cli.contracts.anchoring import enclosing_qualname

pytestmark = pytest.mark.architectural

# ---------------------------------------------------------------------------
# Layer coverage guards (issue #395)
# ---------------------------------------------------------------------------

# Top-level src/ packages intentionally excluded from layer enforcement.
# Add entries here only for transitional / deprecated packages that will be
# removed once migration is complete.  Entries MUST include a comment
# explaining WHY they are excluded and when they can be removed.
# Empty since mission dead-port-disposition-01M1TZVN (FR-013): the last entry,
# `constitution` (the pre-3.x predecessor of `charter`), outlived mission 063's
# rename by which it was retired. `test_layer_exclusions_name_existing_packages`
# keeps every future entry honest.
_EXCLUDED_FROM_LAYER_ENFORCEMENT: frozenset[str] = frozenset()

_SRC = Path(__file__).resolve().parents[2] / "src"

# Layer names as defined in the `landscape` fixture in conftest.py.
# Keep this in sync with that fixture; both lists must agree.
#
# "doctrine" was dropped (charter-code-topology-01M152G1, S5): src/doctrine
# relocated to src/charter/offering (S2a), so the collapsed chain is
# kernel <- charter <- glossary/runtime/mission_runtime <- specify_cli.
_DEFINED_LAYERS: frozenset[str] = frozenset(
    ["kernel", "charter", "glossary", "runtime", "mission_runtime", "specify_cli"]
)

# ---------------------------------------------------------------------------
# WP08 / FR-009 (#2327, WS1): mission_runtime -> specify_cli outbound ledger
# ---------------------------------------------------------------------------
#
# The landscape places ``mission_runtime`` BELOW ``specify_cli``
# (kernel <- ... <- mission_runtime <- specify_cli), so the clean invariant is
# "mission_runtime must NOT import specify_cli". Today ``resolution.py`` (plus a
# single edge in ``artifacts.py``) carry real *lazy, in-function* upward imports
# into the ``specify_cli.*`` subpackages named below.
#
# PRE-DECIDED (research D6, renata-reviewed): these edges are a DOCUMENTED
# allowed-exception set with recorded rationale — they are NOT violations. The
# clean rule ``mission_runtime should_not access specify_cli`` would red on
# existing, working code; converting the edges to hard errors is a carved-out
# FUTURE mission (invert the dependency behind a port — infra/logic separation
# epic #2173). This ledger is therefore bound as an outbound guard, not a purge.
#
# The ledger is bounded by import, stale-entry, and independent size checks:
#   * ADDING a new ``specify_cli.<sub>`` edge outside this set MUST red the rule
#     (loud additions — proven by ``test_rule_rejects_out_of_ledger_import``),
#   * REMOVING an edge (future port work) must delete its entry here; a stale
#     entry with no matching live import reds ``test_ledger_has_no_stale_entries``.
#   * GROWING the ledger alongside an import fails its independent
#     ``mission_runtime_allowed_specify_cli`` cap in ``_baselines.yaml``.
#
# Each entry is a first-level ``specify_cli.<subpackage>`` name, derived from a
# live AST scan of ``src/mission_runtime/`` (do NOT hand-copy from the plan).
_MISSION_RUNTIME_ROOT = _SRC / "mission_runtime"

_MISSION_RUNTIME_ALLOWED_SPECIFY_CLI: frozenset[str] = frozenset(
    {
        "coordination",      # resolution.py: CoordinationWorkspace, surface_resolver
        "core",              # artifacts.py + resolution.py: constants, paths, dependency_graph
        # coord-trust-2841: the "lanes" allow-row (resolution.py's coord-state
        # branch resolving the mid8 disambiguator via
        # ``lanes.branch_naming.resolve_mid8``, GEC-3 / contract C3) is CLOSED.
        # ``resolve_mid8`` (and its heuristic sibling ``mid8_from_slug``) was
        # pure and is now relocated to ``mission_runtime.identity``;
        # ``specify_cli.lanes.branch_naming`` re-exports both verbatim so
        # existing importers are unaffected. resolution.py imports the
        # resolver directly from its new in-layer home — no specify_cli.lanes
        # crossing remains.
        "migration",         # resolution.py: backfill_topology.read_topology
        "mission",           # resolution.py: get_mission_type
        "mission_metadata",  # resolution.py: load_meta
        "missions",          # resolution.py: _read_path_resolver
        # coord-primary-partition-lock WP01 (H-1, binding): the placement seam's
        # RETROSPECTIVE read leg MUST delegate to the SINGLE home authority
        # ``retrospective.writer.resolve_retrospective_home`` (#2119) — computing
        # a second RETROSPECTIVE home in mission_runtime would duplicate that
        # authority and fail its own single-authority guard. This is a sanctioned
        # upward edge, same class as the ``missions`` read-path delegation above.
        "retrospective",     # resolution.py: PlacementSeam.read_dir -> resolve_retrospective_home
        "status",            # resolution.py: Lane, get_wp_lane, read_events, ...
        "task_utils",        # resolution.py: locate_work_package, split_frontmatter
        "workspace",         # resolution.py: resolve_workspace_for_wp
    }
)

# ---------------------------------------------------------------------------
# post-convergence-governance-01M1TMPH / WP03 (#3522): runtime -> specify_cli
# outbound ledger
# ---------------------------------------------------------------------------
#
# The landscape places ``runtime`` BELOW ``specify_cli``
# (kernel <- ... <- runtime <- specify_cli), so a ``runtime -> specify_cli`` import
# is a layer inversion. Before this WP the inversion was UNGATED: ``TestRuntimeBoundary``
# (below) forbids only ``specify_cli.cli`` / ``specify_cli.next``, and the
# runtime<->doctrine gate (``test_runtime_charter_doctrine_boundary.py``) scans only
# the doctrine surface — so a NEW ``runtime -> specify_cli`` edge landed green. Modularity
# SSOT audit (report 11, D5; #3522, also #2986/#3290) measured **93 such edges** across
# **23** first-level ``specify_cli.<sub>`` subpackages.
#
# PRE-DECIDED (mirrors the sibling ``mission_runtime`` ledger, research D6): the clean rule
# ``runtime should_not access specify_cli`` would red on existing, working code, so these
# edges are a DOCUMENTED allowed-exception set. Inverting them (behind ports) is carved-out
# future work (infra/logic epic #2173; #3522). Independent checks bound this ledger:
#   * ADDING a ``specify_cli.<sub>`` edge outside this set MUST red the rule
#     (proven by ``test_rule_rejects_out_of_ledger_import``),
#   * REMOVING an edge (future port work) must delete its entry; a stale entry with no
#     matching live import reds ``test_runtime_ledger_has_no_stale_entries``.
#   * GROWING the ledger alongside a new import fails the independent size cap in
#     ``_baselines.yaml`` / ``test_ratchet_baselines.py``. A stale-entry check alone
#     cannot prevent growth; raising the cap requires a justified baseline edit.
#
# ``specify_cli.cli`` / ``specify_cli.next`` are DELIBERATELY ABSENT — they stay
# hard-forbidden by ``TestRuntimeBoundary``; if runtime ever imported them this ledger would
# red too (belt-and-suspenders). Derived from a live AST scan of ``src/runtime/`` — do NOT
# hand-copy from the plan; re-scan to refresh.
_RUNTIME_ROOT = _SRC / "runtime"

_RUNTIME_ALLOWED_SPECIFY_CLI: frozenset[str] = frozenset(
    {
        "bulk_edit",
        "coordination",
        "core",
        "events",
        "invocation",
        "lanes",
        "migration",
        "mission",
        "mission_loader",
        "mission_metadata",
        "mission_step_contracts",
        "mission_v1",
        "missions",
        "requirement_mapping",
        "retrospective",
        "review",
        "runtime",           # specify_cli.runtime (installed-runtime assets), not the top-level pkg
        "shims",
        "status",
        "status_lanes",
        "task_utils",
        "workspace",
    }
)


def _is_specify_cli_module(module: str) -> bool:
    """True when ``module`` is ``specify_cli`` itself or one of its subpackages."""
    return module == "specify_cli" or module.startswith("specify_cli.")


def _specify_cli_subpackage(module: str) -> str:
    """First-level subpackage of a ``specify_cli`` import.

    ``specify_cli.core.paths`` -> ``"core"``; bare ``specify_cli`` -> ``""``.
    """
    parts = module.split(".")
    return parts[1] if len(parts) > 1 else ""


@dataclass(frozen=True)
class ImportSite:
    """One AST-observed ``specify_cli`` import, site-level.

    ``qualname`` is the innermost enclosing function/class scope (or
    ``"<module>"``), computed via :func:`enclosing_qualname` so a boundary
    violation's failure message can name *where* in the file the offending
    import lives, not just which line.
    """

    rel: str
    lineno: int
    qualname: str
    module: str


_DYNAMIC_IMPORT_CALLABLE_NAMES: frozenset[str] = frozenset({"import_module", "__import__", "find_spec"})


def _pkg_parts(rel: str) -> tuple[str, ...]:
    """The dotted package (as path parts) that *owns* the module at *rel*.

    ``specify_cli/consolidation/git_probes.py`` -> ``("specify_cli", "consolidation")``;
    ``specify_cli/consolidation/__init__.py`` -> ``("specify_cli", "consolidation")`` too (an
    ``__init__`` module's *own* package is one level up from its file name,
    same as any other module's -- both cases drop exactly the last part).
    """
    return Path(rel).with_suffix("").parts[:-1]


def _is_real_submodule(pkg_dotted: str, name: str) -> bool:
    """True when ``<pkg_dotted>/<name>`` exists on disk under ``_SRC`` as a
    module or package (never imports/executes anything — a pure filesystem
    check so this stays safe to run over untrusted/dynamic trees)."""
    if not pkg_dotted:
        return False
    candidate = _SRC.joinpath(*pkg_dotted.split("."), name)
    return candidate.is_dir() or candidate.with_suffix(".py").is_file()


def _resolve_import_from_base(node: ast.ImportFrom, rel: str) -> str:
    """The dotted base module of ``from <base> import ...``, relative-aware.

    ``node.level == 0`` (absolute) returns ``node.module`` verbatim (possibly
    ``""`` for a bare ``from . import x`` — level-0 imports never have that
    shape, so this is effectively always non-empty for level 0). A relative
    import resolves against the *importing file's own package*
    (:func:`_pkg_parts`), walking up one level per ``node.level`` beyond the
    first (mirrors ``research/merge_cli_rule_probe.py``'s ``resolve_from``).
    """
    if node.level == 0:
        return node.module or ""
    pkg = list(_pkg_parts(rel))
    if node.level > 1:
        pkg = pkg[: len(pkg) - (node.level - 1)]
    parts = [*pkg]
    if node.module:
        parts.append(node.module)
    return ".".join(parts)


def _expand_from_targets(base: str, node: ast.ImportFrom) -> list[str]:
    """Modules yielded by ``from base import name, ...``.

    ``base == "specify_cli"`` (the literal bare root) keeps the pre-existing
    EXCLUSIVE per-alias resolution byte-identical to the original collector:
    one entry per alias — the real submodule form (``specify_cli.<alias>``)
    when the alias resolves to a real module/package on disk, else the bare
    root itself. This is what keeps ``TestRuntimeSpecifyCliLedger``'s
    root-member tests (and the mission_runtime/runtime ledgers, verified by a
    live before/after AST diff — research R3 step 6) byte-for-byte unchanged.

    Any OTHER ``specify_cli`` base (``specify_cli.cli``,
    ``specify_cli.cli.commands``, ...) uses the ADDITIVE form instead: the
    base itself, PLUS ``base.alias`` for every alias that resolves to a real
    submodule. This is what lets one
    ``from specify_cli.cli.commands import merge_driver`` site surface as
    BOTH ``specify_cli.cli.commands`` and
    ``specify_cli.cli.commands.merge_driver`` — the two entries
    ``TestMergeCliBoundary`` dedupes back down to one reported finding
    (matching ``research/merge_cli_rule_probe.py``'s additive ``resolve_from``).
    """
    if not base:
        return []
    if base == "specify_cli":
        return [
            f"{base}.{alias.name}" if _is_real_submodule(base, alias.name) else base
            for alias in node.names
        ]
    targets = [base]
    for alias in node.names:
        if _is_real_submodule(base, alias.name):
            targets.append(f"{base}.{alias.name}")
    return targets


def _dynamic_import_target(node: ast.Call) -> str | None:
    """The literal string module argument of a dynamic-import call, if any.

    Matches ``importlib.import_module(...)`` / bare ``import_module(...)``
    (however the name reached scope) / ``__import__(...)`` /
    ``importlib.util.find_spec(...)`` / bare ``find_spec(...)`` — always by
    the call's final attribute/name only, so the fully-qualified spelling
    does not need to be reproduced here. Requires a string-literal first
    argument (a dynamic/computed module name is out of scope — this rule
    catches *static* boundary leaks, not every possible obfuscation) and
    NEVER matches an unrelated call sharing another name (e.g.
    ``logging.getLogger("specify_cli.cli.commands.merge")`` — ``getLogger``
    is not in :data:`_DYNAMIC_IMPORT_CALLABLE_NAMES`).
    """
    func = node.func
    name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
    if name not in _DYNAMIC_IMPORT_CALLABLE_NAMES:
        return None
    if not node.args:
        return None
    first_arg = node.args[0]
    if not (isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str)):
        return None
    return first_arg.value


def _collect_specify_cli_import_sites(root: Path) -> list[ImportSite]:
    """Return every ``specify_cli`` import site under *root*.

    Walks the full AST (so *lazy, in-function* imports are included — the
    ``mission_runtime``/``runtime`` upward edges live inside functions) in
    FOUR forms other collectors have historically missed: module-level,
    function-local, RELATIVE (``from ..cli.commands import x`` —
    :func:`_resolve_import_from_base`), and literal-string dynamic
    (``importlib.import_module("...")`` / ``__import__("...")`` /
    ``importlib.util.find_spec("...")`` — :func:`_dynamic_import_target`).
    A bare string elsewhere (a logger name, a docstring) is never matched —
    only a string that is BOTH a dynamic-import call's first argument AND
    itself a ``specify_cli`` module reaches this list.
    """
    sites: list[ImportSite] = []
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        rel = str(path.relative_to(_SRC))
        for node in ast.walk(tree):
            modules: list[str] = []
            if isinstance(node, ast.ImportFrom):
                base = _resolve_import_from_base(node, rel)
                if _is_specify_cli_module(base):
                    modules = _expand_from_targets(base, node)
            elif isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names if _is_specify_cli_module(alias.name)]
            elif isinstance(node, ast.Call):
                dynamic_target = _dynamic_import_target(node)
                if dynamic_target is not None and _is_specify_cli_module(dynamic_target):
                    modules = [dynamic_target]
            for module in modules:
                sites.append(
                    ImportSite(
                        rel=rel,
                        lineno=node.lineno,
                        qualname=enclosing_qualname(source, node.lineno),
                        module=module,
                    )
                )
    return sites


def _collect_specify_cli_imports(root: Path) -> list[tuple[str, str]]:
    """Return ``(relative_path, imported_module)`` for every specify_cli import.

    A thin projection over :func:`_collect_specify_cli_import_sites` (the
    single-collector authority, C-007) so every consumer
    (``TestRuntimeBoundary``, ``TestMissionRuntimeBoundary``,
    ``TestRuntimeSpecifyCliLedger``) keeps its exact ``(rel, module)``
    signature and, over the real ``runtime``/``mission_runtime`` trees,
    byte-identical results (verified live — no relative/dynamic
    ``specify_cli`` imports exist there today; see
    :func:`_expand_from_targets` for the bare-root resolution rule).
    """
    return [(site.rel, site.module) for site in _collect_specify_cli_import_sites(root)]


def _out_of_ledger_specify_cli_imports(
    imports: Iterable[tuple[str, str]],
    allowed: frozenset[str],
) -> list[str]:
    """Rule matcher: ``"path imports module"`` for edges outside ``allowed``.

    Pure function of its inputs so the negative test can drive it with a
    synthetic out-of-set edge and prove non-vacuity without touching disk.
    """
    return [
        f"{rel} imports {module}"
        for rel, module in imports
        if _specify_cli_subpackage(module) not in allowed
    ]


class TestLayerCoverage:
    """Meta-tests that keep the landscape fixture honest."""

    def test_no_unregistered_src_packages(self) -> None:
        """Every top-level src/ package must have a layer definition.

        When a new package is added to src/ without a corresponding layer,
        architectural boundary rules pass vacuously for it — violations go
        undetected.  Add the package to `_DEFINED_LAYERS` in the landscape
        fixture *and* to this file's `_DEFINED_LAYERS` constant, or add it
        to `_EXCLUDED_FROM_LAYER_ENFORCEMENT` with a documented reason.
        """
        src_packages = {
            p.name
            for p in _SRC.iterdir()
            if p.is_dir()
            and not p.name.startswith("_")
            and (p / "__init__.py").exists()
        }
        unregistered = src_packages - _DEFINED_LAYERS - _EXCLUDED_FROM_LAYER_ENFORCEMENT
        assert not unregistered, (
            f"src/ packages with no architectural layer assignment: "
            f"{sorted(unregistered)!r}.  "
            "Add a layer to tests/architectural/conftest.py or add to "
            "_EXCLUDED_FROM_LAYER_ENFORCEMENT with a documented reason."
        )

    def test_layer_exclusions_name_existing_packages(self) -> None:
        """Every layer-enforcement exclusion must name a package that exists.

        ``_EXCLUDED_FROM_LAYER_ENFORCEMENT`` is a transitional escape hatch: an
        entry for a package that is no longer under ``src/`` is a stale
        exclusion that would silently exempt the package if it were ever
        re-created under that name (mission dead-port-disposition-01M1TZVN,
        FR-013 / SC-008: the ``constitution`` exclusion outlived mission 063).
        """
        stale = sorted(name for name in _EXCLUDED_FROM_LAYER_ENFORCEMENT if not (_SRC / name / "__init__.py").exists())
        assert not stale, (
            f"_EXCLUDED_FROM_LAYER_ENFORCEMENT names packages that do not exist under src/: {stale!r}. "
            "Delete the stale entries; an exclusion for a nonexistent package is a vacuous gate."
        )

    def test_all_defined_layers_match_at_least_one_module(self) -> None:
        """Every defined layer must match at least one importable module.

        If a package is renamed or removed, the layer definition becomes an
        empty set and all its rules pass vacuously.
        """
        empty: list[str] = []
        for layer in sorted(_DEFINED_LAYERS):
            installed = importlib.util.find_spec(layer) is not None
            on_disk = (_SRC / layer / "__init__.py").exists()
            if not installed and not on_disk:
                empty.append(layer)
        assert not empty, (
            f"Layers defined but no matching module found: {empty!r}.  "
            "The boundary rules for these layers would pass vacuously.  "
            "Remove the layer or restore the package."
        )


# --- Invariant 1: kernel is the true root (zero outgoing deps) ---


class TestKernelIsolation:
    """kernel must not import from any other landscape container."""

    def test_kernel_does_not_import_charter(self, evaluable, landscape):
        (
            LayerRule()
            .based_on(landscape)
            .layers_that()
            .are_named("kernel")
            .should_not()
            .access_layers_that()
            .are_named("charter")
        ).assert_applies(evaluable)

    def test_kernel_does_not_import_specify_cli(self, evaluable, landscape):
        (
            LayerRule()
            .based_on(landscape)
            .layers_that()
            .are_named("kernel")
            .should_not()
            .access_layers_that()
            .are_named("specify_cli")
        ).assert_applies(evaluable)


# --- Invariant 2 (retired): "doctrine depends only on kernel" ---
#
# Dropped (charter-code-topology-01M152G1, S5): ``src/doctrine`` relocated
# to ``src/charter/offering`` (S2a) and is no longer a top-level landscape
# layer, so a ``LayerRule`` naming a "doctrine" layer would error against the
# collapsed ``landscape`` fixture (the layer node no longer exists). The
# invariant this class enforced (no upward imports from the former doctrine
# package) is now covered intra-package by
# ``test_charter_offering_does_not_import_activation.py`` plus the ordinary
# ``TestCharterBoundary`` rule below, which already proves the whole
# ``charter`` layer (including ``charter.offering``) does not import
# ``specify_cli``.


# --- Invariant 3: charter boundary ---


class TestCharterBoundary:
    """charter (including the former-doctrine ``charter.offering`` sub-package)
    may import kernel only. No specify_cli imports."""

    def test_charter_does_not_import_specify_cli(self, evaluable, landscape):
        (
            LayerRule()
            .based_on(landscape)
            .layers_that()
            .are_named("charter")
            .should_not()
            .access_layers_that()
            .are_named("specify_cli")
        ).assert_applies(evaluable)


class TestGlossaryBoundary:
    """glossary may import lower layers, but not specify_cli adapters."""

    def test_glossary_does_not_import_specify_cli(self, evaluable, landscape):
        (
            LayerRule()
            .based_on(landscape)
            .layers_that()
            .are_named("glossary")
            .should_not()
            .access_layers_that()
            .are_named("specify_cli")
        ).assert_applies(evaluable)


class TestRuntimeBoundary:
    """runtime owns next-step decisions and must not import CLI presentation."""

    def test_runtime_does_not_import_cli_commands(self) -> None:
        forbidden_prefixes = ("specify_cli.cli", "specify_cli.next")
        offenders = [
            f"{rel} imports {module}"
            for rel, module in _collect_specify_cli_imports(_SRC / "runtime")
            if any(module == prefix or module.startswith(prefix + ".") for prefix in forbidden_prefixes)
        ]
        assert not offenders


# ---------------------------------------------------------------------------
# TestMergeCliBoundary: merge -> cli.commands rule
# ---------------------------------------------------------------------------
#
# ``specify_cli/consolidation/**`` must not import the CLI command layer (the
# upward leak this rule closes). The one sanctioned exception is
# ``specify_cli.cli.console`` — a presentation-only singleton — imported by
# the named ledger below. The same upward leak also exists in
# ``status/doctor.py`` -> ``cli.commands.review`` and
# ``tasks/`` -> ``cli.commands`` (C-008 scope note): those are out of scope
# for this rule.
#
# No ``_baselines.yaml`` row for this ledger (C-002/C-007 deferral): the
# named ledger + its own stale-entry guard below is the shrink-only
# mechanism, mirroring the sibling mission_runtime/runtime ledgers but
# without touching the ratchet-owned baseline file.

_MERGE_ROOT = _SRC / "specify_cli" / "consolidation"

_MERGE_CLI_CONSOLE_IMPORTERS: frozenset[str] = frozenset(
    {
        "specify_cli/consolidation/done_bookkeeping.py",
        "specify_cli/consolidation/mission_number/bake.py",
        "specify_cli/consolidation/forecast.py",
        "specify_cli/consolidation/push_preflight.py",
        "specify_cli/consolidation/git_probes.py",
        "specify_cli/consolidation/preflight.py",
        "specify_cli/consolidation/executor.py",
        "specify_cli/consolidation/coord_strand.py",
        "specify_cli/consolidation/phase_claim.py",
        "specify_cli/consolidation/phase_advance.py",
        "specify_cli/consolidation/phase_bookkeeping.py",
        "specify_cli/consolidation/phase_gate.py",
        "specify_cli/consolidation/phase_teardown.py",
        "specify_cli/consolidation/phase_finalize.py",
        "specify_cli/consolidation/entry_preflight.py",
        "specify_cli/consolidation/resume_recovery.py",
    }
)


def _is_forbidden_merge_cli_import(module: str) -> bool:
    """True for any ``specify_cli.cli``/``specify_cli.cli.*`` module OTHER
    than the one sanctioned exception, ``specify_cli.cli.console`` (a
    presentation-only singleton every merge module may print through)."""
    if module == "specify_cli.cli.console":
        return False
    return module == "specify_cli.cli" or module.startswith("specify_cli.cli.")


def _merge_cli_boundary_offenders(sites: Iterable[ImportSite]) -> list[str]:
    """Format + dedupe offending ``merge -> cli.commands`` sites.

    Deduped per ``(rel, lineno)``: the additive ``_expand_from_targets``
    form deliberately yields MULTIPLE module strings for one physical
    import statement (e.g. both ``specify_cli.cli.commands`` and
    ``specify_cli.cli.commands.merge_driver`` for the single
    ``git_probes.py:667`` statement) so every offending form is caught —
    but a single import statement is still exactly one offending SITE, so
    the reported failure names it once, using its most specific (longest)
    offending module string.
    """
    grouped: dict[tuple[str, int], list[ImportSite]] = {}
    for site in sites:
        if _is_forbidden_merge_cli_import(site.module):
            grouped.setdefault((site.rel, site.lineno), []).append(site)
    offenders: list[str] = []
    for (rel, lineno), grouped_sites in sorted(grouped.items()):
        representative = max(grouped_sites, key=lambda site: len(site.module))
        offenders.append(f"{rel}:{lineno} {representative.qualname} -> {representative.module}")
    return offenders


class TestMergeCliBoundary:
    """``specify_cli/consolidation/**`` must not import the CLI command layer."""

    def test_merge_does_not_import_cli_command_layer(self) -> None:
        """No ``specify_cli/consolidation/**`` module may import the CLI command
        layer; the driver body lives in ``consolidation/drivers.py`` instead."""
        sites = _collect_specify_cli_import_sites(_MERGE_ROOT)
        offenders = _merge_cli_boundary_offenders(sites)
        assert not offenders, (
            "specify_cli/consolidation/** must not import specify_cli.cli / "
            "specify_cli.cli.* other than specify_cli.cli.console — move "
            "the driver body into consolidation/drivers.py instead:\n  " + "\n  ".join(offenders)
        )

    def test_console_importers_within_ledger(self) -> None:
        """Every ``specify_cli.cli.console`` importer is a named, reviewed one."""
        sites = _collect_specify_cli_import_sites(_MERGE_ROOT)
        importers = {site.rel for site in sites if site.module == "specify_cli.cli.console"}
        unlisted = importers - _MERGE_CLI_CONSOLE_IMPORTERS
        assert not unlisted, (
            f"unlisted specify_cli.cli.console importer(s) under specify_cli/consolidation/: "
            f"{sorted(unlisted)!r}. Add them to _MERGE_CLI_CONSOLE_IMPORTERS with a reason."
        )

    def test_console_ledger_has_no_stale_entries(self) -> None:
        """Stale-entry guard: every ledger file must still import console (shrink-only)."""
        sites = _collect_specify_cli_import_sites(_MERGE_ROOT)
        importers = {site.rel for site in sites if site.module == "specify_cli.cli.console"}
        stale = _MERGE_CLI_CONSOLE_IMPORTERS - importers
        assert not stale, (
            f"_MERGE_CLI_CONSOLE_IMPORTERS has stale entries with no live "
            f"specify_cli.cli.console import: {sorted(stale)!r}. Remove them."
        )

    @staticmethod
    def _write_probe_tree(tmp_path: Path) -> tuple[Path, Path]:
        """Build a minimal ``specify_cli/{merge,cli/commands}`` tree under
        *tmp_path* for the self-mutation forms below. Returns
        ``(merge_pkg, probe_path)``."""
        merge_pkg = tmp_path / "specify_cli" / "consolidation"
        merge_pkg.mkdir(parents=True)
        (merge_pkg / "__init__.py").write_text("", encoding="utf-8")
        cli_pkg = tmp_path / "specify_cli" / "cli"
        cli_pkg.mkdir(parents=True)
        (cli_pkg / "__init__.py").write_text("", encoding="utf-8")
        (cli_pkg / "console.py").write_text("console = None\n", encoding="utf-8")
        commands_pkg = cli_pkg / "commands"
        commands_pkg.mkdir()
        (commands_pkg / "__init__.py").write_text("", encoding="utf-8")
        (commands_pkg / "merge_driver.py").write_text("", encoding="utf-8")
        return merge_pkg, merge_pkg / "probe.py"

    @pytest.mark.parametrize("lazy", [False, True], ids=["top-level", "lazy"])
    @pytest.mark.parametrize(
        "statement",
        [
            "import specify_cli.cli.commands.merge_driver",
            "from specify_cli.cli.commands import merge_driver",
            "from specify_cli.cli import commands",
            "from ..cli.commands import merge_driver",
            'importlib.import_module("specify_cli.cli.commands.merge_driver")',
            '__import__("specify_cli.cli.commands")',
        ],
        ids=[
            "import-dotted",
            "from-commands-import-merge-driver",
            "from-cli-import-commands",
            "relative-from-cli-commands",
            "import-module-literal",
            "dunder-import-literal",
        ],
    )
    def test_boundary_catches_every_import_form(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        lazy: bool,
        statement: str,
    ) -> None:
        """Self-mutation (non-vacuity): every documented import shape is caught,
        module-level and function-local alike."""
        merge_pkg, probe_path = self._write_probe_tree(tmp_path)
        header = "import importlib\n" if "importlib." in statement else ""
        source = f"{header}def load():\n    {statement}\n" if lazy else f"{header}{statement}\n"
        probe_path.write_text(source, encoding="utf-8")
        monkeypatch.setattr(sys.modules[__name__], "_SRC", tmp_path)
        sites = _collect_specify_cli_import_sites(merge_pkg)
        offenders = _merge_cli_boundary_offenders(sites)
        assert offenders, f"form {statement!r} (lazy={lazy}) was not caught by the merge -> cli boundary rule"

    @pytest.mark.parametrize("lazy", [False, True], ids=["top-level", "lazy"])
    @pytest.mark.parametrize(
        "statement",
        [
            "from specify_cli.cli.console import console",
            'logging.getLogger("specify_cli.cli.commands.merge")',
        ],
        ids=["console-import", "logger-name-string"],
    )
    def test_boundary_ignores_negative_controls(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        lazy: bool,
        statement: str,
    ) -> None:
        """Negative controls: the console exception and a bare logger-name
        string that happens to look like a forbidden module path — neither
        is a real import and neither must ever be reported."""
        merge_pkg, probe_path = self._write_probe_tree(tmp_path)
        header = "import logging\n" if "getLogger" in statement else ""
        source = f"{header}def load():\n    {statement}\n" if lazy else f"{header}{statement}\n"
        probe_path.write_text(source, encoding="utf-8")
        monkeypatch.setattr(sys.modules[__name__], "_SRC", tmp_path)
        sites = _collect_specify_cli_import_sites(merge_pkg)
        offenders = _merge_cli_boundary_offenders(sites)
        assert not offenders, f"negative control {statement!r} (lazy={lazy}) was wrongly flagged: {offenders!r}"


class TestRefAdvancePlumbingBoundary:
    """NFR-004 ratchet (mission meta-json-fail-closed-routing-01KZPJ1F, WP02).

    ``git/ref_advance.py`` is git plumbing that must import **zero**
    ``specify_cli`` modules (C-003): it is called from the merge pipeline and
    may only depend downward into the kernel. A ``pytestarch`` ``LayerRule``
    cannot express this — ``ref_advance`` lives *inside* the ``specify_cli``
    layer, so a layer rule for that layer cannot forbid a same-layer edge. A
    bespoke AST scan (mirroring :class:`TestRuntimeBoundary`) is the only way to
    ratchet the single-file boundary so the fail-closed routing cannot silently
    regress by re-introducing a ``specify_cli`` import.
    """

    def test_ref_advance_imports_zero_specify_cli(self) -> None:
        ref_advance = _SRC / "specify_cli" / "git" / "ref_advance.py"
        tree = ast.parse(ref_advance.read_text(encoding="utf-8"))
        offenders: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                offenders.extend(
                    alias.name for alias in node.names if _is_specify_cli_module(alias.name)
                )
            elif (
                isinstance(node, ast.ImportFrom)
                and node.module
                and _is_specify_cli_module(node.module)
            ):
                offenders.append(node.module)
        assert not offenders, (
            "git/ref_advance.py must import zero specify_cli modules (C-003 / "
            f"NFR-004); found: {sorted(offenders)!r}. It is git plumbing — route "
            "meta.json decoding through kernel.meta_decode / kernel.vcs_lock, not "
            "back through specify_cli."
        )


# --- Invariant 4: WP01 — unified MissionStep model location ---


def _non_canonical_instances(objs: Iterable[object], canonical: type) -> list[str]:
    """Return a description for every ``obj`` that is not an instance of ``canonical``.

    Pure function of its inputs (FR-011/FR-013) so the plant-and-catch
    negative test can drive it with a synthetic wrong-wiring object and
    prove non-vacuity without touching disk or real resolver state. Used in
    place of literal ``__module__ == "..."`` comparisons: identity/usage
    is what matters, not which module a class happens to report.
    """
    return [
        f"{obj!r} is {type(obj).__module__}.{type(obj).__qualname__}, "
        f"not {canonical.__qualname__}"
        for obj in objs
        if not isinstance(obj, canonical)
    ]


class TestUnifiedMissionStepBoundary:
    """WP01 (mission charter-doctrine-mission-type-configuration-01KSWJVX).

    After the unification, the legacy ``charter.offering.mission_step_contracts``
    subpackage is gone. The unified :class:`MissionStep` model lives at
    ``charter.offering.missions.models``; the legacy step-contract types relocate
    to ``charter.offering.missions.step_contracts``. Charter modules import from
    ``doctrine.*`` directly (allowed: charter sits above doctrine in the
    dependency stack); the runtime layer reaches doctrine artifacts
    through the charter facades whenever possible.
    """

    def test_legacy_subpackage_is_gone(self) -> None:
        """The legacy ``charter.offering.mission_step_contracts`` import path must
        not resolve. WP01 retired this subpackage; any code importing it
        would silently shadow the unified model and reintroduce the
        fragmentation that this WP eliminated.

        We tolerate a leftover ``__pycache__`` directory (pytest may
        recreate the parent on import-error paths even after the source
        files are gone). The invariant the WP enforces is that none of
        the source ``__init__.py`` / ``models.py`` / ``repository.py``
        files exist; the package itself becomes unimportable as a
        consequence.

        Note: ``importlib.util.find_spec`` may return a non-None namespace
        ModuleSpec even when no source files are present (Python namespace
        package behaviour). We therefore rely solely on the source-file
        existence check as the authoritative gate.
        """
        legacy = Path(__file__).resolve().parents[2] / "src" / "charter" / "offering" / "mission_step_contracts"
        forbidden_source_files = ("__init__.py", "models.py", "repository.py")
        present = [name for name in forbidden_source_files if (legacy / name).exists()]
        assert not present, (
            f"Legacy subpackage source files present after WP01: {present}. "
            "Use charter.offering.missions.models.MissionStep (unified) or "
            "charter.offering.missions.step_contracts (legacy contract types) instead."
        )

    def test_unified_model_resolves_at_new_location(self) -> None:
        """The unified :class:`MissionStep` is BOTH importable via its
        public surface AND the exact class the doctrine mission-step
        resolver actually instantiates when parsing on-disk ``step.yaml``
        definitions (FR-011) — not merely a same-named class that happens
        to report a pinned literal ``__module__`` string.

        Behavioural, not literal: this stays GREEN across a relocation that
        keeps the resolver correctly wired, and it REDS if the resolver
        were ever wired to a decoy/duplicate class (see
        ``test_plant_and_catch_wrong_mission_step_wiring`` below).
        """
        from charter.offering.missions.mission_step_repository import MissionStepRepository
        from charter.offering.missions.models import MissionStep

        resolved = MissionStepRepository.default().resolve_all_for_mission_type(
            "software-dev"
        )
        assert resolved, (
            "expected the shipped software-dev built-in mission-steps to "
            "resolve at least one step"
        )
        offenders = _non_canonical_instances(resolved.values(), MissionStep)
        assert not offenders, (
            "the mission-step resolver produced steps that are not "
            f"instances of the canonical MissionStep class: {offenders}"
        )

    def test_legacy_contract_types_resolve_at_new_location(self) -> None:
        """The relocated legacy step-contract types are BOTH importable at
        ``charter.offering.missions.step_contracts`` AND the exact classes the
        shipped ``*.step-contract.yaml`` loader actually instantiates
        (FR-011) — not merely same-named classes at a pinned literal
        module path.
        """
        from charter.offering.missions.step_contracts import (
            DelegatesTo,
            MissionStepContract,
            MissionStepContractRepository,
            MissionStepContractStep,
        )

        repo = MissionStepContractRepository()
        contract = repo.get("implement")
        assert contract is not None, (
            "expected the shipped 'implement' step contract to load"
        )
        assert isinstance(contract, MissionStepContract)

        offenders = _non_canonical_instances(contract.steps, MissionStepContractStep)
        assert not offenders, (
            f"loaded contract.steps produced non-canonical instances: {offenders}"
        )

        delegating_steps = [s for s in contract.steps if s.delegates_to is not None]
        assert delegating_steps, (
            "expected at least one shipped 'implement' step (e.g. 'workspace') "
            "to populate delegates_to — the fixture this test relies on has drifted"
        )
        offenders = _non_canonical_instances(
            (s.delegates_to for s in delegating_steps), DelegatesTo
        )
        assert not offenders, (
            f"loaded delegates_to values are not canonical DelegatesTo "
            f"instances: {offenders}"
        )

    def test_plant_and_catch_wrong_mission_step_wiring(self) -> None:
        """Non-vacuity guard for the two behavioural tests above (FR-013).

        Feeds :func:`_non_canonical_instances` a synthetic decoy object that
        is NOT an instance of the canonical class (simulating a resolver
        accidentally wired to a same-named-but-different class) and asserts
        it is flagged. Without this test, a resolver silently rewired to
        the wrong class could pass the behavioural tests above vacuously.
        """

        class _DecoyMissionStep:
            """Same-named decoy — proves identity/usage checks have teeth."""

        from charter.offering.missions.models import MissionStep

        offenders = _non_canonical_instances([_DecoyMissionStep()], MissionStep)
        assert offenders, (
            "expected the decoy instance to be flagged as non-canonical — "
            "the wrong-wiring self-test has lost its teeth"
        )


# --- Invariant 5: WP08 — mission_runtime outbound boundary (FR-009, #2327) ---


class TestMissionRuntimeBoundary:
    """WP08 / FR-009 (#2327, WS1): bind the mission_runtime -> specify_cli edge.

    ``mission_runtime`` sits BELOW ``specify_cli`` in the landscape, so importing
    upward is a layer inversion. The clean ``should_not access specify_cli`` rule
    (as used by the sibling ``TestCharterBoundary`` / ``TestGlossaryBoundary``
    classes) would red on existing, working code, so — per research D6 — the real
    upward edges are pinned as a named allowed-exception ledger
    (:data:`_MISSION_RUNTIME_ALLOWED_SPECIFY_CLI`). This class binds the
    previously missing outbound rule and proves it is non-vacuous.

    See :data:`_MISSION_RUNTIME_ALLOWED_SPECIFY_CLI` for the full decision record
    and the future-mission carve-out.
    """

    def test_mission_runtime_specify_cli_imports_within_ledger(self) -> None:
        """Every mission_runtime -> specify_cli edge must be in the named ledger.

        Adding a NEW ``specify_cli.<sub>`` import outside the ledger reds here —
        the intended loud signal for the carved-out future dependency-inversion
        work. This is the outbound LayerRule the WP binds.
        """
        offenders = _out_of_ledger_specify_cli_imports(
            _collect_specify_cli_imports(_MISSION_RUNTIME_ROOT),
            _MISSION_RUNTIME_ALLOWED_SPECIFY_CLI,
        )
        assert not offenders, (
            "mission_runtime imports specify_cli subpackages outside the "
            "documented allowed-exception ledger "
            "(_MISSION_RUNTIME_ALLOWED_SPECIFY_CLI):\n  "
            + "\n  ".join(offenders)
            + "\nInvert the dependency (preferred). A sanctioned ledger expansion also "
            "requires a justified independent _baselines.yaml update."
        )

    def test_rule_rejects_out_of_ledger_import(self) -> None:
        """Non-vacuity guard: the matcher MUST flag a synthetic out-of-set edge.

        A rule that silently allowed everything would pass the ledger test above
        vacuously. Here we drive the SAME matcher with a synthetic
        ``specify_cli.cli`` edge (deliberately absent from the ledger) and assert
        it is rejected — proving the rule has teeth. This is the committed,
        CI-selected negative test (module marker ``architectural``; NFR-005/#2034).
        """
        synthetic = [
            ("mission_runtime/resolution.py", "specify_cli.cli.commands.tasks"),
        ]
        offenders = _out_of_ledger_specify_cli_imports(
            synthetic, _MISSION_RUNTIME_ALLOWED_SPECIFY_CLI
        )
        assert offenders == [
            "mission_runtime/resolution.py imports specify_cli.cli.commands.tasks"
        ], "the outbound rule must reject a specify_cli subpackage outside the ledger"

    def test_ledger_has_no_stale_entries(self) -> None:
        """Stale-entry guard: every ledger entry must match a live source edge.

        When future port work removes an upward edge, its ledger entry must be
        deleted too. A stale entry (no matching import under
        ``src/mission_runtime/``) reds here, keeping the exception set honestly
        minimal. Independent baseline comparisons enforce the size cap.
        """
        live_subpackages = {
            _specify_cli_subpackage(module)
            for _, module in _collect_specify_cli_imports(_MISSION_RUNTIME_ROOT)
        }
        stale = _MISSION_RUNTIME_ALLOWED_SPECIFY_CLI - live_subpackages
        assert not stale, (
            f"allowed-exception ledger has entries with no live edge: {sorted(stale)!r}. "
            "Remove them and lower the independent _baselines.yaml cap."
        )


# --- Invariant 6: WP03 — runtime -> specify_cli outbound boundary (#3522) ---


class TestRuntimeSpecifyCliLedger:
    """post-convergence-governance-01M1TMPH / WP03 (#3522): bind runtime -> specify_cli.

    ``runtime`` sits BELOW ``specify_cli`` in the landscape, so importing upward is a
    layer inversion. The clean ``should_not access specify_cli`` rule would red on the 93
    existing, working edges, so — mirroring the sibling ``TestMissionRuntimeBoundary`` — the
    real upward edges are pinned as a named allowed-exception ledger
    (:data:`_RUNTIME_ALLOWED_SPECIFY_CLI`). This class binds the previously-missing outbound
    rule (the #3522 hole: a new runtime->specify_cli edge used to land green) and proves it
    is non-vacuous. Its size is independently capped by ``_baselines.yaml`` and
    ``test_ratchet_baselines.py``. Reuses the same matcher/collector helpers as the
    mission_runtime ledger so the two boundaries stay behaviourally identical.
    """

    @pytest.mark.parametrize("lazy", [False, True], ids=["top-level", "lazy"])
    @pytest.mark.parametrize("subpackage", ["cli", "next", "saas_client"])
    @pytest.mark.parametrize(
        "form",
        [
            "import specify_cli.{subpackage}",
            "import specify_cli.{subpackage} as imported",
            "from specify_cli import {subpackage}",
            "from specify_cli import {subpackage} as imported",
            "from specify_cli.{subpackage} import member as imported",
        ],
    )
    def test_source_import_forms_cannot_bypass_guards(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        lazy: bool,
        subpackage: str,
        form: str,
    ) -> None:
        """Real source must reach both guards through the shared collector."""
        runtime = tmp_path / "runtime"
        runtime.mkdir()
        package = tmp_path / "specify_cli"
        package.mkdir()
        # Exercise both package directories and single-file modules.
        (package / "cli").mkdir()
        (package / "saas_client").mkdir()
        (package / "next.py").write_text("", encoding="utf-8")
        statement = form.format(subpackage=subpackage)
        source = f"def load():\n    {statement}\n" if lazy else f"{statement}\n"
        (runtime / "probe.py").write_text(source, encoding="utf-8")
        monkeypatch.setattr(sys.modules[__name__], "_SRC", tmp_path)
        imports = _collect_specify_cli_imports(runtime)
        expected = f"runtime/probe.py imports specify_cli.{subpackage}"
        assert _out_of_ledger_specify_cli_imports(imports, _RUNTIME_ALLOWED_SPECIFY_CLI) == [expected]
        if subpackage in {"cli", "next"}:
            with pytest.raises(AssertionError, match=f"specify_cli.{subpackage}"):
                TestRuntimeBoundary().test_runtime_does_not_import_cli_commands()

    @pytest.mark.parametrize("lazy", [False, True], ids=["top-level", "lazy"])
    @pytest.mark.parametrize(
        "statement, expected_modules",
        [
            ("import specify_cli", {"specify_cli"}),
            ("import specify_cli as package", {"specify_cli"}),
            (
                "from specify_cli import main as run, __file__, __version__, app, core as c",
                {"specify_cli", "specify_cli.core"},
            ),
        ],
    )
    def test_root_members_are_not_invented_subpackages(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        lazy: bool,
        statement: str,
        expected_modules: set[str],
    ) -> None:
        """Root members stay distinct from subpackages, and the bare root has no ledger entry (WP06).

        ``from specify_cli import core as c`` is an edge to ``specify_cli.core`` (ledgered); a bare
        ``import specify_cli`` or a root attribute is an edge to the root, which the runtime
        no longer imports, so the ledger refuses it.
        """
        runtime = tmp_path / "runtime"
        runtime.mkdir()
        package = tmp_path / "specify_cli"
        package.mkdir()
        (package / "core").mkdir()
        (package / "__init__.py").write_text("__version__ = 'test'\napp = None\ndef main():\n    pass\n", encoding="utf-8")
        source = f"def load():\n    {statement}\n" if lazy else f"{statement}\n"
        (runtime / "probe.py").write_text(source, encoding="utf-8")
        monkeypatch.setattr(sys.modules[__name__], "_SRC", tmp_path)
        imports = _collect_specify_cli_imports(runtime)
        assert {module for _, module in imports} == expected_modules
        assert {edge.split(" imports ")[1] for edge in _out_of_ledger_specify_cli_imports(imports, _RUNTIME_ALLOWED_SPECIFY_CLI)} == {"specify_cli"}

    def test_runtime_specify_cli_imports_within_ledger(self) -> None:
        """Every runtime -> specify_cli edge must be in the named ledger.

        Adding a NEW ``specify_cli.<sub>`` import outside the ledger reds here — the intended
        loud signal for the carved-out dependency-inversion work (#2173). This is the
        outbound rule the WP binds; before it, the edge was ungated (#3522).
        """
        offenders = _out_of_ledger_specify_cli_imports(
            _collect_specify_cli_imports(_RUNTIME_ROOT),
            _RUNTIME_ALLOWED_SPECIFY_CLI,
        )
        assert not offenders, (
            "runtime imports specify_cli subpackages outside the documented "
            "allowed-exception ledger (_RUNTIME_ALLOWED_SPECIFY_CLI):\n  "
            + "\n  ".join(offenders)
            + "\nInvert the dependency (preferred). A sanctioned ledger expansion also "
            "requires a justified independent _baselines.yaml update. Note: specify_cli.cli / "
            "specify_cli.next are hard-forbidden (TestRuntimeBoundary) and must NOT be added."
        )

    def test_rule_rejects_out_of_ledger_import(self) -> None:
        """Non-vacuity guard: the matcher MUST flag a synthetic out-of-set edge.

        Drives the SAME matcher with a synthetic ``specify_cli.cli`` edge (deliberately
        absent from the ledger, and additionally hard-forbidden) and asserts it is rejected,
        proving the rule has teeth. Committed CI-selected negative test.
        """
        synthetic = [
            ("runtime/next/runtime_bridge.py", "specify_cli.cli.commands.tasks"),
        ]
        offenders = _out_of_ledger_specify_cli_imports(
            synthetic, _RUNTIME_ALLOWED_SPECIFY_CLI
        )
        assert offenders == [
            "runtime/next/runtime_bridge.py imports specify_cli.cli.commands.tasks"
        ], "the outbound rule must reject a specify_cli subpackage outside the ledger"

    def test_runtime_ledger_has_no_stale_entries(self) -> None:
        """Stale-entry guard: every ledger entry must match a live source edge.

        When future port work removes an upward edge, its ledger entry must be deleted too.
        A stale entry (no matching import under ``src/runtime/``) reds here, keeping the
        exception set minimal. Independent baseline comparisons enforce the size cap.
        """
        live_subpackages = {
            _specify_cli_subpackage(module)
            for _, module in _collect_specify_cli_imports(_RUNTIME_ROOT)
        }
        stale = _RUNTIME_ALLOWED_SPECIFY_CLI - live_subpackages
        assert not stale, (
            f"allowed-exception ledger has entries with no live edge: {sorted(stale)!r}. "
            "Remove them and lower the independent _baselines.yaml cap."
        )
