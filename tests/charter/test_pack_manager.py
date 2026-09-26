"""Unit tests for ``charter.activation.pack_manager`` (WP04, T019).

Covers:
- ``YAML_KEY_MAP``: entry count, mission-type outlier, value naming conventions
- ``activate()``: None-state materialisation, existing-set append, no-duplicate,
  comment preservation, invalid-kind ValueError
- ``deactivate()``: None-state exit-1 with upgrade guidance, remove from list,
  warn-when-absent, invalid-kind ValueError
- ``list_activated()``: None-state returns None per kind, populated returns frozenset
- ``merge_defaults()``: writes absent keys, preserves present keys, backup on charter
- Mission-type layer scan (WP05, T011/T012 -- FR-003/FR-005/NFR-002): org/project
  layer resolution for the flat ``mission-type`` kind, built-in->org->project
  precedence order, the missing-project-directory edge case, and the
  ``.kittify/missions/mission_types/`` roster vs
  ``.kittify/missions/<mission-name>/`` instance non-collision guarantee.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from charter.activation.activation_engine import UnknownActivationIdError
from charter.activation.invocation_context import ProjectContext
from charter.activation.pack_manager import (
    CharterPackManager,
    YAML_KEY_MAP,
)

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("pointer", [False, True])
@pytest.mark.parametrize("newline", ["\n", "\r\n"])
@pytest.mark.parametrize(
    "body",
    [
        "activated_directives: # rationale\n# key detail\n  - old\n",
        "? activated_directives\n: [old]\n",
    ],
)
def test_deactivate_preserves_entry_boundaries(tmp_path: Path, pointer: bool, newline: str, body: str) -> None:
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    config = tmp_path / ".kittify/config.yaml"
    config.parent.mkdir()
    target = tmp_path / "policy.yaml" if pointer else config
    if pointer:
        config.write_bytes(b"charter: policy.yaml\n")
    tail = 'metadata: {label: "keep"}\n'.replace("\n", newline).encode()
    target.write_bytes(body.replace("\n", newline).encode() + tail)
    before = snapshot({"project": tmp_path})
    manager = CharterPackManager()
    context = ProjectContext(repo_root=tmp_path)
    result = manager.deactivate(context, kind="directive", artifact_id="old")
    assert result.deactivated == ["old"]
    raw = target.read_bytes()
    assert yaml.safe_load(raw)["activated_directives"] == []
    assert raw.endswith(tail)
    if "# key detail" in body:
        assert raw.count(b"# rationale") == raw.count(b"# key detail") == 1
    if pointer:
        assert snapshot({"project": tmp_path})[("project", ".kittify/config.yaml")] == before[("project", ".kittify/config.yaml")]
    after = snapshot({"project": tmp_path})
    assert manager.deactivate(context, kind="directive", artifact_id="old").deactivated == []
    assert_unchanged(after, snapshot({"project": tmp_path}))


@pytest.mark.parametrize("pointer", [None, {}, [], 42, "relative", "absolute"])
def test_preparation_preserves_target_policy(tmp_path: Path, pointer: object) -> None:
    from charter.activation.pack_manager import prepare_activation_write
    from charter.activation.charter_yaml_io import apply_yaml_write
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    config = tmp_path / ".kittify/config.yaml"
    config.parent.mkdir()
    target = tmp_path / "policy.yaml" if isinstance(pointer, str) else config
    value = str(target) if pointer == "absolute" else "policy.yaml" if pointer == "relative" else pointer
    config.write_text(yaml.safe_dump({"charter": value, "unowned": ["preserve"]}), encoding="utf-8")
    if target != config:
        target.write_text('# policy\nmetadata: {label: "keep"}\n', encoding="utf-8")
    before = snapshot({"project": tmp_path})
    prepared = prepare_activation_write(tmp_path, {"mission_type_activations": ["research"]})
    assert prepared.target == target
    assert_unchanged(before, snapshot({"project": tmp_path}))
    assert apply_yaml_write(prepared)
    assert yaml.safe_load(target.read_bytes())["mission_type_activations"] == ["research"]
    if target != config:
        assert snapshot({"project": tmp_path})[("project", ".kittify/config.yaml")] == before[("project", ".kittify/config.yaml")]


@pytest.mark.parametrize("problem", ["dangling", "malformed", "scalar", "unreadable", "config", "link"])
def test_preparation_refuses_broken_required_inputs(tmp_path: Path, problem: str) -> None:
    from ruamel.yaml.error import YAMLError
    from charter.activation.pack_context import CharterPackConfigError
    from charter.activation.pack_manager import prepare_activation_write
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    config = tmp_path / ".kittify/config.yaml"
    config.parent.mkdir()
    config.write_text("charter: policy.yaml\n", encoding="utf-8")
    target = tmp_path / "policy.yaml"
    if problem != "dangling":
        target.write_text("[broken" if problem == "malformed" else "scalar" if problem == "scalar" else "metadata: {}\n", encoding="utf-8")
    if problem == "unreadable":
        target.chmod(0)
    elif problem == "config":
        config.write_text("[broken", encoding="utf-8")
    elif problem == "link":
        target.rename(tmp_path / "sentinel.yaml")
        target.symlink_to(tmp_path / "sentinel.yaml")
    # The independent oracle needs read access to inventory the unreadable
    # case; compare its sentinel/config and lstat separately in that cell.
    if problem == "unreadable":
        before_config = config.read_bytes()
        before_stat = target.lstat()
        with pytest.raises(PermissionError):
            prepare_activation_write(tmp_path, {"mission_type_activations": ["research"]})
        assert target.lstat() == before_stat and config.read_bytes() == before_config
        target.chmod(0o600)
    else:
        before = snapshot({"project": tmp_path})
        with pytest.raises((ValueError, OSError, YAMLError, CharterPackConfigError)) as caught:
            prepare_activation_write(tmp_path, {"mission_type_activations": ["research"]})
        assert str(caught.value)
        assert_unchanged(before, snapshot({"project": tmp_path}))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    """Create a minimal .kittify/ directory with an empty config.yaml."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text("# empty config\n", encoding="utf-8")
    return tmp_path


