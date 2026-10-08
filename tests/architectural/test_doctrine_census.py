"""Doctrine reach-through census gate (mission doctrine-public-api-surface, WP01).

This module is the **authoritative, machine-readable disposition manifest** for the
doctrine public-API-surface mission. It is deliberately self-contained: WP02's
INTERNAL-negative test and WP04's lazy-import ratchet baseline import the constants
below directly rather than re-deriving a classification (or re-reading prose from
``data-model.md`` that can silently drift from what the tests enforce)::

    from tests.architectural.test_doctrine_census import (
        DISPOSITION,
        EXEMPT_MANAGEMENT_SURFACE,
        TICKETED_BASELINE,
        reached_doctrine_paths,
    )

The census is **re-run against the live tree** on every invocation (an AST sweep of
the ``_SCAN_ROOTS`` — ``src/specify_cli/`` and, since the #3522 widening,
``src/runtime/``; no subpackage is exempt since mission
``charter-pack-cutover-01M491G6`` WP05 deleted the former management package
rather than moving its exemption, NFR-002) — the disposition table is not trusted from a stale snapshot. A newly
reach-through-ed, undoored doctrine path therefore fails CI (FR-002 / SC-002).

Census numbers, re-measured on this tip (post WP05–WP07 migration + the #3522
``src/runtime`` widening) via ``reached_doctrine_paths()`` — the same live scan the
gate runs on every invocation:

* module-level direct ``from charter.offering …`` imports (``ImportFrom.level == 0``): **0**
* lazy (function-body) direct doctrine imports: **6 files / 11 reaches**
* distinct doctrine module-paths reached (non-TYPE_CHECKING): **10**

(The pre-widening prose claimed 4 files / 5 reaches — a stale-spelling artifact:
the census matcher recognized only the legacy ``doctrine.*`` name after the
``charter.offering`` relocation, so the live scan was returning EMPTY and the
gates below passed vacuously. Fixed together with the #3522 widening.)

(Earlier snapshots recorded 29 files / 54 lines / 23 paths before the WP05–WP07
migration, and 34 files / 70 lines / 26 paths at planning time — both superseded.
The gate re-censuses the live tree every run, so it, not this prose, is the
authority; reproduce the numbers above with ``reached_doctrine_paths()``.)

See ``kitty-specs/doctrine-public-api-surface-01KZPDSR/data-model.md`` for the finalized
per-symbol disposition table and the management-surface / C-007-mission notes.
"""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from tests.architectural._ast_scan import parse_file

pytestmark = [pytest.mark.architectural]


# ---------------------------------------------------------------------------
# Repository anchors
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
# Census roots are an EXPLICIT LIST (#3522): ``src/runtime`` joins the sweep so
# a doctrine reach-through there is censused and disposition-checked exactly
# like a ``specify_cli`` reach (it was silently unscanned before the widening).
_SCAN_ROOTS: tuple[Path, ...] = (
    _REPO_ROOT / "src" / "specify_cli",
    _REPO_ROOT / "src" / "runtime",
)
_MISSION_TASKS = _REPO_ROOT / "kitty-specs" / "doctrine-public-api-surface-01KZPDSR" / "tasks"

# ---------------------------------------------------------------------------
# Manifest — the machine-readable disposition surface (imported by WP02 / WP04)
# ---------------------------------------------------------------------------

#: The inbound-only *management surface*: runtime locations permitted to import
#: ``charter.offering.*`` directly. Empty: mission ``charter-pack-cutover-01M491G6``
#: WP05 (#3732, FR-010 / NFR-002) deleted the one exempt package and removed its
#: exemption rather than moving it; its adapters reach the offering tier only
#: through the ``charter.drg`` / ``charter.packs`` doors. Pinned empty (test below):
#: any entry is a deliberate, reviewed widening.
EXEMPT_MANAGEMENT_SURFACE: frozenset[str] = frozenset()

#: The full disposition taxonomy (data-model.md "Taxonomy (value set)" + the two
#: census-only tags: TICKETED-BASELINE for doorless management internals, and
#: INTERNAL-METADATA for ``import charter.offering`` path/metadata introspection).
TAXONOMY: frozenset[str] = frozenset(
    {
        "PUBLIC",
        "FACADE-ONLY",
        "MANAGEMENT",
        "TICKETED-BASELINE",
        "INTERNAL",
        "CONSTRUCTION-ROUTED",
        "INTERNAL-METADATA",
    }
)

