"""Audit-tail reader hardening (mission cli-error-surface-seam-01M2WJD2,
WP07/#4746).

Hardens the 7 readers named in research.md's census, plus the
``runtime_bridge.py`` masking ``except Exception`` (T026), so corrupt/
non-UTF-8 input on a *present* file routes through
:func:`kernel.guarded_read.read_guarded` into a typed
:class:`kernel.errors.GuardedReadError` subclass instead of an untyped
traceback or an indistinguishable generic string — while an *absent* file
keeps its documented ``None``/``False`` return exactly as before (D5,
research.md).

Two testing strategies are used, per reader, matched to how each is
actually reached:

- **Command-level** (``decisions/service.py`` via ``agent decision open``,
  ``status/validate.py`` via ``agent status validate``,
  ``core/wps_manifest.py`` via ``agent mission finalize-tasks``): driven
  through the real top-level Typer ``app`` + ``specify_cli.
  _run_app_with_error_hook`` — the SAME seam
  ``tests/specify_cli/cli/commands/test_mission_close_guard.py`` and
  ``tests/specify_cli/cli/commands/test_workflow_guard.py`` use — because
  ``typer.testing.CliRunner`` never passes through that hook (it calls the
  Click app object directly; the hook wraps ``app()`` one layer up, in
  ``specify_cli.main()``).
- **Reader-level, documented** (``merge/state.py``, ``review/lock.py``,
  ``review/artifacts.py``, ``review/baseline.py``): each of these readers'
  real reachable command (``spec-kitty merge``, ``spec-kitty review``)
  requires a genuine git repo + worktree + lane/coordination scaffold
  disproportionate to a read-guard regression test. Per this WP's own
  "Notes" allowance ("a focused reader-level test is acceptable if you
  document why the command path is impractical"), these are tested through
  their PUBLIC caller-facing API (``load_state``/``ReviewLock.load``/
  ``ReviewCycleArtifact.from_file``/``BaselineTestResult.load``) — never
  the private module internals — with the reason recorded on each test.

``runtime_bridge.py``'s ``_check_requirement_mapping_ready`` is, by its own
docstring, "a gather-only internal preflight, not a CLI command boundary"
(consumed by the ``next`` control loop, never exposed as a Typer command
itself) — so its companion-assertion coverage is reader-level by design,
not a documented exception.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli import _run_app_with_error_hook, app

pytestmark = [pytest.mark.regression, pytest.mark.unit]


def _invoke(monkeypatch: pytest.MonkeyPatch, argv: list[str], *, json_mode: bool = False) -> int:
    """Run *argv* through the real top-level app + the real global hook.

    Mirrors ``test_mission_close_guard.py``'s ``_invoke`` helper (the
    canonical pattern for this mission's WPs).
    """
    monkeypatch.setattr(sys, "argv", ["spec-kitty", *argv])
    with pytest.raises(SystemExit) as exc_info:
        _run_app_with_error_hook(app, json_mode=json_mode)
    return int(exc_info.value.code or 0)


# ---------------------------------------------------------------------------
# 1. decisions/service.py::_opened_event_exists — via `agent decision open`
# ---------------------------------------------------------------------------


_DECISION_MISSION_ID = "01KDECISIONREADERTEST00001"
_DECISION_MISSION_SLUG = "decision-reader-test"


def _seed_decision_mission(repo_root: Path) -> Path:
    mission_dir = repo_root / "kitty-specs" / _DECISION_MISSION_SLUG
    mission_dir.mkdir(parents=True, exist_ok=True)
    meta = {"mission_id": _DECISION_MISSION_ID, "mission_slug": _DECISION_MISSION_SLUG}
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return mission_dir


def _open_decision_argv(*, actor: str = "alice") -> list[str]:
    return [
        "agent",
        "decision",
        "open",
        "--mission",
        _DECISION_MISSION_SLUG,
        "--flow",
        "charter",
        "--input-key",
        "team_size",
        "--question",
        "How large?",
        "--step-id",
        "step-1",
        "--actor",
        actor,
    ]


@pytest.mark.regression
def test_decision_open_corrupt_events_log_presents_typed_error_not_traceback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """WP07/#4746: a non-UTF-8 ``status.events.jsonl`` reached on the
    idempotent-reopen path (``_repair_missing_opened_event`` ->
    ``_opened_event_exists``) must present a clean, typed error — not an
    unguarded ``UnicodeDecodeError`` traceback (pre-fix guard gap: the
    reader only caught ``OSError``/``JSONDecodeError``, never
    ``UnicodeDecodeError``)."""
    monkeypatch.chdir(tmp_path)
    mission_dir = _seed_decision_mission(tmp_path)

    # First open persists the entry + emits the opened event.
    exit_code = _invoke(monkeypatch, _open_decision_argv())
    assert exit_code == 0
    capsys.readouterr()  # discard the first (successful) open's output

    events_path = mission_dir / "status.events.jsonl"
    assert events_path.exists()
    events_path.write_bytes(b"\xff\xfe\x00not utf-8 at all\n")

    exit_code = _invoke(monkeypatch, _open_decision_argv())

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out


@pytest.mark.regression
def test_decision_open_corrupt_events_log_json_envelope_names_the_typed_kind(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """--json mode: exactly one JSON object naming the typed error kind."""
    monkeypatch.chdir(tmp_path)
    mission_dir = _seed_decision_mission(tmp_path)

    exit_code = _invoke(monkeypatch, _open_decision_argv())
    assert exit_code == 0
    capsys.readouterr()  # discard the first (successful) open's output

    events_path = mission_dir / "status.events.jsonl"
    events_path.write_text("not-json-at-all{{{\n", encoding="utf-8")

    exit_code = _invoke(monkeypatch, [*_open_decision_argv(), "--json"], json_mode=True)

    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.err == ""
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["kind"] == "DecisionEventLogReadError"


def test_opened_event_exists_returns_false_when_events_log_absent() -> None:
    """D5: an absent ``status.events.jsonl`` still returns ``False`` — never
    routed through the guard (reader-level: the fastest, most direct way to
    pin this specific contract line, already exercised indirectly above by
    the first ``_invoke`` call in each corrupt-log test)."""
    from specify_cli.decisions.service import _opened_event_exists

    repo_root = Path("/nonexistent-repo-root-for-absent-check")
    assert _opened_event_exists(repo_root, "some-mission", "some-decision-id") is False


# ---------------------------------------------------------------------------
# 2. status/validate.py::validate_materialization_drift — via `agent status validate`
# ---------------------------------------------------------------------------


_STATUS_MISSION_SLUG = "042-status-reader-test"


def _seed_status_feature(tmp_path: Path) -> Path:
    (tmp_path / ".kittify").mkdir()
    feature_dir = tmp_path / "kitty-specs" / _STATUS_MISSION_SLUG
    feature_dir.mkdir(parents=True)
    event = {
        "event_id": "01HXYZ0123456789ABCDEFGHJK",
        "mission_slug": _STATUS_MISSION_SLUG,
        "wp_id": "WP01",
        "from_lane": "planned",
        "to_lane": "claimed",
        "at": "2026-02-08T12:00:00Z",
        "actor": "claude",
        "force": False,
        "execution_mode": "worktree",
    }
    (feature_dir / "status.events.jsonl").write_text(json.dumps(event, sort_keys=True) + "\n", encoding="utf-8")
    from specify_cli.status.reducer import materialize as do_materialize

    do_materialize(feature_dir)
    return feature_dir


@pytest.mark.regression
def test_status_validate_corrupt_snapshot_presents_typed_error_not_traceback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """WP07/#4746: ``status/validate.py``'s ``status_path.read_text()`` +
    ``json.loads()`` pair was fully unguarded — non-UTF-8 bytes in
    ``status.json`` (with a valid, non-empty ``status.events.jsonl``
    alongside it, so ``_validate_materialization_files`` lets both through)
    must present a clean, typed error via ``agent status validate``, not a
    raw ``UnicodeDecodeError`` traceback."""
    monkeypatch.chdir(tmp_path)
    feature_dir = _seed_status_feature(tmp_path)
    (feature_dir / "status.json").write_bytes(b"\xff\xfe\x00corrupt")

    with (
        patch(
            "specify_cli.cli.commands.agent.status.locate_project_root",
            return_value=tmp_path,
        ),
        patch(
            "specify_cli.cli.commands.agent.status.get_main_repo_root",
            return_value=tmp_path,
        ),
    ):
        exit_code = _invoke(monkeypatch, ["agent", "status", "validate", "--mission", _STATUS_MISSION_SLUG])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "Traceback" not in captured.err
    assert "Traceback" not in captured.out


@pytest.mark.regression
def test_status_validate_corrupt_snapshot_json_envelope_names_the_typed_kind(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    feature_dir = _seed_status_feature(tmp_path)
    (feature_dir / "status.json").write_text("not valid json{{{", encoding="utf-8")

    with (
        patch(
            "specify_cli.cli.commands.agent.status.locate_project_root",
            return_value=tmp_path,
        ),
        patch(
            "specify_cli.cli.commands.agent.status.get_main_repo_root",
            return_value=tmp_path,
        ),
    ):
        exit_code = _invoke(
            monkeypatch,
            ["agent", "status", "validate", "--mission", _STATUS_MISSION_SLUG, "--json"],
            json_mode=True,
        )

    assert exit_code == 1
    captured = capsys.readouterr()
    assert captured.err == ""
    lines = [line for line in captured.out.splitlines() if line.strip()]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["kind"] == "StatusValidationReadError"


def test_validate_materialization_drift_absent_files_returns_findings_not_error() -> None:
    """D5: absent status.json/status.events.jsonl stay outside the guard —
    ``_validate_materialization_files`` handles them with plain findings,
    never routed through ``read_guarded`` (reader-level: the direct,
    unambiguous way to pin this contract)."""
    from specify_cli.status.validate import validate_materialization_drift

    findings = validate_materialization_drift(Path("/nonexistent-feature-dir-for-absent-check"))
    assert findings == []


# ---------------------------------------------------------------------------
# 3. core/wps_manifest.py::load_wps_manifest — via `agent mission finalize-tasks`
# ---------------------------------------------------------------------------


def _seed_wps_manifest_feature(tmp_path: Path, wps_yaml_content: str) -> Path:
    feature_dir = tmp_path / "kitty-specs" / "069-wps-reader-test"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text('{"target_branch": "main"}\n', encoding="utf-8")
    (feature_dir / "spec.md").write_text(
        "# Spec\n"
        "## Functional Requirements\n"
        "| ID | Requirement | Acceptance Criteria | Status |\n"
        "| --- | --- | --- | --- |\n"
        "| FR-001 | Test requirement | Covered by WP01. | proposed |\n",
        encoding="utf-8",
    )
    (feature_dir / "wps.yaml").write_text(wps_yaml_content, encoding="utf-8")
    (tasks_dir / "WP01-test.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Test\n"
        "dependencies: []\n"
        "requirement_refs: [FR-001]\n"
        "subtasks: []\n"
        "owned_files:\n"
        "  - src/module_a/**\n"
        "authoritative_surface: src/module_a/\n"
        "execution_mode: code_change\n"
        "---\n"
        "# WP01\n",
        encoding="utf-8",
    )
    return feature_dir


@pytest.mark.regression
def test_finalize_tasks_malformed_wps_yaml_presents_clean_typed_message(
    tmp_path: Path,
) -> None:
    """WP07/#4746: ``finalize-tasks`` already wraps ``load_wps_manifest`` in
    its own broad ``except Exception`` (``_load_manifest`` in
    ``mission_finalize.py``) — so a corrupt ``wps.yaml`` did NOT surface a
    raw traceback even before this WP (the ``finalize-tasks`` red state for
    THIS specific reader is "an ugly generic message", not "a crash"; see
    this file's module docstring / the WP's own "record which is which"
    allowance). This test pins the POST-fix improvement: the wrapped
    message now carries the clean, one-line ``WpsManifestReadError`` reason
    instead of a raw multi-line ``ruamel.yaml.YAMLError`` repr, and confirms
    the command still exits 1 cleanly either way (no regression)."""
    from typer.testing import CliRunner

    from specify_cli.cli.commands.agent.mission import app as mission_app

    feature_dir = _seed_wps_manifest_feature(tmp_path, "work_packages: [unterminated\n")

    with (
        patch(
            "specify_cli.cli.commands.agent.mission.locate_project_root",
            return_value=tmp_path,
        ),
        patch(
            "specify_cli.cli.commands.agent.mission._find_feature_directory",
            return_value=feature_dir,
        ),
    ):
        result = CliRunner().invoke(mission_app, ["finalize-tasks", "--mission", "069-wps-reader-test", "--json"])

    assert result.exit_code == 1
    assert "Traceback" not in result.output
    assert "wps.yaml is present but could not be loaded" in result.output


def test_load_wps_manifest_returns_none_when_wps_yaml_absent(tmp_path: Path) -> None:
    """D5: a legacy mission with no ``wps.yaml`` stays ``None`` (prose-based
    ``tasks.md`` fallback) — never routed through the guard."""
    from specify_cli.core.wps_manifest import load_wps_manifest

    feature_dir = tmp_path / "kitty-specs" / "legacy-mission"
    feature_dir.mkdir(parents=True)
    assert load_wps_manifest(feature_dir) is None


@pytest.mark.regression
def test_load_wps_manifest_non_utf8_bytes_raises_typed_error(tmp_path: Path) -> None:
    """WP07/#4746: non-UTF-8 bytes in ``wps.yaml`` (fully unguarded pre-fix)
    now raise the typed ``WpsManifestReadError``."""
    from specify_cli.core.wps_manifest import WpsManifestReadError, load_wps_manifest

    feature_dir = tmp_path / "kitty-specs" / "corrupt-wps-mission"
    feature_dir.mkdir(parents=True)
    (feature_dir / "wps.yaml").write_bytes(b"\xff\xfe\x00work_packages:")

    with pytest.raises(WpsManifestReadError):
        load_wps_manifest(feature_dir)


def test_load_wps_manifest_schema_invalid_still_raises_plain_validation_error(
    tmp_path: Path,
) -> None:
    """Deliberate NON-regression pin: a syntactically-valid-YAML but
    schema-invalid manifest keeps raising bare ``pydantic.ValidationError``
    (unchanged from pre-WP07), NOT ``WpsManifestReadError`` — see
    ``WpsManifestReadError``'s docstring for why (pydantic-core's
    ``ValidationError`` cannot be practically re-parented onto
    ``GuardedReadError``'s ``path``/``reason`` constructor contract).
    Already pinned by ``tests/core/test_wps_manifest.py``; duplicated here
    as a fast, colocated guard against silently changing this on a future
    ``read_guarded`` refactor."""
    from pydantic import ValidationError

    from specify_cli.core.wps_manifest import load_wps_manifest

    feature_dir = tmp_path / "kitty-specs" / "schema-invalid-wps-mission"
    feature_dir.mkdir(parents=True)
    (feature_dir / "wps.yaml").write_text(
        "work_packages:\n  - id: WP01\n",
        encoding="utf-8",  # missing required 'title'
    )

    with pytest.raises(ValidationError):
        load_wps_manifest(feature_dir)


# ---------------------------------------------------------------------------
# 4. merge/state.py::_load_state_file — via load_state()/has_active_merge()
#
# Reader-level, documented: the real reachable command (`spec-kitty merge`,
# `spec-kitty doctor coordination`) requires a genuine git repo, branches,
# and lanes.json scaffold disproportionate to this read-guard regression
# test. `load_state`/`has_active_merge` ARE the public API `_load_state_file`
# exists to serve -- never the private reader itself.
# ---------------------------------------------------------------------------


def test_load_state_returns_none_when_state_file_absent(tmp_path: Path) -> None:
    """D5: an absent state.json still returns None for an explicit mission_id."""
    from specify_cli.merge.state import load_state

    assert load_state(tmp_path, "some-mission") is None


@pytest.mark.regression
def test_load_state_explicit_mission_id_raises_typed_error_on_corrupt_json(
    tmp_path: Path,
) -> None:
    """WP07/#4746: pre-fix, `_load_state_file` silently collapsed corrupt
    JSON into `None` -- indistinguishable from "no merge in progress", a
    fail-open bug (a corrupt RESUMABLE merge state masquerading as nothing
    to resume). Now raises the typed `MergeStateReadError` for the
    explicit-mission_id (fail-closed) path."""
    from specify_cli.merge.state import MergeStateReadError, load_state

    state_file = tmp_path / ".kittify" / "runtime" / "merge" / "057-test" / "state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text("not valid json{", encoding="utf-8")

    with pytest.raises(MergeStateReadError):
        load_state(tmp_path, "057-test")


@pytest.mark.regression
def test_load_state_non_utf8_bytes_raises_typed_error(tmp_path: Path) -> None:
    """WP07/#4746: non-UTF-8 bytes were fully unguarded pre-fix (the old
    `except (JSONDecodeError, TypeError, KeyError)` never caught
    `UnicodeDecodeError`) -- now collapsed into the same typed error."""
    from specify_cli.merge.state import MergeStateReadError, load_state

    state_file = tmp_path / ".kittify" / "runtime" / "merge" / "057-test" / "state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_bytes(b"\xff\xfe\x00not utf-8")

    with pytest.raises(MergeStateReadError):
        load_state(tmp_path, "057-test")


@pytest.mark.regression
def test_load_state_scan_all_skips_a_corrupt_mission_and_still_finds_the_valid_one(
    tmp_path: Path,
) -> None:
    """Deliberate design choice (documented in `load_state`'s own
    docstring): the no-`mission_id` SCAN path must not let one mission's
    corrupt state.json block resolving another mission's active merge --
    unlike the explicit-mission_id path above, which fails closed. Skips
    the corrupt one and still returns the valid state."""
    from specify_cli.merge.state import MergeState, load_state, save_state

    corrupt_dir = tmp_path / ".kittify" / "runtime" / "merge" / "corrupt-mission"
    corrupt_dir.mkdir(parents=True)
    (corrupt_dir / "state.json").write_text("not valid json{", encoding="utf-8")

    valid_state = MergeState(
        mission_id="valid-mission",
        mission_slug="valid-mission",
        target_branch="main",
        wp_order=["WP01"],
    )
    save_state(valid_state, tmp_path)

    result = load_state(tmp_path)
    assert result is not None
    assert result.mission_id == "valid-mission"


def test_iter_pending_coord_reconcile_markers_skips_a_corrupt_state_file(
    tmp_path: Path,
) -> None:
    """Same resilience contract as the scan-all test above, for the
    coordination doctor's enumeration seam (its own docstring already
    promised "unparseable state files are skipped")."""
    from specify_cli.merge.state import (
        MergeState,
        iter_pending_coord_reconcile_markers,
        save_state,
    )

    corrupt_dir = tmp_path / ".kittify" / "runtime" / "merge" / "corrupt-mission"
    corrupt_dir.mkdir(parents=True)
    (corrupt_dir / "state.json").write_bytes(b"\xff\xfe\x00not utf-8")

    marked_state = MergeState(
        mission_id="marked-mission",
        mission_slug="marked-mission",
        target_branch="main",
        wp_order=["WP01"],
        pending_coord_reconcile={"coord_ref": "coord"},
    )
    save_state(marked_state, tmp_path)

    results = list(iter_pending_coord_reconcile_markers(tmp_path))
    assert [s.mission_id for s in results] == ["marked-mission"]


# ---------------------------------------------------------------------------
# 5. review/lock.py::ReviewLock.load — via ReviewLock.load()/.acquire()
#
# Reader-level, documented: the real reachable command (`spec-kitty review`
# claim step, workflow.py) requires creating a genuine git worktree before
# `ReviewLock.acquire` is ever called. `load`/`acquire` are the public
# classmethods themselves (there is no narrower private reader beneath
# `load` to defer to) -- calling them directly IS calling the documented
# public contract, just without the surrounding worktree-creation machinery.
# ---------------------------------------------------------------------------


def test_review_lock_load_returns_none_when_absent(tmp_path: Path) -> None:
    from specify_cli.review.lock import ReviewLock

    assert ReviewLock.load(tmp_path) is None


@pytest.mark.regression
def test_review_lock_load_raises_typed_error_on_corrupt_json(tmp_path: Path) -> None:
    """WP07/#4746: pre-fix, this silently returned None -- indistinguishable
    from "no active lock", a stale-lock safety gap (see
    `ReviewLockReadError`'s docstring: `acquire()` would happily grant a
    second concurrent review past a lock file it could not verify)."""
    from specify_cli.review.lock import LOCK_DIR, LOCK_FILE, ReviewLock, ReviewLockReadError

    lock_dir = tmp_path / LOCK_DIR
    lock_dir.mkdir(parents=True)
    (lock_dir / LOCK_FILE).write_text("{not valid json", encoding="utf-8")

    with pytest.raises(ReviewLockReadError):
        ReviewLock.load(tmp_path)


@pytest.mark.regression
def test_review_lock_acquire_fails_closed_on_corrupt_lock_rather_than_silently_overwriting(
    tmp_path: Path,
) -> None:
    """The safety-gap consequence, one layer up: pre-fix, `acquire()` would
    treat a corrupt lock as "no lock" and happily grant a second concurrent
    review. Post-fix, the typed error propagates out of `acquire()` too --
    the caller (`workflow.py`'s `except ReviewLockError` — a DIFFERENT
    type) does not catch it, so it fails closed instead of silently
    proceeding."""
    from specify_cli.review.lock import LOCK_DIR, LOCK_FILE, ReviewLock, ReviewLockReadError

    lock_dir = tmp_path / LOCK_DIR
    lock_dir.mkdir(parents=True)
    (lock_dir / LOCK_FILE).write_bytes(b"\xff\xfe\x00not utf-8")

    with pytest.raises(ReviewLockReadError):
        ReviewLock.acquire(tmp_path, wp_id="WP01", agent="claude")


# ---------------------------------------------------------------------------
# 6. review/artifacts.py::ReviewCycleArtifact.from_file — via .from_file()/.latest()
#
# Reader-level, documented: the real reachable command (submitting a review
# verdict via `spec-kitty review`) requires a full review-cycle mission
# scaffold. `from_file`/`latest` are the public classmethods themselves.
# ---------------------------------------------------------------------------


def test_review_cycle_artifact_latest_returns_none_when_no_candidates(tmp_path: Path) -> None:
    from specify_cli.review.artifacts import ReviewCycleArtifact

    assert ReviewCycleArtifact.latest(tmp_path) is None


@pytest.mark.regression
def test_review_cycle_artifact_from_file_non_utf8_raises_typed_error(tmp_path: Path) -> None:
    """WP07/#4746: `from_file`'s `path.read_text` used to catch only
    `OSError`, re-raising a bare `ValueError` -- non-UTF-8 bytes propagated
    as a raw `UnicodeDecodeError`. Now collapsed into the typed
    `ReviewArtifactReadError` (still a `ValueError`, D3)."""
    from specify_cli.review.artifacts import ReviewArtifactReadError, ReviewCycleArtifact

    path = tmp_path / "review-cycle-1.md"
    path.write_bytes(b"\xff\xfe\x00not utf-8")

    with pytest.raises(ReviewArtifactReadError):
        ReviewCycleArtifact.from_file(path)


def test_review_cycle_artifact_from_file_malformed_frontmatter_still_raises_value_error(
    tmp_path: Path,
) -> None:
    """D3 back-compat: the existing `except ValueError` call sites
    (`review/cycle.py`) keep matching -- `ReviewArtifactReadError`
    subclasses `ValueError` too."""
    from specify_cli.review.artifacts import ReviewCycleArtifact

    path = tmp_path / "review-cycle-1.md"
    path.write_text("no frontmatter delimiter here at all\n", encoding="utf-8")

    with pytest.raises(ValueError, match="no YAML frontmatter"):
        ReviewCycleArtifact.from_file(path)


# ---------------------------------------------------------------------------
# 7. review/baseline.py::BaselineTestResult.load — via BaselineTestResult.load()
#
# Reader-level, documented: the real reachable command (`agent tasks
# move-task` / `workflow_executor.py`'s review-baseline-context read)
# requires a deep mission+worktree+review-cycle scaffold. `load` is the
# public classmethod itself.
# ---------------------------------------------------------------------------


def test_baseline_load_returns_none_when_absent(tmp_path: Path) -> None:
    from specify_cli.review.baseline import BaselineTestResult

    assert BaselineTestResult.load(tmp_path / "nonexistent.json") is None


@pytest.mark.regression
def test_baseline_load_non_utf8_bytes_raises_typed_error(tmp_path: Path) -> None:
    """WP07/#4746: non-UTF-8 bytes were fully unguarded pre-fix (only
    `json.JSONDecodeError` was caught, re-raised as `ValueError`)."""
    from specify_cli.review.baseline import BaselineTestResult, ReviewBaselineReadError

    artifact = tmp_path / "baseline-tests.json"
    artifact.write_bytes(b"\xff\xfe\x00not utf-8")

    with pytest.raises(ReviewBaselineReadError):
        BaselineTestResult.load(artifact)


def test_baseline_load_malformed_json_still_raises_value_error_with_original_message_shape(
    tmp_path: Path,
) -> None:
    """D3 back-compat: `tests/review/test_baseline.py::
    test_load_raises_on_malformed_json` pins `pytest.raises(ValueError,
    match="Malformed baseline JSON")` -- `ReviewBaselineReadError`
    subclasses `ValueError` AND composes the identical message prefix."""
    from specify_cli.review.baseline import BaselineTestResult

    artifact = tmp_path / "baseline-tests.json"
    artifact.write_text("NOT JSON {{{}}", encoding="utf-8")

    with pytest.raises(ValueError, match="Malformed baseline JSON"):
        BaselineTestResult.load(artifact)


# ---------------------------------------------------------------------------
# T026 — runtime_bridge.py: the masking `except Exception` around
# `load_wps_manifest`, plus the companion assertion that the other three
# operations sharing the try block are unaffected.
# ---------------------------------------------------------------------------


def _seed_requirement_mapping_feature(tmp_path: Path) -> Path:
    feature_dir = tmp_path / "kitty-specs" / "042-runtime-bridge-reader-test"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text(
        "# Spec\n\n"
        "## Functional Requirements\n\n"
        "| ID | Requirement | Acceptance Criteria | Status |\n"
        "| --- | --- | --- | --- |\n"
        "| FR-001 | First | Covered by WP01. | proposed |\n",
        encoding="utf-8",
    )
    (tasks_dir / "WP01.md").write_text(
        "---\nwork_package_id: WP01\ntitle: WP01\nrequirement_refs: [FR-001]\n---\n",
        encoding="utf-8",
    )
    return feature_dir


@pytest.mark.regression
def test_runtime_bridge_corrupt_wps_manifest_gets_a_specific_typed_finding(
    tmp_path: Path,
) -> None:
    """WP07/#4746 (T026): pre-fix, a corrupt `wps.yaml` collapsed into the
    SAME generic "Requirement mapping preflight failed: {exc}" string as
    every other failure in the shared try block. Post-fix, it is caught
    narrowly via `_load_wps_manifest_findings` (`WpsManifestReadError`) and
    gets its own distinguishable finding, naming the manifest specifically."""
    from runtime.next.runtime_bridge import _check_requirement_mapping_ready

    feature_dir = _seed_requirement_mapping_feature(tmp_path)
    (feature_dir / "wps.yaml").write_bytes(b"\xff\xfe\x00work_packages:")

    findings = _check_requirement_mapping_ready(feature_dir)

    assert len(findings) == 1
    assert "wps.yaml is corrupt" in findings[0]
    assert "Requirement mapping preflight failed" in findings[0]


@pytest.mark.regression
def test_runtime_bridge_companion_assertion_other_three_operations_unaffected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Companion assertion (T026, binding amendment): narrowing the
    `load_wps_manifest` catch must NOT change the behavior of the other
    THREE operations sharing the try block --
    `parse_requirement_ids_from_spec_md` (representative of
    `spec_md.read_text`'s downstream consumer too, since both run before
    `load_wps_manifest`), `read_all_wp_requirement_refs`, and the
    `tasks_md.read_text` prose fallback. Simulates a genuine crash in
    `parse_requirement_ids_from_spec_md` (mirrors the pre-existing
    `tests/next/test_runtime_bridge_unit.py::
    test_requirement_mapping_preflight_wraps_unexpected_errors` pin) and
    confirms it STILL falls into the SAME broad `except Exception` ->
    generic-message contract, completely unchanged by this WP."""
    from runtime.next.runtime_bridge import _check_requirement_mapping_ready
    from specify_cli import requirement_mapping as rm

    feature_dir = _seed_requirement_mapping_feature(tmp_path)

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("simulated preflight crash")

    monkeypatch.setattr(rm, "parse_requirement_ids_from_spec_md", _boom)

    findings = _check_requirement_mapping_ready(feature_dir)

    assert len(findings) == 1
    assert "Requirement mapping preflight failed" in findings[0]
    assert "simulated preflight crash" in findings[0]
    assert "wps.yaml is corrupt" not in findings[0]


def test_load_wps_manifest_findings_returns_none_manifest_when_absent(tmp_path: Path) -> None:
    """D5, at the runtime_bridge seam: an absent wps.yaml still resolves to
    `(None, None)` -- the legacy tasks.md-prose-fallback branch, never a
    finding."""
    from runtime.next.runtime_bridge import _load_wps_manifest_findings

    feature_dir = tmp_path / "kitty-specs" / "legacy-mission-no-wps-yaml"
    feature_dir.mkdir(parents=True)

    manifest, findings = _load_wps_manifest_findings(feature_dir)
    assert manifest is None
    assert findings is None
