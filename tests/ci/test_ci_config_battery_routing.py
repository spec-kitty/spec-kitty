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

from scripts.ci.gate_selection import DEFAULT_ROUTER_PATH, Router, load_router, select_gates, select_modules
from scripts.ci.prose_only import prose_only_pr_verdict
from tests.architectural import _ci_integrity_oracle as oracle

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
    "path",
    [
        pytest.param("docs/x.md", id="docs-only"),
        pytest.param("uv.lock", id="uv.lock"),
        pytest.param("tests/conftest.py", id="tests/conftest.py"),
        pytest.param("packs/built-in/missions/foo.md", id="packs-prose"),
    ],
)
def test_out_of_scope_paths_still_skip_the_battery(router: Router, path: str) -> None:
    """``uv.lock`` and ``tests/conftest.py`` are deliberately outside ``ci_config`` (D-09)."""
    selection = select_gates([path], router=router)

    assert _HEAVY not in selection.selected_jobs
    assert _GROUP not in selection.matched_groups


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


def test_ci_config_is_a_top_level_changes_output_with_the_non_src_fold() -> None:
    """The output folds like ``architectural``; it never reads the push event."""
    match = re.search(r"^\s+ci_config: (\$\{\{.*\}\})$", _ROUTER_TEXT, re.MULTILINE)

    assert match, "ci-router.yml `changes.outputs` must expose ci_config"
    fold = match.group(1)
    assert "inputs.mode == 'full'" in fold
    assert "steps.unmatched.outputs.unmatched == 'true'" in fold
    assert "steps.filter.outputs.ci_config" in fold
    assert "github.event_name" not in fold


def test_unmapped_src_change_still_runs_everything_with_ci_config_selected(router: Router) -> None:
    """C-008: an unmatched ``src/`` path stays fail-closed run-all, including ``ci_config``."""
    selection = select_gates(["src/zz_unmapped_package/module.py"], router=router)

    assert selection.unmatched_src
    assert _HEAVY in selection.selected_jobs
    assert selection.selected_code_shards >= router.code_shard_jobs


def test_battery_if_keeps_the_prose_only_conjunct_as_the_single_outer_and() -> None:
    """C-002: the OR grows by one term; the subtraction stays the one outer AND."""
    condition = _battery_condition()

    assert condition.count("needs.prose-scan.outputs.prose_only != 'true'") == 1
    assert re.search(r"\)\s*&&\s*needs\.prose-scan\.outputs\.prose_only != 'true'\s*$", condition)
    assert "needs.changes.outputs.ci_config == 'true'" in condition


def _battery_condition() -> str:
    workflow = yaml.safe_load(_ROUTER_TEXT)
    return str(workflow["jobs"][_HEAVY]["if"])


def test_proven_prose_only_ci_script_is_still_subtracted_but_config_files_never_are(router: Router) -> None:
    """C-002: a docstring-only ``scripts/ci/*.py`` is prose-only (the battery's
    ``prose_only != 'true'`` conjunct then drops the battery, exactly as for ``src/``);
    workflow YAML, ``pytest.ini``, ``pyproject.toml`` and the ``Makefile`` are never prose-only.
    """
    doc_globs = [*router.filters["docs"], *router.filters["corpus"]]

    def blobs(path: str, side: str) -> str | None:
        return _PROSE_BASE if side == "base" else _PROSE_HEAD

    assert prose_only_pr_verdict(["scripts/ci/some_helper.py"], blobs, doc_globs) is True
    for config_only in (".github/workflows/ci-router.yml", "pytest.ini", "pyproject.toml", "Makefile"):
        assert prose_only_pr_verdict([config_only], blobs, doc_globs) is False, config_only


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
    assert frozenset({"architectural", _GROUP}) == oracle.HEAVY_BATTERY_NON_SRC_GROUPS
    monkeypatch.setattr(oracle, "HEAVY_BATTERY_NON_SRC_GROUPS", frozenset({"architectural"}))

    with pytest.raises(oracle.MustRunGateUnwiredError, match=_GROUP):
        oracle.assert_must_run_gates_wired(router)


def test_dropping_ci_config_from_the_battery_gate_set_reds_the_oracle(router: Router) -> None:
    """Positive control modelled on ``test_heavy_battery_losing_a_non_src_group_reds_the_oracle``."""
    job_gates = dict(router.job_gates)
    job_gates[oracle.HEAVY_BATTERY_GATE] = router.job_gates[oracle.HEAVY_BATTERY_GATE] - {_GROUP}
    drifted = Router(filters=router.filters, job_gates=job_gates)

    with pytest.raises(oracle.MustRunGateUnwiredError, match=_GROUP):
        oracle.assert_must_run_gates_wired(drifted)
