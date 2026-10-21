"""Unit tests for ``charter.activation.pack_manager`` (WP04, T019).

Covers:
- ``YAML_KEY_MAP``: entry count, mission-type outlier, value naming conventions
- ``activate()``: None-state materialisation, existing-set append, no-duplicate,
  comment preservation, invalid-kind ValueError
- ``deactivate()``: None-state exit-1 with activate-first guidance, remove from list,
  warn-when-absent, invalid-kind ValueError
- ``list_activated()``: None-state returns None per kind, populated returns frozenset
- Mission-type layer scan (WP05, T011/T012 -- FR-003/FR-005/NFR-002): org/project
  layer resolution for the flat ``mission-type`` kind, built-in->org->project
  precedence order, the missing-project-directory edge case, and the
  ``.kittify/missions/mission_types/`` roster vs
  ``.kittify/missions/<mission-name>/`` instance non-collision guarantee.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
import yaml

from charter.activation.pack_context import ActiveCharterConfigError
from tests._factories.activation_ledger import legacy_target_scope, read_activation_ledger, seed_activation_ledger
from tests._support.eacces import deny_path_method
from charter.activation.activation_engine import UnknownActivationIdError
from charter.activation.invocation_context import ProjectContext
from charter.activation.pack_manager import (
    ActiveCharterManager,
    YAML_KEY_MAP,
    resolve_activation_write_target,
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
    manager = ActiveCharterManager()
    context = ProjectContext(repo_root=tmp_path)
    # A deactivation that records an exclusion refuses on a legacy surface (FR-017, C-003) and writes nothing.
    with pytest.raises(ActiveCharterConfigError):
        manager.deactivate(context, kind="directive", artifact_id="old")
    assert_unchanged(before, snapshot({"project": tmp_path}))
    # The allow-entry removal alone (a cascade child, D-11) keeps the legacy target's entry boundaries.
    result = manager.deactivate(context, kind="directive", artifact_id="old", record_exclusion=False)
    assert result.deactivated == ["old"]
    raw = target.read_bytes()
    assert yaml.safe_load(raw)["activated_directives"] == []
    assert "deactivated_directives" not in yaml.safe_load(raw)
    assert tail in raw
    if "# key detail" in body:
        assert raw.count(b"# rationale") == raw.count(b"# key detail") == 1
    if pointer:
        assert snapshot({"project": tmp_path})[("project", ".kittify/config.yaml")] == before[("project", ".kittify/config.yaml")]
    after = snapshot({"project": tmp_path})
    with pytest.raises(UnknownActivationIdError):  # neither listed nor available any more: refused, nothing written
        manager.deactivate(context, kind="directive", artifact_id="old", record_exclusion=False)
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
    # The subject is the legacy target policy; a keyless project is fresh (the ledger) outside the upgrade scope.
    with legacy_target_scope(tmp_path):
        prepared = prepare_activation_write(tmp_path, {"mission_type_activations": ["research"]})
    assert prepared.target == target
    assert_unchanged(before, snapshot({"project": tmp_path}))
    assert apply_yaml_write(prepared)
    assert yaml.safe_load(target.read_bytes())["mission_type_activations"] == ["research"]
    if target != config:
        assert snapshot({"project": tmp_path})[("project", ".kittify/config.yaml")] == before[("project", ".kittify/config.yaml")]


@pytest.mark.parametrize("problem", ["dangling", "malformed", "scalar", "unreadable", "config", "link"])
def test_preparation_refuses_broken_required_inputs(tmp_path: Path, problem: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """The subject is the legacy target's input refusal; a keyless project is fresh outside the upgrade scope."""
    with legacy_target_scope(tmp_path):
        _assert_preparation_refuses_broken_required_inputs(tmp_path, problem, monkeypatch)


