"""Golden characterization of the ``spec-kitty doctor`` CLI surface (WP01, #2059).

This is the single objective proof that the public ``doctor`` surface stays
byte-identical across the god-module decomposition (FR-001, FR-002, C-005, I-1).
It MUST pass at HEAD against the un-refactored ``doctor.py`` and is re-run by
every subsequent extraction WP.

It pins, independently of the implementation source:

* the exact set of registered subcommand names (set-equality, order-free);
  24 as of #4130, which added ``bytecode`` (installed-package .pyc
  corruption check, #4124's detection half) via the same auto-discovery seam,
  on top of the 23 as of operator-config-ergonomics-01M04YK8, which added the
  ``provenance`` (WP03, C-PRV-5 leak-check), ``channel`` (WP05, C-CHN-3 rc
  release-channel report), and ``env-file`` (WP06, T019 ``.kitty.env`` health
  report) subcommands -- each registered via the ``doctor.py`` auto-discovery
  seam (T015) rather than a hand-written ``@app.command`` shell in this file --
  on top of the 20 names as of mission-type-guard-registry-01KZY2FG WP02, which
  added ``mission-type`` (FR-007 mission-type resolution health audit) on top
  of the 19 names as of review-cycle-verdict-seam-rebuild-01KZ2W7W WP08's
  ``review-cycle-reconcile`` addition (FR-008 stranded-record reconciliation)
  on top of the 18 prior names (17 names as of
  runtime-state-birth-cutover-all-paths-01KYH654 WP05's ``cutover`` addition:
  16 de-godding names from #2059 + ``contracts`` from #2441);
* each subcommand's option flags + arity (flag/value/multi);
* each subcommand's ``--help`` body (whitespace-normalized snapshot);
* the documented exit-code contracts, including the load-bearing names
  (``skills``, ``sparse-checkout``) that ``compat`` safety predicates key on.
  (The daemon commands the argv fast-path keyed on died with the sync
  transport, issue #5.)

The help snapshots are captured through :func:`force_wide_help_console`, which
pins Typer's Rich help console to a fixed wide, colourless size so no line ever
wraps, then normalized (box-drawing stripped, lines trimmed, blanks dropped,
internal whitespace collapsed) so each option/usage entry is one logical line.
That makes the snapshot genuinely deterministic across terminal widths — local
wide terminals, CI's TTY-less 80-column fallback, ``COLUMNS`` set or unset —
while still failing on any usage/description/flag/help-text drift.
"""

from __future__ import annotations

import os

import click
import pytest
from typer.main import get_command
from typer.testing import CliRunner

from specify_cli.cli.commands.doctor import app
from specify_cli.cli.commands import _apply_short_help_options
from tests.specify_cli.cli.commands._help_snapshot import (
    force_wide_help_console,
    normalize_help,
)

pytestmark = [pytest.mark.fast]

# Match the root registration policy explicitly so this standalone singleton
# is deterministic regardless of test import order.
_apply_short_help_options(app)

# --- Frozen contract: the 17 subcommand names (cli-surface-contract.md) -------
# 16 de-godding names (#2059) + ``contracts`` (#2441, Contract Registry validator).
# operator-config-ergonomics adds ``provenance`` (WP03), ``channel`` (WP05), and
# ``env-file`` (WP06) on top of main's ``mission-type`` (mission-type-guard-registry
# WP02): 23 total.

FROZEN_SUBCOMMANDS: frozenset[str] = frozenset(
    {
        "command-files",
        "skills",
        "tool-surfaces",
        "state-roots",
        "workspaces",
        "identity",
        "topology",
        "mission-type",
        "sparse-checkout",
        "shim-registry",
        "contracts",
        "invocation-pairing",
        "ops",
        "mission-state",
        "doctrine",
        "coordination",
        "cutover",
        "review-cycle-reconcile",
        "provenance",
        "channel",
        "env-file",
        "bytecode",
    }
)

