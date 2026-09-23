"""ATDD pinning test for the ``interpreter-matrix`` job's ``uv run`` step (#4866, WP03).

Issue #4866: the ``interpreter-matrix`` job in ``.github/workflows/ci-nightly.yml``
syncs the project environment with ``uv sync --frozen --all-extras --python
"${{ matrix.python-version }}"`` (correct), but its next step runs ``uv run
--frozen pytest -m "fast or unit" ...`` with neither ``--python`` nor
``--all-extras``. ``uv run --frozen`` silently re-syncs the project environment
against the repo's ``.python-version`` (3.11.15) with default (non-``test``)
extras, discarding the preceding 3.13 ``--all-extras`` sync — the interpreter
matrix has been running on the wrong interpreter with the wrong extras, every
night, for a week.

This test parses the REAL ``.github/workflows/ci-nightly.yml`` (never a
hardcoded copy of its text) and asserts that the ``uv run`` step's own
``run:`` string — not the job's or file's full YAML text — pins both
``--python`` and ``--all-extras``, and that those flags sit BEFORE the
``pytest`` command word.

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
import yaml

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKFLOW_PATH = _REPO_ROOT / ".github" / "workflows" / "ci-nightly.yml"

# Marker substring that identifies the `uv run` step among the job's steps,
# distinct from the earlier `uv sync` step (which has no `pytest` in its
# `run:` string at all).
_PYTEST_MARKER = 'pytest -m "fast or unit"'


def _load_workflow() -> dict[str, Any]:
    with _WORKFLOW_PATH.open(encoding="utf-8") as handle:
        # GitHub Actions workflow YAML uses the bare key `on:`, which PyYAML's
        # default resolver would otherwise fold into the boolean key `True`.
        # yaml.safe_load handles this fine for our purposes since we never
        # read the `on:` mapping here -- plain safe_load is sufficient.
        loaded = yaml.safe_load(handle)
    assert isinstance(loaded, dict), f"expected a YAML mapping at the file root, got {type(loaded)!r}"
    return loaded


def _find_interpreter_matrix_run_step(workflow: dict[str, Any]) -> dict[str, Any]:
    jobs = workflow["jobs"]
    job = jobs["interpreter-matrix"]
    steps = job["steps"]
    matching = [step for step in steps if isinstance(step.get("run"), str) and _PYTEST_MARKER in step["run"]]
    assert len(matching) == 1, (
        f"expected exactly one interpreter-matrix step whose run: string "
        f"contains {_PYTEST_MARKER!r}, found {len(matching)}. Steps with a "
        f"run: key: {[s.get('name') for s in steps if 'run' in s]}"
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


class TestInterpreterMatrixUvRunStepPinsEnv:
    """FR-001/NFR-002/C-004: the `uv run` step must pin interpreter + extras."""

    def test_uv_run_step_exists_and_is_distinct_from_uv_sync_step(self) -> None:
        workflow = _load_workflow()
        job = workflow["jobs"]["interpreter-matrix"]
        sync_steps = [step for step in job["steps"] if isinstance(step.get("run"), str) and "uv sync" in step["run"]]
        assert len(sync_steps) == 1, "expected exactly one uv sync step"
        # Sanity: the sync step's run string never contains the pytest
        # marker -- if it did, our step-isolation logic below would be
        # ambiguous.
        assert _PYTEST_MARKER not in sync_steps[0]["run"]

        run_step = _find_interpreter_matrix_run_step(workflow)
        assert run_step is not sync_steps[0]

    def test_uv_run_step_pins_python_and_all_extras_before_pytest(self) -> None:
        """The load-bearing assertion (FR-001).

        Isolates the `uv run` step's OWN `run:` string (not the job's or
        file's full YAML text -- the preceding `uv sync` step already
        carries `--python`/`--all-extras`, so a whole-text match would be
        vacuously green even before the fix lands), then further isolates
        the prefix BEFORE the `pytest` command word, and asserts both
        `--python` and `--all-extras` appear in that prefix specifically.
        """
        workflow = _load_workflow()
        run_step = _find_interpreter_matrix_run_step(workflow)
        run_str = run_step["run"]

        prefix = _prefix_before_pytest_command_word(run_str)

        assert "--python" in prefix, (
            "the interpreter-matrix `uv run` step must pin --python before "
            f"the `pytest` command word so `uv run --frozen` cannot silently "
            f"re-sync against .python-version's default interpreter; got "
            f"run string: {run_str!r}"
        )
        assert "--all-extras" in prefix, (
            "the interpreter-matrix `uv run` step must pin --all-extras "
            f"before the `pytest` command word so `uv run --frozen` cannot "
            f"silently re-sync with default (non-test) extras; got run "
            f"string: {run_str!r}"
        )

    def test_uv_run_step_preserves_existing_pytest_invocation(self) -> None:
        """The fix must not disturb the existing pytest arguments/order."""
        workflow = _load_workflow()
        run_step = _find_interpreter_matrix_run_step(workflow)
        run_str = run_step["run"]

        assert "--frozen" in run_str
        assert 'pytest -m "fast or unit" -q' in run_str
        assert '--junitxml="out/reports/xunit-nightly-interpreter-${{ matrix.python-version }}.xml"' in run_str

    def test_uv_run_step_passes_parallelism_flag_to_pytest_not_uv(self) -> None:
        """#4866 scope extension (operator-authorized): the step must pass a
        pytest-xdist parallelism flag (`-n auto`) to PYTEST -- i.e. AFTER the
        `pytest` command word -- never to `uv run` (before it).

        Root cause this closes: the job's pytest invocation ran serially
        (no `-n auto`), so a real dispatch (CI run 35778042008) was killed
        by the job's 45-minute cap before the fast/unit suite could finish
        -- WP01's serial local run of the same ~34.8k-test population took
        5036s (84 minutes); WP05's `-n auto` run of the same population
        took 475.87s (~8 minutes), and verified the shared/pinned
        environment survives byte-identical, because WP04 already fixed
        shared-`.venv` corruption at the root (`--no-sync` at the two
        nested call sites, plus this job's own per-interpreter
        `UV_PROJECT_ENVIRONMENT` pin).

        A test that merely grepped for `-n` anywhere in the run string
        would pass even on a BROKEN placement -- `-n auto` sitting before
        `pytest` would be consumed by `uv run`'s own CLI grammar instead of
        being passed through to pytest, which is the exact class of
        flag-misplacement bug this mission exists to fix (see
        `test_uv_run_step_pins_python_and_all_extras_before_pytest` above
        for the identical hazard on `--python`/`--all-extras`, just
        mirrored: those must stay BEFORE `pytest`, this must land AFTER
        it). This test isolates the pytest-argument region with
        `_suffix_from_pytest_command_word` (the mirror of
        `_prefix_before_pytest_command_word`) and asserts the flag is
        there and nowhere in the uv-run prefix.
        """
        workflow = _load_workflow()
        run_step = _find_interpreter_matrix_run_step(workflow)
        run_str = run_step["run"]

        prefix = _prefix_before_pytest_command_word(run_str)
        suffix = _suffix_from_pytest_command_word(run_str)

        assert re.search(r"(?<!\S)-n(?:\s+|=)auto(?!\S)", suffix), (
            "the interpreter-matrix `uv run` step must pass a pytest-xdist "
            "parallelism flag (`-n auto`) to pytest itself, positioned "
            "AFTER the `pytest` command word, so the fast/unit suite runs "
            "in parallel and fits the job's 45-minute timeout instead of "
            f"being killed mid-run; got run string: {run_str!r}"
        )
        assert not re.search(r"(?<!\S)-n(?:\s+|=)auto(?!\S)", prefix), (
            "a parallelism flag must never appear in the uv-run prefix "
            "(before `pytest`) -- `uv run` would consume it as its own "
            "option instead of passing it through to pytest, reproducing "
            "the exact flag-misplacement bug class this mission exists to "
            f"fix; prefix: {prefix!r}"
        )

    def test_uv_run_step_passes_dist_loadfile_flag_to_pytest_not_uv(self) -> None:
        """#4866 pre-merge squad finding pr-merged-002: bare `-n auto` (no
        `--dist`) falls back to xdist's `load` distribution (verified
        against the installed xdist 3.8.0 source, `plugin.py:318-320`), but
        the repo's own testing doc
        (`docs/development/testing/testing-parallel.md`) and both Makefile
        xdist invocations (`FAST_TIER_MARKERS`/`PARALLEL_UNSAFE_MARKERS`
        recipes) require `loadfile` -- `load` scatters a file's tests across
        workers and breaks file-scoped fixtures/collection-order assumptions
        that 64 files in `tests/` rely on (`scope="module"`/`scope="class"`).

        Mirrors `test_uv_run_step_passes_parallelism_flag_to_pytest_not_uv`
        above: `--dist loadfile` is a PYTEST flag and must sit AFTER the
        `pytest` command word, never before it (where `uv run` would try to
        consume it as its own option instead).
        """
        workflow = _load_workflow()
        run_step = _find_interpreter_matrix_run_step(workflow)
        run_str = run_step["run"]

        prefix = _prefix_before_pytest_command_word(run_str)
        suffix = _suffix_from_pytest_command_word(run_str)

        assert "--dist loadfile" in suffix, (
            "the interpreter-matrix `uv run` step must pass `--dist loadfile` "
            "to pytest itself, positioned AFTER the `pytest` command word -- "
            "bare `-n auto` falls back to xdist's `load` distribution, which "
            "breaks file-scoped fixtures relied on across the fast/unit "
            f"population; got run string: {run_str!r}"
        )
        assert "--dist loadfile" not in prefix, (
            "`--dist loadfile` must never appear in the uv-run prefix "
            "(before `pytest`) -- `uv run` would consume it as its own "
            f"option instead of passing it through to pytest; prefix: {prefix!r}"
        )

    def test_uv_sync_step_untouched(self) -> None:
        """T002/reviewer guidance: the already-correct uv sync step (line
        ~205) must not be modified by this WP -- only the uv run step's
        flags change."""
        workflow = _load_workflow()
        job = workflow["jobs"]["interpreter-matrix"]
        sync_steps = [step for step in job["steps"] if isinstance(step.get("run"), str) and "uv sync" in step["run"]]
        assert len(sync_steps) == 1
        assert sync_steps[0]["run"] == ('uv sync --frozen --all-extras --python "${{ matrix.python-version }}"')
