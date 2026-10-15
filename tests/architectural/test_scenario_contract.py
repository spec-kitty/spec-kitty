"""Per-PR contract check for the CLI acceptance scenarios (no JDK needed).

Runs ``scripts/ci/scenario_contract.py`` over the real ``tests/scenarios`` tree against the
real Java step definitions, and over broken fixtures (one rule each) to prove every rule can
fail. The step vocabulary is read from the Java sources; nothing here duplicates it.

Also checks, per ADR 2026-10-15-1:

* the absorption ledger (``scripts/ci/absorption_ledger.py`` over
  ``tests/scenarios/absorption-ledger.json``): every engineering test retired from
  ``tests/integration`` or ``tests/e2e`` is gone and is carried by a gating scenario or a
  surviving pytest test, and no baseline file disappears without a row. Each rule has a planted
  tree built under ``tmp_path`` that must fail it;
* the ownership rules: ``.github/CODEOWNERS`` gives the scenarios to QA and core together and the
  runner to core, resolved with the last-matching-rule semantics of
  ``contracts/tools/codeowners_check.py`` (reused, not re-implemented).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.ci import absorption_ledger as ledger
from scripts.ci import scenario_contract as contract
from tests.contract._loader import load_tool

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).parent / "fixtures" / "scenarios"
FIXTURE_FEATURES = FIXTURES / "features"
FIXTURE_STEPS = FIXTURES / "steps"
REAL_FEATURES = REPO_ROOT / "tests" / "scenarios"
REAL_STEPS = REPO_ROOT / "acceptance-jvm" / "src" / "test" / "java"


@pytest.fixture(scope="module")
def fixture_defs():
    defs, problems = contract.load_step_definitions(FIXTURE_STEPS)
    assert problems == []
    return defs


def _codes(problems, severity="error"):
    return sorted(p.code for p in problems if p.severity == severity)


EXPECTED_ERRORS = {
    "parse_error.feature": ["PARSE_ERROR"],
    "no_steps.feature": ["NO_STEPS"],
    "no_scenarios.feature": ["NO_SCENARIOS"],
    "bad_promise.feature": ["BAD_PROMISE_ID"],
    "duplicate_promise.feature": ["DUPLICATE_PROMISE"],
    "wip_missing_owner.feature": ["WIP_MISSING_OWNER"],
    "wip_missing_since.feature": ["WIP_MISSING_SINCE"],
    "bad_wip_since.feature": ["BAD_WIP_SINCE"],
    "bad_wip_owner.feature": ["BAD_WIP_OWNER"],
    "bad_defect.feature": ["BAD_DEFECT"],
    "bad_qa.feature": ["BAD_QA_REF"],
    "unknown_prefixed_tag.feature": ["UNKNOWN_PREFIXED_TAG"],
    "bad_bare_tag.feature": ["BAD_BARE_TAG"],
    "unbound_step.feature": ["UNBOUND_STEP"],
    "ambiguous_step.feature": ["AMBIGUOUS_STEP"],
    "outline_unbound.feature": ["UNBOUND_STEP"],
    "outline_no_examples.feature": ["NO_EXAMPLES"],
}


@pytest.mark.parametrize("name,codes", sorted(EXPECTED_ERRORS.items()))
def test_each_broken_fixture_reports_its_rule(name, codes, fixture_defs):
    problems = contract.check_feature_file(FIXTURE_FEATURES / name, fixture_defs)
    assert _codes(problems) == codes


@pytest.mark.parametrize("name", ["wip_unbound.feature", "manual_unbound.feature"])
def test_non_gating_unbound_steps_are_information_only(name, fixture_defs):
    problems = contract.check_feature_file(FIXTURE_FEATURES / name, fixture_defs)
    assert _codes(problems) == []
    assert _codes(problems, "info") == ["UNBOUND_STEP"]


def test_valid_fixture_is_clean(fixture_defs):
    assert contract.check_feature_file(FIXTURE_FEATURES / "valid.feature", fixture_defs) == []


def test_unsupported_expressions_are_reported_with_their_source():
    problems = contract.load_step_definitions(FIXTURES / "steps_unsupported")[1]
    assert _codes(problems) == ["UNSUPPORTED_EXPRESSION"] * 3
    assert all(Path(p.file).name == "BadSteps.java" and p.line > 0 for p in problems)


def test_fixture_tree_reports_every_broken_file(fixture_defs):
    problems = contract.check_tree(FIXTURE_FEATURES, FIXTURE_STEPS)
    broken = {Path(p.file).name for p in problems if p.severity == "error"}
    assert broken == set(EXPECTED_ERRORS)


def test_real_tree_is_non_empty_and_clean():
    features = sorted(REAL_FEATURES.rglob("*.feature"))
    assert features, "tests/scenarios has no .feature files"
    problems = contract.check_tree(REAL_FEATURES, REAL_STEPS)
    assert _codes(problems) == [], contract.format_problems(problems)


def test_real_step_vocabulary_is_read_from_java():
    defs, problems = contract.load_step_definitions(REAL_STEPS)
    assert problems == []
    expressions = {d.expression for d in defs}
    assert "the command succeeds" in expressions
    assert "I run {string}" in expressions


def test_cli_exit_codes(capsys):
    bad = contract.main(["--features", str(FIXTURE_FEATURES), "--steps", str(FIXTURE_STEPS)])
    assert bad == 1
    assert "UNBOUND_STEP" in capsys.readouterr().out
    good = contract.main(["--features", str(REAL_FEATURES), "--steps", str(REAL_STEPS)])
    assert good == 0


# --- absorption ledger (ADR 2026-10-15-1, decision 3) ------------------------------------------

REAL_LEDGER = REPO_ROOT / "tests" / "scenarios" / "absorption-ledger.json"
GATING_FEATURE = """Feature: F
  Scenario: Gating
    Given a step
  @wip @wip-owner:qa @wip-since:2026-10-15
  Scenario: Drafted
    Given a step
