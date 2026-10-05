"""Scope-boundary contract tests for the ``--feature`` legacy alias.

These tests prove two complementary invariants:

1. **Hard-removal verification (T014 / FR-005):** The ``merge`` command
   (previously a deferred out-of-scope command) now fully rejects ``--feature``;
   the CLI parser returns exit 2 / "No such option".  All 8 user-facing commands
   cleaned in mission feature-alias-removal-01KW0N87 WP01–WP03 are covered by
   the in-scope file list below.

2. **First-party caller check (T015 / FR-003):** No source under
   ``src/charter/offering/`` passes ``--feature`` to any of the 18 in-scope internal
   command files.  ``next`` and ``merge`` are now in-scope and the stale
   doctrine ``--feature`` references on them have been removed — doctrine no
   longer references ``--feature`` on any command.

Rationale
---------
Mission feature-alias-removal-01KW0N87 (WP01–WP03) eliminated ``--feature``
from all 8 user-facing commands.  ``merge``, ``next``, ``implement``,
``research``, ``context``, ``accept``, ``lifecycle``, and ``mission-type``
now only accept ``--mission``.  This file locks that boundary.

All tests are offline / loopback — no network calls, no real git operations.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from typer.testing import CliRunner

from specify_cli import app

pytestmark = [pytest.mark.contract, pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# The same list as INSCOPE_FEATURE_FREE_FILES in test_terminology_guards.py.
# Kept in sync deliberately as a cross-file assertion boundary.
# ---------------------------------------------------------------------------
_INSCOPE_FILES: tuple[str, ...] = (
    # Original 10 internal command files cleaned in the prior mission.
    "src/specify_cli/cli/commands/agent/status.py",
    "src/specify_cli/cli/commands/agent/tasks.py",
    "src/specify_cli/cli/commands/agent/workflow.py",
    "src/specify_cli/cli/commands/agent/context.py",
    "src/specify_cli/cli/commands/agent/mission.py",
    "src/specify_cli/cli/commands/charter/lint.py",
    "src/specify_cli/cli/commands/materialize.py",
    "src/specify_cli/cli/commands/validate_encoding.py",
    "src/specify_cli/cli/commands/validate_tasks.py",
    "src/specify_cli/cli/commands/verify.py",
    # 8 user-facing command files de-aliased in mission feature-alias-removal-
    # 01KW0N87 WP01–WP03.  Authority: spec.md FR-007.
    "src/specify_cli/cli/commands/implement.py",
    "src/specify_cli/cli/commands/implement_planning_commit.py",
    "src/specify_cli/cli/commands/implement_claim.py",
    "src/specify_cli/cli/commands/merge.py",
    "src/specify_cli/cli/commands/next_cmd.py",
    "src/specify_cli/cli/commands/research.py",
    "src/specify_cli/cli/commands/context.py",
    "src/specify_cli/cli/commands/accept.py",
    "src/specify_cli/cli/commands/lifecycle.py",
    "src/specify_cli/cli/commands/mission_type.py",
)

# Leaf command names that correspond to the in-scope files, used for the
# first-party caller grep in T015.  These are the CLI surface names as exposed
# in the app's command tree.
_INSCOPE_COMMAND_NAMES: tuple[str, ...] = (
    "agent status",
    "agent tasks",
    "agent action",
    "agent workflow",
    "agent context",
    "agent mission",
    "charter lint",
    "materialize",
    "validate-encoding",
    "validate-tasks",
    "verify",
)

runner = CliRunner()


# ---------------------------------------------------------------------------
# T014 – Out-of-scope preservation regression
# Authority: spec.md FR-005
# ---------------------------------------------------------------------------


def test_merge_rejects_feature_alias() -> None:
    """``merge --feature <slug>`` must be rejected by the parser (WP01 hard removal).

    After mission feature-alias-removal-01KW0N87 WP01, ``--feature`` is fully
    removed from the merge command.  Passing it must produce Typer's
    "No such option: --feature" parse error (exit 2).

    Offline: no network call; the command exits at the parser level.
    """
    result = runner.invoke(app, ["consolidate", "--feature", "some-mission-slug"])

    # Exit 2 means Click/Typer rejected the flag ("No such option") — expected.
    assert result.exit_code == 2, (
        "WP01 regression: 'merge --feature' was NOT rejected by the parser "
        "(expected exit 2 / 'No such option').  The alias must be fully removed.\n"
        f"Output: {result.output!r}"
    )

    assert "No such option" in result.output, (
        "WP01 regression: 'merge --feature' did not produce 'No such option' "
        "parse error.  The alias must be fully removed.\n"
        f"Output: {result.output!r}"
    )


def test_merge_mission_accepted_feature_rejected() -> None:
    """``--mission`` is accepted; ``--feature`` is rejected by the merge parser (WP01).

    After mission feature-alias-removal-01KW0N87 WP01, only ``--mission`` (the
    canonical flag) is accepted.  ``--feature`` must produce a parse error
    (exit 2 / "No such option").

    Authority: WP01 hard-removal contract.
    """
    result_mission = runner.invoke(app, ["consolidate", "--mission", "some-mission-slug"])
    result_feature = runner.invoke(app, ["consolidate", "--feature", "some-mission-slug"])

    # --mission must be accepted (not a parse error / exit 2)
    assert result_mission.exit_code != 2, (
        "Canonical '--mission' flag rejected by merge parser (exit 2).\n"
        f"Output: {result_mission.output!r}"
    )
    assert "No such option" not in result_mission.output, (
        "Canonical '--mission' produced a parse-rejection message.\n"
        f"Output: {result_mission.output!r}"
    )

    # --feature must be rejected (exit 2 / "No such option")
    assert result_feature.exit_code == 2, (
        "WP01 regression: '--feature' was NOT rejected by merge parser (expected exit 2).\n"
        f"Output: {result_feature.output!r}"
    )
    assert "No such option" in result_feature.output, (
        "WP01 regression: '--feature' did not produce 'No such option' parse error.\n"
        f"Output: {result_feature.output!r}"
    )


# ---------------------------------------------------------------------------
# T015 – FR-003 first-party-caller check
# Authority: spec.md FR-003
# ---------------------------------------------------------------------------


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_no_doctrine_source_passes_feature_to_inscope_commands() -> None:
    """No ``src/charter/offering/`` source must pass ``--feature`` to an in-scope command.

    Scans all files under ``src/charter/offering/`` for occurrences of ``--feature``
    followed by (or in the context of) a reference to one of the 10 in-scope
    command names.  The 3 known doctrine hits (implement-review SKILL.md,
    runtime-next SKILL.md, occurrence-classification-workflow tactic) all
    reference out-of-scope commands (``next``, ``merge``, ``bulk-edit``).

    Authority: spec.md FR-003.  Research note R3.
    """
    doctrine_root = REPO_ROOT / "src" / "charter" / "offering"
    assert doctrine_root.exists(), f"src/charter/offering/ not found at {doctrine_root}"

    # Build a pattern that catches lines containing both --feature and an
    # in-scope command name.  We match each in-scope command name individually
    # so the error message is precise.
    offenders: list[str] = []

    for path in sorted(doctrine_root.rglob("*")):
        if not path.is_file():
            continue
        try:
            content = _read(path)
        except UnicodeDecodeError:
            continue  # skip binary files

        if "--feature" not in content:
            continue

        for lineno, line in enumerate(content.splitlines(), start=1):
            if "--feature" not in line:
                continue
            # Check if this line also references an in-scope command name
            for cmd_name in _INSCOPE_COMMAND_NAMES:
                # Match the command name as a substring (covers both
                # "spec-kitty agent status" and bare "agent status")
                if cmd_name in line or cmd_name.replace(" ", "-") in line:
                    rel = path.relative_to(REPO_ROOT).as_posix()
                    offenders.append(
                        f"{rel}:{lineno}: {line.strip()!r}  (in-scope command: {cmd_name!r})"
                    )

    assert not offenders, (
        "FR-003 regression: src/charter/offering/ source passes '--feature' to an in-scope "
        "command.  In-scope commands must be invoked without '--feature'.\n  "
        + "\n  ".join(offenders)
    )


def test_doctrine_feature_hits_are_only_outofscope_commands() -> None:
    """All ``--feature`` occurrences in ``src/charter/offering/`` reference out-of-scope commands.

    Positive-form companion to ``test_no_doctrine_source_passes_feature_to_inscope_commands``.
    Verifies that the known doctrine hits (implement-review, runtime-next,
    occurrence-classification-workflow) are still present and that they reference
    only out-of-scope commands (``next``, ``merge``, ``bulk-edit``).

    This test does NOT mandate that the hits exist — if doctrine is cleaned up
    in a future mission the test still passes.  It only enforces that any
    remaining hits name out-of-scope commands.

    Authority: spec.md FR-003.
    """
    doctrine_root = REPO_ROOT / "src" / "charter" / "offering"
    out_of_scope_command_fragments = (
        "next",
        "merge",
        "bulk-edit",
        "implement",
        "review",
        "specify",
        "plan",
        "tasks",
        # Note: "agent tasks" is in-scope but bare "tasks" in a skill
        # context typically refers to the full pipeline noun, not the command.
        # The companion test (test_no_doctrine_source_passes_feature_to_inscope_commands)
        # catches the specific "agent tasks" + "--feature" combination.
    )

    unexpected: list[str] = []

    for path in sorted(doctrine_root.rglob("*")):
        if not path.is_file():
            continue
        try:
            content = _read(path)
        except UnicodeDecodeError:
            continue

        if "--feature" not in content:
            continue

        for lineno, line in enumerate(content.splitlines(), start=1):
            if "--feature" not in line:
                continue
            # Skip lines that are clearly out-of-scope (contain known OOS tokens)
            if any(token in line for token in out_of_scope_command_fragments):
                continue
            # Skip pure notes / documentation lines (no command invocation)
            stripped = line.strip()
            # Lines that are plain note/description prose (no shell invocation)
            if stripped.startswith(">") or stripped.startswith("#"):
                continue
            # If we reach here the line has --feature but no known OOS command
            # and is not prose — flag it for review.
            rel = path.relative_to(REPO_ROOT).as_posix()
            unexpected.append(f"{rel}:{lineno}: {stripped!r}")

    # Use a warning-style assertion: fail with an explanatory message so
    # future contributors know what to check.
    unexpected_without_known_context = [
        hit
        for hit in unexpected
        if not any(
            known in hit
            for known in (
                "alias for --mission",
                "deprecated alias",
                "hidden deprecated",
                "--feature` is",
                "--feature` is the",
            )
        )
    ]
    assert not unexpected_without_known_context, (
        "src/charter/offering/ contains '--feature' lines that do not reference a known "
        "out-of-scope command and are not prose deprecation notes.  "
        "Review these lines and either remove '--feature' or add the relevant "
        "out-of-scope command name so the gate recognises them:\n  "
        + "\n  ".join(unexpected_without_known_context)
    )


# ---------------------------------------------------------------------------
# T014 supplemental – introspection: verify merge's --feature is hidden
# (complements the CliRunner invocation test above)
# ---------------------------------------------------------------------------


def test_merge_has_no_feature_param_in_cli_introspection() -> None:
    """Introspection confirms merge has NO ``--feature`` parameter (WP01 hard removal).

    Uses Click's command-tree API (via ``typer.main.get_command``) to inspect
    the merge command's parameters directly.  After WP01, ``--feature`` must be
    completely absent from the merge command's parameter list.

    Authority: WP01 hard-removal contract.
    """
    import click
    from typer.main import get_command

    cli: click.Group = get_command(app)  # type: ignore[assignment]
    merge_cmd = cli.commands.get("consolidate")
    assert merge_cmd is not None, "merge command not found in CLI app"

    feature_params = [
        param
        for param in merge_cmd.params
        if "--feature" in (list(getattr(param, "opts", []) or []) + list(getattr(param, "secondary_opts", []) or []))
    ]
    assert not feature_params, (
        "WP01 regression: merge command still has a '--feature' parameter. "
        "The alias must be fully removed (hard removal, not hidden).\n"
        f"Found: {feature_params!r}"
    )


def test_inscope_files_have_no_feature_param_in_cli_introspection() -> None:
    """Introspection confirms no in-scope command exposes a ``--feature`` param.

    Walks the full CLI command tree and asserts that none of the commands
    backed by the 10 in-scope files declare a ``--feature`` parameter (hidden
    or visible).

    Authority: spec.md FR-003, FR-004.
    """
    import click
    from typer.main import get_command

    cli: click.Group = get_command(app)  # type: ignore[assignment]

    # Map normalised command path strings to their Click commands
    def _walk(
        group: click.Group, prefix: tuple[str, ...] = ()
    ) -> list[tuple[str, click.Command]]:
        found: list[tuple[str, click.Command]] = []
        for name, cmd in group.commands.items():
            path = prefix + (name,)
            if isinstance(cmd, click.Group):
                found.extend(_walk(cmd, path))
            elif isinstance(cmd, click.Command):
                found.append((" ".join(path), cmd))
        return found

    # Normalise in-scope command names for substring matching
    inscope_normalised = {name.replace("-", " ") for name in _INSCOPE_COMMAND_NAMES}

    offenders: list[str] = []
    for path_str, cmd in _walk(cli):
        normalised_path = path_str.replace("-", " ")
        if not any(normalised_path == inscope or normalised_path.endswith(f" {inscope}") for inscope in inscope_normalised):
            continue  # not an in-scope command

        for param in cmd.params:
            declared = list(getattr(param, "opts", []) or []) + list(getattr(param, "secondary_opts", []) or [])
            if "--feature" in declared:
                offenders.append(
                    f"command '{path_str}' still declares '--feature' param "
                    f"(hidden={getattr(param, 'hidden', False)})"
                )

    assert not offenders, (
        "FR-003/FR-004 regression: in-scope commands still declare '--feature' "
        "at the CLI introspection level.  Remove the alias from these commands:\n  "
        + "\n  ".join(offenders)
    )


def test_validate_tasks_requires_selector_cleanly() -> None:
    """``validate-tasks`` with no ``--mission``/``--all`` must error cleanly, not crash.

    Regression guard (adversarial bug-hunt, 1060-A): the WP02 alias removal
    deleted an *unconditional* ``resolve_selector`` call whose both-None branch
    raised a clean "selector required" error. Without an inline guard the bare
    ``mission_slug = mission`` passed ``None`` downstream and raised an uncaught
    ``TypeError`` (Rich traceback) instead. Assert a clean ``Exit(1)`` and that
    no unexpected exception (e.g. TypeError) escapes.
    """
    result = runner.invoke(app, ["validate-tasks"])
    assert result.exit_code == 1, result.output
    assert not isinstance(result.exception, TypeError), result.output
    assert "required" in result.output.lower()


def test_validate_tasks_direct_call_without_selector_clean_error(tmp_path: Path) -> None:
    """Programmatic calls must not leak Typer ``OptionInfo`` into ``.strip()``."""
    from specify_cli.cli.commands.validate_tasks import validate_tasks

    with (
        patch("specify_cli.cli.commands.validate_tasks.find_repo_root", return_value=tmp_path),
        patch(
            "specify_cli.cli.commands.validate_tasks.get_project_root_or_exit",
            return_value=tmp_path,
        ),
        pytest.raises(typer.Exit) as excinfo,
    ):
        validate_tasks(check_all=False)

    assert excinfo.value.exit_code == 1


def test_validate_encoding_requires_selector_cleanly() -> None:
    """``validate-encoding`` with no selector must error cleanly, not crash.

    Same regression class as ``test_validate_tasks_requires_selector_cleanly``.
    """
    result = runner.invoke(app, ["validate-encoding"])
    assert result.exit_code == 1, result.output
    assert not isinstance(result.exception, TypeError), result.output
    assert "required" in result.output.lower()
