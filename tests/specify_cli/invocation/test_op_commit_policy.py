"""Unit tests for the Op-record commit-or-skip policy (#6410)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import specify_cli.coordination.coherence as coherence
from specify_cli.invocation import op_commit_policy
from specify_cli.invocation.op_commit_policy import (
    OP_RECORD_PATH_RE,
    OpCommitProbeError,
    PrimaryTracking,
    is_path_ignored,
    op_commit_skip_reason,
    primary_tracks_op_records,
    probe_primary_tracking,
    resolve_primary_refs,
)

pytestmark = pytest.mark.fast

ULID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
RECORD = f"kitty-ops/{ULID}.jsonl"
SPINE = "kitty-ops/op-closures.jsonl"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-c", "user.email=t@example.com", "-c", "user.name=T", "-c", "commit.gpgsign=false", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _repo(path: Path, branch: str = "main") -> Path:
    _git(path, "init", "-b", branch)
    (path / "README.md").write_text("# readme\n", encoding="utf-8")
    _git(path, "add", "README.md")
    _git(path, "commit", "-m", "initial")
    return path


def _commit_file(repo: Path, rel: str, content: str = "{}\n") -> None:
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(repo, "add", "--force", rel)
    _git(repo, "commit", "-m", f"add {rel}")


def test_op_record_regex_matches_coherence_literal() -> None:
    source = Path(coherence.__file__).read_text(encoding="utf-8")
    assert f're.compile(r"{OP_RECORD_PATH_RE.pattern}")' in source


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        (RECORD, True),
        (f"sub/{RECORD}", True),
        ("kitty-ops/ops-index.jsonl", False),
        ("kitty-ops/lifecycle.jsonl", False),
        ("kitty-ops/propagation-errors.jsonl", False),
        (SPINE, False),
        (f"kitty-ops/{ULID.lower()}.jsonl", False),
    ],
)
def test_op_record_regex_shape(path: str, expected: bool) -> None:
    assert bool(OP_RECORD_PATH_RE.search(path)) is expected


def test_origin_less_trunk_only_repo_resolves_no_primary_and_skips(tmp_path: Path) -> None:
    """FR-006: an op(...) record on the issue branch must not make the issue branch primary."""
    repo = _repo(tmp_path, branch="trunk")
    _git(repo, "checkout", "-b", "fix/x")
    _commit_file(repo, RECORD)

    assert resolve_primary_refs(repo) == ()
    tracking = probe_primary_tracking(repo)
    assert tracking == PrimaryTracking(tracked=False, primary=None)
    reason = op_commit_skip_reason(repo, RECORD, tracking=tracking)
    assert reason is not None
    assert "primary branch unresolved" in reason


@pytest.mark.parametrize("special", ["ops-index.jsonl", "lifecycle.jsonl", "propagation-errors.jsonl", "op-closures.jsonl"])
def test_main_tracking_only_special_files_is_not_tracked(tmp_path: Path, special: str) -> None:
    repo = _repo(tmp_path)
    _commit_file(repo, f"kitty-ops/{special}")

    refs = resolve_primary_refs(repo)
    assert refs == ("refs/heads/main",)
    assert primary_tracks_op_records(repo, refs) is False
    reason = op_commit_skip_reason(repo, RECORD, tracking=probe_primary_tracking(repo))
    assert reason is not None
    assert "primary branch (main)" in reason


def test_main_tracking_one_record_is_tracked_positive_control(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _commit_file(repo, RECORD)
    _git(repo, "checkout", "-b", "fix/x")

    refs = resolve_primary_refs(repo)
    assert primary_tracks_op_records(repo, refs) is True
    tracking = probe_primary_tracking(repo)
    assert tracking == PrimaryTracking(tracked=True, primary="main")
    assert op_commit_skip_reason(repo, f"kitty-ops/{'0' * 25}1.jsonl", tracking=tracking) is None


def test_remote_primary_ref_alone_counts_as_tracking(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _commit_file(repo, RECORD)
    sha = _git(repo, "rev-parse", "HEAD")
    _git(repo, "update-ref", "refs/remotes/origin/main", sha)
    _git(repo, "reset", "--hard", "HEAD~1")  # local main no longer has the record

    refs = resolve_primary_refs(repo)
    assert refs == ("refs/heads/main", "refs/remotes/origin/main")
    assert primary_tracks_op_records(repo, refs) is True


def test_origin_head_selects_primary_branch(tmp_path: Path) -> None:
    repo = _repo(tmp_path, branch="trunk")
    sha = _git(repo, "rev-parse", "HEAD")
    _git(repo, "update-ref", "refs/remotes/origin/trunk", sha)
    _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk")

    assert resolve_primary_refs(repo) == ("refs/heads/trunk", "refs/remotes/origin/trunk")


def test_tracked_but_ignored_spine_is_reported_ignored(tmp_path: Path) -> None:
    """``--no-index`` is what makes a tracked path under an ignore rule count."""
    repo = _repo(tmp_path)
    _commit_file(repo, SPINE)
    (repo / ".gitignore").write_text("kitty-ops/\n", encoding="utf-8")

    assert is_path_ignored(repo, SPINE) is True
    assert is_path_ignored(repo, "README.md") is False
    reason = op_commit_skip_reason(repo, SPINE, tracking=PrimaryTracking(tracked=True, primary="main"))
    assert reason is not None
    assert SPINE in reason
    assert "matches an ignore rule" in reason


def test_probe_failure_raises_probe_error(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    with pytest.raises(OpCommitProbeError):
        primary_tracks_op_records(repo, ("refs/heads/does-not-exist",))
    with pytest.raises(OpCommitProbeError):
        is_path_ignored(tmp_path / "not-a-repo", RECORD)


def test_git_launch_failure_is_a_probe_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_args: object, **_kwargs: object) -> None:
        raise FileNotFoundError("git")

    monkeypatch.setattr(op_commit_policy.subprocess, "run", boom)
    with pytest.raises(OpCommitProbeError):
        is_path_ignored(tmp_path, RECORD)


def test_worst_case_primary_probe_stays_within_nfr_001_bound(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Only ``origin/develop`` exists: the costliest path of the ladder (NFR-001).

    origin/HEAD (1) + main/master probes (4) + develop probes (2) = 7 calls to
    resolve, plus at most 2 ``ls-tree`` calls, never more than 9 in total.
    """
    repo = _repo(tmp_path, branch="topic")
    _commit_file(repo, RECORD)
    _git(repo, "update-ref", "refs/remotes/origin/develop", _git(repo, "rev-parse", "HEAD"))
    calls: list[list[str]] = []
    real_run = subprocess.run

    def counting_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return real_run(args, **kwargs)  # type: ignore[call-overload, no-any-return]  # kwargs forwarded verbatim from _git

    monkeypatch.setattr(op_commit_policy.subprocess, "run", counting_run)
    tracking = probe_primary_tracking(repo)

    assert tracking == PrimaryTracking(tracked=True, primary="develop")
    assert len(calls) <= 9