#: Doctrine module-paths that have **no clean charter door** and are doctrine-
#: *management* internals. Per WP01 T004 they resolve to a documented, tracker-
#: referenced permanent ratchet allowlist entry (TICKETED-BASELINE) rather than
#: MANAGEMENT — MANAGEMENT would widen the exempt surface, the opposite of this
#: mission's intent. WP03 owes no door for these; WP05 keeps them allowlisted.
TICKETED_BASELINE: dict[str, str] = {
    "charter.offering.drg.override_policy": (
        "Doctrine-management internal consumed by _doctrine_collect.py (override-audit paths); no clean charter door. Ratchet allowlist, #3179."
    ),
    "charter.offering.drg.migration.hand_authored_overlay": (
        "write_reference_graph_with_overlay is a DRG-regeneration internal consumed by cli/commands/doctrine.py; no clean charter door. Ratchet allowlist, #3179."
    ),
}

#: The finalized per-path disposition table (keyed by doctrine module-path). This
#: is a **superset** of the currently-reached set: it also classifies paths reached
#: only under ``TYPE_CHECKING`` today (drg.merge, glossary_packs, assets.models) so
#: WP02/WP03 have a stable target even as call sites migrate. Every reached path
#: MUST appear here (test_every_reached_doctrine_path_has_disposition).
DISPOSITION: dict[str, str] = {
    # agent_profiles cluster → charter.profiles (existing door)
    "charter.offering.agent_profiles.profile": "FACADE-ONLY",
    "charter.offering.agent_profiles.repository": "FACADE-ONLY",
    "charter.offering.agent_profiles.capabilities": "FACADE-ONLY",
    "charter.offering.agent_profiles.diagnostics": "FACADE-ONLY",
    # operating_procedures: the single-authority operating-procedures harvest,
    # reached by _doctrine_collect.py (doctor doctrine) + the DRG extractor.
    # FACADE-ONLY per the cluster: it belongs behind the charter.profiles door;
    # the op-procedures door is a tracked follow-up (see PR #3593).
    "charter.offering.agent_profiles.operating_procedures": "FACADE-ONLY",
    # artifact kinds — PUBLIC (already enumerated in charter.offering.api / charter.drg)
    "charter.offering.artifact_kinds": "PUBLIC",
    # DRG cluster → charter.drg (existing/widened door)
    "charter.offering.drg.models": "FACADE-ONLY",
    "charter.offering.drg.loader": "FACADE-ONLY",
    "charter.offering.drg.merge": "FACADE-ONLY",
    "charter.offering.drg.org_pack_config": "FACADE-ONLY",
    "charter.offering.drg.validator": "FACADE-ONLY",
    "charter.offering.drg.override_policy": "TICKETED-BASELINE",
    "charter.offering.drg.migration.hand_authored_overlay": "TICKETED-BASELINE",
    # charter.offering.base — DoctrineLayerCollisionWarning (census-drift: absent from the
    # snapshot table). Doorable → FACADE-ONLY (prefer a clean door over widening
    # the exempt surface). Consumer _doctrine_collect.py is WP05-owned.
    "charter.offering.base": "FACADE-ONLY",
    # missions cluster → new charter.missions door
    "charter.offering.missions.step_contracts": "FACADE-ONLY",
    "charter.offering.missions.repository": "FACADE-ONLY",
    "charter.offering.missions.mission_type_repository": "FACADE-ONLY",
    # The two former "decide IC-01" rows: FACADE-ONLY (a clean charter.missions
    # door exists) — NOT MANAGEMENT, which would widen exemptions.
    "charter.offering.missions.step_projection": "FACADE-ONLY",
    "charter.offering.missions.mission_step_repository": "FACADE-ONLY",
    # model/task routing → new charter.model_routing (symbol-level PUBLIC)
    "charter.offering.model_task_routing": "PUBLIC",
    # assets → new charter.assets (PUBLIC)
    "charter.offering.assets.repository": "PUBLIC",
    "charter.offering.assets.models": "PUBLIC",
    # narrow doors
    "charter.offering.glossary_packs": "FACADE-ONLY",
    "charter.offering.spdd_reasons": "FACADE-ONLY",
    "charter.offering.template_catalog": "FACADE-ONLY",
    "charter.offering.pack_paths": "FACADE-ONLY",
    # sole-door service construction (routed through charter builder, IC-05)
    "charter.offering.service": "CONSTRUCTION-ROUTED",
    # bare ``import charter.offering`` — path/metadata introspection (charter.offering.__file__)
    # in tool_surface/bundles/codex.py. Not a symbol import; FR-006 exempt. Both
    # spellings pinned: the legacy ``doctrine`` name and the relocated
    # ``charter.offering`` name (charter-code-topology-01M152G1).
    "doctrine": "INTERNAL-METADATA",
    "charter.offering": "INTERNAL-METADATA",
}