def _assert_preparation_refuses_broken_required_inputs(tmp_path: Path, problem: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from ruamel.yaml.error import YAMLError
    from charter.activation.pack_context import ActiveCharterConfigError
    from charter.activation.pack_manager import prepare_activation_write
    from tests.upgrade.preview_support.snapshot import assert_unchanged, snapshot

    config = tmp_path / ".kittify/config.yaml"
    config.parent.mkdir()
    config.write_text("charter: policy.yaml\n", encoding="utf-8")
    target = tmp_path / "policy.yaml"
    if problem != "dangling":
        target.write_text("[broken" if problem == "malformed" else "scalar" if problem == "scalar" else "metadata: {}\n", encoding="utf-8")
    if problem == "unreadable":
        # Inject the denial at the read seam instead of chmod(0): root bypasses
        # file mode bits, so a chmod-based setup passed/failed by uid (#5622).
        deny_path_method(monkeypatch, "read_bytes", target)
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

        # "unchanged" means the file was not MODIFIED -- compare only the
        # modification-relevant stat fields, never the whole ``os.stat_result``.
        # A bare ``==`` on ``stat_result`` also compares ``st_atime``/``st_ctime``,
        # which a refusal path's stat/exists probe can bump without touching the
        # file, flaking this gate nondeterministically by filesystem atime policy.
        def _modification_facts(st: os.stat_result) -> tuple[int, int, int, int]:
            return (st.st_mode, st.st_size, st.st_mtime_ns, st.st_ino)

        assert _modification_facts(target.lstat()) == _modification_facts(before_stat)
        assert config.read_bytes() == before_config
    else:
        before = snapshot({"project": tmp_path})
        with pytest.raises((ValueError, OSError, YAMLError, ActiveCharterConfigError)) as caught:
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
    ``ActiveCharterManager`` only ever calls ``ctx.require_repo_root()``
    (``pack_context`` is never read), and ``from_repo`` eagerly resolves
    ``PackContext.from_config()``, which now hard-fails (WP04, C-A1) when
    ``mission_type_activations`` is absent from config.yaml. These tests
    intentionally exercise a bare/near-bare config.yaml for the
    ``activated_*`` keys under test, so building the full pack context here
    would force an unrelated mission-type activation key onto every fixture.
    """
    return ProjectContext(repo_root=project_root)


@pytest.fixture()
def manager() -> ActiveCharterManager:
    return ActiveCharterManager()


# ---------------------------------------------------------------------------
# TestYamlKeyMap
# ---------------------------------------------------------------------------


class TestYamlKeyMap:
    def test_has_exactly_eleven_entries(self) -> None:
        assert YAML_KEY_MAP == {
            "agent-profile": "activated_agent_profiles",
            "directive": "activated_directives",
            "glossary-pack": "activated_glossary_packs",
            "mission-step-contract": "activated_mission_step_contracts",
            "mission-type": "mission_type_activations",
            "skill": "activated_skills",
            "paradigm": "activated_paradigms",
            "procedure": "activated_procedures",
            "styleguide": "activated_styleguides",
            "tactic": "activated_tactics",
            "toolguide": "activated_toolguides",
        }


# ---------------------------------------------------------------------------
# TestActivateNoneState
# ---------------------------------------------------------------------------


class TestActivateNoneState:
    def test_activates_new_artifact_from_empty_config(self, manager: ActiveCharterManager, ctx: ProjectContext, project_root: Path) -> None:
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
        # A fresh project writes the activation ledger (FR-019).
        data = read_activation_ledger(project_root)
        assert "001-architectural-integrity-standard" in data["activated_directives"]

    def test_warns_about_initializing_from_the_effective_set(self, manager: ActiveCharterManager, ctx: ProjectContext) -> None:
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
        assert any("This list is now explicit" in w and "--only" in w for w in result.warnings), "#6408: the warning must say the list is frozen"


# ---------------------------------------------------------------------------
# TestActivateExistingSet
# ---------------------------------------------------------------------------


class TestActivateExistingSet:
    def test_appends_to_existing_list(self, manager: ActiveCharterManager, project_root: Path) -> None:
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

    def test_no_duplicate_on_double_activate(self, manager: ActiveCharterManager, project_root: Path) -> None:
        config = project_root / ".kittify" / "config.yaml"
        config.write_text(
            "activated_directives:\n  - 001-architectural-integrity-standard\n",
            encoding="utf-8",
        )
        ctx = ProjectContext(repo_root=project_root)
        manager.activate(ctx, kind="directive", artifact_id="001-architectural-integrity-standard")
        data = yaml.safe_load(config.read_text())
        assert data["activated_directives"].count("001-architectural-integrity-standard") == 1

    def test_rejects_malformed_existing_activation_set(self, manager: ActiveCharterManager, project_root: Path) -> None:
        """A scalar activation set must not be split into characters on write."""
        config = project_root / ".kittify" / "config.yaml"
        config.write_text("activated_directives: not-a-list\n", encoding="utf-8")
        before = config.read_text(encoding="utf-8")
        ctx = ProjectContext(repo_root=project_root)

        # The activation ledger seam reads the legacy allow keys first and refuses the scalar.
        with pytest.raises(ActiveCharterConfigError) as refused:
            manager.activate(
                ctx,
                kind="directive",
                artifact_id="001-architectural-integrity-standard",
            )

        assert re.search(r"activated_directives.*must be a list", refused.value.body)

        assert config.read_text(encoding="utf-8") == before

    def test_comments_preserved_in_config(self, manager: ActiveCharterManager, project_root: Path) -> None:
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
    def test_raises_value_error_for_unknown_kind(self, manager: ActiveCharterManager, ctx: ProjectContext) -> None:
        with pytest.raises(ValueError, match="Unknown activation kind"):
            manager.activate(ctx, kind="nonexistent-kind", artifact_id="x")

    def test_raises_value_error_for_unknown_artifact_id(self, manager: ActiveCharterManager, ctx: ProjectContext) -> None:
        # WP09 delegates activation to the engine, which raises the typed
        # UnknownActivationIdError (a ValueError subclass) with the actionable
        # "Unknown <kind> ID ..." message.
        with pytest.raises(ValueError, match="Unknown directive ID"):
            manager.activate(ctx, kind="directive", artifact_id="not-a-real-directive")


# ---------------------------------------------------------------------------
# TestDeactivateNoneState
# ---------------------------------------------------------------------------


class TestDeactivateNoneState:
    def test_records_an_exclusion_when_no_activation_set(
        self,
        manager: ActiveCharterManager,
        ctx: ProjectContext,
    ) -> None:
        """deactivate() on a None-state kind records an exclusion (ADR 2026-10-19-1).

        The allow list stays absent ("absent = all"); the id lands in
        ``deactivated_directives`` instead of raising.
        """
        result = manager.deactivate(ctx, kind="directive", artifact_id="001-architectural-integrity-standard")

        assert result.deactivated == ["001-architectural-integrity-standard"]
        _target, data, _save = resolve_activation_write_target(ctx.require_repo_root())
        assert "activated_directives" not in data
        assert list(data["deactivated_directives"]) == ["001-architectural-integrity-standard"]

    def test_unknown_id_is_refused(self, manager: ActiveCharterManager, ctx: ProjectContext) -> None:
        with pytest.raises(UnknownActivationIdError):
            manager.deactivate(ctx, kind="directive", artifact_id="something")


# ---------------------------------------------------------------------------
# TestDeactivateExistingSet
# ---------------------------------------------------------------------------


class TestDeactivateExistingSet:
    def test_removes_artifact_from_list(self, manager: ActiveCharterManager, project_root: Path) -> None:
        seed_activation_ledger(project_root, activated_directives=["keep-me", "remove-me"])
        ctx = ProjectContext(repo_root=project_root)
        result = manager.deactivate(ctx, kind="directive", artifact_id="remove-me")
        assert "remove-me" in result.deactivated
        data = read_activation_ledger(project_root)
        assert "remove-me" not in data["activated_directives"]
        assert "keep-me" in data["activated_directives"]

    def test_refuses_an_id_neither_available_nor_listed(self, manager: ActiveCharterManager, project_root: Path) -> None:
        config = project_root / ".kittify" / "config.yaml"
        config.write_text(
            "activated_directives:\n  - something-else\n",
            encoding="utf-8",
        )
        ctx = ProjectContext(repo_root=project_root)
        before = config.read_bytes()
        # Neither available nor listed: the unknown-id refusal, nothing written (data-model.md §3).
        with pytest.raises(UnknownActivationIdError):
            manager.deactivate(ctx, kind="directive", artifact_id="not-present")
        assert config.read_bytes() == before

    def test_rejects_malformed_existing_activation_set(self, manager: ActiveCharterManager, project_root: Path) -> None:
        config = project_root / ".kittify" / "config.yaml"
        config.write_text("activated_directives: not-a-list\n", encoding="utf-8")
        ctx = ProjectContext(repo_root=project_root)

        with pytest.raises(ActiveCharterConfigError) as refused:
            manager.deactivate(ctx, kind="directive", artifact_id="x")

        assert re.search(r"activated_directives.*must be a list", refused.value.body)


# ---------------------------------------------------------------------------
# TestListActivated
# ---------------------------------------------------------------------------


class TestListActivated:
    def test_none_for_all_kinds_on_empty_config(self, manager: ActiveCharterManager, ctx: ProjectContext) -> None:
        """All kinds return None when config.yaml has no activation keys."""
        result = manager.list_activated(ctx)
        assert len(result) == 11
        for kind in YAML_KEY_MAP:
            assert result[kind] is None, f"Expected None for kind '{kind}'"

    def test_returns_frozenset_for_populated_kind(self, manager: ActiveCharterManager, project_root: Path) -> None:
        config = project_root / ".kittify" / "config.yaml"
        config.write_text(
            "activated_directives:\n  - aaa\n  - bbb\n",
            encoding="utf-8",
        )
        ctx = ProjectContext(repo_root=project_root)
        result = manager.list_activated(ctx)
        assert result["directive"] == frozenset({"aaa", "bbb"})
        # Kinds without a populated key stay unrestricted (None).
        assert result["tactic"] is None
        assert result["paradigm"] is None


# ---------------------------------------------------------------------------
# TestDeactivateCascadeAndInvalidKind
# ---------------------------------------------------------------------------


class TestDeactivateCascadeAndInvalidKind:
    def test_raises_value_error_for_unknown_kind(self, manager: ActiveCharterManager, ctx: ProjectContext) -> None:
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


class TestMissionTypeOrgLayerResolves:
    """FR-003: an org-tier pack's flat ``mission_types/`` directory (CL-005)
    makes a non-built-in mission-type id available."""

    def test_org_pack_mission_type_id_is_available_and_reports_org_layer(self, manager: ActiveCharterManager, ctx: ProjectContext, tmp_path: Path) -> None:
        org_root = tmp_path / "org-pack"
        _write_mission_type(org_root / "mission_types", "qa")

        assert "qa" in manager.list_available(ctx, kind="mission-type", layer_roots={"org": org_root})
        detailed = manager.list_available_detailed(ctx, kind="mission-type", layer_roots={"org": org_root})

        qa_entries = [entry for entry in detailed if entry.artifact_id == "qa"]
        assert [entry.layer for entry in qa_entries] == ["org"]


class TestMissionTypeProjectLayerResolves:
    """FR-005: the project-layer mission-type roster is flat --
    ``.kittify/missions/mission_types/*.yaml`` -- and makes a project-declared
    mission-type id available."""

    def test_project_pack_mission_type_id_is_available_and_reports_project_layer(
        self, manager: ActiveCharterManager, ctx: ProjectContext, project_root: Path
    ) -> None:
        kittify = project_root / ".kittify"
        _write_mission_type(kittify / "missions" / "mission_types", "qa")

        assert "qa" in manager.list_available(ctx, kind="mission-type", layer_roots={"project": kittify / "charter-packs"})
        detailed = manager.list_available_detailed(ctx, kind="mission-type", layer_roots={"project": kittify / "charter-packs"})

        qa_entries = [entry for entry in detailed if entry.artifact_id == "qa"]
        assert [entry.layer for entry in qa_entries] == ["project"]

    def test_missing_project_mission_types_dir_yields_no_contributions(self, manager: ActiveCharterManager, ctx: ProjectContext, project_root: Path) -> None:
        """spec.md edge case: a project layer root is supplied but
        ``.kittify/missions/mission_types/`` does not exist at all (the
        ``project_root`` fixture's ``.kittify`` has no ``missions/`` dir).
        This must resolve as "no project-layer contributions" -- no crash,
        no error -- while built-in ids still resolve normally (NFR-002).
        """
        kittify = project_root / ".kittify"

        result = manager.list_available(ctx, kind="mission-type", layer_roots={"project": kittify / "charter-packs"})

        assert "software-dev" in result  # built-in layer unaffected
        assert "qa" not in result


class TestMissionTypeLayerPrecedenceOrder:
    """FR-003: the built-in -> org -> project precedence order must be
    explicit and tested, not incidental to a dict's iteration order."""

    def test_same_id_in_org_and_project_reports_org_before_project(self, manager: ActiveCharterManager, ctx: ProjectContext, tmp_path: Path) -> None:
        org_root = tmp_path / "org-pack"
        _write_mission_type(org_root / "mission_types", "qa")
        project_kittify = tmp_path / "proj" / ".kittify"
        _write_mission_type(project_kittify / "missions" / "mission_types", "qa")

        detailed = manager.list_available_detailed(ctx, kind="mission-type", layer_roots={"org": org_root, "project": project_kittify / "charter-packs"})

        assert [entry.layer for entry in detailed if entry.artifact_id == "qa"] == ["org", "project"]
        layers = [entry.layer for entry in detailed]
        assert "built-in" in layers
        assert layers.index("built-in") < layers.index("org")


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

    def test_roster_and_mission_instance_coexist_without_collision(self, manager: ActiveCharterManager, ctx: ProjectContext, project_root: Path) -> None:
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
        available = manager.list_available(ctx, kind="mission-type", layer_roots={"project": kittify / "charter-packs"})
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

    def test_nested_per_type_subdirectory_no_longer_leaks(self, manager: ActiveCharterManager, ctx: ProjectContext, project_root: Path) -> None:
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

        available = manager.list_available(ctx, kind="mission-type", layer_roots={"project": kittify / "charter-packs"})

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
    def test_malformed_org_layer_yaml_is_not_silently_skipped(self, manager: ActiveCharterManager, ctx: ProjectContext, tmp_path: Path) -> None:
        """A malformed org-layer mission-type YAML must raise from
        ``list_available_detailed``/``list_available`` -- not be silently
        dropped from the catalog and mistaken for "does not exist"."""
        org_root = tmp_path / "org-pack"
        bad_file = org_root / "mission_types" / "broken.yaml"
        bad_file.parent.mkdir(parents=True, exist_ok=True)
        bad_file.write_text("key: [unterminated\n  - a\n", encoding="utf-8")

        with pytest.raises(ValueError, match=re.escape(f"Malformed YAML in mission-type file {bad_file}")):
            manager.list_available(ctx, kind="mission-type", layer_roots={"org": org_root})

    def test_unreadable_org_layer_directory_raises_naming_the_directory(
        self, manager: ActiveCharterManager, ctx: ProjectContext, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        org_root = tmp_path / "org-pack"
        mt_dir = org_root / "mission_types"
        _write_mission_type(mt_dir, "qa")

        # Inject the denial at the listing seam instead of chmod(0): root bypasses
        # file mode bits, so the chmod form skipped (or diverged) by uid (#5622).
        deny_path_method(monkeypatch, "iterdir", mt_dir)
        with pytest.raises(
            ValueError,
            match=re.escape(f"mission-type directory exists but cannot be read: {mt_dir}"),
        ):
            manager.list_available(ctx, kind="mission-type", layer_roots={"org": org_root})

    def test_activate_on_malformed_org_layer_type_raises_real_cause_not_generic_unknown_id(
        self, manager: ActiveCharterManager, ctx: ProjectContext, tmp_path: Path
    ) -> None:
        """End to end through ``activate()``: a malformed org-layer file must
        surface the real parse failure, never the misleading generic
        ``UnknownActivationIdError`` ("unknown ID") that WP05's tolerant
        scan produced pre-fix for this exact input."""
        org_root = tmp_path / "org-pack"
        bad_file = org_root / "mission_types" / "broken.yaml"
        bad_file.parent.mkdir(parents=True, exist_ok=True)
        bad_file.write_text("key: [unterminated\n  - a\n", encoding="utf-8")

        with pytest.raises(ValueError, match=re.escape(f"Malformed YAML in mission-type file {bad_file}")) as exc_info:
            manager.activate(ctx, kind="mission-type", artifact_id="broken", layer_roots={"org": org_root})

        assert not isinstance(exc_info.value, UnknownActivationIdError)
