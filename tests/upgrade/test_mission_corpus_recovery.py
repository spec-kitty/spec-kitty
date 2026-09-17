"""WP11's complete historical recovery contract, persisted by WP12.

Counterfactuals are reconstructed from original Git objects. These tests postdate
WP11's chronological audit RED; they do not claim to replace that evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from tests.architectural import test_archive_root_byte_identical as gate
from tests.architectural.test_upgrade_recovery_preservation import (
    build_recovery_repo,
    export_tree,
    git,
    recover,
    run_gate,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()  # noqa: TID251 - independent file-integrity oracle, not charter hashing


def isolated_env(root: Path) -> dict[str, str]:
    """No inherited credentials, source/asset overrides or external state roots."""
    env = {
        key: value
        for key, value in os.environ.items()
        if not (
            key.startswith(("SPEC_KITTY_", "SK_", "GIT_", "PYTHON"))
            or any(word in key for word in ("TOKEN", "PASSWORD", "SECRET", "CREDENTIAL", "API_KEY", "ACCESS_KEY", "AUTH"))
        )
    }
    for key in (
        "HOME",
        "USERPROFILE",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
        "APPDATA",
        "LOCALAPPDATA",
        "SPEC_KITTY_HOME",
        "TMPDIR",
        "TMP",
        "TEMP",
    ):
        path = root / key.lower()
        path.mkdir(parents=True, exist_ok=True)
        env[key] = str(path)
    env.update(CI="true", PYTHONDONTWRITEBYTECODE="1", GIT_OPTIONAL_LOCKS="0", PYTEST_ADDOPTS="")
    env["SPEC_KITTY_ENABLE_SAAS_SYNC"] = "0"
    return env


def cli(repo: Path, *args: str) -> tuple[subprocess.CompletedProcess[bytes], dict[str, Any]]:
    executable = Path(sys.executable).parent / "spec-kitty"
    env = isolated_env(repo.parent / "child-home")
    result = subprocess.run([str(executable), *args], cwd=repo, env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=180)
    evidence = repo.parent / "cli-evidence"
    evidence.mkdir(exist_ok=True)
    number = len(list(evidence.glob("*.stdout")))
    stem = evidence / str(number)
    stem.with_suffix(".stdout").write_bytes(result.stdout)
    stem.with_suffix(".stderr").write_bytes(result.stderr)
    stem.with_suffix(".json").write_text(
        json.dumps(
            {
                "argv": result.args,
                "cwd": str(repo),
                "exit": result.returncode,
                "stdout_sha256": sha256(result.stdout),
                "stderr_sha256": sha256(result.stderr),
                "sync": env["SPEC_KITTY_ENABLE_SAAS_SYNC"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    report: dict[str, Any] = json.loads(result.stdout)
    return result, report


def original_corpus_membership() -> frozenset[str]:
    """Immediate directories from the immutable source, never scanner output."""
    names = set()
    for row in git(REPO_ROOT, "--no-replace-objects", "ls-tree", "-z", f"{gate.ORIGINAL}:kitty-specs").split(b"\0"):
        if row:
            header, name = row.split(b"\t", 1)
            if header.split()[1] == b"tree":
                names.add(os.fsdecode(name))
    assert names, "empty pinned corpus membership"
    return frozenset(names)


def disk_corpus_membership(repo: Path) -> frozenset[str]:
    return frozenset(p.name for p in (repo / "kitty-specs").iterdir() if stat.S_ISDIR(p.lstat().st_mode))


def audit(repo: Path, expected_membership: frozenset[str]) -> tuple[subprocess.CompletedProcess[bytes], dict[str, Any]]:
    physical = disk_corpus_membership(repo)
    assert physical == expected_membership, f"disk corpus membership differs: {sorted(physical ^ expected_membership)}"
    result, report = cli(repo, "doctor", "mission-state", "--audit", "--fail-on", "teamspace-blocker", "--json")
    counts = Counter(mission["mission_slug"] for mission in report["missions"])
    duplicates = sorted(name for name, count in counts.items() if count != 1)
    assert not duplicates, f"duplicate corpus membership: {duplicates}"
    assert counts.keys() == expected_membership, (
        f"audit corpus membership differs: missing={sorted(expected_membership - counts.keys())}, unexpected={sorted(counts.keys() - expected_membership)}"
    )
    assert disk_corpus_membership(repo) == physical, "audit changed physical corpus membership"
    return result, report


def assert_zero(result: subprocess.CompletedProcess[bytes], report: dict[str, Any]) -> None:
    assert report["missions"], "empty corpus discovery"
    assert report["repo_summary"]["teamspace_blockers"] == 0, "full corpus TeamSpace blockers remain"
    assert result.returncode == 0, result.stderr.decode(errors="replace")


def inventory(repo: Path) -> dict[str, tuple[int, int, str]]:
    result = {}
    for root in ("kitty-specs", "docs"):
        for path in (repo / root).rglob("*"):
            st = path.lstat()
            if stat.S_ISREG(st.st_mode):
                result[path.relative_to(repo).as_posix()] = (
                    st.st_mode,
                    st.st_mtime_ns,
                    sha256(path.read_bytes()),
                )
            elif stat.S_ISLNK(st.st_mode):
                result[path.relative_to(repo).as_posix()] = (st.st_mode, st.st_mtime_ns, os.readlink(path))
    return result


def test_original_full_corpus_fails_then_recovered_and_landed_corpus_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    repo = build_recovery_repo(tmp_path, full=True)
    (repo / ".kittify").mkdir(exist_ok=True)
    original_inventory = inventory(repo)
    original_membership = original_corpus_membership()
    result, original = audit(repo, original_membership)
    with pytest.raises(AssertionError, match="full corpus TeamSpace blockers remain"):
        assert_zero(result, original)
    assert result.returncode == 1
    expected = {
        "R2-T1-local-legacy-removal": "IDENTITY_MISSING",
        "reject-cyclic-lane-graphs-01M0QCK4": "IDENTITY_MISSING",
        # Both missions are completed (every WP reaches "done" in the event
        # log), so their frozen status.json drift downgrades to the
        # non-blocking SNAPSHOT_DRIFT_TERMINAL/WARNING code (corpus-tolerance
        # fix) instead of the hard SNAPSHOT_DRIFT/ERROR teamspace blocker.
        # ``assert_zero`` above still fails on this corpus because the two
        # IDENTITY_MISSING findings remain hard blockers.
        "doctrine-drg-silent-drop-boundary-01M0PE7E": "SNAPSHOT_DRIFT_TERMINAL",
        "symbolkey-source-module-01M0B0SF": "SNAPSHOT_DRIFT_TERMINAL",
    }
    for mission in original["missions"]:
        name = mission["mission_slug"]
        if name in expected:
            assert expected[name] in {finding["code"] for finding in mission["findings"]}
    assert set(expected) <= {m["mission_slug"] for m in original["missions"]}
    assert inventory(repo) == original_inventory
    recover(repo)
    recovered_inventory = inventory(repo)
    changed = {p for p in original_inventory.keys() | recovered_inventory.keys() if original_inventory.get(p) != recovered_inventory.get(p)}
    restored_paths = set(git(REPO_ROOT, "ls-tree", "-rz", "--name-only", gate.SOURCE, "--", gate.CYCLIC).decode().split("\0")) - {""}
    expected_changed = (restored_paths - {gate.CYCLIC + "/contracts/lane-dependency-cycle.schema.json"}) | {
        *(p for pair in gate.MOVES for p in pair),
        *gate.SNAPSHOTS[:2],
        gate.RECEIPT,
        gate.SPINE,
        gate.NEW_BUNDLE + "/README.md",
    }
    assert changed == expected_changed
    # The two approved document moves remove exactly this directory; restoring
    # the cyclic dossier changes no membership because its schema was retained.
    recovered_membership = original_membership - {Path(gate.OLD_BUNDLE).name}
    final_result, final = audit(repo, recovered_membership)
    assert_zero(final_result, final)
    assert Path(gate.CYCLIC).name in recovered_membership
    run_gate(repo, monkeypatch)
    git(repo, "commit", "-m", "Land complete reviewed recovery")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    landed_result, landed = audit(repo, recovered_membership)
    assert_zero(landed_result, landed)
    run_gate(repo, monkeypatch)
    assert inventory(repo) == recovered_inventory
    # Independently corrupt each original defect on the entire corpus; healthy
    # controls between attacks prove neither an empty scan nor a narrowed scan.
    for path in (gate.CYCLIC + "/meta.json", *gate.SNAPSHOTS):
        target = repo / path
        old = target.read_bytes()
        if path.endswith("meta.json"):
            target.unlink()
        else:
            source = gate.SOURCE if path == gate.SNAPSHOTS[2] else gate.ORIGINAL
            target.write_bytes(git(REPO_ROOT, "show", f"{source}:{path}"))
        bad_result, bad = audit(repo, recovered_membership)
        with pytest.raises(AssertionError, match="full corpus TeamSpace blockers remain"):
            assert_zero(bad_result, bad)
        target.write_bytes(old)
        control_result, control = audit(repo, recovered_membership)
        assert_zero(control_result, control)


def test_historical_inventory_identity_schema_and_eleven_complete_verdicts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = build_recovery_repo(tmp_path)
    recover(repo)
    run_gate(repo, monkeypatch)
    meta = json.loads((repo / gate.CYCLIC / "meta.json").read_bytes())
    assert meta["mission_id"] == "01M0QCK4D9D65AVNC15HKWAQZ7"
    assert meta["created_at"] == "2026-08-23T13:22:37.098012+00:00"
    assert meta["accepted_at"] == "2026-08-23T17:12:57.441258+00:00"
    raw = (repo / gate.CYCLIC / "status.events.jsonl").read_bytes()
    rows = [json.loads(line) for line in raw.splitlines()]
    assert len(rows) == 71
    assert sha256(raw) == "1502470338a65a478c8d04424b642552317eb95d1d96c526a8c2e444df456099"
    schema = repo / gate.CYCLIC / "contracts/lane-dependency-cycle.schema.json"
    import jsonschema

    jsonschema.Draft202012Validator.check_schema(json.loads(schema.read_bytes()))
    assert git(REPO_ROOT, "hash-object", str(schema)).strip() == b"26cb3b8bafde72894f0d1ec0a9c1701cd511f497"
    total = 0
    for path, count in zip(gate.SNAPSHOTS, (5, 3, 3), strict=True):
        source = gate.SOURCE if path == gate.SNAPSHOTS[2] else gate.ORIGINAL
        old = json.loads(git(REPO_ROOT, "show", f"{source}:{path}"))
        current = json.loads((repo / path).read_bytes())
        assert len(current["work_packages"]) == count
        events = [json.loads(line) for line in (repo / path).with_name("status.events.jsonl").read_bytes().splitlines()]
        for wp, state in current["work_packages"].items():
            review = state["review_result"]
            assert review == old["work_packages"][wp]["review_result"]
            assert set(review) >= {"reference", "reviewer", "verdict"}
            assert any(row.get("wp_id") == wp and row.get("review_result") == review for row in events)
            total += 1
    assert total == 11


@pytest.mark.parametrize("attack", ["defect-only", "drop-unrelated", "duplicate"])
def test_full_corpus_audit_rejects_real_scanner_membership_faults(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    attack: str,
) -> None:
    """Mutate discovery, not the real CLI report, classifiers or aggregation."""
    from typer.testing import CliRunner
    from specify_cli.audit import engine
    from specify_cli.audit.models import MissionAuditResult
    from specify_cli.cli.commands.doctor import app

    repo = build_recovery_repo(tmp_path, full=True)
    (repo / ".kittify").mkdir()
    recover(repo)
    monkeypatch.chdir(repo)
    members = original_corpus_membership() - {Path(gate.OLD_BUNDLE).name}
    assert disk_corpus_membership(repo) == members
    defects = {Path(gate.OLD_BUNDLE).name, *(Path(p).parent.name for p in gate.SNAPSHOTS)}
    omitted = sorted(members - defects)[0]
    real_scan = engine._scan_missions
    scans: list[tuple[str, ...]] = []
    reports: list[dict[str, Any]] = []

    def changed_scan(
        scan_root: Path,
        allowed_dirs: frozenset[Path] | None,
        identity_index: dict[str, Any],
    ) -> list[MissionAuditResult]:
        selected = members & defects if attack == "defect-only" else members - {omitted}
        if attack == "duplicate":
            selected = members
        allowed = frozenset(scan_root / name for name in selected)
        rows: list[MissionAuditResult] = real_scan(scan_root, allowed if allowed_dirs is None else allowed & allowed_dirs, identity_index)
        if attack == "duplicate":
            rows.append(rows[0])
        scans.append(tuple(row.mission_slug for row in rows))
        return rows

    def actual_doctor_cli(root: Path, *args: str) -> tuple[subprocess.CompletedProcess[bytes], dict[str, Any]]:
        assert root == repo and args[0] == "doctor"
        result = CliRunner().invoke(app, list(args[1:]), env=isolated_env(tmp_path / "doctor-home"))
        label = str(len(reports))
        (tmp_path / f"{label}.stdout").write_text(result.stdout, encoding="utf-8")
        (tmp_path / f"{label}.stderr").write_text(result.stderr, encoding="utf-8")
        assert result.exit_code == 0, result.output
        report = json.loads(result.stdout)
        reports.append(report)
        return subprocess.CompletedProcess(args, result.exit_code, result.stdout.encode(), result.stderr.encode()), report

    monkeypatch.setattr(sys.modules[__name__], "cli", actual_doctor_cli)
    healthy_result, healthy = audit(repo, members)
    assert_zero(healthy_result, healthy)
    with monkeypatch.context() as fault:
        fault.setattr(engine, "_scan_missions", changed_scan)
        with pytest.raises(AssertionError, match="corpus membership"):
            audit(repo, members)
    assert scans
    if attack == "duplicate":
        assert len(scans[0]) > len(set(scans[0]))
    else:
        assert set(scans[0]) < members and omitted not in scans[0]
    control_result, control = audit(repo, members)
    assert_zero(control_result, control)


def test_physical_omission_cannot_redefine_pinned_corpus(tmp_path: Path) -> None:
    repo = build_recovery_repo(tmp_path, full=True)
    members = original_corpus_membership()
    assert disk_corpus_membership(repo) == members
    defects = {Path(gate.OLD_BUNDLE).name, *(Path(p).parent.name for p in gate.SNAPSHOTS)}
    missing = sorted(members - defects)[0]
    directory = repo / "kitty-specs" / missing
    directory.rename(repo / missing)
    with pytest.raises(AssertionError, match="disk corpus membership differs"):
        audit(repo, members)
    (repo / missing).rename(directory)
    assert disk_corpus_membership(repo) == members


def test_repeat_real_restore_move_and_public_replay_has_no_churn(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = build_recovery_repo(tmp_path)
    (repo / ".kittify").mkdir(exist_ok=True)
    recover(repo)
    before = inventory(repo)
    recover(repo)
    assert inventory(repo) == before
    for path in gate.SNAPSHOTS:
        result, _ = cli(repo, "agent", "status", "materialize", "--mission", Path(path).parent.name, "--json")
        assert result.returncode == 0, result.stderr
        assert inventory(repo) == before
    run_gate(repo, monkeypatch)
    # A same-byte rewrite is visible to this independent mtime oracle.
    target = repo / gate.SNAPSHOTS[0]
    st = target.stat()
    os.utime(target, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
    with pytest.raises(AssertionError):
        assert inventory(repo) == before


def test_metadata_only_restoration_cannot_hide_missing_dossier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = build_recovery_repo(tmp_path)
    export_tree(repo, gate.SOURCE, gate.CYCLIC + "/meta.json")
    # Real public classification recognizes identity, but preservation still
    # requires the entire historical tree and independently pinned evidence.
    from specify_cli.audit.engine import run_audit
    from specify_cli.audit.models import AuditOptions

    report = run_audit(AuditOptions(repo_root=repo))
    cyclic = next(m for m in report.missions if m.mission_slug == Path(gate.CYCLIC).name)
    assert "IDENTITY_MISSING" not in {f.code for f in cyclic.findings}
    git(repo, "add", "-f", "--all")
    monkeypatch.setattr(gate, "REPO_ROOT", repo)
    with pytest.raises(AssertionError, match="recovery-receipt.json"):
        gate._check_recovery(gate._index())


def test_real_upgrade_yes_preserves_history_until_separate_tty_consent(tmp_path: Path) -> None:
    """Actual successful human upgrade, then actual TTY-owned repair approval."""
    import pty

    repo = tmp_path / "upgrade-project"
    repo.mkdir()
    env = isolated_env(tmp_path / "upgrade-home")
    executable = str(Path(sys.executable).parent / "spec-kitty")
    setup = subprocess.run([executable, "init", "--ai", "codex", "--yes"], cwd=repo, env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=180)
    assert setup.returncode == 0, setup.stdout.decode(errors="replace") + setup.stderr.decode(errors="replace")
    git(repo, "init", "--initial-branch=wp12-consent")
    git(repo, "config", "user.name", "WP12 consent")
    git(repo, "config", "user.email", "wp12@example.invalid")
    git(repo, "config", "commit.gpgsign", "false")
    directory = gate.SNAPSHOTS[0].rsplit("/", 1)[0]
    export_tree(repo, gate.ORIGINAL, directory)
    git(repo, "add", "-f", ".")
    git(repo, "commit", "-m", "Real damaged historical corpus")
    before = inventory(repo)
    command = [executable, "upgrade", "--yes", "--no-worktrees"]
    denied = subprocess.run(command, cwd=repo, env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=180)
    (tmp_path / "upgrade-denied.stdout").write_bytes(denied.stdout)
    (tmp_path / "upgrade-denied.stderr").write_bytes(denied.stderr)
    assert denied.returncode == 0, denied.stdout.decode(errors="replace") + denied.stderr.decode(errors="replace")
    assert inventory(repo) == before, "upgrade --yes changed historical state without separate consent"
    assert b"mission-state" in denied.stdout, "successful human finalizer did not reach the damaged-corpus gate"
    master, slave = pty.openpty()
    try:
        with subprocess.Popen(command, cwd=repo, env=env, stdin=slave, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as child:
            os.write(master, b"y\n")
            stdout, stderr = child.communicate(timeout=180)
        assert child.returncode == 0, stdout.decode(errors="replace") + stderr.decode(errors="replace")
    finally:
        os.close(master)
        os.close(slave)
    (tmp_path / "upgrade-approved.stdout").write_bytes(stdout)
    (tmp_path / "upgrade-approved.stderr").write_bytes(stderr)
    assert b"--fix" in stdout, "independent TTY consent prompt was not reached"
    assert inventory(repo) != before, "separate consent never reached the repair owner"
    from specify_cli.status.reducer import materialize_snapshot, materialize_to_json

    snapshot = repo / gate.SNAPSHOTS[0]
    assert snapshot.read_bytes() == materialize_to_json(materialize_snapshot(snapshot.parent)).encode()