#: Consumer files that reach doctrine (lazy import) but are **not** claimed by any
#: migration WP's ``owned_files`` — surfaced by the re-run census, not the snapshot.
#: Documented, ticket-referenced exceptions so the orphan is loud and reviewed
#: rather than silently passing the catch-all owner check. A NEW orphan (reached,
#: unowned, not listed here) fails test_no_reached_file_is_orphaned.
#:
#: ``charter/interview.py`` was the sole orphan: it reached ``charter.offering.artifact_kinds``
#: (ArtifactKind) directly while being owned by no migration WP. Mission
#: ``doctrine-public-api-surface-01KZPDSR`` WP07 folded it in (out-of-map, justified):
#: its ArtifactKind import now routes through ``charter.drg`` and its
#: ``charter.activation.org_charter`` usage is a first-party call into the
#: activation tier (not a laundered doctrine symbol). Any NEW orphan (reached,
#: unowned, not listed here) fails ``test_no_reached_file_is_orphaned``.
#: Tracker: #3179.
ORPHAN_REACHED_EXCEPTIONS: frozenset[tuple[str, str]] = frozenset(
    {
        # #3522 scan-root widening: ``src/runtime`` joined the census. Its two
        # lazy reaches (``charter.offering.missions.step_contracts`` /
        # ``….step_projection``, both FACADE-ONLY) predate the widening and
        # belong to no 01KZPDSR migration WP; routing them through a
        # charter.missions door is #2173 port work. They are ledger-pinned in
        # test_runtime_charter_doctrine_boundary.py's lazy baseline.
        ("src/runtime/next/runtime_bridge_composition.py", "charter.offering.missions.step_contracts"),
        ("src/runtime/next/runtime_bridge_io.py", "charter.offering.missions.step_projection"),
    }
)

#: Migration WPs whose union of ``owned_files`` must cover the reach-through census.
_MIGRATION_WP_FILES: tuple[str, ...] = (
    "WP05-conduit-closure-sole-door.md",
    "WP06-runtime-migration-profiles-routing.md",
    "WP07-runtime-migration-missions-bundles.md",
)


# ---------------------------------------------------------------------------
# AST census — parent-tracking descent (skips TYPE_CHECKING, tracks nesting)
# ---------------------------------------------------------------------------


def _is_type_checking(test: ast.expr) -> bool:
    """True for ``if TYPE_CHECKING:`` / ``if typing.TYPE_CHECKING:`` guards."""
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    if isinstance(test, ast.Attribute):
        return test.attr == "TYPE_CHECKING"
    return False


def _is_doctrine_name(name: str) -> bool:
    """True for an absolute doctrine module name, in EITHER spelling.

    Post-relocation (charter-code-topology-01M152G1) the doctrine layer lives at
    ``charter.offering.*``; the legacy ``doctrine``/``doctrine.*`` spelling
    resolves through the ``src/doctrine.py`` shim. The census must recognize
    both — matching only the legacy spelling left ``reached_doctrine_paths()``
    EMPTY on the relocated tree, so every census gate passed vacuously (found
    during the #3522 scan-root widening). The boundary gate shares this matcher.
    """
    if name in ("doctrine", "charter.offering"):
        return True
    return name.startswith("doctrine.") or name.startswith("charter.offering.")


