"""Red-first unit tests for the two-partition migration ledger (WP01 / IC-01).

Covers FR-001 (ledger module), FR-002 (clone_local_effect routing key),
FR-003 (record shape round-trip), FR-009 (legacy-id normalization on read),
FR-013 (tracked vs clone-local partition), FR-014 / NFR-001 (atomic,
single-writer, no torn file).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from kernel.clock import now_utc, parse_iso

from specify_cli.upgrade.ledger import (
    CLONE_LOCAL_LEDGER_RELPATH,
    TRACKED_LEDGER_RELPATH,
    LedgerRecord,
    MigrationLedger,
    assemble_report,
    build_record,
    compute_content_hash,
)


class _FakeMigration:
    """Duck-typed migration for ledger tests (no BaseMigration import — C/FR-005)."""

    def __init__(
        self,
        migration_id: str,
        *,
        clone_local_effect: bool = False,
        content_hash_sources: tuple[str, ...] = (),
        detect_result: bool = False,
    ) -> None:
        self.migration_id = migration_id
        self.clone_local_effect = clone_local_effect
        self._detect_result = detect_result
        if content_hash_sources:
            self.content_hash_sources = content_hash_sources

    def detect(self, project_path: Path) -> bool:  # noqa: ARG002 - duck-typed detect
        return self._detect_result


def _record(migration_id: str, *, clone_local: bool = False, content_hash: str = "sha256:deadbeef") -> LedgerRecord:
    return LedgerRecord(
        id=migration_id,
        applied_at=now_utc(),
        result="success",
        identity=migration_id,
        content_hash=content_hash,
        cli_version="4.0.0rc8",
        clone_local=clone_local,
    )


def test_record_round_trips_through_jsonl() -> None:
    rec = _record("0.2.0_specify_to_kittify")
    restored = LedgerRecord.from_dict(json.loads(json.dumps(rec.to_dict())))
    assert restored.id == rec.id
    assert restored.result == "success"
    assert restored.identity == rec.identity
    assert restored.content_hash == rec.content_hash
    assert restored.cli_version == "4.0.0rc8"
    assert restored.clone_local is False
    # tracked records omit the clone_local key entirely (ADR table)
    assert "clone_local" not in rec.to_dict()


def test_clone_local_record_carries_the_flag() -> None:
    rec = _record("0.13.1_exclude_worktrees", clone_local=True)
    assert rec.to_dict()["clone_local"] is True
    assert LedgerRecord.from_dict(rec.to_dict()).clone_local is True


def test_append_round_trips_in_both_partitions(tmp_path: Path) -> None:
    ledger = MigrationLedger(tmp_path)
    tracked = _record("0.2.0_specify_to_kittify")
    clone = _record("0.13.1_exclude_worktrees", clone_local=True)

    ledger.append(tracked)
    ledger.append(clone)

    assert [r.id for r in ledger.read_tracked()] == ["0.2.0_specify_to_kittify"]
    assert [r.id for r in ledger.read_clone_local()] == ["0.13.1_exclude_worktrees"]
    # Physical partition: tracked file is the sibling of metadata.yaml; the
    # clone-local file lives inside the already-ignored .kittify/migrations/.
    assert (tmp_path / TRACKED_LEDGER_RELPATH).exists()
    assert (tmp_path / CLONE_LOCAL_LEDGER_RELPATH).exists()


def test_append_routes_by_clone_local_effect(tmp_path: Path) -> None:
    ledger = MigrationLedger(tmp_path)
    ledger.append(_record("tracked_one"))
    ledger.append(_record("clone_one", clone_local=True))

    tracked_mig = _FakeMigration("tracked_one", clone_local_effect=False)
    clone_mig = _FakeMigration("clone_one", clone_local_effect=True)

    assert [r.id for r in ledger.applicable_records_for(tracked_mig)] == ["tracked_one"]
    assert [r.id for r in ledger.applicable_records_for(clone_mig)] == ["clone_one"]
    # routing key is the migration's clone_local_effect, not a reselection trigger
    assert ledger.applicable_records_for(clone_mig) != ledger.applicable_records_for(tracked_mig)


def test_legacy_id_and_charter_id_resolve_to_one_record(tmp_path: Path) -> None:
    """FR-009: a constitution-era id and its charter-era id collapse to one record on read."""
    path = tmp_path / TRACKED_LEDGER_RELPATH
    path.parent.mkdir(parents=True, exist_ok=True)
    legacy = _record("2.0.0_constitution_directory")
    charter = _record("2.0.0_charter_directory")
    path.write_text(
        json.dumps(legacy.to_dict()) + "\n" + json.dumps(charter.to_dict()) + "\n",
        encoding="utf-8",
    )

    ledger = MigrationLedger(tmp_path)
    ids = [r.id for r in ledger.read_tracked()]
    # both normalize to the charter-era id and collapse to a single record
    assert ids == ["2.0.0_charter_directory"]


def test_append_is_atomic_leaving_no_torn_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-001/FR-014: a crash mid-append leaves the valid old ledger, never a partial file."""
    ledger = MigrationLedger(tmp_path)
    ledger.append(_record("first"))

    import specify_cli.core.atomic as atomic_mod

    real_replace = atomic_mod.os.replace

    def _boom(src: str, dst: str) -> None:  # noqa: ARG001 - simulate a crash during replace
        raise OSError("simulated crash during atomic replace")

    monkeypatch.setattr(atomic_mod.os, "replace", _boom)
    with pytest.raises(OSError, match="simulated crash"):
        ledger.append(_record("second"))
    monkeypatch.setattr(atomic_mod.os, "replace", real_replace)

    # The ledger on disk is still the complete, valid pre-crash content.
    records = ledger.read_tracked()
    assert [r.id for r in records] == ["first"]
    # No leftover temp files beside the ledger.
    assert not list((tmp_path / ".kittify").glob(".atomic-*"))


