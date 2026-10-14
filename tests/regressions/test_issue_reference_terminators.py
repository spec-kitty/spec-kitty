"""Regression for (#6069): issue references ending in ``:`` ``!`` ``?`` and wrapped URLs.

The single issue-reference detector (``_GH_ISSUE_PATTERN``) used to end a bare
``#NNNN`` only at whitespace, ``)``, ``]``, ``,``, ``;``, ``.`` or end of line,
and a same-repo issue URL only at those plus ``#`` and ``/``.  Citations such as
``Issue #6058: title`` therefore never produced an issue-matrix row and no gate
asked for a verdict.

Every test drives a production entry point (``gating_issue_numbers``,
``detect_issue_references`` or the merge-gate completeness check).  Each
"never recognized" shape is paired with a recognized sibling built from the same
skeleton so a probe that sees nothing cannot pass vacuously.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.cli.commands.agent.tasks_parsing_validation import _issue_matrix_approval_blocker
from specify_cli.policy.merge_gates import GateVerdict, _evaluate_issue_matrix_completeness_gate
from specify_cli.status.models import Lane
from specify_cli.tasks.issue_matrix import detect_issue_references
from specify_cli.tasks.issue_reference_discovery import GatingClass, gating_issue_numbers

pytestmark = [pytest.mark.regression, pytest.mark.fast]

NNNN = 6058
MMMM = 5974
GATES = {f"#{NNNN}"}
OWN = "https://github.com/spec-kitty/spec-kitty/issues"
OTHER = "https://github.com/acme/widgets/issues"


def _feature_dir(tmp_path: Path, spec_line: str) -> Path:
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    (feature_dir / "spec.md").write_text(spec_line.format(n=NNNN, m=MMMM) + "\n", encoding="utf-8")
    return feature_dir


def _gated(tmp_path: Path, spec_line: str) -> set[str]:
    return set(gating_issue_numbers(_feature_dir(tmp_path, spec_line)))


NOW_RECOGNIZED = [
    pytest.param("**Input**: Issue #{n}: the audit fails", id="colon-then-space"),
    pytest.param("Tracked in #{n}:", id="colon-end-of-line"),
    pytest.param("Status for #{n}:** pending", id="colon-closing-bold"),
    pytest.param("Fixes #{n}!", id="bang"),
    pytest.param("Does this close #{n}?", id="question"),
    pytest.param("Ref #{n}:: x", id="double-colon"),
    pytest.param("Ref #{n}:- x", id="colon-dash"),
    pytest.param("Ref #{n}:/ x", id="colon-slash"),
    pytest.param("Ref (#{n}:) x", id="colon-paren"),
    pytest.param("Ref #{n}!! x", id="double-bang"),
    pytest.param("Ref #{n}!=0 x", id="bang-equals"),
    pytest.param("Ref `" + OWN + "/{n}` here", id="url-backtick"),
    pytest.param("Ref <" + OWN + "/{n}> here", id="url-autolink"),
    pytest.param("Ref **" + OWN + "/{n}** here", id="url-bold"),
    pytest.param('Ref "' + OWN + '/{n}" here', id="url-double-quote"),
    pytest.param("Ref '" + OWN + "/{n}' here", id="url-single-quote"),
    pytest.param("Ref " + OWN + "/{n}: details", id="url-colon"),
    pytest.param("Ref " + OWN + "/{n}?x=1 here", id="url-query"),
]

UNCHANGED_CONTROLS = [
    pytest.param("Ref (#{n})", id="parenthesized"),
    pytest.param("Ref #{n} here", id="space"),
    pytest.param("Ref #{n}, here", id="comma"),
    pytest.param("Ref " + OWN + "/{n}#issuecomment-1", id="url-anchor"),
    pytest.param("Ref " + OWN + "/{n}/", id="url-trailing-slash"),
]

# (excluded shape, recognized sibling on the same skeleton)
EXCLUDED_WITH_SIBLING = [
    pytest.param("Ref #{n}:45", "Ref #{n}: 45", id="line-column"),
    pytest.param("Ref #{n}:L5", "Ref #{n}: L5", id="line-label"),
    pytest.param("Ref #{n}:tada:", "Ref #{n}: tada", id="shortcode"),
    pytest.param("Ref #{n}?x", "Ref #{n}? x", id="question-word"),
    pytest.param("Ref #{n}!x", "Ref #{n}! x", id="bang-word"),
    pytest.param("Ref #{n}?q=1", "Ref #{n}? q=1", id="question-query"),
    pytest.param("Ref #{n}-fix", "Ref #{n} fix", id="branch-like"),
    pytest.param("Ref acme/widgets#{n}:", "Ref widgets #{n}:", id="cross-repo-short"),
    pytest.param("Ref `" + OTHER + "/{n}`", "Ref `" + OWN + "/{n}`", id="cross-repo-url-backtick"),
    pytest.param("Ref <" + OTHER + "/{n}>", "Ref <" + OWN + "/{n}>", id="cross-repo-url-autolink"),
    pytest.param("Ref " + OTHER + "/{n}:", "Ref " + OWN + "/{n}:", id="cross-repo-url-colon"),
    pytest.param("Ref " + OWN + "/{n}abc", "Ref " + OWN + "/{n} ", id="url-letter-suffix"),
    pytest.param("Ref " + OWN + "/{n}_x", "Ref " + OWN + "/{n} ", id="url-underscore-suffix"),
    pytest.param("Ref **" + OTHER + "/{n}**", "Ref **" + OWN + "/{n}**", id="cross-repo-url-bold"),
    pytest.param('Ref "' + OTHER + '/{n}"', 'Ref "' + OWN + '/{n}"', id="cross-repo-url-double-quote"),
    pytest.param("Ref '" + OTHER + "/{n}'", "Ref '" + OWN + "/{n}'", id="cross-repo-url-single-quote"),
    pytest.param("Ref " + OTHER + "/{n}?x=1", "Ref " + OWN + "/{n}?x=1", id="cross-repo-url-query"),
    pytest.param("Ref #section-name", "Ref #{n}", id="markdown-anchor"),
    pytest.param("Ref #12345678", "Ref #{n}", id="seven-plus-digits"),
    pytest.param("Ref " + OWN + "/12345678", "Ref " + OWN + "/{n}", id="seven-plus-digits-url"),
]


@pytest.mark.parametrize("spec_line", NOW_RECOGNIZED)
def test_terminated_citation_is_gating(tmp_path: Path, spec_line: str) -> None:
    assert _gated(tmp_path, spec_line) == GATES


@pytest.mark.parametrize("spec_line", UNCHANGED_CONTROLS)
def test_previously_recognized_shapes_still_gate(tmp_path: Path, spec_line: str) -> None:
    assert _gated(tmp_path, spec_line) == GATES


@pytest.mark.parametrize(("excluded", "sibling"), EXCLUDED_WITH_SIBLING)
def test_excluded_shape_stays_unrecognized_with_positive_control(tmp_path: Path, excluded: str, sibling: str) -> None:
    sibling_dir = tmp_path / "sibling"
    excluded_dir = tmp_path / "excluded"
    assert _gated(sibling_dir, sibling) == GATES, "positive control must be recognized"
    assert _gated(excluded_dir, excluded) == set()


def test_completeness_gate_fails_for_colon_citation_without_matrix(tmp_path: Path) -> None:
    """FR-006: the user-visible symptom, through the merge-gate entry point."""
    _feature_dir(tmp_path, "**Input**: Issue #{n}: the audit fails")
    gate = _evaluate_issue_matrix_completeness_gate(tmp_path, "demo", is_blocking=True)
    assert gate.verdict == GateVerdict.FAIL
    assert gate.blocking is True
    assert f"#{NNNN}" in gate.details


def test_completeness_gate_control_parenthesized_citation(tmp_path: Path) -> None:
    _feature_dir(tmp_path, "**Input**: Issue (#{n}) the audit fails")
    gate = _evaluate_issue_matrix_completeness_gate(tmp_path, "demo", is_blocking=True)
    assert gate.verdict == GateVerdict.FAIL
    assert gate.blocking is True
    assert f"#{NNNN}" in gate.details


def test_classification_of_newly_recognized_shapes(tmp_path: Path) -> None:
    """FR-009 / C-002: recognition widens, classification does not change."""
    feature_dir = tmp_path / "kitty-specs" / "demo"
    feature_dir.mkdir(parents=True)
    spec = feature_dir / "spec.md"
    spec.write_text(
        f"see #{MMMM}: the concurrent mission\nIssue #{NNNN}: the audit fails\n",
        encoding="utf-8",
    )
    refs = {ref.number: ref.classification for ref in detect_issue_references(spec)}
    assert refs == {
        MMMM: GatingClass.CONTEXT_ONLY,
        NNNN: GatingClass.IMPLEMENTATION_TARGET,
    }
    assert set(gating_issue_numbers(feature_dir)) == GATES


@pytest.mark.parametrize(
    "spec_line",
    [
        pytest.param("Issue #{n}: the audit fails", id="colon"),
        pytest.param("Ref `" + OWN + "/{n}` here", id="url-backtick"),
    ],
)
def test_approval_blocker_names_newly_recognized_citation(tmp_path: Path, spec_line: str) -> None:
    """SC-001: the approval gate blocks and names the issue (no matrix present)."""
    feature_dir = _feature_dir(tmp_path, spec_line)
    blocker = _issue_matrix_approval_blocker(feature_dir, target_lane=Lane.APPROVED)
    assert blocker is not None
    assert f"#{NNNN}" in blocker


def test_approval_blocker_ignores_line_reference_with_positive_control(tmp_path: Path) -> None:
    excluded = _feature_dir(tmp_path / "excluded", "see line #{n}:45")
    # Control: a recognized same-skeleton citation blocks (so the probe can see).
    control = _feature_dir(tmp_path / "control", "Issue #{n}: 45 here")
    assert _issue_matrix_approval_blocker(control, target_lane=Lane.APPROVED) is not None
    assert _issue_matrix_approval_blocker(excluded, target_lane=Lane.APPROVED) is None