def _doctrine_paths(node: ast.AST) -> set[str]:
    """Absolute doctrine targets; root from-imports include the imported member.

    Bare package imports can be pinned for metadata access. Importing a member
    of that package is a distinct reach, even when the member is locally aliased.
    """
    if isinstance(node, ast.ImportFrom):
        if node.level != 0:
            return set()
        module = node.module or ""
        if module in ("doctrine", "charter.offering"):
            return {f"{module}.{alias.name}" for alias in node.names}
        if _is_doctrine_name(module):
            return {module}
        if module == "charter" and any(alias.name == "offering" for alias in node.names):
            return {"charter.offering"}
    if isinstance(node, ast.Import):
        return {alias.name for alias in node.names if _is_doctrine_name(alias.name)}
    return set()


class _ReachVisitor(ast.NodeVisitor):
    """Collect non-TYPE_CHECKING ``doctrine.*`` imports (module-level or lazy)."""

    def __init__(self) -> None:
        self.paths: set[str] = set()
        self._type_checking_depth = 0

    def _record(self, node: ast.AST) -> None:
        if self._type_checking_depth:
            return
        self.paths.update(_doctrine_paths(node))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        self._record(node)

    def visit_Import(self, node: ast.Import) -> None:
        self._record(node)

    def visit_If(self, node: ast.If) -> None:
        guarded = _is_type_checking(node.test)
        if guarded:
            self._type_checking_depth += 1
        for child in node.body:
            self.visit(child)
        if guarded:
            self._type_checking_depth -= 1
        for child in node.orelse:
            self.visit(child)


def reached_doctrine_paths() -> dict[str, set[str]]:
    """Map each runtime file → the set of doctrine module-paths it reaches.

    Reach = a direct ``from charter.offering…`` / ``import charter.offering`` with
    ``ImportFrom.level == 0``, at module level *or* inside a function body,
    excluding ``if TYPE_CHECKING:`` blocks. Files that reach nothing are omitted.
    Public so WP04's ratchet baseline can consume the identical census.
    """
    result: dict[str, set[str]] = {}
    for path in sorted(p for root in _SCAN_ROOTS for p in root.rglob("*.py")):
        tree = parse_file(path)
        visitor = _ReachVisitor()
        for child in tree.body:
            visitor.visit(child)
        if visitor.paths:
            result[str(path.relative_to(_REPO_ROOT))] = visitor.paths
    return result


def undoored_paths(reached: set[str], disposition: dict[str, str]) -> set[str]:
    """Pure helper: reached doctrine paths that carry no disposition (an undoored gap)."""
    return {path for path in reached if path not in disposition}


def _owned_files(task_filename: str) -> list[str]:
    """Read the ``owned_files`` list from a WP task file's YAML frontmatter."""
    text = (_MISSION_TASKS / task_filename).read_text(encoding="utf-8")
    parts = text.split("---", 2)
    frontmatter = yaml.safe_load(parts[1]) if len(parts) >= 3 else {}
    return list(frontmatter.get("owned_files", []) or [])


# ---------------------------------------------------------------------------
# Gates
# ---------------------------------------------------------------------------


def test_every_reached_doctrine_path_has_disposition() -> None:
    """FR-002 / SC-002: every reached, non-exempt doctrine path is classified.

    A newly reach-through-ed doctrine module-path that lacks a disposition entry
    fails here — the machine-checkable "no undoored reach-through" guard.
    """
    reached: set[str] = set().union(*reached_doctrine_paths().values())
    undoored = undoored_paths(reached, DISPOSITION)
    assert not undoored, (
        "Undoored doctrine reach-through — the following doctrine module-paths are "
        "reached by non-exempt runtime code but carry no disposition in DISPOSITION:\n"
        + "\n".join(f"  - {path}" for path in sorted(undoored))
        + "\n\nClassify each (PUBLIC / FACADE-ONLY / TICKETED-BASELINE / …) in "
        "tests/architectural/test_doctrine_census.py::DISPOSITION and record the "
        "target door in data-model.md."
    )


def test_disposition_values_are_within_taxonomy() -> None:
    """Every disposition value is a member of the sanctioned taxonomy."""
    invalid = {v for v in DISPOSITION.values() if v not in TAXONOMY}
    assert not invalid, f"Disposition values outside the taxonomy: {sorted(invalid)}"


