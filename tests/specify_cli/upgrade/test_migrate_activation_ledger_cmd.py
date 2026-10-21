"""``spec-kitty migrate activation-ledger`` (WP08 T051, FR-021, data-model.md §11).

The command
runs exactly the ledger migration's move (the planner and apply functions of
``4.0.0rc8_activation_ledger``) and nothing else of an upgrade.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from kernel.activation_ledger_store import activation_ledger_path
from kernel.clock import now_utc
from specify_cli.cli.commands.migrate_cmd import app
from specify_cli.upgrade.ledger import MigrationLedger, build_record
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.registry import MigrationRegistry
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_MIGRATION_ID = "4.0.0rc8_activation_ledger"
_POINTER = ".kittify/charter/charter.yaml"
_LEDGER = ".kittify/charter/activation.yaml"
_CONFIG = ".kittify/config.yaml"


def _project(root: Path, *, charter: str = "activated_tactics:\n- T\n", config: str = "", migration_ledger: bool = False) -> Path:
    kittify = root / ".kittify"
    (kittify / "charter").mkdir(parents=True)
    (kittify / "config.yaml").write_text(f"vcs:\n  type: git\ncharter: {_POINTER}\n{config}", encoding="utf-8")
    (root / _POINTER).write_text(f"# authored\ncatalog: {{}}\n{charter}", encoding="utf-8")
    if migration_ledger:
        (kittify / "migration-ledger.jsonl").write_text("", encoding="utf-8")
    return root


def _files(root: Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted((root / ".kittify").rglob("*")) if path.is_file()}


def _run(root: Path, monkeypatch: pytest.MonkeyPatch, *args: str) -> Any:
    monkeypatch.chdir(root)
    return CliRunner().invoke(app, ["activation-ledger", *args])


def _payload(result: Any) -> dict[str, Any]:
    return dict(json.loads(result.output))


def _rc8_records(root: Path) -> list[str]:
    return [record.result for record in MigrationLedger(root).read_all() if record.id == _MIGRATION_ID]


def test_dry_run_lists_the_moves_and_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path, config="activated_tactics:\n- T\n")
    before = _files(root)

    result = _run(root, monkeypatch, "--dry-run", "--json")

    assert result.exit_code == 0, result.output
    assert _payload(result) == {
        "result": "dry_run",
        "moves": [
            {"key": "activated_tactics", "from": _POINTER, "to": _LEDGER},
            {"key": "activated_tactics", "from": _CONFIG, "to": _LEDGER},
        ],
        "refusal": None,
        "ledger_record": "not_recorded",
    }
    assert _files(root) == before


def test_move_then_rerun_is_a_noop(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path)

    moved = _run(root, monkeypatch, "--json")
    assert moved.exit_code == 0, moved.output
    assert _payload(moved)["result"] == "moved"
    assert yaml.safe_load(activation_ledger_path(root).read_text(encoding="utf-8")) == {"activated_tactics": ["T"]}
    after = _files(root)

    again = _run(root, monkeypatch, "--json")
    assert again.exit_code == 0, again.output
    assert _payload(again) == {"result": "noop", "moves": [], "refusal": None, "ledger_record": "not_recorded"}
    assert _files(root) == after


def test_human_output_names_the_moves(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path)
    dry = _run(root, monkeypatch, "--dry-run")
    assert dry.exit_code == 0, dry.output
    assert "activated_tactics" in dry.output and "Would move" in dry.output
    moved = _run(root, monkeypatch)
    assert moved.exit_code == 0, moved.output
    assert "Moved" in moved.output
    noop = _run(root, monkeypatch)
    assert "Nothing to do" in noop.output


@pytest.mark.parametrize(
    ("charter", "config", "key", "reason"),
    [
        ("activated_tactics:\n- T\n", "activated_tactics:\n- U\n", "activated_tactics", "divergent"),
        ("activated_tactics:\n- T\ndeactivated_tactics:\n- X\n", "", "deactivated_tactics", "legacy_deny_key"),
    ],
    ids=["divergence", "legacy-deny-key"],
)
def test_refusal_exits_1_and_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, charter: str, config: str, key: str, reason: str) -> None:
    root = _project(tmp_path, charter=charter, config=config, migration_ledger=True)
    before = _files(root)

    result = _run(root, monkeypatch, "--json")

    assert result.exit_code == 1, result.output
    payload = _payload(result)
    assert payload["result"] == "refused"
    assert payload["moves"] == []
    assert payload["ledger_record"] == "not_recorded"
    assert payload["refusal"]["key"] == key
    assert payload["refusal"]["reason"] == reason
    assert _POINTER in payload["refusal"]["files"]
    assert _files(root) == before


def test_human_refusal_exits_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path, config="activated_tactics:\n- U\n")
    result = _run(root, monkeypatch)
    assert result.exit_code == 1
    assert "activated_tactics" in result.output


def test_usage_error_exits_2(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path)
    assert _run(root, monkeypatch, "--no-such-flag").exit_code == 2


def test_outside_a_project_exits_1_with_a_json_envelope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    result = _run(tmp_path, monkeypatch, "--json")
    assert result.exit_code == 1
    assert json.loads(result.output)["ok"] is False


def test_a_malformed_surface_exits_1(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path, charter="activated_tactics: T\n")
    result = _run(root, monkeypatch, "--json")
    assert result.exit_code == 1
    assert json.loads(result.output)["ok"] is False


# --------------------------------------------------------------------------- #
# The migration-ledger record (T051.2)
# --------------------------------------------------------------------------- #


def test_records_success_when_the_migration_ledger_exists(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path, migration_ledger=True)

    result = _run(root, monkeypatch, "--json")

    assert result.exit_code == 0, result.output
    assert _payload(result)["ledger_record"] == "written"
    assert _rc8_records(root) == ["success"]

    again = _run(root, monkeypatch, "--json")
    assert _payload(again) == {"result": "noop", "moves": [], "refusal": None, "ledger_record": "written"}
    assert _rc8_records(root) == ["success"]

    auto_discover_migrations()
    selected = {m.migration_id for m in MigrationRegistry.get_applicable("0.0.0", "99.0.0", project_path=root)}
    assert _MIGRATION_ID not in selected


def test_records_nothing_without_a_migration_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path)
    metadata = ProjectMetadata(version="4.0.0rc7", initialized_at=now_utc(), python_version="3.11", platform="test", platform_version="test")
    metadata.record_migration("4.0.0rc7_track_charter_pack_yaml", "success")
    metadata.save(root / ".kittify")
    metadata_before = (root / ".kittify" / "metadata.yaml").read_bytes()

    result = _run(root, monkeypatch, "--json")

    assert result.exit_code == 0, result.output
    assert _payload(result)["ledger_record"] == "not_recorded"
    assert not (root / ".kittify" / "migration-ledger.jsonl").exists()
    assert (root / ".kittify" / "metadata.yaml").read_bytes() == metadata_before


def test_without_a_migration_ledger_a_later_upgrade_selects_rc8_and_skips_it(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path)
    assert _run(root, monkeypatch, "--json").exit_code == 0
    moved = _files(root)

    auto_discover_migrations()
    selected = {m.migration_id: m for m in MigrationRegistry.get_applicable("0.0.0", "99.0.0", project_path=root)}
    assert _MIGRATION_ID in selected
    migration = selected[_MIGRATION_ID]
    runner = MigrationRunner(root)
    metadata = runner._create_initial_metadata("4.0.0rc7")

    preview, preview_status = runner._apply_migration(migration, metadata, dry_run=True)
    assert preview_status == "skipped"
    assert any("not needed" in warning for warning in preview.warnings)
    assert _files(root) == moved

    _result, status = runner._apply_migration(migration, metadata, dry_run=False)
    assert status == "skipped"
    assert _rc8_records(root) == ["skipped"]
    assert yaml.safe_load(activation_ledger_path(root).read_text(encoding="utf-8")) == {"activated_tactics": ["T"]}


def test_a_ledger_record_written_once_is_not_duplicated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path, migration_ledger=True)
    auto_discover_migrations()
    rc8 = MigrationRegistry.get_by_id(_MIGRATION_ID)
    assert rc8 is not None
    MigrationLedger(root).append(build_record(rc8, "success"))

    result = _run(root, monkeypatch, "--json")

    assert _payload(result)["ledger_record"] == "written"
    assert _rc8_records(root) == ["success"]


def test_a_lagging_stamp_is_nothing_to_do_and_never_prints_moved(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Review cycle 1: a ledger project whose manifest stamp lags (a hand-edit) is a no-op."""
    root = _project(tmp_path, charter="")
    (root / ".kittify" / "charter" / "activation.yaml").write_text("activated_tactics:\n- T\n", encoding="utf-8")
    from charter.activation.synthesizer.manifest import MANIFEST_PATH, SynthesisManifest, finalize_manifest
    from charter.activation.synthesizer.synthesize_pipeline import canonical_yaml
    from charter.bundle import compute_bundle_content_hash

    stamped = finalize_manifest(
        SynthesisManifest(
            created_at="2026-10-19T00:00:00Z",
            run_id="01TESTRUN",
            adapter_id="project-direct-write",
            adapter_version="1",
            synthesizer_version="1",
            manifest_hash="0" * 64,
            built_in_only=False,
            bundle_content_hash=compute_bundle_content_hash(root),
        )
    )
    (root / MANIFEST_PATH).write_text(canonical_yaml(stamped.model_dump(mode="python")).decode("utf-8"), encoding="utf-8")
    with (root / _POINTER).open("a", encoding="utf-8") as handle:
        handle.write("# hand edit after synthesis\n")
    before = _files(root)

    dry = _run(root, monkeypatch, "--dry-run", "--json")
    assert _payload(dry)["result"] == "noop"
    human = _run(root, monkeypatch)
    assert human.exit_code == 0, human.output
    assert "Moved" not in human.output
    assert "Nothing to do" in human.output
    assert _files(root) == before
