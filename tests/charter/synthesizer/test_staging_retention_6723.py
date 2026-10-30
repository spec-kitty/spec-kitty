"""#6723 -- a refused synthesis keeps a bounded number of failed staging dirs.

Every refused ``charter synthesize`` / ``charter resynthesize`` preserves its
staging dir as ``.kittify/charter/.staging/<run_id>.failed/`` with a
``cause.yaml`` for diagnosis. Nothing pruned them, so a project that keeps being
refused accumulated one directory per attempt (#4226 counted 15, then 16).

The retention bound lives in the staging lifecycle (``StagingDir``), which every
refusing caller passes through. These tests drive that seam directly and then
once through the real ``charter synthesize`` CLI.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner, Result

from charter.activation.synthesizer.path_guard import PathGuard
from charter.activation.synthesizer.staging import DEFAULT_KEEP_FAILED_RUNS, StagingDir
from specify_cli.cli.commands.charter import app
from tests._support.charter_cwd import CHARTER_FIND_REPO_ROOT

RUN_PREFIX = "01M6723TESTSTAGING"
STAGING_REL = Path(".kittify") / "charter" / ".staging"

# --- Real-CLI fixture seed (same shape as test_collision_refusal_6510.py) ---

_GENERATED = Path(".kittify/charter/generated")
_PLURALS = {"directive": "directives", "tactic": "tactics", "styleguide": "styleguides"}

_OWN_STEM = "001-project-intent-directive"
_OWN_ID = "PROJECT_001"

_ANSWERS = (
    "schema_version: '1'\nmission: software-dev\nprofile: minimal\nanswers:\n"
    "  mission_type: software_dev\n  testing_philosophy: test-driven\n  risk_appetite: moderate\n"
    "selected_paradigms: []\nselected_directives: []\navailable_tools: []\n"
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_repo_root(tmp_path: Path) -> Path:
    """A temporary repo root with the two directories PathGuard allows."""
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / ".kittify" / "charter").mkdir(parents=True)
    (repo / ".kittify" / "charter-packs").mkdir(parents=True)
    return repo


def _run_id(n: int) -> str:
    return f"{RUN_PREFIX}{n:04d}"


def _fail_run(repo: Path, n: int, reason: str | None = None) -> Path:
    """Create a staging dir and preserve it as a failure; return the .failed dir."""
    run_id = _run_id(n)
    stage = StagingDir.create(repo, run_id)
    stage.commit_to_failed(reason or f"refusal {n}")
    return stage.root.parent / f"{run_id}.failed"


def _failed_dirs(repo: Path) -> list[Path]:
    staging = repo / STAGING_REL
    if not staging.exists():
        return []
    return sorted(p for p in staging.iterdir() if p.is_dir() and p.name.endswith(".failed"))


def _cause_reason(failed_dir: Path) -> str:
    return yaml.safe_load((failed_dir / "cause.yaml").read_text(encoding="utf-8"))["reason"]


def _set_mtime(path: Path, stamp: float) -> None:
    os.utime(path, (stamp, stamp))


# ---------------------------------------------------------------------------
# Lifecycle: the bound
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_six_refusals_leave_the_retention_bound(tmp_path: Path) -> None:
    """The reported defect: six refused runs used to leave six failed dirs."""
    repo = _make_repo_root(tmp_path)

    for n in range(6):
        _fail_run(repo, n)

    failed = _failed_dirs(repo)
    assert len(failed) == DEFAULT_KEEP_FAILED_RUNS, [p.name for p in failed]
    assert len(failed) < 6


@pytest.mark.unit
def test_latest_failure_and_its_cause_survive(tmp_path: Path) -> None:
    """The failure the command just reported is always diagnosable."""
    repo = _make_repo_root(tmp_path)

    for n in range(5):
        last = _fail_run(repo, n, reason=f"distinct refusal {n}")

    assert last.is_dir(), "the newest preserved failure must still exist"
    assert "distinct refusal 4" in _cause_reason(last)
    assert _run_id(4) in {p.name.removesuffix(".failed") for p in _failed_dirs(repo)}


@pytest.mark.unit
def test_existing_overflow_is_reduced_not_frozen(tmp_path: Path) -> None:
    """A tree that already holds more than the bound is brought down to it."""
    repo = _make_repo_root(tmp_path)
    staging = repo / STAGING_REL

    # Hand-build an overflow the way an older version left it behind.
    for n in range(6):
        failed = staging / f"{_run_id(n)}.failed"
        failed.mkdir(parents=True)
        (failed / "cause.yaml").write_text(f"reason: old refusal {n}\n", encoding="utf-8")

    assert len(_failed_dirs(repo)) == 6

    _fail_run(repo, 6)

    assert len(_failed_dirs(repo)) == DEFAULT_KEEP_FAILED_RUNS


@pytest.mark.unit
def test_live_staging_directory_is_never_removed(tmp_path: Path) -> None:
    """An in-progress run's workspace is not a retention candidate."""
    repo = _make_repo_root(tmp_path)
    live = StagingDir.create(repo, _run_id(99))
    marker = live.root / "charter-packs" / "directive" / "in-flight.directive.yaml"
    marker.write_text("id: PROJECT_001\n", encoding="utf-8")
    for n in range(DEFAULT_KEEP_FAILED_RUNS + 2):
        _fail_run(repo, n)

    assert live.root.is_dir(), "a live staging dir must survive retention"
    assert marker.read_text(encoding="utf-8") == "id: PROJECT_001\n"
    assert not (live.root.parent / f"{_run_id(99)}.failed").exists()


