"""Integration tests for ``spec-kitty profile-invocation complete`` (WP03 T012/T014).

Covers FR-003/FR-012:
- closed_by="agent" is recorded on every CLI close (no --closed-by flag exists).
- --outcome is required and validated at the CLI boundary (never silently "done").
- Each outcome value is written verbatim.
- Double close exits 1 with the structured already-closed error (rich + --json).
- Evidence refused for legacy advisory records before any write; accepted for task_execution.

WP05 (FR-013/C-005/C-007) extends this to the closer's help surface: the group
epilog must name ``spec-kitty dispatch`` as the opener without adding a command,
touching ``help=``, or changing anything ``complete`` records or emits.
"""

from __future__ import annotations

import json
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import click
import pytest
from click.testing import Result
from typer.main import get_command
from typer.testing import CliRunner

from specify_cli import app as cli_app
from specify_cli import completion
from specify_cli.cli.commands.profile_invocation import profile_invocation_app
from specify_cli.invocation.executor import ProfileInvocationExecutor
from specify_cli.invocation.modes import ModeOfWork
from specify_cli.invocation.writer import EVENTS_DIR
from tests._support.ansi import strip_ansi

# Marked for mutmut sandbox skip — subprocess CLI invocation.
pytestmark = [pytest.mark.non_sandbox, pytest.mark.fast]


class ArgvCliRunner(CliRunner):
    """CliRunner that also patches ``sys.argv`` so the CLI sees the real prog name."""

    # typer's CliRunner renames click's first parameter (``cli`` -> ``app``), so no
    # override can satisfy both supertypes; the runtime contract is typer's.
    def invoke(  # type: ignore[override]
        self,
        app: Any,
        args: str | Sequence[str] | None = None,
        **kwargs: Any,
    ) -> Result:
        argv = ["spec-kitty", *(list(args) if args is not None and not isinstance(args, str) else [])]
        with patch.object(sys, "argv", argv):
            return super().invoke(app, args, **kwargs)


runner = ArgvCliRunner()

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "profiles"

_COMPACT_CTX = MagicMock()
_COMPACT_CTX.mode = "compact"
_COMPACT_CTX.text = "compact governance context"


def _setup_project(tmp_path: Path) -> Path:
    """Create minimal project structure with fixture profiles."""
    profiles_dir = tmp_path / ".kittify" / "profiles"
    profiles_dir.mkdir(parents=True)
    for yaml_file in FIXTURES_DIR.glob("*.agent.yaml"):
        shutil.copy(yaml_file, profiles_dir / yaml_file.name)
    (tmp_path / EVENTS_DIR).mkdir(parents=True, exist_ok=True)
    return tmp_path


def _open_invocation(project: Path, mode: ModeOfWork = ModeOfWork.TASK_EXECUTION) -> str:
    """Open an Op directly through the executor; return its invocation_id."""
    with patch(
        "specify_cli.invocation.executor.build_charter_context",
        return_value=_COMPACT_CTX,
    ):
        executor = ProfileInvocationExecutor(project)
        payload = executor.invoke(
            "implement the feature",
            profile_hint="implementer-fixture",
            mode_of_work=mode,
        )
    return payload.invocation_id


def _run_complete(project: Path, *args: str):  # type: ignore[no-untyped-def]
    with (
        patch("specify_cli.cli.commands.profile_invocation.find_repo_root", return_value=project),
        patch(
            "specify_cli.invocation.executor.build_charter_context",
            return_value=_COMPACT_CTX,
        ),
    ):
        return runner.invoke(cli_app, ["profile-invocation", "complete", *args])


