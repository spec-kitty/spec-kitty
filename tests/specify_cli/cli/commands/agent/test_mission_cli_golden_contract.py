"""Golden CLI characterization harness for ``agent mission`` (#2056 WP01).

This is the **load-bearing safety net** for the entire decomposition of
``src/specify_cli/cli/commands/agent/mission.py``. It pins the byte-for-byte
``agent mission`` CLI surface — command names, per-command flag names and
defaults, positional arguments, and representative JSON success/error envelope
key sets — so every later WP can prove the extraction was behavior-preserving.

Source of truth: ``kitty-specs/decompose-mission-god-module-01KVXHF8/contracts/
cli-surface-contract.md`` (the frozen contract) and research.md §1 / §5.

NO production code is touched by this WP — test only (C-005).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import click
import pytest
from typer.main import get_command
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.mission import app as mission_app


def _resolve_subcommand(command_name: str) -> click.Command:
    """Resolve a registered ``agent mission`` subcommand from the Click tree.

    Introspects the resolved Click command tree directly (rather than the
    rendered ``--help`` text) so wrapped/truncated help output cannot mask a
    surface regression.
    """
    group = get_command(mission_app)
    assert isinstance(group, click.Group), "mission app must resolve to a Click Group"
    ctx = click.Context(group)
    sub = group.get_command(ctx, command_name)
    assert sub is not None, f"subcommand {command_name!r} not registered"
    return sub


def _command_flag_tokens(command_name: str) -> set[str]:
    """Return the exact option-flag token set for ``command_name``."""
    sub = _resolve_subcommand(command_name)
    tokens: set[str] = set()
    for param in sub.params:
        if isinstance(param, click.Option):
            tokens.update(param.opts)
            tokens.update(param.secondary_opts)
    return tokens


def _command_positional_names(command_name: str) -> set[str]:
    """Return the positional-argument parameter names for ``command_name``."""
    sub = _resolve_subcommand(command_name)
    return {p.name for p in sub.params if isinstance(p, click.Argument) and p.name is not None}


pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Frozen contract data (cli-surface-contract.md)
# ---------------------------------------------------------------------------


# The exact 10 subcommands `app` exposes, in alphabetical (Typer help) order.
# `repair` was added by WP08 of coord-write-placement-closure-01KYCF83 (the
# Gap-2 cross-partition content repair cure, FR-005/NFR-005) after the
# original #2056 characterization. `acceptance-verdict` was added by WP04 of
# write-side-seam-matrix-tracer-01KYP3MH (FR-001/FR-002/FR-012 — records one
# acceptance-criterion verdict into acceptance-matrix.json via the WP03 write
# seam). The contract below is amended in place rather than treated as
# append-only drift, per DIRECTIVE_044.
_EXPECTED_COMMANDS: frozenset[str] = frozenset(
    {
        "branch-context",
        "create",
        "check-prerequisites",
        "record-analysis",
        "setup-plan",
        "accept",
        "merge",
        "finalize-tasks",
        "repair",
        "acceptance-verdict",
    }
)


# Per-command flag surface. Each entry maps a subcommand name to the set of
# option flag *tokens* that MUST appear in its ``--help``. ``--no-*`` halves of
# boolean-pair flags are listed explicitly. A positional argument is recorded
# separately in ``_EXPECTED_POSITIONALS``.
_EXPECTED_FLAGS: dict[str, frozenset[str]] = {
    "branch-context": frozenset({"--json", "--target-branch"}),
    "create": frozenset(
        {
            "--mission-type",
            "--mission",
            "--json",
            "--target-branch",
            "--friendly-name",
            "--purpose-tldr",
            "--purpose-context",
            "--pr-bound",
            "--no-pr-bound",
            "--branch-strategy",
            "--start-branch",
            "--force-recreate-coordination-branch",
            "--topology",
            "--owned-checkout",  # added for the #3328 owned-checkout ownership fix (2026-08-13)
            "--retain-branches",  # added for the #3131 merge-retention opt-in (2026-09-02)
            "--retain-worktrees",  # added for the #3131 merge-retention opt-in (2026-09-02)
            "--allow-duplicate",  # added for the #4033 idempotency-guard escape hatch (2026-09-14)
            "--allow-dup",  # alias for --allow-duplicate (#4033)
        }
    ),
    "check-prerequisites": frozenset(
        {
            "--mission",
            "--json",
            "--paths-only",
            "--include-tasks",
            "--require-tasks",
            "--resume-probe",
            "--owned-checkout",
        }
    ),
    # Explicit opt-in added by analysis-report-transaction-01M38YDX; the
    # default broad dirty-tree guard remains the contract below.
    "record-analysis": frozenset({"--mission", "--input-file", "--agent", "--json", "--report-only"}),
    "setup-plan": frozenset({"--mission", "--json"}),
    # `--merge-commit` added for the #4231 PR-merge baseline recording passthrough (2026-09-13);
    # `--target-branch` added in the same issue's fix round for the PR-base-branch landing check (2026-09-14);
    # `--attest-first-landing-commit` added in fix round 4 — every landing shape needs the
    # operator attestation, so the agent lane must forward it too (2026-09-14).
    "accept": frozenset(
        {"--mission", "--mode", "--json", "--lenient", "--no-commit", "--diagnose", "--merge-commit", "--target-branch", "--attest-first-landing-commit"}
    ),
    "merge": frozenset(
        {
            "--mission",
            "--target",
            "--strategy",
            "--push",
            "--dry-run",
            "--keep-branch",
            "--delete-branch",
            "--keep-worktree",
            "--remove-worktree",
            "--auto-retry",
            "--no-auto-retry",
        }
    ),
    # 2026-09-09 (#4141): re-pinned to add --refresh-planning-commit (the
    # planning_commit_sha re-point affordance once execution has begun).
    # `missing: []` on the prior pin proves nothing was removed, only added —
    # same in-place amendment precedent as the 2026-08-04 fold below.
    # #4827: `--allow-orphaned` added -- the explicit operator assertion
    # required to re-pin an ORPHANED (mid-mission-rebase) planning_commit_sha
    # alongside `--refresh-planning-commit`. `missing: []` proves nothing
    # else was removed.
    "finalize-tasks": frozenset({"--mission", "--json", "--validate-only", "--target-branch", "--owned-checkout", "--refresh-planning-commit", "--allow-orphaned"}),
    "repair": frozenset({"--mission"}),
    # 2026-08-04 landing fold (PR #3175, fold-golden-flag-surface): re-pinned
    # to add the six negative-invariant-mode flags (--negative-invariant,
    # --description, --verification-command, --scope, --execute/--no-execute)
    # introduced by commit e5612270693b129f81368d89debd8abcd689736e ("feat:
    # post-consolidation write surface + deterministic authoring finish",
    # closing #2318/#1738). That commit is already an ancestor of merge-base
    # abca7ec96 — the flags are pre-existing, shipped, documented (see
    # docs/api/agent-subcommands.md) product surface; the frozen contract
    # simply never joined them. `missing: []` on the prior pin proved nothing
    # was removed, only added — this re-pin closes that gap per DIRECTIVE_044
    # (contract amended in place, not treated as append-only drift).
    "acceptance-verdict": frozenset(
        {
            "--mission",
            "--criterion",
            "--result",
            "--verification-method",
            "--actor",
            "--evidence",
            "--json",
            "--negative-invariant",
            "--description",
            "--verification-command",
            "--scope",
            "--execute",
            "--no-execute",
        }
    ),
}


# Subcommands that take a positional argument (Click parameter name).
_EXPECTED_POSITIONALS: dict[str, str] = {
    "create": "mission_slug",
}


# The ``--input-file`` default for record-analysis is the stdin sentinel ``-``.
_RECORD_ANALYSIS_INPUT_FILE_DEFAULT = "-"


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        check=True,
    )


def _init_repo(repo: Path) -> None:
    (repo / ".kittify").mkdir(exist_ok=True)
    (repo / "kitty-specs").mkdir(exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, capture_output=True, check=True)
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "commit", "-m", "init", "--allow-empty")


@pytest.fixture()
def runner() -> CliRunner:
    """Return a Typer CliRunner (typer >=0.13 separates stdout/stderr)."""
    return CliRunner()


# ---------------------------------------------------------------------------
# T001 — the command set is exactly the 10 frozen commands
# ---------------------------------------------------------------------------


def test_app_exposes_exactly_ten_frozen_commands(runner: CliRunner) -> None:
    """``app --help`` lists exactly the 10 contracted commands — no more, no fewer."""
    result = runner.invoke(mission_app, ["--help"], catch_exceptions=False)
    assert result.exit_code == 0, result.stdout

    registered = {cmd.name for cmd in mission_app.registered_commands}
    assert registered == set(_EXPECTED_COMMANDS), (
        f"Mission CLI command set drifted from the frozen contract.\n  expected: {sorted(_EXPECTED_COMMANDS)}\n  actual:   {sorted(registered)}"
    )

    # The help text must also surface every command name to the operator.
    for name in _EXPECTED_COMMANDS:
        assert name in result.stdout, f"command {name!r} missing from --help"


# ---------------------------------------------------------------------------
# T002 — per-command flags (names + key defaults) and positionals
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("command", sorted(_EXPECTED_FLAGS))
def test_command_exposes_exact_flag_surface(command: str) -> None:
    """Each subcommand exposes exactly the contracted flag token set.

    Introspects the resolved Click command (not rendered help) so the
    assertion is exact in both directions: no flag may be dropped AND no flag
    may be silently added during the decomposition.
    """
    actual = _command_flag_tokens(command)
    # `--help` is always present and not part of the domain contract.
    actual.discard("--help")
    expected = set(_EXPECTED_FLAGS[command])
    assert actual == expected, (
        f"`{command}` flag surface drifted from the frozen contract.\n  missing: {sorted(expected - actual)}\n  extra:   {sorted(actual - expected)}"
    )


def test_acceptance_verdict_flag_removal_reported_as_missing() -> None:
    """T010 regression: a flag dropped from the ACTUAL surface reds as `missing`.

    `test_command_exposes_exact_flag_surface` asserts full set equality
    (``actual == expected``), which is symmetric by construction: it can
    catch a flag being silently ADDED (``extra``) as well as one being
    silently REMOVED (``missing``). This is proven concretely for
    ``acceptance-verdict`` (rather than assumed) by simulating one of its six
    re-pinned flags disappearing from the command's real, introspected
    surface — without touching ``acceptance_verdict.py`` itself, which stays
    untouched per T010's binding constraint — and confirming the same
    ``expected - actual`` computation the parametrized test relies on
    reports exactly that flag under ``missing``, not silently.
    """
    expected = set(_EXPECTED_FLAGS["acceptance-verdict"])
    actual = _command_flag_tokens("acceptance-verdict")
    actual.discard("--help")
    # Sanity precondition: today's real surface matches the frozen contract
    # exactly. If it didn't, the simulated-removal assertion below would be
    # vacuous (a real drift would already be masking the injected one).
    assert actual == expected

    simulated_flag_dropped_from_command = "--negative-invariant"
    simulated_actual = actual - {simulated_flag_dropped_from_command}

    missing = expected - simulated_actual
    extra = simulated_actual - expected
    assert missing == {simulated_flag_dropped_from_command}, (
        f"removing a contracted flag from the command's actual surface must surface it under `missing`; got missing={sorted(missing)}"
    )
    assert not extra, f"unexpected extra reported: {sorted(extra)}"
    # The exact top-level assertion the real, parametrized test performs
    # (`actual == expected`) must itself go red under the simulated removal —
    # a half-contract that only compares "is actual a subset of expected"
    # would NOT catch this.
    assert simulated_actual != expected


@pytest.mark.parametrize("command,name", sorted(_EXPECTED_POSITIONALS.items()))
def test_command_exposes_positional_argument(command: str, name: str) -> None:
    """Commands with a positional argument expose it as a Click argument."""
    assert name in _command_positional_names(command), f"positional {name!r} missing from `{command}` parameters"


def test_record_analysis_input_file_default_is_stdin_sentinel() -> None:
    """``record-analysis --input-file`` defaults to the stdin sentinel ``-``."""
    sub = _resolve_subcommand("record-analysis")
    option = next(p for p in sub.params if isinstance(p, click.Option) and "--input-file" in p.opts)
    assert option.default == _RECORD_ANALYSIS_INPUT_FILE_DEFAULT


def test_record_analysis_report_only_requires_explicit_opt_in() -> None:
    """The transaction option never silently changes the default dirty guard."""
    sub = _resolve_subcommand("record-analysis")
    option = next(p for p in sub.params if isinstance(p, click.Option) and "--report-only" in p.opts)
    assert option.default is False


def test_create_mission_flag_is_hidden_deprecation() -> None:
    """``create``'s ``--mission`` flag is the hidden deprecated alias.

    The flag is registered (so the parser accepts it) but marked hidden, while
    the canonical ``--mission-type`` flag is visible.
    """
    sub = _resolve_subcommand("create")
    by_flag = {flag: p for p in sub.params if isinstance(p, click.Option) for flag in p.opts}
    assert "--mission" in by_flag, "deprecated --mission alias must remain registered"
    assert by_flag["--mission"].hidden is True, "--mission must stay hidden"
    assert "--mission-type" in by_flag
    assert by_flag["--mission-type"].hidden is False


# ---------------------------------------------------------------------------
# T003 — representative success JSON envelopes
# ---------------------------------------------------------------------------


# Keys the branch-context success envelope MUST carry. Includes the
# CLI-version injection (`_with_cli_version`) and the branch contract.
_BRANCH_CONTEXT_SUCCESS_KEYS: frozenset[str] = frozenset(
    {
        "result",
        "repo_root",
        "target_branch_source",
        "next_step",
        "current_branch",
        "planning_base_branch",
        "merge_target_branch",
        "branch_matches_target",
        "primary_branch",
        "current_is_primary",
        "recommended_strategy",
        "branch_recommendation_reason",
        "spec_kitty_version",
    }
)


def test_branch_context_success_envelope_keys(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``branch-context --json`` on a clean branch carries the frozen key set."""
    _init_repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(mission_app, ["branch-context", "--json"], catch_exceptions=False)
    assert result.exit_code == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"

    envelope = json.loads(result.stdout)
    assert isinstance(envelope, dict)
    missing = _BRANCH_CONTEXT_SUCCESS_KEYS - set(envelope)
    assert not missing, f"branch-context success envelope dropped keys: {sorted(missing)}\nenvelope keys: {sorted(envelope)}"
    assert envelope["result"] == "success"
    # Version-injection invariant (_with_cli_version): the version key is a str.
    assert isinstance(envelope["spec_kitty_version"], str)


