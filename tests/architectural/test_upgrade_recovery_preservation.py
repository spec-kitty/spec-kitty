"""Real Git counterfactuals for the archive preservation gate (WP12)."""

from __future__ import annotations

import os
import io
import json
import re
import stat
import subprocess
import tarfile
import types
from pathlib import Path

import pytest
from _pytest.fixtures import SubRequest
from kernel.clock import UTC, datetime

from specify_cli.invocation.lifecycle import append_lifecycle_record
from specify_cli.invocation.record import ProfileInvocationRecord
from tests.architectural import test_archive_root_byte_identical as gate

REPO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = [pytest.mark.architectural, pytest.mark.git_repo]


@pytest.hookimpl(tryfirst=True)
def pytest_fixture_setup(fixturedef: pytest.FixtureDef[object], request: SubRequest) -> Path | None:
    """Opt-in execution binding for the supplied frozen venv, including xdist.

    Loaded as a plugin only by the recorded WP12 verification command. The
    normal fixture and every unrelated conftest guard remain unchanged.
    """
    frozen = os.environ.get("WP12_FROZEN_VENV")
    if fixturedef.argname != "test_venv" or not frozen:
        return None
    value = Path(frozen)
    assert value.is_absolute() and (value / "bin/python").is_file()
    os.environ["SPEC_KITTY_TEST_VENV"] = str(value)
    fixturedef.cached_result = (value, fixturedef.cache_key(request), None)
    return value


def git(repo: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        check=True,
        env={**os.environ, "SPEC_KITTY_ENABLE_SAAS_SYNC": "0"},
    ).stdout


def append(repo: Path, action: str = "wp12::inspect") -> Path:
    path = append_lifecycle_record(
        repo,
        ProfileInvocationRecord(
            canonical_action_id=action,
            phase="started",
            at=datetime(2026, 9, 6, tzinfo=UTC),
            agent="codex",
            mission_id="01M0QCK4D9D65AVNC15HKWAQZ7",
        ),
    )
    assert isinstance(path, Path)
    return path


@pytest.fixture
def archive_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    repo = tmp_path / "archive"
    repo.mkdir()
    git(repo, "init", "--initial-branch=main")
    git(repo, "config", "user.email", "wp12@example.invalid")
    git(repo, "config", "user.name", "WP12 fixture")
    git(repo, "config", "commit.gpgsign", "false")
    append(repo, "wp12::historical")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "Nonempty historical archive")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    monkeypatch.setattr(gate, "REPO_ROOT", repo)
    return repo


def test_real_writer_append_passes_existing_gate(archive_repo: Path) -> None:
    """RED first: the old gate rejects a genuine, model-valid suffix."""
    gate.test_archive_baseline_is_non_empty()
    assert git(archive_repo, "merge-base", "HEAD", "origin/main").strip()
    append(archive_repo)
    gate.test_no_preexisting_archived_file_was_modified()


def test_new_archive_path_remains_allowed(archive_repo: Path) -> None:
    path = archive_repo / "kitty-ops/new-proof.txt"
    path.write_bytes(b"New proof\n")
    git(archive_repo, "add", "kitty-ops/new-proof.txt")
    gate.test_no_preexisting_archived_file_was_modified()


def test_unchanged_nonempty_archive_passes(archive_repo: Path) -> None:
    gate.test_archive_baseline_is_non_empty()
    gate.test_no_preexisting_archived_file_was_modified()


