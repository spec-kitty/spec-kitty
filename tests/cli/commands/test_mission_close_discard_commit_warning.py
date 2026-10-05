"""The warning ``mission close --discard`` prints when the flatten commit fails (#5078, #5750).

``_commit_flattened_meta`` is fail-open: a refused bookkeeping commit never turns a completed discard
into an error, but the warning must say what is true (``meta.json`` is left uncommitted) and name only
a command that recovers (the idempotent re-run of the same discard from the project root), never a raw
git recipe. An integration test drives the same arm end to end
(``tests/integration/test_issue_3716_discard_transactional_close_guard.py``, which does not run per
pull request); this one lives in the per-PR ``cli`` home and uses a real repository whose
``pre-commit`` hook refuses every commit. No product code is patched.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.cli.commands import mission_type

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.regression]

_SLUG = "discard-warning-mission"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def _repo_with_a_flattened_meta(tmp_path: Path) -> tuple[Path, Path]:
    subprocess.run(["git", "init", "-q", "-b", "main", str(tmp_path)], check=True, capture_output=True)
    for key, value in (("user.email", "test@test.com"), ("user.name", "Test"), ("commit.gpgsign", "false")):
        _git(tmp_path, "config", key, value)
    feature_dir = tmp_path / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)
    meta_path = feature_dir / "meta.json"
    meta_path.write_text(json.dumps({"mission_slug": _SLUG, "target_branch": "topic", "coordination_branch": "kitty/mission-gone"}), encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "init")
    _git(tmp_path, "checkout", "-q", "-b", "topic")
    meta_path.write_text(json.dumps({"mission_slug": _SLUG, "target_branch": "topic"}), encoding="utf-8")  # the flatten
    return tmp_path, feature_dir


def test_a_refused_flatten_commit_warns_with_the_idempotent_rerun_and_leaves_meta_uncommitted(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    repo, feature_dir = _repo_with_a_flattened_meta(tmp_path)
    hook = repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho 'commit refused by test hook' >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)

    mission_type._commit_flattened_meta(repo, feature_dir, _SLUG)  # fail-open: never raises

    flat = " ".join(capsys.readouterr().out.split())
    assert f"discard of {_SLUG} flattened meta.json but could not commit it" in flat
    assert "meta.json is left uncommitted." in flat
    assert f"`spec-kitty mission close --mission {_SLUG} --discard --force`" in flat
    assert "commit refused by test hook" in flat  # the real cause is shown
    guidance = flat.split("From the project root", 1)[1]  # the failure text above it quotes git itself
    for forbidden in ("git -C", "git add", "git commit", "safe-commit", "SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS"):
        assert forbidden not in guidance, (forbidden, guidance)
    assert f"kitty-specs/{_SLUG}/meta.json" in _git(repo, "status", "--porcelain")


def test_an_unchanged_meta_is_a_silent_no_op(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    repo, feature_dir = _repo_with_a_flattened_meta(tmp_path)
    _git(repo, "checkout", "--", str(feature_dir / "meta.json"))

    mission_type._commit_flattened_meta(repo, feature_dir, _SLUG)

    assert capsys.readouterr().out == ""
