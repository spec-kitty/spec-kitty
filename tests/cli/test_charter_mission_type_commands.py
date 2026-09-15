"""Consumed CLI contracts for mission-type discovery.

Each test crosses Typer's public command boundary.  Table-field spot checks,
help registration, and charter-layer source-shape checks live elsewhere or are
implied by these executable routes.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.charter import charter_app
from specify_cli.cli.commands.doctrine import app as doctrine_app
from specify_cli.cli.commands.mission_type import app as mission_type_app


runner = CliRunner()
pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _write_org_mission_type_yaml(
    org_root: Path,
    mission_type_id: str,
    *,
    action_sequence: list[str],
) -> None:
    """Write a minimal org-layer mission-type YAML (CL-005 flat layout)."""
    mt_dir = org_root / "mission_types"
    mt_dir.mkdir(parents=True, exist_ok=True)
    lines = [
        "schema_version: 1",
        f"id: {mission_type_id}",
        f"display_name: {mission_type_id.title()}",
        "action_sequence:",
        *(f"  - {step}" for step in action_sequence),
    ]
    (mt_dir / f"{mission_type_id}.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_org_mission_step_yaml(
    org_root: Path,
    mission_type_id: str,
    step_id: str,
    *,
    artifact_key: str,
    template_file: str,
    sequence_index: int = 0,
) -> None:
    """Write a step.yaml in the org-pack layout carrying a template ref.

    Mirrors ``tests/charter/test_mission_type_profiles.py``'s own
    ``_write_org_mission_step_yaml`` helper (org-pack layout convention:
    ``{org_root}/mission-steps/{mission_type_id}/{step_id}/step.yaml``).
    """
    step_dir = org_root / "mission-steps" / mission_type_id / step_id
    step_dir.mkdir(parents=True, exist_ok=True)
    (step_dir / "step.yaml").write_text(
        f"id: {step_id}\n"
        f"display_name: {step_id.title()}\n"
        "step_type: agent\n"
        "prompt_template: prompt.md\n"
        "in_action_sequence: true\n"
        f"sequence_index: {sequence_index}\n"
        "template:\n"
        f"  artifact_key: {artifact_key}\n"
        f"  template_file: {template_file}\n",
        encoding="utf-8",
    )


def _git_init_minimal(repo_root: Path) -> None:
    """Mirrors ``tests/charter/test_mission_type_profiles.py``'s own helper."""
    for cmd in (
        ["git", "init", "--initial-branch=main"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Test"],
        ["git", "config", "commit.gpgsign", "false"],
    ):
        subprocess.run(cmd, cwd=repo_root, check=True, capture_output=True)


def test_charter_mission_type_list_json_contract() -> None:
    """The canonical list route emits usable activated mission descriptors."""
    result = runner.invoke(charter_app, ["mission-type", "list", "--json"])
    assert result.exit_code == 0, result.output

    rows = json.loads(result.output)
    assert rows
    assert all({"id", "source_layer", "display_name", "action_sequence"} <= row.keys() and isinstance(row["action_sequence"], list) for row in rows)


def test_mission_type_app_registers_list_exactly_once() -> None:
    """No shadowed duplicate ``list`` command handler survives on the app.

    Typer silently lets the *last* registration of a given command name win,
    with no error or warning for the earlier, now-unreachable one. Asserting
    on the resolved command's *output* alone would not catch a lingering
    shadowed duplicate (the surviving handler's output already looked
    correct even while shadowed) — this asserts on registration *count*,
    which is the only signal a stale duplicate handler actually trips.
    """
    list_commands = [cmd for cmd in mission_type_app.registered_commands if cmd.name == "list"]
    assert len(list_commands) == 1
    assert list_commands[0].callback is not None
    assert list_commands[0].callback.__name__ == "list_mission_types"


def test_mission_type_list_alias_reaches_the_same_catalog() -> None:
    """The documented top-level alias resolves the canonical catalog."""
    alias = runner.invoke(mission_type_app, ["list", "--json"])
    canonical = runner.invoke(charter_app, ["mission-type", "list", "--json"])
    assert alias.exit_code == canonical.exit_code == 0
    assert {row["id"] for row in json.loads(alias.output)} == {row["id"] for row in json.loads(canonical.output)}


def test_mission_type_show_json_contract() -> None:
    """A selected descriptor exposes the fields consumed by callers."""
    result = runner.invoke(mission_type_app, ["show", "software-dev", "--json"])
    assert result.exit_code == 0, result.output

    row = json.loads(result.output)
    assert row["id"] == "software-dev"
    assert row["source_layer"] == "built-in"
    assert isinstance(row["action_sequence"], list) and row["action_sequence"]


def test_mission_type_show_rejects_an_unknown_id() -> None:
    """The negative route fails closed and identifies the rejected input."""
    result = runner.invoke(mission_type_app, ["show", "unknown-type"])
    assert result.exit_code == 1
    assert "unknown-type" in result.output


def test_charter_mission_type_list_reports_real_layer_for_activated_org_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FR-006: an activated org-layer type reports its real ``source_layer``.

    Pre-fix, ``charter_mission_type_list`` only ever queries the built-in-only
    ``MissionTypeRepository.default()``; an activated non-built-in id falls
    into the ``source_layer: "unknown"`` / ``action_sequence: []`` tolerate
    branch even though it resolves fine end to end (User Story 1 AC1).
    """
    from charter.offering.missions.mission_type_repository import MissionTypeRepository

    from charter.activation.pack_context import PackContext

    org_root = tmp_path / "org-pack"
    _write_org_mission_type_yaml(org_root, "qa", action_sequence=["design", "implement"])
    pack_context = PackContext(
        activated_kinds=frozenset(),
        activated_mission_types=frozenset({"qa"}),
        pack_roots=(tmp_path / "unused-builtin-placeholder", org_root),
        org_pack_names=("org-pack",),
        repo_root=tmp_path,
    )
    monkeypatch.chdir(tmp_path)
    MissionTypeRepository.cache_clear()
    try:
        with patch("charter.activation.pack_context.PackContext.from_config", return_value=pack_context):
            result = runner.invoke(charter_app, ["mission-type", "list", "--json"])
    finally:
        MissionTypeRepository.cache_clear()

    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)
    qa_row = next(row for row in rows if row["id"] == "qa")
    assert qa_row["source_layer"] == "org"
    assert qa_row["action_sequence"] == ["design", "implement"]


# ---------------------------------------------------------------------------
# T020 (capstone) -- SC-001 end-to-end regression: an org-pack mission type
# with a populated action_sequence, activated in a test project, resolves
# through mission create, charter mission-type list, mission-type show, and
# doctrine mission-type list with correct, non-empty, non-"unknown" output
# at every one of those four CLI surfaces (User Story 1's own Independent
# Test, verbatim).
# ---------------------------------------------------------------------------


def test_sc001_org_pack_mission_type_resolves_across_all_four_cli_surfaces(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SC-001 capstone: T016-T019's fixes assembled into one coherent scenario."""
    from charter.offering.missions.mission_type_repository import MissionTypeRepository

    from charter.activation.mission_type_profiles import resolve_mission_type_context
    from charter.activation.pack_context import PackContext
    from specify_cli.core.mission_creation import create_mission_core

    _git_init_minimal(tmp_path)
    subprocess.run(
        ["git", "commit", "-m", "init", "--allow-empty"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    # create_mission_core commits planning artifacts via safe_commit, which
    # refuses protected branches (e.g. "main") since FR-001 removed the
    # swallowed-exception fallback -- check out a non-protected feature
    # branch first, exactly as the product's own error message instructs.
    subprocess.run(
        ["git", "checkout", "-b", "feature/qa-mission"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    org_root = tmp_path / "org-pack"
    _write_org_mission_type_yaml(org_root, "qa", action_sequence=["design", "implement"])
    _write_org_mission_step_yaml(
        org_root,
        "qa",
        "design",
        artifact_key="spec",
        template_file="qa-spec-template.md",
    )
    _write_org_mission_step_yaml(
        org_root,
        "qa",
        "implement",
        artifact_key="implementation",
        template_file="qa-implementation-template.md",
        sequence_index=1,
    )
    # create_mission_core's template-copy step resolves the declared
    # template_file through runtime.resolver's own 5-tier chain (C-004: out
    # of this mission's scope) -- for a scratch, org-only type, the project
    # override tier is the only tier reachable without touching the real
    # global home or package defaults.
    overrides_dir = tmp_path / ".kittify" / "overrides" / "templates"
    overrides_dir.mkdir(parents=True, exist_ok=True)
    (overrides_dir / "qa-spec-template.md").write_text("# QA Spec\n", encoding="utf-8")
    (overrides_dir / "qa-implementation-template.md").write_text(
        "# QA Implementation\n",
        encoding="utf-8",
    )
    pack_context = PackContext(
        activated_kinds=frozenset(),
        activated_mission_types=frozenset({"qa"}),
        pack_roots=(tmp_path / "unused-builtin-placeholder", org_root),
        org_pack_names=("org-pack",),
        repo_root=tmp_path,
    )

    monkeypatch.chdir(tmp_path)
    MissionTypeRepository.cache_clear()
    try:
        with patch("charter.activation.pack_context.PackContext.from_config", return_value=pack_context):
            # Surface 1: mission create -- the created mission's projected
            # action sequence and template set match the org-pack's declared
            # steps exactly (User Story 1 AC2).
            result = create_mission_core(
                tmp_path,
                "qa-mission",
                mission="qa",
                friendly_name="QA Mission",
                purpose_tldr="Exercise the SC-001 capstone end-to-end.",
                purpose_context="Confirms all four CLI surfaces resolve 'qa' for real.",
            )
            assert result.meta.get("mission_type") == "qa"
            bundle = resolve_mission_type_context(tmp_path, mission_type="qa")
            assert bundle.action_sequence == ["design", "implement"]
            assert dict(bundle.template_set) == {
                "spec": "qa-spec-template.md",
                "implementation": "qa-implementation-template.md",
            }

            # Surface 2: charter mission-type list (FR-006) -- real layer,
            # not "unknown".
            list_result = runner.invoke(charter_app, ["mission-type", "list", "--json"])
            assert list_result.exit_code == 0, list_result.output
            qa_row = next(
                row for row in json.loads(list_result.output) if row["id"] == "qa"
            )
            assert qa_row["source_layer"] == "org"
            assert qa_row["action_sequence"] == ["design", "implement"]

            # Surface 3: mission-type show (FR-007) -- succeeds (not
            # typer.Exit(1)) with the correct layer on both --json and the
            # default panel output.
            show_json = runner.invoke(mission_type_app, ["show", "qa", "--json"])
            assert show_json.exit_code == 0, show_json.output
            show_data = json.loads(show_json.output.strip())
            assert show_data["source_layer"] == "org"
            assert show_data["action_sequence"] == ["design", "implement"]

            show_panel = runner.invoke(mission_type_app, ["show", "qa"])
            assert show_panel.exit_code == 0, show_panel.output
            assert "Source Layer: org" in show_panel.output

            # Surface 4: doctrine mission-type list (FR-008) -- the type
            # appears with the correct layer, a true all-layers listing.
            #
            # CR-02 (mission charter-code-topology-01M152G1 S4): `doctrine_app`
            # now carries a deprecation-notice `@app.callback()` that writes
            # to stderr (`err=True`) -- parse `.stdout` (stdout only), not
            # `.output` (Click 8.2+'s stdout+stderr merge), so that notice
            # never lands inside the JSON payload under test here.
            doctrine_result = runner.invoke(doctrine_app, ["mission-type", "list", "--json"])
            assert doctrine_result.exit_code == 0, doctrine_result.output
            doctrine_row = next(
                row
                for row in json.loads(doctrine_result.stdout.strip())
                if row["id"] == "qa"
            )
            assert doctrine_row["source_layer"] == "org"
    finally:
        MissionTypeRepository.cache_clear()
