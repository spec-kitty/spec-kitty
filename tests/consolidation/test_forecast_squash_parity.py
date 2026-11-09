"""The dry-run forecast runs the content check of the real run's strategy (#7244).

``MergeOutcomeVerifier.forecast_content_verdict`` is the forecast's one entry into the
verifier: with a squashed tree it runs the squash blob attribution the real squash gate
runs, otherwise the per-commit closed-world scan the real merge / rebase gate runs.
The integration parity (dry run vs real run through the CLI) lives in
``tests/integration/test_consolidate_upgraded_mission_recovery.py``.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
import typer

from specify_cli.consolidation import claim_inputs, forecast
from specify_cli.consolidation.reconciliation import (
    ApprovedWpCommitSet,
    MergeOutcomeVerifier,
    VerifyResult,
    VerifyStatus,
)

pytestmark = [pytest.mark.git_repo]


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def _commit(repo: Path, path: str, content: str, message: str) -> str:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(repo, "add", path)
    _git(repo, "commit", "-qm", message)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q", "-b", "main")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    _commit(tmp_path, "README.md", "base\n", "base")
    return tmp_path


def _claim(base: str, **overrides: Any) -> ApprovedWpCommitSet:
    fields: dict[str, Any] = {
        "approved": {"WP01": ("a" * 40,)},
        "manifest_wp_ids": frozenset({"WP01"}),
        "surface_resolved": True,
        "enforce_closed_world": True,
        "excluded_window_base": base,
        "mission_slug": "m",
    }
    fields.update(overrides)
    return ApprovedWpCommitSet(**fields)


def test_squashed_tree_runs_blob_attribution_not_the_per_commit_scan(repo: Path) -> None:
    """A commit no WP authored, whose content the squash leaves on the target, is attributed by blob."""
    base = _git(repo, "rev-parse", "HEAD")
    sha = _commit(repo, "src/a.py", "A = 1\n", "unattributed commit")
    blob = _git(repo, "rev-parse", f"{sha}:src/a.py")
    tree = _git(repo, "rev-parse", f"{sha}^{{tree}}")
    claim = _claim(base, authored_blobs=frozenset({("src/a.py", blob)}))
    verifier = MergeOutcomeVerifier(repo)

    assert verifier._unattributable_in(("main",), claim), "control: the per-commit scan calls the commit un-attributable"
    assert verifier.forecast_content_verdict(("main",), claim, squashed_tree=tree).status is VerifyStatus.PASS


def test_squashed_tree_fails_on_a_blob_no_lane_authored(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    sha = _commit(repo, "src/a.py", "A = 1\n", "content")
    tree = _git(repo, "rev-parse", f"{sha}^{{tree}}")
    claim = _claim(base, authored_blobs=frozenset({("src/a.py", "f" * 40)}))

    result = MergeOutcomeVerifier(repo).forecast_content_verdict(("main",), claim, squashed_tree=tree)

    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    assert [path for path, _blob in result.divergence.unattributable_blobs] == ["src/a.py"]


def test_squashed_tree_refuses_when_authorship_could_not_be_built(repo: Path) -> None:
    """The same fail-closed REFUSE the real squash gate gives a claim with commits but no authored blobs."""
    base = _git(repo, "rev-parse", "HEAD")
    sha = _commit(repo, "src/a.py", "A = 1\n", "content")
    tree = _git(repo, "rev-parse", f"{sha}^{{tree}}")

    result = MergeOutcomeVerifier(repo).forecast_content_verdict(("main",), _claim(base), squashed_tree=tree)

    assert result.status is VerifyStatus.REFUSE


def test_without_a_squashed_tree_the_per_commit_scan_runs(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    sha = _commit(repo, "src/a.py", "A = 1\n", "unattributed commit")
    blob = _git(repo, "rev-parse", f"{sha}:src/a.py")
    claim = _claim(base, authored_blobs=frozenset({("src/a.py", blob)}))

    result = MergeOutcomeVerifier(repo).forecast_content_verdict(("main",), claim, squashed_tree=None)

    assert result.status is VerifyStatus.FAIL
    assert result.divergence is not None
    assert [commit for commit, _pid in result.divergence.unattributable_content] == [sha]


def test_without_a_squashed_tree_an_attributed_window_passes(repo: Path) -> None:
    base = _git(repo, "rev-parse", "HEAD")
    sha = _commit(repo, "src/a.py", "A = 1\n", "authored commit")
    claim = _claim(base, authored_shas=frozenset({sha}))

    assert MergeOutcomeVerifier(repo).forecast_content_verdict(("main",), claim, squashed_tree=None).is_pass


def test_forecast_renders_a_content_refuse_as_a_claim_refusal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A REFUSE from the content check is reported with the claim-refusal code, never as a pass."""
    claim = ApprovedWpCommitSet(approved={"WP01": ("a" * 40,)}, manifest_wp_ids=frozenset({"WP01"}), surface_resolved=True)
    seen: dict[str, object] = {}

    def _verdict(_self: MergeOutcomeVerifier, refs: tuple[str, ...], _claim: ApprovedWpCommitSet, *, squashed_tree: str | None) -> VerifyResult:
        seen["squashed_tree"] = squashed_tree
        return VerifyResult.refused("authorship could not be built.")

    monkeypatch.setattr(forecast, "get_main_repo_root", lambda root: root)
    monkeypatch.setattr(forecast, "_declared_with_recorded", lambda *args, **kwargs: ((), {}))
    monkeypatch.setattr(forecast, "resolve_commit", lambda repo, ref: "b" * 40)
    from types import SimpleNamespace

    import specify_cli.status as _status_pkg  # #7276: callers import the read door from the package

    monkeypatch.setattr(_status_pkg, "resolve_status_read", lambda repo, mission: SimpleNamespace(path=tmp_path, ref=None))
    monkeypatch.setattr(claim_inputs, "build_approved_wp_set", lambda *args, **kwargs: claim)
    monkeypatch.setattr(MergeOutcomeVerifier, "forecast_content_verdict", _verdict)

    class _Manifest:
        mission_branch = "kitty/mission-m"
        lanes: list[object] = []

    with pytest.raises(typer.Exit) as exc_info:
        forecast._refuse_unattributable_in_forecast(
            repo_root=tmp_path,
            resolved_feature="m",
            resolved_target_branch="main",
            lanes_manifest=_Manifest(),
            dependency_refs=(),
            json_output=True,
            squashed_tree="c" * 40,
        )

    assert exc_info.value.exit_code == 1
    assert seen["squashed_tree"] == "c" * 40
    payload = json.loads(capsys.readouterr().out)
    assert payload["error_code"] == forecast.CLAIM_REFUSED_FORECAST
    assert payload["error"].startswith("Reconciliation would REFUSE (fail-closed): authorship could not be built. The real run")
