"""Pin the shape of the pre-test collection step in the consuming workflows.

Mission shared-collection-and-shard-recapture-01M42V58, WP03 (FR-008, FR-009, NFR-001..003, C-010).

Two jobs run a test that collects the test universe: the heavy architectural battery legs
(``ci-router.yml`` job ``architectural-heavy``) and the module shard that selects
``tests/ci/test_corpus_blocking_home.py`` (``module-tests.yml`` job ``test``). Each collects once in
a step before pytest, restores the store on a re-run, and fails when a later request fell back to a
collection of its own. Each does so only when it holds a test that collects: a ``select`` step
writes ``universe=true|false`` to the step output and every later universe step is guarded on it
(a battery leg asks ``collect_universe_prestep consumers``; the module shard greps its test list).
``ci-nightly.yml`` carries one job that proves a stored universe equals a fresh one. The shape
(``contracts/collection-store.md``, "Workflow shape"):

    select (universe=true|false) -> compute key -> restore store (guarded on a non-empty key)
    -> ``collect`` -> save store -> pytest (unchanged) -> ``check`` with ``if: always()``

All steps after ``select`` carry the ``select`` guard.

Every rule is a pure function of one parsed job, so each mutation test feeds a broken copy of the
same job to the same function the real-workflow test uses.
"""

from __future__ import annotations

import copy
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tests.architectural._gate_coverage import load_spliced_workflow

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOWS = _REPO_ROOT / ".github" / "workflows"
_ROUTER = _WORKFLOWS / "ci-router.yml"
_MODULE_TESTS = _WORKFLOWS / "module-tests.yml"
_NIGHTLY = _WORKFLOWS / "ci-nightly.yml"

_HEAVY_JOB = "architectural-heavy"
_MODULE_JOB = "test"
_NIGHTLY_JOB = "universe-equivalence"
_SUMMARY_JOB = "nightly-summary"

_CACHE_SHA = "55cc8345863c7cc4c66a329aec7e433d2d1c52a9"
_CACHE_VERSION_COMMENT = "# v6.1.0"
_STORE_PATH = ".pytest_cache/universe-store"
_REPORT_ENV = "SK_GATE_REUSE_REPORT"
_REPORT_FILE = "universe-reuse.jsonl"
_UNIVERSE_GUARD = "steps.select.outputs.universe == 'true'"
_CORE_REPOSITORY_GUARD = "github.repository == 'spec-kitty/spec-kitty'"
_CONSUMING_FILE = "tests/ci/test_corpus_blocking_home.py"
_CONSUMING_TEST = "test_every_corpus_test_has_a_blocking_per_pr_home"
_CONSUMING_NODE = f"{_CONSUMING_FILE}::{_CONSUMING_TEST}"

_PRESTEP = r"-m scripts\.ci\.collect_universe_prestep"
_KEY_RE = re.compile(rf"{_PRESTEP} key\b")
_KEY_WITH_COMMIT_RE = re.compile(rf"{_PRESTEP} key --with-commit\b")
_COLLECT_RE = re.compile(rf"{_PRESTEP} collect\b")
_CHECK_RE = re.compile(rf"{_PRESTEP} check\b")
_CONSUMERS_RE = re.compile(rf"{_PRESTEP} consumers --battery-part \${{{{ matrix\.shard }}}}")
_COMPARE_RE = re.compile(rf"{_PRESTEP} compare\b")
_PYTEST_RE = re.compile(r"-m pytest\b")
_DECISION_ID = "select"
_RESTORE_PREFIX = f"actions/cache/restore@{_CACHE_SHA}"
_SAVE_PREFIX = f"actions/cache/save@{_CACHE_SHA}"

# What must never appear in the pytest step: the pre-step is a separate step, and the job's pytest
# command line is byte-identical to the one the neighbouring wiring tests already pin.
_FORBIDDEN_IN_PYTEST_STEP = ("collect_universe_prestep", "universe", "--collect-only", "-p no:cacheprovider")

Job = dict[str, Any]
Step = dict[str, Any]


def _jobs(path: Path) -> dict[str, Job]:
    loaded = load_spliced_workflow(path)
    assert isinstance(loaded, dict)
    return loaded["jobs"]


def _run(step: Step) -> str:
    return str(step.get("run", ""))