@pytest.fixture()
def ctx(project_root: Path) -> ProjectContext:
    """ProjectContext built from the minimal project root.

    Uses the direct constructor rather than ``ProjectContext.from_repo`` --
    ``CharterPackManager`` only ever calls ``ctx.require_repo_root()``
    (``pack_context`` is never read), and ``from_repo`` eagerly resolves
    ``PackContext.from_config()``, which now hard-fails (WP04, C-A1) when
    ``mission_type_activations`` is absent from config.yaml. These tests
    intentionally exercise a bare/near-bare config.yaml for the
    ``activated_*`` keys under test, so building the full pack context here
    would force an unrelated mission-type activation key onto every fixture.
    """
    return ProjectContext(repo_root=project_root)


@pytest.fixture()
def manager() -> CharterPackManager:
    return CharterPackManager()


# ---------------------------------------------------------------------------
# TestYamlKeyMap
# ---------------------------------------------------------------------------


class TestYamlKeyMap:
    def test_has_exactly_ten_entries(self) -> None:
        assert YAML_KEY_MAP == {
            "agent-profile": "activated_agent_profiles",
            "directive": "activated_directives",
            "glossary-pack": "activated_glossary_packs",
            "mission-step-contract": "activated_mission_step_contracts",
            "mission-type": "mission_type_activations",
            "paradigm": "activated_paradigms",
            "procedure": "activated_procedures",
            "styleguide": "activated_styleguides",
            "tactic": "activated_tactics",
            "toolguide": "activated_toolguides",
        }

    def test_mission_type_maps_to_correct_key(self) -> None:
        assert YAML_KEY_MAP["mission-type"] == "mission_type_activations"

    def test_directive_maps_to_activated_directives(self) -> None:
        assert YAML_KEY_MAP["directive"] == "activated_directives"

    def test_all_values_start_with_activated_or_mission(self) -> None:
        for kind, yaml_key in YAML_KEY_MAP.items():
            assert yaml_key.startswith("activated_") or yaml_key == "mission_type_activations", f"Key '{kind}' maps to unexpected yaml_key '{yaml_key}'"


# ---------------------------------------------------------------------------
# TestActivateNoneState
# ---------------------------------------------------------------------------


class TestActivateNoneState:
    def test_activates_new_artifact_from_empty_config(self, manager: CharterPackManager, ctx: ProjectContext, project_root: Path) -> None:
        """Activating on a fresh config preserves what was effective, then adds the ID.

        #4253: this used to materialize ``default.yaml`` — a strict subset of
        the available corpus — which deactivated everything outside it. From
        the unrestricted state the artifact was effective only implicitly, so
        the call that makes it explicit reports it as activated rather than as
        "already activated".
        """
        result = manager.activate(
            ctx,
            kind="directive",
            artifact_id="001-architectural-integrity-standard",
        )
        assert result.activated == ["001-architectural-integrity-standard"]
        assert any("already effective" in w for w in result.warnings)
        # config.yaml must now contain the key
        config = project_root / ".kittify" / "config.yaml"
        data = yaml.safe_load(config.read_text())
        assert "001-architectural-integrity-standard" in data["activated_directives"]

    def test_warns_about_initializing_from_the_effective_set(self, manager: CharterPackManager, ctx: ProjectContext) -> None:
        """#4253: the warning names what was preserved, not a default pack.

        The old wording ("initialized from default pack") described the
        narrowing this issue removed; an operator reading it had no signal
        that artifacts had just been deactivated.
        """
        result = manager.activate(
            ctx,
            kind="directive",
            artifact_id="001-architectural-integrity-standard",
        )
        assert any("had no explicit activation set" in w for w in result.warnings)
        assert any("nothing in force was deactivated" in w for w in result.warnings)

    def test_default_ids_are_present_after_materialize(self, manager: CharterPackManager, ctx: ProjectContext, project_root: Path) -> None:
        manager.activate(ctx, kind="directive", artifact_id="001-architectural-integrity-standard")
        config = project_root / ".kittify" / "config.yaml"
        data = yaml.safe_load(config.read_text())
        # At least one canonical built-in directive must be present
        assert "001-architectural-integrity-standard" in data["activated_directives"]