# Frozen option contract per subcommand: name -> {flag: ("flag" | "value" | "multi")}.
# "flag" = boolean switch (is_flag), "value" = takes one value, "multi" = repeatable.
EXPECTED_OPTIONS: dict[str, dict[str, str]] = {
    "command-files": {"--json": "flag"},
    "skills": {"--fix": "flag", "--json": "flag"},
    "tool-surfaces": {
        "--kind": "multi",
        "--tool": "value",
        "--fix": "flag",
        "--json": "flag",
    },
    "state-roots": {"--json": "flag"},
    "workspaces": {"--fix": "flag", "--json": "flag"},
    "identity": {"--json": "flag", "--mission": "value", "--fail-on": "value"},
    "topology": {"--json": "flag", "--mission": "value"},
    "mission-type": {"--json": "flag", "--mission": "value", "--fail-on": "value"},
    "sparse-checkout": {"--fix": "flag"},
    "shim-registry": {"--json": "flag"},
    "contracts": {"--json": "flag"},
    "invocation-pairing": {"--json": "flag"},
    "ops": {"--json": "flag", "--close-stale": "flag", "--threshold": "value"},
    "mission-state": {
        "--audit": "flag",
        "--fix": "flag",
        "--teamspace-dry-run": "flag",
        "--json": "flag",
        "--mission": "value",
        "--fail-on": "value",
        "--fixture-dir": "value",
        "--include-fixtures": "flag",
        "--manifest-path": "value",
        "--allow-dirty": "flag",
    },
    "doctrine": {"--json": "flag"},
    "coordination": {
        "--fix": "flag",
        "--json": "flag",
        "--check-staleness": "flag",
        "--mission": "value",
    },
    "cutover": {"--json": "flag"},
    "review-cycle-reconcile": {"--mission": "value", "--json": "flag"},
    "provenance": {"--json": "flag"},
    "channel": {"--json": "flag"},
    "env-file": {"--json": "flag"},
    "bytecode": {"--json": "flag"},
}