def test_no_reached_path_tagged_management() -> None:
    """MANAGEMENT (per-path) stays empty — the mission tightens, never widens.

    Choosing MANAGEMENT for a reached path widens the exempt surface, the opposite
    of this mission's goal. The four former "decide IC-01" rows resolved to
    FACADE-ONLY or TICKETED-BASELINE; none to MANAGEMENT.
    """
    management = {path for path, disp in DISPOSITION.items() if disp == "MANAGEMENT"}
    assert not management, (
        "A doctrine path was tagged MANAGEMENT, widening the exempt surface. Prefer "
        f"FACADE-ONLY (clean door) or TICKETED-BASELINE (doorless internal): {sorted(management)}"
    )


def test_management_surface_is_frozen() -> None:
    """Pin the management surface empty: the exemption was deleted, not moved (NFR-002).

    Mission ``charter-pack-cutover-01M491G6`` WP05 deleted the one exempt package
    (FR-010); its fetch/scaffold adapters moved to ``specify_cli.charter_packs``
    with no exemption. Any entry here is a deliberate, reviewed widening.
    """
    assert not EXEMPT_MANAGEMENT_SURFACE, sorted(EXEMPT_MANAGEMENT_SURFACE)
    retired = _REPO_ROOT.joinpath("src", "specify_cli", "doctrine")
    assert not retired.exists(), "the retired management package is back in the tree"
    assert _REPO_ROOT.joinpath("src", "specify_cli").is_dir(), "control: the scan root exists"


def test_ticketed_baseline_paths_are_classified() -> None:
    """The two doorless management internals are TICKETED-BASELINE, not MANAGEMENT."""
    for path in TICKETED_BASELINE:
        assert DISPOSITION.get(path) == "TICKETED-BASELINE", f"{path} must be TICKETED-BASELINE in DISPOSITION (see WP01 T004)"


def test_no_reached_file_is_orphaned() -> None:
    """SC-001 catch-all owner check: every reached file has a named migration owner.

    The union of WP05/WP06/WP07 ``owned_files`` must cover the re-run lazy-import
    census set; any remainder must be a documented ORPHAN_REACHED_EXCEPTIONS entry
    (else the reached file is orphaned and this fails).
    """
    census = reached_doctrine_paths()
    owned: set[str] = set()
    for task_filename in _MIGRATION_WP_FILES:
        owned.update(_owned_files(task_filename))
    orphans = {(file, module) for file, modules in census.items() if file not in owned for module in modules} - ORPHAN_REACHED_EXCEPTIONS
    assert not orphans, (
        "Orphaned doctrine reach-through — the following files reach doctrine but are "
        "claimed by no migration WP (WP05/06/07) and are not a documented exception:\n"
        + "\n".join(f"  - {file} -> {module}" for file, module in sorted(orphans))
        + "\n\nAssign each to a migration WP's owned_files, or record a ticketed "
        "ORPHAN_REACHED_EXCEPTIONS entry."
    )


def test_orphan_exceptions_are_actually_reached() -> None:
    """Each excepted file/import pair must still be reached, even in a live file."""
    census_pairs = {(file, module) for file, modules in reached_doctrine_paths().items() for module in modules}
    stale = ORPHAN_REACHED_EXCEPTIONS - census_pairs
    assert not stale, f"Stale ORPHAN_REACHED_EXCEPTIONS entries (no longer reach doctrine — a migration likely landed): {sorted(stale)}. Remove them."


def test_injected_undoored_path_is_flagged() -> None:
    """The undoored detector flags a synthetic newly-reached path (gate efficacy).

    Proves the census gate would fail on a real regression without mutating the tree.
    """
    reached = {"charter.offering.artifact_kinds", "charter.offering.brand_new_undoored_module"}
    flagged = undoored_paths(reached, DISPOSITION)
    assert flagged == {"charter.offering.brand_new_undoored_module"}
    # And the real, fully-classified reached set must flag nothing.
    real = set().union(*reached_doctrine_paths().values())
    assert undoored_paths(real, DISPOSITION) == set()