# ---------------------------------------------------------------------------
# TestActivateExistingSet
# ---------------------------------------------------------------------------


class TestActivateExistingSet:
    def test_appends_to_existing_list(self, manager: CharterPackManager, project_root: Path) -> None:
        config = project_root / ".kittify" / "config.yaml"
        config.write_text(
            "activated_directives:\n  - 001-architectural-integrity-standard\n",
            encoding="utf-8",
        )
        ctx = ProjectContext(repo_root=project_root)
        result = manager.activate(ctx, kind="directive", artifact_id="003-decision-documentation-requirement")
        assert "003-decision-documentation-requirement" in result.activated
        data = yaml.safe_load(config.read_text())
        assert "001-architectural-integrity-standard" in data["activated_directives"]
        assert "003-decision-documentation-requirement" in data["activated_directives"]

    def test_no_duplicate_on_double_activate(self, manager: CharterPackManager, project_root: Path) -> None:
        config = project_root / ".kittify" / "config.yaml"
        config.write_text(
            "activated_directives:\n  - 001-architectural-integrity-standard\n",
            encoding="utf-8",
        )
        ctx = ProjectContext(repo_root=project_root)
        manager.activate(ctx, kind="directive", artifact_id="001-architectural-integrity-standard")
        data = yaml.safe_load(config.read_text())
        assert data["activated_directives"].count("001-architectural-integrity-standard") == 1

    def test_rejects_malformed_existing_activation_set(self, manager: CharterPackManager, project_root: Path) -> None:
        """A scalar activation set must not be split into characters on write."""
        config = project_root / ".kittify" / "config.yaml"
        config.write_text("activated_directives: not-a-list\n", encoding="utf-8")
        before = config.read_text(encoding="utf-8")
        ctx = ProjectContext(repo_root=project_root)

        with pytest.raises(ValueError, match="activated_directives.*must be a list"):
            manager.activate(
                ctx,
                kind="directive",
                artifact_id="001-architectural-integrity-standard",
            )

        assert config.read_text(encoding="utf-8") == before

    def test_comments_preserved_in_config(self, manager: CharterPackManager, project_root: Path) -> None:
        config = project_root / ".kittify" / "config.yaml"
        config.write_text(
            "# project-level comment\nactivated_directives:\n  - 001-architectural-integrity-standard\n",
            encoding="utf-8",
        )
        ctx = ProjectContext(repo_root=project_root)
        manager.activate(ctx, kind="directive", artifact_id="003-decision-documentation-requirement")
        raw = config.read_text()
        assert "# project-level comment" in raw


# ---------------------------------------------------------------------------
# TestActivateInvalidKind
# ---------------------------------------------------------------------------


class TestActivateInvalidKind:
    def test_raises_value_error_for_unknown_kind(self, manager: CharterPackManager, ctx: ProjectContext) -> None:
        with pytest.raises(ValueError, match="Unknown activation kind"):
            manager.activate(ctx, kind="nonexistent-kind", artifact_id="x")

    def test_raises_value_error_for_unknown_artifact_id(self, manager: CharterPackManager, ctx: ProjectContext) -> None:
        # WP09 delegates activation to the engine, which raises the typed
        # UnknownActivationIdError (a ValueError subclass) with the actionable
        # "Unknown <kind> ID ..." message.
        with pytest.raises(ValueError, match="Unknown directive ID"):
            manager.activate(ctx, kind="directive", artifact_id="not-a-real-directive")


# ---------------------------------------------------------------------------
# TestDeactivateNoneState
# ---------------------------------------------------------------------------


class TestDeactivateNoneState:
    def test_raises_typed_error_when_no_activation_set(
        self,
        manager: CharterPackManager,
        ctx: ProjectContext,
    ) -> None:
        """deactivate() on a None-state kind raises the typed engine error.

        WP09/T042: the legacy ``sys.exit(1)`` is gone — the activation engine
        raises NoActivationRestrictionsError (carrying the "run upgrade first"
        guidance) for the CLI (WP12) to surface, so the engine/manager never
        touch process state.
        """
        from charter.activation.activation_engine import NoActivationRestrictionsError

        with pytest.raises(NoActivationRestrictionsError, match="spec-kitty upgrade"):
            manager.deactivate(ctx, kind="directive", artifact_id="something")


