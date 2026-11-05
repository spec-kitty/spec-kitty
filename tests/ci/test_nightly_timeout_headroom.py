"""Pin CI ``timeout-minutes`` caps against their own measured-max comments (#5378).

The interpreter-matrix shard jobs and ``specify-cli-out-of-matrix`` in
``ci-nightly.yml`` were being cancelled at their cap after the suite itself had
finished (job overhead counts against ``timeout-minutes``). The per-PR
``module-tests.yml`` shard job (``test``) hit the same wall on the charter
module, and the advisory Packs corpus job (``packs.yml``) hit it on PRs whose
diff has nothing to do with packs (#7206). The workflow is the single authority
for caps, so each of those jobs records its measured maximum suite wall-clock in
a structured comment directly above ``timeout-minutes``::

    # headroom (#5378): max-suite=12:35 runs=... formula=ceil((max+0:30)*1.5)

This test parses ONLY the workflow text and asserts every such job's cap is at
least ``ceil((max_suite_minutes + 0.5) * 1.5)``. No durations are committed here.

The advisory corpus job is the third target (#7206): its measured maximum is
recorded the same way, so a cap can no longer be picked by feel on a lane whose
fixed costs (whole-tree collection plus the serial wall-clock policy scan) are
architectural. :func:`headroom_record` is the one reader of that record; the
budget module ``tests/ci/test_corpus_suite_budget.py`` reuses it rather than
parsing the workflow a second time.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from pathlib import Path

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_WORKFLOWS_DIR = Path(__file__).resolve().parents[2] / ".github" / "workflows"
_WORKFLOW_PATH = _WORKFLOWS_DIR / "ci-nightly.yml"
_MODULE_TESTS_PATH = _WORKFLOWS_DIR / "module-tests.yml"
_PACKS_PATH = _WORKFLOWS_DIR / "packs.yml"

_SHARD_PREFIX = "interpreter-matrix-shard-"
_OUT_OF_MATRIX_JOB = "specify-cli-out-of-matrix"
_MODULE_TESTS_JOB = "test"
# The advisory ``-m corpus`` suite (#7206): measured p95 20.3 min against a
# 20-minute cap. Its own budget module holds the step budget and the notice.
_PACKS_CORPUS_JOB = "built-in-corpus-suite"
_JOB_KEY_RE = re.compile(r"^  ([A-Za-z0-9_-]+):\s*$", re.MULTILINE)
# Job-level key only (4-space indent): a step-level `timeout-minutes` must never
# be read as the job cap.
_TIMEOUT_RE = re.compile(r"^    timeout-minutes:\s*(\d+)\s*$", re.MULTILINE)
_HEADROOM_RE = re.compile(r"#\s*headroom \(#5378\):\s*max-suite(>=|=)(\d+):(\d{2})\b")
_OVERHEAD_MINUTES = 0.5
_HEADROOM_FACTOR = 1.5


def _required_cap(max_suite: str) -> int:
    """Return ``ceil((max + 30s) * 1.5)`` minutes for an ``MM:SS`` maximum."""
    minutes, seconds = max_suite.split(":")
    total = int(minutes) + int(seconds) / 60
    return math.ceil((total + _OVERHEAD_MINUTES) * _HEADROOM_FACTOR)


def _is_nightly_target(key: str) -> bool:
    return key.startswith(_SHARD_PREFIX) or key == _OUT_OF_MATRIX_JOB


def _is_module_tests_target(key: str) -> bool:
    return key == _MODULE_TESTS_JOB


def _is_packs_corpus_target(key: str) -> bool:
    return key == _PACKS_CORPUS_JOB


def _job_blocks(text: str, is_target: Callable[[str], bool] = _is_nightly_target) -> dict[str, str]:
    """Map each target job key to its text block (up to the next job key)."""
    jobs_start = text.find("\njobs:")
    body = text[jobs_start:] if jobs_start >= 0 else text
    matches = list(_JOB_KEY_RE.finditer(body))
    blocks: dict[str, str] = {}
    for index, match in enumerate(matches):
        key = match.group(1)
        if not is_target(key):
            continue
        end = matches[index + 1].start() if index + 1 < len(matches) else len(body)
        blocks[key] = body[match.start() : end]
    return blocks


def _comment_above(block: str, offset: int) -> str:
    """Return the last non-blank line before ``offset`` in ``block``."""
    preceding = [line for line in block[:offset].splitlines() if line.strip()]
    return preceding[-1] if preceding else ""


def _cap_violations(text: str, is_target: Callable[[str], bool] = _is_nightly_target) -> list[str]:
    """Return one named message per target job whose cap or comment is wrong."""
    problems: list[str] = []
    for job, block in _job_blocks(text, is_target).items():
        timeout = _TIMEOUT_RE.search(block)
        if timeout is None:
            problems.append(f"{job}: no job-level `timeout-minutes:` found")
            continue
        headroom = _HEADROOM_RE.search(_comment_above(block, timeout.start()))
        if headroom is None:
            problems.append(f"{job}: missing `# headroom (#5378): max-suite(>=|=)MM:SS` comment directly above `timeout-minutes:`")
            continue
        required = _required_cap(f"{headroom.group(2)}:{headroom.group(3)}")
        cap = int(timeout.group(1))
        if cap < required:
            problems.append(f"{job}: timeout-minutes {cap} < required {required} for max-suite{headroom.group(1)}{headroom.group(2)}:{headroom.group(3)}")
    return problems


def headroom_record(text: str, job: str, *, is_target: Callable[[str], bool]) -> tuple[int, str]:
    """Return ``(cap_minutes, recorded_max_suite)`` for *job*; fail loudly when either is absent.

    The single reader of the #5378 record: the cap guard below and the advisory
    corpus budget module both call it, so no second parser can disagree with this
    one about what the workflow records.
    """
    blocks = _job_blocks(text, is_target)
    assert job in blocks, f"{job}: not a target job in this workflow text (found {sorted(blocks)})"
    block = blocks[job]
    timeout = _TIMEOUT_RE.search(block)
    assert timeout is not None, f"{job}: no job-level `timeout-minutes:` found"
    headroom = _HEADROOM_RE.search(_comment_above(block, timeout.start()))
    assert headroom is not None, f"{job}: missing `# headroom (#5378): max-suite(>=|=)MM:SS` comment directly above `timeout-minutes:`"
    return int(timeout.group(1)), f"{headroom.group(2)}:{headroom.group(3)}"


def test_required_cap_formula() -> None:
    assert _required_cap("12:35") == 20
    assert _required_cap("20:09") == 31
    assert _required_cap("45:01") == 69
    assert _required_cap("7:26") == 12


def test_violation_check_flags_low_cap_and_missing_comment() -> None:
    synthetic = (
        "jobs:\n"
        "  interpreter-matrix-shard-1:\n"
        "    # headroom (#5378): max-suite=20:09 runs=1 formula=x\n"
        "    timeout-minutes: 30\n"
        "  interpreter-matrix-shard-2:\n"
        "    timeout-minutes: 99\n"
        "  interpreter-matrix-shard-3:\n"
        "    # headroom (#5378): max-suite>=20:09 runs=1 formula=x\n"
        "    timeout-minutes: 31\n"
        "  unrelated:\n"
        "    timeout-minutes: 1\n"
    )
    problems = _cap_violations(synthetic)
    assert len(problems) == 2
    assert "interpreter-matrix-shard-1" in problems[0] and "< required 31" in problems[0]
    assert "interpreter-matrix-shard-2" in problems[1] and "missing" in problems[1]


def test_violation_check_ignores_step_level_timeout() -> None:
    synthetic = (
        "jobs:\n"
        "  interpreter-matrix-shard-1:\n"
        "    steps:\n"
        "      - name: x\n"
        "        # headroom (#5378): max-suite=1:00 runs=1 formula=x\n"
        "        timeout-minutes: 99\n"
    )
    assert _cap_violations(synthetic) == ["interpreter-matrix-shard-1: no job-level `timeout-minutes:` found"]


def test_violation_check_rejects_comment_in_neighbouring_job() -> None:
    synthetic = (
        "jobs:\n"
        "  interpreter-matrix-shard-1:\n"
        "    timeout-minutes: 99\n"
        "    # headroom (#5378): max-suite=1:00 runs=1 formula=x\n"
        "  interpreter-matrix-shard-2:\n"
        "    timeout-minutes: 99\n"
    )
    problems = _cap_violations(synthetic)
    assert len(problems) == 2
    assert all("missing" in problem for problem in problems)


def test_nightly_timeout_caps_meet_recorded_headroom() -> None:
    text = _WORKFLOW_PATH.read_text(encoding="utf-8")
    blocks = _job_blocks(text)
    shards = [key for key in blocks if key.startswith(_SHARD_PREFIX)]
    assert len(blocks) >= 7, f"non-vacuity: expected >=7 target jobs, found {sorted(blocks)}"
    assert len(shards) >= 6, f"non-vacuity: expected >=6 shards, found {sorted(shards)}"
    assert _OUT_OF_MATRIX_JOB in blocks
    assert _cap_violations(text) == []


def test_module_tests_selector_targets_only_the_shard_job() -> None:
    synthetic = (
        "jobs:\n"
        "  test:\n"
        "    # headroom (#5378): max-suite>=38:03 runs=1 formula=x\n"
        "    timeout-minutes: 57\n"
        "  interpreter-matrix-shard-1:\n"
        "    timeout-minutes: 1\n"
    )
    assert _cap_violations(synthetic, _is_module_tests_target) == ["test: timeout-minutes 57 < required 58 for max-suite>=38:03"]


def test_module_tests_timeout_cap_meets_recorded_headroom() -> None:
    text = _MODULE_TESTS_PATH.read_text(encoding="utf-8")
    blocks = _job_blocks(text, _is_module_tests_target)
    assert list(blocks) == [_MODULE_TESTS_JOB], f"non-vacuity: expected the `{_MODULE_TESTS_JOB}` shard job, found {sorted(blocks)}"
    assert _cap_violations(text, _is_module_tests_target) == []


def test_packs_corpus_timeout_cap_meets_recorded_headroom() -> None:
    """#7206: the advisory corpus cap follows its recorded measured maximum."""
    text = _PACKS_PATH.read_text(encoding="utf-8")
    blocks = _job_blocks(text, _is_packs_corpus_target)
    assert list(blocks) == [_PACKS_CORPUS_JOB], f"non-vacuity: expected the `{_PACKS_CORPUS_JOB}` advisory job, found {sorted(blocks)}"
    assert _cap_violations(text, _is_packs_corpus_target) == []


