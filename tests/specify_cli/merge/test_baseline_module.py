"""WP05 — guards for the extracted ``merge/baseline.py`` cluster (#2027).

These tests lock the relocation invariants:

* the public API is importable from BOTH the canonical ``specify_cli.merge``
  surface AND the relocated ``specify_cli.merge.baseline`` module;
* the legacy ``cli.commands.merge`` back-compat private aliases remain
  importable (6 pre-existing suites depend on the ``_``-prefixed names);
* a record -> assert round-trip behaves identically through the new module.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MISSION_ID = "01KVCGQCBASELINEMODULE00000"
_MISSION_SLUG = "baseline-module-roundtrip-01kvcgqc"
_TARGET_BRANCH = "main"


def test_public_api_importable_from_merge_package() -> None:
    from specify_cli.merge import (
        BaselineMergeCommitError,
        assert_baseline_merge_commit_on_target,
        record_baseline_merge_commit,
    )

    assert issubclass(BaselineMergeCommitError, RuntimeError)
    assert callable(record_baseline_merge_commit)
    assert callable(assert_baseline_merge_commit_on_target)


def test_public_api_importable_from_baseline_module() -> None:
    from specify_cli.merge.baseline import (
        BaselineMergeCommitError,
        assert_baseline_merge_commit_on_target,
        record_baseline_merge_commit,
    )

    assert issubclass(BaselineMergeCommitError, RuntimeError)
    assert callable(record_baseline_merge_commit)
    assert callable(assert_baseline_merge_commit_on_target)


def test_legacy_private_aliases_importable_from_merge_py() -> None:
    """6 pre-existing suites import these ``_``-prefixed names directly."""
    from specify_cli.cli.commands.merge import (
        BaselineMergeCommitError as LegacyError,
        _assert_baseline_merge_commit_on_target,
        _read_committed_meta_json,
        _record_baseline_merge_commit,
        _recorded_baseline_from_working_meta,
    )
    from specify_cli.merge.baseline import BaselineMergeCommitError as CanonicalError

    # The legacy surface re-exports the canonical symbol (identity preserved).
    assert LegacyError is CanonicalError
    assert callable(_record_baseline_merge_commit)
    assert callable(_assert_baseline_merge_commit_on_target)
    assert callable(_recorded_baseline_from_working_meta)
    assert callable(_read_committed_meta_json)


def _git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_record_then_assert_roundtrip(tmp_path: Path) -> None:
    """A modern-mission record -> commit -> assert round-trip succeeds."""
    from specify_cli.merge.baseline import (
        assert_baseline_merge_commit_on_target,
        record_baseline_merge_commit,
    )

    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-b", _TARGET_BRANCH)
    _git(repo_root, "config", "user.email", "pedro@example.com")
    _git(repo_root, "config", "user.name", "Python Pedro")

    feature_dir = repo_root / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    meta_path = feature_dir / "meta.json"
    meta_path.write_text(
        json.dumps({"mission_id": _MISSION_ID, "mission_slug": _MISSION_SLUG}),
        encoding="utf-8",
    )
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "seed")
    baseline_sha = _git(repo_root, "rev-parse", "HEAD")

    written = record_baseline_merge_commit(feature_dir, baseline_sha, mission_id=_MISSION_ID)
    assert written == meta_path
    assert json.loads(meta_path.read_text())["baseline_merge_commit"] == baseline_sha

    # Idempotent: a second record with the value already set is a no-op.
    assert record_baseline_merge_commit(feature_dir, baseline_sha, mission_id=_MISSION_ID) is None

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "record baseline")

    # Durable-in-git verification passes.
    assert_baseline_merge_commit_on_target(
        repo_root,
        _MISSION_SLUG,
        _TARGET_BRANCH,
        baseline_sha,
        feature_dir=feature_dir,
        mission_id=_MISSION_ID,
    )


# ---------------------------------------------------------------------------
# Error / legacy branches (diff-coverage gap closeout — #2028)
#
# These exercise the relocated error-handling branches of the baseline cluster
# that moved verbatim from ``cli/commands/merge.py`` and were never directly
# covered. Fixtures are topology-true (real on-disk meta.json, real git repos
# for the git-show path); the two genuinely-defensive ``meta is None`` /
# non-dict branches are driven via a narrow ``load_meta_fail_closed`` patch
# (FR-007: the reader this module actually calls) and called out explicitly
# below.
# ---------------------------------------------------------------------------


def _write_meta(feature_dir: Path, payload: dict[str, object]) -> Path:
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta_path = feature_dir / "meta.json"
    meta_path.write_text(json.dumps(payload), encoding="utf-8")
    return meta_path


# --- record_baseline_merge_commit ------------------------------------------


def test_record_modern_empty_baseline_raises() -> None:
    """Modern mission + empty baseline SHA -> hard failure (lines 66-71)."""
    from specify_cli.merge.baseline import (
        BaselineMergeCommitError,
        record_baseline_merge_commit,
    )

    with pytest.raises(BaselineMergeCommitError, match="no target baseline SHA"):
        record_baseline_merge_commit(Path("/nonexistent/mission"), "   ", mission_id=_MISSION_ID)


def test_record_legacy_empty_baseline_returns_none() -> None:
    """Legacy mission (no mission_id) + empty baseline -> soft ``None`` (line 71)."""
    from specify_cli.merge.baseline import record_baseline_merge_commit

    assert record_baseline_merge_commit(Path("/nonexistent/mission"), None) is None


def test_record_modern_missing_meta_raises(tmp_path: Path) -> None:
    """Modern mission + absent meta.json -> hard failure (lines 75-79)."""
    from specify_cli.merge.baseline import (
        BaselineMergeCommitError,
        record_baseline_merge_commit,
    )

    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)  # meta.json deliberately absent

    with pytest.raises(BaselineMergeCommitError, match="meta.json is missing"):
        record_baseline_merge_commit(feature_dir, "deadbeef", mission_id=_MISSION_ID)


def test_record_legacy_missing_meta_warns_and_returns_none(tmp_path: Path) -> None:
    """Legacy mission + absent meta.json -> warn + ``None`` (lines 80-84)."""
    from specify_cli.merge.baseline import record_baseline_merge_commit

    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)

    assert record_baseline_merge_commit(feature_dir, "deadbeef") is None


def test_record_modern_corrupt_meta_raises(tmp_path: Path) -> None:
    """Modern mission + malformed meta.json -> hard failure (lines 88-93)."""
    from specify_cli.merge.baseline import (
        BaselineMergeCommitError,
        record_baseline_merge_commit,
    )

    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text("{ not: valid json", encoding="utf-8")

    with pytest.raises(BaselineMergeCommitError, match="meta.json is invalid"):
        record_baseline_merge_commit(feature_dir, "deadbeef", mission_id=_MISSION_ID)


def test_record_legacy_corrupt_meta_warns_and_returns_none(tmp_path: Path) -> None:
    """Legacy mission + malformed meta.json -> warn + ``None`` (lines 94-99)."""
    from specify_cli.merge.baseline import record_baseline_merge_commit

    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text("{ not: valid json", encoding="utf-8")

    assert record_baseline_merge_commit(feature_dir, "deadbeef") is None


def test_record_modern_meta_loads_none_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Modern mission + reader returning ``None`` -> hard failure (102-103).

    DEFENSIVE branch: with the real on-disk contract, an *existing* meta.json
    makes the reader return a dict or raise ``MissionMetaReadError`` — it never
    returns ``None``. We drive it via a narrow patch to lock the guard that
    protects against that contract changing.

    FR-007: the patched name is ``load_meta_fail_closed`` because that is the
    reader ``record_baseline_merge_commit`` now calls. Patching the retired
    ``load_meta`` name would be a no-op that silently exercises nothing.
    """
    from specify_cli.merge import baseline as baseline_mod
    from specify_cli.merge.baseline import (
        BaselineMergeCommitError,
        record_baseline_merge_commit,
    )

    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    _write_meta(feature_dir, {"mission_id": _MISSION_ID})
    monkeypatch.setattr(baseline_mod, "load_meta_fail_closed", lambda _fd: None)

    with pytest.raises(BaselineMergeCommitError, match="could not be loaded"):
        record_baseline_merge_commit(feature_dir, "deadbeef", mission_id=_MISSION_ID)