def _read_events(project: Path, invocation_id: str) -> list[dict[str, object]]:
    text = (project / EVENTS_DIR / f"{invocation_id}.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# closed_by="agent" on CLI closes; outcomes verbatim
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("outcome", ["done", "failed", "abandoned"])
def test_cli_close_records_outcome_verbatim_and_closed_by_agent(tmp_path: Path, outcome: str) -> None:
    project = _setup_project(tmp_path)
    inv_id = _open_invocation(project)

    result = _run_complete(project, "--invocation-id", inv_id, "--outcome", outcome)

    assert result.exit_code == 0, result.output
    events = _read_events(project, inv_id)
    completed = events[1]
    assert completed["event"] == "completed"
    assert completed["outcome"] == outcome
    assert completed["closed_by"] == "agent"


def test_cli_does_not_expose_closed_by_flag(tmp_path: Path) -> None:
    """The sweep is the only other closer and calls the executor directly (FR-003)."""
    project = _setup_project(tmp_path)
    inv_id = _open_invocation(project)

    result = _run_complete(
        project,
        "--invocation-id",
        inv_id,
        "--outcome",
        "done",
        "--closed-by",
        "doctor_sweep",
    )
    assert result.exit_code != 0
    # The Op stays open: the unknown option is rejected before any write.
    events = _read_events(project, inv_id)
    assert [e["event"] for e in events] == ["started"]


# ---------------------------------------------------------------------------
# Explicit-outcome guard: missing/invalid outcome is a usage error
# ---------------------------------------------------------------------------


def test_cli_missing_outcome_is_usage_error(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    inv_id = _open_invocation(project)

    result = _run_complete(project, "--invocation-id", inv_id)

    assert result.exit_code == 2, result.output
    # Nothing written — the Op is still open.
    events = _read_events(project, inv_id)
    assert [e["event"] for e in events] == ["started"]


def test_cli_invalid_outcome_is_usage_error(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    inv_id = _open_invocation(project)

    result = _run_complete(project, "--invocation-id", inv_id, "--outcome", "finished")

    assert result.exit_code == 2, result.output
    events = _read_events(project, inv_id)
    assert [e["event"] for e in events] == ["started"]


# ---------------------------------------------------------------------------
# Double close: structured already-closed error, exit 1, rich + JSON
# ---------------------------------------------------------------------------


def test_double_close_exits_1_rich(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    inv_id = _open_invocation(project)

    first = _run_complete(project, "--invocation-id", inv_id, "--outcome", "done")
    assert first.exit_code == 0, first.output

    second = _run_complete(project, "--invocation-id", inv_id, "--outcome", "done")
    assert second.exit_code == 1
    assert "already closed" in second.output

    # Idempotent: still exactly one completed event.
    events = _read_events(project, inv_id)
    assert [e["event"] for e in events].count("completed") == 1


def test_double_close_exits_1_json(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    inv_id = _open_invocation(project)

    first = _run_complete(project, "--invocation-id", inv_id, "--outcome", "done", "--json")
    assert first.exit_code == 0, first.output

    second = _run_complete(project, "--invocation-id", inv_id, "--outcome", "done", "--json")
    assert second.exit_code == 1
    error_obj = json.loads(second.output.strip().splitlines()[-1])
    assert error_obj == {"error": "already_closed", "invocation_id": inv_id}


# ---------------------------------------------------------------------------
# Evidence mode gate through the CLI (FR-009): refused before any write
# ---------------------------------------------------------------------------


def test_cli_evidence_refused_for_legacy_advisory_before_any_write(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    inv_id = _open_invocation(project, mode=ModeOfWork.ADVISORY)
    evidence = tmp_path / "evidence.md"
    evidence.write_text("# evidence", encoding="utf-8")

    result = _run_complete(
        project,
        "--invocation-id",
        inv_id,
        "--outcome",
        "done",
        "--evidence",
        str(evidence),
    )

    assert result.exit_code == 2
    # Pre-write rejection: started is still the only event; Op stays open.
    events = _read_events(project, inv_id)
    assert [e["event"] for e in events] == ["started"]
    assert not (project / ".kittify" / "evidence" / inv_id).exists()


def test_cli_evidence_accepted_for_task_execution(tmp_path: Path) -> None:
    project = _setup_project(tmp_path)
    inv_id = _open_invocation(project, mode=ModeOfWork.TASK_EXECUTION)
    evidence = tmp_path / "evidence.md"
    evidence.write_text("# evidence", encoding="utf-8")

    result = _run_complete(
        project,
        "--invocation-id",
        inv_id,
        "--outcome",
        "done",
        "--evidence",
        str(evidence),
    )

    assert result.exit_code == 0, result.output
    events = _read_events(project, inv_id)
    completed = events[1]
    assert completed["event"] == "completed"
    assert completed["closed_by"] == "agent"
    assert (project / ".kittify" / "evidence" / inv_id / "evidence.md").exists()


# ---------------------------------------------------------------------------
# Correlation links still appended after the completed event (FR-007)
# ---------------------------------------------------------------------------


def test_cli_close_appends_artifact_and_commit_links_after_completed(
    tmp_path: Path,
) -> None:
    project = _setup_project(tmp_path)
    inv_id = _open_invocation(project)

    result = _run_complete(
        project,
        "--invocation-id",
        inv_id,
        "--outcome",
        "done",
        "--artifact",
        "src/foo.py",
        "--artifact",
        "src/bar.py",
        "--commit",
        "deadbeef1234",
    )

    assert result.exit_code == 0, result.output
    events = [e["event"] for e in _read_events(project, inv_id)]
    assert events == [
        "started",
        "completed",
        "artifact_link",
        "artifact_link",
        "commit_link",
    ]


def test_cli_close_records_url_artifact_verbatim(tmp_path: Path) -> None:
    """#5270: an ``--artifact`` URL is recorded and echoed intact, not path-mangled."""
    project = _setup_project(tmp_path)
    inv_id = _open_invocation(project)
    url = "https://github.com/spec-kitty/spec-kitty/pull/5266"

    result = _run_complete(
        project,
        "--invocation-id",
        inv_id,
        "--outcome",
        "done",
        "--artifact",
        url,
        "--artifact",
        "src/foo.py",
        "--json",
    )

    assert result.exit_code == 0, result.output
    refs = [e["ref"] for e in _read_events(project, inv_id) if e["event"] == "artifact_link"]
    assert refs == [url, str(Path("src") / "foo.py")]
    assert json.loads(result.stdout)["artifact_links"] == refs


# ---------------------------------------------------------------------------
# Opener discoverability (FR-013 / SC-005): the closer's help names
# ``spec-kitty dispatch``, and it does so from the epilog only (C-007).
# ---------------------------------------------------------------------------


def _flatten(text: str) -> str:
    """Normalise Rich's help rendering so assertions survive any environment.

    Two independent renderings have to be collapsed before a literal can match:

    * **Colour.** Typer renders ``--help`` through its own ``rich`` console in
      :mod:`typer.rich_utils`, not a ``specify_cli.cli.console`` singleton. Since
      #5258 the ``_plain_cli_console_seam`` autouse fixture in
      ``tests/conftest.py`` also pins that console colourless, but this helper
      keeps stripping as defence in depth: under a colour-forcing harness Rich
      splices SGR codes *inside* tokens (``--outcome`` renders as a styled ``-``
      followed by a styled ``-outcome``), and stripping restores the plain text
      the user actually reads.
    * **Width.** Rich wraps and pads to the console width, so a literal spanning
      a wrap point needs whitespace collapsed.
    """
    return " ".join(strip_ansi(text).split())


def _resolve_group() -> click.Command:
    """Resolve the live ``profile-invocation`` group from the real CLI app."""
    root = get_command(cli_app)
    ctx = click.Context(root, info_name=completion.PROG_NAME)
    group: click.Command | None = root.get_command(ctx, "profile-invocation")  # type: ignore[attr-defined]
    assert group is not None
    return group


def test_group_help_names_the_dispatch_opener() -> None:
    result = runner.invoke(cli_app, ["profile-invocation", "--help"])

    assert result.exit_code == 0, result.output
    flat = _flatten(result.output)
    assert 'spec-kitty dispatch "<request>"' in flat
    assert "spec-kitty profile-invocation complete --invocation-id <id> --outcome <outcome>" in flat


def test_opener_pointer_lives_in_the_epilog_not_in_help() -> None:
    """C-007: ``help=`` feeds the completion manifest; the epilog does not."""
    info = profile_invocation_app.info

    assert info.help == "Manage invocation records."
    assert "dispatch" not in (info.help or "")
    assert "spec-kitty dispatch" in (info.epilog or "")


def test_no_profile_invocation_dispatch_subcommand() -> None:
    """C-007: the fix is help text, not an alias command."""
    result = runner.invoke(cli_app, ["profile-invocation", "dispatch", "--help"])

    assert result.exit_code != 0
    group = _resolve_group()
    subcommands = group.list_commands(click.Context(group, info_name="profile-invocation"))  # type: ignore[attr-defined]
    assert subcommands == ["complete"]


def test_completion_manifest_entry_unchanged_by_epilog() -> None:
    """C-007/C-005: the epilog carries no completion-manifest churn.

    Rebuild the ``profile-invocation`` node from the live CLI with the real
    generator and compare it to the committed manifest. Moving the pointer into
    ``help=`` (or adding a subcommand) fails this — the fix is to move the text
    back, never to regenerate the manifest.
    """
    live_node = completion.build_manifest_from_command(_resolve_group())
    committed_node = completion._load_manifest()["commands"]["profile-invocation"]

    assert live_node == committed_node
    assert "dispatch" not in json.dumps(live_node)
    assert sorted(live_node) == ["commands", "deprecated", "help", "hidden"]


def test_close_metadata_unchanged_by_epilog(tmp_path: Path) -> None:
    """FR-013 must not leak into what ``complete`` records or emits."""
    project = _setup_project(tmp_path)
    inv_id = _open_invocation(project)

    result = _run_complete(project, "--invocation-id", inv_id, "--outcome", "done", "--json")

    assert result.exit_code == 0, result.output
    assert json.loads(result.output) == {
        "result": "success",
        "invocation_id": inv_id,
        "outcome": "done",
        "evidence_ref": None,
        "artifact_links": [],
        "commit_link": None,
    }

    events = _read_events(project, inv_id)
    completed = events[1]
    assert sorted(completed) == [
        "closed_by",
        "completed_at",
        "event",
        "invocation_id",
        "outcome",
    ]
    assert "dispatch" not in json.dumps(events)