"""


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _ledger_doc(rows: list[dict], baseline: list[str]) -> dict:
    return {"schema_version": 1, "baseline": {"files": baseline}, "retired": rows}


def _row(retired: str, *replaced_by: str) -> dict:
    return {"retired": retired, "replaced_by": list(replaced_by), "issue": 6101, "note": "planted"}


def _planted_tree(root: Path) -> list[str]:
    """A tree with one kept integration file, one surviving pytest test and one feature file."""
    _write(root, "tests/integration/test_kept.py", "class TestKept:\n    def test_stays(self):\n        pass\n")
    _write(root, "tests/unit/test_survivor.py", "def test_survivor():\n    pass\n")
    _write(root, "tests/scenarios/area/area.feature", GATING_FEATURE)
    return ["tests/e2e/test_gone.py", "tests/integration/test_kept.py"]


def _check(root: Path, doc: object) -> list[str]:
    path = root / "ledger.json"
    path.write_text(doc if isinstance(doc, str) else json.dumps(doc), encoding="utf-8")
    return sorted(p.code for p in ledger.check(root, path))


CLEAN_ROWS = [
    _row("tests/e2e/test_gone.py", "tests/scenarios/area/area.feature::Gating"),
    _row("tests/integration/test_kept.py::TestKept::test_moved", "tests/unit/test_survivor.py::test_survivor"),
]

PLANTED_LEDGERS = {
    "LEDGER_UNREADABLE": "{not json",
    "LEDGER_SCHEMA": {"schema_version": 2, "baseline": {"files": []}, "retired": []},
    "EMPTY_BASELINE": _ledger_doc([], []),
    "DUPLICATE_RETIRED": None,  # built in the test from CLEAN_ROWS
    "RETIRED_NOT_IN_BASELINE": _ledger_doc(
        [*CLEAN_ROWS, _row("tests/integration/test_other.py", "tests/unit/test_survivor.py")], ["tests/e2e/test_gone.py", "tests/integration/test_kept.py"]
    ),
    "RETIRED_STILL_PRESENT": _ledger_doc(
        [*CLEAN_ROWS, _row("tests/integration/test_kept.py::TestKept::test_stays", "tests/unit/test_survivor.py")],
        ["tests/e2e/test_gone.py", "tests/integration/test_kept.py"],
    ),
    "REPLACEMENT_MISSING": _ledger_doc(
        [CLEAN_ROWS[0], _row("tests/integration/test_kept.py::TestKept::test_moved", "tests/scenarios/area/area.feature::No such scenario")],
        ["tests/e2e/test_gone.py", "tests/integration/test_kept.py"],
    ),
    "REPLACEMENT_NOT_GATING": _ledger_doc(
        [CLEAN_ROWS[0], _row("tests/integration/test_kept.py::TestKept::test_moved", "tests/scenarios/area/area.feature::Drafted")],
        ["tests/e2e/test_gone.py", "tests/integration/test_kept.py"],
    ),
    "UNLEDGERED_REMOVAL": _ledger_doc([CLEAN_ROWS[1]], ["tests/e2e/test_gone.py", "tests/integration/test_kept.py"]),
}


def test_planted_clean_ledger_passes(tmp_path):
    baseline = _planted_tree(tmp_path)
    assert _check(tmp_path, _ledger_doc(CLEAN_ROWS, baseline)) == []


@pytest.mark.parametrize("code", sorted(PLANTED_LEDGERS))
def test_each_planted_ledger_fails_its_rule(tmp_path, code):
    baseline = _planted_tree(tmp_path)
    doc = PLANTED_LEDGERS[code] if code != "DUPLICATE_RETIRED" else _ledger_doc([*CLEAN_ROWS, CLEAN_ROWS[0]], baseline)
    assert _check(tmp_path, doc) == [code]


def test_a_malformed_row_is_a_schema_problem(tmp_path):
    baseline = _planted_tree(tmp_path)
    rows = [*CLEAN_ROWS, {"retired": "src/not_a_test.py", "replaced_by": [], "issue": "6101"}]
    assert _check(tmp_path, _ledger_doc(rows, baseline)) == ["LEDGER_SCHEMA"] * 3


def test_node_ids_resolve_nested_and_parametrized_names(tmp_path):
    _planted_tree(tmp_path)
    assert ledger.node_exists(tmp_path, "tests/integration/test_kept.py::TestKept::test_stays[case-1]")
    assert not ledger.node_exists(tmp_path, "tests/integration/test_kept.py::test_stays")
    assert not ledger.node_exists(tmp_path, "tests/integration/test_missing.py")


def test_real_ledger_is_clean_and_covers_both_trees():
    problems = ledger.check(REPO_ROOT)
    assert problems == [], "\n".join(p.render() for p in problems)
    loaded, _ = ledger.load_ledger(REAL_LEDGER)
    assert loaded is not None
    roots = {path.split("/", 2)[1] for path in loaded.baseline}
    assert roots == {"integration", "e2e"}
    assert len(loaded.baseline) >= 180, "the baseline froze 184 files on 2026-10-15; it never shrinks"
    assert loaded.rows, "the ledger records at least the first absorption tranche"


def test_ledger_cli_exit_codes(tmp_path, capsys):
    assert ledger.main(["--root", str(REPO_ROOT)]) == 0
    _planted_tree(tmp_path)
    bad = tmp_path / "ledger.json"
    bad.write_text(json.dumps(PLANTED_LEDGERS["UNLEDGERED_REMOVAL"]), encoding="utf-8")
    assert ledger.main(["--root", str(tmp_path), "--ledger", str(bad)]) == 1
    assert "UNLEDGERED_REMOVAL" in capsys.readouterr().out


# --- ownership (ADR 2026-10-15-1, decision 1) ----------------------------------------------------

CODEOWNERS = REPO_ROOT / ".github" / "CODEOWNERS"
SHARED_OWNERS = ("@stijn-dejongh", "@kentonium3", "@Ivan-Melck")
ENGINEERING_OWNERS = ("@stijn-dejongh",)
EXPECTED_OWNERS = {
    "tests/scenarios/init/init.feature": SHARED_OWNERS,
    "tests/scenarios/absorption-ledger.json": SHARED_OWNERS,
    "docs/development/testing/acceptance-scenarios.md": SHARED_OWNERS,
    "docs/development/testing/test-pyramid-rebalance.md": SHARED_OWNERS,
    "acceptance-jvm/src/test/java/kitty/acceptance/steps/ArrangeSteps.java": ENGINEERING_OWNERS,
    "acceptance-jvm/build.gradle": ENGINEERING_OWNERS,
}


@pytest.fixture(scope="module")
def owners_tool():
    tools = REPO_ROOT / "contracts" / "tools"
    with pytest.MonkeyPatch.context() as mp:
        yield load_tool(mp, tools / "codeowners_check.py", "codeowners_check_for_scenarios", syspath=tools)


def ownership_mismatches(tool, text: str) -> dict[str, tuple[str, ...]]:
    """Paths whose last matching CODEOWNERS rule does not name exactly the expected owners."""
    rules = tool.parse_rules(text)
    mismatches = {}
    for path, expected in EXPECTED_OWNERS.items():
        matching = [rule for rule in rules if tool.pattern_covers(rule.pattern, path)]
        owners = matching[-1].owners if matching else ()
        if sorted(owners) != sorted(expected):
            mismatches[path] = owners
    return mismatches


def test_codeowners_shares_the_scenarios_and_gives_the_runner_to_core(owners_tool):
    assert ownership_mismatches(owners_tool, CODEOWNERS.read_text(encoding="utf-8")) == {}


def test_ownership_check_fails_when_a_later_rule_overrides_the_scenarios(owners_tool):
    planted = CODEOWNERS.read_text(encoding="utf-8") + "\n/tests/ @stijn-dejongh\n"
    mismatches = ownership_mismatches(owners_tool, planted)
    assert set(mismatches) == {"tests/scenarios/init/init.feature", "tests/scenarios/absorption-ledger.json"}
