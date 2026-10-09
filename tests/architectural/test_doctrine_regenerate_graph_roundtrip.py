"""Golden DRG round-trip behavior-lock (mission doctrine-public-api-surface, WP01).

This is the shared behavior baseline that WP08 (campsite Sonar / literal hoist),
WP09 (extractor complexity refactor) and WP10 (remaining complexity closeout) rely
on: ``spec-kitty charter pack regenerate-graph --check`` regenerates the DRG into a temp
directory and byte-compares it against the committed
``packs/built-in/**/*.graph.yaml`` fragments (14 today), exiting non-zero when stale.

An exit 0 here means the FR-009 literal hoist and the FR-010 complexity refactor left
the DRG output byte-identical (C-006, C7). Reusing the shipped ``--check`` mechanism is
deliberate — no bespoke golden fixture is built.

**Hard precondition, not a skip (post-tasks squad):** CLI unavailability must FAIL, never
``xfail``/skip. A skipped golden would make WP08–10's "byte-identical" definition-of-done
vacuously green, so "the golden actually ran (not skipped)" is part of the WP08/09/10
acceptance. This test therefore hard-fails if ``spec-kitty`` cannot be invoked.

Stale-install note: ``spec-kitty`` is a console-script entry point; run ``pip install -e .``
before this test if the CLI shells out stale (a stale install reports false reds).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_GOLDEN_ROOT = _REPO_ROOT / "packs" / "built-in"


def _regenerate_graph_check() -> subprocess.CompletedProcess[str]:
    """Invoke ``spec-kitty charter pack regenerate-graph --check`` as a subprocess.

    Prefer the ``spec-kitty`` console script; fall back to ``python -m specify_cli``
    so a PATH without the shim still exercises the real CLI. Hard-fail (never skip)
    when neither entry point is invocable — the golden must not be silently vacuous.
    """
    spec_kitty = shutil.which("spec-kitty")
    if spec_kitty is not None:
        argv = [spec_kitty, "charter", "pack", "regenerate-graph", "--check"]
    else:
        argv = [
            sys.executable,
            "-m",
            "specify_cli",
            "charter",
            "pack",
            "regenerate-graph",
            "--check",
        ]
    try:
        return subprocess.run(
            argv,
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover - env failure
        pytest.fail(
            "Could not invoke `spec-kitty charter pack regenerate-graph --check` "
            f"({argv[0]}): {exc}. The golden round-trip is a hard precondition — "
            "it must run, not skip. Run `pip install -e .` and retry."
        )


def test_committed_golden_fragments_present() -> None:
    """The committed golden fragments exist — the round-trip has something to lock."""
    fragments = list(_GOLDEN_ROOT.rglob("*.graph.yaml"))
    assert fragments, (
        f"No committed golden `*.graph.yaml` fragments under {_GOLDEN_ROOT}. "
        "The behavior-lock has nothing to compare against."
    )


def test_regenerate_graph_check_is_byte_identical() -> None:
    """C7 / FR-009 / FR-010: `regenerate-graph --check` exits 0 (DRG byte-identical)."""
    result = _regenerate_graph_check()
    assert result.returncode == 0, (
        "`spec-kitty charter pack regenerate-graph --check` exited "
        f"{result.returncode} — the DRG graph source is NOT byte-identical to the "
        "committed golden. A doctrine change altered regeneration output (behavior "
        "drift, C-006 violation) or the golden fragments are stale.\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