def test_packs_corpus_target_reports_a_low_cap_and_a_missing_record() -> None:
    """Mutation control: the new target's check is load-bearing in both directions."""
    synthetic = (
        "jobs:\n"
        f"  {_PACKS_CORPUS_JOB}:\n"
        "    # headroom (#5378): max-suite>=19:55 runs=55 formula=x\n"
        "    timeout-minutes: 30\n"
        "  built-in-other:\n"
        "    timeout-minutes: 1\n"
    )
    assert _cap_violations(synthetic, _is_packs_corpus_target) == [f"{_PACKS_CORPUS_JOB}: timeout-minutes 30 < required 31 for max-suite>=19:55"]

    without_record = f"jobs:\n  {_PACKS_CORPUS_JOB}:\n    timeout-minutes: 31\n"
    assert _cap_violations(without_record, _is_packs_corpus_target) == [
        f"{_PACKS_CORPUS_JOB}: missing `# headroom (#5378): max-suite(>=|=)MM:SS` comment directly above `timeout-minutes:`"
    ]


def test_packs_corpus_target_judges_only_that_job() -> None:
    """Non-vacuity: other Packs jobs are not silently judged by this lane's rule."""
    text = _PACKS_PATH.read_text(encoding="utf-8")
    assert list(_job_blocks(text, _is_packs_corpus_target)) == [_PACKS_CORPUS_JOB]
    untargeted = "jobs:\n  built-in-other:\n    timeout-minutes: 1\n"
    assert _job_blocks(untargeted, _is_packs_corpus_target) == {}
