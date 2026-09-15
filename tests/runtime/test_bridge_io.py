"""I/O-port seam tests for ``runtime_bridge_io`` (#2531 WP05, FR-006).

Four independent concerns:

1. **Non-vacuousness / compat-guard checks** — the seam actually defines every
   symbol T017-T019 relocated. Native-delegate status for the `_`-prefixed
   compat-guarded set was verified by a dedicated frozen family guard (which
   hardcoded the tolerated cross-module baseline to the 3 pre-existing
   ``runtime.next.decision``-origin names), retired in #3285; this file
   additionally guards the
   two PUBLIC relocated names (``get_or_start_run``,
   ``build_operational_context_for_claim``) that grep-derived guard does not
   cover (it only tracks leading-underscore names).

2. **Focused unit tests (FR-006)** against the moved ports in isolation —
   stubbing the underlying I/O (tmp_path fixtures, monkeypatched
   ``runtime_bridge`` guard-helpers) rather than driving the real runtime.
   These pin the behavior-preserving move (C-001) for: the feature-runs
   index, template/pack discovery, run lifecycle, the OC builder,
   ``gather_artifact_presence`` (T018), and ``resolve_commit_target`` (T019,
   tested as a pure no-I/O function per NFR-003).

3. **Intra-seam / cross-seam live-lookup regression** (the WP05-specific risk
   flagged in ``research.md`` §Compat and ``contracts/compat-surface.md``):
   now that the moved cluster lives together in one seam module (plus calls
   back into compat-tracked names that stay in the residual), a bare
   intra-module/direct call would resolve via the seam's own globals (or fail
   to resolve at all) — bypassing a ``monkeypatch.setattr(runtime_bridge,
   "<name>", …)``. ``test_*_uses_live_lookup_for_*`` pin this by patching the
   callee on ``runtime_bridge`` and asserting the (unpatched) caller in the
   seam still observes it. ``_build_discovery_context`` is the grounded 🔴
   high-risk case research.md names explicitly.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

import pytest

from runtime.next._internal_runtime import MissionRunRef
from runtime.next import runtime_bridge_io as io_seam
from specify_cli.core.constants import MISSION_TYPE_SOFTWARE_DEV

# Module name the WP06 (FR-010/FR-011) diagnostics log under -- matches
# ``_logger = logging.getLogger(__name__)`` in ``runtime_bridge_io.py``.
_IO_SEAM_LOGGER_NAME = "runtime.next.runtime_bridge_io"

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# ---------------------------------------------------------------------------
# 1. Non-vacuousness / compat-guard checks
# ---------------------------------------------------------------------------

# Every symbol T017-T019 relocated to runtime_bridge_io.py that the WP02
# compat guard bound (ALL_COMPAT_SYMBOLS / REACH -- that dedicated guard was
# retired in #3285) -- MUST stay a native def/class on runtime_bridge, never a
# plain re-export (see module docstring above).
_COMPAT_GUARDED_NAMES = frozenset(
    {
        "_load_feature_runs",
        "_build_run_ref",
        "_mission_key_for_run_ref",
        "_build_discovery_context",
        "_resolve_runtime_template_in_root",
        "_runtime_template_key",
        "_existing_run_ref",
        "_start_ephemeral_query_run",
        "_resolve_run_dir_for_mission",
        "_resolve_tech_stack_for_profile",
        "_build_operational_context_for_decision",
    }
)

# Public (non-underscore) names moved by this WP. Not part of the WP02 guard's
# tracked `_`-prefixed inventory (that guard's grep only matches leading-
# underscore names), but heavily monkeypatched directly on `runtime_bridge` by
# OTHER (non-frozen) test files -- e.g. tests/unit/mission_loader/test_command.py,
# tests/integration/test_mission_run_command.py. Kept as native thin delegates
# for the same safety, even though not strictly required by guard B.
_PUBLIC_RELOCATED_NAMES = frozenset({"get_or_start_run", "build_operational_context_for_claim"})


def test_seam_defines_every_relocated_symbol() -> None:
    """Non-vacuousness check: the seam must actually define every relocated
    name, or the native-thin-delegate assertion below would pass for the
    wrong reason (nobody needing the port at all).

    ``_load_feature_runs`` is deliberately excluded here: its "body" on the
    seam is the composition ``load_feature_runs(_feature_runs_path(repo_root))``
    (the textbook path-based port + the repo_root -> path resolver), not a
    literal ``_load_feature_runs`` name on ``runtime_bridge_io`` -- only the
    residual keeps that exact repo_root-keyed compat name.
    """
    seam_names = (_COMPAT_GUARDED_NAMES - {"_load_feature_runs"}) | _PUBLIC_RELOCATED_NAMES | {
        "resolve_commit_target",
        "gather_artifact_presence",
        "load_feature_runs",
        "save_feature_runs",
        "_feature_runs_path",
    }
    for name in sorted(seam_names):
        assert hasattr(io_seam, name), f"seam is missing relocated symbol {name!r}"


def test_runtime_bridge_keeps_native_thin_delegates_for_public_relocated_names() -> None:
    """The two PUBLIC relocated names must stay a NATIVE ``def`` statement in
    runtime_bridge.py (a thin delegate), never a plain ``import`` alias. The
    frozen family guard's grep-derived inventory only tracks leading-
    underscore (``_``-prefixed) symbols, so it does NOT cover these two public
    names -- this is their only native-delegate guard."""
    from runtime.next import runtime_bridge as rb

    for name in sorted(_PUBLIC_RELOCATED_NAMES):
        obj = getattr(rb, name)
        assert obj.__module__ == rb.__name__, (
            f"{name!r} on runtime_bridge is NOT natively defined there "
            f"(__module__={obj.__module__!r}) -- it must be a native thin "
            "delegate, not a plain re-export; unlike the `_`-prefixed compat "
            "set, no other guard covers this public name."
        )


def test_runtime_bridge_no_longer_owns_feature_runs_file_constants() -> None:
    """The move actually happened: the residual no longer defines the
    feature-runs-index leaf constants (``_feature_runs_path``,
    ``MISSION_RUNTIME_YAML``, ``MISSION_YAML``) -- they live solely on the
    seam now (mirrors the WP04 "only seam owns this import surface" check,
    scoped to this WP's leaf constants instead of a third-party package)."""
    from runtime.next import runtime_bridge as rb

    assert not hasattr(rb, "_feature_runs_path")
    assert not hasattr(rb, "MISSION_RUNTIME_YAML")
    assert not hasattr(rb, "MISSION_YAML")
    assert not hasattr(rb, "_FEATURE_RUNS_FILE")
    # KITTIFY_DIR is still used by unmoved residual code (e.g. bulk_edit gate
    # path composition), so it legitimately stays defined on both modules.
    assert hasattr(rb, "KITTIFY_DIR")
    assert hasattr(io_seam, "KITTIFY_DIR")


# ---------------------------------------------------------------------------
# 2a. Feature-runs index port
# ---------------------------------------------------------------------------


def test_load_feature_runs_missing_file_returns_empty_dict(tmp_path: Path) -> None:
    assert io_seam.load_feature_runs(tmp_path / "does-not-exist.json") == {}


def test_load_feature_runs_malformed_json_returns_empty_dict(tmp_path: Path) -> None:
    path = tmp_path / "feature-runs.json"
    path.write_text("{not-json", encoding="utf-8")
    assert io_seam.load_feature_runs(path) == {}


def test_save_then_load_feature_runs_round_trips(tmp_path: Path) -> None:
    path = tmp_path / "runtime" / "feature-runs.json"
    index: dict[str, io_seam._FeatureRunEntry] = {
        "042-test-feature": {
            "run_id": "01HRUNID000000000000000000",
            "run_dir": str(tmp_path / "runs" / "01HRUNID000000000000000000"),
            "mission_type": "software-dev",
            "mission_key": "software-dev",
            "mission_id": None,
            "mission_slug": "042-test-feature",
        }
    }
    io_seam.save_feature_runs(path, index)
    assert path.exists()
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk == index
    assert io_seam.load_feature_runs(path) == index


def test_feature_runs_path_composes_kittify_runtime_location(tmp_path: Path) -> None:
    assert io_seam._feature_runs_path(tmp_path) == tmp_path / ".kittify" / "runtime" / "feature-runs.json"


def test_build_run_ref_uses_mission_key() -> None:
    # Non-shared-temp-dir absolute sentinel (category B, test_no_tmp_paths_in_tests):
    # no real I/O happens against this path -- it is only echoed back as a string.
    ref = io_seam._build_run_ref(run_id="r1", run_dir="/fake-run-store/r1", mission_type="software-dev")
    assert ref.run_id == "r1"
    assert ref.run_dir == "/fake-run-store/r1"
    assert ref.mission_key == "software-dev"


def test_mission_key_for_run_ref_prefers_mission_key_then_default() -> None:
    ref_present = cast(MissionRunRef, SimpleNamespace(mission_key="software-dev"))
    assert io_seam._mission_key_for_run_ref(ref_present, default="fallback") == "software-dev"

    # Blank/whitespace-only mission_key falls through to the default -- the
    # sole remaining field (the retired cross-version `mission_type` fallback
    # was confirmed dead: the real MissionRunRef model only ever has
    # `mission_key`) -- see runtime_bridge_io.py.
    ref_blank = cast(MissionRunRef, SimpleNamespace(mission_key="  "))
    assert io_seam._mission_key_for_run_ref(ref_blank, default="fallback") == "fallback"

    ref_empty = cast(MissionRunRef, SimpleNamespace(mission_key=""))
    assert io_seam._mission_key_for_run_ref(ref_empty, default="fallback") == "fallback"


# ---------------------------------------------------------------------------
# 2b. Discovery cluster
# ---------------------------------------------------------------------------


def test_candidate_templates_for_root_dedupes_and_orders(tmp_path: Path) -> None:
    root = tmp_path / "missions"
    root.mkdir()
    candidates = io_seam._candidate_templates_for_root(root, "software-dev")
    # De-duplicated (no repeats) and non-empty for a directory root.
    assert len(candidates) == len({str(c) for c in candidates})
    assert candidates  # at least one candidate composed for a dir root


def test_candidate_templates_for_root_single_file(tmp_path: Path) -> None:
    mission_yaml = tmp_path / "mission.yaml"
    mission_yaml.write_text("mission:\n  key: software-dev\n", encoding="utf-8")
    assert io_seam._candidate_templates_for_root(mission_yaml, "software-dev") == [mission_yaml]


def test_candidate_templates_for_root_rejects_unrelated_file(tmp_path: Path) -> None:
    other = tmp_path / "notes.txt"
    other.write_text("hello", encoding="utf-8")
    assert io_seam._candidate_templates_for_root(other, "software-dev") == []


def test_template_key_for_file_returns_none_on_load_failure(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """T032 (FR-010): the return-value contract is unchanged (still `None`
    on a load failure -- callers that depend on `None` meaning "skip this
    candidate" keep working exactly as before), but the failure is no
    longer swallowed in total silence -- a named warning identifying the
    offending path is now also recorded. Before this WP, calling
    ``_template_key_for_file`` directly on a malformed file produced zero
    diagnostics anywhere; this asserts both halves of that change."""
    bogus = tmp_path / "mission.yaml"
    bogus.write_text("not: valid: yaml: at: all:", encoding="utf-8")

    with caplog.at_level(logging.WARNING, logger=_IO_SEAM_LOGGER_NAME):
        result = io_seam._template_key_for_file(bogus)

    assert result is None
    assert any(str(bogus) in record.getMessage() for record in caplog.records), (
        f"expected a named warning identifying {bogus}, found none in "
        f"{caplog.records!r}"
    )


def test_split_env_paths_blank_is_empty() -> None:
    assert io_seam._split_env_paths("   ") == []


def test_split_env_paths_splits_on_os_pathsep(tmp_path: Path) -> None:
    import os

    joined = os.pathsep.join([str(tmp_path / "a"), str(tmp_path / "b")])
    assert io_seam._split_env_paths(joined) == [tmp_path / "a", tmp_path / "b"]


def test_project_config_pack_paths_missing_config_is_empty(tmp_path: Path) -> None:
    assert io_seam._project_config_pack_paths(tmp_path) == []


def test_project_config_pack_paths_reads_mission_packs(tmp_path: Path) -> None:
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        "mission_packs:\n  - packs/one\n  - packs/two\n", encoding="utf-8"
    )
    assert io_seam._project_config_pack_paths(tmp_path) == [
        tmp_path / "packs/one",
        tmp_path / "packs/two",
    ]


def test_build_discovery_context_anchors_on_repo_root(tmp_path: Path) -> None:
    context = io_seam._build_discovery_context(tmp_path)
    assert context.project_dir == tmp_path
    assert len(context.builtin_roots) == 1
    assert context.builtin_roots[0].name == "missions"


# ---------------------------------------------------------------------------
# 2b-org. Org tier -- Walk A wiring site 1 + Walk B (WP04, FR-008/FR-009,
# mission up-org-template-fsm-01M06F9K). Fixture layout mirrors WP03's
# ``tests/runtime/test_resolver_unit.py::_write_org_pack_config`` helper
# (kept as a local copy, not a cross-test-module import, so this file's
# fixtures stay self-contained).
# ---------------------------------------------------------------------------


def _write_org_pack_config(repo_root: Path, *, pack_name: str, local_path: Path) -> None:
    """Write a canonical ``doctrine.org.packs[].local_path`` config.yaml entry."""
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yaml").write_text(
        "doctrine:\n"
        "  org:\n"
        "    packs:\n"
        f"      - name: {pack_name}\n"
        f"        local_path: {local_path}\n",
        encoding="utf-8",
    )


