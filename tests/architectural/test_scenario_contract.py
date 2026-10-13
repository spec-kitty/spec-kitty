"""Per-PR contract check for the CLI acceptance scenarios (no JDK needed).

Runs ``scripts/ci/scenario_contract.py`` over the real ``tests/scenarios`` tree against the
real Java step definitions, and over broken fixtures (one rule each) to prove every rule can
fail. The step vocabulary is read from the Java sources; nothing here duplicates it.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.ci import scenario_contract as contract

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
    "bad_promise.feature": ["BAD_PROMISE_ID"],
    "duplicate_promise.feature": ["DUPLICATE_PROMISE"],
    "wip_missing_owner.feature": ["WIP_MISSING_OWNER"],
    "wip_missing_since.feature": ["WIP_MISSING_SINCE"],
    "bad_wip_since.feature": ["BAD_WIP_SINCE"],
    "bad_wip_owner.feature": ["BAD_WIP_OWNER"],
    "bad_defect.feature": ["BAD_DEFECT"],
    "bad_qa.feature": ["BAD_QA_REF"],
    "unknown_prefixed_tag.feature": ["UNKNOWN_PREFIXED_TAG"],
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