def test_unchanged_outside_root_gitlink_passes_old_and_current_gate(archive_repo: Path) -> None:
    """A real unrelated submodule is not an archive blob-kind violation."""
    head = git(archive_repo, "rev-parse", "HEAD").decode().strip()
    (archive_repo / "vendor/example").mkdir(parents=True)
    git(archive_repo, "update-index", "--add", "--cacheinfo", f"160000,{head},vendor/example")
    git(archive_repo, "commit", "-m", "Unchanged outside-root Gitlink baseline")
    git(archive_repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    assert git(archive_repo, "diff", "--name-only", "origin/main", "--", "vendor/example") == b""
    old_source = git(
        REPO_ROOT,
        "show",
        "6e60f8b42e783b2c8fb8dea237a7a5514854a8ec:tests/architectural/test_archive_root_byte_identical.py",
    )
    old = types.ModuleType("wp12_original_archive_gate")
    old.__file__ = gate.__file__
    exec(compile(old_source, old.__file__, "exec"), old.__dict__)
    old.__dict__["REPO_ROOT"] = archive_repo
    old.test_archive_baseline_is_non_empty()
    old.test_no_preexisting_archived_file_was_modified()
    gate.test_no_preexisting_archived_file_was_modified()
    gate.test_archive_baseline_is_non_empty()


@pytest.mark.parametrize("root", gate._ARCHIVE_ROOTS)
@pytest.mark.parametrize("at_root", [False, True])
def test_protected_gitlink_remains_rejected(archive_repo: Path, root: str, at_root: bool) -> None:
    head = git(archive_repo, "rev-parse", "HEAD").decode().strip()
    path = root.rstrip("/") if at_root else root + "example"
    if at_root:
        git(archive_repo, "rm", "-r", "--cached", "--ignore-unmatch", "--", path)
    git(archive_repo, "update-index", "--add", "--cacheinfo", f"160000,{head},{path}")
    git(archive_repo, "commit", "-m", "Protected non-blob baseline")
    git(archive_repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    with pytest.raises(AssertionError, match="non-blob historical entry"):
        gate.test_no_preexisting_archived_file_was_modified()
    with pytest.raises(AssertionError, match="non-blob historical entry"):
        gate.test_archive_baseline_is_non_empty()


def run_gate(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gate, "REPO_ROOT", repo)
    gate.test_archive_baseline_is_non_empty()
    gate.test_no_preexisting_archived_file_was_modified()


@pytest.mark.parametrize(
    "attack,reason",
    [
        ("rewrite", "historical byte prefix"),
        ("remove", "historical byte prefix"),
        ("reorder", "historical byte prefix"),
        ("prepend", "historical byte prefix"),
        ("truncate", "historical byte prefix"),
        ("crlf", "historical byte prefix"),
        ("json", "invalid suffix row"),
        ("utf8", "invalid suffix row"),
        ("blank", "invalid suffix row"),
        ("array", "invalid suffix row"),
        ("middle", "invalid suffix row 2"),
        ("model", "invalid suffix row"),
        ("incomplete", "incomplete suffix"),
        ("mode", "mode changed"),
        ("symlink", "regular-file kind"),
        ("parent", "unsafe parent"),
        ("delete", "missing file"),
        ("staged-delete", "deleted or renamed"),
        ("staged-rewrite", "historical byte prefix"),
        ("staged-mode", "index mode"),
    ],
)
def test_lifecycle_corruption_is_rejected(
    archive_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    attack: str,
    reason: str,
) -> None:
    path = append(archive_repo)
    git(archive_repo, "add", ".")
    git(archive_repo, "commit", "-m", "Second historical row")
    git(archive_repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    before = path.read_bytes()
    append(archive_repo, "wp12::new")
    valid = path.read_bytes()
    run_gate(archive_repo, monkeypatch)
    rows = before.splitlines(keepends=True)
    alterations = {
        "rewrite": b"X" + valid[1:],
        "remove": rows[1],
        "reorder": rows[1] + rows[0],
        "prepend": b"{}\n" + valid,
        "truncate": before[:-3],
        "crlf": valid.replace(b"\n", b"\r\n"),
        "json": valid + b"{\n",
        "utf8": valid + b"\xff\n",
        "blank": valid + b"\n",
        "array": valid + b"[]\n",
        "middle": valid + b"{}\n" + valid[len(before) :],
        "model": valid + b'{"phase":"invented","at":"invalid"}\n',
        "incomplete": valid[:-1],
        "staged-rewrite": b"X" + valid[1:],
    }
    if attack in alterations:
        path.write_bytes(alterations[attack])
    elif attack in {"mode", "staged-mode"}:
        path.chmod(0o755)
    elif attack == "symlink":
        target = archive_repo.parent / "target"
        target.write_bytes(valid)
        path.unlink()
        path.symlink_to(target)
    elif attack == "parent":
        moved = archive_repo.parent / "outside-ops"
        path.parent.rename(moved)
        path.parent.symlink_to(moved, target_is_directory=True)
    else:
        path.unlink()
    if attack.startswith("staged-"):
        git(archive_repo, "add", "-A")
        path.write_bytes(valid)
        path.chmod(0o644)
    with pytest.raises(AssertionError, match=reason):
        run_gate(archive_repo, monkeypatch)


@pytest.mark.parametrize("historical", [b"legacy unterminated", b"legacy\r\n", b"", b" { legacy } \n"])
def test_historical_bytes_are_not_reserialized(
    archive_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    historical: bytes,
) -> None:
    path = archive_repo / "kitty-ops/lifecycle.jsonl"
    path.write_bytes(historical)
    git(archive_repo, "add", ".")
    git(archive_repo, "commit", "-m", "Historical shape")
    git(archive_repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    run_gate(archive_repo, monkeypatch)
    append(archive_repo)
    if historical and not historical.endswith(b"\n"):
        with pytest.raises(AssertionError, match="unterminated historical boundary"):
            run_gate(archive_repo, monkeypatch)
    else:
        run_gate(archive_repo, monkeypatch)


@pytest.mark.parametrize(
    "path",
    [
        "kitty-specs/old/spec.md",
        "kitty-specs/old/status.events.jsonl",
        "kitty-specs/old/status.json",
        "kitty-ops/old.jsonl",
        ".kittify/mission-state-audit/quarantine/raw.jsonl",
        ".kittify/missions/old/retrospective.yaml",
        "kitty-specs/tab\tand\nnewline.md",
    ],
)
@pytest.mark.parametrize("operation", ["edit", "delete", "rename-out", "staged-edit"])
def test_valid_append_cannot_hide_ordinary_archive_change(
    archive_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    operation: str,
) -> None:
    target = archive_repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"immutable old proof\n")
    git(archive_repo, "add", ".")
    git(archive_repo, "commit", "-m", "Ordinary proof")
    git(archive_repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    append(archive_repo)
    run_gate(archive_repo, monkeypatch)
    if operation == "delete":
        target.unlink()
    elif operation == "rename-out":
        git(archive_repo, "mv", path, "outside-proof.md")
    else:
        target.write_bytes(b"rewritten proof\n")
    if operation == "staged-edit":
        git(archive_repo, "add", path)
        target.write_bytes(b"immutable old proof\n")
    with pytest.raises(AssertionError, match="ordinary archive history changed") as error:
        run_gate(archive_repo, monkeypatch)
    assert all(part in str(error.value) for part in path.splitlines())


def test_rename_into_archive_is_not_an_addition(archive_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (archive_repo / "outside").write_bytes(b"proof")
    git(archive_repo, "add", ".")
    git(archive_repo, "commit", "-m", "Outside source")
    git(archive_repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    git(archive_repo, "mv", "outside", "kitty-ops/incoming")
    with pytest.raises(AssertionError, match="ordinary archive history changed"):
        run_gate(archive_repo, monkeypatch)


def test_missing_base_fails_under_literal_ci(archive_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CI", "true")
    git(archive_repo, "update-ref", "-d", "refs/remotes/origin/main")
    with pytest.raises(pytest.fail.Exception, match="not reachable"):
        run_gate(archive_repo, monkeypatch)


def test_empty_baseline_cannot_pass(archive_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    git(archive_repo, "rm", "kitty-ops/lifecycle.jsonl")
    git(archive_repo, "commit", "-m", "Empty baseline control")
    git(archive_repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    with pytest.raises(AssertionError, match="no tracked files"):
        run_gate(archive_repo, monkeypatch)


def export_tree(repo: Path, rev: str, *paths: str) -> None:
    """Restore concrete regular Git entries in a disposable copy only."""
    payload = git(REPO_ROOT, "archive", rev, "--", *paths)
    with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
        for member in archive:
            if not member.isfile():
                continue
            relative = Path(member.name)
            assert not relative.is_absolute() and ".." not in relative.parts
            target = repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            stream = archive.extractfile(member)
            assert stream is not None
            target.write_bytes(stream.read())
            target.chmod(member.mode)


def build_recovery_repo(tmp_path: Path, *, full: bool = False) -> Path:
    repo = tmp_path / "corpus"
    # Shared clone reads pinned objects; all refs/index/worktree mutations are local.
    subprocess.run(
        ["git", "clone", "--shared", "--no-checkout", str(REPO_ROOT), str(repo)],
        capture_output=True,
        check=True,
        env={**os.environ, "SPEC_KITTY_ENABLE_SAAS_SYNC": "0"},
    )
    git(repo, "symbolic-ref", "HEAD", "refs/heads/wp12-fixture")
    git(repo, "read-tree", "--empty")
    git(repo, "config", "user.name", "WP12 fixture")
    git(repo, "config", "user.email", "wp12@example.invalid")
    git(repo, "config", "commit.gpgsign", "false")
    paths = (
        ("kitty-specs", "docs")
        if full
        else (
            gate.CYCLIC,
            gate.OLD_BUNDLE,
            gate.SPINE,
            *(p.rsplit("/", 1)[0] for p in gate.SNAPSHOTS[:2]),
        )
    )
    export_tree(repo, "c0054153b9bce0778cf41a85d11ecd4e9650031d", *paths)
    git(repo, "add", "-f", ".")
    git(repo, "commit", "-m", "Original historical corpus")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    return repo


def recover(repo: Path) -> None:
    """Replay the reviewed restore/move operation, refusing collisions/rewrite."""
    restored = git(REPO_ROOT, "ls-tree", "-rz", gate.SOURCE, "--", gate.CYCLIC)
    for row in restored.split(b"\0"):
        if not row:
            continue
        header, encoded_name = row.split(b"\t", 1)
        mode, kind, oid = header.decode().split()
        assert kind == "blob"
        path = repo / os.fsdecode(encoded_name)
        expected = git(REPO_ROOT, "cat-file", "blob", oid)
        if path.exists():
            assert path.is_file() and not path.is_symlink(), f"{path}: restore kind"
            assert bool(path.stat().st_mode & stat.S_IXUSR) == (mode == "100755"), f"{path}: restore mode"
            # An already-completed cyclic replay has separate reviewed proof.
            final = git(REPO_ROOT, "show", f"{gate.RECOVERED}:{os.fsdecode(encoded_name)}")
            assert path.read_bytes() in (expected, final), f"{path}: restore collision"
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(expected)
            path.chmod(int(mode, 8) & 0o777)
    for old, new in gate.MOVES:
        source, destination = repo / old, repo / new
        expected = git(REPO_ROOT, "show", f"{gate.ORIGINAL}:{old}")
        if source.exists():
            assert source.is_file() and not source.is_symlink()
            assert not source.stat().st_mode & stat.S_IXUSR
            assert source.read_bytes() == expected
            assert not destination.exists(), f"{new}: relocation collision"
            destination.parent.mkdir(parents=True, exist_ok=True)
            source.rename(destination)
        assert not destination.is_symlink() and destination.is_file(), f"{new}: completed relocation kind"
        assert not destination.stat().st_mode & stat.S_IXUSR, f"{new}: completed relocation mode"
        assert destination.read_bytes() == expected, f"{new}: completed relocation proof"
    old_dir = repo / gate.OLD_BUNDLE
    if old_dir.exists():
        old_dir.rmdir()
    from specify_cli.status.reducer import materialize

    for snapshot in gate.SNAPSHOTS:
        materialize(repo / snapshot.rsplit("/", 1)[0])
    for name in (gate.RECEIPT, gate.SPINE, gate.NEW_BUNDLE + "/README.md"):
        expected = git(REPO_ROOT, "show", f"{gate.RECOVERED}:{name}")
        target = repo / name
        if not target.exists() or target.read_bytes() != expected:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(expected)
    git(repo, "add", "-f", "--all")


@pytest.fixture
def recovery_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    repo = build_recovery_repo(tmp_path)
    recover(repo)
    run_gate(repo, monkeypatch)
    return repo


@pytest.mark.parametrize("renames", ["true", "false"])
def test_exact_recovery_passes_both_git_move_representations(
    recovery_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    renames: str,
) -> None:
    git(recovery_repo, "config", "diff.renames", renames)
    changes = git(recovery_repo, "diff", "--cached", "--name-status", "origin/main")
    assert (b"R100" in changes) == (renames == "true")
    run_gate(recovery_repo, monkeypatch)


@pytest.mark.parametrize("landed", [False, True])
@pytest.mark.parametrize(
    "path",
    [
        *gate.SNAPSHOTS,
        *(new for _, new in gate.MOVES),
        gate.RECEIPT,
        gate.NEW_BUNDLE + "/README.md",
        gate.SPINE,
        gate.CYCLIC + "/meta.json",
        gate.CYCLIC + "/status.events.jsonl",
        gate.CYCLIC + "/tasks/.gitkeep",
        gate.CYCLIC + "/.kittify/dossiers/reject-cyclic-lane-graphs-01M0QCK4/snapshot-latest.json",
    ],
)
@pytest.mark.parametrize("attack", ["bytes", "delete", "mode"])
def test_recovery_results_remain_protected_after_landing(
    recovery_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    landed: bool,
    path: str,
    attack: str,
) -> None:
    if landed:
        git(recovery_repo, "commit", "-m", "Land genuine recovery")
        git(recovery_repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    run_gate(recovery_repo, monkeypatch)
    target = recovery_repo / path
    if attack == "delete":
        target.unlink()
    elif attack == "mode":
        target.chmod(0o755)
    else:
        raw = target.read_bytes()
        target.write_bytes(b"X" + raw[1:])
    with pytest.raises(AssertionError, match=re.escape(path)):
        run_gate(recovery_repo, monkeypatch)


@pytest.mark.parametrize(
    "attack",
    [
        "omit",
        "duplicate",
        "extra",
        "absolute",
        "traversal",
        "source",
        "oid",
        "mode",
        "unknown-action",
        "input",
        "forged-output",
        "fourth-replay",
    ],
)
def test_receipt_cannot_authorize_its_own_candidate(
    recovery_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    attack: str,
) -> None:
    path = recovery_repo / gate.RECEIPT
    receipt = json.loads(path.read_bytes())
    if attack == "omit":
        receipt["restores"].pop()
    elif attack == "duplicate":
        receipt["restores"].append(receipt["restores"][0])
    elif attack in {"extra", "absolute", "traversal"}:
        receipt["restores"][0]["path"] = {
            "extra": "kitty-specs/fourth/status.json",
            "absolute": str(recovery_repo.parent / "escape"),
            "traversal": "../escape",
        }[attack]
    elif attack in {"source", "unknown-action"}:
        receipt["source_commit" if attack == "source" else "action"] = "invented"
    elif attack in {"oid", "mode"}:
        receipt["restores"][0]["blob" if attack == "oid" else "mode"] = "000000"
    elif attack == "input":
        receipt["replays"][0]["events"]["sha256"] = "0" * 64
    else:
        forged = recovery_repo / gate.SNAPSHOTS[0]
        forged.write_bytes(forged.read_bytes().replace(b'"done"', b'"planned"'))
        import hashlib

        receipt["replays"][0]["after_sha256"] = hashlib.sha256(forged.read_bytes()).hexdigest()  # noqa: TID251 - adversarial file checksum
        if attack == "fourth-replay":
            receipt["replays"].append({"path": "kitty-specs/fourth/status.json"})
    path.write_text(json.dumps(receipt), encoding="utf-8")
    git(recovery_repo, "add", "-f", "--all")
    with pytest.raises(AssertionError, match="recovery-receipt.json.*reviewed proof"):
        run_gate(recovery_repo, monkeypatch)


@pytest.mark.parametrize("attack", ["untracked", "wrong-path", "symlink", "parent", "collision", "third-move"])
def test_relocation_requires_exact_tracked_confined_destination(
    recovery_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    attack: str,
) -> None:
    old, new = gate.MOVES[0]
    target = recovery_repo / new
    if attack == "untracked":
        git(recovery_repo, "rm", "--cached", new)
    elif attack == "wrong-path":
        target.rename(target.with_name("wrong.md"))
    elif attack == "symlink":
        other = recovery_repo.parent / "outside"
        target.rename(other)
        target.symlink_to(other)
    elif attack == "parent":
        other = recovery_repo.parent / "outside-parent"
        target.parent.rename(other)
        target.parent.symlink_to(other, target_is_directory=True)
    elif attack == "collision":
        target.write_bytes(b"different occupant")
    else:
        ordinary = recovery_repo / gate.CYCLIC / "spec.md"
        ordinary.rename(recovery_repo / "third-move.md")
    with pytest.raises(AssertionError, match="(tracked index|missing file|regular-file kind|unsafe parent|reviewed bytes|inventory differs)"):
        run_gate(recovery_repo, monkeypatch)


def test_reducer_and_output_cannot_change_together(
    recovery_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = recovery_repo / gate.SNAPSHOTS[0]
    forged = path.read_bytes().replace(b'"done"', b'"planned"')
    path.write_bytes(forged)
    monkeypatch.setattr(gate, "materialize_to_json", lambda _: forged.decode())
    with pytest.raises(AssertionError, match="reviewed bytes changed"):
        run_gate(recovery_repo, monkeypatch)


def test_current_canonical_computation_is_still_required(
    recovery_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(gate, "materialize_to_json", lambda _: "{}\n")
    with pytest.raises(AssertionError, match="canonical replay differs"):
        run_gate(recovery_repo, monkeypatch)


@pytest.mark.parametrize("snapshot", gate.SNAPSHOTS)
@pytest.mark.parametrize("attack", ["meta", "events", "review", "identity", "annotation", "json-format"])
def test_snapshot_history_and_complete_verdict_are_pinned(
    recovery_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    snapshot: str,
    attack: str,
) -> None:
    directory = snapshot.rsplit("/", 1)[0]
    filename = {"meta": "meta.json", "events": "status.events.jsonl", "annotation": "status.events.jsonl"}
    path = f"{directory}/{filename.get(attack, 'status.json')}"
    target = recovery_repo / path
    raw = target.read_bytes()
    if attack in {"events", "annotation"}:
        rows = raw.splitlines(keepends=True)
        position = next(i for i, row in enumerate(rows) if json.loads(row).get("kind") == "annotation") if attack == "annotation" else 0
        target.write_bytes(b"".join(rows[:position] + rows[position + 1 :]))
    else:
        value = json.loads(raw)
        if attack == "meta":
            value["mission_id"] = "forged-but-valid-json"
        elif attack == "review":
            next(iter(value["work_packages"].values()))["review_result"].pop("verdict")
        elif attack == "identity":
            value["mission_type"] = "wrong-mission"
        target.write_text(json.dumps(value, separators=(",", ":")), encoding="utf-8")
    git(recovery_repo, "add", path)
    with pytest.raises(AssertionError, match=re.escape(path) + ".*reviewed"):
        run_gate(recovery_repo, monkeypatch)
    target.write_bytes(raw)
    git(recovery_repo, "add", path)
    run_gate(recovery_repo, monkeypatch)


@pytest.mark.parametrize("path", [gate.CYCLIC + "/meta.json", gate.MOVES[0][1]])
def test_repeat_recovery_refuses_divergent_completed_proof(
    recovery_repo: Path,
    path: str,
) -> None:
    recover(recovery_repo)
    target = recovery_repo / path
    raw = target.read_bytes()
    target.write_bytes(raw + b" ")
    with pytest.raises(AssertionError, match="(restore collision|completed relocation proof)"):
        recover(recovery_repo)
    target.write_bytes(raw)
    recover(recovery_repo)


def test_gate_does_not_repair_its_inputs(recovery_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    paths = [p for root in ("kitty-specs", "docs") for p in (recovery_repo / root).rglob("*") if p.is_file()]
    before = {p: (p.read_bytes(), p.lstat().st_mode, p.lstat().st_mtime_ns) for p in paths}
    run_gate(recovery_repo, monkeypatch)
    assert before == {p: (p.read_bytes(), p.lstat().st_mode, p.lstat().st_mtime_ns) for p in paths}


def mutant_module(tmp_path: Path, old: str, new: str) -> types.ModuleType:
    source = Path(gate.__file__).read_text(encoding="utf-8")
    assert old in source
    file = tmp_path / "mutated_gate.py"
    file.write_text(source.replace(old, new, 1), encoding="utf-8")
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location("wp12_mutated_gate", file)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_structural_floor_detects_deleted_gate(tmp_path: Path) -> None:
    module = mutant_module(tmp_path, "def test_archive_baseline_is_non_empty()", "def removed_gate()")
    with pytest.raises(AssertionError, match="protected gate function missing"):
        module.test_archive_freeze_gate_uses_the_exp_port_base_without_import_time_skip()


def test_prefix_self_mutation_breaks_independent_control(archive_repo: Path, tmp_path: Path) -> None:
    module = mutant_module(tmp_path, "if after == before:", "if True:")
    module.__dict__["REPO_ROOT"] = archive_repo
    path = archive_repo / "kitty-ops/lifecycle.jsonl"
    path.write_bytes(b"rewritten\n")
    with pytest.raises(pytest.fail.Exception, match="DID NOT RAISE"), pytest.raises(AssertionError, match="historical byte prefix"):
        module.test_no_preexisting_archived_file_was_modified()


@pytest.mark.parametrize("attack", ["destination", "receipt"])
def test_removing_exact_candidate_proof_breaks_controls(
    recovery_repo: Path,
    tmp_path: Path,
    attack: str,
) -> None:
    old = '''    assert index.get(path) == expected, f"{path}: tracked index blob/mode differs from reviewed proof"
    raw = _disk(path, expected.mode)
    assert raw == expected.read(), f"{path}: reviewed bytes changed"'''
    replacement = "    raw = _disk(path, expected.mode)"
    if attack == "receipt":
        # Deliberately let the candidate index choose its own trusted hash.
        replacement = "    if path == RECEIPT:\n        expected = index[path]\n" + old
    module = mutant_module(tmp_path, old, replacement)
    module.__dict__["REPO_ROOT"] = recovery_repo
    path = gate.MOVES[0][1] if attack == "destination" else gate.RECEIPT
    target = recovery_repo / path
    target.write_bytes(target.read_bytes() + b" ")
    git(recovery_repo, "add", path)
    with pytest.raises(pytest.fail.Exception, match="DID NOT RAISE"), pytest.raises(AssertionError, match="reviewed"):
        module.test_no_preexisting_archived_file_was_modified()


def test_omitting_archive_root_breaks_independent_control(
    archive_repo: Path,
    tmp_path: Path,
) -> None:
    path = archive_repo / ".kittify/missions/old/retrospective.yaml"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"old")
    git(archive_repo, "add", ".")
    git(archive_repo, "commit", "-m", "Fourth root baseline")
    git(archive_repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    module = mutant_module(tmp_path, '    ".kittify/missions/",\n', "")
    module.__dict__["REPO_ROOT"] = archive_repo
    path.write_bytes(b"changed")
    with pytest.raises(pytest.fail.Exception, match="DID NOT RAISE"), pytest.raises(AssertionError, match="ordinary archive"):
        module.test_no_preexisting_archived_file_was_modified()


def test_public_next_appends_real_lifecycle_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from typer.testing import CliRunner
    from specify_cli import app
    from tests.specify_cli.next.test_next_invocation_lifecycle_seam import (
        _scaffold_project,
        _write_three_step_input_mission,
    )

    # Reuse the established fixture's identity/runtime setup, retaining the
    # real preflight (including its uninitialized-charter warning).
    slug, mission_type = "wp12-lifecycle-mission", "wp12-lifecycle-input"
    repo = _scaffold_project(tmp_path, mission_slug=slug, mission_type=mission_type)
    _write_three_step_input_mission(repo, mission_type=mission_type)
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    lifecycle = append(repo, "wp12::existing-proof")
    before = lifecycle.read_bytes()
    git(repo, "add", "kitty-ops/lifecycle.jsonl")
    git(repo, "commit", "-m", "Lifecycle prefix before public next")
    git(repo, "update-ref", "refs/remotes/origin/main", "HEAD")
    runner = CliRunner()
    args = ["next", "--agent", "wp12", "--mission", slug, "--json"]
    query = runner.invoke(app, args)
    assert query.exit_code == 0, query.output
    assert json.loads(query.stdout)["kind"] == "query"
    assert lifecycle.read_bytes() == before
    issue = runner.invoke(app, [*args, "--result", "success"])
    assert issue.exit_code == 0, issue.output
    assert json.loads(issue.stdout)["kind"] == "step"
    # The requested fixture action has no output contract; record its actual
    # completion before reporting success, then answer the issued decision.
    (repo / "step-one-complete.txt").write_text("Executed fixture step_one.\n", encoding="utf-8")
    decision = runner.invoke(app, [*args, "--result", "success"])
    assert decision.exit_code == 0, decision.output
    payload = json.loads(decision.stdout)
    assert payload["kind"] == "decision_required"
    answer = runner.invoke(app, [*args, "--result", "success", "--answer", "yes", "--decision-id", payload["decision_id"]])
    assert answer.exit_code == 0, answer.output
    assert json.loads(answer.stdout)["kind"] == "step"
    after = lifecycle.read_bytes()
    assert after.startswith(before) and len(after) > len(before)
    records = [ProfileInvocationRecord.from_dict(json.loads(row)) for row in after[len(before) :].splitlines()]
    assert any(record.phase == "started" for record in records)
    assert any(record.phase == "completed" for record in records)
    run_gate(repo, monkeypatch)