def _find(job: Job, predicate: Callable[[Step], bool]) -> list[int]:
    return [index for index, step in enumerate(job["steps"]) if predicate(step)]


def _one(job: Job, predicate: Callable[[Step], bool], what: str, problems: list[str]) -> int | None:
    found = _find(job, predicate)
    if len(found) != 1:
        problems.append(f"expected exactly one {what} step, found {len(found)}")
        return None
    return found[0]


def _uses(step: Step, prefix: str) -> bool:
    return str(step.get("uses", "")).startswith(prefix)


def _step_if(step: Step) -> str:
    return str(step.get("if", ""))


def _has_report_env(step: Step) -> bool:
    return _REPORT_FILE in str((step.get("env") or {}).get(_REPORT_ENV, ""))


def _guard_problems(step: Step, label: str, guard: str | None) -> list[str]:
    if guard is not None and guard not in _step_if(step):
        return [f"{label} step is not guarded on the selection condition {guard!r}"]
    return []


def _cache_problems(job: Job, key_index: int, collect_index: int, pytest_index: int, guard: str | None) -> list[str]:
    problems: list[str] = []
    steps = job["steps"]
    key_id = steps[key_index].get("id")
    wanted_key = f"${{{{ steps.{key_id}.outputs.key }}}}"
    restore = _find(job, lambda step: _uses(step, "actions/cache/restore@"))
    save = _find(job, lambda step: _uses(step, "actions/cache/save@"))
    if len(restore) != 1 or len(save) != 1:
        return [f"expected one cache restore and one cache save step, found {len(restore)} and {len(save)}"]
    restore_step, save_step = steps[restore[0]], steps[save[0]]
    if not _KEY_WITH_COMMIT_RE.search(_run(steps[key_index])):
        problems.append("the key step must run `key --with-commit`: a stored record is valid for one commit, and a cache key is immutable")
    if not _uses(restore_step, _RESTORE_PREFIX):
        problems.append(f"the restore step must use {_RESTORE_PREFIX}")
    if not _uses(save_step, _SAVE_PREFIX):
        problems.append(f"the save step must use {_SAVE_PREFIX}")
    if not key_index < restore[0] < collect_index:
        problems.append("the cache restore must sit after the key step and before the pre-step")
    if not collect_index < save[0] < pytest_index:
        problems.append("the cache save must sit between the pre-step and the pytest step, so it never depends on pytest")
    for label, step in (("restore", restore_step), ("save", save_step)):
        options = step.get("with") or {}
        if "restore-keys" in options:
            problems.append(f"the cache {label} step declares restore-keys; only an exact key may restore")
        if options.get("key") != wanted_key:
            problems.append(f"the cache {label} key must be {wanted_key}, got {options.get('key')!r}")
        if options.get("path") != _STORE_PATH:
            problems.append(f"the cache {label} path must be {_STORE_PATH}, got {options.get('path')!r}")
        if "steps." + str(key_id) + ".outputs.key != ''" not in _step_if(step):
            problems.append(f"the cache {label} step is not guarded on a non-empty key")
        problems.extend(_guard_problems(step, f"cache {label}", guard))
    if "cache-hit" not in _step_if(save_step):
        problems.append("the cache save step must skip when the restore hit")
    return problems


def _continue_on_error_problems(job: Job, patterns: tuple[re.Pattern[str], ...]) -> list[str]:
    """A pre-test or check step that may fail without failing the job would turn the check into a summary.

    ``continue-on-error`` is flagged whatever its value: only an absent key (or a literal false)
    keeps the step able to turn the job red.
    """
    problems: list[str] = []
    for step in job["steps"]:
        if not any(pattern.search(_run(step)) for pattern in patterns):
            continue
        flag = step.get("continue-on-error")
        if flag is not None and flag is not False:
            problems.append(f"step {step.get('name')!r} sets continue-on-error: {flag!r}; it could no longer fail the job")
    return problems


