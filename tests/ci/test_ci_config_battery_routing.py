"""FR-007 / SC-006: a CI-configuration-only diff selects the architectural battery.

Mission ``ci-runtime-stabilisation-01M3TZH6``, WP07. Before this mission a PR
that edited only CI configuration (a workflow, a composite action, a
``scripts/ci/`` helper, ``pytest.ini``, ``pyproject.toml``, the ``Makefile``, the
module registry or the shard timings) matched no src-backed group, so the heavy
architectural battery -- whose gates guard exactly those files -- first ran after
merge. The non-src ``ci_config`` filter group (contract amendment A1,
``kitty-specs/ci-runtime-stabilisation-01M3TZH6/contracts/router-two-authority-amendment.md``)
closes that gap.

Every answer here comes from the single gate-selection authority
(:func:`scripts.ci.gate_selection.select_gates`) parsing the REAL
``ci-router.yml``. The probe paths are probes only: no glob is hand-encoded as a
path-group map (the #2476 hazard). The mutation tests rewrite a tmp copy of the
live workflow and prove each pin goes red under the obvious drop:

* dropping the ``ci_config`` term from the battery ``if:``;
* dropping the ``ci_config`` filter group;
* dropping ``ci_config`` from ``HEAVY_BATTERY_NON_SRC_GROUPS``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from scripts.ci.gate_selection import DEFAULT_ROUTER_PATH, Router, load_router, select_battery_gates, select_gates, select_modules
from scripts.ci.prose_only import prose_only_pr_verdict
from tests.architectural import _ci_integrity_oracle as oracle
from tests.ci._gh_if import eval_gh_if, eval_gh_value

pytestmark = pytest.mark.fast

_HEAVY = "architectural-heavy"
_GROUP = "ci_config"

#: One probe path per ``ci_config`` glob (D-09), keyed by a human-readable id.
_CI_CONFIG_PROBES = [
    pytest.param(".github/workflows/ci-aggregate.yml", id=".github/workflows/**"),
    pytest.param(".github/actions/warmup/action.yml", id=".github/actions/**"),
    pytest.param("scripts/ci/gate_selection.py", id="scripts/ci/**"),
    pytest.param("pytest.ini", id="pytest.ini"),
    pytest.param("pyproject.toml", id="pyproject.toml"),
    pytest.param("Makefile", id="Makefile"),
    pytest.param(".github/ci-module-registry.yml", id="ci-module-registry.yml"),
    pytest.param(".github/ci-shard-timings.json", id="ci-shard-timings.json"),
]

#: Probes whose module selection is the ``ci`` registry row (its roots are
#: ``scripts/ci/**`` + ``.github/workflows/**``); every other ``ci_config`` glob
#: selects no module -- the module matrix is deliberately not widened.
_CI_MODULE_PROBES = frozenset({".github/workflows/ci-aggregate.yml", "scripts/ci/gate_selection.py"})

_ROUTER_TEXT = DEFAULT_ROUTER_PATH.read_text(encoding="utf-8")

_BATTERY_TERM_RE = re.compile(r"^[ \t]+needs\.changes\.outputs\.ci_config == 'true' \|\|\n", re.MULTILINE)
_FILTER_GROUP_RE = re.compile(r"^[ \t]+ci_config:\n(?:[ \t]+- '[^']*'\n)+", re.MULTILINE)

_PROSE_BASE = '"""Old docstring."""\n\n\ndef f(x):\n    return x + 1\n'
_PROSE_HEAD = '"""New docstring, no code change."""\n\n\ndef f(x):\n    return x + 1\n'


@pytest.fixture(scope="module")
def router() -> Router:
    return load_router()


def _mutated_router(tmp_path: Path, pattern: re.Pattern[str]) -> Router:
    """A router parsed from a tmp copy of the live workflow with ``pattern`` removed."""
    mutated, count = pattern.subn("", _ROUTER_TEXT)
    assert count == 1, f"mutation {pattern.pattern!r} must match exactly once in the live ci-router.yml, matched {count}"
    target = tmp_path / "ci-router.yml"
    target.write_text(mutated, encoding="utf-8")
    return load_router(target)


@pytest.mark.parametrize("path", _CI_CONFIG_PROBES)
def test_ci_config_only_diff_selects_the_heavy_battery(router: Router, path: str) -> None:
    selection = select_gates([path], router=router)

    assert _HEAVY in selection.selected_jobs
    assert _HEAVY in selection.selected_code_shards
    assert _GROUP in selection.matched_groups
    assert not selection.unmatched_src


@pytest.mark.parametrize("path", _CI_CONFIG_PROBES)
def test_ci_config_leaves_the_module_selection_unchanged(router: Router, path: str) -> None:
    expected = frozenset({"ci"}) if path in _CI_MODULE_PROBES else frozenset()

    assert select_modules([path], router=router) == expected


@pytest.mark.parametrize(
    ("path", "battery"),
    [
        pytest.param("docs/x.md", "scoped", id="docs-only"),
        pytest.param("uv.lock", "none", id="uv.lock"),
        pytest.param("tests/conftest.py", "whole", id="tests/conftest.py"),
        pytest.param("packs/built-in/missions/foo.md", "scoped", id="packs-prose"),
    ],
)
def test_out_of_scope_paths_stay_outside_ci_config(router: Router, path: str, battery: str) -> None:
    """``uv.lock`` and ``tests/conftest.py`` are deliberately outside ``ci_config`` (D-09).

    Since #6994 a path some battery gate reads selects the battery through ``arch_scan_scope``: a
    scoped run of those gates, or the whole battery for battery code such as ``tests/conftest.py``.
    """
    selection = select_gates([path], router=router)

    assert _GROUP not in selection.matched_groups
    assert (_HEAVY in selection.selected_jobs) is (battery != "none")
    if battery != "none":
        assert (select_battery_gates([path], router=router) is None) is (battery == "whole")


def test_ci_config_is_non_src_and_outside_the_catch_all(router: Router) -> None:
    assert _GROUP in router.routing_groups
    assert _GROUP not in router.src_backed_groups
    assert router.job_gates[_HEAVY] >= {_GROUP}


def test_ci_config_gates_only_the_battery() -> None:
    """Contract A1: ``ci_config`` gates ONLY the architectural battery -- no other router job.

    Compares the raw ``if:`` text of every router job (not the parsed group model), so a
    job gated on ``ci_config`` in any spelling is caught; the ``changes`` job's own
    ``outputs`` fold is not an ``if:`` and is out of scope here.
    """
    jobs = yaml.safe_load(_ROUTER_TEXT)["jobs"]
    gated = {name for name, job in jobs.items() if _GROUP in str(job.get("if", ""))}

    assert gated == {_HEAVY}
    # WP08 out-of-map companion (WP07's review): the parsed model must agree with the raw text.
    assert {job for job, groups in load_router().job_gates.items() if _GROUP in groups} == gated


def _ci_config_fold_expr(text: str = _ROUTER_TEXT) -> str:
    """The raw ``changes.outputs.ci_config`` expression from a router workflow text."""
    return str(yaml.safe_load(text)["jobs"]["changes"]["outputs"][_GROUP])


def _fold_context(mode: str, unmatched: str, filter_value: str) -> dict[str, str]:
    return {
        "inputs.mode": mode,
        "steps.unmatched.outputs.unmatched": unmatched,
        f"steps.filter.outputs.{_GROUP}": filter_value,
    }


#: One truth-table row: the three inputs the fold reads and the output GitHub must produce.
_FoldRow = tuple[str, str, str, str]


def _fold_rows() -> list[_FoldRow]:
    """Every input combination: full mode, the unmatched catch-all, the ci_config filter verdict."""
    return [
        (mode, unmatched, flt, "true" if (mode == "full" or unmatched == "true") else flt)
        for mode in ("full", "pr", "")
        for unmatched in ("true", "false")
        for flt in ("true", "false")
    ]


_FOLD_ROWS = _fold_rows()
_FOLD_PARAMS = [pytest.param(*row, id=f"mode={row[0] or 'empty'}-unmatched={row[1]}-filter={row[2]}") for row in _FOLD_ROWS]


@pytest.mark.parametrize(("mode", "unmatched", "filter_value", "expected"), _FOLD_PARAMS)
def test_ci_config_output_folds_like_architectural_semantically(mode: str, unmatched: str, filter_value: str, expected: str) -> None:
    """Full mode or an unmatched src change forces ``true``; otherwise the filter verdict passes through.

    Evaluated with GitHub value semantics (not substring checks), so ``||`` -> ``&&`` or a dropped
    term goes red. The context models no ``github.event_name``: an expression that starts reading
    the push event fails the evaluator's unmodeled-context assertion (the fold never reads it).
    """
    context = _fold_context(mode, unmatched, filter_value)

    assert eval_gh_value(_ci_config_fold_expr(), context) == expected


def test_ci_config_fold_matches_the_architectural_fold_on_the_whole_truth_table() -> None:
    """The sibling non-src group folds identically (the A1 ``like architectural`` claim, semantically)."""
    outputs = yaml.safe_load(_ROUTER_TEXT)["jobs"]["changes"]["outputs"]
    for mode, unmatched, flt, _expected in _FOLD_ROWS:
        ci_config = eval_gh_value(str(outputs[_GROUP]), _fold_context(mode, unmatched, flt))
        arch_context = {**_fold_context(mode, unmatched, flt), "steps.filter.outputs.architectural": flt}
        assert ci_config == eval_gh_value(str(outputs["architectural"]), arch_context)


@pytest.mark.parametrize("which", [0, 1], ids=["inner-or", "outer-or"])
def test_ci_config_fold_or_to_and_mutation_is_caught_by_the_truth_table(which: int) -> None:
    """Mutation control: turning either ``||`` of the live fold into ``&&`` must disagree with the table."""
    live = _ci_config_fold_expr()
    positions = [match.start() for match in re.finditer(re.escape("||"), live)]
    assert len(positions) == 2, "the fold has exactly two || operators"
    cut = positions[which]
    mutated = live[:cut] + "&&" + live[cut + 2 :]
    disagreements = [row for row in _FOLD_ROWS if eval_gh_value(mutated, _fold_context(*row[:3])) != row[3]]

    assert disagreements, "the truth table must go red when a || of the fold becomes &&"


def test_unmapped_src_change_still_runs_everything_with_ci_config_selected(router: Router) -> None:
    """C-008: an unmatched ``src/`` path stays fail-closed run-all, including ``ci_config``."""
    selection = select_gates(["src/zz_unmapped_package/module.py"], router=router)

    assert selection.unmatched_src
    assert _HEAVY in selection.selected_jobs
    assert selection.selected_code_shards >= router.code_shard_jobs


def test_battery_if_keeps_the_prose_only_conjunct_as_the_single_outer_and() -> None:
    """C-002 + #6999 (operator ruling 2026-11-01): the OR grows by one term; the prose
    subtraction stays the one outer ``&&`` but is EXEMPTED for a declared scan-scope match.
    """
    condition = _battery_condition()

    assert condition.count("needs.prose-scan.outputs.prose_only != 'true'") == 1
    # The subtraction is still the single outer AND, now a two-term guard: prose subtracts the
    # battery unless the diff touches a declared scan scope (#6999).
    assert re.search(
        r"\)\s*&&\s*\(\s*needs\.prose-scan\.outputs\.prose_only != 'true' \|\|\s*needs\.prose-scan\.outputs\.scan_scope_match == 'true'\s*\)\s*$",
        condition,
    ), condition
    assert "needs.changes.outputs.ci_config == 'true'" in condition


def _condition_context(prose_only: bool, scan_scope: bool) -> dict[str, bool]:
    """Every output the battery ``if:`` reads, defaulted false, with the two prose inputs set.

    ``scan_scope`` is prose-scan's ``scan_scope_match`` companion output (#6999): the same parsed
    ``arch_scan_scope`` globs, evaluated in the job that already holds the diff. Keeping it out of
    ``needs.changes.outputs.*`` leaves the battery ``if:`` naming that group exactly once, so the
    #6994 planted control (drop the group's OR term) still reds.
    """
    context = {f"{job}.{name}": False for job, name in _CONTEXT_OUTPUTS}
    # The routing half: a diff that touches a declared scan scope selects the battery through the
    # `arch_scan_scope` group, so the group term is lit in every row and only the prose guard varies.
    context["changes.arch_scan_scope"] = True
    context["prose-scan.prose_only"] = prose_only
    context["prose-scan.scan_scope_match"] = scan_scope
    return context


def test_the_prose_only_exemption_runs_the_battery_only_for_a_declared_scan_scope_match() -> None:
    """#6999: the ruling's truth table, evaluated on the REAL ``if:`` string.

    Operator ruling 2026-11-01: a prose-only diff still skips the battery as a whole, but every
    gate whose declared ``scan_scopes`` entry matches runs (the ``arch_scan_scope`` group is the
    test-pinned transcription of those declarations).
    """
    condition = _battery_condition()

    # Group lit (declared scope routed) in every row; the prose guard is what varies.
    assert eval_gh_if(condition, _condition_context(prose_only=True, scan_scope=True)) is True, "declared prose match keeps the battery"
    assert eval_gh_if(condition, _condition_context(prose_only=True, scan_scope=False)) is False, "prose with no declared match is still down-routed"
    assert eval_gh_if(condition, _condition_context(prose_only=False, scan_scope=True)) is True, "code PR unchanged"
    assert eval_gh_if(condition, _condition_context(prose_only=False, scan_scope=False)) is True, "code PR unchanged (#6994)"


def test_dropping_the_prose_only_scan_scope_exemption_reds_the_ruling_truth_table() -> None:
    """Planted control (#6999, SC-004): reverting the exemption must make the prose half fail."""
    exempted = _battery_condition()
    reverted, count = re.subn(
        r"\)\s*&&\s*\(\s*needs\.prose-scan\.outputs\.prose_only != 'true' \|\|\s*needs\.prose-scan\.outputs\.scan_scope_match == 'true'\s*\)\s*$",
        ") && needs.prose-scan.outputs.prose_only != 'true'\n",
        exempted,
    )
    assert count == 1, "the exemption must be one replaceable guard, so the control cannot silently no-op"
    context = _condition_context(prose_only=True, scan_scope=True)

    assert eval_gh_if(exempted, context) is True, "the shipped if: must run the battery for a declared prose match"
    assert eval_gh_if(reverted, context) is False, "the reverted subtraction must drop the battery, or this control is vacuous"


def _battery_condition() -> str:
    workflow = yaml.safe_load(_ROUTER_TEXT)
    return str(workflow["jobs"][_HEAVY]["if"])


#: Every ``needs.<job>.outputs.<name>`` the battery ``if:`` reads, so the truth tables above are
#: explicit about their context instead of relying on a helper's defaults.
_CONTEXT_OUTPUTS = tuple((match.group(1), match.group(2)) for match in re.finditer(r"needs\.([A-Za-z0-9_-]+)\.outputs\.([A-Za-z0-9_]+)", _battery_condition()))


def test_proven_prose_only_ci_script_is_still_scoped_but_config_files_never_are(router: Router) -> None:
    """C-002 + #6999: a docstring-only ``scripts/ci/*.py`` is prose-only, so the battery runs only
    the heavy gates that DECLARE ``scripts/**`` in their scan scope (operator ruling 2026-11-01);
    workflow YAML, ``pytest.ini``, ``pyproject.toml`` and the ``Makefile`` are never prose-only.
    """
    doc_globs = [*router.filters["docs"], *router.filters["corpus"]]

    def blobs(path: str, side: str) -> str | None:
        return _PROSE_BASE if side == "base" else _PROSE_HEAD

    # Not under scripts/ci/** (that is the ci_config code group): a scripts/** path whose only
    # router group is the declared scan scope, so the prose narrowing is what is under test.
    prose_path = "scripts/release/some_helper.py"
    assert prose_only_pr_verdict([prose_path], blobs, doc_globs) is True
    for config_only in (".github/workflows/ci-router.yml", "pytest.ini", "pyproject.toml", "Makefile"):
        assert prose_only_pr_verdict([config_only], blobs, doc_globs) is False, config_only

    # The prose verdict narrows to the declared scanners instead of dropping the battery whole.
    selected = select_battery_gates([prose_path], router=router, prose_only=True)
    assert selected is not None and selected, "a prose-only scripts/ci diff must keep its declared scanners"
    assert selected == select_battery_gates([prose_path], router=router), "a scope-only path keeps exactly its declared matches"
    assert "tests/architectural/test_clock_call_ban.py" in selected


# ---------------------------------------------------------------------------
# Mutation controls: every pin above must go red under the obvious drop.
# ---------------------------------------------------------------------------


def test_dropping_ci_config_from_the_battery_if_stops_selecting_the_battery_and_reds_the_oracle(tmp_path: Path) -> None:
    drifted = _mutated_router(tmp_path, _BATTERY_TERM_RE)

    assert _HEAVY not in select_gates(["pytest.ini"], router=drifted).selected_jobs
    with pytest.raises(oracle.MustRunGateUnwiredError, match=_GROUP):
        oracle.assert_must_run_gates_wired(drifted)


def test_dropping_the_ci_config_filter_group_matches_nothing_and_selects_no_battery(tmp_path: Path, router: Router) -> None:
    """Without the filter group a CI-config path matches no group (the ``if:`` term alone is inert)."""
    drifted = _mutated_router(tmp_path, _FILTER_GROUP_RE)

    for path in ("pytest.ini", "pyproject.toml", "Makefile", ".github/actions/warmup/action.yml"):
        assert _GROUP in select_gates([path], router=router).matched_groups
        selection = select_gates([path], router=drifted)
        assert _GROUP not in selection.matched_groups
        assert _HEAVY not in selection.selected_jobs


def test_dropping_ci_config_from_the_oracle_constant_reds_the_live_router(router: Router, monkeypatch: pytest.MonkeyPatch) -> None:
    """The exact-equality oracle must reject the live router once the constant forgets ``ci_config``."""
    assert frozenset({"architectural", _GROUP, "arch_scan_scope"}) == oracle.HEAVY_BATTERY_NON_SRC_GROUPS
    monkeypatch.setattr(oracle, "HEAVY_BATTERY_NON_SRC_GROUPS", frozenset({"architectural", "arch_scan_scope"}))

    with pytest.raises(oracle.MustRunGateUnwiredError, match=_GROUP):
        oracle.assert_must_run_gates_wired(router)


def test_dropping_ci_config_from_the_battery_gate_set_reds_the_oracle(router: Router) -> None:
    """Positive control modelled on ``test_heavy_battery_losing_a_non_src_group_reds_the_oracle``."""
    job_gates = dict(router.job_gates)
    job_gates[oracle.HEAVY_BATTERY_GATE] = router.job_gates[oracle.HEAVY_BATTERY_GATE] - {_GROUP}
    drifted = Router(filters=router.filters, job_gates=job_gates)

    with pytest.raises(oracle.MustRunGateUnwiredError, match=_GROUP):
        oracle.assert_must_run_gates_wired(drifted)
