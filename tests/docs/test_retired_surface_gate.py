"""The retired-surface gate over the published living pages (#7520).

A published living page (the published set minus ``adr/``, ``plans/``, ``reports/``,
``changelog/`` and ``archive/``) must not newly name a retired surface. The retired set
has one authority, :mod:`scripts.retired_surfaces`, which the code gate
``tests/architectural/test_no_retired_subsystems.py`` reads too. Existing hits are a
tracked burn-down, ``scripts/docs/retired_surface_burndown.yaml``: each entry names the
section sub-issue (#7522-#7528) that drains it, a stale entry fails like a new hit, and
the entry count is a shrink-only size ratchet in ``tests/architectural/_baselines.yaml``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts import retired_surfaces
from scripts.docs import retired_surface_gate as gate
from scripts.docs.staleness_audit import section_issue

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DOCS = _REPO_ROOT / "docs"

#: The (page, surface) pairs the burn-down held when the gate landed (#7520). Entries may only
#: leave: a pair outside this set is a refill (a swap, or a re-addition after a fix) and fails.
_LANDING_PAIRS: frozenset[tuple[str, str]] = frozenset(
    {
        ("api/batch-api-contract.md", "spec-kitty auth"),
        ("api/batch-api-contract.md", "src/specify_cli/delivery"),
        ("api/batch-api-contract.md", "src/specify_cli/sync"),
        ("api/batch-api-contract.md", "src/specify_cli/tracker/saas_service.py"),
        ("api/configuration.md", "Zeitgeist"),
        ("api/configuration.md", "spec-kitty moments"),
        ("api/environment-variables.md", "spec-kitty merge"),
        ("api/file-structure.md", "/spec-kitty.merge"),
        ("api/skills/spk-gate-mission-review.md", "spec-kitty merge"),
        ("architecture/00_landscape/README.md", "Zeitgeist"),
        ("architecture/00_landscape/README.md", "saas_client"),
        ("architecture/00_landscape/README.md", "spec-kitty dashboard"),
        ("architecture/00_landscape/README.md", "src/doctrine"),
        ("architecture/00_landscape/README.md", "src/specify_cli/dashboard"),
        ("architecture/04_implementation_mapping/README.md", "Zeitgeist"),
        ("architecture/04_implementation_mapping/README.md", "saas_client"),
        ("architecture/04_implementation_mapping/README.md", "src/specify_cli/dashboard"),
        ("architecture/04_implementation_mapping/README.md", "src/specify_cli/saas"),
        ("architecture/05_ownership_map.md", "Zeitgeist"),
        ("architecture/05_ownership_map.md", "saas_client"),
        ("architecture/05_ownership_map.md", "src/doctrine"),
        ("architecture/05_ownership_map.md", "src/specify_cli/saas"),
        ("architecture/05_ownership_map.md", "src/specify_cli/sync"),
        ("architecture/README.md", "Zeitgeist"),
        ("architecture/diagrams/01_context/README.md", "Zeitgeist"),
        ("architecture/diagrams/01_context/README.md", "saas_client"),
        ("architecture/diagrams/02_containers/README.md", "Zeitgeist"),
        ("architecture/diagrams/02_containers/runtime-execution-domain.md", "Zeitgeist"),
        ("architecture/documentation-mission.md", "/spec-kitty.merge"),
        ("architecture/mission-type-resolution.md", "src/doctrine"),
        ("architecture/vision/README.md", "Zeitgeist"),
        ("architecture/vision/README.md", "saas_client"),
        ("context/README.md", "Zeitgeist"),
        ("context/identity.md", "saas_client"),
        ("context/identity.md", "src/specify_cli/egress.py"),
        ("context/identity.md", "src/specify_cli/tracker/saas_client.py"),
        ("context/orchestration.md", "Zeitgeist"),
        ("context/orchestration.md", "spec-kitty merge"),
        ("context/orchestration.md", "src/specify_cli/auth"),
        ("context/orchestration.md", "src/specify_cli/delivery"),
        ("context/orchestration.md", "src/specify_cli/sync"),
        ("context/product-lines.md", "Zeitgeist"),
        ("context/team-kitty.md", "Zeitgeist"),
        ("context/team-kitty.md", "saas_client"),
        ("context/team-kitty.md", "spec-kitty sync"),
        ("context/team-kitty.md", "src/specify_cli/sync"),
        ("development/agent-fleet.md", "Zeitgeist"),
        ("development/how-to/manage-issue-tracker.md", "Zeitgeist"),
        ("development/how-to/manage-issue-tracker.md", "saas_client"),
        ("development/how-to/review-gates.md", "src/doctrine"),
        ("development/testing/testing-parallel.md", "src/specify_cli/cli/commands/sync.py"),
        ("guides/how-to/collaboration/run-an-autonomous-mission.md", "spec-kitty merge"),
        ("guides/how-to/governance/use-retrospective-learning.md", "spec-kitty merge"),
        ("guides/how-to/harnesses/amazon-q.md", "/spec-kitty.merge"),
        ("guides/how-to/harnesses/augment.md", "/spec-kitty.merge"),
        ("guides/how-to/harnesses/claude-code.md", "/spec-kitty.merge"),
        ("guides/how-to/harnesses/copilot.md", "/spec-kitty.merge"),
        ("guides/how-to/harnesses/cursor.md", "/spec-kitty.merge"),
        ("guides/how-to/harnesses/gemini.md", "/spec-kitty.merge"),
        ("guides/how-to/harnesses/kilocode.md", "/spec-kitty.merge"),
        ("guides/how-to/harnesses/opencode.md", "/spec-kitty.merge"),
        ("guides/how-to/harnesses/qwen.md", "/spec-kitty.merge"),
        ("guides/how-to/harnesses/setup-lint-hooks.md", "spec-kitty live-work"),
        ("guides/how-to/harnesses/windsurf.md", "/spec-kitty.merge"),
        ("guides/how-to/installation/install-spec-kitty.md", "/spec-kitty.merge"),
        ("guides/how-to/missions/accept-and-merge.md", "/spec-kitty.merge"),
        ("guides/how-to/missions/keep-main-clean.md", "spec-kitty merge"),
        ("guides/how-to/missions/merge-mission.md", "spec-kitty merge"),
        ("guides/how-to/monitoring/use-dashboard.md", "/spec-kitty.dashboard"),
        ("guides/how-to/monitoring/use-dashboard.md", "spec-kitty dashboard"),
        ("guides/how-to/recovery/recover-from-implementation-crash.md", "spec-kitty merge"),
        ("guides/how-to/scenarios/agency-client-demo.md", "/spec-kitty.merge"),
        ("guides/how-to/scenarios/claude-cursor-collaboration.md", "/spec-kitty.merge"),
        ("guides/how-to/scenarios/multi-agent-mission-development.md", "/spec-kitty.merge"),
        ("guides/how-to/scenarios/parallel-implementation-tracking.md", "/spec-kitty.merge"),
        ("guides/how-to/scenarios/research-mission-example.md", "/spec-kitty.merge"),
        ("guides/how-to/scenarios/solo-developer-workflow.md", "/spec-kitty.merge"),
        ("guides/how-to/scenarios/worktree-parallel-missions.md", "/spec-kitty.merge"),
        ("guides/tutorials/claude-code-integration.md", "/spec-kitty.merge"),
        ("guides/tutorials/claude-code-workflow.md", "/spec-kitty.merge"),
        ("guides/tutorials/claude-code-workflow.md", "spec-kitty merge"),
        ("guides/tutorials/your-first-mission.md", "/spec-kitty.merge"),
        ("guides/tutorials/your-first-mission.md", "spec-kitty merge"),
        ("migrations/charter-pack-cutover.md", "spec-kitty live-work"),
        ("migrations/from-charter-2x.md", "src/doctrine"),
        ("migrations/relocate-builtin-doctrine-packs.md", "src/doctrine"),
        ("migrations/tracker-egress-refusal.md", "spec-kitty sync"),
        ("operations/manual-test-plan.md", "spec-kitty auth"),
        ("operations/manual-test-plan.md", "spec-kitty merge"),
    }
)


# --- One authority --------------------------------------------------------------


def test_the_code_gate_reads_the_one_retired_list() -> None:
    from tests.architectural import test_no_retired_subsystems as code_gate

    assert code_gate._RETIRED_PATHS is retired_surfaces.RETIRED_PATHS
    assert code_gate._RETIRED_CLI_PREFIXES is retired_surfaces.RETIRED_CLI_PREFIXES


def test_every_retired_source_path_and_command_is_a_docs_surface() -> None:
    ids = {surface.id for surface in retired_surfaces.docs_retired_surfaces()}
    source_paths = {path for path in retired_surfaces.RETIRED_PATHS if path.startswith("src/")}
    assert source_paths, "non-vacuity: the retired list names source paths"
    assert source_paths <= ids
    commands = {"spec-kitty " + " ".join(prefix) for prefix in retired_surfaces.RETIRED_CLI_PREFIXES}
    assert commands <= ids


@pytest.mark.parametrize(
    "surface_id",
    ["src/doctrine", "src/specify_cli/glossary", "spec-kitty merge", "Blacksmith", "Zeitgeist", "saas_client", "spec-kitty auth"],
)
def test_the_documentation_retirements_are_named(surface_id: str) -> None:
    assert surface_id in {surface.id for surface in retired_surfaces.docs_retired_surfaces()}


def test_every_surface_says_what_retired_it() -> None:
    for surface in retired_surfaces.docs_retired_surfaces():
        assert surface.retired_by.strip(), surface.id


# --- Matching -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "surface_id"),
    [
        ("See `src/doctrine/directives/` for the old layout.", "src/doctrine"),
        ("Run `spec-kitty merge --mission x`.", "spec-kitty merge"),
        ("The Blacksmith producer built every PR.", "Blacksmith"),
        ("The bundled zeitgeist_client talks to it.", "Zeitgeist"),
        ("import specify_cli.sync.daemon", "src/specify_cli/sync"),
        ("Run `spec-kitty sync now`.", "spec-kitty sync"),
        ("The glossary lived in src/specify_cli/glossary/.", "src/specify_cli/glossary"),
    ],
)
def test_a_retired_surface_is_found(line: str, surface_id: str) -> None:
    assert surface_id in gate.surfaces_named(line)


@pytest.mark.parametrize(
    "line",
    [
        "Run `spec-kitty merge-driver-event-log` in the hook.",
        "Run `spec-kitty charter sync` after editing the charter.",
        "Run `spec-kitty tracker sync publish`.",
        "Offering content lives in `src/charter/offering/doctrine-kinds.md`.",
        "The glossary pipeline is `src/glossary/`.",
        "Run `spec-kitty consolidate`.",
    ],
)
def test_a_live_identifier_is_not_a_hit(line: str) -> None:
    assert gate.surfaces_named(line) == {}


# --- Retired slash commands ------------------------------------------------------------


def test_the_retired_slash_commands_are_the_historical_ones_no_longer_installed() -> None:
    """Source of truth: every ``spec-kitty.<cmd>.md`` ever written, minus the commands installed today."""
    from specify_cli.skills.command_installer import CANONICAL_COMMANDS
    from specify_cli.upgrade.migrations.m_4_0_0rc8_retire_antigravity_workflows import HISTORICAL_COMMANDS

    assert set(retired_surfaces.RETIRED_SLASH_COMMANDS) == set(HISTORICAL_COMMANDS) - set(CANONICAL_COMMANDS)
    ids = {surface.id for surface in retired_surfaces.docs_retired_surfaces()}
    assert {f"/spec-kitty.{command}" for command in retired_surfaces.RETIRED_SLASH_COMMANDS} <= ids


@pytest.mark.parametrize(
    ("line", "surface_id"),
    [
        ("Run `/spec-kitty.merge` when the Mission is accepted.", "/spec-kitty.merge"),
        ("The command file is `.claude/commands/spec-kitty.merge.md`.", "/spec-kitty.merge"),
        ("Open the board with /spec-kitty.dashboard.", "/spec-kitty.dashboard"),
        ("Run `/spec-kitty.constitution` first.", "/spec-kitty.constitution"),
    ],
)
def test_a_retired_slash_command_is_found(line: str, surface_id: str) -> None:
    assert surface_id in gate.surfaces_named(line)


@pytest.mark.parametrize(
    "line",
    [
        "Run `/spec-kitty.consolidate` when the Mission is accepted.",
        "The command file is `.claude/commands/spec-kitty.charter.md`.",
        "Run `/spec-kitty.tasks-finalize`.",
    ],
)
def test_a_live_slash_command_is_not_a_hit(line: str) -> None:
    assert gate.surfaces_named(line) == {}


def test_a_planted_slash_command_fails_the_gate(docs: Path) -> None:
    _page(docs, "guides/clean.md", "Run `spec-kitty consolidate`.\nOr `/spec-kitty.merge`.\n")

    assert [finding.split(" (")[0] for finding in gate.check(docs, _BURNDOWN)] == ["NEW guides/clean.md:9: names retired surface '/spec-kitty.merge'"]


def test_hits_carry_their_line_numbers() -> None:
    assert gate.surfaces_named("ok\nRun spec-kitty merge.\nand spec-kitty merge again\n") == {"spec-kitty merge": [2, 3]}


# --- The gate over a tree ---------------------------------------------------------


def _page(root: Path, rel: str, body: str, status: str = "active") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\ntitle: t\ndescription: d\ndoc_status: {status}\nkind: How-To\nupdated: '2026-01-01T00:00:00Z'\n---\n{body}", encoding="utf-8")


@pytest.fixture
def docs(tmp_path: Path) -> Path:
    root = tmp_path / "docs"
    _page(root, "README.md", "# Home\n")
    _page(root, "guides/old.md", "Run `spec-kitty merge`.\n")
    _page(root, "guides/clean.md", "Run `spec-kitty consolidate`.\n")
    _page(root, "guides/wip.md", "Run `spec-kitty merge`.\n", status="draft")
    _page(root, "plans/history.md", "The Blacksmith producer.\n")
    _page(root, "adr/4.x/2026-01-01-1-x.md", "The Blacksmith producer.\n")
    return root


_BURNDOWN = [gate.BurnDownEntry(page="guides/old.md", surfaces=("spec-kitty merge",), issue="#7523")]


def test_a_tree_whose_hits_are_all_burned_down_passes(docs: Path) -> None:
    assert gate.check(docs, _BURNDOWN) == []


def test_a_new_hit_on_a_living_page_fails_naming_page_and_surface(docs: Path) -> None:
    _page(docs, "guides/clean.md", "Run `spec-kitty consolidate`.\nNot `spec-kitty merge`.\n")

    findings = gate.check(docs, _BURNDOWN)

    assert findings == ["NEW guides/clean.md:9: names retired surface 'spec-kitty merge' (retired: #3080: renamed to spec-kitty consolidate)"]


def test_a_second_surface_on_a_burned_down_page_is_new(docs: Path) -> None:
    _page(docs, "guides/old.md", "Run `spec-kitty merge`.\nThe Blacksmith producer.\n")

    assert [finding.split(":")[0] for finding in gate.check(docs, _BURNDOWN)] == ["NEW guides/old.md"]


def test_a_burn_down_entry_with_no_hit_left_is_stale(docs: Path) -> None:
    _page(docs, "guides/old.md", "Run `spec-kitty consolidate`.\n")

    assert gate.check(docs, _BURNDOWN) == ["STALE guides/old.md: 'spec-kitty merge' is no longer named; remove it from the burn-down (#7523)"]


def test_history_and_unpublished_pages_are_not_checked(docs: Path) -> None:
    assert set(gate.scan(docs)) == {"guides/old.md"}


def test_main_exits_one_on_a_finding(docs: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    burndown = tmp_path / "burndown.yaml"
    burndown.write_text("kind: retired-surface-burndown\nversion: 1\nentries: []\n", encoding="utf-8")

    baselines = tmp_path / "_baselines.yaml"
    baselines.write_text("test_retired_surface_gate:\n  burn_down: 0\n", encoding="utf-8")

    assert gate.main(["--docs-root", str(docs), "--burndown", str(burndown), "--baselines", str(baselines)]) == 1
    assert "NEW guides/old.md:8" in capsys.readouterr().err


# --- The committed burn-down ---------------------------------------------------------


def test_the_living_pages_pass_the_gate() -> None:
    findings = gate.check(_DOCS, gate.load_burndown(gate.DEFAULT_BURNDOWN))
    assert findings == [], "\n".join(findings)


def test_every_burn_down_entry_names_its_section_issue() -> None:
    entries = gate.load_burndown(gate.DEFAULT_BURNDOWN)
    assert entries, "non-vacuity: today's living pages still name retired surfaces"
    for entry in entries:
        assert entry.issue == section_issue(entry.page), entry
        assert entry.issue in {"#7522", "#7523", "#7524", "#7525", "#7526", "#7527", "#7528"}


def test_the_ratcheted_size_is_the_number_of_burned_down_pairs() -> None:
    entries = gate.load_burndown(gate.DEFAULT_BURNDOWN)
    assert len(gate.BURN_DOWN) == sum(len(entry.surfaces) for entry in entries)


def test_load_refuses_an_unknown_shape(tmp_path: Path) -> None:
    path = tmp_path / "b.yaml"
    path.write_text("kind: something-else\nversion: 1\nentries: []\n", encoding="utf-8")
    with pytest.raises(gate.BurnDownError):
        gate.load_burndown(path)


def test_the_burn_down_only_shrinks_from_its_landing_set() -> None:
    assert gate.refilled(gate.BURN_DOWN, _LANDING_PAIRS) == []


def test_a_swapped_or_re_added_pair_is_a_refill() -> None:
    fixed = set(_LANDING_PAIRS) - {min(_LANDING_PAIRS)}
    assert gate.refilled(frozenset(fixed), _LANDING_PAIRS) == []  # shrinking is allowed
    swapped = frozenset({*fixed, ("guides/README.md", "spec-kitty merge")})
    assert gate.refilled(swapped, _LANDING_PAIRS) == [("guides/README.md", "spec-kitty merge")]


# --- Leaving is one-way: the live count equals the recorded baseline ----------------------------


def test_the_burn_down_count_equals_its_baseline() -> None:
    """The one authority for the count is ``tests/architectural/_baselines.yaml`` (test_retired_surface_gate.burn_down)."""
    assert gate.baseline_findings(gate.BURN_DOWN, gate.load_baseline(gate.DEFAULT_BASELINES)) == []


def test_a_drained_pair_lowers_the_baseline_and_cannot_come_back() -> None:
    drained = min(_LANDING_PAIRS)
    after_drain = frozenset(_LANDING_PAIRS - {drained})
    baseline = len(_LANDING_PAIRS)

    # Draining without lowering the baseline fails and says to lower it.
    (finding,) = gate.baseline_findings(after_drain, baseline)
    assert "lower" in finding and "_baselines.yaml" in finding
    # Draining with the baseline lowered in the same pull request is clean.
    lowered = baseline - 1
    assert gate.baseline_findings(after_drain, lowered) == []
    # Putting the drained pair back exceeds the lowered baseline and fails.
    readded = frozenset({*after_drain, drained})
    assert gate.refilled(readded, _LANDING_PAIRS) == []  # the subset check alone would miss it
    (finding,) = gate.baseline_findings(readded, lowered)
    assert "above" in finding


def test_main_reports_a_baseline_mismatch(docs: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    burndown = tmp_path / "burndown.yaml"
    burndown.write_text(
        "kind: retired-surface-burndown\nversion: 1\nentries:\n  - {page: guides/old.md, issue: '#7523', surfaces: [spec-kitty merge]}\n",
        encoding="utf-8",
    )
    baselines = tmp_path / "_baselines.yaml"
    baselines.write_text("test_retired_surface_gate:\n  burn_down: 2\n", encoding="utf-8")

    assert gate.main(["--docs-root", str(docs), "--burndown", str(burndown), "--baselines", str(baselines)]) == 1
    err = capsys.readouterr().err
    assert "BASELINE" in err
    assert "_baselines.yaml" in err


# --- Frontmatter, wording and the burn-down file's shape -----------------------------------


def test_a_published_title_or_description_is_scanned_too(docs: Path) -> None:
    """``title`` and ``description`` are published, so a retired surface there is a hit (file line numbers)."""
    path = docs / "guides" / "clean.md"
    path.write_text(path.read_text(encoding="utf-8").replace("title: t", "title: Run spec-kitty merge"), encoding="utf-8")

    assert [finding.split(" (")[0] for finding in gate.check(docs, _BURNDOWN)] == ["NEW guides/clean.md:2: names retired surface 'spec-kitty merge'"]


def test_other_frontmatter_keys_are_not_scanned(docs: Path) -> None:
    path = docs / "guides" / "clean.md"
    path.write_text(path.read_text(encoding="utf-8").replace("kind: How-To", "kind: How-To\nexternal_note: spec-kitty merge"), encoding="utf-8")

    assert gate.check(docs, _BURNDOWN) == []


def test_a_code_list_surface_says_there_is_no_replacement(docs: Path) -> None:
    _page(docs, "guides/clean.md", "The `specify_cli.sync` package.\n")

    (finding,) = gate.check(docs, _BURNDOWN)

    assert "no replacement" in finding
    assert "retired by removed" not in finding


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("entries: {}\n", "entries must be a list"),
        ("entries: [3]\n", "entries[0] must be a mapping"),
        ("entries:\n  - page: a.md\n    issue: '#7523'\n", "needs a page, an issue and a non-empty surfaces list"),
        ("entries:\n  - page: a.md\n    issue: '#7523'\n    surfaces: []\n", "needs a page, an issue and a non-empty surfaces list"),
        (
            "entries:\n  - {page: a.md, issue: '#7523', surfaces: [x]}\n  - {page: a.md, issue: '#7523', surfaces: [y]}\n",
            "duplicate page a.md",
        ),
    ],
)
def test_load_refuses_a_malformed_burn_down(tmp_path: Path, body: str, message: str) -> None:
    path = tmp_path / "b.yaml"
    path.write_text("kind: retired-surface-burndown\nversion: 1\n" + body, encoding="utf-8")
    with pytest.raises(gate.BurnDownError, match=re.escape(message)):
        gate.load_burndown(path)


def test_a_folded_description_is_read_whole(docs: Path) -> None:
    """A ``>-`` value is read through the YAML loader, so a mention split across lines is found."""
    path = docs / "guides" / "clean.md"
    path.write_text(
        path.read_text(encoding="utf-8").replace("description: d", "description: >-\n  Run spec-kitty\n  merge to land it."),
        encoding="utf-8",
    )

    assert [finding.split(" (")[0] for finding in gate.check(docs, _BURNDOWN)] == ["NEW guides/clean.md:3: names retired surface 'spec-kitty merge'"]