def _decision_problems(job: Job, key_index: int) -> list[str]:
    """The ``select`` step: it exists once, runs before the key, writes the output, and cannot be swallowed."""
    found = _find(job, lambda step: step.get("id") == _DECISION_ID)
    if len(found) != 1:
        return [f"expected exactly one step with id {_DECISION_ID!r}, found {len(found)}"]
    step = job["steps"][found[0]]
    problems: list[str] = []
    if not found[0] < key_index:
        problems.append("the select step must run before the key step")
    if "GITHUB_OUTPUT" not in _run(step) or "universe=" not in _run(step):
        problems.append("the select step must write universe=<true|false> to GITHUB_OUTPUT")
    flag = step.get("continue-on-error")
    if flag is not None and flag is not False:
        problems.append(f"the select step sets continue-on-error: {flag!r}; a failed decision must fail the job")
    if "if" in step:
        problems.append("the select step must always run: a skipped decision would leave every universe step off")
    return problems


def _heavy_decision_problems(job: Job) -> list[str]:
    """A battery leg asks the Python authority which files collect; an error must fail the job.

    The decision may not swallow a failure (``|| ...``, ``|| true``): a leg that holds a collecting
    test but silently skipped the pre-step would collect for itself, ``check`` would not run, and
    the reuse would be lost without a signal. Under ``shell: bash`` (``-eo pipefail``) a failing
    command substitution in an assignment fails the step.
    """
    found = _find(job, lambda step: step.get("id") == _DECISION_ID)
    if len(found) != 1:
        return [f"expected exactly one step with id {_DECISION_ID!r}, found {len(found)}"]
    step = job["steps"][found[0]]
    text = _run(step)
    problems: list[str] = []
    if not _CONSUMERS_RE.search(text):
        problems.append("the select step must run `collect_universe_prestep consumers --battery-part ${{ matrix.shard }}`")
    if "||" in text:
        problems.append("the select step must not swallow a failure of the consumers command (`||`)")
    if step.get("shell") != "bash":
        problems.append("the select step must declare `shell: bash` so a failing command fails the step")
    return problems


def _prestep_problems(job: Job, *, selection_guard: str | None) -> list[str]:
    """Every rule of the shape; an empty list means the job is wired as the contract demands."""
    problems: list[str] = []
    steps = job["steps"]
    key = _one(job, lambda step: bool(_KEY_RE.search(_run(step))), "key", problems)
    collect = _one(job, lambda step: bool(_COLLECT_RE.search(_run(step))), "collect", problems)
    check = _one(job, lambda step: bool(_CHECK_RE.search(_run(step))), "check", problems)
    pytest_step = _one(job, lambda step: bool(_PYTEST_RE.search(_run(step))), "pytest", problems)
    if None in (key, collect, check, pytest_step):
        return problems
    assert key is not None and collect is not None and check is not None and pytest_step is not None

    if not collect < pytest_step:
        problems.append("the collect step must run before the pytest step")
    if not check > pytest_step:
        problems.append("the check step must run after the pytest step")
    check_if = _step_if(steps[check])
    if not check_if.startswith("always()"):
        problems.append("the check step must run on a red suite too (if: always())")
    if selection_guard is None and check_if != "always()":
        problems.append(f"the check step's if must be exactly always(), got {check_if!r}")
    problems.extend(_guard_problems(steps[check], "check", selection_guard))
    for label, index in (("key", key), ("collect", collect)):
        problems.extend(_guard_problems(steps[index], label, selection_guard))
    if selection_guard is not None:
        problems.extend(_decision_problems(job, key))
    for label, index in (("collect", collect), ("pytest", pytest_step), ("check", check)):
        if not _has_report_env(steps[index]):
            problems.append(f"the {label} step does not see {_REPORT_ENV} ({_REPORT_FILE})")
    pytest_text = _run(steps[pytest_step])
    problems.extend(f"the pytest step mentions {word!r}; its command line must stay unchanged" for word in _FORBIDDEN_IN_PYTEST_STEP if word in pytest_text)
    problems.extend(_cache_problems(job, key, collect, pytest_step, selection_guard))
    problems.extend(_continue_on_error_problems(job, (_COLLECT_RE, _CHECK_RE)))
    return problems


@pytest.fixture(scope="module")
def heavy_job() -> Job:
    return _jobs(_ROUTER)[_HEAVY_JOB]


@pytest.fixture(scope="module")
def module_job() -> Job:
    return _jobs(_MODULE_TESTS)[_MODULE_JOB]


# ---------------------------------------------------------------------------
# The real workflows
# ---------------------------------------------------------------------------


def test_heavy_battery_legs_collect_once_before_pytest_when_they_hold_a_collecting_test(heavy_job: Job) -> None:
    assert _prestep_problems(heavy_job, selection_guard=_UNIVERSE_GUARD) == []


