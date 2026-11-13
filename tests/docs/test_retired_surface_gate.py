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

# --- One authority --------------------------------------------------------------


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


def test_a_surface_without_a_retired_by_note_is_refused() -> None:
    with pytest.raises(ValueError, match="must say what retired it"):
        retired_surfaces.RetiredSurface(id="x", pattern=re.compile("x"), retired_by="  ")


def test_every_surface_says_what_retired_it() -> None:
    for surface in retired_surfaces.docs_retired_surfaces():
        assert surface.retired_by.strip(), surface.id


# --- Matching -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "surface_id"),
    [
        ("See `src/doctrine/directives/` for the old layout.", "src/doctrine"),
        ("Run `spec-kitty merge --mission x`.", "spec-kitty merge"),
        ("jobs run with `runs-on: blacksmith-4vcpu-ubuntu-2404`.", "Blacksmith"),
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
        "The Zeitgeist relay and the Blacksmith producer were retired (#6164, #3995).",
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
    _page(root, "plans/history.md", "runs-on: blacksmith-4vcpu\n")
    _page(root, "adr/4.x/2026-01-01-1-x.md", "runs-on: blacksmith-4vcpu\n")
    return root


_BURNDOWN = [gate.BurnDownEntry(page="guides/old.md", surfaces={"spec-kitty merge": 1}, issue="#7523")]


def test_a_tree_whose_hits_are_all_burned_down_passes(docs: Path) -> None:
    assert gate.check(docs, _BURNDOWN) == []


def test_a_new_hit_on_a_living_page_fails_naming_page_and_surface(docs: Path) -> None:
    _page(docs, "guides/clean.md", "Run `spec-kitty consolidate`.\nNot `spec-kitty merge`.\n")

    findings = gate.check(docs, _BURNDOWN)

    assert findings == ["NEW guides/clean.md:9: names retired surface 'spec-kitty merge' (retired: #3080: renamed to spec-kitty consolidate)"]


def test_a_second_surface_on_a_burned_down_page_is_new(docs: Path) -> None:
    _page(docs, "guides/old.md", "Run `spec-kitty merge`.\nThe `zeitgeist_client` package.\n")

    assert [finding.split(":")[0] for finding in gate.check(docs, _BURNDOWN)] == ["NEW guides/old.md"]


def test_a_burned_down_page_cannot_add_a_mention_of_the_same_surface(docs: Path) -> None:
    """The burn-down records a line count per pair: more lines is NEW, fewer is STALE (ratchet down)."""
    _page(docs, "guides/old.md", "Run `spec-kitty merge`.\nThen `spec-kitty merge` again.\n")
    (finding,) = gate.check(docs, _BURNDOWN)
    assert finding.startswith("NEW guides/old.md:9: names retired surface 'spec-kitty merge' on 2 lines, the burn-down allows 1")

    _page(docs, "guides/old.md", "Run `spec-kitty merge`.\n")
    higher = [gate.BurnDownEntry(page="guides/old.md", surfaces={"spec-kitty merge": 2}, issue="#7523")]
    assert gate.check(docs, higher) == ["STALE guides/old.md: 'spec-kitty merge' is named on 1 lines, below the burn-down's 2; lower it to 1 (#7523)"]


def test_a_burn_down_entry_with_no_hit_left_is_stale(docs: Path) -> None:
    _page(docs, "guides/old.md", "Run `spec-kitty consolidate`.\n")

    assert gate.check(docs, _BURNDOWN) == ["STALE guides/old.md: 'spec-kitty merge' is no longer named; remove it from the burn-down (#7523)"]


def test_history_and_unpublished_pages_are_not_checked(docs: Path) -> None:
    assert set(gate.scan(docs)) == {"guides/old.md"}


def test_main_exits_one_on_a_finding(docs: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    burndown = tmp_path / "burndown.yaml"
    burndown.write_text("kind: retired-surface-burndown\nversion: 2\nentries: []\n", encoding="utf-8")

    baselines = tmp_path / "_baselines.yaml"
    baselines.write_text("test_retired_surface_gate:\n  burn_down: 0\n", encoding="utf-8")
    landing = tmp_path / "landing.yaml"
    landing.write_text("kind: retired-surface-landing\nversion: 1\npages:\n  guides/old.md: {spec-kitty merge: 1}\n", encoding="utf-8")

    assert gate.main(["--docs-root", str(docs), "--burndown", str(burndown), "--baselines", str(baselines), "--landing", str(landing)]) == 1
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
    path.write_text("kind: something-else\nversion: 2\nentries: []\n", encoding="utf-8")
    with pytest.raises(gate.BurnDownError):
        gate.load_burndown(path)


def test_the_burn_down_only_shrinks_from_its_landing_set() -> None:
    counts = gate.burn_down_counts(gate.load_burndown(gate.DEFAULT_BURNDOWN))
    assert gate.refilled(counts, gate.load_landing(gate.DEFAULT_LANDING)) == []


# --- Leaving is one-way: the live count equals the recorded baseline ----------------------------


def test_the_burn_down_count_equals_its_baseline() -> None:
    """The one authority for the count is ``tests/architectural/_baselines.yaml`` (test_retired_surface_gate.burn_down)."""
    assert gate.baseline_findings(gate.BURN_DOWN, gate.load_baseline(gate.DEFAULT_BASELINES)) == []


def test_a_drained_pair_lowers_the_baseline_and_cannot_come_back() -> None:
    landing = frozenset({("a.md", "x"), ("b.md", "x"), ("c.md", "x")})
    after_drain = landing - {("a.md", "x")}

    # Draining without lowering the baseline fails and says to lower it.
    (finding,) = gate.baseline_findings(after_drain, len(landing))
    assert "lower" in finding and "_baselines.yaml" in finding
    # Draining with the baseline lowered in the same pull request is clean.
    assert gate.baseline_findings(after_drain, len(landing) - 1) == []
    # Putting the drained pair back exceeds the lowered baseline and fails.
    (finding,) = gate.baseline_findings(landing, len(landing) - 1)
    assert "above" in finding


def test_main_reports_a_swapped_pair_as_a_refill(docs: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Drain one pair and add another: the pair count is unchanged, so only the landing set catches it."""
    burndown = tmp_path / "burndown.yaml"
    burndown.write_text(
        "kind: retired-surface-burndown\nversion: 2\nentries:\n  - {page: guides/old.md, issue: '#7523', surfaces: {spec-kitty merge: 1}}\n",
        encoding="utf-8",
    )
    landing = tmp_path / "landing.yaml"
    landing.write_text("kind: retired-surface-landing\nversion: 1\npages:\n  guides/other.md: {spec-kitty merge: 1}\n", encoding="utf-8")
    baselines = tmp_path / "_baselines.yaml"
    baselines.write_text("test_retired_surface_gate:\n  burn_down: 1\n", encoding="utf-8")

    assert gate.main(["--docs-root", str(docs), "--burndown", str(burndown), "--landing", str(landing), "--baselines", str(baselines)]) == 1
    assert "REFILL guides/old.md: 'spec-kitty merge'" in capsys.readouterr().err


def test_main_reports_a_baseline_mismatch(docs: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    burndown = tmp_path / "burndown.yaml"
    burndown.write_text(
        "kind: retired-surface-burndown\nversion: 2\nentries:\n  - {page: guides/old.md, issue: '#7523', surfaces: {spec-kitty merge: 1}}\n",
        encoding="utf-8",
    )
    baselines = tmp_path / "_baselines.yaml"
    baselines.write_text("test_retired_surface_gate:\n  burn_down: 2\n", encoding="utf-8")
    landing = tmp_path / "landing.yaml"
    landing.write_text("kind: retired-surface-landing\nversion: 1\npages:\n  guides/old.md: {spec-kitty merge: 1}\n", encoding="utf-8")

    assert gate.main(["--docs-root", str(docs), "--burndown", str(burndown), "--baselines", str(baselines), "--landing", str(landing)]) == 1
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
        ("entries:\n  - page: a.md\n    issue: '#7523'\n", "needs a page, an issue and a non-empty surfaces mapping"),
        ("entries:\n  - page: a.md\n    issue: '#7523'\n    surfaces: {}\n", "needs a page, an issue and a non-empty surfaces mapping"),
        ("entries:\n  - {page: a.md, issue: '#7523', surfaces: {Zeitgeist: 0}}\n", "every surface needs a positive integer line count"),
        ("entries:\n  - {page: a.md, issue: '#7523', surfaces: {not-a-surface: 1}}\n", "unknown retired surface 'not-a-surface'"),
        (
            "entries:\n  - {page: a.md, issue: '#7523', surfaces: {Zeitgeist: 1}}\n  - {page: a.md, issue: '#7523', surfaces: {saas_client: 1}}\n",
            "duplicate page a.md",
        ),
    ],
)
def test_load_refuses_a_malformed_burn_down(tmp_path: Path, body: str, message: str) -> None:
    path = tmp_path / "b.yaml"
    path.write_text("kind: retired-surface-burndown\nversion: 2\n" + body, encoding="utf-8")
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