# Golden ``--help`` snapshots (whitespace-normalized) per subcommand.
EXPECTED_HELP: dict[str, list[str]] = {
    "command-files": [
        "Usage: doctor command-files [OPTIONS]",
        "Check all agent command files for correctness.",
        "Verifies that every configured agent has the correct command files:",
        "- Full rendered prompts for prompt-driven commands (specify, plan, tasks, ...)",
        "- Thin shims for CLI-driven commands (implement, review, merge, ...)",
        "- Current version markers on all files",
        "Examples:",
        "spec-kitty doctor command-files",
        "spec-kitty doctor command-files --json",
        "Options",
        "--json Machine-readable JSON output",
        "--help -h Show this message and exit.",
    ],
    "skills": [
        "Usage: doctor skills [OPTIONS]",
        "Check command-skill manifest drift for Codex, Vibe, Pi, and Letta.",
        "Options",
        "--fix Repair missing command-skill files",
        "--json Machine-readable JSON output",
        "--help -h Show this message and exit.",
    ],
    "tool-surfaces": [
        "Usage: doctor tool-surfaces [OPTIONS]",
        "Audit (and optionally repair) every configured tool surface.",
        "Examples:",
        "spec-kitty doctor tool-surfaces --json",
        "spec-kitty doctor tool-surfaces --kind command-skill --json",
        "spec-kitty doctor tool-surfaces --tool codex --fix",
        "Options",
        "--kind TEXT Filter to surface kind(s), e.g. command-skill",
        "--tool TEXT Filter to a single configured tool key",
        "--fix Repair missing or stale surfaces",
        "--json Machine-readable JSON output",
        "--help -h Show this message and exit.",
    ],
    "state-roots": [
        "Usage: doctor state-roots [OPTIONS]",
        "Show state roots, surface classification, and safety warnings.",
        "Displays the three state roots with resolved paths, all registered",
        "state surfaces grouped by root with authority and Git classification,",
        "and warnings for any runtime surfaces not covered by .gitignore.",
        "Examples:",
        "spec-kitty doctor state-roots",
        "spec-kitty doctor state-roots --json",
        "Options",
        "--json Machine-readable JSON output",
        "--help -h Show this message and exit.",
    ],
    "workspaces": [
        "Usage: doctor workspaces [OPTIONS]",
        "Report .worktrees/ husk directories (entries lacking a .git entry).",
        "A husk is not a usable git worktree: git commands run inside it fall",
        "through to the primary repository (#1833). Workspace resolution refuses",
        "husks with a structured error; this check is the recovery path.",
        "Examples:",
        "spec-kitty doctor workspaces",
        "spec-kitty doctor workspaces --fix",
        "spec-kitty doctor workspaces --json",
        "Options",
        "--fix Remove husks that are NOT registered in `git worktree list` (registered worktrees are never removed)",
        "--json Machine-readable JSON output",
        "--help -h Show this message and exit.",
    ],
    "identity": [
        "Usage: doctor identity [OPTIONS]",
        "Report mission-identity health across kitty-specs/.",
        "Classifies every mission into one of four states (FR-045):",
        "\\b",
        "- assigned: mission_id present AND mission_number non-null (fully migrated)",
        "- pending: mission_id present AND mission_number null (pre-merge)",
        "- legacy: mission_id missing AND mission_number present (needs backfill)",
        "- orphan: both fields missing or meta.json unreadable (needs triage)",
        "Also reports duplicate numeric prefixes (FR-011) and ambiguous selectors",
        "that would resolve to multiple missions (FR-012).",
        "Examples:",
        "spec-kitty doctor identity",
        "spec-kitty doctor identity --json",
        "spec-kitty doctor identity --mission 083-foo",
        "spec-kitty doctor identity --fail-on legacy,orphan",
        "Options",
        "--json Emit structured JSON output (suitable for CI)",
        "--mission TEXT Scope report to a single mission slug",
        "--fail-on TEXT Exit non-zero if any mission is in the given state(s). Comma-separated list of: assigned, pending, legacy, orphan.",
        "--help -h Show this message and exit.",
    ],
    "topology": [
        "Usage: doctor topology [OPTIONS]",
        "Report each mission's STORED topology across kitty-specs/.",
        "Reads the authoritative ``topology`` value persisted in ``meta.json`` WITHOUT",
        "re-inferring from disk/git. Missions not yet backfilled surface",
        "``topology: null`` — run ``spec-kitty migrate backfill-topology`` to persist",
        "the computed value.",
        "Examples:",
        "spec-kitty doctor topology",
        "spec-kitty doctor topology --json",
        "spec-kitty doctor topology --mission 083-foo",
        "Options",
        "--json Emit structured JSON output (suitable for CI)",
        "--mission TEXT Scope report to a single mission slug",
        "--help -h Show this message and exit.",
    ],
    "mission-type": [
        "Usage: doctor mission-type [OPTIONS]",
        "Report mission-type resolution health across kitty-specs/.",
        "Classifies every mission into one of six states (FR-008):",
        "\\b",
        "- resolved: mission_type present, activated, and loadable",
        "- activated-unresolvable: activated but has no loadable profile on disk",
        "- unknown: mission_type present but not activated/registered anywhere",
        "- typeless: no mission_type key (or a blank/null/non-string value)",
        "- legacy-key-only: only the retired `mission` key is present",
        "- error: meta.json unreadable or malformed",
        "Examples:",
        "spec-kitty doctor mission-type",
        "spec-kitty doctor mission-type --json",
        "spec-kitty doctor mission-type --mission 083-foo",
        "spec-kitty doctor mission-type --fail-on unknown,activated-unresolvable",
        "Options",
        "--json Emit structured JSON output (suitable for CI)",
        "--mission TEXT Scope report to a single mission slug",
        "--fail-on TEXT Exit non-zero if any mission is in the given state(s). "
        "Comma-separated list of: resolved, activated-unresolvable, unknown, "
        "typeless, legacy-key-only, error.",
        "--help -h Show this message and exit.",
    ],
    "sparse-checkout": [
        "Usage: doctor sparse-checkout [OPTIONS]",
        "Detect and optionally remediate legacy sparse-checkout state.",
        "Without ``--fix``: scans the repo and prints a warning finding",
        "describing any active sparse-checkout state (primary + lane",
        "worktrees). Exits 0 when clean, 1 when state is present.",
        "With ``--fix``: in an interactive TTY, prints a step-by-step plan,",
        "prompts once for consent, and calls WP03's ``remediate()``. In",
        "non-interactive / CI environments, prints a remediation pointer and",
        "exits non-zero without mutating state (FR-023).",
        "Examples:",
        "spec-kitty doctor sparse-checkout",
        "spec-kitty doctor sparse-checkout --fix",
        "Options",
        "--fix Apply remediation (disable sparse-checkout on primary + worktrees).",
        "--help -h Show this message and exit.",
    ],
    "shim-registry": [
        "Usage: doctor shim-registry [OPTIONS]",
        "Check for overdue compatibility shims in the shim registry.",
        "Reads docs/migrations/shim-registry.yaml and compares each entry's",
        "removal_target_release against the current project version. Fails with",
        "exit code 1 if any shim is overdue (removal release has shipped but",
        "shim file still exists on disk).",
        "Exit codes:",
        "0 All entries are pending, removed, or grandfathered.",
        "1 At least one entry is overdue — shim must be deleted or window extended.",
        "2 Configuration error (registry file or pyproject.toml missing/invalid).",
        "Examples:",
        "spec-kitty doctor shim-registry",
        "spec-kitty doctor shim-registry --json",
        "Options",
        "--json Machine-readable JSON output",
        "--help -h Show this message and exit.",
    ],
    "contracts": [
        "Usage: doctor contracts [OPTIONS]",
        "Validate the Contract Registry for well-formedness.",
        "Reads docs/contracts/contract-registry.yaml and validates every record",
        "against the schema: required fields present, kind/status/enforcement in",
        "range, semver + tracker refs well-formed, anchors resolve, and — the DIR-041",
        "self-consistency gate (NFR-003) — NO positional file:line anchoring anywhere.",
        "Structural validation is the only enforcing gate in v1; the retirement",
        "absence-sweep is advisory.",
        "Exit codes:",
        "0 Registry is well-formed (or empty).",
        "2 Configuration error (registry file missing) or a schema violation.",
        "Examples:",
        "spec-kitty doctor contracts",
        "spec-kitty doctor contracts --json",
        "Options",
        "--json Machine-readable JSON output",
        "--help -h Show this message and exit.",
    ],
    "invocation-pairing": [
        "Usage: doctor invocation-pairing [OPTIONS]",
        "List orphan profile-invocation lifecycle records.",
        "WP05 (#843) wiring: scans",
        "``.kittify/events/profile-invocation-lifecycle.jsonl`` for ``started``",
        "records with no paired ``completed`` or ``failed`` partner. Mid-cycle",
        "agent crashes show up here. The check observes; it does not remediate.",
        "Exit codes:",
        "0 No orphans observed.",
        "1 At least one orphan found.",
        "Examples:",
        "spec-kitty doctor invocation-pairing",
        "spec-kitty doctor invocation-pairing --json",
        "Options",
        "--json Machine-readable JSON output",
        "--help -h Show this message and exit.",
    ],
    "ops": [
        "Usage: doctor ops [OPTIONS]",
        "List orphan Op records; --close-stale sweeps stale ones closed as abandoned.",
        "Options",
        "--json Machine-readable JSON output",
        "--close-stale Close open Ops older than --threshold as abandoned (closed_by=doctor_sweep)",
        "--threshold FLOAT Staleness threshold in hours (default 24; 0 closes all). Requires --close-stale.",
        "--help -h Show this message and exit.",
    ],
    "mission-state": [
        "Usage: doctor mission-state [OPTIONS]",
        "Audit, repair, or TeamSpace-validate mission-state shapes.",
        "Options",
        "--audit Run mission-state audit (required to proceed)",
        "--fix Repair mission-state artifacts in place and write a migration manifest",
        "--teamspace-dry-run Synthesize canonical TeamSpace envelopes from local state and validate them",
        "--json Emit JSON report to stdout",
        "--mission TEXT Scope to a single mission handle",
        "--fail-on TEXT Exit 1 if findings meet a gate (error|warning|info|teamspace-blocker)",
        "--fixture-dir PATH Override scan root (for testing)",
        "--include-fixtures Audit the bundled mission-state survey fixtures",
        "--manifest-path PATH Path for --fix migration manifest",
        "--allow-dirty Allow --fix when relevant git paths are already dirty",
        "--help -h Show this message and exit.",
    ],
    "doctrine": [
        "Usage: doctor doctrine [OPTIONS]",
        "Check org doctrine snapshot status and list installed pack artifacts.",
        "Exit code reflects health (WP01, operator directive: loud over hidden): the",
        "command exits **1 when the report is unhealthy** and 0 only when healthy",
        "(``report.healthy`` drives the code on every output path). A clear RC=1 with",
        "a surfaced error is preferred over an RC=0 that hides a defect. It",
        "enumerates each configured org pack (from ``.kittify/config.yaml``), prints",
        "its on-disk version (``git describe`` for git-managed packs, otherwise the",
        "``pack-manifest.yaml`` ``pack_version``), per-artifact YAML counts, and",
        "``org-charter.yaml`` policy status when present.",
        "Override governance (FR-010 / FR-012): when org packs are configured, any",
        "``org:``-provenance override of a built-in DRG node that is NOT sanctioned",
        "by ``.kittify/doctrine/replaceable-builtins.yaml`` is reported as an",
        "``unsanctioned_overrides`` finding and flips the report unhealthy (RC=1).",
        "Project-tier (``.kittify/doctrine/``) overrides of built-ins are",
        "intentionally **ungoverned** — project doctrine is the trusted operator tier",
        "and is not gated by the consumer-facing allowlist; only org-tier overrides",
        "are adjudicated.",
        "Examples:",
        "spec-kitty doctor doctrine",
        "spec-kitty doctor doctrine --json",
        "Options",
        "--json Machine-readable JSON output",
        "--help -h Show this message and exit.",
    ],
    "coordination": [
        "Usage: doctor coordination [OPTIONS]",
        "Run the WP04 #1348 coordination + sparse-checkout health checks.",
        "Iterates over every mission under ``kitty-specs/`` whose ``meta.json``",
        "declares a ``coordination_branch`` field, runs the coord-worktree",
        "and lane-sparse-checkout health checks, and prints findings.",
        "Also runs the minimum git-version (RR-01) check.",
        "Exits with code 1 if any ``error`` finding is emitted; ``warning``",
        "findings exit 0 but are still printed.",
        "With ``--fix``, automatically flattens missions that have a stale",
        "``coordination_branch`` key (branch never created or already deleted),",
        "re-derives topology, and attempts the Gap-1 coord-vs-target fast-forward",
        "(FR-009) -- which fails loud with a unified diff and mutates nothing when",
        "the coord branch has diverged or its worktree is dirty. Safe to run on",
        "100%-done missions before ``spec-kitty next`` or ``spec-kitty merge``.",
        "With ``--check-staleness``, also reports Gap-1 coord-branch-vs-target",
        "staleness (FR-008) — non-blocking either way.",
        "With ``--mission <handle>``, scopes every per-mission check (and the",
        "``--fix`` Gap-1 fast-forward) to the single mission the shared resolver maps",
        "the handle to. An unresolvable / ambiguous handle fails closed with exit 1.",
        "Examples:",
        "spec-kitty doctor coordination",
        "spec-kitty doctor coordination --fix",
        "spec-kitty doctor coordination --json",
        "spec-kitty doctor coordination --check-staleness",
        "spec-kitty doctor coordination --mission 083-my-mission",
        "Options",
        "--fix Remove stale coordination_branch keys from meta.json for missions "
        "whose coord branch was never created, then re-derive topology via "
        "`migrate backfill-topology`.",
        "--json Machine-readable JSON output",
        "--check-staleness Also report coord-branch-vs-target-branch staleness "
        "(Gap-1, FR-008): non-blocking, whether the coord branch is behind or has "
        "diverged from its mission's target_branch.",
        "--mission TEXT Scope the checks to a single mission handle (mission_id / mid8 / slug), resolved via the same resolver as `doctor mission-state`.",
        "--help -h Show this message and exit.",
    ],
    "cutover": [
        "Usage: doctor cutover [OPTIONS]",
        "Audit every mission's cut-over status outside CI (FR-007).",
        "Backed by ``migration.runtime_state_cutover.cutover_repo(dry_run=True)``:",
        "the same fail-closed seed-then-verify spine the birth-cutover migration",
        "uses, read-only and writing nothing. Reports each mission slug, whether",
        "it is cut over, and a reason when it is not.",
        "Informational only: always exits 0 with a summary count.",
        "Examples:",
        "spec-kitty doctor cutover",
        "spec-kitty doctor cutover --json",
        "Options",
        "--json Machine-readable JSON output",
        "--help -h Show this message and exit.",
    ],
    "review-cycle-reconcile": [
        "Usage: doctor review-cycle-reconcile [OPTIONS]",
        "Find review-cycle / arbiter-override records stranded under a retired resolver path, ahead of WP13's consumer-unification (FR-008).",
        "Every retired resolver comes from WP08's reviewed retirement set, not a",
        "guessed set. Reports two DISTINCT stranded classes per finding: a",
        "deleted-coordination-branch mission (absorbed to PRIMARY, the measured",
        "45-mission corpus) and a live-coordination-branch mission still carrying a",
        "pre-ADR PRIMARY record. Never a bare count — every finding names its",
        "mission, WP, retired resolver, and resolved directory.",
        "Informational only: always exits 0. No ``--fix`` — a stranded record may",
        "have a legitimate divergent sibling, and this command does not pick a",
        "winner.",
        "Examples:",
        "spec-kitty doctor review-cycle-reconcile",
        "spec-kitty doctor review-cycle-reconcile --mission my-mission-01ABCD",
        "spec-kitty doctor review-cycle-reconcile --json",
        "Options",
        "--mission TEXT Scope to a single mission (mission_id / mid8 / slug)",
        "--json Machine-readable JSON output",
        "--help -h Show this message and exit.",
    ],
    "provenance": [
        "Usage: doctor provenance [OPTIONS]",
        "Flag committed absolute built-in-pack source_path leaks (C-PRV-5).",
        "Scans .kittify/charter/charter.yaml's catalog and",
        ".kittify/agent_profiles_manifest.json for a source_path that should",
        "be a ${SPEC_KITTY_PACKS_ROOT}/built-in/... token but is not, and",
        "prints a heal hint for each. Read-only -- never mutates state.",
        "Examples:",
        "spec-kitty doctor provenance",
        "spec-kitty doctor provenance --json",
        "Options",
        "--json Machine-readable JSON output",
        "--help -h Show this message and exit.",
    ],
    "channel": [
        "Usage: doctor channel [OPTIONS]",
        "Report the active release channel (stable vs. prerelease-opt-in).",
        "Reads SPEC_KITTY_PRERELEASE (default OFF — stable channel). Never",
        "mutates state.",
        "Examples:",
        "spec-kitty doctor channel",
        "spec-kitty doctor channel --json",
        "Options",
        "--json Machine-readable JSON output",
        "--help -h Show this message and exit.",
    ],
    "env-file": [
        "Usage: doctor env-file [OPTIONS]",
        "Report ``.kitty.env`` operator env-file health (presence/tier/ignore).",
        "Reads the repo- and home-tier ``.kitty.env`` files and the",
        "config.yaml ``env_file`` pointer, and reports which governed vars",
        "are set and from which tier -- names/presence only for anything not",
        "on the printable-var allowlist (C-SEC-1), values never leaked.",
        "Read-only -- never mutates state.",
        "Examples:",
        "spec-kitty doctor env-file",
        "spec-kitty doctor env-file --json",
        "Options",
        "--json Machine-readable JSON output",
        "--help -h Show this message and exit.",
    ],
    "bytecode": [
        "Usage: doctor bytecode [OPTIONS]",
        "Flag a corrupt installed-package .pyc before it bites (#4124, #4130).",
        "Reads each .pyc under the installed specify_cli package and flags one",
        "whose header Python's import machinery would trust (so it would be",
        "used as-is) but whose body fails to unmarshal into a code object --",
        "the truncated-write shape that crashed a training machine in #4124.",
        "A cache Python would already recompile from source (bad magic, stale",
        "timestamp/size) is not flagged; it never bites. Read-only -- never",
        "deletes anything.",
        "Examples:",
        "spec-kitty doctor bytecode",
        "spec-kitty doctor bytecode --json",
        "Options",
        "--json Machine-readable JSON output",
        "--help -h Show this message and exit.",
    ],
}


