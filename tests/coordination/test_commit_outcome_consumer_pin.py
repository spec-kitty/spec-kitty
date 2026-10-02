"""Pin the commit-outcome consumer list (WP20 / T110, FR-007, ``contracts/commit-outcome.md`` rule 6).

Rule 6: "Every consumer renders through ``render_commit_outcome`` (text) or
``commit_outcome_payload`` (JSON). No consumer formats surface outcomes by hand.
A test pins the consumer list from research D8." The masking defects (#5513,
#5501) lived in the shared contract, so this pin keeps a consumer from drifting
back to hand-formatting, or from quietly discarding a refused surface.

The pin is AST-only and syntactic (a proxy, not a value-flow proof):

* every pinned ``(rel_path, qualname)`` consumer function resolves to ONE live
  definition and calls ``render_commit_outcome`` or ``commit_outcome_payload``
  (``commit_outcome_exit_code`` is a companion, never a substitute);
* no pinned consumer references ``.committed`` / ``.skipped`` / ``.refused``
  inside an f-string or a ``str.format`` call -- that is hand formatting;
* a consumer that renders through a module-local helper is pinned twice: the
  helper (which calls the shared renderer) and the caller (which calls the
  helper), see ``_HELPER_CALLERS``;
* the wrapper modules ``write_seam.py`` and ``agent_tasks_ports.py`` only pass
  ``surfaces`` through -- their CALLERS render, so the callers are pinned and
  the wrappers are asserted free of hand formatting.

The list is RE-DERIVED against the merged code (several WPs extracted helpers
after research D8 was written); the D8 row each pair serves is named inline.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.architectural._ast_scan import parse_source, read_source

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]

#: Callees that render a ``CommitRouterResult`` / wrapper result through the
#: shared contract (rule 6): text and JSON.
_RENDER_CALLEES: frozenset[str] = frozenset({"render_commit_outcome", "commit_outcome_payload"})
#: ``commit_outcome_exit_code`` is allowed alongside a render callee, never instead of one.
_COMPANION_CALLEES: frozenset[str] = frozenset({"commit_outcome_exit_code"})
#: ``SurfaceOutcome`` fields whose appearance inside an f-string / ``.format``
#: call means a surface outcome is being formatted by hand.
_SURFACE_FIELDS: frozenset[str] = frozenset({"committed", "skipped", "refused"})

#: research D8's consumer-site count; the pin never shrinks below it.
_CONSUMER_FLOOR = 14

_MSP = "src/specify_cli/cli/commands/agent/mission_setup_plan.py"
_MRA = "src/specify_cli/cli/commands/agent/mission_record_analysis.py"
_VERDICT = "src/specify_cli/cli/commands/agent/acceptance_verdict.py"
_FINALIZE = "src/specify_cli/cli/commands/agent/mission_finalize.py"
_ACCEPT = "src/specify_cli/cli/commands/accept.py"
_RETROSPECT = "src/specify_cli/cli/commands/retrospect.py"
_SPEC_COMMIT = "src/specify_cli/cli/commands/spec_commit_cmd.py"
_MAP_REQUIREMENTS = "src/specify_cli/cli/commands/agent/tasks_map_requirements.py"
_TRACER_APPEND = "src/specify_cli/cli/commands/agent/tracer_append.py"
_TRACER_WRITER = "src/specify_cli/retrospective/tracer_writer.py"
_ISSUE_MATRIX = "src/specify_cli/tasks/issue_matrix.py"
_CYCLE = "src/specify_cli/review/cycle.py"

#: ``(rel_path_from_repo_root, dotted_qualname)`` of every function that renders a
#: commit outcome, one block per research D8 row.
_CONSUMERS: tuple[tuple[str, str], ...] = (
    # setup-plan (D8: mission_setup_plan.py L237 / L892 / L951). The gap-analysis
    # and generator-config sites discard the result and warn through the helper.
    (_MSP, "_commit_to_branch"),
    (_MSP, "_warn_on_incomplete_surfaces"),
    (_MSP, "_build_setup_plan_result"),
    # record-analysis (D8: mission_record_analysis.py L374). There is no
    # ``_maybe_auto_commit`` here; the consumer is ``record_analysis`` plus its helper.
    (_MRA, "record_analysis"),
    (_MRA, "_warn_on_incomplete_surfaces"),
    # report transaction (D8: git/report_transaction.py L199).
    ("src/specify_cli/git/report_transaction.py", "record_report_transaction"),
    # orchestrator API (D8: orchestrator_api/commands.py L3018).
    ("src/specify_cli/orchestrator_api/commands.py", "_record_analysis_commit_surfaces_payload"),
    # acceptance (D8: acceptance/__init__.py L1791, L1822).
    ("src/specify_cli/acceptance/__init__.py", "_commit_acceptance_meta_via_router"),
    # write seam -> acceptance matrix (D8: acceptance/matrix.py L524). The matrix
    # module is a ``write_seam.write_artifact`` wrapper; its CALLERS render.
    (_VERDICT, "_emit_outcome_error"),
    (_VERDICT, "_run_criterion_mode"),
    (_VERDICT, "_run_negative_invariant_mode"),
    # write seam -> issue matrix and tracer (D8: tasks/issue_matrix.py L404,
    # retrospective/tracer_writer.py L298): module-local discarded-surface warners.
    (_ISSUE_MATRIX, "_warn_on_discarded_surfaces"),
    (_TRACER_WRITER, "_warn_on_discarded_surfaces"),
    # accept coordination residuals (D8: cli/commands/accept.py L426); WP16's
    # router-result helpers.
    (_ACCEPT, "_render_accept_result"),
    (_ACCEPT, "_format_residual_failure_detail"),
    # finalize and its pin refresh (D8: mission_finalize.py L3659 / L2874).
    (_FINALIZE, "_apply_finalize_commit_router_result"),
    (_FINALIZE, "_finalize_pin_refresh_commit_outcome"),
    # retrospect (D8: retrospect.py L315); ``_maybe_auto_commit`` calls this helper.
    (_RETROSPECT, "_render_unexplained_surfaces"),
    # spec-commit (D8: spec_commit_cmd.py L214): WP13's render helpers.
    (_SPEC_COMMIT, "_build_spec_commit_payload"),
    (_SPEC_COMMIT, "_print_spec_commit_text"),
    # tasks ports (D8: agent_tasks_ports.py L389/400 -> review/cycle.py L712,
    # tasks_map_requirements.py L668). ``agent_tasks_ports`` passes ``surfaces``
    # through; these callers render. mark-status is NOT a consumer (it commits
    # nothing; its ``_ms_commit`` shim is dead).
    (_CYCLE, "_with_surface_detail"),
    (_MAP_REQUIREMENTS, "_mr_render_refused_surfaces"),
    (_MAP_REQUIREMENTS, "_mr_surfaces_payload"),
    # tracer-append CLI (D8: tracer_append.py L135-163), migrated by WP10
    # (post-tasks squad R-M2).
    (_TRACER_APPEND, "tracer_append"),
    (_TRACER_APPEND, "_emit_with_surfaces"),
)

#: ``(rel_path, caller_qualname, helper_callee)``: a consumer that renders through
#: a module-local helper must call that helper (the helper itself is pinned in
#: ``_CONSUMERS``). Without this, a caller could stop calling the helper and
#: silently drop a refused surface.
_HELPER_CALLERS: tuple[tuple[str, str, str], ...] = (
    (_MSP, "_run_documentation_gap_analysis", "_warn_on_incomplete_surfaces"),
    (_MSP, "_detect_and_configure_generators", "_warn_on_incomplete_surfaces"),
    (_MRA, "record_analysis", "_warn_on_incomplete_surfaces"),
    (_MRA, "_run_report_only", "_warn_on_incomplete_surfaces"),
    (_ISSUE_MATRIX, "write_issue_matrix", "_warn_on_discarded_surfaces"),
    (_TRACER_WRITER, "append_tracer_finding", "_warn_on_discarded_surfaces"),
    (_RETROSPECT, "_maybe_auto_commit", "_render_unexplained_surfaces"),
)

#: Wrapper modules that only pass ``surfaces`` through (callers render): asserted
#: free of hand formatting anywhere in the module.
_PASS_THROUGH_WRAPPER_MODULES: tuple[str, ...] = (
    "src/specify_cli/coordination/write_seam.py",
    "src/specify_cli/agent_tasks_ports.py",
)

#: Every research D8 consumer module that must keep at least one pinned function.
_D8_RENDERING_MODULES: frozenset[str] = frozenset(
    {
        _MSP,
        _MRA,
        "src/specify_cli/git/report_transaction.py",
        "src/specify_cli/orchestrator_api/commands.py",
        "src/specify_cli/acceptance/__init__.py",
        _VERDICT,
        _ISSUE_MATRIX,
        _TRACER_WRITER,
        _ACCEPT,
        _FINALIZE,
        _RETROSPECT,
        _SPEC_COMMIT,
        _CYCLE,
        _MAP_REQUIREMENTS,
        _TRACER_APPEND,
    }
)

FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


@dataclass(frozen=True)
class _ConsumerViolation:
    rel_path: str
    qualname: str
    problem: str

    def describe(self) -> str:
        return f"{self.rel_path}::{self.qualname}: {self.problem}"


def _find_function(tree: ast.Module, qualname: str) -> FunctionNode | None:
    """The single function a dotted ``qualname`` names (class bodies are walked), else ``None``."""
    *owners, name = qualname.split(".")
    body: list[ast.stmt] = tree.body
    for owner in owners:
        classes = [node for node in body if isinstance(node, ast.ClassDef) and node.name == owner]
        if len(classes) != 1:
            return None
        body = classes[0].body
    functions = [node for node in body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name]
    return functions[0] if len(functions) == 1 else None


def _callee_name(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _called_names(node: ast.AST) -> set[str]:
    """Every callee identifier invoked anywhere under *node* (nested defs included)."""
    return {name for call in ast.walk(node) if isinstance(call, ast.Call) and (name := _callee_name(call)) is not None}


def _surface_field_reads(node: ast.AST) -> set[str]:
    return {sub.attr for sub in ast.walk(node) if isinstance(sub, ast.Attribute) and sub.attr in _SURFACE_FIELDS}


def _hand_formatted_fields(node: ast.AST) -> set[str]:
    """Surface fields referenced inside an f-string or a ``str.format`` call under *node*.

    A bare ``len(outcome.committed)`` outside any formatting construct is NOT
    hand formatting; ``f"{outcome.refused}"`` and ``"{}".format(outcome.skipped)`` are.
    """
    found: set[str] = set()
    for sub in ast.walk(node):
        if isinstance(sub, ast.JoinedStr) or isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr == "format":
            found |= _surface_field_reads(sub)
    return found


def _consumer_problems(function: FunctionNode) -> list[str]:
    """What is wrong with a pinned consumer *function* (empty when it conforms)."""
    problems: list[str] = []
    called = _called_names(function)
    if not called & _RENDER_CALLEES:
        companion = " (only a companion exit-code call is not enough)" if called & _COMPANION_CALLEES else ""
        problems.append(f"does not call {' or '.join(sorted(_RENDER_CALLEES))}{companion}")
    hand_formatted = _hand_formatted_fields(function)
    if hand_formatted:
        problems.append(f"hand-formats surface field(s) {sorted(hand_formatted)} in an f-string / str.format")
    return problems


def _consumer_violations_in_source(source: str, rel_path: str, qualname: str) -> list[_ConsumerViolation]:
    tree = parse_source(source, display=rel_path)
    function = _find_function(tree, qualname)
    if function is None:
        return [_ConsumerViolation(rel_path, qualname, "no single live definition")]
    return [_ConsumerViolation(rel_path, qualname, problem) for problem in _consumer_problems(function)]


def _collect_consumer_violations(consumers: tuple[tuple[str, str], ...], repo_root: Path = _REPO_ROOT) -> list[_ConsumerViolation]:
    violations: list[_ConsumerViolation] = []
    for rel_path, qualname in consumers:
        source = read_source(repo_root / rel_path)
        violations.extend(_consumer_violations_in_source(source, rel_path, qualname))
    return violations


def _helper_caller_violations(callers: tuple[tuple[str, str, str], ...], repo_root: Path = _REPO_ROOT) -> list[_ConsumerViolation]:
    violations: list[_ConsumerViolation] = []
    for rel_path, qualname, helper in callers:
        tree = parse_source(read_source(repo_root / rel_path), display=rel_path)
        function = _find_function(tree, qualname)
        if function is None:
            violations.append(_ConsumerViolation(rel_path, qualname, "no single live definition"))
        elif helper not in _called_names(function):
            violations.append(_ConsumerViolation(rel_path, qualname, f"does not call its surface helper {helper}()"))
    return violations


# ---------------------------------------------------------------------------
# The pin
# ---------------------------------------------------------------------------


def test_consumer_list_meets_its_floor_and_covers_every_d8_module() -> None:
    """Non-vacuity: the pin cannot silently shrink below research D8's 14 sites."""
    assert len(set(_CONSUMERS)) == len(_CONSUMERS), "duplicate consumer pairs would inflate the floor"
    assert len(_CONSUMERS) >= _CONSUMER_FLOOR
    pinned_modules = {rel_path for rel_path, _ in _CONSUMERS}
    missing = _D8_RENDERING_MODULES - pinned_modules
    assert not missing, f"D8 consumer module(s) with no pinned function: {sorted(missing)}"
    assert "src/specify_cli/cli/commands/agent/tracer_append.py" in pinned_modules, "WP10's tracer-append CLI is part of the floor (R-M2)"
    assert not any(rel_path.endswith("tasks_mark_status.py") for rel_path in pinned_modules), (
        "mark-status commits nothing (its _ms_commit shim is dead); it is not a consumer"
    )


