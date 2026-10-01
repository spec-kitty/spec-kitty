"""Architectural guard: no real ``~/.spec-kitty`` mutation under xdist (T007).

Mission ``test-suite-acceleration``, SC-006 / E1 I2: *no test reads, writes, or
truncates the real ``Path.home()/.spec-kitty`` under xdist*. The per-worker
HOME/state isolation autouse fixture (WP04, shipped long ago) makes this true;
this guard is the executable regression test that **fails the build** if that
guarantee ever regresses.

Isolation is required on every branch this guard runs on. It therefore:

1. Detects whether per-worker home isolation is active by running a tiny probe
   test in a ``-n auto`` subprocess. Each worker writes the ``Path.home()`` it
   resolves to into a parent-supplied temp dir; the parent reads those files
   back. If any worker resolves to the developer's *real* home, isolation has
   regressed and the guard **fails**, naming the offending worker homes. The
   probe never writes to the real home, so detection itself is always safe.
2. Once isolation is confirmed active (workers resolve to per-worker temp homes), records
   the real ``~/.spec-kitty`` state (absent, or mtime+size of a sentinel),
   drives a representative parallel selection that touches ``Path.home()``, and
   asserts the real sentinel is unchanged/absent afterward.

**Transport note (Cycle 1 fix).** Detection must survive the xdist worker→parent
process boundary. pytest-xdist does **not** forward worker ``print()`` to the
parent's captured stdout (not with ``-s``, not at any ``-n``), so an earlier
stdout-based probe always reported nothing and the guard skipped *permanently* —
a vacuous safeguard. The probe now uses a **file transport**: each worker writes
``str(Path.home())`` to ``OUT / <pid>`` in a parent-supplied dir, which the
parent reads after the subprocess exits. This was verified to surface the
worker's real home under ``-n auto --dist loadfile``. ``test_detection_transport_observes_worker_home``
pins this transport so a regression back to stdout-only is caught.

Mirrors the WP-gated-skip convention in
``tests/architectural/test_docs_cli_reference_parity.py`` and the subprocess
ratchet idiom in ``tests/architectural/test_no_op_stable_writes.py``.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from tests._support.coverage_safety import Mutation, assert_mutation_caught
from tests.conftest import _REAL_HOME_ENV_VAR

pytestmark = [pytest.mark.architectural]

# Dedicated sentinel under the real home. The guard asserts on THIS path only
# (Risks & Mitigations: assert on a dedicated sentinel, capture before/after)
# so it never depends on unrelated ``~/.spec-kitty`` churn from other tooling.
_SENTINEL_RELPATH = ".spec-kitty/.home_isolation_guard_sentinel"

_REPO_ROOT = Path(__file__).resolve().parents[2]

# This is NOT "isolation absent" — it is "the
# file transport produced no worker homes at all". That means xdist did not
# run the probe (unavailable / collection error) OR the transport itself broke.
# Conflating this with a soft skip would let a future transport breakage
# silently disarm the guard, so we surface it as a hard failure.
_NO_WORKER_HOMES = (
    "Home-isolation detection probe produced NO worker homes under -n auto. "
    "The file transport (worker writes Path.home() to a parent-supplied dir) "
    "observed nothing: xdist did not run the probe, or the transport is "
    "broken. This is a hard failure, not a skip — a skip here would silently "
    "disarm the SC-006 guard. stdout:\n{stdout}\nstderr:\n{stderr}"
)


def _probe_body(out_dir: Path, *, write_sentinel: bool) -> str:
    """Source of a single ``test_probe`` that reports its worker home via file.

    Every probe writes ``str(Path.home())`` to ``OUT / <pid>`` so the parent can
    observe which home the worker resolved to (the xdist-safe transport). When
    *write_sentinel* is True it additionally writes the dedicated sentinel under
    ``Path.home()/.spec-kitty`` — the representative mutation that, absent WP04
    isolation, would land in the real home.
    """
    lines = [
        "import os",
        "from pathlib import Path",
        "",
        "",
        f"OUT = Path({str(out_dir)!r})",
        "",
        "",
        "def test_probe():",
        "    OUT.mkdir(parents=True, exist_ok=True)",
        "    (OUT / str(os.getpid())).write_text(str(Path.home()), encoding='utf-8')",
    ]
    if write_sentinel:
        lines += [
            f"    sentinel = Path.home() / {_SENTINEL_RELPATH!r}",
            "    sentinel.parent.mkdir(parents=True, exist_ok=True)",
            "    sentinel.write_text('worker wrote here', encoding='utf-8')",
            "    assert sentinel.read_text(encoding='utf-8') == 'worker wrote here'",
        ]
    return "\n".join(lines)


def _run_probe(
    out_dir: Path, *, parallel: bool, write_sentinel: bool
) -> subprocess.CompletedProcess[str]:
    """Run the probe as a one-test pytest module in a subprocess.

    When *parallel* is True the run uses ``-n auto --dist loadfile`` so the probe
    executes on an xdist worker (where WP04's isolation applies); otherwise it
    runs serially. The module is collected from a throwaway temp dir under the
    repo root so the repo's own conftest (and thus WP04's autouse fixture, once
    present) still applies via ``rootdir`` discovery.
    """
    probe_parent = _REPO_ROOT / ".pytest_cache" / "home-isolation-probes"
    probe_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=probe_parent) as tmp:
        module = Path(tmp) / "test_home_probe.py"
        module.write_text(
            _probe_body(out_dir, write_sentinel=write_sentinel),
            encoding="utf-8",
        )
        parallel_flags = (
            ["-n", "auto", "--dist", "loadfile"] if parallel else ["-p", "no:xdist"]
        )
        return subprocess.run(  # noqa: S603 — fixed pytest invocation, no shell input
            [
                sys.executable,
                "-m",
                "pytest",
                str(module),
                "-q",
                "-p",
                "no:cacheprovider",
                *parallel_flags,
            ],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )


def _read_worker_homes(out_dir: Path) -> list[str]:
    """Read every worker-reported ``Path.home()`` from the file transport.

    Each worker wrote one file (named by its pid) containing the home it
    resolved to. Returns the de-duplicated, sorted list of those homes. Empty
    iff no worker ran the probe (the caller treats that as a hard failure, not
    a silent skip — see :data:`_NO_WORKER_HOMES`).
    """
    if not out_dir.exists():
        return []
    homes = {
        f.read_text(encoding="utf-8").strip()
        for f in out_dir.iterdir()
        if f.is_file()
    }
    return sorted(h for h in homes if h)


def _isolation_active_from_homes(worker_homes: list[str], real_home: str) -> bool:
    """Decide whether WP04 isolation is active from observed worker homes.

    Pure decision used by the guard *and* by its anti-vacuity unit test. Returns
    True iff every observed worker home is redirected away from *real_home*
    (WP04 isolation active). Callers must have already verified *worker_homes*
    is non-empty — an empty list is a transport failure, not "isolation absent",
    and is handled separately.
    """
    return all(home != real_home for home in worker_homes)


def _sentinel_unchanged(
    before: tuple[bool, int, float] | None,
    after: tuple[bool, int, float] | None,
) -> bool:
    """True iff the real-home sentinel snapshot is identical before/after.

    Pure compare extracted so the mutation assertion can be exercised directly:
    a regression (worker reached the real home) changes ``after`` and this
    returns False; correct isolation leaves them equal and this returns True.
    """
    return after == before


def _detect_worker_homes(out_dir: Path) -> tuple[list[str], subprocess.CompletedProcess[str]]:
    """Run the read-only probe under ``-n auto`` and return observed worker homes.

    The probe only writes to the parent-supplied *out_dir* and reads
    ``Path.home()`` — it never writes to the real home — so detection is safe
    regardless of whether per-worker HOME isolation (WP04) is active. Returns
    ``(worker_homes, completed_process)`` so callers can both inspect the
    homes and surface subprocess diagnostics on failure.
    """
    result = _run_probe(out_dir, parallel=True, write_sentinel=False)
    return _read_worker_homes(out_dir), result


def test_detection_transport_observes_worker_home() -> None:
    """The file transport surfaces a worker's ``Path.home()`` under ``-n auto``.

    This pins the *transport itself*: pytest-xdist does not forward worker
    stdout to the parent, so the detection must use the file channel. If a
    future change regresses detection back to stdout-only, this test fails
    (the skip path of the guard would otherwise stay silently untested and the
    SC-006 guard would disarm).
    """
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp) / "homes"
        worker_homes, result = _detect_worker_homes(out_dir)

    assert result.returncode == 0, (
        "detection probe subprocess failed unexpectedly:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert worker_homes, (
        "File transport observed NO worker homes under -n auto — the "
        "worker->parent channel is broken (the exact regression this test "
        f"guards against).\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    # Before WP04 landed, the worker resolved to the real home; now it
    # resolves to a per-worker temp home. Either way the transport must
    # surface *a* home — that is the property under test here, independent
    # of whether per-worker HOME isolation is active.
    assert all(home for home in worker_homes)


def test_no_real_home_mutation_under_xdist() -> None:
    """The real ``~/.spec-kitty`` sentinel is untouched by an xdist run (SC-006).

    Isolation is required on this branch (WP04 shipped long ago): asserts every
    observed xdist worker resolved ``Path.home()`` away from the real home,
    then captures the real sentinel's state, runs a parallel selection that
    writes a sentinel via ``Path.home()``, and asserts the real path is
    unchanged.
    """
    real_home = Path(os.environ[_REAL_HOME_ENV_VAR])

    with tempfile.TemporaryDirectory() as tmp:
        detect_dir = Path(tmp) / "homes"
        worker_homes, detect_result = _detect_worker_homes(detect_dir)

    # No homes at all → the transport observed nothing. Distinct from "isolation
    # absent"; treat as a hard failure so a transport breakage cannot silently
    # disarm the guard (secondary review point).
    assert worker_homes, _NO_WORKER_HOMES.format(
        stdout=detect_result.stdout, stderr=detect_result.stderr
    )

    assert _isolation_active_from_homes(worker_homes, str(real_home)), (
        "Per-worker HOME isolation (WP04) has regressed: at least one xdist "
        f"worker resolved Path.home() to the real home ({real_home!r}). "
        f"Observed worker homes: {worker_homes!r}."
    )

    _assert_real_sentinel_untouched(real_home)


def _assert_real_sentinel_untouched(real_home: Path) -> None:
    """Drive a parallel sentinel write and assert no real-home churn.

    Extracted as a single named unit so the isolation-mutation assertion has a
    dedicated home; always reachable now that WP04's isolation fixture has
    shipped and isolation is required, not merely detected-and-skipped.
    """
    real_sentinel = real_home / _SENTINEL_RELPATH

    def _snapshot() -> tuple[bool, int, float] | None:
        if not real_sentinel.exists():
            return None
        st = real_sentinel.stat()
        return (True, st.st_size, st.st_mtime)

    before = _snapshot()

    # A representative parallel selection: a probe that WRITES a sentinel under
    # Path.home()/.spec-kitty. Under WP04 isolation this lands in the worker's
    # temp home, never the real one. If a regression drops isolation, this would
    # hit the real sentinel and the after-snapshot would change.
    with tempfile.TemporaryDirectory() as tmp:
        mutate_dir = Path(tmp) / "homes"
        result = _run_probe(mutate_dir, parallel=True, write_sentinel=True)
    assert result.returncode == 0, (
        "home-isolation probe subprocess failed unexpectedly:\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    after = _snapshot()
    assert _sentinel_unchanged(before, after), (
        "Real ~/.spec-kitty sentinel was mutated by an xdist run "
        f"(SC-006 / E1 I2 regression): before={before!r} after={after!r}. "
        "A parallel worker reached the developer's real home instead of its "
        "isolated per-worker home — WP04's isolation guarantee has regressed."
    )


# --- Anti-vacuity unit tests (no subprocess) -------------------------------
#
# The reviewer's bar (same as T008): prove the guard *bites* on a regression and
# *passes* on correct isolation, using a simulated isolated home so we do not
# depend on WP04 actually being present. We exercise the two pure helpers the
# integration guard composes:
#   * _read_worker_homes  — the xdist-safe file transport (regression-proofed
#     against a return to stdout-only),
#   * _sentinel_unchanged — the mutation assertion (must FAIL when a worker
#     reaches the real home, PASS when isolation redirects it).

_REAL_HOME = "/real/home"
_ISOLATED_HOME = "/nonexistent/worker-0/home"


def test_probe_body_uses_file_transport_not_stdout(tmp_path: Path) -> None:
    """The generated probe reports its home via the file channel, never stdout.

    Pins the transport at source level: the detection probe must write
    ``Path.home()`` to ``OUT / <pid>`` (xdist-safe) and must NOT ``print`` it
    (the defect this fix removes). The mutation probe additionally writes the
    real-home sentinel.
    """
    detect_src = _probe_body(tmp_path, write_sentinel=False)
    assert "OUT / str(os.getpid())" in detect_src
    assert "write_text(str(Path.home())" in detect_src
    assert "print(" not in detect_src  # regression guard: no stdout transport
    assert _SENTINEL_RELPATH not in detect_src  # read-only detection probe

    mutate_src = _probe_body(tmp_path, write_sentinel=True)
    assert _SENTINEL_RELPATH in mutate_src
    assert "sentinel.write_text('worker wrote here'" in mutate_src
    assert "print(" not in mutate_src


def test_read_worker_homes_round_trips_file_transport(tmp_path: Path) -> None:
    """``_read_worker_homes`` surfaces what workers wrote (file transport).

    Simulates two xdist workers each writing their resolved ``Path.home()`` to a
    pid-named file in the parent-supplied dir. The parent must read both back —
    this is the property the stdout transport could never satisfy.
    """
    (tmp_path / "1001").write_text(_ISOLATED_HOME, encoding="utf-8")
    (tmp_path / "1002").write_text(_ISOLATED_HOME, encoding="utf-8")

    assert _read_worker_homes(tmp_path) == [_ISOLATED_HOME]


def test_read_worker_homes_empty_when_no_files(tmp_path: Path) -> None:
    """No worker wrote anything → empty list (the hard-failure signal).

    Distinguishes "transport observed nothing" from "isolation absent"; the
    integration guard turns this into a hard failure, not a silent skip.
    """
    assert _read_worker_homes(tmp_path) == []
    assert _read_worker_homes(tmp_path / "missing") == []


def test_isolation_active_decision_is_real() -> None:
    """``_isolation_active_from_homes`` is True only when homes are redirected."""
    assert _isolation_active_from_homes([_ISOLATED_HOME], _REAL_HOME) is True
    assert _isolation_active_from_homes([_REAL_HOME], _REAL_HOME) is False
    # A single leaked worker (real home) among isolated ones is NOT active.
    assert (
        _isolation_active_from_homes([_ISOLATED_HOME, _REAL_HOME], _REAL_HOME)
        is False
    )


def test_sentinel_guard_is_non_vacuous() -> None:
    """The sentinel assertion FAILS on a real-home write and PASSES on redirect.

    Mirrors T008's anti-vacuity bar. We model the snapshot pair as the data and
    plant the regression "a worker mutated the real sentinel" (the ``after``
    snapshot diverges). ``_sentinel_unchanged`` MUST reject it; if it did not,
    :func:`assert_mutation_caught` raises and this test fails — proving the
    guard's core assertion is not a no-op.
    """
    # "Good" world = correct WP04 isolation: the worker wrote its sentinel into
    # its isolated home, so the REAL sentinel is unchanged (before == after).
    before_after = ((True, 16, 100.0), (True, 16, 100.0))

    def check(pair: tuple[tuple[bool, int, float] | None, tuple[bool, int, float] | None]) -> None:
        before, after = pair
        assert _sentinel_unchanged(before, after)

    # Sanity: the redirected (isolated) world passes the guard.
    check(before_after)

    # Plant the SC-006 regression: a worker reached the real home and rewrote the
    # sentinel, so ``after`` diverges (different size + mtime). The guard MUST
    # catch this — otherwise it is vacuous.
    def break_isolation(
        pair: tuple[tuple[bool, int, float] | None, tuple[bool, int, float] | None],
    ) -> tuple[tuple[bool, int, float] | None, tuple[bool, int, float] | None]:
        before, _ = pair
        mutated_after = (True, 32, 200.0)  # worker rewrote the real sentinel
        return (before, mutated_after)

    assert_mutation_caught(
        check,
        before_after,
        Mutation(name="worker mutated real ~/.spec-kitty sentinel", apply=break_isolation),
    )


def test_sentinel_guard_catches_creation_from_absent() -> None:
    """A sentinel created where there was none (None → present) is caught too.

    Covers the "real home had no sentinel, a leaked worker created one" regression
    in addition to the rewrite case above.
    """
    before_after: tuple[tuple[bool, int, float] | None, tuple[bool, int, float] | None] = (
        None,
        None,
    )

    def check(pair: tuple[tuple[bool, int, float] | None, tuple[bool, int, float] | None]) -> None:
        before, after = pair
        assert _sentinel_unchanged(before, after)

    check(before_after)

    def create_sentinel(
        pair: tuple[tuple[bool, int, float] | None, tuple[bool, int, float] | None],
    ) -> tuple[tuple[bool, int, float] | None, tuple[bool, int, float] | None]:
        before, _ = pair
        return (before, (True, 16, 123.0))  # leaked worker created the sentinel

    assert_mutation_caught(
        check,
        before_after,
        Mutation(name="leaked worker created real sentinel", apply=create_sentinel),
    )
