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
from specify_cli.cli.commands.accept import accept
from specify_cli.config.path_conventions import PathConventionsConfigError
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
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
