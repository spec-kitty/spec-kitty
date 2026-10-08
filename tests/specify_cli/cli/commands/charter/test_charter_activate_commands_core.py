"""Tests for WP06/T024: spec-kitty charter activate refactored command.

Split from the original `test_charter_activate_commands.py` (ci-test-topology-
performance-01KXBJRT WP05/T021, FR-005) to break the `fast-tests-cli` job's
single-worker tail: `--dist loadfile` pins every test in a file to one xdist
worker, so one heavy monolith caps the job regardless of idle workers.

This sibling covers the happy-path/error/misc tests of `TestActivateCommand`
(the lighter half by measured duration) — the cascade-flag and
cascade-output-absence tests live in the `_cascade_flags` and
`_cascade_output` siblings.

Covers:
- T024: New activate API: <kind> <id> [--cascade], writes to config.yaml

The old API (--action-sequence, mission-type subcommand, override file) is removed.
All assertions for override-file behavior are also removed.
The activate_mission_type_override function is removed (FR-014: activation now goes
through ActiveCharterManager.activate() which writes to config.yaml directly).
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app

runner = CliRunner()

pytestmark = [pytest.mark.fast]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def project_root(tmp_path: Path) -> Path:
    """A minimal project with .kittify/config.yaml.

    Carries ``mission_type_activations`` (WP04, C-A1): the provisioned
    charter is the sole mission-type activation authority, so
    ``PackContext.from_config`` fails closed when the key is absent.
    """
    kittify = tmp_path / ".kittify"
    kittify.mkdir()
    (kittify / "config.yaml").write_text(
        "mission_type_activations:\n  - software-dev\n", encoding="utf-8"
    )
    return tmp_path


def _invoke_activate(project_root: Path, *args: str) -> object:
    """Invoke charter activate with --repo-root placed before positional args."""
    return runner.invoke(
        charter_app,
        ["activate", "--repo-root", str(project_root), *args],
        catch_exceptions=False,
    )


# ---------------------------------------------------------------------------
# T024 — new activate API: <kind> <id> [--cascade] (happy-path/error/misc)
# ---------------------------------------------------------------------------


class TestActivateCommand:
    def test_activate_directive_happy_path(self, project_root: Path) -> None:
        """Activating a directive kind writes to config.yaml."""
        result = _invoke_activate(
            project_root,
            "directive",
            "001-architectural-integrity-standard",
        )
        assert result.exit_code == 0, result.output
        config = project_root / ".kittify" / "config.yaml"
        data = yaml.safe_load(config.read_text())
        assert "001-architectural-integrity-standard" in data["activated_directives"]

    def test_activate_config_yaml_updated(self, project_root: Path) -> None:
        """config.yaml is updated, not an override file."""
        _invoke_activate(
            project_root,
            "directive",
            "003-decision-documentation-requirement",
        )
        config = project_root / ".kittify" / "config.yaml"
        data = yaml.safe_load(config.read_text())
        assert "activated_directives" in data
        assert "003-decision-documentation-requirement" in data["activated_directives"]

    def test_activate_unknown_artifact_id_exits_1_without_mutating(self, project_root: Path) -> None:
        result = _invoke_activate(project_root, "directive", "not-a-real-directive")
        assert result.exit_code == 1
        # WP09: activation now delegates to the engine, which raises the typed
        # UnknownActivationIdError (a ValueError subclass) with an actionable
        # "Unknown <kind> ID ..." message. The CLI's existing `except ValueError`
        # still catches it and exits 1 without mutating config.yaml.
        assert "Unknown directive ID" in result.output

        config = project_root / ".kittify" / "config.yaml"
        data = yaml.safe_load(config.read_text()) or {}
        assert "activated_directives" not in data

    def test_activate_unknown_kind_exits_1(self, project_root: Path) -> None:
        """Activating with an unknown kind exits with code 1."""
        result = runner.invoke(
            charter_app,
            ["activate", "--repo-root", str(project_root), "nonsense-kind", "some-id"],
        )
        assert result.exit_code == 1
        assert "Unknown kind" in result.output

    def test_activate_mission_type_kind(self, project_root: Path) -> None:
        """Activating mission-type kind writes to mission_type_activations key."""
        result = _invoke_activate(project_root, "mission-type", "software-dev")
        assert result.exit_code == 0, result.output
        config = project_root / ".kittify" / "config.yaml"
        data = yaml.safe_load(config.read_text())
        assert "software-dev" in data["mission_type_activations"]

    def test_activate_already_active_emits_warning(self, project_root: Path) -> None:
        """Activating an already-active artifact emits a warning."""
        # First activation
        _invoke_activate(project_root, "directive", "001-architectural-integrity-standard")
        # Second activation of the same artifact
        result = _invoke_activate(project_root, "directive", "001-architectural-integrity-standard")
        assert result.exit_code == 0, result.output
        assert "Warning" in result.output or "already activated" in result.output.lower()

    def test_activate_no_action_sequence_flag_exists(self) -> None:
        """The old --action-sequence flag is no longer present."""
        result = runner.invoke(charter_app, ["activate", "--help"])
        assert "action-sequence" not in result.output.lower()
        assert "action_sequence" not in result.output.lower()

    def test_activate_output_contains_activated(self, project_root: Path) -> None:
        """Successful activation prints 'Activated' in output."""
        (project_root / ".kittify" / "config.yaml").write_text(
            "activated_tactics: []\nmission_type_activations:\n  - software-dev\n",
            encoding="utf-8",
        )
        result = _invoke_activate(project_root, "tactic", "acceptance-test-first")
        assert result.exit_code == 0, result.output
        assert "Activated" in result.output


# ---------------------------------------------------------------------------
# WP01 (mission charter-activate-empty-action-sequence-01M0STSX) — T002/T003:
# `charter activate mission-type <T>` activation-time empty-action-sequence
# gate (FR-001/NFR-001).
#
# SK-81 methodological trap (binding, copied verbatim from plan.md /
# tasks/WP01-activation-empty-action-sequence-gate.md -- do not paraphrase
# or shorten): two prior observations of this defect recorded activation as
# already failing by pre-seeding the candidate into `mission_type_activations`
# before calling activation -- under that precondition the existing
# read-path guard fires and the command never demonstrates the actual
# defect. The regression test below uses the natural operator path instead:
# the org pack is declared and `<T>` is left OUT of `mission_type_activations`
# before the command under test is invoked; the org-pack YAML and the
# activation-set config are written by two SEPARATE calls, never combined
# into one. A pre-seeded-only test would pass with zero code changed
# (spec.md SC-004) and is NOT accepted as coverage for FR-001/SC-001.
#
# This file has no `CliRunner`-free precedent for cross-importing the
# private test helpers from `tests/charter/test_mission_type_profiles.py`
# (`_write_layered_mission_type_yaml` / `_write_org_pack_config`), so the
# two-call fixture shape is reproduced locally below rather than imported.
# ---------------------------------------------------------------------------


def _write_candidate_mission_type_yaml(
    org_root: Path,
    mission_type_id: str,
    *,
    action_sequence: list[str] | None = None,
    extends: str | None = None,
) -> None:
    """Write a minimal org-pack mission-type YAML directly.

    ``action_sequence=None`` omits the field entirely (the CL-003
    empty-action-sequence edge case this gate closes).
    """
    mission_types_dir = org_root / "mission_types"
    mission_types_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "schema_version: 1",
        f"id: {mission_type_id}",
        f"display_name: {mission_type_id.title()}",
    ]
    if action_sequence is not None:
        lines.append("action_sequence:")
        lines.extend(f"  - {step}" for step in action_sequence)
    if extends is not None:
        lines.append(f"extends: {extends}")
    (mission_types_dir / f"{mission_type_id}.yaml").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def _write_org_pack_activation_config(
    tmp_path: Path,
    *,
    org_root: Path,
    org_pack_name: str,
    activated_mission_types: list[str],
) -> Path:
    """Write ``.kittify/config.yaml`` declaring the org pack + the
    mission-type activation set -- a SEPARATE call from the YAML fixture
    above (SK-81 trap: never combine the two into one call).
    """
    kittify = tmp_path / ".kittify"
    kittify.mkdir(exist_ok=True)
    lines = ["mission_type_activations:"]
    for mission_type in activated_mission_types:
        lines.append(f"  - {mission_type}")
    lines += [
        "doctrine:",
        "  org:",
        "    packs:",
        f"      - name: {org_pack_name}",
        f"        local_path: {org_root}",
    ]
    (kittify / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return tmp_path


class TestActivateMissionTypeEmptyActionSequenceGate:
    """WP01: FR-001/NFR-001 activation-time gate, natural-operator-path
    fixture per the SK-81 methodological trap above.
    """

    def test_empty_action_sequence_refuses_activation_without_mutating_config(
        self, tmp_path: Path
    ) -> None:
        org_root = tmp_path / "org-pack"
        _write_candidate_mission_type_yaml(org_root, "qa", action_sequence=None)
        project_root = _write_org_pack_activation_config(
            tmp_path,
            org_root=org_root,
            org_pack_name="acme",
            activated_mission_types=[],
        )

        config_path = project_root / ".kittify" / "config.yaml"
        before = yaml.safe_load(config_path.read_text())
        # SK-81 trap guard: confirm the natural-operator precondition
        # immediately before invoking -- "qa" must NOT already be
        # registered.
        assert "qa" not in (before.get("mission_type_activations") or [])
        before_bytes = config_path.read_bytes()

        result = _invoke_activate(project_root, "mission-type", "qa")

        assert result.exit_code != 0, result.output
        assert "qa" in result.output
        assert "org" in result.output
        assert config_path.read_bytes() == before_bytes

    def test_extends_fallback_non_empty_parent_activates_successfully(
        self, tmp_path: Path
    ) -> None:
        """AC4/FR-005: a candidate whose own ``action_sequence`` is empty
        but whose single-level ``extends`` parent resolves non-empty
        activates successfully.

        Documented exception (plan.md, WP01 T003): this assertion is
        expected GREEN already at the T003 commit -- it pins TODAY's
        unconditional-success behavior for an unregistered candidate, not
        the fix; activation already unconditionally succeeds today for any
        unregistered candidate, including one whose extends chain would
        resolve non-empty. Only the sibling unit-level extends test in
        ``tests/charter/test_mission_type_profiles.py`` is RED at that
        commit.
        """
        org_root = tmp_path / "org-pack"
        _write_candidate_mission_type_yaml(
            org_root, "parent", action_sequence=["specify", "plan"]
        )
        _write_candidate_mission_type_yaml(
            org_root, "qa", action_sequence=None, extends="parent"
        )
        project_root = _write_org_pack_activation_config(
            tmp_path,
            org_root=org_root,
            org_pack_name="acme",
            activated_mission_types=[],
        )

        result = _invoke_activate(project_root, "mission-type", "qa")

        assert result.exit_code == 0, result.output
        config = project_root / ".kittify" / "config.yaml"
        data = yaml.safe_load(config.read_text())
        assert "qa" in data["mission_type_activations"]