# ---------------------------------------------------------------------------
# TestDeactivateExistingSet
# ---------------------------------------------------------------------------


class TestDeactivateExistingSet:
    def test_removes_artifact_from_list(self, manager: CharterPackManager, project_root: Path) -> None:
        config = project_root / ".kittify" / "config.yaml"
        config.write_text(
            "activated_directives:\n  - keep-me\n  - remove-me\n",
            encoding="utf-8",
        )
        ctx = ProjectContext(repo_root=project_root)
        result = manager.deactivate(ctx, kind="directive", artifact_id="remove-me")
        assert "remove-me" in result.deactivated
        data = yaml.safe_load(config.read_text())
        assert "remove-me" not in data["activated_directives"]
        assert "keep-me" in data["activated_directives"]

    def test_warns_when_artifact_not_in_set(self, manager: CharterPackManager, project_root: Path) -> None:
        config = project_root / ".kittify" / "config.yaml"
        config.write_text(
            "activated_directives:\n  - something-else\n",
            encoding="utf-8",
        )
        ctx = ProjectContext(repo_root=project_root)
        result = manager.deactivate(ctx, kind="directive", artifact_id="not-present")
        assert result.deactivated == []
        assert any("not in the activation set" in w for w in result.warnings)

    def test_rejects_malformed_existing_activation_set(self, manager: CharterPackManager, project_root: Path) -> None:
        config = project_root / ".kittify" / "config.yaml"
        config.write_text("activated_directives: not-a-list\n", encoding="utf-8")
        ctx = ProjectContext(repo_root=project_root)

        with pytest.raises(ValueError, match="activated_directives.*must be a list"):
            manager.deactivate(ctx, kind="directive", artifact_id="x")


# ---------------------------------------------------------------------------
# TestListActivated
# ---------------------------------------------------------------------------


class TestListActivated:
    def test_none_for_all_kinds_on_empty_config(self, manager: CharterPackManager, ctx: ProjectContext) -> None:
        """All kinds return None when config.yaml has no activation keys."""
        result = manager.list_activated(ctx)
        assert len(result) == 10
        for kind in YAML_KEY_MAP:
            assert result[kind] is None, f"Expected None for kind '{kind}'"

    def test_returns_frozenset_for_populated_kind(self, manager: CharterPackManager, project_root: Path) -> None:
        config = project_root / ".kittify" / "config.yaml"
        config.write_text(
            "activated_directives:\n  - aaa\n  - bbb\n",
            encoding="utf-8",
        )
        ctx = ProjectContext(repo_root=project_root)
        result = manager.list_activated(ctx)
        assert result["directive"] == frozenset({"aaa", "bbb"})

    def test_other_kinds_still_none_when_one_populated(self, manager: CharterPackManager, project_root: Path) -> None:
        config = project_root / ".kittify" / "config.yaml"
        config.write_text(
            "activated_directives:\n  - something\n",
            encoding="utf-8",
        )
        ctx = ProjectContext(repo_root=project_root)
        result = manager.list_activated(ctx)
        assert result["tactic"] is None
        assert result["paradigm"] is None


# ---------------------------------------------------------------------------
# TestMergeDefaults
# ---------------------------------------------------------------------------