@pytest.fixture(scope="module")
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def _fixed_terminal_width(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force wrap-free, colourless ``--help`` rendering for deterministic snapshots.

    Replaces the old ``COLUMNS=100`` pin, which CI ignored on the Rich help path
    (no TTY → 80-column fallback), with a genuine width-invariant render so the
    snapshot is identical on any machine regardless of the ambient terminal.
    """
    force_wide_help_console(monkeypatch)


# --- T001: names + per-subcommand params ------------------------------------


def test_registered_command_names_match_frozen_subcommands() -> None:
    # Frozenset-equality subsumes a length check: two equal sets have equal
    # cardinality, and equality also pins the exact names (a stale count would
    # miss a same-size rename/swap that this catches).
    cli = get_command(app)
    assert hasattr(cli, "commands")
    registered = frozenset(cli.commands.keys())
    assert registered == FROZEN_SUBCOMMANDS


def _is_option_param(param: object) -> bool:
    """Return True for option parameters in both click.Option and typer.core.TyperOption.

    Click 8.4+ with Typer uses TyperOption which does not inherit from click.Option
    but has the same duck-typed surface (is_flag, multiple, opts).
    """
    return isinstance(param, click.Option) or (hasattr(param, "is_flag") and hasattr(param, "opts"))


def _option_arity(opt: click.Option) -> str:
    if opt.multiple:
        return "multi"
    if opt.is_flag:
        return "flag"
    return "value"


@pytest.mark.parametrize("name", sorted(FROZEN_SUBCOMMANDS))
def test_subcommand_option_contract(name: str) -> None:
    cli = get_command(app)
    assert hasattr(cli, "commands")
    command = cli.commands[name]
    actual: dict[str, str] = {}
    for param in command.params:
        if _is_option_param(param):
            # The contract pins the long flags only; --help is implicit.
            for flag in param.opts:  # type: ignore[union-attr]
                if flag == "--help":
                    continue
                actual[flag] = _option_arity(param)  # type: ignore[arg-type]
    assert actual == EXPECTED_OPTIONS[name]


# --- T002: per-subcommand --help snapshot ------------------------------------


@pytest.mark.parametrize("name", sorted(FROZEN_SUBCOMMANDS))
def test_subcommand_help_snapshot(name: str, runner: CliRunner) -> None:
    result = runner.invoke(app, [name, "--help"])
    assert result.exit_code == 0
    expected = normalize_help("\n".join(EXPECTED_HELP[name]))
    assert normalize_help(result.output) == expected


# --- T003: exit-code contracts + load-bearing names --------------------------


def test_ops_threshold_without_close_stale_is_bad_parameter(
    runner: CliRunner,
) -> None:
    result = runner.invoke(app, ["ops", "--threshold", "5"])
    # BadParameter surfaces as a usage error (exit code 2) through the CLI.
    assert result.exit_code == 2
    assert "--threshold requires --close-stale" in result.output


def test_skills_name_is_invokable_and_returns_documented_exit_code(
    runner: CliRunner,
) -> None:
    # Load-bearing name (compat safety predicate + __init__ argv fast-path).
    # Outside a project the contract returns 2 (not-in-project); inside, 0/1.
    result = runner.invoke(app, ["skills", "--json"])
    assert result.exit_code in {0, 1, 2}


def test_sparse_checkout_fix_reaches_refusal_or_clean_path(
    runner: CliRunner,
) -> None:
    # Load-bearing name (compat safety predicate). In a non-interactive runner
    # --fix reaches the CI-refusal (non-zero) or clean (0) path, never crashes.
    prior = os.environ.get("CI")
    os.environ["CI"] = "1"
    try:
        result = runner.invoke(app, ["sparse-checkout", "--fix"])
    finally:
        if prior is None:
            os.environ.pop("CI", None)
        else:
            os.environ["CI"] = prior
    assert result.exit_code in {0, 1}
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_public_and_load_bearing_symbols_are_importable() -> None:
    # I-5 anchor: the public surface must remain importable from the shim.
    from specify_cli.cli.commands.doctor import SlashCommandGap as _gap
    from specify_cli.cli.commands.doctor import app as _app

    assert _app is app
    assert _gap is not None


# --- T004: cross-surface name coupling (#2059, GAP 1) ------------------------
#
# FROZEN_SUBCOMMANDS pins the live Typer names, but one OTHER string-keyed
# surface hard-codes a subset of those names and is NOT cross-checked by the
# golden snapshots above: the ``compat.safety_modes`` SAFETY_REGISTRY tuples
# (e.g. ``("doctor", "skills")``, ``("doctor", "sparse-checkout")``).
#
# A rename that updates FROZEN_SUBCOMMANDS + doctor.py but forgets that
# surface silently desyncs: the mode-gate tests monkeypatch sys.argv to the
# hard-coded literal, so they stay green. The test below derives expected
# values from the LIVE app + the real registry symbols (no second copy of
# the literal), so such a rename FAILS here.
#
# (The ``__init__`` argv fast-path predicate and ``cli.commands`` registration
# fast-path predicate for ``restart-daemon`` this comment used to describe
# were removed along with the ``restart-daemon`` subcommand itself, issue #5;
# the remaining fast-path predicate below covers ``skills`` only.)


def _live_doctor_subcommand_names() -> frozenset[str]:
    cli = get_command(app)
    assert hasattr(cli, "commands")
    return frozenset(cli.commands.keys())


def test_safety_registry_doctor_names_are_live_subcommands() -> None:
    """Every ``("doctor", <name>)`` tuple in the safety registry must be a
    live registered subcommand.

    Teeth: rename a doctor subcommand in ``doctor.py`` (which flows into the
    live app + must be mirrored into FROZEN_SUBCOMMANDS) WITHOUT updating
    ``safety_modes.py`` and the stale registered name is no longer live →
    this assertion fails. The mode-gate tests would not catch it because they
    monkeypatch ``sys.argv`` to the hard-coded literal.
    """
    from specify_cli.compat.safety import SAFETY_REGISTRY
    from specify_cli.compat.safety_modes import register_mode_predicates

    # Idempotent; ensures the doctor subcommand tuples are present.
    register_mode_predicates()

    registered_doctor_names = {path[1] for path in SAFETY_REGISTRY if len(path) == 2 and path[0] == "doctor"}
    # Sanity: the registry actually carries the load-bearing names so this
    # test cannot pass vacuously if the registry is ever emptied.
    assert {"skills", "sparse-checkout"} <= registered_doctor_names

    live = _live_doctor_subcommand_names()
    orphaned = registered_doctor_names - live
    assert not orphaned, (
        "safety_modes.py registers doctor subcommand name(s) that are no "
        f"longer live in the Typer app: {sorted(orphaned)}. A subcommand was "
        "renamed in doctor.py without updating compat/safety_modes.py."
    )


def test_init_skills_fast_path_predicate_keys_on_a_live_name() -> None:
    """The ``__init__`` ``doctor skills`` fast-path predicate must recognise
    the LIVE ``skills`` subcommand name.

    Teeth: rename ``skills`` in ``doctor.py`` + FROZEN_SUBCOMMANDS but leave the
    ``args[1] == "skills"`` literal in ``__init__._is_doctor_skills_invocation``
    untouched and this predicate stops matching the live name → fails.
    """
    from specify_cli import _is_doctor_skills_invocation

    live = _live_doctor_subcommand_names()
    assert "skills" in live, "golden contract guarantees a 'skills' subcommand"

    # Build argv from the LIVE name, not a copied literal.
    argv = ["spec-kitty", "doctor", "skills", "--json"]
    assert _is_doctor_skills_invocation(argv) is True
    # Negative control: a different live subcommand must NOT match the
    # skills-specific predicate (proves the predicate keys on the name).
    other = next(name for name in sorted(live) if name != "skills")
    assert _is_doctor_skills_invocation(["spec-kitty", "doctor", other]) is False