def _write_runtime_mission_yaml(path: Path, *, key: str) -> None:
    """Write a minimal, schema-valid runtime mission.yaml at ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "mission:\n"
        f"  key: {key}\n"
        f"  name: {key.title()}\n"
        '  version: "1.0.0"\n'
        "steps:\n"
        "  - id: discover\n"
        "    title: Discover\n"
        "    prompt: Run discovery.\n",
        encoding="utf-8",
    )


def test_build_discovery_context_populates_org_roots_from_configured_pack(
    tmp_path: Path,
) -> None:
    """FR-008 (DEC-006 site 1 -- the construction site that feeds Walk A for
    both `spec-kitty next` and query-mode runs): org_roots is populated via
    `charter.drg.resolve_org_roots(repo_root)` for a configured org pack."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    org_root = tmp_path / "org-pack"
    org_root.mkdir()
    _write_org_pack_config(repo_root, pack_name="acme", local_path=org_root)

    context = io_seam._build_discovery_context(repo_root)

    assert context.org_roots == [org_root]


def test_build_discovery_context_org_roots_empty_when_unconfigured(tmp_path: Path) -> None:
    """NFR-005/SC-007: with no `doctrine.org.packs` entries (no
    `.kittify/config.yaml` at all -- the overwhelmingly common case),
    `org_roots` is empty and every other field stays exactly what it was
    before this WP -- a verified no-op."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    context = io_seam._build_discovery_context(repo_root)

    assert context.org_roots == []
    assert context.project_dir == repo_root
    assert [r.name for r in context.builtin_roots] == ["missions"]


def test_build_discovery_context_propagates_org_pack_subdir_escape_error(
    tmp_path: Path,
) -> None:
    """DEC-005/NFR-001: `OrgPackSubdirEscapeError` is not swallowed by
    `_build_discovery_context` -- it propagates exactly as it does out of
    `resolve_org_roots()` itself. No `try/except` wraps the call."""
    from charter.offering.drg.org_pack_config import OrgPackSubdirEscapeError

    repo_root = tmp_path / "repo"
    pack_root = tmp_path / "org-pack"
    pack_root.mkdir(parents=True)
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir()
    (pack_root / "escape").symlink_to(outside_dir)

    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text(
        "doctrine:\n"
        "  org:\n"
        "    packs:\n"
        "      - name: acme\n"
        f"        local_path: {pack_root}\n"
        "        subdir: escape\n",
        encoding="utf-8",
    )

    with pytest.raises(OrgPackSubdirEscapeError):
        io_seam._build_discovery_context(repo_root)


def test_build_discovery_context_malformed_config_still_resolves_with_zero_org_roots(
    tmp_path: Path,
) -> None:
    """NFR-001(b)/DEC-005 (Walk A regression, mirrors WP03's T017): a
    malformed `.kittify/config.yaml` does not raise -- `load_pack_registry`'s
    pre-existing fail-soft absorbs it, so `_build_discovery_context` still
    returns a usable context with zero org roots contributed.

    Regression guard (pre-merge lens, mission
    ``up-org-template-fsm-01M06F9K``): resolution is a hot path that may run
    many times per invocation. A project with no readable org-pack intent
    (this config can't even be parsed) must see ZERO new warning output --
    NFR-005/SC-007 requires byte-identical behaviour, explicitly including
    "same log output, no new warnings", for a project with no org pack
    configured. Before the fix this asserted the opposite
    (``pytest.warns(UserWarning)``), codifying the regression as expected."""
    import warnings

    repo_root = tmp_path / "repo"
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text(
        "not: [valid, doctrine.org.packs shape\n", encoding="utf-8"
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        context = io_seam._build_discovery_context(repo_root)

    assert caught == []
    assert context.org_roots == []
    assert context.project_dir == repo_root


def test_runtime_template_key_malformed_config_still_resolves_project_legacy(
    tmp_path: Path,
) -> None:
    """NFR-001(b)/DEC-005 (Walk B regression, mirrors WP03's T017): a
    malformed `.kittify/config.yaml` does not prevent `_runtime_template_key`
    from still resolving the project-legacy mission -- the pre-existing
    fail-soft in `load_pack_registry` absorbs it, contributing zero org
    roots rather than raising.

    Regression guard (pre-merge lens, mission
    ``up-org-template-fsm-01M06F9K``): same NFR-005/SC-007 zero-new-warnings
    requirement as the Walk A test above -- see its docstring."""
    import warnings

    repo_root = tmp_path / "repo"
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True)
    (config_dir / "config.yaml").write_text(
        "not: [valid, doctrine.org.packs shape\n", encoding="utf-8"
    )
    legacy_mission = repo_root / ".kittify" / "missions" / "software-dev" / "mission.yaml"
    _write_runtime_mission_yaml(legacy_mission, key="software-dev")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        resolved = io_seam._runtime_template_key("software-dev", repo_root)

    assert caught == []
    assert resolved == str(legacy_mission.resolve())


def test_build_discovery_context_declared_but_broken_org_pack_still_warns(
    tmp_path: Path,
) -> None:
    """Positive case for the two fixes above: a config that DOES declare
    ``doctrine.org.packs`` but fails schema validation (two packs sharing
    the same ``name``) is a genuinely misconfigured org pack -- the operator
    demonstrably opted in and deserves to know it's broken. Unlike the
    unparseable-file case, that signal must remain a loud ``UserWarning``
    through this same resolution hot path (Walk A: ``_build_discovery_context``)."""
    import warnings

    repo_root = tmp_path / "repo"
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True)
    acme_one = tmp_path / "acme-one"
    acme_two = tmp_path / "acme-two"
    (config_dir / "config.yaml").write_text(
        "doctrine:\n"
        "  org:\n"
        "    packs:\n"
        "      - name: acme\n"
        f"        local_path: {acme_one}\n"
        "      - name: acme\n"
        f"        local_path: {acme_two}\n",
        encoding="utf-8",
    )

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        context = io_seam._build_discovery_context(repo_root)

    assert len(caught) == 1
    assert "Invalid org-pack config" in str(caught[0].message)
    # Fails soft to zero org roots -- resolution still proceeds.
    assert context.org_roots == []


def test_runtime_template_key_resolves_org_tier_mission(tmp_path: Path) -> None:
    """User Story 3, Acceptance Scenario 2 (SC-003 part 2): an org-pack
    `mission.yaml` resolves over the built-in `mission-runtime.yaml` for a
    mission type the org pack also ships."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    org_root = tmp_path / "org-pack"
    org_mission = org_root / "missions" / "software-dev" / "mission.yaml"
    _write_runtime_mission_yaml(org_mission, key="software-dev")
    _write_org_pack_config(repo_root, pack_name="acme", local_path=org_root)

    resolved = io_seam._runtime_template_key("software-dev", repo_root)

    assert resolved == str(org_mission.resolve())


def test_runtime_template_key_project_legacy_wins_over_org(tmp_path: Path) -> None:
    """User Story 3, Acceptance Scenario 3 (Walk B half): a project-legacy
    mission.yaml wins over the org-pack file for the same mission type --
    position parity with Walk A (T024)."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    org_root = tmp_path / "org-pack"
    org_mission = org_root / "missions" / "software-dev" / "mission.yaml"
    _write_runtime_mission_yaml(org_mission, key="software-dev")
    _write_org_pack_config(repo_root, pack_name="acme", local_path=org_root)

    legacy_mission = repo_root / ".kittify" / "missions" / "software-dev" / "mission.yaml"
    _write_runtime_mission_yaml(legacy_mission, key="software-dev")

    resolved = io_seam._runtime_template_key("software-dev", repo_root)

    assert resolved == str(legacy_mission.resolve())


def test_runtime_template_key_no_org_roots_configured_is_a_noop(tmp_path: Path) -> None:
    """NFR-005/SC-007: with no org pack configured, `_runtime_template_key`
    resolves exactly as it did before this WP -- the project-legacy file,
    with the org tier contributing nothing."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    legacy_mission = repo_root / ".kittify" / "missions" / "software-dev" / "mission.yaml"
    _write_runtime_mission_yaml(legacy_mission, key="software-dev")

    resolved = io_seam._runtime_template_key("software-dev", repo_root)

    assert resolved == str(legacy_mission.resolve())


# ---------------------------------------------------------------------------
# 2b-org-parity. NFR-004/SC-008 cross-site org-tier position parity (T025).
# One pair of tests asserting the org tier sits at the identical relative
# position -- immediately below project/legacy, immediately above
# machine-global -- across all four sites this mission's org tier touches:
# doctrine/resolver.py + specify_cli/runtime/resolver.py (WP03), and FSM
# Walk A + Walk B (this WP). Position parity is verified functionally
# (which tier wins for identical fixtures across all four), not by
# asserting internal tier-list index equality -- Walk B's project_tiers
# list also has a `_project_config_pack_paths` slot between org and
# machine-global that the other three sites do not share (a pre-existing,
# out-of-scope divergence noted in FR-009's own docstring update above).
# ---------------------------------------------------------------------------


def test_org_tier_position_parity_project_legacy_wins_across_four_sites(
    tmp_path: Path,
) -> None:
    """Given project-legacy AND org fixtures for the same mission key, all
    four sites select project-legacy -- org sits BELOW project-legacy
    everywhere, not just in one walk."""
    import charter.offering.resolver as doctrine_resolver
    import specify_cli.runtime.resolver as specify_resolver
    from runtime.next._internal_runtime.discovery import DiscoveryContext as FSMContext
    from runtime.next._internal_runtime.discovery import discover_missions

    mission = "wp04-parity-legacy-wins"
    project = tmp_path / "project"
    project.mkdir()
    org_root = tmp_path / "org-pack"

    legacy_mission_yaml = project / ".kittify" / "missions" / mission / "mission.yaml"
    _write_runtime_mission_yaml(legacy_mission_yaml, key=mission)
    org_mission_yaml = org_root / "missions" / mission / "mission.yaml"
    _write_runtime_mission_yaml(org_mission_yaml, key=mission)

    _write_org_pack_config(project, pack_name="acme", local_path=org_root)

    # Site 1: doctrine/resolver.py
    doctrine_result = doctrine_resolver.resolve_mission(mission, project)
    assert doctrine_result.tier.name == "LEGACY"
    assert doctrine_result.path == legacy_mission_yaml

    # Site 2: specify_cli/runtime/resolver.py
    specify_result = specify_resolver.resolve_mission(mission, project)
    assert specify_result.tier.name == "LEGACY"
    assert specify_result.path == legacy_mission_yaml

    # Site 3: FSM Walk A
    walk_a_ctx = FSMContext(project_dir=project, org_roots=[org_root], user_home=tmp_path / "home")
    walk_a_by_tier = {d.precedence_tier: d for d in discover_missions(walk_a_ctx) if d.key == mission}
    assert walk_a_by_tier["project_legacy"].selected is True
    assert walk_a_by_tier["org"].selected is False

    # Site 4: FSM Walk B
    walk_b_resolved = io_seam._runtime_template_key(mission, project)
    assert walk_b_resolved == str(legacy_mission_yaml.resolve())


def test_org_tier_position_parity_org_wins_over_global_across_four_sites(
    tmp_path: Path,
) -> None:
    """Given ONLY an org fixture (no project-legacy) for the same mission
    key, all four sites select org -- org sits ABOVE machine-global
    everywhere, not just in one walk."""
    import charter.offering.resolver as doctrine_resolver
    import specify_cli.runtime.resolver as specify_resolver
    from runtime.next._internal_runtime.discovery import DiscoveryContext as FSMContext
    from runtime.next._internal_runtime.discovery import discover_missions

    mission = "wp04-parity-org-wins"
    project = tmp_path / "project"
    project.mkdir()
    org_root = tmp_path / "org-pack"

    org_mission_yaml = org_root / "missions" / mission / "mission.yaml"
    _write_runtime_mission_yaml(org_mission_yaml, key=mission)

    _write_org_pack_config(project, pack_name="acme", local_path=org_root)

    # Sites 1-2: resolvers. Point the global tier at an empty, isolated
    # directory so a miss there cannot masquerade as a false org "win".
    empty_home = tmp_path / "no-home"
    with patch("charter.offering.resolver.get_kittify_home", return_value=empty_home):
        doctrine_result = doctrine_resolver.resolve_mission(mission, project)
    with patch("specify_cli.runtime.resolver.get_kittify_home", return_value=empty_home):
        specify_result = specify_resolver.resolve_mission(mission, project)
    assert doctrine_result.tier.name == "ORG"
    assert doctrine_result.path == org_mission_yaml
    assert specify_result.tier.name == "ORG"
    assert specify_result.path == org_mission_yaml

    # Site 3: FSM Walk A
    walk_a_ctx = FSMContext(project_dir=project, org_roots=[org_root], user_home=tmp_path / "home")
    walk_a_by_tier = {d.precedence_tier: d for d in discover_missions(walk_a_ctx) if d.key == mission}
    assert walk_a_by_tier["org"].selected is True

    # Site 4: FSM Walk B
    walk_b_resolved = io_seam._runtime_template_key(mission, project)
    assert walk_b_resolved == str(org_mission_yaml.resolve())


# ---------------------------------------------------------------------------
# 2d. Walk B de-silencing (WP06, FR-010/FR-011, IC-06, mission
# up-org-template-fsm-01M06F9K). Named diagnostics for a load failure
# (T031/T032) and a non-built-in tier shipping both sidecar files
# (T033/T034/T035), replacing what was previously total silence.
# ---------------------------------------------------------------------------


def test_runtime_template_key_org_tier_malformed_mission_yaml_warns(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """FR-010, User Story 4 Acceptance Scenario 1 / SC-005: a malformed
    ``mission.yaml`` at the org tier produces a named warning identifying
    the offending path and tier (not silence). Before this WP,
    ``_runtime_template_key`` fell through to the bare ``mission_type``
    string with ZERO warnings recorded anywhere for this exact fixture --
    the fallback-to-``mission_type``-string return contract stays
    unchanged; only the diagnostic is new."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    org_root = tmp_path / "org-pack"
    # A mission type no built-in/global tier can also satisfy, so resolution
    # genuinely falls through to the bare string after the org tier's
    # malformed file is tried and warned about -- not masked by a real
    # built-in match at a later tier.
    mission_type = "wp06-malformed-org-mission"
    malformed = org_root / "missions" / mission_type / "mission.yaml"
    malformed.parent.mkdir(parents=True)
    malformed.write_text("not: valid: yaml: at: all:", encoding="utf-8")
    _write_org_pack_config(repo_root, pack_name="acme", local_path=org_root)

    with caplog.at_level(logging.WARNING, logger=_IO_SEAM_LOGGER_NAME):
        resolved = io_seam._runtime_template_key(mission_type, repo_root)

    assert resolved == mission_type
    matches = [record for record in caplog.records if str(malformed) in record.getMessage()]
    assert matches, (
        f"expected a named warning identifying the malformed org-tier file "
        f"{malformed}, found none in {caplog.records!r}"
    )
    assert str(org_root) in matches[0].getMessage(), (
        "expected the warning to also identify the offending tier/root, "
        f"got: {matches[0].getMessage()!r}"
    )


def test_non_builtin_tier_sidecar_pair_warns(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """FR-011, User Story 4 Acceptance Scenario 2 (positive half, T033/T034):
    a non-built-in tier (here, an org pack) shipping both ``mission.yaml``
    and ``mission-runtime.yaml`` for the same mission key produces a named
    diagnostic. C-005: the pre-existing ``mission-runtime.yaml``-wins
    preference is unchanged -- only the missing diagnostic is added; no
    error is raised and resolution still succeeds."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    org_root = tmp_path / "org-pack"
    mission_type = "wp06-sidecar-pair-mission"
    mission_dir = org_root / "missions" / mission_type
    _write_runtime_mission_yaml(mission_dir / "mission.yaml", key=mission_type)
    _write_runtime_mission_yaml(mission_dir / "mission-runtime.yaml", key=mission_type)
    _write_org_pack_config(repo_root, pack_name="acme", local_path=org_root)

    with caplog.at_level(logging.WARNING, logger=_IO_SEAM_LOGGER_NAME):
        resolved = io_seam._runtime_template_key(mission_type, repo_root)

    # C-005: sidecar preference is unchanged -- mission-runtime.yaml wins.
    assert resolved == str((mission_dir / "mission-runtime.yaml").resolve())
    matches = [record for record in caplog.records if str(mission_dir) in record.getMessage()]
    assert matches, (
        f"expected a named diagnostic for the non-built-in sidecar pair at "
        f"{mission_dir}, found none in {caplog.records!r}"
    )


@pytest.mark.parametrize(
    "mission_type", ["plan", "research", "documentation", MISSION_TYPE_SOFTWARE_DEV]
)
def test_builtin_sidecar_pairs_stay_silent(
    mission_type: str,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-011, User Story 4 Acceptance Scenario 2 (negative half, T035 --
    the main correctness risk per plan.md's IC-06 risk note): all four
    built-in mission directories already legitimately ship both
    ``mission.yaml`` and ``mission-runtime.yaml``. The new sidecar
    diagnostic MUST NOT fire for any of them -- exercised individually for
    all four, not just one representative.

    ``_runtime_template_key``'s global tier is ``DiscoveryContext.user_home``
    (``runtime/next/_internal_runtime/discovery.py``), which defaults to the
    *ambient* ``Path.home()`` -- not the ``SPEC_KITTY_HOME``-scoped override
    the bootstrap tests use. The per-worker isolated HOME the root conftest
    sets up (``tests/conftest.py``'s ``_isolated_worker_home``) is stable for
    the lifetime of the worker process, not reset between tests, so a stray
    ``~/.kittify/missions/<mission>/`` tier left by *any* other test that ran
    earlier in the same process is still visible here and would make this
    test observe a real (if accidental) non-built-in tier -- exactly the
    condition the diagnostic exists to report, just not the one this test
    means to exercise. Give the test its own definitely-empty HOME so the
    global tier is guaranteed absent, matching the pattern already used by
    ``tests/sync/test_*`` (``monkeypatch.setenv("HOME", ...)`` /
    ``"USERPROFILE"`` for Windows) rather than relying on process-wide
    isolation to also mean per-test isolation."""
    isolated_home = tmp_path / "isolated-home"
    isolated_home.mkdir()
    monkeypatch.setenv("HOME", str(isolated_home))
    monkeypatch.setenv("USERPROFILE", str(isolated_home))

    repo_root = tmp_path / "repo"
    repo_root.mkdir()

    with caplog.at_level(logging.WARNING, logger=_IO_SEAM_LOGGER_NAME):
        io_seam._runtime_template_key(mission_type, repo_root)

    sidecar_diagnostics = [
        record for record in caplog.records if "ships both" in record.getMessage()
    ]
    assert sidecar_diagnostics == [], (
        f"built-in mission {mission_type!r} must not trigger the "
        f"non-built-in sidecar diagnostic; got {sidecar_diagnostics!r}"
    )


def test_runtime_template_key_no_org_pack_configured_emits_no_new_warnings(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """NFR-005/SC-007 regression safety: a project with no org pack
    configured (the overwhelmingly common case) resolves the project-legacy
    mission byte-identically to before this WP, including emitting NO new
    warnings -- an unconditional/miscalibrated warn would be its own
    defect. This is the mandatory negative case for both FR-010 and
    FR-011's diagnostics in the same pass."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    legacy_mission = repo_root / ".kittify" / "missions" / "software-dev" / "mission.yaml"
    _write_runtime_mission_yaml(legacy_mission, key="software-dev")

    with caplog.at_level(logging.WARNING, logger=_IO_SEAM_LOGGER_NAME):
        resolved = io_seam._runtime_template_key("software-dev", repo_root)

    assert resolved == str(legacy_mission.resolve())
    assert caplog.records == [], (
        "no org pack configured -- expected zero warnings on the common "
        f"path, got {caplog.records!r}"
    )


# ---------------------------------------------------------------------------
# 2c. Run lifecycle
# ---------------------------------------------------------------------------


def test_existing_run_ref_returns_none_when_slug_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from runtime.next import runtime_bridge as rb

    monkeypatch.setattr(rb, "_load_feature_runs", lambda repo_root: {})
    assert io_seam._existing_run_ref("missing-mission", tmp_path, "software-dev") is None


def test_existing_run_ref_raises_when_state_file_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """WP05 / FR-016: a live index entry whose ``state.json`` is gone is a loud
    ``RunStateMissing``, never ``None`` (which used to let the caller start a
    fresh run over the orphaned history)."""
    from runtime.next import runtime_bridge as rb

    run_dir = tmp_path / "runs" / "r1"
    run_dir.mkdir(parents=True)
    monkeypatch.setattr(
        rb,
        "_load_feature_runs",
        lambda repo_root: {"042-mission": {"run_id": "r1", "run_dir": str(run_dir)}},
    )
    with pytest.raises(io_seam.RunStateMissing) as excinfo:
        io_seam._existing_run_ref("042-mission", tmp_path, "software-dev")
    assert excinfo.value.run_id == "r1"
    assert excinfo.value.error_code == "RUN_STATE_MISSING"


def test_existing_run_ref_builds_ref_when_state_file_present(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from runtime.next import runtime_bridge as rb

    run_dir = tmp_path / "runs" / "r1"
    run_dir.mkdir(parents=True)
    (run_dir / "state.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        rb,
        "_load_feature_runs",
        lambda repo_root: {
            "042-mission": {"run_id": "r1", "run_dir": str(run_dir), "mission_key": "software-dev"}
        },
    )
    ref = io_seam._existing_run_ref("042-mission", tmp_path, "software-dev")
    assert ref is not None
    assert ref.run_id == "r1"
    assert ref.mission_key == "software-dev"


def test_get_or_start_run_returns_existing_ref_without_starting_new_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """get_or_start_run must not call start_mission_run when a valid existing
    run is on record (mirrors the pre-extraction inline behavior)."""
    from runtime.next import runtime_bridge as rb

    run_dir = tmp_path / "runs" / "r1"
    run_dir.mkdir(parents=True)
    (run_dir / "state.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        rb,
        "_load_feature_runs",
        lambda repo_root: {
            "042-mission": {"run_id": "r1", "run_dir": str(run_dir), "mission_key": "software-dev"}
        },
    )

    def _should_not_start(**_kwargs: Any) -> Any:
        raise AssertionError("start_mission_run must not be called for an existing run")

    monkeypatch.setattr(io_seam, "start_mission_run", _should_not_start)

    ref = io_seam.get_or_start_run("042-mission", tmp_path, "software-dev")
    assert ref.run_id == "r1"


# ---------------------------------------------------------------------------
# 2d. OperationalContext (OC) builder
# ---------------------------------------------------------------------------


def test_resolve_run_dir_for_mission_none_when_no_run_recorded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from runtime.next import runtime_bridge as rb

    monkeypatch.setattr(rb, "_load_feature_runs", lambda repo_root: {})
    assert io_seam._resolve_run_dir_for_mission(tmp_path, "042-mission") is None


def test_resolve_run_dir_for_mission_returns_recorded_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from runtime.next import runtime_bridge as rb

    monkeypatch.setattr(
        rb,
        "_load_feature_runs",
        lambda repo_root: {"042-mission": {"run_dir": str(tmp_path / "runs" / "r1")}},
    )
    assert io_seam._resolve_run_dir_for_mission(tmp_path, "042-mission") == tmp_path / "runs" / "r1"


def test_resolve_tech_stack_for_profile_empty_when_no_profile_id(tmp_path: Path) -> None:
    assert io_seam._resolve_tech_stack_for_profile(tmp_path, None) == frozenset()


def test_resolve_tech_stack_for_profile_empty_on_resolution_failure(tmp_path: Path) -> None:
    # No doctrine directory at all -> AgentProfileRepository resolution fails
    # -> best-effort empty frozenset (never raises), matching NFR-004.
    assert io_seam._resolve_tech_stack_for_profile(tmp_path, "nonexistent-profile") == frozenset()


def test_resolve_tech_stack_for_profile_bare_repo_resolves_python_pedro(tmp_path: Path) -> None:
    """Regression (charter-sole-door-bypass-closure-01KZ3WAA landing-fold fix).

    ``tmp_path`` here has NO ``.kittify`` directory at all -- no compiled
    charter, no interview transcript -- the same bare-project shape as
    ``test_resolve_tech_stack_for_profile_empty_on_resolution_failure`` above,
    but with a REAL built-in profile id (``python-pedro``) instead of a
    nonexistent one.

    Confirmed red against the pre-fix code: ``build_activation_aware_doctrine_
    service(tmp_path)`` computed ``active_languages=[]`` (explicitly empty,
    not ``None``) for this bare fixture, which drops ``python-pedro`` (a
    language-scoped built-in) from ``agent_profile_repository``, so
    ``resolve_profile("python-pedro")`` raised ``KeyError`` -- silently
    swallowed by this function's best-effort ``except Exception`` -- and the
    resolved tech stack came back empty instead of ``{"python"}``. That
    silent emptiness fed straight into
    :class:`~charter.activation.invocation_context.OperationalContext` (see
    ``test_build_operational_context_for_claim_resolves_profile_from_run_dir``
    above), so this is a real end-to-end regression, not just an internal
    resolution detail.
    """
    result = io_seam._resolve_tech_stack_for_profile(tmp_path, "python-pedro")
    assert result == frozenset({"python"})


def test_build_operational_context_for_claim_resolves_profile_from_run_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from runtime.next import runtime_bridge as rb

    monkeypatch.setattr(rb, "_resolve_run_dir_for_mission", lambda repo_root, mission_slug: tmp_path)
    monkeypatch.setattr(rb, "_resolve_step_agent_profile", lambda run_dir, activity: "python-pedro")
    monkeypatch.setattr(rb, "_resolve_tech_stack_for_profile", lambda repo_root, profile_id: frozenset({"python"}))

    oc = io_seam.build_operational_context_for_claim(
        repo_root=tmp_path,
        feature_dir=tmp_path,
        mission_slug="042-mission",
        wp_id="WP01",
        actor="claude",
        active_model="sonnet",
        active_role=None,
        current_activity="implement",
    )
    assert oc.active_profile == "python-pedro"
    assert oc.tech_stack == frozenset({"python"})
    assert oc.active_role == "claude"


def test_build_operational_context_for_claim_explicit_profile_skips_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from runtime.next import runtime_bridge as rb

    def _should_not_resolve(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("must not resolve run_dir when active_profile is explicit")

    monkeypatch.setattr(rb, "_resolve_run_dir_for_mission", _should_not_resolve)
    monkeypatch.setattr(rb, "_resolve_tech_stack_for_profile", lambda repo_root, profile_id: frozenset())

    oc = io_seam.build_operational_context_for_claim(
        repo_root=tmp_path,
        feature_dir=tmp_path,
        mission_slug="042-mission",
        wp_id="WP01",
        actor="claude",
        active_model="sonnet",
        active_role=None,
        active_profile="explicit-profile",
    )
    assert oc.active_profile == "explicit-profile"


# ---------------------------------------------------------------------------
# 3. T018 — gather_artifact_presence
# ---------------------------------------------------------------------------


def _stub_guard_helpers(
    monkeypatch: pytest.MonkeyPatch,
    *,
    requirement_mapping_failures: list[str] | None = None,
    occurrence_gate_failures: list[str] | None = None,
    source_documented_count: int = 0,
    publication_approved: bool = False,
    has_raw_dependencies_field: bool = True,
) -> None:
    """Stub the compat-tracked guard helpers ``gather_artifact_presence``
    reaches via live lookup.

    ``_has_generated_docs`` is deliberately NOT stubbed here: it is not part
    of the WP02 compat guard's tracked inventory (nothing patches it in
    production code). A dedicated frozen guard
    (``test_reach_map_covers_the_full_grep_derived_inventory``) once grep-scanned
    the whole tests tree for any ``monkeypatch.setattr`` binding on
    ``runtime_bridge`` and failed if the bound name was not already a tracked
    symbol; that guard was retired in #3285. Tests
    that need ``has_generated_docs=True`` drive it with a real ``docs/*.md``
    file instead (see ``test_gather_artifact_presence_carries_generated_docs_flag``).
    """
    from runtime.next import runtime_bridge as rb

    monkeypatch.setattr(rb, "_check_requirement_mapping_ready", lambda feature_dir: requirement_mapping_failures or [])
    monkeypatch.setattr(rb, "_occurrence_gate_failures", lambda feature_dir: occurrence_gate_failures or [])
    monkeypatch.setattr(rb, "_count_source_documented_events", lambda feature_dir: source_documented_count)
    monkeypatch.setattr(rb, "_publication_approved", lambda feature_dir: publication_approved)
    monkeypatch.setattr(rb, "_has_raw_dependencies_field", lambda wp_file: has_raw_dependencies_field)


def test_gather_artifact_presence_reads_file_presence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_guard_helpers(monkeypatch)
    (tmp_path / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (tmp_path / "plan.md").write_text("# Plan\n", encoding="utf-8")

    snapshot = io_seam.gather_artifact_presence(
        tmp_path, mission_family="software-dev", step_id="tasks_outline"
    )
    assert snapshot.present_artifacts == {"spec.md", "plan.md"}
    assert snapshot.mission_family == "software-dev"
    assert snapshot.step_id == "tasks_outline"
    assert snapshot.legacy_step_id is None
    assert snapshot.status_facts["tasks_dir_is_dir"] is False
    assert snapshot.status_facts["wp_ids"] == ()


def test_gather_artifact_presence_reads_research_md_presence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Disk-backed revert-discipline pin (T001 step 4 / T004): exercises the
    real ``gather_artifact_presence`` function (not a hand-constructed
    ``ArtifactPresenceSnapshot``), so a revert of "research.md" from
    ``_PRESENCE_FILE_TAGS`` is actually detectable. RED today -- the file
    exists on disk, but ``_PRESENCE_FILE_TAGS`` does not include
    "research.md" yet, so ``present_artifacts`` comes back empty."""
    _stub_guard_helpers(monkeypatch)
    (tmp_path / "research.md").write_text("# Research\n", encoding="utf-8")

    snapshot = io_seam.gather_artifact_presence(tmp_path, mission_family="plan", step_id="research")
    assert "research.md" in snapshot.present_artifacts


def test_gather_artifact_presence_reads_wp_lane_and_dependencies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _stub_guard_helpers(monkeypatch, has_raw_dependencies_field=False)
    monkeypatch.setattr(io_seam, "get_wp_lane", lambda feature_dir, wp_id: "for_review")

    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "WP01-writeside.md").write_text("# WP01\n", encoding="utf-8")

    snapshot = io_seam.gather_artifact_presence(
        tmp_path, mission_family="software-dev", step_id="implement", legacy_step_id="tasks_finalize"
    )
    assert "tasks_wp_files" in snapshot.present_artifacts
    assert snapshot.status_facts["tasks_dir_is_dir"] is True
    assert snapshot.status_facts["wp_ids"] == ("WP01",)
    assert snapshot.status_facts["wp_lane_raw"] == {"WP01": "for_review"}
    assert snapshot.status_facts["wp_dependencies_present"] == {"WP01": False}
    assert snapshot.legacy_step_id == "tasks_finalize"


def test_gather_artifact_presence_carries_research_facts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_guard_helpers(
        monkeypatch,
        source_documented_count=3,
        publication_approved=True,
    )
    snapshot = io_seam.gather_artifact_presence(tmp_path, mission_family="research", step_id="output")
    assert snapshot.status_facts["source_documented_count"] == 3
    assert snapshot.status_facts["publication_approved"] is True


def test_gather_artifact_presence_carries_generated_docs_flag(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_guard_helpers(monkeypatch)
    docs_dir = tmp_path / "docs" / "guides"
    docs_dir.mkdir(parents=True)
    (docs_dir / "getting-started.md").write_text("# Getting started\n", encoding="utf-8")

    snapshot = io_seam.gather_artifact_presence(tmp_path, mission_family="documentation", step_id="generate")
    assert "generated_docs" in snapshot.present_artifacts
    assert snapshot.status_facts["has_generated_docs"] is True


def test_gather_artifact_presence_never_decides_only_gathers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sanity check on the FR-009 contract: the returned snapshot carries raw
    facts, not a pass/fail verdict -- there is no boolean "guards_passed" or
    similar decision field on the value object."""
    _stub_guard_helpers(monkeypatch, requirement_mapping_failures=["missing refs for WPs: WP01"])
    snapshot = io_seam.gather_artifact_presence(tmp_path, mission_family="software-dev", step_id="tasks_packages")
    assert snapshot.status_facts["requirement_mapping_failures"] == ("missing refs for WPs: WP01",)
    assert not hasattr(snapshot, "guards_passed")
    assert not hasattr(snapshot, "guard_failures")


# ---------------------------------------------------------------------------
# 4. T019 — resolve_commit_target (pure, no I/O -- NFR-003)
# ---------------------------------------------------------------------------


def test_resolve_commit_target_non_coord_topology_lands_on_repo_root(tmp_path: Path) -> None:
    mid8, worktree_root, target = io_seam.resolve_commit_target(
        coord_routing_topology=False,
        mission_slug="042-mission",
        mission_id="01HULIDXXXXXXXXXXXXXXXXXXX",
        coordination_branch="kitty/mission-042-mission",
        repo_root=tmp_path,
    )
    assert worktree_root == tmp_path
    assert target.ref == "kitty/mission-042-mission"
    assert mid8 == "01HULIDX"


def test_resolve_commit_target_coord_topology_computes_candidate_worktree_path(tmp_path: Path) -> None:
    mission_id = "01HULIDXXXXXXXXXXXXXXXXXXX"
    mid8, worktree_root_candidate, target = io_seam.resolve_commit_target(
        coord_routing_topology=True,
        mission_slug="042-mission",
        mission_id=mission_id,
        coordination_branch="kitty/mission-042-mission-01hulidx-coord",
        repo_root=tmp_path,
    )
    assert mid8 == "01hulidx".upper()[:8].lower() or mid8 == mission_id[:8]
    assert worktree_root_candidate == tmp_path / ".worktrees" / f"042-mission-{mid8}-coord"
    assert target.ref == "kitty/mission-042-mission-01hulidx-coord"
    # No disk I/O performed: the candidate path need not exist on disk.
    assert not worktree_root_candidate.exists()


def test_resolve_commit_target_raises_when_coord_topology_has_no_resolvable_mid8(tmp_path: Path) -> None:
    from runtime.next.runtime_bridge import DecisionGitLogUnavailable

    with pytest.raises(DecisionGitLogUnavailable):
        io_seam.resolve_commit_target(
            coord_routing_topology=True,
            mission_slug="bare-slug-no-tail",
            mission_id=None,
            coordination_branch="kitty/mission-bare-slug-no-tail",
            repo_root=tmp_path,
        )


# ---------------------------------------------------------------------------
# Live-lookup regressions (the WP05-specific false-green risk)
# ---------------------------------------------------------------------------


def test_runtime_template_key_uses_live_lookup_for_build_discovery_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The grounded 🔴 high-risk case research.md §Compat names explicitly:
    ``_build_discovery_context`` is patched in production tests
    (``test_query_mode_unit.py:751``) and reached only via intra-seam movers
    -- ``_runtime_template_key`` must resolve it via a live lookup through
    ``runtime_bridge``, never a bare intra-module call."""
    from runtime.next import runtime_bridge as rb

    calls: list[Path] = []
    sentinel_context = rb._build_discovery_context(tmp_path)

    def _spy(repo_root: Path) -> Any:
        calls.append(repo_root)
        return sentinel_context

    monkeypatch.setattr(rb, "_build_discovery_context", _spy)
    monkeypatch.setattr(rb, "_resolve_runtime_template_in_root", lambda root, mission_type: None)

    io_seam._runtime_template_key("software-dev", tmp_path)

    assert calls == [tmp_path]


def test_runtime_template_key_uses_live_lookup_for_resolve_runtime_template_in_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same false-green risk for ``_resolve_runtime_template_in_root`` --
    both it and its caller ``_runtime_template_key`` moved into this same
    seam module."""
    from runtime.next import runtime_bridge as rb

    resolved = tmp_path / "mission.yaml"
    calls: list[str] = []

    def _spy(root: Path, mission_type: str) -> Path | None:
        calls.append(mission_type)
        return resolved

    monkeypatch.setattr(rb, "_resolve_runtime_template_in_root", _spy)

    result = io_seam._runtime_template_key("software-dev", tmp_path)

    assert calls, "the patched runtime_bridge._resolve_runtime_template_in_root was never invoked"
    assert result == str(resolved)


def test_existing_run_ref_uses_live_lookup_for_load_feature_runs_and_build_run_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from runtime.next import runtime_bridge as rb

    run_dir = tmp_path / "runs" / "r1"
    run_dir.mkdir(parents=True)
    (run_dir / "state.json").write_text("{}", encoding="utf-8")

    load_calls: list[Path] = []
    build_calls: list[dict[str, Any]] = []

    def _spy_load(repo_root: Path) -> dict[str, Any]:
        load_calls.append(repo_root)
        return {"042-mission": {"run_id": "r1", "run_dir": str(run_dir)}}

    def _spy_build(*, run_id: str, run_dir: str, mission_type: str) -> Any:
        build_calls.append({"run_id": run_id, "run_dir": run_dir, "mission_type": mission_type})
        # Call the seam's real implementation directly -- NOT rb._build_run_ref,
        # which this very monkeypatch has replaced (calling it here would spy
        # on itself and recurse forever).
        return io_seam._build_run_ref(run_id=run_id, run_dir=run_dir, mission_type=mission_type)

    monkeypatch.setattr(rb, "_load_feature_runs", _spy_load)
    monkeypatch.setattr(rb, "_build_run_ref", _spy_build)

    ref = io_seam._existing_run_ref("042-mission", tmp_path, "software-dev")

    assert load_calls == [tmp_path]
    assert build_calls == [{"run_id": "r1", "run_dir": str(run_dir), "mission_type": "software-dev"}]
    assert ref is not None


def test_get_or_start_run_uses_live_lookup_for_resolve_mission_ulid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Cross-seam-to-residual risk: ``_resolve_mission_ulid`` stays on the
    identity cluster in the residual (not moved by this WP); ``get_or_start_run``
    (moved) must still reach it via a live lookup, not a stale cached import."""
    from runtime.next import runtime_bridge as rb

    monkeypatch.setattr(rb, "_load_feature_runs", lambda repo_root: {})
    monkeypatch.setattr(rb, "_runtime_template_key", lambda mission_type, repo_root: "software-dev")
    monkeypatch.setattr(io_seam, "_workflow_runtime_template", lambda *a, **k: (None, None))

    class _FakeRunRef:
        run_id = "new-run"
        run_dir = str(tmp_path / "runs" / "new-run")
        mission_key = "software-dev"
        mission_type = "software-dev"

    monkeypatch.setattr(io_seam, "start_mission_run", lambda **_kw: _FakeRunRef())

    calls: list[str] = []

    def _spy_resolve_mission_ulid(mission_slug: str, repo_root: Path) -> str | None:
        calls.append(mission_slug)
        return "01HULIDXXXXXXXXXXXXXXXXXXX"

    monkeypatch.setattr(rb, "_resolve_mission_ulid", _spy_resolve_mission_ulid)

    io_seam.get_or_start_run("042-mission", tmp_path, "software-dev")

    assert calls == ["042-mission"]


def test_build_operational_context_for_claim_uses_live_lookup_for_resolve_tech_stack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Intra-seam risk: ``build_operational_context_for_claim`` and
    ``_resolve_tech_stack_for_profile`` both moved into this seam module."""
    from runtime.next import runtime_bridge as rb

    monkeypatch.setattr(rb, "_resolve_run_dir_for_mission", lambda repo_root, mission_slug: None)

    calls: list[str | None] = []

    def _spy(repo_root: Path, profile_id: str | None) -> frozenset[str]:
        calls.append(profile_id)
        return frozenset({"python"})

    monkeypatch.setattr(rb, "_resolve_tech_stack_for_profile", _spy)

    oc = io_seam.build_operational_context_for_claim(
        repo_root=tmp_path,
        feature_dir=tmp_path,
        mission_slug="042-mission",
        wp_id="WP01",
        actor="claude",
        active_model="sonnet",
        active_role=None,
        active_profile="explicit-profile",
    )

    assert calls == ["explicit-profile"]
    assert oc.tech_stack == frozenset({"python"})
