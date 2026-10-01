"""Characterisation of every exit path of ``spec-kitty accept`` (WP14 / T075).

``accept()`` is decomposed (FR-026) and then converted onto the validated
owned-checkout fact (FR-001/FR-003). These tests freeze what an operator or an
automation can observe *before* either change: the exit code, the top-level
JSON key set, and the order of the side effects in the ``finally`` block. They
were committed green against the undecomposed command so the refactor is
provably behaviour-preserving.

Isolation: only module attributes of ``specify_cli.cli.commands.accept`` are
patched (one fixture, :func:`harness`); no git, no real acceptance pipeline.
The owned-entry seam is patched in exactly one place (``_patch_owned_entry``)
so the conversion onto the shared owned-checkout helper only moves that target.
"""

from __future__ import annotations

import ast
import inspect
import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any, get_type_hints

import pytest
import typer
from mission_runtime import ActionContextError, MissionTopology, OwnedCheckout, OwnedRefusalCode
from typer.testing import CliRunner

from specify_cli.acceptance import AcceptanceError, ArtifactEncodingError
from specify_cli.cli.commands._owned_checkout import OwnedCheckoutOption
from specify_cli.core.owned_mission import LIFECYCLE_OWNED_TOPOLOGIES
from specify_cli.acceptance.matrix import AcceptanceMatrixParseError
from specify_cli.cli.commands import accept as accept_module
from specify_cli.cli.commands.accept import accept
from specify_cli.consolidation.baseline import PrMergeEvidenceError
from specify_cli.task_utils import TaskCliError
from specify_cli.upgrade.pre30_guard import Pre30LayoutError
from tests._owned_fixtures import RSnapshotter
from tests.specify_cli.cli.commands.test_accept_clean_tree import _create_lane_feature

_SLUG = "characterised-01M3M2ZB"
_OWNED_REFUSAL_CODE = OwnedRefusalCode.OWNED_BRANCH_REFUSED
_OPTION_UNSUPPORTED_CODE = OwnedRefusalCode.OWNED_OPTION_UNSUPPORTED
_MERGE_COMMIT = "abc123"

_runner = CliRunner()
_accept_app = typer.Typer()
_accept_app.command()(accept)


def _flat(output: str) -> str:
    """Collapse rich line wrapping so substring assertions are width independent."""
    return " ".join(output.split())


def _fake_summary(*, ok: bool) -> SimpleNamespace:
    return SimpleNamespace(
        ok=ok,
        warnings=[],
        lanes={},
        feature=_SLUG,
        skipped_checks=[],
        blocked_checks=[],
        recommended_fix_order=[],
        to_dict=lambda: {"ok": ok, "feature": _SLUG},
        outstanding=lambda: {},
        failed_checks=lambda: [],
    )


def _fake_result(summary: SimpleNamespace, *, commit_created: bool = True) -> SimpleNamespace:
    notes: list[str] = []
    return SimpleNamespace(
        summary=summary,
        notes=notes,
        commit_created=commit_created,
        accepted_at="2026-09-29T00:00:00Z",
        accepted_by="tester",
        accept_commit=None,
        parent_commit=None,
        accepted_wps=[],
        merge_pending_wps=[],
        done_wps=[],
        instructions=[],
        cleanup_instructions=[],
        to_dict=lambda: {"accepted_by": "tester", "notes": notes},
    )


@dataclass
class Harness:
    """Recorded calls plus the knobs each characterised path turns."""

    root: Path
    calls: list[str] = field(default_factory=list)
    perform_kwargs: dict[str, Any] = field(default_factory=dict)
    stamp_owned: list[object] = field(default_factory=list)
    choose_mode_requests: list[str] = field(default_factory=list)
    verify_kwargs: dict[str, Any] = field(default_factory=dict)
    summary: SimpleNamespace = field(default_factory=lambda: _fake_summary(ok=True))
    resolved_mode: str | None = None
    owned: object | None = None
    entry_error: Exception | None = None
    repo_root_error: Exception | None = None
    verify_error: Exception | None = None
    collect_error: Exception | None = None
    perform_error: Exception | None = None
    stamp_error: Exception | None = None
    pr_merge_error: Exception | None = None
    residual_error: Exception | None = None

    def invoke(self, *args: str, json_output: bool = True) -> Any:
        argv = [*args, *(["--json"] if json_output else [])]
        return _runner.invoke(_accept_app, argv)

    # -- fakes standing in for accept's collaborators -----------------------

    def find_repo_root(self) -> Path:
        _raise_if(self.repo_root_error)
        return self.root

    def choose_mode(self, requested: str, _repo_root: Path) -> str:
        self.choose_mode_requests.append(requested)
        if self.resolved_mode is not None:
            return self.resolved_mode
        return "local" if requested == "auto" else requested

    def collect(self, *_args: object, **_kwargs: object) -> SimpleNamespace:
        _raise_if(self.collect_error)
        return self.summary

    def verify(self, *_args: object, **kwargs: Any) -> SimpleNamespace:
        self.verify_kwargs = kwargs
        _raise_if(self.verify_error)
        return SimpleNamespace(baseline_merge_commit="base0", pr_merge_commit=_MERGE_COMMIT, anchor_evidence="attested")

    def perform(self, summary: SimpleNamespace, **kwargs: Any) -> SimpleNamespace:
        self.calls.append("perform_acceptance")
        self.perform_kwargs = kwargs
        _raise_if(self.perform_error)
        return _fake_result(summary, commit_created=kwargs["auto_commit"])

    def stamp(self, *_args: object, **kwargs: Any) -> None:
        self.calls.append("stamp")
        self.stamp_owned.append(kwargs.get("owned"))
        _raise_if(self.stamp_error)

    def record_pr_merge(self, *_args: object, **_kwargs: object) -> None:
        self.calls.append("record_pr_merge")
        _raise_if(self.pr_merge_error)

    def residual(self, *_args: object, **_kwargs: object) -> bool:
        self.calls.append("residual")
        _raise_if(self.residual_error)
        return False

    def validate_ownership(self, *_args: object, **_kwargs: object) -> object | None:
        _raise_if(self.entry_error)
        return self.owned