def test_every_pinned_consumer_resolves_and_renders_through_the_shared_contract() -> None:
    violations = _collect_consumer_violations(_CONSUMERS)
    assert not violations, (
        "commit-outcome consumers must render through render_commit_outcome / commit_outcome_payload and never "
        "format a SurfaceOutcome by hand (contracts/commit-outcome.md rule 6). A stale qualname means a consumer "
        "was renamed: re-point the pin, never delete it to green.\n" + "\n".join(v.describe() for v in violations)
    )


def test_every_helper_consumer_still_calls_its_surface_helper() -> None:
    violations = _helper_caller_violations(_HELPER_CALLERS)
    assert not violations, "\n".join(v.describe() for v in violations)


def test_helper_callers_name_a_pinned_helper() -> None:
    """A helper caller that names an UNPINNED helper would be an unchecked renderer."""
    pinned = {(rel_path, qualname) for rel_path, qualname in _CONSUMERS}
    for rel_path, _caller, helper in _HELPER_CALLERS:
        assert (rel_path, helper) in pinned, f"{rel_path}::{helper} is called as a surface helper but is not in _CONSUMERS"


@pytest.mark.parametrize("rel_path", _PASS_THROUGH_WRAPPER_MODULES)
def test_pass_through_wrapper_modules_do_not_hand_format_surfaces(rel_path: str) -> None:
    """``WriteSeamResult`` / ``CommitArtifactResult`` only carry ``surfaces``; their callers render."""
    tree = parse_source(read_source(_REPO_ROOT / rel_path), display=rel_path)
    assert _hand_formatted_fields(tree) == set()


