"""FR-005: ``spec-kitty accept --normalize-encoding`` repair path.

WP02 preserves the standalone tasks CLI's one genuinely-unique capability —
opt-in acceptance-artifact encoding normalization — on the *supported*
``spec-kitty accept`` command before the standalone surface is deleted. The
flag, on an ``ArtifactEncodingError``, delegates to the **canonical**
``specify_cli.acceptance.normalize_feature_encoding`` (C-003 — reuse canonical,
copy no standalone logic), reports the repaired paths, re-collects, and
proceeds.

Test taxonomy (read before editing):

* ``test_normalize_encoding_repairs_artifact_with_flag`` (T006) is the
  **red-first wiring test**: it fails before the ``--normalize-encoding`` option
  exists and passes once the option + repair wiring land. It is non-vacuous —
  reverting the T005 wiring reds it (the encoding error propagates instead of
  being repaired).
* ``test_default_off_leaves_bytes_untouched`` (T007) and
  ``test_without_flag_clean_exit_referencing_flag`` (T008) are **regression
  pins** for the *pre-existing* default path (no rewrite, raise → exit 1). They
  pass with or without the FR-005 wiring; each reds only if its own default
  behavior is later changed.

The repair path is exercised through ``--diagnose`` (read-only): it forces the
``collect_feature_summary`` read — where the strict UTF-8 decode raises — then
exits 0 after reporting diagnostics, isolating the wiring under test from the
unrelated commit / dirty-tree machinery.
"""

from __future__ import annotations

import json
import subprocess
from kernel.clock import now_utc_iso
from io import StringIO
from pathlib import Path

import pytest
import typer
from rich.console import Console

import specify_cli.cli.commands.accept as accept_cmd
from specify_cli.acceptance import AcceptanceError
from specify_cli.acceptance.matrix import (
    AcceptanceCriterion,
    AcceptanceMatrix,
    write_acceptance_matrix,
)
from specify_cli.cli.commands.accept import accept
from specify_cli.config.path_conventions import PathConventionsConfigError
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.status.emit import build_claim_policy_metadata
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.reducer import materialize
from specify_cli.status.store import append_event

# Marked for mutmut sandbox skip — subprocess CLI/git invocation.
pytestmark = [pytest.mark.non_sandbox, pytest.mark.git_repo]

_SLUG = "099-normalize-encoding"
_MISSION_ID = "01JZZZZZZZZZZZZZZZZZZZZZZZ"
_MISSION_BRANCH = f"kitty/mission-{_SLUG}"

# Windows-1252 right single quotation mark — invalid as standalone UTF-8, the
# canonical mojibake byte ``normalize_feature_encoding`` recovers. Appending it
# to ``plan.md`` makes the strict acceptance read raise ``ArtifactEncodingError``.
_CP1252_SMART_QUOTE = b"\x92"