@pytest.mark.parametrize("spelling", ["doctrine", "charter.offering"])
def test_orphan_gate_rejects_added_reach_in_excepted_file(spelling: str) -> None:
    target = _REPO_ROOT / "src/runtime/next/runtime_bridge_composition.py"
    original_read = Path.read_text
    source = target.read_text(encoding="utf-8")
    facade = "from charter.drg import resolve_org_dirs"
    assert source.count(facade) == 1
    mutation = source.replace(facade, f"from {spelling}.drg.org_pack_config import resolve_org_dirs")

    def read_source(path: Path, encoding: str | None = None) -> str:
        return mutation if path == target else original_read(path, encoding=encoding)

    with (
        patch.object(Path, "read_text", read_source),
        pytest.raises(AssertionError, match="org_pack_config"),
    ):
        test_no_reached_file_is_orphaned()


def test_orphan_gate_rejects_replaced_exception() -> None:
    target = _REPO_ROOT / "src/runtime/next/runtime_bridge_composition.py"
    original_read = Path.read_text
    source = target.read_text(encoding="utf-8")
    assert "from charter.offering.missions.step_contracts import" in source
    mutation = source.replace("from charter.offering.missions.step_contracts import", "from charter.offering.service import")

    def read_source(path: Path, encoding: str | None = None) -> str:
        return mutation if path == target else original_read(path, encoding=encoding)

    with (
        patch.object(Path, "read_text", read_source),
        pytest.raises(AssertionError, match="step_contracts"),
    ):
        test_orphan_exceptions_are_actually_reached()


@pytest.mark.parametrize("package", ["runtime", "specify_cli"])
@pytest.mark.parametrize("lazy", [False, True], ids=["top-level", "lazy"])
@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        ("from doctrine.drg.org_pack_config import resolve_org_dirs", {"doctrine.drg.org_pack_config"}),
        ("from charter.offering.drg.org_pack_config import resolve_org_dirs", {"charter.offering.drg.org_pack_config"}),
        ("from charter import offering as implementation", {"charter.offering"}),
        ("import charter.offering.service, charter.offering.drg.org_pack_config", {"charter.offering.service", "charter.offering.drg.org_pack_config"}),
    ],
)
def test_census_source_scan_collects_import_forms(package: str, lazy: bool, statement: str, expected: set[str]) -> None:
    target = _REPO_ROOT / "src" / package / "__init__.py"
    original_read = Path.read_text
    addition = f"def injected_probe():\n    {statement}\n" if lazy else statement + "\n"
    mutation = target.read_text(encoding="utf-8") + "\n" + addition

    def read_source(path: Path, encoding: str | None = None) -> str:
        return mutation if path == target else original_read(path, encoding=encoding)

    with patch.object(Path, "read_text", read_source):
        assert reached_doctrine_paths().get(str(target.relative_to(_REPO_ROOT)), set()) == expected


@pytest.mark.parametrize(
    "source",
    [
        "from charter.drg import resolve_org_dirs\n",
        "from .doctrine import local_name\n",
        "from .charter import offering\n",
        "import doctrine_tools, charter.offerings\n",
        "if TYPE_CHECKING:\n    from doctrine import profile\n",
        "def probe():\n    if typing.TYPE_CHECKING:\n        from charter import offering\n",
    ],
)
def test_census_ignores_compliant_and_non_runtime_imports(source: str) -> None:
    visitor = _ReachVisitor()
    visitor.visit(ast.parse(source))
    assert visitor.paths == set()


@pytest.mark.parametrize("spelling", ["doctrine", "charter.offering"])
@pytest.mark.parametrize(
    ("members", "targets"),
    [
        ("drg as implementation", {"drg"}),
        ("service as factory, drg as implementation", {"service", "drg"}),
        ("*", {"*"}),
    ],
)
def test_census_distinguishes_root_members_from_metadata(spelling: str, members: str, targets: set[str]) -> None:
    target = _REPO_ROOT / "src/specify_cli/tool_surface/bundles/codex.py"
    original_read = Path.read_text
    metadata_import = "import charter.offering as _charter_offering"
    source = target.read_text(encoding="utf-8") + f"\n{metadata_import}\n{metadata_import}\n"
    assert source.count(metadata_import) == 2
    mutation = source.replace(metadata_import, f"from {spelling} import {members}", 1)

    def read_source(path: Path, encoding: str | None = None) -> str:
        return mutation if path == target else original_read(path, encoding=encoding)

    with patch.object(Path, "read_text", read_source):
        expected = {"charter.offering"} | {f"{spelling}.{member}" for member in targets}
        assert reached_doctrine_paths()[str(target.relative_to(_REPO_ROOT))] == expected