def test_dangling_origin_head_falls_through_to_the_ladder(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    _commit_file(repo, RECORD)
    _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/gone")

    refs = resolve_primary_refs(repo)
    assert refs == ("refs/heads/main",)
    assert primary_tracks_op_records(repo, refs) is True


def test_worst_case_with_dangling_origin_head_stays_within_nfr_001_bound(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A dangling ``origin/HEAD`` plus an ``origin/develop``-only ladder hit (NFR-001).

    symbolic-ref (1) + dangling name (2) + main/master (4) + develop (2) = 9 to
    resolve, then at most 2 ``ls-tree``: at most 11 before ``check-ignore``.
    """
    repo = _repo(tmp_path, branch="topic")
    _commit_file(repo, RECORD)
    _git(repo, "update-ref", "refs/remotes/origin/develop", _git(repo, "rev-parse", "HEAD"))
    _git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/gone")
    calls: list[list[str]] = []
    real_run = subprocess.run

    def counting_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return real_run(args, **kwargs)  # type: ignore[call-overload, no-any-return]  # kwargs forwarded verbatim from _git

    monkeypatch.setattr(op_commit_policy.subprocess, "run", counting_run)
    tracking = probe_primary_tracking(repo)

    assert tracking == PrimaryTracking(tracked=True, primary="develop")
    assert len(calls) <= 11