# A realistic-length cp1252 payload (accented Latin-1 characters + smart
# punctuation, padded with plain-ASCII body lines) the canonical detector
# (``charter.encoding_recovery.recover``, #4968 WP01/WP03) can confidently
# settle on cp1252 for -- a bare single appended byte among otherwise-tiny
# ASCII text is genuinely ambiguous (too little context to disambiguate a
# codepage) and is correctly refused rather than repaired.
_CP1252_PLAN_TEXT = "# plan.md\n" + "Done.\n" * 8 + "Owner: José Peña, São Paulo. “freeze” — don’t ship.\n"


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _create_accept_ready_feature(repo_root: Path) -> Path:
    """Build a clean, accept-ready lane-based mission on its mission branch.

    Mirrors the proven setup in ``test_accept_clean_tree`` so the real top-level
    ``accept`` command resolves the mission and reaches ``collect_feature_summary``.
    Returns the feature directory.
    """
    _git(repo_root, "init", ".")
    _git(repo_root, "config", "user.email", "test@test.com")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "branch", "-M", "main")

    (repo_root / ".kittify").mkdir()
    for required_dir in ("src", "tests", "docs"):
        path = repo_root / required_dir
        path.mkdir()
        (path / ".gitkeep").write_text("")

    feature_dir = repo_root / "kitty-specs" / _SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "contracts").mkdir(parents=True, exist_ok=True)

    meta = {
        "mission_number": "099",
        "slug": _SLUG,
        "mission_slug": _SLUG,
        "mission_id": _MISSION_ID,
        "mid8": _MISSION_ID[:8],
        "friendly_name": "Normalize Encoding",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-01-01T00:00:00Z",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")

    for fname in ("spec.md", "plan.md", "tasks.md"):
        (feature_dir / fname).write_text(f"# {fname}\nDone.\n")

    (tasks_dir / "WP01-test.md").write_text(
        "---\n"
        'work_package_id: "WP01"\n'
        'title: "Test WP"\n'
        'lane: "done"\n'
        'assignee: "test-agent"\n'
        'agent: "test-agent"\n'
        'shell_pid: "12345"\n'
        "---\n"
        "# WP01\nDone.\n"
    )

    append_event(
        feature_dir,
        StatusEvent(
            event_id="01TESTNORMALIZEENCODING0001",
            mission_slug=_SLUG,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.DONE,
            at=now_utc_iso(),
            actor="test-agent",
            force=True,
            execution_mode="direct_repo",
            reason="Test setup: skip to done",
        ),
    )
    materialize(feature_dir)

    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug=_SLUG,
            mission_id=_SLUG,
            mission_branch=_MISSION_BRANCH,
            target_branch="main",
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=("WP01",),
                    write_scope=("src/**",),
                    predicted_surfaces=("test",),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at="2026-04-05T12:00:00Z",
            computed_from="test",
        ),
    )

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "init")
    _git(repo_root, "checkout", "-b", _MISSION_BRANCH)
    return feature_dir


def _corrupt_plan_encoding(feature_dir: Path) -> Path:
    """Rewrite ``plan.md`` as cp1252-encoded text so the strict read raises.

    Uses :data:`_CP1252_PLAN_TEXT` (realistic-length, confidently
    cp1252-detectable) rather than a single appended byte -- see its
    docstring for why (#4968).
    """
    plan_path = feature_dir / "plan.md"
    plan_path.write_bytes(_CP1252_PLAN_TEXT.encode("cp1252"))
    return plan_path


def _capture_console(monkeypatch: pytest.MonkeyPatch) -> StringIO:
    """Redirect the command's module-level console into a buffer."""
    buf = StringIO()
    monkeypatch.setattr(
        accept_cmd,
        "console",
        Console(file=buf, highlight=False, markup=True, width=200),
    )
    return buf