def test_record_legacy_meta_loads_none_returns_none(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Legacy mission + ``load_meta`` returning ``None`` -> ``None`` (line 107).

    DEFENSIVE branch (see above) — driven via a narrow ``load_meta`` patch.
    """
    from specify_cli.merge import baseline as baseline_mod
    from specify_cli.merge.baseline import record_baseline_merge_commit

    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    _write_meta(feature_dir, {"mission_id": _MISSION_ID})
    monkeypatch.setattr(baseline_mod, "load_meta_fail_closed", lambda _fd: None)

    assert record_baseline_merge_commit(feature_dir, "deadbeef") is None


def test_record_existing_baseline_is_not_overwritten(tmp_path: Path) -> None:
    """An already-recorded ``baseline_merge_commit`` is never overwritten (#4090).

    The baseline half stays idempotent, but the coupled ``merged_at`` marker is
    absent here, so the call still writes it and returns the meta path (folded
    into the bookkeeping commit). The pre-existing baseline is preserved verbatim.
    """
    import json

    from specify_cli.merge.baseline import record_baseline_merge_commit

    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    _write_meta(
        feature_dir,
        {"mission_id": _MISSION_ID, "baseline_merge_commit": "already-set"},
    )

    result = record_baseline_merge_commit(feature_dir, "new-sha", mission_id=_MISSION_ID)
    assert result == feature_dir / "meta.json"  # merged_at was freshly stamped

    written = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert written["baseline_merge_commit"] == "already-set"  # NOT overwritten
    assert str(written.get("merged_at") or "").strip()  # marker landed


def test_record_fully_marked_meta_is_idempotent_noop(tmp_path: Path) -> None:
    """Both markers already present -> a true no-op returning ``None`` (#4090)."""
    from specify_cli.merge.baseline import record_baseline_merge_commit

    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    _write_meta(
        feature_dir,
        {
            "mission_id": _MISSION_ID,
            "baseline_merge_commit": "already-set",
            "merged_at": "2026-08-30T00:00:00+00:00",
        },
    )

    assert record_baseline_merge_commit(feature_dir, "new-sha", mission_id=_MISSION_ID) is None


# --- _recorded_baseline_from_working_meta ----------------------------------


def test_recorded_baseline_none_feature_dir_returns_empty() -> None:
    """``feature_dir is None`` -> empty string (lines 119-120)."""
    from specify_cli.merge.baseline import _recorded_baseline_from_working_meta

    assert _recorded_baseline_from_working_meta(None) == ""


def test_recorded_baseline_corrupt_meta_returns_empty(tmp_path: Path) -> None:
    """Malformed working meta.json -> empty string (lines 123-124)."""
    from specify_cli.merge.baseline import _recorded_baseline_from_working_meta

    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text("{ broken", encoding="utf-8")

    assert _recorded_baseline_from_working_meta(feature_dir) == ""


def test_recorded_baseline_non_dict_meta_returns_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``load_meta`` returning a non-dict -> empty string (line 126).

    DEFENSIVE branch: ``load_meta`` raises ``ValueError`` on a non-dict
    payload rather than returning one, so this guard is unreachable via real
    on-disk state. Driven via a narrow ``load_meta`` patch.
    """
    from specify_cli.merge import baseline as baseline_mod
    from specify_cli.merge.baseline import _recorded_baseline_from_working_meta

    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    _write_meta(feature_dir, {"mission_id": _MISSION_ID})
    monkeypatch.setattr(baseline_mod, "load_meta_fail_closed", lambda _fd: ["not", "a", "dict"])

    assert _recorded_baseline_from_working_meta(feature_dir) == ""


# --- _read_committed_meta_json ---------------------------------------------


def _seed_repo_with_committed_meta(tmp_path: Path, meta_text: str) -> Path:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-b", _TARGET_BRANCH)
    _git(repo_root, "config", "user.email", "pedro@example.com")
    _git(repo_root, "config", "user.name", "Python Pedro")
    feature_dir = repo_root / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(meta_text, encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "seed")
    return repo_root


def test_read_committed_meta_git_show_failure_raises(tmp_path: Path) -> None:
    """A missing committed path -> ``git show`` failure raise (lines 142-147)."""
    from specify_cli.merge.baseline import (
        BaselineMergeCommitError,
        _read_committed_meta_json,
    )

    repo_root = _seed_repo_with_committed_meta(tmp_path, json.dumps({"mission_id": _MISSION_ID}))

    with pytest.raises(BaselineMergeCommitError, match="could not read"):
        _read_committed_meta_json(
            repo_root,
            _TARGET_BRANCH,
            "kitty-specs/does-not-exist/meta.json",
            _MISSION_SLUG,
        )


def test_read_committed_meta_invalid_json_raises(tmp_path: Path) -> None:
    """Committed-but-malformed meta.json -> JSON decode raise (lines 151-152)."""
    from specify_cli.merge.baseline import (
        BaselineMergeCommitError,
        _read_committed_meta_json,
    )

    repo_root = _seed_repo_with_committed_meta(tmp_path, "{ not json at all")

    with pytest.raises(BaselineMergeCommitError, match="not valid JSON"):
        _read_committed_meta_json(
            repo_root,
            _TARGET_BRANCH,
            f"kitty-specs/{_MISSION_SLUG}/meta.json",
            _MISSION_SLUG,
        )


def test_read_committed_meta_non_object_raises(tmp_path: Path) -> None:
    """Committed JSON array (not object) -> raise (line 158)."""
    from specify_cli.merge.baseline import (
        BaselineMergeCommitError,
        _read_committed_meta_json,
    )

    repo_root = _seed_repo_with_committed_meta(tmp_path, json.dumps([1, 2, 3]))

    with pytest.raises(BaselineMergeCommitError, match="not a JSON object"):
        _read_committed_meta_json(
            repo_root,
            _TARGET_BRANCH,
            f"kitty-specs/{_MISSION_SLUG}/meta.json",
            _MISSION_SLUG,
        )


# --- assert_baseline_merge_commit_on_target --------------------------------


def test_assert_legacy_mission_is_skipped() -> None:
    """Legacy mission (no mission_id) -> early return, no git access (line 200)."""
    from specify_cli.merge.baseline import assert_baseline_merge_commit_on_target

    # No exception even though repo/branch are bogus: legacy missions skip.
    assert_baseline_merge_commit_on_target(Path("/nonexistent"), _MISSION_SLUG, _TARGET_BRANCH, None)


def test_assert_modern_no_recorded_baseline_raises(tmp_path: Path) -> None:
    """Modern mission with no recorded/expected baseline -> raise (line 205)."""
    from specify_cli.merge.baseline import (
        BaselineMergeCommitError,
        assert_baseline_merge_commit_on_target,
    )

    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    _write_meta(feature_dir, {"mission_id": _MISSION_ID})  # no baseline_merge_commit

    with pytest.raises(BaselineMergeCommitError, match="no recorded baseline SHA"):
        assert_baseline_merge_commit_on_target(
            tmp_path,
            _MISSION_SLUG,
            _TARGET_BRANCH,
            expected_baseline="   ",
            feature_dir=feature_dir,
            mission_id=_MISSION_ID,
        )


def test_assert_modern_baseline_missing_on_target_raises(tmp_path: Path) -> None:
    """Committed meta lacks ``baseline_merge_commit`` -> raise (lines 215-221)."""
    from specify_cli.merge.baseline import (
        BaselineMergeCommitError,
        assert_baseline_merge_commit_on_target,
    )

    repo_root = _seed_repo_with_committed_meta(tmp_path, json.dumps({"mission_id": _MISSION_ID}))
    feature_dir = repo_root / "kitty-specs" / _MISSION_SLUG

    with pytest.raises(BaselineMergeCommitError, match="is missing from committed"):
        assert_baseline_merge_commit_on_target(
            repo_root,
            _MISSION_SLUG,
            _TARGET_BRANCH,
            expected_baseline="some-captured-sha",
            feature_dir=feature_dir,
            mission_id=_MISSION_ID,
        )


def test_assert_modern_baseline_mismatch_raises(tmp_path: Path) -> None:
    """Committed baseline != recorded/expected -> raise (lines 223-228)."""
    from specify_cli.merge.baseline import (
        BaselineMergeCommitError,
        assert_baseline_merge_commit_on_target,
    )

    repo_root = _seed_repo_with_committed_meta(
        tmp_path,
        json.dumps({"mission_id": _MISSION_ID, "baseline_merge_commit": "committed-sha"}),
    )
    feature_dir = repo_root / "kitty-specs" / _MISSION_SLUG
    # Diverge the *working* meta from the committed copy: the recorded value
    # (read from the working tree) drives ``expected`` and must differ from the
    # committed baseline read via ``git show`` to trigger the mismatch branch.
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": _MISSION_ID, "baseline_merge_commit": "recorded-sha"}),
        encoding="utf-8",
    )

    with pytest.raises(BaselineMergeCommitError, match="does not match the captured"):
        assert_baseline_merge_commit_on_target(
            repo_root,
            _MISSION_SLUG,
            _TARGET_BRANCH,
            expected_baseline="different-captured-sha",
            feature_dir=feature_dir,
            mission_id=_MISSION_ID,
        )