def _raise_if(error: Exception | None) -> None:
    if error is not None:
        raise error


def _fake_owned(root: Path) -> SimpleNamespace:
    """A stand-in for the validated fact (canonical fields only)."""
    return SimpleNamespace(
        repository_root=root / "repo",
        owned_root=root,
        mission_dir=root / "kitty-specs" / _SLUG,
        mission_slug=_SLUG,
    )


def _patch_owned_entry(monkeypatch: pytest.MonkeyPatch, h: Harness) -> None:
    """The single place that stands in for the ownership validator collaborator."""
    monkeypatch.setattr(accept_module, "resolve_owned_or_adopt", h.validate_ownership)
    monkeypatch.setattr(accept_module, "require_unstaged_index", lambda _owned: None)


@pytest.fixture
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Harness:
    h = Harness(root=tmp_path)
    mission_dir = tmp_path / "kitty-specs" / _SLUG
    monkeypatch.setattr(accept_module, "show_banner", lambda: None)
    monkeypatch.setattr(accept_module, "find_repo_root", h.find_repo_root)
    monkeypatch.setattr(accept_module, "resolve_mission_dir_with_bare_modern_fold", lambda *_a, **_k: mission_dir)
    monkeypatch.setattr(accept_module, "choose_mode", h.choose_mode)
    monkeypatch.setattr(accept_module, "_stranded_verdict_provenance_note", lambda _dir: None)
    monkeypatch.setattr(accept_module, "_collect_summary_with_optional_repair", h.collect)
    monkeypatch.setattr(accept_module, "verify_pr_merge_evidence", h.verify)
    monkeypatch.setattr(accept_module, "perform_acceptance", h.perform)
    monkeypatch.setattr(accept_module, "resolve_acceptance_actor", lambda _actor: "tester")
    monkeypatch.setattr(accept_module, "_stamp_birth_cutover_for_accept", h.stamp)
    monkeypatch.setattr(accept_module, "_record_pr_merge_for_accept", h.record_pr_merge)
    monkeypatch.setattr(accept_module, "_commit_residual_acceptance_artifacts", h.residual)
    _patch_owned_entry(monkeypatch, h)
    return h


def _json_keys(output: str) -> set[str]:
    return set(json.loads(output))


