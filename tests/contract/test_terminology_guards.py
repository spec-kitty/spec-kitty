"""CI grep guards for canonical terminology drift.

These guards prevent the Mission Type / Mission / Mission Run terminology
boundary from drifting back to legacy selector vocabulary. They are scoped
to live first-party surfaces only.

Explicitly does not scan:
- `kitty-specs/**` (historical mission artifacts)
- `architecture/**` (historical ADRs and initiative records)
- `.kittify/**` (runtime state)
- `tests/**` (tests legitimately mention forbidden patterns)
- `docs/migrations/**` (migration docs must name deprecated flags)
- historical version sections of `CHANGELOG.md`
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest

pytestmark = [pytest.mark.contract, pytest.mark.fast]
REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# T013 in-scope cluster: the 10 internal command files from which the
# ``--feature`` alias was fully removed (WP01 + WP02).  Any reintroduction
# of the literal ``--feature`` string in these files — whether inside a
# typer.Option block, an alias_flag argument, a resolve_selector call, or
# any other construct — must fail this gate.
# Authority: spec.md FR-003, FR-004.
# ---------------------------------------------------------------------------
INSCOPE_FEATURE_FREE_FILES: tuple[str, ...] = (
    # Original 10 internal command files cleaned in the prior mission (WP01/WP02
    # of release-3-2-0a5-tranche-1).
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
    "src/specify_cli/cli/commands/merge.py",
    "src/specify_cli/cli/commands/next_cmd.py",
    "src/specify_cli/cli/commands/research.py",
    "src/specify_cli/cli/commands/context.py",
    "src/specify_cli/cli/commands/accept.py",
    "src/specify_cli/cli/commands/lifecycle.py",
    "src/specify_cli/cli/commands/mission_type.py",
)

CLI_COMMAND_GLOBS = ("src/specify_cli/cli/commands/**/*.py",)
DOCTRINE_SKILL_GLOBS = ("src/charter/offering/skills/**/*.md",)
AGENT_DOC_GLOBS = ("docs/**/*.md",)
TOP_LEVEL_DOCS = ("README.md", "CONTRIBUTING.md")
# Exemption policy and rationale for each exempt surface:
# docs/development/reference/terminology-exemptions.md
FORBIDDEN_SCAN_ROOTS = (
    "kitty-specs/",
    "architecture/",
    ".kittify/",
    "tests/",
    "docs/migrations/",
    # docs/adr/ holds immutable historical decision records (the common-docs move
    # relocated them from the unscanned architecture/ tree). Their bodies are
    # byte-invariant under C-002/C-006 and legitimately reference era-correct
    # wording (--feature, main-centric workflow). Mirrors the narrow docs/adr/
    # exemption in tests/architectural/test_no_legacy_terminology.py.
    "docs/adr/",
    # Historical/archival sub-areas relocated under docs/plans/ by the common-docs
    # move (the old, unscanned engineering_notes/initiatives world): completed
    # initiative records, retained 1.x deep-dive notes, and engineering notes.
    # These are archival records of era-correct decisions, not live first-party
    # docs — the active planning pages at docs/plans/*.md stay scanned.
    "docs/plans/engineering-notes/",
    "docs/plans/initiatives/",
)


def _glob(pattern: str) -> list[Path]:
    return sorted(REPO_ROOT.glob(pattern))


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _iter_typer_option_blocks(content: str) -> Iterator[tuple[int, str]]:
    """Yield `(offset, block)` tuples for each `typer.Option(...)` call."""
    pattern = re.compile(r"typer\.Option\((?:[^()]|\([^()]*\))*\)", re.DOTALL)
    for match in pattern.finditer(content):
        yield match.start(), match.group(0)


def _extract_help(option_block: str) -> str:
    """Extract the `help=` string from a typer.Option block when present."""
    match = re.search(r'help\s*=\s*"([^"]*)"', option_block)
    if match:
        return match.group(1)
    match = re.search(r"help\s*=\s*'([^']*)'", option_block)
    return match.group(1) if match else ""


def _extract_changelog_unreleased(path: Path) -> str:
    """Return the portion of CHANGELOG.md above the first version heading."""
    content = _read(path)
    match = re.search(r"^## \[\d+\.\d+\.\d+", content, flags=re.MULTILINE)
    if match is None:
        return content
    return content[: match.start()]


def _live_doc_scan_targets() -> list[tuple[Path, str]]:
    """Return live first-party docs that must stay terminology-clean."""
    scan_targets: list[tuple[Path, str]] = []
    for path_pattern in AGENT_DOC_GLOBS:
        for path in _glob(path_pattern):
            relative_path = path.relative_to(REPO_ROOT).as_posix()
            # docs/migrations/, docs/adr/, and the relocated archival sub-areas of
            # docs/plans/ are historical/immutable surfaces, not live first-party
            # docs (docs/adr/ holds byte-invariant ADR records).
            if relative_path.startswith(
                (
                    "docs/migrations/",
                    "docs/adr/",
                    "docs/plans/engineering-notes/",
                    "docs/plans/initiatives/",
                )
            ):
                continue
            # The relocated canonical CHANGELOG is handled like root CHANGELOG.md
            # below (only the Unreleased section is scanned; historical version
            # sections legitimately carry era-correct terminology). Its sibling
            # docs/changelog/index.md stays a normally-scanned live doc.
            if relative_path == "docs/changelog/CHANGELOG.md":
                continue
            scan_targets.append((path, _read(path)))
    for top_level in TOP_LEVEL_DOCS:
        path = REPO_ROOT / top_level
        if path.exists():
            scan_targets.append((path, _read(path)))
    for changelog_path in (REPO_ROOT / "CHANGELOG.md", REPO_ROOT / "docs" / "changelog" / "CHANGELOG.md"):
        if changelog_path.exists():
            scan_targets.append((changelog_path, _extract_changelog_unreleased(changelog_path)))
    return scan_targets


def _surrounding_param_name(content: str, offset: int) -> str:
    """Best-effort extraction of the enclosing parameter name."""
    window = content[max(0, offset - 300):offset]
    matches = list(re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*[^=\n]+=\s*$", window, re.MULTILINE))
    if matches:
        return matches[-1].group(1)
    matches = list(re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*$", window, re.MULTILINE))
    return matches[-1].group(1) if matches else ""


def _is_runtime_session_param(param_name: str) -> bool:
    lowered = param_name.lower()
    return any(token in lowered for token in ("runtime", "session", "run_id", "run"))


def _line_number(content: str, offset: int) -> int:
    return content.count("\n", 0, offset) + 1


def test_no_mission_run_alias_in_tracked_mission_selectors() -> None:
    """Live CLI command files must not declare --mission-run for mission selection.

    Authority: spec.md FR-002, FR-003.
    """
    pattern = re.compile(r"typer\.Option\((?:[^()]|\([^()]*\))*\"--mission-run\"(?:[^()]|\([^()]*\))*\)", re.DOTALL)
    for path_pattern in CLI_COMMAND_GLOBS:
        for path in _glob(path_pattern):
            content = _read(path)
            for match in pattern.finditer(content):
                param_name = _surrounding_param_name(content, match.start())
                if _is_runtime_session_param(param_name):
                    continue
                line = _line_number(content, match.start())
                pytest.fail(
                    f"{path.relative_to(REPO_ROOT)}:{line}: --mission-run used as a tracked-mission selector. "
                    "Authority: spec.md FR-002/FR-003. Fix: use --mission instead."
                )


def test_no_mission_run_slug_help_text_in_cli_commands() -> None:
    """Tracked-mission CLI help text must not say 'Mission run slug'.

    Authority: spec.md FR-008.
    """
    for path_pattern in CLI_COMMAND_GLOBS:
        for path in _glob(path_pattern):
            content = _read(path)
            if "Mission run slug" not in content:
                continue
            line = _line_number(content, content.index("Mission run slug"))
            pytest.fail(
                f"{path.relative_to(REPO_ROOT)}:{line}: contains 'Mission run slug'. "
                "Authority: spec.md FR-008. Fix: say 'Mission slug'."
            )


def test_no_visible_feature_alias_in_cli_commands() -> None:
    """--feature must not appear at all in CLI-command Typer option blocks.

    The alias was fully removed (#1060); it is no longer permitted even as a
    ``hidden=True`` option. This is consistent with
    ``test_zero_feature_flags_exist_cli_wide``.

    Authority: spec.md FR-005 and charter terminology canon.
    """
    for path_pattern in CLI_COMMAND_GLOBS:
        for path in _glob(path_pattern):
            content = _read(path)
            for offset, option_block in _iter_typer_option_blocks(content):
                if '"--feature"' not in option_block:
                    continue
                line = _line_number(content, offset)
                pytest.fail(
                    f"{path.relative_to(REPO_ROOT)}:{line}: --feature declared in a Typer option block. "
                    "Authority: spec.md FR-005 and charter terminology canon. "
                    "Fix: --feature must not appear at all — it was fully removed, not hidden."
                )


def test_no_mission_run_instructions_in_doctrine_skills() -> None:
    """Doctrine skills must teach --mission for tracked-mission selection.

    Authority: spec.md FR-009.
    """
    forbidden_patterns = (
        r"--mission-run\s+\d{3}",
        r"--mission-run\s+<slug>",
        r"--mission-run\s+<mission",
    )
    for path_pattern in DOCTRINE_SKILL_GLOBS:
        for path in _glob(path_pattern):
            content = _read(path)
            for pattern in forbidden_patterns:
                for match in re.finditer(pattern, content):
                    line = _line_number(content, match.start())
                    pytest.fail(
                        f"{path.relative_to(REPO_ROOT)}:{line}: doctrine skill instructs --mission-run. "
                        "Authority: spec.md FR-009. Fix: use --mission."
                    )


def test_no_mission_run_instructions_in_agent_facing_docs() -> None:
    """Live docs must teach --mission for tracked-mission selection.

    Authority: spec.md FR-010 and FR-022.
    """
    forbidden_patterns = (
        r"--mission-run\s+\d{3}",
        r"--mission-run\s+<slug>",
        r"--mission-run\s+<mission",
    )

    for path, content in _live_doc_scan_targets():
        for pattern in forbidden_patterns:
            for match in re.finditer(pattern, content):
                line = _line_number(content, match.start())
                pytest.fail(
                    f"{path.relative_to(REPO_ROOT)}:{line}: doc instructs --mission-run. "
                    "Authority: spec.md FR-010/FR-022. Fix: use --mission."
                )


def test_no_feature_flag_in_live_first_party_docs() -> None:
    """Live docs must not document --feature as a live CLI option.

    Authority: spec.md FR-005, FR-022, and the charter terminology canon.
    """
    forbidden_patterns = (
        r"--feature\s+<slug>",
        r"--feature\s+\d{3}",
        r"--feature\s+[a-z][a-z0-9-]*",
        r"\|\s*`--feature[\s|<>`]",
    )

    for path, content in _live_doc_scan_targets():
        for pattern in forbidden_patterns:
            for match in re.finditer(pattern, content):
                line = _line_number(content, match.start())
                snippet = content[max(0, match.start() - 25):match.end() + 25]
                pytest.fail(
                    f"{path.relative_to(REPO_ROOT)}:{line}: documents --feature as a live CLI option: {snippet!r}. "
                    "Authority: spec.md FR-005/FR-022 and charter terminology canon. "
                    "Fix: use --mission or link to docs/migrations/feature-flag-deprecation.md."
                )


def test_no_removed_orchestrator_api_command_names_in_live_docs() -> None:
    """Live docs must not teach removed host orchestrator-api subcommands.

    Authority: spec.md FR-010, FR-022.
    """
    forbidden_patterns = (
        r"spec-kitty orchestrator-api feature-state\b",
        r"spec-kitty orchestrator-api accept-feature\b",
        r"spec-kitty orchestrator-api merge-feature\b",
    )
    for path, content in _live_doc_scan_targets():
        for pattern in forbidden_patterns:
            for match in re.finditer(pattern, content):
                line = _line_number(content, match.start())
                pytest.fail(
                    f"{path.relative_to(REPO_ROOT)}:{line}: doc teaches removed orchestrator-api command. "
                    "Authority: spec.md FR-010/FR-022. Fix: use mission-state/accept-mission/merge-mission."
                )


def test_orchestrator_api_docs_do_not_teach_removed_json_flag_or_unpinned_provider_source() -> None:
    """Live docs must not teach host/provider patterns known to fail today.

    Authority: orchestrator-api JSON-default contract and host/provider
    compatibility boundary.
    """
    forbidden_patterns = (
        r"spec-kitty orchestrator-api[^\n]*--json",
        r"--json[^\n]*spec-kitty orchestrator-api",
        r"git\+https://github\.com/spec-kitty/spec-kitty-orchestrator\.git",
    )
    for path, content in _live_doc_scan_targets():
        for pattern in forbidden_patterns:
            for match in re.finditer(pattern, content):
                line = _line_number(content, match.start())
                pytest.fail(
                    f"{path.relative_to(REPO_ROOT)}:{line}: doc teaches an incompatible orchestrator provider pattern. "
                    "Fix: orchestrator-api output is JSON by default and provider installs must be pinned to a compatible build."
                )


def test_no_mission_used_to_mean_mission_type_in_cli_commands() -> None:
    """CLI command files must not declare --mission with mission-type semantics.

    Authority: spec.md FR-021.
    """
    for path_pattern in CLI_COMMAND_GLOBS:
        for path in _glob(path_pattern):
            content = _read(path)
            for offset, option_block in _iter_typer_option_blocks(content):
                if '"--mission"' not in option_block:
                    continue
                help_text = _extract_help(option_block).lower()
                if "mission type" not in help_text and "mission key" not in help_text:
                    continue
                if '"--mission-type"' in option_block:
                    continue
                line = _line_number(content, offset)
                pytest.fail(
                    f"{path.relative_to(REPO_ROOT)}:{line}: --mission declared with mission-type semantics. "
                    "Authority: spec.md FR-021. Fix: use --mission-type as canonical and keep --mission only as a hidden alias."
                )


def test_reference_examples_match_runtime_requirements() -> None:
    """Reference docs must not teach invocation patterns that now hard-fail.

    Authority: spec.md FR-010, FR-013, FR-022.
    """

    cli_reference = _read(REPO_ROOT / "docs/api/cli-commands.md")
    assert "spec-kitty next --json" not in cli_reference
    assert "bare call (no `--agent`)" not in cli_reference

    agent_reference = _read(REPO_ROOT / "docs/api/agent-subcommands.md")
    forbidden_example_lines = (
        r"^spec-kitty agent mission accept$",
        r"^spec-kitty agent mission accept --json$",
        r"^spec-kitty agent tasks mark-status T001 --status done$",
        r"^spec-kitty agent tasks status$",
        r"^spec-kitty agent tasks status --json$",
        r"^spec-kitty agent tasks list-tasks --json$",
        r"^spec-kitty agent tasks list-tasks --lane doing --json$",
        r"^spec-kitty agent tasks add-history WP01 --note \"Completed implementation\" --json$",
        r"^spec-kitty agent tasks finalize-tasks --json$",
        r"^spec-kitty agent tasks map-requirements --wp WP04 --refs FR-001,FR-002$",
        r"^spec-kitty agent tasks map-requirements --batch '\{\"WP01\":\[\"FR-001\"\],\"WP02\":\[\"FR-003\"\]\}' --json$",
        r"^spec-kitty agent tasks map-requirements --wp WP01 --refs FR-005 --replace$",
        r"^spec-kitty agent tasks validate-workflow WP01 --json$",
        r"^spec-kitty agent tasks list-dependents WP13$",
        r"^spec-kitty agent action implement WP01 --agent claude$",
        r"^spec-kitty agent action implement WP02 --agent claude$",
        r"^spec-kitty agent action implement --agent gemini$",
        r"^spec-kitty agent action review WP01 --agent claude$",
        r"^spec-kitty agent action review --agent gemini$",
        r"^spec-kitty agent status emit WP01 --to claimed --actor claude$",
        r"^spec-kitty agent status materialize$",
        r"^spec-kitty agent status materialize --json$",
        r"^spec-kitty agent status doctor$",
        r"^spec-kitty agent status doctor --stale-claimed-days 3 --json$",
        r"^spec-kitty agent status validate$",
        r"^spec-kitty agent status validate --json$",
        r"^spec-kitty agent status reconcile --dry-run$",
    )
    for pattern in forbidden_example_lines:
        assert re.search(pattern, agent_reference, flags=re.MULTILINE) is None


def test_no_main_branch_workflow_language_in_live_docs_and_skills() -> None:
    """Live docs and doctrine skills must not teach generic main-branch workflow rules.

    Authority: charter branch-intent terminology governance and spec.md FR-022.
    """

    forbidden_patterns = (
        r"planning happens in `main`",
        r"planning happens in main\b",
        r"task generation happens in main\b",
        r"merge to `main`",
        r"merge to main\b",
        r"run from the main repository root",
        r"from the main repository root",
    )

    scan_targets = _live_doc_scan_targets()
    for path_pattern in DOCTRINE_SKILL_GLOBS:
        for path in _glob(path_pattern):
            scan_targets.append((path, _read(path)))

    for path, content in scan_targets:
        relative = path.relative_to(REPO_ROOT)
        for pattern in forbidden_patterns:
            for match in re.finditer(pattern, content, flags=re.IGNORECASE):
                line = _line_number(content, match.start())
                pytest.fail(
                    f"{relative}:{line}: teaches deprecated main-centric workflow wording. "
                    "Fix: distinguish repository root checkout from explicit branch intent."
                )


def test_orchestrator_api_envelope_width_unchanged() -> None:
    """The orchestrator-api envelope must remain the canonical 7-key shape.

    Authority: spec.md C-010.
    """
    from specify_cli.orchestrator_api.envelope import make_envelope

    envelope = make_envelope("test-cmd", success=True, data={})
    expected_keys = {
        "contract_version",
        "command",
        "timestamp",
        "correlation_id",
        "success",
        "error_code",
        "data",
    }
    assert set(envelope.keys()) == expected_keys, (
        f"Orchestrator-api envelope keys must remain exactly {expected_keys}; got {set(envelope.keys())}. "
        "Authority: spec.md C-010."
    )
    assert len(envelope) == 7, (
        f"Orchestrator-api envelope must remain exactly 7 keys; got {len(envelope)}. "
        "Authority: spec.md C-010."
    )


def test_grep_guards_do_not_scan_historical_artifacts() -> None:
    """Verify the grep guard scope excludes historical artifacts.

    Authority: spec.md FR-022 and C-011.
    """
    for group in (CLI_COMMAND_GLOBS, DOCTRINE_SKILL_GLOBS, AGENT_DOC_GLOBS):
        for pattern in group:
            normalized = pattern.replace("\\", "/")
            for forbidden in FORBIDDEN_SCAN_ROOTS:
                assert forbidden not in normalized, (
                    f"Guard scan pattern {pattern!r} must not target {forbidden!r}. "
                    "Authority: spec.md FR-022/C-011."
                )

    assert "CHANGELOG.md" not in AGENT_DOC_GLOBS, (
        "CHANGELOG.md must be handled through _extract_changelog_unreleased(), not a raw glob. "
        "Authority: spec.md FR-022."
    )


def test_docs_adr_exemption_is_narrow() -> None:
    """docs/adr/ is exempt (immutable historical ADRs), but the rest of docs/ is not.

    The common-docs move relocated ADRs from the unscanned architecture/ tree into
    docs/adr/. Their byte-invariant bodies legitimately carry era-correct wording,
    so they must not be scanned — but the exemption must stay narrow: every other
    docs/ page is still a live first-party surface. This pins both halves so a future
    glob change cannot silently widen the carve-out to all of docs/.
    """
    scanned = {p.relative_to(REPO_ROOT).as_posix() for p, _ in _live_doc_scan_targets()}
    assert not any(p.startswith("docs/adr/") for p in scanned), (
        "docs/adr/ ADR records must be excluded from the live-docs terminology scan"
    )
    # Non-vacuity / narrowness: live docs/ pages outside the exempt roots ARE scanned.
    assert any(
        p.startswith("docs/")
        and not p.startswith(("docs/adr/", "docs/migrations/"))
        for p in scanned
    ), "the exemption widened too far — no live docs/ page is being scanned"


def test_no_feature_alias_in_internal_command_cluster() -> None:
    """The in-scope internal command cluster must contain zero occurrences of ``--feature``.

    This gate complements ``test_no_visible_feature_alias_in_cli_commands``
    (which forbids ``--feature`` in any Typer Option block) by scanning the
    in-scope files for ANY ``--feature`` literal, not just option declarations.
    The WP01/WP02 removals eliminated the alias entirely from these 10 files.
    ANY reintroduction
    — whether inside a typer.Option call, an ``alias_flag="--feature"`` argument,
    a ``resolve_selector(... "--feature" ...)`` call, or a stray comment-free
    string literal — must fail this gate.

    Authority: spec.md FR-003, FR-004.  Defined by INSCOPE_FEATURE_FREE_FILES.
    """
    offenders: list[str] = []
    for rel_path in INSCOPE_FEATURE_FREE_FILES:
        path = REPO_ROOT / rel_path
        if not path.exists():
            pytest.fail(
                f"In-scope file not found: {rel_path}. "
                "Update INSCOPE_FEATURE_FREE_FILES or restore the file."
            )
        content = _read(path)
        if "--feature" in content:
            # Report each hit with line number for fast triage
            for lineno, line in enumerate(content.splitlines(), start=1):
                if "--feature" in line:
                    offenders.append(f"{rel_path}:{lineno}: {line.strip()!r}")
    assert not offenders, (
        "FR-003/FR-004 regression: '--feature' literal found in in-scope command files "
        "(INSCOPE_FEATURE_FREE_FILES).  Remove the alias entirely — do not hide it.\n  "
        + "\n  ".join(offenders)
    )


@pytest.mark.fast
def test_terminology_exemption_policy_doc_is_present_and_consistent() -> None:
    """The exemption policy doc exists, is referenced from this file, and covers all three exemptions.

    Confirms that the policy rationale captured in the comment above
    FORBIDDEN_SCAN_ROOTS is also reflected in a human-readable policy document,
    and that both the document and this test agree on the three exempt surfaces.

    Authority: FR-013 (policy doc linked from the guard test).
    """
    policy_doc = REPO_ROOT / "docs" / "development" / "reference" / "terminology-exemptions.md"
    assert policy_doc.exists(), (
        "docs/development/reference/terminology-exemptions.md must exist. "
        "Authority: FR-013. The exemption policy must be documented in a human-readable form."
    )

    # This guard test must reference the policy doc by its canonical path so
    # a reader can navigate from the exemption comment to the full rationale.
    guard_source = Path(__file__).read_text(encoding="utf-8")
    assert "docs/development/terminology-exemptions.md" in guard_source, (
        "test_terminology_guards.py must reference docs/development/terminology-exemptions.md. "
        "Authority: FR-013. The link must appear in the guard test itself."
    )

    # The policy doc must cover ALL four exempt surfaces in FORBIDDEN_SCAN_ROOTS.
    # Each token is a substring that must appear in the document to confirm
    # coverage — keeps the doc honest if a future exemption is added/dropped.
    policy_content = policy_doc.read_text(encoding="utf-8")
    required_tokens = (
        "docs/adr/",
        "docs/migrations/",
        "docs/plans/engineering-notes/",
        "Unreleased",
    )
    for token in required_tokens:
        assert token in policy_content, (
            f"docs/development/terminology-exemptions.md must contain exemption token {token!r}. "
            "Authority: FR-013. All four exempt surfaces must be documented."
        )
