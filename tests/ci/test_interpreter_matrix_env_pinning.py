"""ATDD pinning test for the interpreter-matrix shards' ``uv run`` step (#4866, WP03).

Issue #4866: the (then-single) ``interpreter-matrix`` job in
``.github/workflows/ci-nightly.yml`` synced the project environment with
``uv sync --frozen --all-extras --python "${{ matrix.python-version }}"``
(correct), but its next step ran ``uv run --frozen pytest -m "fast or unit"
...`` with neither ``--python`` nor ``--all-extras``. ``uv run --frozen``
silently re-syncs the project environment against the repo's
``.python-version`` (3.11.15) with default (non-``test``) extras, discarding
the preceding 3.13 ``--all-extras`` sync — the interpreter matrix had been
running on the wrong interpreter with the wrong extras, every night, for a
week.

**#4951 update**: the single ``interpreter-matrix`` job was split into N
independent ``interpreter-matrix-shard-<N>`` jobs (see
``_interpreter_shard_roster.py``). Each shard keeps its OWN independent
``uv sync --frozen --all-extras --python "3.13"`` step (FR-008), so this
test now iterates every roster-declared shard job (dynamic discovery, never
a second hardcoded job list) rather than the single retired job key.

**``--python "3.13"`` is REQUIRED on the ``uv run ... pytest`` line**
(#3189 follow-up to #5244). An earlier revision of this split dropped it on
the premise that ``actions/setup-python`` plus the job's
``UV_PROJECT_ENVIRONMENT: .venv-py3.13`` keep the interpreter pinned. They do
not: without ``--python``, ``uv run`` honours the repo's ``.python-version``
(3.11.15), removes the ``.venv-py3.13`` environment the preceding sync built,
and rebuilds it on 3.11 -- reproduced on uv 0.8.17 and 0.12.19 ("Removed
virtual environment at: .venv-py3.13"). The shards would report "3.13" while
running every test on 3.11. The flag had been dropped because
``tests/architectural/_gate_coverage.py``'s runner-prefix tokenizer let
``--frozen`` swallow ``--python`` as its value; that tokenizer is fixed, so
the pinned form now parses (see ``test_gate_coverage_runner_prefix.py``).
Both halves of #4866's original defect -- ``--python`` and ``--all-extras``
-- are asserted below.

This test parses the REAL ``.github/workflows/ci-nightly.yml`` (never a
hardcoded copy) and asserts that each shard's ``uv run`` step's own
``run:`` string — not the job's or file's full YAML text — pins
``--all-extras`` before the ``pytest`` command word, and that pytest's own
flags (``-n auto``, ``--dist loadfile``) sit AFTER it.

Position matters, not just presence: once the ``pytest`` command word
appears, ``uv run``'s CLI grammar passes every subsequent token straight
through to pytest rather than consuming it as a ``uv run`` option. Flags
appended after ``pytest -m "fast or unit" ...`` would be silently swallowed
by pytest's own arg parsing (or rejected) rather than pinning the
environment — reproducing the exact defect this WP exists to fix. A test
that only checked substring presence anywhere in the step (or in the whole
job/file text, where the preceding ``uv sync`` step already carries these
flags) would pass on that broken form. This test isolates the specific
``uv run`` step and the specific prefix before the ``pytest`` word, so it
fails for the right reason.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from tests.architectural._gate_coverage import load_spliced_workflow
from tests.architectural._interpreter_shard_roster import (
    INTERPRETER_SHARD_JOB_KEYS,
    INTERPRETER_SHARDS,
    shard_roster_non_vacuity_violation,
)

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "ci-nightly.yml"

# job_key -> roster shard, so tests parametrized on the bare job_key string
# (INTERPRETER_SHARD_JOB_KEYS, mirroring this module's existing style) can
# still look up that shard's roster-derived names (landing pass #5244,
# LAND-PAT-002) instead of re-deriving them ad hoc from the job_key string.
_SHARD_BY_JOB_KEY = {shard.job_key: shard for shard in INTERPRETER_SHARDS}

# Marker substring that identifies the `uv run` step among a shard job's
# steps, distinct from the earlier `uv sync` step (which has no `pytest` in
# its `run:` string at all).
_PYTEST_MARKER = 'pytest -m "fast or unit"'

# The interpreter every shard targets; the sync step asserts the same literal.
_SHARD_PYTHON = "3.13"


def _pins_interpreter(uv_run_prefix: str, version: str) -> bool:
    """True when ``uv run``'s own option prefix carries ``--python <version>``
    (quoted or bare, space- or ``=``-separated)."""
    pattern = r"(?<!\S)--python(?:\s+|=)(['\"]?)" + re.escape(version) + r"\1(?!\S)"
    return re.search(pattern, uv_run_prefix) is not None


def _load_workflow() -> dict[str, Any]:
    # Landing pass #5244 (LAND-PAT-003): every workflow reader that may see a
    # local `uses:` caller job or composite-action step must load through
    # `load_spliced_workflow`, never a raw `yaml.safe_load` -- ci-nightly.yml
    # itself has one such caller job (`full-module-matrix` -> `uses: ./.github
    # /workflows/module-tests.yml`), so a raw reader mis-models that job (no
    # `steps:` key) even though today's shard/marker-lane readers here never
    # touch it. The prior justification for a raw `safe_load` here (the bare
    # `on:` key folding into PyYAML's boolean `True`) was never the actual
    # reason splicing exists; it is dropped rather than repeated.
    loaded = load_spliced_workflow(_WORKFLOW_PATH)
    assert isinstance(loaded, dict), f"expected a YAML mapping at the file root, got {type(loaded)!r}"
    return loaded


def _find_shard_run_step(workflow: dict[str, Any], job_key: str) -> dict[str, Any]:
    jobs = workflow["jobs"]
    job = jobs[job_key]
    steps = job["steps"]
    matching = [step for step in steps if isinstance(step.get("run"), str) and _PYTEST_MARKER in step["run"]]
    assert len(matching) == 1, (
        f"expected exactly one {job_key!r} step whose run: string contains "
        f"{_PYTEST_MARKER!r}, found {len(matching)}. Steps with a run: key: "
        f"{[s.get('name') for s in steps if 'run' in s]}"
    )
    result = matching[0]
    assert isinstance(result, dict)
    return result


def _prefix_before_pytest_command_word(run_str: str) -> str:
    """Return everything in ``run_str`` before the ``pytest`` command word.

    Uses a word-boundary match so flags appended AFTER `pytest` (the broken
    form this WP fixes) are excluded from the returned prefix -- only flags
    sitting between `uv run --frozen` and `pytest` count.
    """
    match = re.search(r"\bpytest\b", run_str)
    assert match is not None, f"no `pytest` command word found in run string: {run_str!r}"
    return run_str[: match.start()]


def _suffix_from_pytest_command_word(run_str: str) -> str:
    """Return ``run_str`` from the ``pytest`` command word onward.

    The mirror image of :func:`_prefix_before_pytest_command_word`: this is
    the region where pytest's OWN arguments live (pytest-xdist's ``-n auto``
    among them), as opposed to ``uv run``'s own option prefix.
    """
    match = re.search(r"\bpytest\b", run_str)
    assert match is not None, f"no `pytest` command word found in run string: {run_str!r}"
    return run_str[match.start() :]


# ---------------------------------------------------------------------------
# PR-TESTS-002 (pre-merge squad, severity 3): every test in
# ``TestInterpreterMatrixUvRunStepPinsEnv`` below is
# ``@pytest.mark.parametrize("job_key", INTERPRETER_SHARD_JOB_KEYS)``. If the
# roster is ever emptied, pytest reports "got empty parameter set" SKIPPED
# for each -- a fully green summary with zero real coverage, not a failure.
# This guard fails loudly instead, and additionally proves the roster still
# matches reality (a SHRUNKEN, non-empty roster is caught too): the number
# of shard job keys declared here must equal the number of
# ``interpreter-matrix-shard-*``-shaped jobs ci-nightly.yml actually defines.
# ---------------------------------------------------------------------------


def test_shard_roster_non_vacuity() -> None:
    """PR-TESTS-002: fails loudly on an emptied or shrunken roster instead
    of letting every ``@pytest.mark.parametrize`` test below silently
    contribute zero real coverage. Landing pass #5244 (LAND-PAT-006): the
    comparison itself is now the roster's shared
    ``shard_roster_non_vacuity_violation`` helper, not a local copy."""
    violation = shard_roster_non_vacuity_violation(INTERPRETER_SHARD_JOB_KEYS, _load_workflow()["jobs"])
    assert violation is None, violation


def test_shard_roster_non_vacuity_check_fails_on_an_emptied_roster() -> None:
    """Standing Order #5 positive control: proves
    ``shard_roster_non_vacuity_violation`` -- the SAME shared function the
    guard above calls -- actually fails on an emptied roster, without ever
    touching ``_interpreter_shard_roster.py`` on disk (a scratch ``()``
    passed directly, mirroring this module's other scratch-copy tests)."""
    violation = shard_roster_non_vacuity_violation((), _load_workflow()["jobs"])
    assert violation is not None and "must not be empty" in violation, f"expected an empty-roster violation, got: {violation!r}"


def test_shard_roster_non_vacuity_check_fails_on_a_shrunken_roster() -> None:
    """Standing Order #5 positive control: a non-empty but SHRUNKEN scratch
    roster (one shard dropped) must also surface as a violation -- the
    empty-set check alone would miss this case."""
    shrunken = INTERPRETER_SHARD_JOB_KEYS[:-1]
    violation = shard_roster_non_vacuity_violation(shrunken, _load_workflow()["jobs"])
    assert violation is not None and "defines" in violation, f"expected a count-mismatch violation, got: {violation!r}"


class TestInterpreterMatrixUvRunStepPinsEnv:
    """FR-008/NFR-002/C-004: every shard's `uv run` step must pin extras."""

    @pytest.mark.parametrize("job_key", INTERPRETER_SHARD_JOB_KEYS)
    def test_uv_run_step_exists_and_is_distinct_from_uv_sync_step(self, job_key: str) -> None:
        workflow = _load_workflow()
        job = workflow["jobs"][job_key]
        sync_steps = [step for step in job["steps"] if isinstance(step.get("run"), str) and "uv sync" in step["run"]]
        assert len(sync_steps) == 1, f"{job_key}: expected exactly one uv sync step"
        # Sanity: the sync step's run string never contains the pytest
        # marker -- if it did, our step-isolation logic below would be
        # ambiguous.
        assert _PYTEST_MARKER not in sync_steps[0]["run"]

        run_step = _find_shard_run_step(workflow, job_key)
        assert run_step is not sync_steps[0]

    @pytest.mark.parametrize("job_key", INTERPRETER_SHARD_JOB_KEYS)
    def test_uv_run_step_pins_all_extras_before_pytest(self, job_key: str) -> None:
        """The load-bearing assertion (FR-008).

        Isolates the `uv run` step's OWN `run:` string (not the job's or
        file's full YAML text -- the preceding `uv sync` step already
        carries `--all-extras`, so a whole-text match would be vacuously
        green even before the fix lands), then further isolates the prefix
        BEFORE the `pytest` command word, and asserts `--all-extras`
        appears in that prefix specifically. The interpreter pin is
        asserted separately by `test_uv_run_step_pins_python_before_pytest`.
        """
        workflow = _load_workflow()
        run_step = _find_shard_run_step(workflow, job_key)
        run_str = run_step["run"]

        prefix = _prefix_before_pytest_command_word(run_str)

        assert "--all-extras" in prefix, (
            f"{job_key}: the `uv run` step must pin --all-extras before the "
            f"`pytest` command word so `uv run --frozen` cannot silently "
            f"re-sync with default (non-test) extras; got run string: {run_str!r}"
        )

    @pytest.mark.parametrize("job_key", INTERPRETER_SHARD_JOB_KEYS)
    def test_uv_run_step_pins_python_before_pytest(self, job_key: str) -> None:
        """The other load-bearing assertion (#3189, #4866).

        Without `--python` on this line, `uv run` re-syncs the shard's
        `UV_PROJECT_ENVIRONMENT` venv onto `.python-version` (3.11) and the
        "3.13" shard silently tests 3.11. Checked in the prefix before the
        `pytest` command word, where `uv run` consumes it.
        """
        workflow = _load_workflow()
        run_str = _find_shard_run_step(workflow, job_key)["run"]
        assert _pins_interpreter(_prefix_before_pytest_command_word(run_str), _SHARD_PYTHON), (
            f"{job_key}: the `uv run` step must pin --python {_SHARD_PYTHON!r} before the "
            f"`pytest` command word, or uv rebuilds the venv on .python-version; got run string: {run_str!r}"
        )

    def test_python_pin_check_rejects_the_unpinned_form(self) -> None:
        """Standing Order #5 positive control: the exact line an earlier
        revision of #5244 shipped must fail the pin check."""
        unpinned = 'uv run --frozen --all-extras pytest -m "fast or unit" tests/unit'
        assert not _pins_interpreter(_prefix_before_pytest_command_word(unpinned), _SHARD_PYTHON)
        wrong = 'uv run --frozen --python "3.11" --all-extras pytest -m "fast or unit" tests/unit'
        assert not _pins_interpreter(_prefix_before_pytest_command_word(wrong), _SHARD_PYTHON)

    @pytest.mark.parametrize("job_key", INTERPRETER_SHARD_JOB_KEYS)
    def test_uv_run_step_preserves_existing_pytest_invocation(self, job_key: str) -> None:
        """The fix must not disturb the existing pytest arguments/order."""
        workflow = _load_workflow()
        run_step = _find_shard_run_step(workflow, job_key)
        run_str = run_step["run"]

        assert "--frozen" in run_str
        assert 'pytest -m "fast or unit"' in run_str
        assert "-q" in run_str
        shard = _SHARD_BY_JOB_KEY[job_key]
        assert f'--junitxml="out/reports/{shard.junit_filename}"' in run_str

    @pytest.mark.parametrize("job_key", INTERPRETER_SHARD_JOB_KEYS)
    def test_uv_run_step_passes_parallelism_flag_to_pytest_not_uv(self, job_key: str) -> None:
        """#4866 scope extension (operator-authorized): each shard's step
        must pass a pytest-xdist parallelism flag (`-n auto`) to PYTEST --
        i.e. AFTER the `pytest` command word -- never to `uv run` (before
        it).

        Root cause this closes: the (pre-split) job's pytest invocation ran
        serially (no `-n auto`), so a real dispatch (CI run 35778042008) was
        killed by the job's 45-minute cap before the fast/unit suite could
        finish. `-n auto` remains required on every post-split shard.

        A test that merely grepped for `-n` anywhere in the run string
        would pass even on a BROKEN placement -- `-n auto` sitting before
        `pytest` would be consumed by `uv run`'s own CLI grammar instead of
        being passed through to pytest, which is the exact class of
        flag-misplacement bug this mission exists to fix. This test
        isolates the pytest-argument region with
        `_suffix_from_pytest_command_word` (the mirror of
        `_prefix_before_pytest_command_word`) and asserts the flag is there
        and nowhere in the uv-run prefix.
        """
        workflow = _load_workflow()
        run_step = _find_shard_run_step(workflow, job_key)
        run_str = run_step["run"]

        prefix = _prefix_before_pytest_command_word(run_str)
        suffix = _suffix_from_pytest_command_word(run_str)

        assert re.search(r"(?<!\S)-n(?:\s+|=)auto(?!\S)", suffix), (
            f"{job_key}: the `uv run` step must pass a pytest-xdist "
            "parallelism flag (`-n auto`) to pytest itself, positioned "
            "AFTER the `pytest` command word, so the fast/unit suite runs "
            "in parallel and fits the shard's own timeout instead of "
            f"being killed mid-run; got run string: {run_str!r}"
        )
        assert not re.search(r"(?<!\S)-n(?:\s+|=)auto(?!\S)", prefix), (
            f"{job_key}: a parallelism flag must never appear in the "
            "uv-run prefix (before `pytest`) -- `uv run` would consume it "
            "as its own option instead of passing it through to pytest, "
            "reproducing the exact flag-misplacement bug class this "
            f"mission exists to fix; prefix: {prefix!r}"
        )

    @pytest.mark.parametrize("job_key", INTERPRETER_SHARD_JOB_KEYS)
    def test_uv_run_step_passes_dist_loadfile_flag_to_pytest_not_uv(self, job_key: str) -> None:
        """#4866 pre-merge squad finding pr-merged-002: bare `-n auto` (no
        `--dist`) falls back to xdist's `load` distribution (verified
        against the installed xdist 3.8.0 source, `plugin.py:318-320`), but
        the repo's own testing doc
        (`docs/development/testing/testing-parallel.md`) and both Makefile
        xdist invocations (`FAST_TIER_MARKERS`/`PARALLEL_UNSAFE_MARKERS`
        recipes) require `loadfile` -- `load` scatters a file's tests across
        workers and breaks file-scoped fixtures/collection-order assumptions
        that many files in `tests/` rely on (`scope="module"`/`scope="class"`).

        Mirrors `test_uv_run_step_passes_parallelism_flag_to_pytest_not_uv`
        above: `--dist loadfile` is a PYTEST flag and must sit AFTER the
        `pytest` command word, never before it (where `uv run` would try to
        consume it as its own option instead).
        """
        workflow = _load_workflow()
        run_step = _find_shard_run_step(workflow, job_key)
        run_str = run_step["run"]

        prefix = _prefix_before_pytest_command_word(run_str)
        suffix = _suffix_from_pytest_command_word(run_str)

        assert "--dist loadfile" in suffix, (
            f"{job_key}: the `uv run` step must pass `--dist loadfile` to "
            "pytest itself, positioned AFTER the `pytest` command word -- "
            "bare `-n auto` falls back to xdist's `load` distribution, which "
            "breaks file-scoped fixtures relied on across the fast/unit "
            f"population; got run string: {run_str!r}"
        )
        assert "--dist loadfile" not in prefix, (
            f"{job_key}: `--dist loadfile` must never appear in the uv-run "
            "prefix (before `pytest`) -- `uv run` would consume it as its "
            f"own option instead of passing it through to pytest; prefix: {prefix!r}"
        )

    @pytest.mark.parametrize("job_key", INTERPRETER_SHARD_JOB_KEYS)
    def test_uv_sync_step_pins_python_and_all_extras(self, job_key: str) -> None:
        """T002/reviewer guidance: the sync step pins `--python "3.13"` too,
        so the venv is built on 3.13 before the `uv run` step (which carries
        its own pin, see `test_uv_run_step_pins_python_before_pytest`)."""
        workflow = _load_workflow()
        job = workflow["jobs"][job_key]
        sync_steps = [step for step in job["steps"] if isinstance(step.get("run"), str) and "uv sync" in step["run"]]
        assert len(sync_steps) == 1
        assert sync_steps[0]["run"] == 'uv sync --frozen --all-extras --python "3.13"'

    @pytest.mark.parametrize("job_key", INTERPRETER_SHARD_JOB_KEYS)
    def test_upload_artifact_name_matches_the_roster(self, job_key: str) -> None:
        """LAND-PAT-002 (landing pass #5244): the shard's
        ``actions/upload-artifact`` ``name:`` must equal the roster's
        ``artifact_name`` property -- one more per-shard naming convention
        moved onto :class:`InterpreterShard` instead of being re-derived ad
        hoc per test module."""
        workflow = _load_workflow()
        job = workflow["jobs"][job_key]
        upload_steps = [step for step in job["steps"] if isinstance(step.get("uses"), str) and step["uses"].startswith("actions/upload-artifact@")]
        assert len(upload_steps) == 1, f"{job_key}: expected exactly one actions/upload-artifact step, found {len(upload_steps)}"
        shard = _SHARD_BY_JOB_KEY[job_key]
        with_block = upload_steps[0].get("with") or {}
        assert with_block.get("name") == shard.artifact_name, f"{job_key}: expected upload-artifact name {shard.artifact_name!r}, got {with_block.get('name')!r}"