def test_heavy_battery_leg_asks_the_python_authority_and_cannot_swallow_an_error(heavy_job: Job) -> None:
    assert _heavy_decision_problems(heavy_job) == []


def test_heavy_battery_environment_is_synced_before_the_key_is_computed(heavy_job: Job) -> None:
    sync = _find(heavy_job, lambda step: "uv sync" in _run(step))
    decision = _find(heavy_job, lambda step: step.get("id") == _DECISION_ID)
    assert decision and sync[0] < decision[0], "the decision runs `uv run`, so the environment is synced first"
    key = _find(heavy_job, lambda step: bool(_KEY_RE.search(_run(step))))
    pytest_step = _find(heavy_job, lambda step: bool(_PYTEST_RE.search(_run(step))))
    assert sync and key and pytest_step
    assert sync[0] < key[0] < pytest_step[0]
    assert "-m pytest" not in _run(heavy_job["steps"][sync[0]]), "uv sync and pytest must no longer share a run block (research B-05)"


def test_module_shard_collects_once_before_pytest_when_selected(module_job: Job) -> None:
    assert _prestep_problems(module_job, selection_guard=_UNIVERSE_GUARD) == []


def test_module_shard_decides_from_the_selected_list_and_only_in_pr_mode(module_job: Job) -> None:
    (select,) = [step for step in module_job["steps"] if step.get("id") == "select"]
    text = _run(select)
    assert _CONSUMING_NODE in text, "the pre-step runs only when the selected list holds the consuming test (research D-06)"
    assert "GITHUB_OUTPUT" in text and "universe=" in text
    assert '"$MODE" = "pr"' in text, "a full-mode warm-up may rewrite uv.lock, so the checkout is not clean there"


def test_the_consuming_test_still_exists_and_still_takes_the_universe_fixture() -> None:
    """The selection condition names one test node; a rename must fail here, not silently disable reuse."""
    source = (_REPO_ROOT / _CONSUMING_FILE).read_text(encoding="utf-8")
    signature = re.search(rf"^def {_CONSUMING_TEST}\((?P<args>[^)]*)\)", source, re.MULTILINE)
    assert signature is not None, f"{_CONSUMING_NODE} no longer exists; update the module-tests.yml selection condition"
    assert "live_universe" in signature.group("args")


def test_module_shard_list_is_not_written_inside_the_checkout(module_job: Job) -> None:
    lines = [line for step in module_job["steps"] for line in _run(step).splitlines() if "shard_tests.txt" in line]
    assert lines, "non-vacuity: the shard list file is still used"
    assert all("RUNNER_TEMP" in line for line in lines), f"shard_tests.txt must live in the runner temp directory: {lines}"


def test_module_shard_keeps_the_step_names_the_dual_mode_contract_reads(module_job: Job) -> None:
    names = {step.get("name") for step in module_job["steps"]}
    assert {"Run pytest for this shard", "Upload coverage + xunit artefacts"} <= names


def test_every_universe_cache_use_is_sha_pinned_with_a_version_comment() -> None:
    texts = [path.read_text(encoding="utf-8") for path in (_ROUTER, _MODULE_TESTS)]
    uses = [line for text in texts for line in text.splitlines() if re.search(r"uses:\s*actions/cache/(restore|save)@", line)]
    assert len(uses) == 4, f"expected a restore and a save in each of the two consuming jobs, found {uses}"
    for line in uses:
        assert re.search(rf"@{_CACHE_SHA}\s+{re.escape(_CACHE_VERSION_COMMENT)}\s*$", line), line


def test_nightly_equivalence_job_compares_and_is_summarised() -> None:
    jobs = _jobs(_NIGHTLY)
    job = jobs[_NIGHTLY_JOB]
    runs = "\n".join(_run(step) for step in job["steps"])
    assert _COLLECT_RE.search(runs) and _COMPARE_RE.search(runs)
    assert _CORE_REPOSITORY_GUARD in str(job["if"]), "automated runs are core-repository only (tests/ci/test_fork_guard.py)"
    assert _NIGHTLY_JOB in jobs[_SUMMARY_JOB]["needs"]
    assert isinstance(job.get("timeout-minutes"), int)
    assert any(_has_report_env(step) for step in job["steps"] if _COLLECT_RE.search(_run(step)))
    assert _continue_on_error_problems(job, (_COLLECT_RE, _COMPARE_RE)) == []