@pytest.mark.unit
def test_equal_mtimes_resolve_deterministically(tmp_path: Path) -> None:
    """A restored tree with identical mtimes still prunes the same entries."""
    repo = _make_repo_root(tmp_path)
    for n in range(5):
        _fail_run(repo, n)
    stamp = 1_700_000_000.0
    for failed in _failed_dirs(repo):
        _set_mtime(failed, stamp)

    _fail_run(repo, 5)  # fresh mtime: newest, then the name tiebreak decides

    kept = {p.name for p in _failed_dirs(repo)}
    assert len(kept) == DEFAULT_KEEP_FAILED_RUNS
    assert kept == {f"{_run_id(5)}.failed", f"{_run_id(4)}.failed", f"{_run_id(3)}.failed"}


@pytest.mark.unit
def test_removal_failure_does_not_raise_and_leaves_the_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Retention never masks the synthesis failure."""
    repo = _make_repo_root(tmp_path)
    for n in range(DEFAULT_KEEP_FAILED_RUNS + 2):
        _fail_run(repo, n)
    victim = _failed_dirs(repo)[0]

    real_rmtree = PathGuard.rmtree

    def _denied(self: PathGuard, path: Path, caller: str = "rmtree") -> None:
        if path == victim:
            raise PermissionError(13, "Permission denied", str(path))
        real_rmtree(self, path, caller=caller)

    monkeypatch.setattr(PathGuard, "rmtree", _denied)

    _fail_run(repo, 10)  # must not raise

    assert victim.is_dir(), "an unremovable directory simply stays"
    assert (repo / STAGING_REL / f"{_run_id(10)}.failed").is_dir()


@pytest.mark.unit
def test_stale_bundle_warning_sees_the_bounded_set(tmp_path: Path) -> None:
    """``charter bundle validate`` warns for at most the retained dirs."""
    from charter.bundle import validate_synthesis_state

    repo = _make_repo_root(tmp_path)
    for n in range(5):
        _fail_run(repo, n)

    result = validate_synthesis_state(repo)

    stale = [w for w in result.warnings if "Stale failed staging directory" in w]
    assert len(stale) == DEFAULT_KEEP_FAILED_RUNS


@pytest.mark.unit
def test_refusal_text_states_the_enforced_bound() -> None:
    """FR-007/FR-008: the operator text and the enforced number share one source."""
    from charter.activation.synthesizer.errors import NeutralityGateViolation, StagingPromoteError
    from charter.activation.synthesizer.staging import retention_hint

    promote = str(StagingPromoteError(run_id="X", staging_dir="/tmp/run-X", cause="boom"))
    neutrality = str(NeutralityGateViolation(artifact_urn="tactic:t", detected_terms=("java",), staging_dir=Path("/tmp/run-Y")))

    for message in (promote, neutrality):
        assert retention_hint() in message
        assert f"the newest {DEFAULT_KEEP_FAILED_RUNS}" in message


# ---------------------------------------------------------------------------
# Real CLI: a "synthesized once" project whose publish target is blocked
# ---------------------------------------------------------------------------


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _invoke(*args: str) -> Result:
    return runner.invoke(app, list(args), catch_exceptions=False)


def _write_generated(root: Path, kind: str, artifact_id: str, body: dict[str, Any], filename: str | None = None) -> None:
    folder = root / _GENERATED / _PLURALS[kind]
    folder.mkdir(parents=True, exist_ok=True)
    name = filename or f"{artifact_id}.{kind}.yaml"
    (folder / name).write_text(yaml.safe_dump({"id": artifact_id, "schema_version": "1.0", **body}), encoding="utf-8")


def _write_tactic(root: Path, tactic_id: str) -> None:
    _write_generated(
        root,
        "tactic",
        tactic_id,
        {"name": tactic_id, "purpose": "p", "steps": [{"title": "s", "description": "d"}]},
    )


def _build_template(root: Path) -> None:
    _git(root, "init", "--initial-branch=main")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    answers = root / ".kittify" / "charter" / "interview" / "answers.yaml"
    answers.parent.mkdir(parents=True, exist_ok=True)
    answers.write_text(_ANSWERS, encoding="utf-8")
    generated = _invoke("generate", "--from-interview")
    assert generated.exit_code == 0, generated.output
    own = {"title": "Project Intent Directive", "intent": "Serve the outcome.", "enforcement": "required"}
    _write_generated(root, "directive", _OWN_ID, own, filename=f"{_OWN_STEM}.directive.yaml")
    risk = {"title": "Risk Appetite Directive", "intent": "Take moderate risks.", "enforcement": "advisory"}
    _write_generated(root, "directive", "PROJECT_002", risk, filename="002-risk-appetite-directive.directive.yaml")
    _write_tactic(root, "testing-philosophy-tactic")
    _write_tactic(root, "how-we-apply-directive-003")
    _write_tactic(root, "how-we-apply-project-001")
    _write_generated(root, "styleguide", "testing-style-guide", {"title": "Testing", "scope": "code", "principles": ["Be good."]})
    first = _invoke("synthesize", "--json")
    assert first.exit_code == 0, first.output
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", "synthesized once")


@pytest.fixture(scope="module")
def synthesized_template(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    root = tmp_path_factory.mktemp("retention-6723")
    with pytest.MonkeyPatch.context() as mp:
        mp.chdir(root)
        mp.setattr(CHARTER_FIND_REPO_ROOT, lambda *args, **kwargs: root)
        _build_template(root)
    yield root


@pytest.mark.integration
@pytest.mark.git_repo
def test_repeated_cli_refusals_keep_the_bound_and_a_readable_latest_cause(
    tmp_path: Path, synthesized_template: Path, charter_cwd_isolation: Callable[..., Path]
) -> None:
    """Repeated ``charter synthesize`` refusals leave three dirs, newest diagnosable."""
    root = tmp_path / "project"
    shutil.copytree(synthesized_template, root, symlinks=True)
    project = charter_cwd_isolation(root)

    blocker = project / ".kittify" / "charter-packs" / "directive" / "002-risk-appetite-directive.directive.yaml"
    blocker.unlink()
    blocker.mkdir()
    generated = project / _GENERATED / "directives" / "002-risk-appetite-directive.directive.yaml"
    generated.write_text(
        yaml.safe_dump(
            {
                "id": "PROJECT_002",
                "schema_version": "1.0",
                "title": "Risk Appetite Directive",
                "intent": "Take moderate risks, revised.",
                "enforcement": "advisory",
            }
        ),
        encoding="utf-8",
    )

    last_output = ""
    for _ in range(5):
        result = _invoke("synthesize", "--json")
        if result.exit_code == 0:
            pytest.fail(f"synthesis unexpectedly succeeded: {result.output}")
        last_output = result.output

    failed = _failed_dirs(project)
    assert len(failed) == DEFAULT_KEEP_FAILED_RUNS, [p.name for p in failed]

    named = [p for p in failed if p.name.removesuffix(".failed") in last_output]
    assert named, f"the refusal must name a preserved directory: {last_output[-2000:]}"
    assert (named[0] / "cause.yaml").is_file()
    assert "StagingPromoteError" in _cause_reason(named[0])


# ---------------------------------------------------------------------------
# Edge branches of the retention pass itself
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_unreadable_staging_root_is_not_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A `.staging` root that cannot be listed leaves the refusal intact."""
    from charter.activation.synthesizer.staging import retain_failed_staging_dirs

    repo = _make_repo_root(tmp_path)
    guard = PathGuard(repo)

    def _denied(self: Path) -> object:
        raise PermissionError(13, "Permission denied", str(self))

    monkeypatch.setattr(Path, "iterdir", _denied)

    assert retain_failed_staging_dirs(guard, repo / STAGING_REL, keep=1) == ()