def test_check_prerequisites_success_envelope_carries_paths_and_version(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``check-prerequisites --json --paths-only`` carries the path + version keys.

    Drives the command against a minimal valid mission fixture so the success
    envelope (rather than a detection error) is produced.
    """
    _init_repo(tmp_path)
    feature_dir = tmp_path / "kitty-specs" / "001-golden-fixture"
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "fixture mission")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        mission_app,
        ["check-prerequisites", "--mission", "001-golden-fixture", "--paths-only", "--json"],
        catch_exceptions=False,
    )
    # paths-only emits the legacy paths payload + branch contract + version.
    assert result.stdout, f"stderr={result.stderr!r}"
    envelope = json.loads(result.stdout)
    assert isinstance(envelope, dict)
    # Version injection and a representative path alias key are present.
    for key in ("spec_kitty_version", "FEATURE_DIR"):
        assert key in envelope, f"check-prerequisites paths-only envelope missing {key!r}; keys={sorted(envelope)}"


# ---------------------------------------------------------------------------
# T004 — representative error JSON envelope (PLAN_CONTEXT_UNRESOLVED)
# ---------------------------------------------------------------------------


def test_setup_plan_unresolved_error_envelope_keys(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``setup-plan --json`` with multiple missions emits PLAN_CONTEXT_UNRESOLVED.

    With >=2 candidate missions and no ``--mission`` selector the command cannot
    disambiguate and returns the frozen detection-error envelope. Cross-checks
    the contract keys ``error_code``, ``error``, ``spec_kitty_version``,
    ``available_missions``, ``remediation``, ``example_command``.
    """
    _init_repo(tmp_path)
    specs = tmp_path / "kitty-specs"
    for slug in ("001-alpha-mission", "002-beta-mission"):
        d = specs / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "spec.md").write_text("# Spec\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-m", "two missions")
    # The SaaS-auth FR-011 guard fires first when sync is opt-in; the mission
    # detection (PLAN_CONTEXT_UNRESOLVED) is the surface under test here.
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(mission_app, ["setup-plan", "--json"], catch_exceptions=False)
    assert result.stdout, f"stderr={result.stderr!r}"
    envelope = json.loads(result.stdout)
    assert isinstance(envelope, dict)

    assert envelope.get("error_code") == "PLAN_CONTEXT_UNRESOLVED", envelope
    for key in (
        "error_code",
        "error",
        "spec_kitty_version",
        "available_missions",
        "remediation",
        "example_command",
    ):
        assert key in envelope, f"PLAN_CONTEXT_UNRESOLVED envelope missing {key!r}; keys={sorted(envelope)}"
    assert isinstance(envelope["available_missions"], list)
    assert "001-alpha-mission" in envelope["available_missions"]


def test_setup_plan_no_missions_error_envelope_keys(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With zero candidate missions the envelope still carries the core keys.

    Pins the second (no-candidates) branch of the detection-error builder:
    ``error_code``, ``error``, ``spec_kitty_version``, ``remediation``.
    """
    _init_repo(tmp_path)
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(mission_app, ["setup-plan", "--json"], catch_exceptions=False)
    assert result.stdout, f"stderr={result.stderr!r}"
    envelope = json.loads(result.stdout)
    assert isinstance(envelope, dict)
    assert envelope.get("error_code") == "PLAN_CONTEXT_UNRESOLVED", envelope
    for key in ("error_code", "error", "spec_kitty_version", "remediation"):
        assert key in envelope, f"no-mission envelope missing {key!r}; keys={sorted(envelope)}"