# ---------------------------------------------------------------------------
# Bite tests: the pin is not inert.
# ---------------------------------------------------------------------------

_SYNTHETIC_REL_PATH = "src/specify_cli/synthetic.py"

_GOOD_CONSUMER = "def _consumer(result):\n    for line in render_commit_outcome(result):\n        print(line)\n    return commit_outcome_exit_code(result)\n"


def _synthetic_problems(source: str) -> list[str]:
    return [v.problem for v in _consumer_violations_in_source(source, _SYNTHETIC_REL_PATH, "_consumer")]


def test_a_conforming_consumer_is_clean() -> None:
    assert _synthetic_problems(_GOOD_CONSUMER) == []
    payload_consumer = "def _consumer(result):\n    return {**commit_outcome_payload(result)}\n"
    assert _synthetic_problems(payload_consumer) == []


def test_bite_a_hand_formatting_consumer_that_never_calls_the_renderer_is_flagged() -> None:
    """The WP20 plant: ``f"{outcome.refused}"`` with no shared-renderer call."""
    source = 'def _consumer(result):\n    for outcome in result.surfaces:\n        print(f"{outcome.refused}")\n'
    problems = _synthetic_problems(source)
    assert any("does not call" in problem for problem in problems), problems
    assert any("hand-formats surface field(s) ['refused']" in problem for problem in problems), problems