class TestMergeDefaults:
    def test_writes_absent_keys(self, manager: CharterPackManager, ctx: ProjectContext, project_root: Path) -> None:
        result = manager.merge_defaults(ctx)
        assert len(result.kinds_written) == 10  # all 10 kinds were absent
        config = project_root / ".kittify" / "config.yaml"
        data = yaml.safe_load(config.read_text())
        for yaml_key in YAML_KEY_MAP.values():
            assert yaml_key in data, f"Missing key after merge_defaults: {yaml_key}"

    def test_does_not_overwrite_present_keys(self, manager: CharterPackManager, project_root: Path) -> None:
        config = project_root / ".kittify" / "config.yaml"
        config.write_text(
            "activated_directives:\n  - only-mine\n",
            encoding="utf-8",
        )
        ctx = ProjectContext(repo_root=project_root)
        result = manager.merge_defaults(ctx)
        data = yaml.safe_load(config.read_text())
        # existing directive key must not be overwritten
        assert data["activated_directives"] == ["only-mine"]
        # other 9 absent kinds must have been written
        assert "directive" not in result.kinds_written
        assert len(result.kinds_written) == 9

    def test_creates_backup_when_charter_exists(self, manager: CharterPackManager, ctx: ProjectContext, project_root: Path) -> None:
        charter_dir = project_root / ".kittify" / "charter"
        charter_dir.mkdir(parents=True)
        charter_file = charter_dir / "charter.md"
        charter_file.write_text("# My Charter\n", encoding="utf-8")

        result = manager.merge_defaults(ctx)
        assert result.backup_path is not None
        assert result.backup_path.exists()
        assert result.backup_path.read_text() == "# My Charter\n"
        assert result.backup_path.parent.name == "backups"

    def test_no_backup_when_no_charter(self, manager: CharterPackManager, ctx: ProjectContext) -> None:
        result = manager.merge_defaults(ctx)
        assert result.backup_path is None

    def test_backup_filename_matches_pre_migration_golden_bytes(
        self,
        manager: CharterPackManager,
        ctx: ProjectContext,
        project_root: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """SC-004 persisted-artifact golden (kernel-clock-single-door WP07).

        Captured from the PRE-migration tree (before ``pack_manager.py``
        routed onto the door): under a frozen instant of
        ``2026-11-02T14:15:16.654321+00:00``, the raw
        ``datetime.now(tz=UTC).strftime("%Y%m%dT%H%M%SZ")`` call this method
        used to make produced the literal backup filename
        ``charter-20261102T141516Z.md``. This test freezes the door's
        ``DEFAULT_CLOCK`` (the seam the migrated call now reads through via
        ``now_utc_compact_stamp()``) to that exact instant and asserts the
        backup filename this WP's migrated code produces is byte-identical
        to that pre-migration golden -- proving the swap-to-producer changed
        no on-disk bytes.
        """
        import kernel.clock as clock_module
        from kernel.clock import UTC, FrozenClock, datetime as door_datetime

        fixed = door_datetime(2026, 11, 2, 14, 15, 16, 654321, tzinfo=UTC)
        monkeypatch.setattr(clock_module, "DEFAULT_CLOCK", FrozenClock(instant=fixed))

        charter_dir = project_root / ".kittify" / "charter"
        charter_dir.mkdir(parents=True)
        (charter_dir / "charter.md").write_text("# My Charter\n", encoding="utf-8")

        result = manager.merge_defaults(ctx)

        assert result.backup_path is not None
        assert result.backup_path.name == "charter-20261102T141516Z.md"


# ---------------------------------------------------------------------------
# TestActivateCascadeWarning
# ---------------------------------------------------------------------------


class TestActivateCascadeWarning:
    def test_cascade_true_does_not_append_manager_warning(self, manager: CharterPackManager, project_root: Path) -> None:
        """activate(cascade=True) keeps manager warnings scoped to activation state."""
        config = project_root / ".kittify" / "config.yaml"
        config.write_text(
            "activated_directives:\n  - 001-architectural-integrity-standard\n",
            encoding="utf-8",
        )
        ctx = ProjectContext(repo_root=project_root)
        result = manager.activate(
            ctx,
            kind="directive",
            artifact_id="003-decision-documentation-requirement",
            cascade=True,
        )
        assert not any("cascade" in w.lower() for w in result.warnings)


# ---------------------------------------------------------------------------
# TestDeactivateCascadeAndInvalidKind
# ---------------------------------------------------------------------------


class TestDeactivateCascadeAndInvalidKind:
    def test_cascade_true_does_not_append_manager_warning(self, manager: CharterPackManager, project_root: Path) -> None:
        """deactivate(cascade=True) keeps manager warnings scoped to activation state."""
        config = project_root / ".kittify" / "config.yaml"
        config.write_text("activated_directives:\n  - to-remove\n", encoding="utf-8")
        ctx = ProjectContext(repo_root=project_root)
        result = manager.deactivate(ctx, kind="directive", artifact_id="to-remove", cascade=True)
        assert not any("cascade" in w.lower() for w in result.warnings)

    def test_raises_value_error_for_unknown_kind(self, manager: CharterPackManager, ctx: ProjectContext) -> None:
        """deactivate() with an unknown kind raises ValueError."""
        with pytest.raises(ValueError, match="Unknown activation kind"):
            manager.deactivate(ctx, kind="not-a-kind", artifact_id="x")


# ---------------------------------------------------------------------------
# WP05 (T011/T012) -- mission-type org/project layer scan
#
# FR-003: charter activate mission-type <id> must resolve <id> against
# built-in, org AND project layers (in that precedence order), not only the
# built-in four. FR-005/CL-005: the project-layer roster is a FLAT
# .kittify/missions/mission_types/*.yaml, scanned non-recursively, and does
# not collide with the pre-existing .kittify/missions/<mission_name>/
# per-mission-instance convention. NFR-002: no path here may silently
# degrade to None/empty/"unknown".
#
# Pre-fix, ``_resolve_layer_candidate`` only resolves a directory for
# ``kind is None`` (mission-type) when ``layer == "built-in"``; org/project
# fall through to the final ``return None`` (src/charter/activation/pack_manager.py,
# confirmed live before this WP's change). Every test class below was
# written and run RED against that pre-fix body before the production fix
# was made -- see WP05's report for the captured pre-fix pytest output.
# ---------------------------------------------------------------------------


def _write_mission_type(dir_path: Path, mission_type_id: str) -> None:
    """Write a minimal, schema-valid ``<id>.yaml`` mission-type roster file.

    PR-CONTRACT-002 (pre-merge squad, mission up-mission-type-seam-01KZY1JB):
    ``list_available_detailed``'s ``kind is None`` (mission-type) branch now
    routes through the same schema-validating, loud-fail scan
    ``resolve_layered_mission_types`` uses post-activation (see that
    function's own module for the rationale) -- a file with only ``id:``/
    ``name:`` (``name`` is not a ``MissionType`` field; ``display_name`` is
    required) would now raise instead of being tolerated, so every fixture
    written by this helper must be a genuinely valid ``MissionType``.
    """
    dir_path.mkdir(parents=True, exist_ok=True)
    (dir_path / f"{mission_type_id}.yaml").write_text(
        f"schema_version: 1\nid: {mission_type_id}\ndisplay_name: {mission_type_id.title()}\n",
        encoding="utf-8",
    )


class TestResolveLayerCandidateMissionTypeLayers:
    """Unit-level pin for the exact directories ``_resolve_layer_candidate``
    resolves for ``kind is None`` (mission-type) org/project layers
    (FR-003/FR-005, CL-005's chosen locations).
    """

    def test_org_layer_resolves_to_pack_root_mission_types(self, tmp_path: Path) -> None:
        from charter.activation.pack_manager import _resolve_layer_candidate

        candidate = _resolve_layer_candidate("org", tmp_path, None, "missions/mission_types", layered=False)
        assert candidate == tmp_path / "mission_types"

    def test_project_layer_resolves_to_kittify_missions_mission_types(self, tmp_path: Path) -> None:
        """``root`` for the project layer is already ``repo_root / ".kittify"``
        (see ``specify_cli.cli.commands.charter._layer_roots.resolve_layer_roots``),
        so the resolved directory is ``.kittify/missions/mission_types`` -- a flat
        sibling of, not nested inside, ``.kittify/missions/<mission_name>/``.
        """
        from charter.activation.pack_manager import _resolve_layer_candidate

        candidate = _resolve_layer_candidate("project", tmp_path, None, "missions/mission_types", layered=False)
        assert candidate == tmp_path / "missions" / "mission_types"

    def test_built_in_layer_branch_is_unaffected(self, tmp_path: Path) -> None:
        """The pre-existing built-in-layer branch for ``kind is None`` must be
        untouched by adding the org/project branch."""
        from charter.activation.pack_manager import _resolve_layer_candidate
        from charter.offering.missions.repository import MissionTemplateRepository

        candidate = _resolve_layer_candidate("built-in", tmp_path, None, "missions/mission_types", layered=False)
        assert candidate == MissionTemplateRepository.default_missions_root() / "mission_types"


class TestMissionTypeOrgLayerResolves:
    """FR-003: an org-tier pack's flat ``mission_types/`` directory (CL-005)
    makes a non-built-in mission-type id available."""

    def test_org_pack_mission_type_id_is_available(self, manager: CharterPackManager, ctx: ProjectContext, tmp_path: Path) -> None:
        org_root = tmp_path / "org-pack"
        _write_mission_type(org_root / "mission_types", "qa")

        result = manager.list_available(ctx, kind="mission-type", layer_roots={"org": org_root})

        assert "qa" in result

    def test_org_pack_mission_type_id_reports_org_layer(self, manager: CharterPackManager, ctx: ProjectContext, tmp_path: Path) -> None:
        org_root = tmp_path / "org-pack"
        _write_mission_type(org_root / "mission_types", "qa")

        detailed = manager.list_available_detailed(ctx, kind="mission-type", layer_roots={"org": org_root})

        qa_entries = [entry for entry in detailed if entry.artifact_id == "qa"]
        assert [entry.layer for entry in qa_entries] == ["org"]


class TestMissionTypeProjectLayerResolves:
    """FR-005: the project-layer mission-type roster is flat --
    ``.kittify/missions/mission_types/*.yaml`` -- and makes a project-declared
    mission-type id available."""

    def test_project_pack_mission_type_id_is_available(self, manager: CharterPackManager, ctx: ProjectContext, project_root: Path) -> None:
        kittify = project_root / ".kittify"
        _write_mission_type(kittify / "missions" / "mission_types", "qa")

        result = manager.list_available(ctx, kind="mission-type", layer_roots={"project": kittify})

        assert "qa" in result

    def test_project_pack_mission_type_id_reports_project_layer(self, manager: CharterPackManager, ctx: ProjectContext, project_root: Path) -> None:
        kittify = project_root / ".kittify"
        _write_mission_type(kittify / "missions" / "mission_types", "qa")

        detailed = manager.list_available_detailed(ctx, kind="mission-type", layer_roots={"project": kittify})

        qa_entries = [entry for entry in detailed if entry.artifact_id == "qa"]
        assert [entry.layer for entry in qa_entries] == ["project"]

    def test_missing_project_mission_types_dir_yields_no_contributions(self, manager: CharterPackManager, ctx: ProjectContext, project_root: Path) -> None:
        """spec.md edge case: a project layer root is supplied but
        ``.kittify/missions/mission_types/`` does not exist at all (the
        ``project_root`` fixture's ``.kittify`` has no ``missions/`` dir).
        This must resolve as "no project-layer contributions" -- no crash,
        no error -- while built-in ids still resolve normally (NFR-002).
        """
        kittify = project_root / ".kittify"

        result = manager.list_available(ctx, kind="mission-type", layer_roots={"project": kittify})

        assert "software-dev" in result  # built-in layer unaffected
        assert "qa" not in result


class TestMissionTypeLayerPrecedenceOrder:
    """FR-003: the built-in -> org -> project precedence order must be
    explicit and tested, not incidental to a dict's iteration order."""

    def test_scan_layer_dirs_order_is_built_in_org_project(self, manager: CharterPackManager, tmp_path: Path) -> None:
        org_root = tmp_path / "org-pack"
        _write_mission_type(org_root / "mission_types", "qa")
        project_kittify = tmp_path / "proj" / ".kittify"
        _write_mission_type(project_kittify / "missions" / "mission_types", "qa")

        dirs = manager._scan_layer_dirs("mission-type", layer_roots={"org": org_root, "project": project_kittify})

        layers = [layer for layer, _dir in dirs]
        assert layers == ["built-in", "org", "project"]


class TestMissionTypeProjectLayerNonCollision:
    """FR-005/CL-005 (T012): confirm, not merely assert, that
    ``.kittify/missions/mission_types/`` (the flat mission-type roster) and
    ``.kittify/missions/<mission_name>/`` (a real mission instance) coexist
    as siblings under ``.kittify/missions/`` without either being misread as
    the other.

    The real protection is pre-existing and structural, independent of this
    WP or WP02's dead-code deletions: ``_mission_dir_if_valid``
    (``src/specify_cli/mission.py``) only recognizes a subdirectory as a
    mission instance when it contains a file literally named
    ``mission.yaml`` -- the roster directory's flat ``*.yaml`` files (named
    after mission-type ids, never ``mission.yaml`` itself) can never satisfy
    that check.
    """

    def test_roster_and_mission_instance_coexist_without_collision(self, manager: CharterPackManager, ctx: ProjectContext, project_root: Path) -> None:
        from specify_cli.mission import _mission_dir_if_valid, list_available_missions

        kittify = project_root / ".kittify"
        missions_dir = kittify / "missions"

        # The mission-type roster: a flat directory of *.yaml files named
        # after mission-type ids -- NOT mission.yaml.
        _write_mission_type(missions_dir / "mission_types", "qa")

        # A real mission instance: a subdirectory containing mission.yaml.
        instance_dir = missions_dir / "some-mission-instance"
        instance_dir.mkdir(parents=True)
        (instance_dir / "mission.yaml").write_text("name: some-mission-instance\n", encoding="utf-8")

        # 1. The charter layer resolves "qa" as a mission-type roster entry
        #    -- never "some-mission-instance" or the bare filename "mission".
        available = manager.list_available(ctx, kind="mission-type", layer_roots={"project": kittify})
        assert "qa" in available
        assert "some-mission-instance" not in available
        assert "mission" not in available

        # 2. The mission-instance scanner recognizes the real instance and
        #    refuses the roster directory -- pre-existing/structural
        #    (mission.yaml presence), not a byproduct of this WP.
        assert _mission_dir_if_valid(instance_dir) == instance_dir
        assert _mission_dir_if_valid(missions_dir / "mission_types") is None

        # 3. list_available_missions (the top-level scanner over
        #    .kittify/missions/) reports the real instance and never the
        #    roster directory -- confirming no live collision end to end.
        names = list_available_missions(kittify)
        assert "some-mission-instance" in names
        assert "mission_types" not in names

    def test_nested_per_type_subdirectory_no_longer_leaks(self, manager: CharterPackManager, ctx: ProjectContext, project_root: Path) -> None:
        """CL-005's *flat* layout trap, closed (PR-CONTRACT-002, pre-merge
        squad, mission up-mission-type-seam-01KZY1JB).

        Formerly (``test_rglob_would_leak_a_nested_per_type_subdirectory``,
        pre-fix): ``list_available_detailed``'s ``kind is None`` branch used
        ``scan_dir.rglob(glob)`` -- the SAME universal per-kind scan every
        other charter-activatable kind uses -- which recurses into any
        nested subdirectory and would mint a bogus mission-type id from an
        unrelated file (e.g. the rejected
        ``.kittify/doctrine/mission_types/<type>/governance-profile.yaml``
        shape CL-005 explicitly avoided by convention, not by code). Fixing
        PR-CONTRACT-002 -- routing the mission-type branch through the same
        non-recursive, ``iterdir()``-based scan
        ``resolve_layered_mission_types`` already uses post-activation
        (``charter.offering.missions.mission_type_repository.scan_mission_types_dir``)
        -- closes this leak as a direct, intended side effect: the scan no
        longer descends into ``roster_dir / "qa"`` at all, so
        ``governance-profile`` is never even visited.
        """
        kittify = project_root / ".kittify"
        roster_dir = kittify / "missions" / "mission_types"
        _write_mission_type(roster_dir, "qa")

        nested_dir = roster_dir / "qa"
        nested_dir.mkdir(parents=True)
        (nested_dir / "governance-profile.yaml").write_text("id: governance-profile\n", encoding="utf-8")

        available = manager.list_available(ctx, kind="mission-type", layer_roots={"project": kittify})

        assert "qa" in available
        assert "governance-profile" not in available


# ---------------------------------------------------------------------------
# PR-CONTRACT-002 (pre-merge squad, mission up-mission-type-seam-01KZY1JB):
# WP05's ``_declared_id`` (via ``rglob`` + a broad ``except (OSError,
# YAMLError, TypeError): return None``) silently drops a malformed or
# unreadable org/project mission-type file from ``list_available_detailed``
# -- the availability catalog ``activate()`` checks BEFORE allowing
# ``charter activate mission-type <id>`` -- while ``resolve_layered_mission_
# types`` (the path used post-activation) already loud-fails on the
# IDENTICAL file. These tests pin the loud-fail parity.
# ---------------------------------------------------------------------------


class TestMissionTypeMalformedOrgLayerLoudFails:
    def test_malformed_org_layer_yaml_is_not_silently_skipped(self, manager: CharterPackManager, ctx: ProjectContext, tmp_path: Path) -> None:
        """A malformed org-layer mission-type YAML must raise from
        ``list_available_detailed``/``list_available`` -- not be silently
        dropped from the catalog and mistaken for "does not exist"."""
        org_root = tmp_path / "org-pack"
        bad_file = org_root / "mission_types" / "broken.yaml"
        bad_file.parent.mkdir(parents=True, exist_ok=True)
        bad_file.write_text("key: [unterminated\n  - a\n", encoding="utf-8")

        with pytest.raises(Exception) as exc_info:  # noqa: PT011 - message content is the assertion
            manager.list_available(ctx, kind="mission-type", layer_roots={"org": org_root})

        assert str(bad_file) in str(exc_info.value)

    def test_unreadable_org_layer_directory_raises_naming_the_directory(self, manager: CharterPackManager, ctx: ProjectContext, tmp_path: Path) -> None:
        if os.name != "posix" or os.geteuid() == 0:
            pytest.skip("chmod-based unreadability needs POSIX and a non-root user")

        org_root = tmp_path / "org-pack"
        mt_dir = org_root / "mission_types"
        _write_mission_type(mt_dir, "qa")

        os.chmod(mt_dir, 0o000)
        try:
            with pytest.raises(Exception) as exc_info:  # noqa: PT011 - message content is the assertion
                manager.list_available(ctx, kind="mission-type", layer_roots={"org": org_root})
            assert str(mt_dir) in str(exc_info.value)
        finally:
            os.chmod(mt_dir, 0o755)

    def test_activate_on_malformed_org_layer_type_raises_real_cause_not_generic_unknown_id(
        self, manager: CharterPackManager, ctx: ProjectContext, tmp_path: Path
    ) -> None:
        """End to end through ``activate()``: a malformed org-layer file must
        surface the real parse failure, never the misleading generic
        ``UnknownActivationIdError`` ("unknown ID") that WP05's tolerant
        scan produced pre-fix for this exact input."""
        org_root = tmp_path / "org-pack"
        bad_file = org_root / "mission_types" / "broken.yaml"
        bad_file.parent.mkdir(parents=True, exist_ok=True)
        bad_file.write_text("key: [unterminated\n  - a\n", encoding="utf-8")

        with pytest.raises(Exception) as exc_info:  # noqa: PT011 - message content is the assertion
            manager.activate(ctx, kind="mission-type", artifact_id="broken", layer_roots={"org": org_root})

        assert not isinstance(exc_info.value, UnknownActivationIdError)
        assert str(bad_file) in str(exc_info.value)
