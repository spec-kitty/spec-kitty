"""Keep QA #801's unratified proposal complete and its binding claims mechanically honest."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from scripts.ci.scenario_contract import load_step_definitions, parse_feature

ROOT = Path(__file__).resolve().parents[2]
SUITE = ROOT / "tests/scenarios/charter-activation"
STEPS = ROOT / "acceptance-jvm/src/test/java/kitty/acceptance/steps"


def _scenarios():
    result = {}
    for path in sorted(SUITE.rglob("*.feature")):
        scenarios, problems = parse_feature(path)
        assert not problems
        for scenario in scenarios:
            ref = f"{path.relative_to(SUITE).as_posix()}#{scenario.name}"
            assert ref not in result
            result[ref] = scenario
    return result


def _rows(text: str):
    return [[cell.strip().strip("`") for cell in line.strip("|").split("|")]
            for line in text.splitlines() if re.match(r"^\| A\d{2} \|", line)]


def _binding_problems(text: str) -> list[str]:
    scenarios = _scenarios()
    definitions, problems = load_step_definitions(STEPS)
    assert not problems
    rows = _rows(text)
    found = [row[1] for row in rows]
    errors = []
    if len(rows) != 22 or len(set(found)) != len(found) or set(found) != set(scenarios):
        errors.append("rows must identify each of the 22 scenarios exactly once")
    for row in rows:
        if row[1] not in scenarios:
            continue
        steps = scenarios[row[1]].steps
        bound = sum(sum(bool(d.regex.fullmatch(s.text)) for d in definitions) == 1 for s in steps)
        if row[3] != f"{bound}/{len(steps)}":
            errors.append(f"{row[0]}: stale binding count")
    return errors


def test_every_scenario_has_one_honest_binding_disposition() -> None:
    assert _binding_problems((SUITE / "BINDINGS.md").read_text()) == []


def test_candidate_ledger_is_complete_but_not_ratified() -> None:
    ledger = (SUITE / "PROMISES.md").read_text()
    assert "Status: PROPOSED — NOT RATIFIED" in ledger
    assert "Ratifier: not assigned" in ledger
    ids = re.findall(r"^\| `(PR-CHARTER-ACTIVATION-\d{3})` \|", ledger, re.MULTILINE)
    assert len(ids) == len(set(ids)) == 17
    cases = _rows((SUITE / "BINDINGS.md").read_text())
    assert {row[2] for row in cases} - {"—"} == set(ids)
    assert sum(row[2] == "—" for row in cases) == 5


def test_proposal_does_not_promote_or_tag_unratified_scenarios() -> None:
    scenarios = _scenarios()
    assert len(scenarios) == 22
    for scenario in scenarios.values():
        assert "wip" in scenario.tags
        assert any(t.startswith("wip-owner:") for t in scenario.tags)
        assert any(t.startswith("wip-since:") for t in scenario.tags)
        assert not any(t.startswith("promise:") for t in scenario.tags)


def test_critical_starting_states_and_non_noop_controls_are_explicit() -> None:
    texts = {p.parent.name: p.read_text() for p in SUITE.rglob("*.feature")}
    assert "the rule is available but is not in force" in texts["turning-governance-on-and-off"]
    assert "explicitly adopts one of those rules" in texts["turning-governance-on-and-off"]
    assert "the retired choice is no longer in force" in texts["turning-off-keeps-the-rest-sound"]
    assert "the referenced governance left outside that scope stays out of force" in texts["brings-what-it-depends-on"]
    assert "the project has explicitly limited the governance it uses" in texts["provisioning-governance-packs"]
    assert "the baseline's chosen directives and tactics are in force" in texts["the-default-governance-profile"]
    assert "Then only that curated baseline of governance is in force" not in texts["the-default-governance-profile"]


def test_proposal_local_links_resolve() -> None:
    for name in ("PROMISES.md", "BINDINGS.md", "RESEARCH.md", "README.md"):
        path = SUITE / name
        for link in re.findall(r"\]\(([^)]+)\)", path.read_text()):
            if "://" not in link and not link.startswith("#"):
                assert (path.parent / link.split("#", 1)[0]).exists(), (name, link)


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "stale-count"])
def test_disposition_guard_rejects_missing_duplicate_and_stale_claims(mutation: str) -> None:
    text = (SUITE / "BINDINGS.md").read_text()
    row = next(line for line in text.splitlines() if line.startswith("| A01 |"))
    if mutation == "missing":
        text = text.replace(row, "")
    elif mutation == "duplicate":
        text += "\n" + row + "\n"
    else:
        cells = row.split("|")
        cells[4] = " 999/999 "
        text = text.replace(row, "|".join(cells))
    assert _binding_problems(text)