@pytest.mark.parametrize(
    "formatting",
    [
        'print(f"{outcome.committed}")',
        'print("skipped: {}".format(outcome.skipped))',
        'print(f"{len(outcome.refused)} refused")',
    ],
)
def test_bite_hand_formatting_is_flagged_even_alongside_a_renderer_call(formatting: str) -> None:
    source = f"def _consumer(result):\n    render_commit_outcome(result)\n    for outcome in result.surfaces:\n        {formatting}\n"
    problems = _synthetic_problems(source)
    assert problems and all("hand-formats" in problem for problem in problems), problems


def test_bite_a_companion_exit_code_call_alone_is_not_rendering() -> None:
    source = "def _consumer(result):\n    return commit_outcome_exit_code(result)\n"
    problems = _synthetic_problems(source)
    assert problems and "companion exit-code call is not enough" in problems[0]


def test_bite_a_missing_consumer_definition_is_reported_not_skipped() -> None:
    violations = _consumer_violations_in_source("def _other():\n    pass\n", _SYNTHETIC_REL_PATH, "_consumer")
    assert [v.problem for v in violations] == ["no single live definition"]


def test_bite_a_caller_that_stops_calling_its_helper_is_flagged(tmp_path: Path) -> None:
    module = tmp_path / "pkg" / "cmd.py"
    module.parent.mkdir()
    module.write_text(
        "def _caller(result):\n    return result\ndef _calls_helper(result):\n    _warn(result)\n",
        encoding="utf-8",
    )
    violations = _helper_caller_violations(
        (("pkg/cmd.py", "_caller", "_warn"), ("pkg/cmd.py", "_calls_helper", "_warn"), ("pkg/cmd.py", "_gone", "_warn")),
        repo_root=tmp_path,
    )
    assert [(v.qualname, v.problem) for v in violations] == [
        ("_caller", "does not call its surface helper _warn()"),
        ("_gone", "no single live definition"),
    ]


def test_surface_field_reads_outside_a_formatting_construct_are_not_hand_formatting() -> None:
    """Counting or iterating a surface's paths is logic, not formatting."""
    source = "def _consumer(result):\n    render_commit_outcome(result)\n    return [len(outcome.committed) for outcome in result.surfaces if outcome.refused]\n"
    assert _synthetic_problems(source) == []


def test_prose_quoting_a_hand_formatted_outcome_is_inert() -> None:
    """A docstring or comment is a ``Constant``, never an f-string: quoting the anti-pattern is fine."""
    source = (
        "def _consumer(result):\n"
        '    """Never write f"{outcome.refused}" by hand."""\n'
        '    # not f"{outcome.skipped}" either\n'
        "    return render_commit_outcome(result)\n"
    )
    assert _synthetic_problems(source) == []


def test_find_function_resolves_methods_and_rejects_ambiguity() -> None:
    tree = parse_source(
        "class Owner:\n    def method(self):\n        pass\ndef twice():\n    pass\ndef twice():\n    pass\n",
        display="<lookup>",
    )
    assert _find_function(tree, "Owner.method") is not None
    assert _find_function(tree, "Owner.absent") is None
    assert _find_function(tree, "Absent.method") is None
    assert _find_function(tree, "twice") is None