def test_malformed_path_conventions_renders_as_acceptance_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A malformed ``project.path_conventions`` section surfaces as a clean accept
    blocking verdict (``AcceptanceError`` → the command's exit-1 handler), never a raw
    traceback (adversarial squad NOTE, #3790).

    Non-vacuous: dropping the ``except PathConventionsConfigError`` conversion in
    ``_collect_summary_with_optional_repair`` lets the raw ``PathConventionsConfigError``
    (a ``ValueError``, not an ``AcceptanceError``) propagate, failing this ``pytest.raises``.
    """

    def _raise_malformed(*_args: object, **_kwargs: object) -> object:
        raise PathConventionsConfigError(
            "project.path_conventions.workspace must not be empty or blank."
        )

    monkeypatch.setattr(accept_cmd, "collect_feature_summary", _raise_malformed)
    with pytest.raises(AcceptanceError, match="path_conventions"):
        accept_cmd._collect_summary_with_optional_repair(
            Path("/nonexistent-repo"),
            _SLUG,
            strict_metadata=False,
            mutate_matrix=False,
            normalize_encoding=False,
        )


def _run_accept(*, normalize_encoding: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    """Invoke the real ``accept`` in read-only diagnose mode.

    ``--diagnose`` forces ``collect_feature_summary`` (where the strict decode
    raises) then exits 0, so the repair wiring is exercised without dragging in
    the commit / dirty-tree machinery.
    """
    accept(
        mission=_SLUG,
        mode="auto",
        actor="tester",
        test=[],
        json_output=False,
        lenient=False,
        no_commit=False,
        diagnose=True,
        allow_fail=False,
        normalize_encoding=normalize_encoding,
    )


def test_normalize_encoding_repairs_artifact_with_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T006 (red-first wiring): the flag repairs the artifact and proceeds.

    Non-vacuous: reverting the T005 wiring (the repair branch) makes the
    ``ArtifactEncodingError`` propagate to the ``except AcceptanceError`` path
    (exit 1) instead of exiting 0 with a repaired, valid-UTF-8 ``plan.md``.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    feature_dir = _create_accept_ready_feature(repo_root)
    plan_path = _corrupt_plan_encoding(feature_dir)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)
    buf = _capture_console(monkeypatch)

    with pytest.raises(typer.Exit) as exc_info:
        _run_accept(normalize_encoding=True, monkeypatch=monkeypatch)

    # Diagnose mode exits 0 once the repaired summary is collected — proving no
    # ArtifactEncodingError surfaced (it was repaired, not raised through).
    assert exc_info.value.exit_code == 0, "repair path should let acceptance proceed"

    # The artifact was rewritten to valid, byte-exact UTF-8.
    plan_path.read_text(encoding="utf-8")  # must not raise
    assert plan_path.read_bytes() == _CP1252_PLAN_TEXT.encode("utf-8")

    # The repaired path was reported to the operator.
    output = buf.getvalue()
    assert "plan.md" in output
    assert "Normalized" in output


def test_default_off_leaves_bytes_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T007 (regression pin): without the flag the artifact bytes are untouched.

    Pins the pre-existing default: ``accept`` performs no encoding rewrite. Reds
    only if a future change starts rewriting artifacts by default.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    feature_dir = _create_accept_ready_feature(repo_root)
    plan_path = _corrupt_plan_encoding(feature_dir)
    before = plan_path.read_bytes()
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)
    _capture_console(monkeypatch)

    with pytest.raises(typer.Exit):
        _run_accept(normalize_encoding=False, monkeypatch=monkeypatch)

    assert plan_path.read_bytes() == before, "default-off accept must not rewrite bytes"
    assert plan_path.read_bytes() == _CP1252_PLAN_TEXT.encode("cp1252")


def test_without_flag_clean_exit_referencing_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T008 (regression pin): without the flag, exit 1 referencing the flag.

    Pins the pre-existing ``ArtifactEncodingError`` surface so a later change
    cannot silently regress the actionable error message.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    feature_dir = _create_accept_ready_feature(repo_root)
    _corrupt_plan_encoding(feature_dir)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)
    buf = _capture_console(monkeypatch)

    with pytest.raises(typer.Exit) as exc_info:
        _run_accept(normalize_encoding=False, monkeypatch=monkeypatch)

    assert exc_info.value.exit_code == 1
    output = buf.getvalue()
    assert "Invalid UTF-8" in output
    assert "--normalize-encoding" in output


# A realistic mostly-ASCII plan with a SINGLE stray cp1252 byte. This is the
# sparse-signal case: too little cp1252 context for the canonical detector to
# confidently pick a code page, so --normalize-encoding correctly REFUSES it
# (fail-closed) rather than risk a wrong-page rewrite (#4962/#4968).
_SPARSE_PLAN_ASCII = "# plan.md\n" + "This is a normal ASCII plan line.\n" * 40


def _corrupt_plan_sparse_signal(feature_dir: Path) -> Path:
    """Write plan.md as long ASCII plus one stray cp1252 byte (ambiguous)."""
    plan_path = feature_dir / "plan.md"
    plan_path.write_bytes(_SPARSE_PLAN_ASCII.encode("ascii") + _CP1252_SMART_QUOTE)
    return plan_path


def test_normalize_encoding_refuses_ambiguous_and_points_to_validate_encoding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A sparse-signal artifact --normalize-encoding cannot disambiguate is
    refused (exit 1), untouched, with a message pointing at ``validate-encoding
    --fix`` -- never re-suggesting the flag that already refused, and never a
    silent wrong-page rewrite (#4962/#4968 fail-closed contract).

    Non-vacuous: without the fold in ``_collect_summary_with_optional_repair``
    the second ``ArtifactEncodingError`` would surface the stale "Run with
    --normalize-encoding" text, failing the ``validate-encoding`` assertion.
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    feature_dir = _create_accept_ready_feature(repo_root)
    plan_path = _corrupt_plan_sparse_signal(feature_dir)
    before = plan_path.read_bytes()
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)
    buf = _capture_console(monkeypatch)

    with pytest.raises(typer.Exit) as exc_info:
        _run_accept(normalize_encoding=True, monkeypatch=monkeypatch)

    assert exc_info.value.exit_code == 1, "ambiguous artifact must be refused, not repaired"
    # Untouched: fail-closed writes nothing (no silent wrong-page rewrite, no backup litter).
    assert plan_path.read_bytes() == before
    output = buf.getvalue()
    assert "validate-encoding --fix" in output, "refusal must point to the byte-offset repair surface"


def _create_accept_ready_feature_for_commit(repo_root: Path) -> Path:
    """Build a REAL-commit-ready lane-based mission (strict metadata + a
    passing acceptance matrix), unlike :func:`_create_accept_ready_feature`
    (whose bare ``planned -> done`` force transition is only exercised through
    ``--diagnose``, which exits 0 regardless of ``AcceptanceSummary.ok`` and so
    never needs the claim-policy sidecar or a resolvable matrix verdict).

    A REAL (non-``--diagnose``) accept additionally requires:

    * a ``planned -> claimed -> done`` event chain carrying the claim-policy
      ``agent``/``shell_pid`` sidecar (strict-metadata's "missing agent in
      canonical runtime state" gate — mirrors
      ``test_accept_clean_tree._create_lane_feature``), and
    * an acceptance matrix with a ``pass`` criterion (otherwise the matrix
      verdict blocks before the commit step is ever reached).

    Returns the feature directory.
    """
    _git(repo_root, "init", ".")
    _git(repo_root, "config", "user.email", "test@test.com")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "branch", "-M", "main")

    (repo_root / ".kittify").mkdir()
    for required_dir in ("src", "tests", "docs"):
        path = repo_root / required_dir
        path.mkdir()
        (path / ".gitkeep").write_text("")

    feature_dir = repo_root / "kitty-specs" / _SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    (feature_dir / "contracts").mkdir(parents=True, exist_ok=True)

    meta = {
        "mission_number": "099",
        "slug": _SLUG,
        "mission_slug": _SLUG,
        "mission_id": _MISSION_ID,
        "mid8": _MISSION_ID[:8],
        "friendly_name": "Normalize Encoding Commit",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-01-01T00:00:00Z",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")

    for fname in ("spec.md", "tasks.md"):
        (feature_dir / fname).write_text(f"# {fname}\nDone.\n")
    # plan.md is committed with the SAME text the encoding repair will later
    # reconstruct (:data:`_CP1252_PLAN_TEXT`, valid UTF-8 here). The test then
    # corrupts the WORKING TREE copy to cp1252 bytes of that identical text
    # (:func:`_corrupt_plan_encoding`) -- a realistic "an editor mis-saved a
    # tracked file's encoding" repro. A successful repair round-trips the
    # working tree back to byte-identical with this commit, so ``plan.md``
    # itself shows NO git diff afterward and the test isolates exactly the
    # ``.bak`` sibling as the only candidate blocking dirt (#4962 fold A).
    (feature_dir / "plan.md").write_text(_CP1252_PLAN_TEXT, encoding="utf-8")

    (tasks_dir / "WP01-test.md").write_text(
        "---\n"
        'work_package_id: "WP01"\n'
        'title: "Test WP"\n'
        'lane: "done"\n'
        'assignee: "test-agent"\n'
        'agent: "test-agent"\n'
        'shell_pid: "12345"\n'
        "subtasks: []\n"
        "---\n"
        "# WP01\nDone.\n"
    )

    append_event(
        feature_dir,
        StatusEvent(
            event_id="01TESTNORMALIZEENCCOMMIT0000",
            mission_slug=_SLUG,
            wp_id="WP01",
            from_lane=Lane.PLANNED,
            to_lane=Lane.CLAIMED,
            at="2026-01-01T00:00:00+00:00",
            actor="test-agent",
            force=False,
            execution_mode="direct_repo",
            policy_metadata=build_claim_policy_metadata(
                shell_pid=12345,
                shell_pid_created_at="2026-01-01T00:00:00+00:00",
                agent="test-agent",
            ),
        ),
    )
    append_event(
        feature_dir,
        StatusEvent(
            event_id="01TESTNORMALIZEENCCOMMIT0001",
            mission_slug=_SLUG,
            wp_id="WP01",
            from_lane=Lane.CLAIMED,
            to_lane=Lane.DONE,
            at=now_utc_iso(),
            actor="test-agent",
            force=True,
            execution_mode="direct_repo",
            reason="Test setup: skip to done",
        ),
    )
    materialize(feature_dir)

    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug=_SLUG,
            mission_id=_SLUG,
            mission_branch=_MISSION_BRANCH,
            target_branch="main",
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=("WP01",),
                    write_scope=("src/**",),
                    predicted_surfaces=("test",),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at="2026-04-05T12:00:00Z",
            computed_from="test",
        ),
    )

    write_acceptance_matrix(
        feature_dir,
        AcceptanceMatrix(
            mission_slug=_SLUG,
            criteria=[
                AcceptanceCriterion(
                    criterion_id="AC1",
                    description="feature behaves as specified",
                    proof_type="automated_test",
                    pass_fail="pass",
                )
            ],
            negative_invariants=[],
        ),
    )

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "init")
    _git(repo_root, "checkout", "-b", _MISSION_BRANCH)
    return feature_dir


def test_normalize_encoding_real_commit_mode_ignores_own_backup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """FOLD A (#4962 review, MAJOR/blocking): a REAL (non-``--diagnose``)
    ``accept`` must not self-block on the untracked ``.bak`` sibling its OWN
    ``--normalize-encoding`` repair just wrote.

    Isolating the ``.bak`` as the ONLY candidate dirt: ``plan.md`` is
    committed with the exact text the repair will reconstruct
    (:data:`_CP1252_PLAN_TEXT`, valid UTF-8), then the WORKING TREE copy is
    corrupted to cp1252 bytes of that SAME text (:func:`_corrupt_plan_encoding`
    -- a realistic "an editor mis-saved a tracked file's encoding" repro). A
    successful repair round-trips ``plan.md`` back to byte-identical with the
    commit, so ``plan.md`` itself carries no git diff afterward; only its
    ``.bak`` sibling is new, untracked dirt.

    Sequence the bug lived in: the repair rewrites ``plan.md`` to UTF-8 and
    leaves the ORIGINAL bytes at ``plan.md.bak`` (:func:`_write_recovered_artifact`);
    ``_collect_summary_with_optional_repair`` then re-collects the summary
    EXACTLY once. Before the accept dirty-gate exclusion, that re-collect's
    ``git status`` snapshot sees the freshly-written, untracked ``plan.md.bak``
    as real dirt, ``AcceptanceSummary.ok`` flips ``False``, and a fully
    successful repair still exits 1 (``diagnose=True`` never caught this: it
    exits 0 unconditionally, before the ``if not summary.ok`` gate this test
    exercises).

    Non-vacuous / RED-before-GREEN: reverting the encoding-backup exclusion in
    ``_accept_dirty_gate`` reds this test (``accept`` raises ``typer.Exit(1)``
    instead of returning).
    """
    repo_root = (tmp_path / "repo").resolve()
    repo_root.mkdir()
    feature_dir = _create_accept_ready_feature_for_commit(repo_root)
    plan_path = _corrupt_plan_encoding(feature_dir)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(repo_root))
    monkeypatch.chdir(repo_root)
    _capture_console(monkeypatch)

    # A successful (non-JSON) accept returns normally -- no typer.Exit raised.
    accept(
        mission=_SLUG,
        mode="auto",
        actor="tester",
        test=[],
        json_output=False,
        lenient=False,
        no_commit=False,
        diagnose=False,
        allow_fail=False,
        normalize_encoding=True,
    )

    # The repaired artifact reads as clean, byte-exact UTF-8...
    assert plan_path.read_bytes() == _CP1252_PLAN_TEXT.encode("utf-8")
    plan_path.read_text(encoding="utf-8")  # must not raise

    # ...and its original-bytes backup is NOT a one-way trip: it survives the
    # accept (never cleaned up, never counted as blocking dirt).
    backup_path = plan_path.with_name(f"{plan_path.name}.bak")
    assert backup_path.exists(), "the encoding-recovery backup must survive a successful accept"
    assert backup_path.read_bytes() == _CP1252_PLAN_TEXT.encode("cp1252")
