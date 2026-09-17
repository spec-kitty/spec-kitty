"""One recovery admission, exercised against real immutable Git inputs."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.audit.classifiers.status_json import classify_status_json
from tests.architectural import test_archive_root_byte_identical as gate
from tests.architectural.test_upgrade_recovery_preservation import export_tree, git

pytestmark = [pytest.mark.architectural, pytest.mark.git_repo]
ROOT = Path(__file__).resolve().parents[2]
SOURCE = "f2be03af4889c89184fdb3a4aeb90fc3f90b3a87"
DIRECTORY = "kitty-specs/dead-port-disposition-01M1VRA2"
SNAPSHOT = DIRECTORY + "/status.json"
OUTPUT = "5c39a554f0958c22bfc8ffc3f2fcfd38023c0287"
RECEIPT = "docs/archive/program-evidence/upgrade-preview-mission-health-01M1V6E1/dead-port-snapshot-recovery.json"


@pytest.fixture
def historical_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    repo = tmp_path / "history"
    subprocess.run(["git", "clone", "--shared", "--no-checkout", str(ROOT), str(repo)], check=True, capture_output=True)
    git(repo, "symbolic-ref", "HEAD", "refs/heads/isolated-recovery")
    git(repo, "read-tree", "--empty")
    git(repo, "config", "user.name", "Recovery witness")
    git(repo, "config", "user.email", "recovery@example.invalid")
    git(repo, "config", "commit.gpgsign", "false")
    export_tree(repo, SOURCE, DIRECTORY)
    other = repo / "kitty-specs/unrelated/status.json"
    other.parent.mkdir(parents=True)
    other.write_text('{"historical":true}\n')
    git(repo, "add", "-f", ".")
    git(repo, "commit", "-m", "Original immutable dossier")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    monkeypatch.setattr(gate, "REPO_ROOT", repo)
    return repo


def recover(repo: Path) -> None:
    (repo / SNAPSHOT).write_bytes(git(ROOT, "cat-file", "blob", OUTPUT))
    receipt = repo / RECEIPT
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_bytes((ROOT / RECEIPT).read_bytes())
    git(repo, "add", "-f", ".")


@pytest.fixture
def recovered_repo(historical_repo: Path) -> Path:
    recover(historical_repo)
    return historical_repo


def test_exact_reviewed_replay_passes_without_hiding_original_corpus_drift(historical_repo: Path) -> None:
    gate.test_no_preexisting_archived_file_was_modified()
    original = (historical_repo / SNAPSHOT).read_bytes()
    # dead-port-disposition-01M1VRA2 is a terminal (all-WPs-done) archived
    # mission, so its unfixable snapshot drift downgrades to the
    # non-blocking SNAPSHOT_DRIFT_TERMINAL/WARNING code (corpus-tolerance
    # fix) rather than the hard SNAPSHOT_DRIFT/ERROR blocker -- but drift is
    # still surfaced, not silently hidden.
    codes_before = {finding.code for finding in classify_status_json(historical_repo / DIRECTORY)}
    assert "SNAPSHOT_DRIFT_TERMINAL" in codes_before
    assert "SNAPSHOT_DRIFT" not in codes_before
    assert (historical_repo / SNAPSHOT).read_bytes() == original
    recover(historical_repo)
    gate.test_no_preexisting_archived_file_was_modified()
    candidate = (historical_repo / SNAPSHOT).read_bytes()
    codes_after = {finding.code for finding in classify_status_json(historical_repo / DIRECTORY)}
    assert "SNAPSHOT_DRIFT" not in codes_after
    assert "SNAPSHOT_DRIFT_TERMINAL" not in codes_after
    assert (historical_repo / SNAPSHOT).read_bytes() == candidate
    git(historical_repo, "commit", "-m", "Land reviewed recovery")
    git(historical_repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    gate.test_no_preexisting_archived_file_was_modified()


def test_different_untouched_historical_baseline_needs_no_recovery_receipt(historical_repo: Path) -> None:
    path = historical_repo / SNAPSHOT
    data = json.loads(path.read_bytes())
    data["mission_type"] = "earlier-historical-value"
    path.write_text(json.dumps(data))
    git(historical_repo, "add", SNAPSHOT)
    git(historical_repo, "commit", "-m", "Different historical baseline")
    git(historical_repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    before = path.read_bytes()
    gate.test_no_preexisting_archived_file_was_modified()
    assert path.read_bytes() == before
    assert not (historical_repo / RECEIPT).exists()


def test_landed_input_provenance_survives_comparison_baseline_advancement(recovered_repo: Path) -> None:
    git(recovered_repo, "commit", "-m", "Land reviewed recovery")
    annotation = recovered_repo / DIRECTORY / "tasks/WP01-seam-foundation.md"
    annotation.write_bytes(annotation.read_bytes() + b"\n")
    git(recovered_repo, "add", ".")
    git(recovered_repo, "commit", "-m", "Counterfactual historical input rewrite")
    git(recovered_repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    assert git(recovered_repo, "diff", "origin/main", "--", DIRECTORY) == b""
    assert "SNAPSHOT_DRIFT" not in {finding.code for finding in classify_status_json(recovered_repo / DIRECTORY)}
    with pytest.raises(AssertionError, match="WP01-seam-foundation.md.*reviewed"):
        gate.test_no_preexisting_archived_file_was_modified()


@pytest.mark.parametrize("surface", ["worktree", "index"])
@pytest.mark.parametrize(
    "attack,relative,reason",
    [
        ("input", DIRECTORY + "/tasks.md", "reviewed"),
        ("annotation", DIRECTORY + "/tasks/WP01-seam-foundation.md", "reviewed"),
        ("input", DIRECTORY + "/status.events.jsonl", "reviewed"),
        ("input", DIRECTORY + "/meta.json", "reviewed"),
        ("review", SNAPSHOT, "reviewed"),
        ("output", SNAPSHOT, "reviewed"),
        ("receipt", RECEIPT, "reviewed"),
        ("mode", SNAPSHOT, "mode"),
        ("mode", DIRECTORY + "/meta.json", "mode"),
        ("extra", DIRECTORY + "/tasks/shadow.md", "inventory"),
        ("delete", DIRECTORY + "/tasks.md", "inventory"),
        ("delete", RECEIPT, "reviewed|missing"),
        ("delete", SNAPSHOT, "inventory"),
        ("stale", SNAPSHOT, "reviewed"),
        ("input", "kitty-specs/unrelated/status.json", "ordinary archive history changed"),
    ],
)
def test_recovery_rejects_changed_proof_history_and_other_snapshots(recovered_repo: Path, surface: str, attack: str, relative: str, reason: str) -> None:
    path = recovered_repo / relative
    before = path.read_bytes() if path.exists() else None
    mode = path.stat().st_mode if path.exists() else None
    if attack == "extra":
        path.write_text("shadow input\n")
    elif attack == "delete":
        path.unlink()
    elif attack == "mode":
        path.chmod(0o755)
    elif attack == "stale":
        path.write_bytes(git(ROOT, "show", f"{SOURCE}:{SNAPSHOT}"))
    elif attack == "input":
        path.write_bytes(path.read_bytes() + b"\n")
    elif attack == "annotation":
        raw = path.read_text()
        assert "agent_profile: python-pedro" in raw
        path.write_text(raw.replace("agent_profile: python-pedro", "agent_profile: forged-profile", 1))
    else:
        data = json.loads(path.read_bytes())
        if attack == "review":
            data["work_packages"]["WP01"]["review_result"]["verdict"] = "rejected"
        elif attack == "output":
            data["event_count"] += 1
        else:
            data["snapshot"]["after_blob"] = "0" * 40
        path.write_text(json.dumps(data))
    if surface == "index":
        git(recovered_repo, "add", "-f", "--all")
        if before is None:
            path.unlink()
        else:
            path.write_bytes(before)
            assert mode is not None
            path.chmod(mode)
    with pytest.raises(AssertionError, match=reason):
        gate.test_no_preexisting_archived_file_was_modified()


@pytest.mark.parametrize("attack", ["receipt-delete", "receipt-rename", "erase-admission", "snapshot-delete"])
def test_landed_recovery_cannot_erase_its_obligations(recovered_repo: Path, attack: str) -> None:
    git(recovered_repo, "commit", "-m", "Land reviewed recovery")
    git(recovered_repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    receipt = recovered_repo / RECEIPT
    if attack == "receipt-rename":
        receipt.rename(receipt.with_name("renamed.json"))
    elif attack == "snapshot-delete":
        (recovered_repo / SNAPSHOT).unlink()
    else:
        receipt.unlink()
        if attack == "erase-admission":
            (recovered_repo / SNAPSHOT).write_bytes(git(ROOT, "show", f"{SOURCE}:{SNAPSHOT}"))
    git(recovered_repo, "add", "-f", "--all")
    with pytest.raises(AssertionError, match="reviewed|inventory|missing"):
        gate.test_no_preexisting_archived_file_was_modified()