@pytest.mark.unit
def test_entry_whose_metadata_cannot_be_read_is_skipped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """One unreadable entry does not stop the surplus from being pruned."""
    from charter.activation.synthesizer.staging import retain_failed_staging_dirs

    repo = _make_repo_root(tmp_path)
    staging = repo / STAGING_REL
    # Built by hand so production retention (keep=3) cannot prune a fourth entry.
    for n in range(4):
        failed = staging / f"{_run_id(n)}.failed"
        failed.mkdir(parents=True)
        (failed / "cause.yaml").write_text(f"reason: refusal {n}\n", encoding="utf-8")
    unreadable = staging / f"{_run_id(0)}.failed"
    real_stat = Path.stat

    def _stat(self: Path, *args: object, **kwargs: object) -> object:
        if self == unreadable:
            raise PermissionError(13, "Permission denied", str(self))
        return real_stat(self, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", _stat)

    removed = retain_failed_staging_dirs(PathGuard(repo), repo / STAGING_REL, keep=1)

    assert unreadable not in removed
    assert os.path.isdir(unreadable)
    # listdir, not _failed_dirs: the assertion must not call the patched stat.
    assert sorted(os.listdir(repo / STAGING_REL)) == [
        f"{_run_id(0)}.failed",
        f"{_run_id(3)}.failed",
    ]


@pytest.mark.unit
def test_preserved_run_survives_even_outside_the_bound(tmp_path: Path) -> None:
    """An odd ordering cannot remove the run the caller is reporting."""
    from charter.activation.synthesizer.staging import retain_failed_staging_dirs

    repo = _make_repo_root(tmp_path)
    staging = repo / STAGING_REL
    # Built by hand: production retention (keep=3) would prune an older fourth
    # entry before this test could hand a lower bound to the helper.
    for n in range(4):
        failed = staging / f"{_run_id(n)}.failed"
        failed.mkdir(parents=True)
        (failed / "cause.yaml").write_text(f"reason: refusal {n}\n", encoding="utf-8")
    oldest = staging / f"{_run_id(0)}.failed"

    removed = retain_failed_staging_dirs(PathGuard(repo), repo / STAGING_REL, keep=1, preserve=_run_id(0))

    assert oldest.is_dir(), "the preserved run must survive a keep below its rank"
    assert _run_id(0) not in {p.name.removesuffix(".failed") for p in removed}
    # keep=1 keeps the newest, plus the explicitly preserved older run.
    assert len(_failed_dirs(repo)) == 2