@pytest.mark.unit
@pytest.mark.fast
class TestEarlyExits:
    def test_missing_mission_json(self, harness: Harness) -> None:
        result = harness.invoke()
        assert result.exit_code == 2
        assert json.loads(result.output) == {"error": "--mission <slug> is required"}

    def test_missing_mission_human(self, harness: Harness) -> None:
        result = harness.invoke(json_output=False)
        assert result.exit_code == 2
        assert "--mission <slug> is required" in _flat(result.output)

    def test_repo_root_failure_json(self, harness: Harness) -> None:
        harness.repo_root_error = TaskCliError("not a repo")
        result = harness.invoke("--mission", _SLUG)
        assert result.exit_code == 1
        assert _json_keys(result.output) == {"error"}

    def test_repo_root_failure_human(self, harness: Harness) -> None:
        harness.repo_root_error = TaskCliError("not a repo")
        result = harness.invoke("--mission", _SLUG, json_output=False)
        assert result.exit_code == 1
        assert "not a repo" in _flat(result.output)

    def test_owned_refusal_json(self, harness: Harness, tmp_path: Path) -> None:
        harness.entry_error = ActionContextError(_OWNED_REFUSAL_CODE, "wrong branch")
        result = harness.invoke("--mission", _SLUG, "--owned-checkout", str(tmp_path))
        assert result.exit_code == 1
        payload = json.loads(result.stdout)
        assert set(payload) == {"error_code", "error"}
        assert payload == {"error_code": _OWNED_REFUSAL_CODE, "error": "wrong branch"}
        assert harness.calls == []

    def test_owned_refusal_human(self, harness: Harness, tmp_path: Path) -> None:
        harness.entry_error = ActionContextError(_OWNED_REFUSAL_CODE, "wrong branch")
        result = harness.invoke("--mission", _SLUG, "--owned-checkout", str(tmp_path), json_output=False)
        assert result.exit_code == 1
        assert result.stdout == ""
        assert f"Error: [{_OWNED_REFUSAL_CODE}] wrong branch" in _flat(result.stderr)

    @pytest.mark.parametrize("merged_mode", ["local", "checklist"])
    def test_merge_commit_outside_pr_mode(self, harness: Harness, merged_mode: str) -> None:
        harness.resolved_mode = merged_mode
        result = harness.invoke("--mission", _SLUG, "--merge-commit", _MERGE_COMMIT)
        assert result.exit_code == 2
        assert "only valid with --mode pr" in json.loads(result.output)["error"]
        assert harness.calls == []

    def test_merge_commit_outside_pr_mode_human(self, harness: Harness) -> None:
        harness.resolved_mode = "local"
        result = harness.invoke("--mission", _SLUG, "--merge-commit", _MERGE_COMMIT, json_output=False)
        assert result.exit_code == 2
        assert "only valid with --mode pr" in _flat(result.output)

    def test_unverifiable_merge_commit(self, harness: Harness) -> None:
        harness.resolved_mode = "pr"
        harness.verify_error = PrMergeEvidenceError("not a landing")
        result = harness.invoke("--mission", _SLUG, "--merge-commit", _MERGE_COMMIT)
        assert result.exit_code == 1
        assert "Cannot record PR merge for" in json.loads(result.output)["error"]
        assert harness.calls == []

    def test_unverifiable_merge_commit_human(self, harness: Harness) -> None:
        harness.resolved_mode = "pr"
        harness.verify_error = PrMergeEvidenceError("not a landing")
        result = harness.invoke("--mission", _SLUG, "--merge-commit", _MERGE_COMMIT, json_output=False)
        assert result.exit_code == 1
        assert "Cannot record PR merge for" in _flat(result.output)


@pytest.mark.unit
@pytest.mark.fast
class TestSummaryCollectionErrors:
    @pytest.mark.parametrize(
        "error",
        [
            Pre30LayoutError(Path("kitty-specs/x"), ["planned"]),
            AcceptanceError("acceptance refused"),
            AcceptanceMatrixParseError(section="negative_invariants", item_index=0, reason="bad item"),
        ],
        ids=lambda error: type(error).__name__,
    )
    @pytest.mark.parametrize("json_output", [True, False], ids=["json", "human"])
    def test_summary_error_exits_one(self, harness: Harness, error: Exception, json_output: bool) -> None:
        harness.collect_error = error
        result = harness.invoke("--mission", _SLUG, json_output=json_output)
        assert result.exit_code == 1
        if json_output:
            assert json.loads(result.output) == {"error": str(error)}
        else:
            assert _flat(str(error)) in _flat(result.output)
        assert harness.calls == []


