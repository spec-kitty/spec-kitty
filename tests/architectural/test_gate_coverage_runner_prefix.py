"""Non-vacuity gate: the runner-prefix tokenizer keeps an interpreter-pinned
``uv run`` visible (#3189).

``_gate_coverage._FLAG_TOKENS`` lets a runner carry ``--flag [value]`` tokens
before the ``pytest`` command word. Its optional value used to accept any
token but ``pytest``, so a valueless flag swallowed the NEXT flag as its value:
in ``uv run --frozen --python "3.13" --all-extras pytest``, ``--frozen`` ate
``--python``, ``"3.13"`` was left unconsumed, and the whole invocation parsed
as "no pytest command here" -- zero gates. That is why the nightly
interpreter shards once dropped ``--python`` from their pytest line, which
made ``uv run`` rebuild the 3.13 venv on ``.python-version`` (3.11).

This module pins the fixed shape on synthetic spellings and on the live
nightly interpreter shards.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.architectural import _gate_coverage as gc
from tests.architectural._interpreter_shard_roster import INTERPRETER_SHARD_JOB_KEYS

pytestmark = pytest.mark.architectural

_NIGHTLY = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci-nightly.yml"


@pytest.mark.parametrize(
    "segment",
    [
        'uv run --frozen --python "3.13" --all-extras pytest -m "fast or unit" tests/unit',
        "uv run --frozen --python 3.13 --all-extras pytest tests/unit",
        "uv run --python=3.13 --frozen pytest tests/unit",
        "uv run --frozen pytest tests/unit",
        "uv run --frozen --all-extras pytest tests/unit",
        "uv run --with 'pytest-xdist' --frozen pytest tests/unit",
        "coverage run --source src -m pytest tests/unit",
    ],
)
def test_runner_prefix_strips_to_the_pytest_command_word(segment: str) -> None:
    assert gc.strip_to_command(segment).startswith("pytest ")


def test_a_valueless_flag_does_not_swallow_the_next_flag() -> None:
    """The pre-fix failure, stated directly: the pinned shape must not stop
    at the unconsumed ``"3.13"`` value."""
    stripped = gc.strip_to_command('uv run --frozen --python "3.13" --all-extras pytest tests/unit')
    assert not stripped.startswith('"3.13"'), stripped


def test_every_live_interpreter_shard_resolves_to_a_gate() -> None:
    """Each nightly interpreter shard -- whose pytest line now carries
    ``--python`` -- must still be visible to the gate model."""
    gated_jobs = {gate.job for gate in gc.parse_workflow(_NIGHTLY)}
    assert INTERPRETER_SHARD_JOB_KEYS, "interpreter shard roster is empty"
    missing = sorted(set(INTERPRETER_SHARD_JOB_KEYS) - gated_jobs)
    assert not missing, f"interpreter shards the gate model cannot see: {missing}"
