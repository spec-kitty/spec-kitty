"""Always-on round-trip gate: ``scripts/lint_canonical_producers.py`` stays wired.

Lifted from ``tests/lint/test_canonical_producers.py`` (mission
canonical-producer-lint-01KS4XX4), a ``tests/lint`` tree recorded
``out_of_matrix`` in ``.github/ci-module-registry.yml`` — no per-PR lane
selects it (#4374 disposition ledger, disposition 2 — lift-invariant).

The source suite is a broad, ~34-test unit suite covering every CP00x
finding code and CLI exit path — genuinely more than one enumerable
invariant, so it is NOT lifted wholesale here (per the WP02 Definition of
Done: "a lift is ONE invariant"; the full edge-case matrix stays
make-test-full-only pending a future promotion decision). What IS lifted is
the single round-trip invariant the tree's disposition depends on: the lint
script still distinguishes canonical construction (zero findings) from the
classic hand-rolled event-dict violation (CP001) — i.e. the linter has not
silently gone inert.
"""

from __future__ import annotations

import importlib.util
import sys
import textwrap
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural]

_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "lint_canonical_producers.py"


def _load_lint_module(monkeypatch: pytest.MonkeyPatch):
    spec = importlib.util.spec_from_file_location("lint_canonical_producers", _SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "lint_canonical_producers", module)
    spec.loader.exec_module(module)
    return module


def _lint_source(tmp_path: Path, source: str, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "candidate.py"
    path.write_text(textwrap.dedent(source), encoding="utf-8")
    lint = _load_lint_module(monkeypatch)
    return lint.lint_paths([path])


def test_clean_canonical_construction_yields_zero_findings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    findings = _lint_source(
        tmp_path,
        """
        from spec_kitty_events.lifecycle import WPApprovedPayload

        def make():
            return WPApprovedPayload(
                wp_id="WP01",
                actor="claude",
            )
        """,
        monkeypatch,
    )
    assert findings == []


def test_hand_rolled_event_dict_still_fires_cp001(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    findings = _lint_source(
        tmp_path,
        """
        def f():
            x = {"event_type": "WPApproved", "payload": {"wp_id": "WP01"}}
            return x
        """,
        monkeypatch,
    )
    codes = [f.code for f in findings]
    assert "CP001" in codes, "canonical-producer lint has gone inert: a hand-rolled event dict no longer fires CP001"