@pytest.mark.unit
@pytest.mark.fast
class TestReportModes:
    def test_diagnose_json(self, harness: Harness) -> None:
        result = harness.invoke("--mission", _SLUG, "--diagnose")
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["diagnose"] is True
        assert payload["advisories"] == []
        assert harness.calls == []

    def test_diagnose_human(self, harness: Harness) -> None:
        result = harness.invoke("--mission", _SLUG, "--diagnose", json_output=False)
        assert result.exit_code == 0
        assert "No failed acceptance checks detected." in _flat(result.output)
        assert harness.calls == []

    def test_provenance_advisory_reaches_both_output_lanes(self, harness: Harness, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(accept_module, "_stranded_verdict_provenance_note", lambda _dir: "run the backfill")
        as_json = harness.invoke("--mission", _SLUG, "--diagnose")
        assert json.loads(as_json.output)["advisories"] == ["run the backfill"]
        as_text = harness.invoke("--mission", _SLUG, "--diagnose", json_output=False)
        assert "run the backfill" in _flat(as_text.output)

    @pytest.mark.parametrize(("ok", "exit_code"), [(True, 0), (False, 1)])
    @pytest.mark.parametrize("json_output", [True, False], ids=["json", "human"])
    def test_checklist_mode(self, harness: Harness, ok: bool, exit_code: int, json_output: bool) -> None:
        harness.summary = _fake_summary(ok=ok)
        result = harness.invoke("--mission", _SLUG, "--mode", "checklist", json_output=json_output)
        assert result.exit_code == exit_code
        if json_output:
            assert {"ok", "advisories"} <= _json_keys(result.output)
        assert harness.calls == []

    @pytest.mark.parametrize("extra", [[], ["--allow-fail"]], ids=["strict", "allow-fail"])
    @pytest.mark.parametrize("json_output", [True, False], ids=["json", "human"])
    def test_not_ok_summary_exits_one_either_way(self, harness: Harness, extra: list[str], json_output: bool) -> None:
        harness.summary = _fake_summary(ok=False)
        result = harness.invoke("--mission", _SLUG, *extra, json_output=json_output)
        assert result.exit_code == 1
        if json_output:
            assert {"ok", "advisories"} <= _json_keys(result.output)
        assert harness.calls == []


@pytest.mark.unit
@pytest.mark.fast
class TestPerformAndFinalize:
    def test_happy_path_pr_mode_call_order(self, harness: Harness) -> None:
        result = harness.invoke("--mission", _SLUG, "--mode", "pr", "--merge-commit", _MERGE_COMMIT)
        assert result.exit_code == 0, result.output
        assert harness.calls == ["perform_acceptance", "stamp", "record_pr_merge", "residual"]
        assert harness.perform_kwargs["auto_commit"] is True
        assert {"accepted_by", "notes", "advisories"} <= _json_keys(result.output)

    def test_happy_path_human(self, harness: Harness) -> None:
        result = harness.invoke("--mission", _SLUG, json_output=False)
        assert result.exit_code == 0, result.output
        assert harness.calls == ["perform_acceptance", "stamp", "residual"]
        assert "Acceptance metadata" in _flat(result.output)

    def test_upper_case_mode_is_lowered_before_choose_mode(self, harness: Harness) -> None:
        harness.invoke("--mission", _SLUG, "--mode", "PR")
        assert harness.choose_mode_requests == ["pr"]

    def test_pr_merge_note_is_appended_to_the_result(self, harness: Harness) -> None:
        outcome = harness.invoke("--mission", _SLUG, "--mode", "pr", "--merge-commit", _MERGE_COMMIT)
        assert outcome.exit_code == 0, outcome.output
        assert any(note.startswith("PR merge recorded:") for note in json.loads(outcome.output)["notes"])

    def test_no_commit_with_merge_commit_only_verifies(self, harness: Harness) -> None:
        outcome = harness.invoke("--mission", _SLUG, "--mode", "pr", "--merge-commit", _MERGE_COMMIT, "--no-commit")
        assert outcome.exit_code == 0, outcome.output
        assert harness.calls == ["perform_acceptance"]
        assert harness.perform_kwargs["auto_commit"] is False
        assert any("re-run without --no-commit" in note for note in json.loads(outcome.output)["notes"])

    def test_acceptance_error_still_runs_the_residual_commit(self, harness: Harness) -> None:
        harness.perform_error = AcceptanceError("acceptance refused")
        result = harness.invoke("--mission", _SLUG)
        assert result.exit_code == 1
        assert json.loads(result.output) == {"error": "acceptance refused"}
        assert harness.calls == ["perform_acceptance", "residual"]

    def test_acceptance_error_human(self, harness: Harness) -> None:
        harness.perform_error = AcceptanceError("acceptance refused")
        result = harness.invoke("--mission", _SLUG, json_output=False)
        assert result.exit_code == 1
        assert "acceptance refused" in _flat(result.output)
        assert harness.calls == ["perform_acceptance", "residual"]

    def test_unexpected_error_propagates_after_the_finally_block_ran(self, harness: Harness) -> None:
        harness.perform_error = RuntimeError("boom")
        result = harness.invoke("--mission", _SLUG)
        assert isinstance(result.exception, RuntimeError)
        assert harness.calls == ["perform_acceptance", "stamp", "residual"]

    def test_checklist_never_commits(self, harness: Harness) -> None:
        result = harness.invoke("--mission", _SLUG, "--mode", "checklist", "--no-commit")
        assert result.exit_code == 0
        assert "perform_acceptance" not in harness.calls

    @pytest.mark.parametrize(
        ("field_name", "prefix"),
        [
            ("stamp_error", "Birth-cutover stamp refused:"),
            ("pr_merge_error", "PR merge recording failed:"),
            ("residual_error", "Residual artifact commit failed:"),
        ],
    )
    @pytest.mark.parametrize("json_output", [True, False], ids=["json", "human"])
    def test_finalize_failure_messages(self, harness: Harness, field_name: str, prefix: str, json_output: bool) -> None:
        harness.resolved_mode = "pr"
        setattr(harness, field_name, AcceptanceError("kaput") if field_name == "stamp_error" else RuntimeError("kaput"))
        result = harness.invoke("--mission", _SLUG, "--mode", "pr", "--merge-commit", _MERGE_COMMIT, json_output=json_output)
        assert result.exit_code == 1
        assert f"{prefix} kaput" in (json.loads(result.output)["error"] if json_output else _flat(result.output))

    @pytest.mark.parametrize(
        ("failing", "expected"),
        [
            (("stamp_error", "pr_merge_error", "residual_error"), "Birth-cutover stamp refused:"),
            (("pr_merge_error", "residual_error"), "PR merge recording failed:"),
            (("stamp_error", "residual_error"), "Birth-cutover stamp refused:"),
        ],
    )
    def test_finalize_failure_precedence(self, harness: Harness, failing: tuple[str, ...], expected: str) -> None:
        harness.resolved_mode = "pr"
        for name in failing:
            setattr(harness, name, AcceptanceError("kaput") if name == "stamp_error" else RuntimeError("kaput"))
        result = harness.invoke("--mission", _SLUG, "--mode", "pr", "--merge-commit", _MERGE_COMMIT)
        assert result.exit_code == 1
        assert json.loads(result.output)["error"].startswith(expected)
        assert harness.calls == ["perform_acceptance", "stamp", "record_pr_merge", "residual"]


@pytest.mark.unit
@pytest.mark.fast
class TestOwnedEntry:
    def test_stamp_receives_the_cli_edge_fact(self, harness: Harness, tmp_path: Path) -> None:
        harness.owned = _fake_owned(tmp_path)
        result = harness.invoke("--mission", _SLUG, "--owned-checkout", str(tmp_path))
        assert result.exit_code == 0, result.output
        assert len(harness.stamp_owned) == 1
        assert harness.stamp_owned[0] is harness.owned

    def test_flagless_run_hands_the_stamp_no_fact(self, harness: Harness) -> None:
        result = harness.invoke("--mission", _SLUG)
        assert result.exit_code == 0, result.output
        assert harness.stamp_owned == [None]

    def test_diagnose_with_normalize_encoding_is_refused_in_owned_mode(self, harness: Harness, tmp_path: Path) -> None:
        harness.owned = _fake_owned(tmp_path)
        result = harness.invoke("--mission", _SLUG, "--owned-checkout", str(tmp_path), "--diagnose", "--normalize-encoding")
        assert result.exit_code == 1
        payload = json.loads(result.output)
        assert set(payload) == {"error_code", "error"}
        assert payload["error_code"] == _OPTION_UNSUPPORTED_CODE
        assert harness.calls == []


# ---------------------------------------------------------------------------
# T079 (FR-003 / NFR-002): ownership is validated exactly once per accept run.
# These build real repositories, so they are integration tests, not fast ones.
# ---------------------------------------------------------------------------

_OWNED_TARGET = "codex/owned"


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()


@dataclass(frozen=True)
class ReadyOwnedAccept:
    """An accept-ready single-branch mission owned by ``owned``, plus the repository root checkout."""

    primary: Path
    owned: Path
    sibling: Path
    slug: str


@pytest.fixture
def ready_owned_accept(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, canonical_home: None) -> ReadyOwnedAccept:
    """Repository root checkout R, an owned checkout P holding an accept-ready mission, and a sibling."""
    primary = tmp_path / "primary"
    primary.mkdir()
    original = _create_lane_feature(primary, with_negative_invariant=True)
    slug = original.name
    _git(primary, "update-ref", "refs/remotes/origin/main", "main")
    _git(primary, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    owned, sibling = tmp_path / "owned", tmp_path / "sibling"
    _git(primary, "worktree", "add", "-qb", _OWNED_TARGET, str(owned))
    _git(primary, "worktree", "add", "-qb", "codex/sibling", str(sibling))
    mission = owned / "kitty-specs" / slug
    meta_path = mission / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update(topology="single_branch", target_branch=_OWNED_TARGET)
    meta_path.write_text(json.dumps(meta), encoding="utf-8")
    lanes_path = mission / "lanes.json"
    lanes = json.loads(lanes_path.read_text(encoding="utf-8"))
    lanes["mission_branch"] = _OWNED_TARGET
    lanes["target_branch"] = _OWNED_TARGET
    lanes_path.write_text(json.dumps(lanes), encoding="utf-8")
    (mission / "contracts").mkdir()
    (mission / "contracts/.gitkeep").touch()
    _git(owned, "add", ".")
    _git(owned, "commit", "-qm", "owned acceptance inputs")
    monkeypatch.chdir(sibling)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(sibling))
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    return ReadyOwnedAccept(primary=primary, owned=owned, sibling=sibling, slug=slug)


def _count_ownership_validations(monkeypatch: pytest.MonkeyPatch) -> list[Path | None]:
    """Count real calls to the ownership-claim primitive (delegating, never stubbing)."""
    from specify_cli.core import checkout_ownership
    from specify_cli.workspace.context import clear_workspace_resolution_caches

    clear_workspace_resolution_caches()
    real_claim = checkout_ownership.resolve_ownership_claim
    claimed: list[Path | None] = []

    def _counting(claimed_checkout: Path | None, **kwargs: Any) -> Any:
        claimed.append(claimed_checkout)
        return real_claim(claimed_checkout, **kwargs)

    monkeypatch.setattr(checkout_ownership, "resolve_ownership_claim", _counting)
    return claimed


def _snapshotter(fixture: ReadyOwnedAccept) -> RSnapshotter:
    home = Path(os.environ["SPEC_KITTY_HOME"]) if os.environ.get("SPEC_KITTY_HOME") else None
    return RSnapshotter(fixture.primary, fixture.owned, home)


@pytest.mark.integration
@pytest.mark.git_repo
def test_owned_diagnose_validates_ownership_exactly_once(ready_owned_accept: ReadyOwnedAccept, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = ready_owned_accept
    snapshotter = _snapshotter(fixture)
    before = snapshotter.take()
    claims = _count_ownership_validations(monkeypatch)

    result = _runner.invoke(_accept_app, ["--mission", fixture.slug, "--owned-checkout", str(fixture.owned), "--diagnose", "--json"])

    assert result.exit_code == 0, result.output
    assert len(claims) == 1
    snapshotter.assert_unchanged(before, snapshotter.take())


@pytest.mark.integration
@pytest.mark.git_repo
def test_owned_committing_accept_validates_ownership_exactly_once(ready_owned_accept: ReadyOwnedAccept, monkeypatch: pytest.MonkeyPatch) -> None:
    """The committing path reaches the birth-cutover stamp, which must consume the CLI-edge fact."""
    fixture = ready_owned_accept
    snapshotter = _snapshotter(fixture)
    before = snapshotter.take()
    claims = _count_ownership_validations(monkeypatch)

    result = _runner.invoke(_accept_app, ["--mission", fixture.slug, "--owned-checkout", str(fixture.owned), "--mode", "local", "--json"])

    assert result.exit_code == 0, result.output
    assert len(claims) == 1
    snapshotter.assert_unchanged(before, snapshotter.take(), tolerate_status_mutex_for=fixture.slug)


@pytest.mark.integration
@pytest.mark.git_repo
def test_flagless_accept_from_the_repository_root_validates_nothing(ready_owned_accept: ReadyOwnedAccept, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = ready_owned_accept
    monkeypatch.chdir(fixture.primary)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(fixture.primary))
    claims = _count_ownership_validations(monkeypatch)

    result = _runner.invoke(_accept_app, ["--mission", fixture.slug, "--diagnose", "--json"])

    assert result.exception is None or isinstance(result.exception, SystemExit)
    assert claims == []


@pytest.mark.unit
@pytest.mark.fast
def test_birth_cutover_stamp_takes_the_validated_fact_not_a_bare_root() -> None:
    """FR-003: the stamp consumes the CLI-edge fact; it has no bare-root parameter to re-validate from."""
    parameters = inspect.signature(accept_module._stamp_birth_cutover_for_accept).parameters
    assert "effective_root" not in parameters
    assert parameters["owned"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["owned"].default is None


# ---------------------------------------------------------------------------
# T078: accept consumes the validated OwnedCheckout fact end to end.
# ---------------------------------------------------------------------------

_MID8 = "01M3PACE"
_FACT_SLUG = f"owned-accept-{_MID8}"
_RETIRED_NAMES = frozenset({"resolve_owned_mission", "effective_root_kwargs", "OwnedMission"})


def _mint_fact(tmp_path: Path) -> OwnedCheckout:
    """A fact over a real ``meta.json``-bearing mission dir (precedent: the WP04 seam tests)."""
    repository_root = tmp_path / "R"
    owned_root = tmp_path / "P"
    mission_dir = owned_root / "kitty-specs" / _FACT_SLUG
    mission_dir.mkdir(parents=True)
    repository_root.mkdir()
    (mission_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01M3PACE000000000000000001",
                "mission_slug": _FACT_SLUG,
                "slug": _FACT_SLUG,
                "mission_type": "software-dev",
                "topology": MissionTopology.SINGLE_BRANCH.value,
                "target_branch": "main",
            }
        ),
        encoding="utf-8",
    )
    return OwnedCheckout._mint(
        repository_root=repository_root,
        owned_root=owned_root,
        mission_dir=mission_dir,
        mission_slug=_FACT_SLUG,
        topology=MissionTopology.SINGLE_BRANCH,
        write_branch="main",
    )


def _recording(seen: list[dict[str, Any]], result: object) -> Any:
    """A stand-in callee that records its keyword arguments and returns ``result``."""

    def _call(*_args: object, **kwargs: Any) -> object:
        seen.append(kwargs)
        return result

    return _call


def _boom(name: str) -> Any:
    def _raise(*_args: object, **_kwargs: object) -> None:
        raise AssertionError(f"{name} must not be called on the owned arm")

    return _raise


@pytest.mark.unit
@pytest.mark.fast
class TestOwnedConversion:
    def test_the_option_is_declared_through_the_shared_owned_checkout_option(self) -> None:
        hints = get_type_hints(accept, include_extras=True)
        assert hints["owned_checkout"] == OwnedCheckoutOption

    def test_accept_no_longer_names_the_retired_owned_surface(self) -> None:
        tree = ast.parse(Path(accept_module.__file__).read_text(encoding="utf-8"))
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        names |= {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        names |= {alias.name for node in ast.walk(tree) if isinstance(node, ast.ImportFrom) for alias in node.names}
        assert names.isdisjoint(_RETIRED_NAMES)
        assert {"root", "primary", "directory", "slug", "target"}.isdisjoint(_owned_attribute_reads(tree))

    def test_owned_arms_make_no_fold_walk_or_git_call(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        fact = _mint_fact(tmp_path)
        monkeypatch.setattr("specify_cli.core.paths.get_main_repo_root", _boom("get_main_repo_root"))
        monkeypatch.setattr("specify_cli.missions._read_path_resolver.candidate_feature_dir_for_mission", _boom("candidate_feature_dir_for_mission"))
        monkeypatch.setattr("specify_cli.missions._read_path_resolver.resolve_handle_to_read_path", _boom("resolve_handle_to_read_path"))
        monkeypatch.setattr(subprocess, "run", _boom("subprocess.run"))
        monkeypatch.setattr(accept_module, "git_status_entries", lambda _root: [])
        stamped: dict[str, Any] = {}

        def _stamp(feature_dir: Path, **kwargs: Any) -> SimpleNamespace:
            stamped.update(feature_dir=feature_dir, **kwargs)
            return SimpleNamespace(flipped=True, error=None)

        monkeypatch.setattr("specify_cli.migration.runtime_state_cutover.stamp_accept_cutover", _stamp)

        assert accept_module._coord_worktree_root(fact.owned_root, _FACT_SLUG, owned=fact) is None
        assert accept_module._coord_status_feature_dir(fact.owned_root, _FACT_SLUG, owned=fact) is None
        assert accept_module._coord_dirty_paths(fact.owned_root, _FACT_SLUG, owned=fact) == []
        assert accept_module._commit_residual_acceptance_artifacts(fact.owned_root, _FACT_SLUG, owned=fact) is False
        accept_module._stamp_birth_cutover_for_accept(fact.owned_root, _FACT_SLUG, owned=fact)

        assert stamped == {"feature_dir": fact.mission_dir, "status_feature_dir": None, "owned": fact}


def _owned_attribute_reads(tree: ast.AST) -> set[str]:
    """Attribute names read off a variable called ``owned`` (the fact's retired aliases)."""
    return {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id in {"owned", "run"}
        and node.attr in {"root", "primary", "directory", "slug", "target"}
    }


@pytest.mark.unit
@pytest.mark.fast
class TestOwnedEntryHelper:
    @pytest.fixture
    def entry(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SimpleNamespace:
        state = SimpleNamespace(calls=[], indexed=[], result=None, tmp=tmp_path)

        def _resolve(*args: object, **kwargs: object) -> Any:
            state.calls.append((args, kwargs))
            return state.result

        monkeypatch.setattr(accept_module, "resolve_owned_or_adopt", _resolve)
        monkeypatch.setattr(accept_module, "require_unstaged_index", state.indexed.append)
        return state

    def test_validation_goes_through_the_shared_helper_with_the_lifecycle_topologies(self, entry: SimpleNamespace, monkeypatch: pytest.MonkeyPatch) -> None:
        entry.result = _fake_owned(entry.tmp)
        monkeypatch.chdir(entry.tmp)
        checkout = entry.tmp / "P"

        owned = accept_module._owned_accept_context(entry.tmp / "R", checkout, _SLUG, diagnose=False, normalize_encoding=False)

        assert owned is entry.result
        [(args, kwargs)] = entry.calls
        assert args == (entry.tmp / "R", checkout, _SLUG)
        assert kwargs == {"cwd": Path.cwd(), "allowed_topologies": LIFECYCLE_OWNED_TOPOLOGIES}
        assert entry.indexed == [entry.result]

    def test_a_run_that_stays_on_the_repository_root_checkout_checks_nothing_else(self, entry: SimpleNamespace) -> None:
        owned = accept_module._owned_accept_context(entry.tmp, None, _SLUG, diagnose=False, normalize_encoding=True)
        assert owned is None
        assert entry.indexed == []

    def test_diagnose_does_not_require_an_unstaged_index(self, entry: SimpleNamespace) -> None:
        entry.result = _fake_owned(entry.tmp)
        owned = accept_module._owned_accept_context(entry.tmp, entry.tmp, _SLUG, diagnose=True, normalize_encoding=False)
        assert owned is entry.result
        assert entry.indexed == []

    def test_diagnose_cannot_repair_encoding_in_an_owned_checkout(self, entry: SimpleNamespace) -> None:
        entry.result = _fake_owned(entry.tmp)
        with pytest.raises(ActionContextError) as refusal:
            accept_module._owned_accept_context(entry.tmp, entry.tmp, _SLUG, diagnose=True, normalize_encoding=True)
        assert refusal.value.code == _OPTION_UNSUPPORTED_CODE


@pytest.mark.unit
@pytest.mark.fast
class TestBridgesToUnconvertedCallees:
    """Calls out of the accept flow hand the ``OwnedCheckout`` fact itself as ``owned=``.

    WP15 converted ``collect_feature_summary`` / ``normalize_feature_encoding`` and WP17
    converted ``record_pr_merge_baseline_for_mission`` / ``verify_pr_merge_evidence``:
    none of them takes a bare-root bridge keyword any more.
    """

    @pytest.mark.parametrize("owned", [False, True], ids=["non-owned", "owned"])
    def test_summary_collection_bridge(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, owned: bool) -> None:
        fact = _mint_fact(tmp_path) if owned else None
        seen: list[dict[str, Any]] = []
        sentinel = object()
        monkeypatch.setattr(accept_module, "collect_feature_summary", _recording(seen, sentinel))

        summary: object = accept_module._collect_summary_with_optional_repair(
            tmp_path, _FACT_SLUG, strict_metadata=True, mutate_matrix=False, normalize_encoding=False, owned=fact
        )

        assert summary is sentinel
        assert seen[0]["owned"] is fact
        assert "effective_root" not in seen[0]

    def test_encoding_repair_bridge_reaches_the_normalizer_and_the_recollect(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        fact = _mint_fact(tmp_path)
        collected: list[dict[str, Any]] = []
        repaired: list[dict[str, Any]] = []
        sentinel = object()
        failure = ArtifactEncodingError(tmp_path / "spec.md", UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"))

        def _collect(*_args: object, **kwargs: Any) -> object:
            collected.append(kwargs)
            if len(collected) == 1:
                raise failure
            return sentinel

        monkeypatch.setattr(accept_module, "collect_feature_summary", _collect)
        monkeypatch.setattr(accept_module, "normalize_feature_encoding", _recording(repaired, []))

        summary: object = accept_module._collect_summary_with_optional_repair(
            tmp_path, _FACT_SLUG, strict_metadata=True, mutate_matrix=True, normalize_encoding=True, owned=fact
        )

        assert summary is sentinel
        assert [call["owned"] for call in collected] == [fact, fact]
        assert repaired == [{"owned": fact}]

    @pytest.mark.parametrize("owned", [False, True], ids=["non-owned", "owned"])
    def test_pr_merge_recording_bridge(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, owned: bool) -> None:
        fact = _mint_fact(tmp_path) if owned else None
        seen: list[dict[str, Any]] = []
        sentinel = object()
        monkeypatch.setattr("specify_cli.consolidation.baseline.record_pr_merge_baseline_for_mission", _recording(seen, sentinel))

        recorded: object = accept_module._record_pr_merge_for_accept(tmp_path, _FACT_SLUG, _MERGE_COMMIT, owned=fact, target_ref="main", attest_first_landing=True)

        assert recorded is sentinel
        assert seen == [{"owned": fact, "target_ref": "main", "attest_first_landing": True}]
        assert seen[0]["owned"] is fact

    @pytest.mark.parametrize("owned", [False, True], ids=["non-owned", "owned"])
    def test_merge_commit_verification_bridge(self, harness: Harness, tmp_path: Path, owned: bool) -> None:
        args = ["--mission", _SLUG, "--mode", "pr", "--merge-commit", _MERGE_COMMIT]
        if owned:
            harness.owned = _fake_owned(tmp_path)
            args += ["--owned-checkout", str(tmp_path)]

        result = harness.invoke(*args)

        assert result.exit_code == 0, result.output
        assert harness.verify_kwargs["owned"] is harness.owned
        assert "effective_root" not in harness.verify_kwargs