# ---------------------------------------------------------------------------
# Self-mutation: a broken copy of the real job must be rejected by the same function
# ---------------------------------------------------------------------------


def _mutated(job: Job, mutate: Callable[[list[Step]], None]) -> Job:
    broken = copy.deepcopy(job)
    mutate(broken["steps"])
    return broken


def _move_after(steps: list[Step], moved: Callable[[Step], bool], anchor: Callable[[Step], bool]) -> None:
    index = next(i for i, step in enumerate(steps) if moved(step))
    step = steps.pop(index)
    steps.insert(next(i for i, other in enumerate(steps) if anchor(other)) + 1, step)


def _is_collect(step: Step) -> bool:
    return bool(_COLLECT_RE.search(_run(step)))


def _is_check(step: Step) -> bool:
    return bool(_CHECK_RE.search(_run(step)))


def _is_pytest(step: Step) -> bool:
    return bool(_PYTEST_RE.search(_run(step)))


def _is_save(step: Step) -> bool:
    return _uses(step, "actions/cache/save@")


def _is_restore(step: Step) -> bool:
    return _uses(step, "actions/cache/restore@")


def _append_to_pytest_run(steps: list[Step], text: str) -> None:
    step = next(step for step in steps if _is_pytest(step))
    step["run"] = _run(step) + text


def _drop_commit_flag(steps: list[Step]) -> None:
    step = next(step for step in steps if _KEY_RE.search(_run(step)))
    step["run"] = _run(step).replace(" --with-commit", "")


def _is_decision(step: Step) -> bool:
    return step.get("id") == _DECISION_ID


def _unguard(steps: list[Step], predicate: Callable[[Step], bool]) -> None:
    """Replace the selection guard with a neutral ``true``: the step would then run on every leg."""
    step = next(step for step in steps if predicate(step))
    step["if"] = _step_if(step).replace(_UNIVERSE_GUARD, "true")


def _is_key(step: Step) -> bool:
    return bool(_KEY_RE.search(_run(step)))


def _drop(steps: list[Step], predicate: Callable[[Step], bool]) -> None:
    steps[:] = [step for step in steps if not predicate(step)]


@pytest.mark.parametrize(
    ("label", "mutate"),
    [
        ("collect step removed", lambda steps: _drop(steps, _is_collect)),
        ("collect moved after pytest", lambda steps: _move_after(steps, _is_collect, _is_pytest)),
        ("check step removed", lambda steps: _drop(steps, _is_check)),
        ("check moved before pytest", lambda steps: steps.insert(0, steps.pop(next(i for i, s in enumerate(steps) if _is_check(s))))),
        ("check loses if: always()", lambda steps: next(s for s in steps if _is_check(s)).pop("if", None)),
        ("save moved after pytest", lambda steps: _move_after(steps, _is_save, _is_pytest)),
        ("save removed", lambda steps: _drop(steps, _is_save)),
        ("restore removed", lambda steps: _drop(steps, _is_restore)),
        ("restore moved after the pre-step", lambda steps: _move_after(steps, _is_restore, _is_collect)),
        ("restore gains restore-keys", lambda steps: next(s for s in steps if _is_restore(s))["with"].update({"restore-keys": "universe-"})),
        ("restore loses its non-empty-key guard", lambda steps: next(s for s in steps if _is_restore(s)).pop("if", None)),
        ("restore no longer keys on the key step", lambda steps: next(s for s in steps if _is_restore(s))["with"].update({"key": "universe-fixed"})),
        ("key step loses the commit", lambda steps: _drop_commit_flag(steps)),
        ("pre-step loses the report variable", lambda steps: next(s for s in steps if _is_collect(s)).pop("env", None)),
        ("pytest gains a pre-step flag", lambda steps: _append_to_pytest_run(steps, " --collect-only")),
        ("decision step removed", lambda steps: _drop(steps, _is_decision)),
        ("decision moved after the key step", lambda steps: _move_after(steps, _is_decision, _is_key)),
        ("decision may fail without failing the job", lambda steps: next(s for s in steps if _is_decision(s)).update({"continue-on-error": True})),
        ("decision no longer writes the output", lambda steps: next(s for s in steps if _is_decision(s)).update({"run": "true"})),
        ("decision is skipped on some legs", lambda steps: next(s for s in steps if _is_decision(s)).update({"if": "matrix.shard == '1/2'"})),
        ("key step loses the decision guard", lambda steps: _unguard(steps, _is_key)),
        ("restore loses the decision guard", lambda steps: _unguard(steps, _is_restore)),
        ("collect loses the decision guard", lambda steps: _unguard(steps, _is_collect)),
        ("save loses the decision guard", lambda steps: _unguard(steps, _is_save)),
        ("check loses the decision guard", lambda steps: _unguard(steps, _is_check)),
    ],
)
def test_a_broken_heavy_job_is_rejected(heavy_job: Job, label: str, mutate: Callable[[list[Step]], None]) -> None:
    assert _prestep_problems(_mutated(heavy_job, mutate), selection_guard=_UNIVERSE_GUARD), label