def test_build_record_computes_identity_and_hash_and_routes(tmp_path: Path) -> None:
    mig = _FakeMigration("tracked_one", clone_local_effect=False)
    rec = build_record(mig, "success", cli_version="4.0.0rc8")
    assert rec.id == "tracked_one"
    assert rec.identity == "tracked_one"  # defensive getattr default (base.py ClassVar lands in WP02)
    assert rec.content_hash.startswith("sha256:")
    assert rec.clone_local is False

    clone = _FakeMigration("clone_one", clone_local_effect=True)
    assert build_record(clone, "success", cli_version="4.0.0rc8").clone_local is True


def test_compute_content_hash_is_deterministic_over_declared_sources(tmp_path: Path) -> None:
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text("alpha", encoding="utf-8")
    b.write_text("beta", encoding="utf-8")
    mig = _FakeMigration("multi", content_hash_sources=(str(b), str(a)))
    first = compute_content_hash(mig)
    second = compute_content_hash(mig)
    assert first == second  # sorted + concatenated: order of declaration does not matter
    # a different payload yields a different hash
    b.write_text("beta-changed", encoding="utf-8")
    assert compute_content_hash(mig) != first


def test_drift_for_flags_changed_source(tmp_path: Path) -> None:
    src = tmp_path / "mod.py"
    src.write_text("v1", encoding="utf-8")
    mig = _FakeMigration("drifty", content_hash_sources=(str(src),))
    ledger = MigrationLedger(tmp_path)
    ledger.append(build_record(mig, "success", cli_version="4.0.0rc8"))

    assert ledger.drift_for(mig) is False  # unchanged source
    src.write_text("v2", encoding="utf-8")
    assert ledger.drift_for(mig) is True  # source changed under a stable identity
    assert ledger.drift_for(_FakeMigration("never_recorded")) is None


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)


def test_partition_paths_match_git_ignore_semantics(tmp_path: Path) -> None:
    """FR-013: the tracked ledger is NOT ignored; the clone-local ledger IS (via git check-ignore)."""
    _git(tmp_path, "init")
    (tmp_path / ".gitignore").write_text(".kittify/migrations/\n", encoding="utf-8")

    tracked = _git(tmp_path, "check-ignore", TRACKED_LEDGER_RELPATH)
    clone = _git(tmp_path, "check-ignore", CLONE_LOCAL_LEDGER_RELPATH)

    assert tracked.returncode != 0, f"tracked ledger must not be ignored, got {tracked.stdout!r}"
    assert clone.returncode == 0, "clone-local ledger must be ignored by .kittify/migrations/"
    assert clone.stdout.strip() == CLONE_LOCAL_LEDGER_RELPATH


def test_applied_at_round_trips_as_iso(tmp_path: Path) -> None:
    rec = _record("x")
    restored = LedgerRecord.from_dict(rec.to_dict())
    assert parse_iso(restored.applied_at.isoformat()) == rec.applied_at


def test_assemble_report_captures_partition_applied_and_in_place(tmp_path: Path) -> None:
    tracked = _FakeMigration("tracked_rep", clone_local_effect=False)
    clone_present = _FakeMigration("clone_present_rep", clone_local_effect=True, detect_result=False)
    clone_absent = _FakeMigration("clone_absent_rep", clone_local_effect=True, detect_result=True)
    pending = _FakeMigration("pending_rep", clone_local_effect=False)

    ledger = MigrationLedger(tmp_path)
    ledger.append(build_record(tracked, "success", cli_version="4.0.0rc8"))
    ledger.append(build_record(clone_present, "success", cli_version="4.0.0rc8"))
    ledger.append(build_record(clone_absent, "success", cli_version="4.0.0rc8"))

    rows = {row.id: row for row in assemble_report([tracked, clone_present, clone_absent, pending], tmp_path)}

    assert rows["tracked_rep"].partition == "tracked"
    assert rows["tracked_rep"].applied is True
    assert rows["tracked_rep"].in_place_here is None  # tracked: not meaningful
    assert rows["clone_present_rep"].partition == "clone-local"
    assert rows["clone_present_rep"].in_place_here is True  # detect() False -> effect present
    assert rows["clone_absent_rep"].in_place_here is False  # detect() True -> effect absent
    assert rows["pending_rep"].applied is False
    assert rows["pending_rep"].drift is None