@pytest.mark.parametrize(
    ("label", "mutate"),
    [
        ("consumers command removed", lambda step: step.update({"run": step["run"].replace("consumers", "key")})),
        ("failure swallowed by || echo false", lambda step: step.update({"run": step["run"] + ' || echo "universe=false" >> "$GITHUB_OUTPUT"'})),
        ("failure swallowed by || true", lambda step: step.update({"run": step["run"].replace(')"\n', ')" || true\n', 1)})),
        ("shell not bash", lambda step: step.pop("shell", None)),
        ("not asked per leg", lambda step: step.update({"run": step["run"].replace("${{ matrix.shard }}", "1/2")})),
    ],
)
def test_a_heavy_decision_that_could_hide_an_error_is_rejected(heavy_job: Job, label: str, mutate: Callable[[Step], None]) -> None:
    assert _heavy_decision_problems(heavy_job) == [], "control: the unmutated job is accepted"
    broken = copy.deepcopy(heavy_job)
    mutate(next(step for step in broken["steps"] if _is_decision(step)))
    assert _heavy_decision_problems(broken), label


def test_a_module_check_without_the_selection_condition_is_rejected(module_job: Job) -> None:
    def unguard(steps: list[Step]) -> None:
        next(step for step in steps if _is_check(step))["if"] = "always()"

    assert _prestep_problems(_mutated(module_job, unguard), selection_guard=_UNIVERSE_GUARD)


def test_a_module_shard_list_inside_the_checkout_is_rejected() -> None:
    def violations(lines: list[str]) -> list[str]:
        return [line for line in lines if "shard_tests.txt" in line and "RUNNER_TEMP" not in line]

    assert violations(["--out shard_tests.txt"]) == ["--out shard_tests.txt"]
    assert violations(['--out "$RUNNER_TEMP/shard_tests.txt"']) == []


@pytest.mark.parametrize("value", [True, "true", "${{ always() }}"], ids=["boolean", "string", "expression"])
@pytest.mark.parametrize("pattern", [_COLLECT_RE, _CHECK_RE], ids=["collect", "check"])
def test_a_consuming_job_step_that_may_fail_without_failing_the_job_is_rejected(heavy_job: Job, module_job: Job, pattern: re.Pattern[str], value: object) -> None:
    for job, guard in ((heavy_job, _UNIVERSE_GUARD), (module_job, _UNIVERSE_GUARD)):
        assert _prestep_problems(job, selection_guard=guard) == [], "control: the unmutated job is accepted"
        broken = _mutated(job, lambda steps: next(step for step in steps if pattern.search(_run(step))).update({"continue-on-error": value}))
        assert any("continue-on-error" in problem for problem in _prestep_problems(broken, selection_guard=guard))


def test_a_nightly_compare_step_that_may_fail_without_failing_the_job_is_rejected() -> None:
    job = _jobs(_NIGHTLY)[_NIGHTLY_JOB]
    patterns = (_COLLECT_RE, _COMPARE_RE)
    assert _continue_on_error_problems(job, patterns) == [], "control: the unmutated job is accepted"
    for pattern in patterns:

        def flag(steps: list[Step], pattern: re.Pattern[str] = pattern) -> None:
            next(step for step in steps if pattern.search(_run(step)))["continue-on-error"] = True

        assert _continue_on_error_problems(_mutated(job, flag), patterns)
