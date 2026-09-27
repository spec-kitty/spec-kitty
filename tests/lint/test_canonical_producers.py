"""Unit tests for scripts/lint_canonical_producers.py.

These tests follow the `function-over-form-testing` tactic: they assert on
observable outcomes (finding codes, line numbers, exit codes) only. They do
not assert on visitor internals.

Mission: canonical-producer-lint-01KS4XX4
Issue: Priivacy-ai/spec-kitty#1248
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import textwrap
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest


pytestmark = [pytest.mark.architectural]


# Load the lint module by file path. The script lives in scripts/ which is
# not a Python package on PYTHONPATH; importlib lets us treat it as a module
# without polluting sys.path semantics.
_SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "lint_canonical_producers.py"
_LINT_MODULE_NAME = "lint_canonical_producers"

#: Populated by the autouse ``_lint_module`` fixture below, once per module.
lint: ModuleType


@pytest.fixture(scope="module", autouse=True)
def _lint_module() -> Iterator[ModuleType]:
    """Load the lint script once for this module's tests.

    ``dataclass()`` on a class defined in a dynamically-loaded module looks
    the class up via ``sys.modules[cls.__module__]``, so the module must be
    registered there before ``exec_module`` runs. A module-scoped
    ``pytest.MonkeyPatch.context()`` — not the function-scoped ``monkeypatch``
    fixture, which a module-scoped fixture cannot depend on — keeps that
    registration and undoes it once every test in this module has run.
    """
    global lint
    with pytest.MonkeyPatch.context() as mp:
        spec = importlib.util.spec_from_file_location(_LINT_MODULE_NAME, _SCRIPT_PATH)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        mp.setitem(sys.modules, _LINT_MODULE_NAME, module)
        spec.loader.exec_module(module)
        lint = module
        yield module


def _write(tmp_path: Path, name: str, source: str) -> Path:
    path = tmp_path / name
    path.write_text(textwrap.dedent(source), encoding="utf-8")
    return path


def _lint_source(tmp_path: Path, source: str, name: str = "candidate.py"):
    path = _write(tmp_path, name, source)
    return lint.lint_paths([path])


# --------------------------------------------------------------------------- #
# Negative cases (canonical construction; lint must stay silent)               #
# --------------------------------------------------------------------------- #


def test_lint_clean_canonical_construction_zero_findings(tmp_path: Path) -> None:
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
    )
    assert findings == []


def test_lint_canonical_dict_inside_envelope_zero_findings(tmp_path: Path) -> None:
    findings = _lint_source(
        tmp_path,
        """
        def make():
            return EventEnvelope(
                payload={"event_type": "X", "payload": {"k": "v"}},
            )
        """,
    )
    # The literal IS inside a canonical call (EventEnvelope), so no CP001.
    assert findings == []


def test_lint_unrelated_dict_str_any_zero_findings(tmp_path: Path) -> None:
    findings = _lint_source(
        tmp_path,
        """
        from typing import Any

        def f() -> dict[str, Any]:
            return {"foo": 1, "bar": 2}
        """,
    )
    assert findings == []


def test_lint_emit_with_model_dump_zero_findings(tmp_path: Path) -> None:
    findings = _lint_source(
        tmp_path,
        """
        def go(client, p):
            client.emit_status(payload=p.model_dump())
        """,
    )
    assert findings == []


def test_lint_emit_with_name_bound_zero_findings(tmp_path: Path) -> None:
    findings = _lint_source(
        tmp_path,
        """
        def go(client, payload):
            client.emit_status(payload=payload)
        """,
    )
    assert findings == []


# --------------------------------------------------------------------------- #
# Positive cases (must fire)                                                   #
# --------------------------------------------------------------------------- #


def test_lint_hand_rolled_event_dict_fires_cp001(tmp_path: Path) -> None:
    findings = _lint_source(
        tmp_path,
        """
        def f():
            x = {"event_type": "WPApproved", "payload": {"wp_id": "WP01"}}
            return x
        """,
    )
    codes = [f.code for f in findings]
    assert "CP001" in codes
    assert all(f.path.name == "candidate.py" for f in findings)


def test_lint_dict_str_any_return_fires_cp002(tmp_path: Path) -> None:
    findings = _lint_source(
        tmp_path,
        """
        from typing import Any

        def f() -> dict[str, Any]:
            return {"event_type": "X", "payload": {"k": "v"}}
        """,
    )
    codes = [f.code for f in findings]
    # CP002 must fire; CP001 may also fire (the dict literal is also a CP001
    # candidate). The point is that the offence is caught at least once.
    assert "CP002" in codes


def test_lint_async_dict_str_any_return_fires_cp002(tmp_path: Path) -> None:
    findings = _lint_source(
        tmp_path,
        """
        from typing import Any

        async def f() -> dict[str, Any]:
            return {"event_type": "X", "payload": {"k": "v"}}
        """,
    )
    assert "CP002" in [f.code for f in findings]


def test_lint_emit_with_inline_dict_payload_fires_cp003(tmp_path: Path) -> None:
    findings = _lint_source(
        tmp_path,
        """
        def go(client):
            client.emit_status(payload={"event_type": "X", "payload": {}})
        """,
    )
    assert "CP003" in [f.code for f in findings]


def test_lint_enqueue_with_inline_dict_payload_fires_cp003(tmp_path: Path) -> None:
    findings = _lint_source(
        tmp_path,
        """
        def go(q):
            q.enqueue_event(payload={"event_type": "X", "payload": {}})
        """,
    )
    assert "CP003" in [f.code for f in findings]


def test_lint_send_event_with_inline_dict_payload_fires_cp003(tmp_path: Path) -> None:
    findings = _lint_source(
        tmp_path,
        """
        def go(client):
            send_event(payload={"event_type": "X", "payload": {}})
        """,
    )
    assert "CP003" in [f.code for f in findings]


# --------------------------------------------------------------------------- #
# Exemption cases                                                              #
# --------------------------------------------------------------------------- #


def test_lint_exempt_with_valid_tracker_zero_findings(tmp_path: Path) -> None:
    findings = _lint_source(
        tmp_path,
        """
        def f():
            # canonical-producer-exempt: #1248 -- intentional regression-test fixture
            x = {"event_type": "WPApproved", "payload": {"wp_id": "WP01"}}
            return x
        """,
    )
    assert findings == []


def test_lint_exempt_with_full_tracker_path_zero_findings(tmp_path: Path) -> None:
    findings = _lint_source(
        tmp_path,
        """
        def f():
            # canonical-producer-exempt: Priivacy-ai/spec-kitty#1248 -- fixture
            x = {"event_type": "WPApproved", "payload": {"wp_id": "WP01"}}
            return x
        """,
    )
    assert findings == []


def test_lint_exempt_with_malformed_tracker_fires_cp900(tmp_path: Path) -> None:
    findings = _lint_source(
        tmp_path,
        """
        def f():
            # canonical-producer-exempt: TODO -- fix later
            x = {"event_type": "WPApproved", "payload": {"wp_id": "WP01"}}
            return x
        """,
    )
    codes = [f.code for f in findings]
    # CP900 must fire (malformed tracker). The original CP001 must NOT fire
    # because the exemption (even malformed) suppresses the underlying
    # finding -- the operator's attention is redirected to CP900 instead.
    assert "CP900" in codes
    assert "CP001" not in codes


def test_lint_exempt_above_literal_zero_findings(tmp_path: Path) -> None:
    findings = _lint_source(
        tmp_path,
        """
        def f():
            # canonical-producer-exempt: #1248 -- comment-above-literal form
            x = {
                "event_type": "WPApproved",
                "payload": {"wp_id": "WP01"},
            }
            return x
        """,
    )
    assert findings == []


def test_lint_dangling_malformed_exemption_fires_cp900(tmp_path: Path) -> None:
    # Even if the exemption doesn't attach to any violation, a malformed one
    # by itself is still flagged so the codebase doesn't accumulate dead /
    # broken exemption comments.
    findings = _lint_source(
        tmp_path,
        """
        # canonical-producer-exempt: TODO -- dangling exemption
        x = 1
        """,
    )
    assert "CP900" in [f.code for f in findings]


# --------------------------------------------------------------------------- #
# Category-backed test-fixture exemption (canonical-event-exempt, #1927)        #
# --------------------------------------------------------------------------- #


def test_event_exempt_comparison_zero_findings(tmp_path: Path) -> None:
    findings = _lint_source(
        tmp_path,
        """
        def test_thing():
            # canonical-event-exempt(comparison): asserts emit output equals this expected dict
            expected = {"event_type": "WPApproved", "payload": {"wp_id": "WP01"}}
            assert expected == expected
        """,
    )
    assert findings == []


def test_event_exempt_exception_flow_zero_findings(tmp_path: Path) -> None:
    findings = _lint_source(
        tmp_path,
        """
        def test_thing():
            # canonical-event-exempt(exception-flow): malformed shape feeds the defensive guard
            malformed = {"event_type": "X", "payload": None}
            return malformed
        """,
    )
    assert findings == []


def test_event_exempt_above_literal_zero_findings(tmp_path: Path) -> None:
    findings = _lint_source(
        tmp_path,
        """
        def test_thing():
            # canonical-event-exempt(exception-flow): legacy shape
            x = {
                "event_type": "X",
                "payload": {"k": "v"},
            }
            return x
        """,
    )
    assert findings == []


def test_event_exempt_unknown_category_fires_cp901(tmp_path: Path) -> None:
    findings = _lint_source(
        tmp_path,
        """
        def test_thing():
            # canonical-event-exempt(typo): not a real category
            x = {"event_type": "X", "payload": {"k": "v"}}
            return x
        """,
    )
    codes = [f.code for f in findings]
    # CP901 fires (bad category); the underlying CP001 is suppressed so the
    # operator's attention is redirected to the malformed annotation.
    assert "CP901" in codes
    assert "CP001" not in codes


def test_event_exempt_empty_reason_fires_cp901(tmp_path: Path) -> None:
    findings = _lint_source(
        tmp_path,
        """
        def test_thing():
            # canonical-event-exempt(comparison):
            x = {"event_type": "X", "payload": {"k": "v"}}
            return x
        """,
    )
    assert "CP901" in [f.code for f in findings]


def test_event_exempt_dangling_malformed_fires_cp901(tmp_path: Path) -> None:
    findings = _lint_source(
        tmp_path,
        """
        # canonical-event-exempt(typo): dangling, attaches to nothing
        x = 1
        """,
    )
    assert "CP901" in [f.code for f in findings]


def test_event_exempt_covers_cp002_return(tmp_path: Path) -> None:
    # A dict[str, Any]-returning helper that builds an event-shaped dict (CP002)
    # is also silenced by a single canonical-event-exempt on the return literal.
    findings = _lint_source(
        tmp_path,
        """
        from typing import Any

        def _make() -> dict[str, Any]:
            # canonical-event-exempt(exception-flow): legacy wire shape under test
            return {"event_type": "X", "payload": {"k": "v"}}
        """,
    )
    assert findings == []


# --------------------------------------------------------------------------- #
# CLI / exit code                                                              #
# --------------------------------------------------------------------------- #


def test_lint_cli_exit_zero_on_clean(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "clean.py",
        """
        def f():
            return 1
        """,
    )
    result = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH), "--paths", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_lint_cli_exit_one_on_violation(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "dirty.py",
        """
        def f():
            return {"event_type": "X", "payload": {}}
        """,
    )
    # We need to mark the def's return type to trigger CP002, OR rely on
    # CP001 firing on the bare literal. Bare literal alone is enough:
    _write(
        tmp_path,
        "dirty2.py",
        """
        x = {"event_type": "X", "payload": {"k": "v"}}
        """,
    )
    result = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH), "--paths", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "CP001" in result.stdout


def test_lint_cli_exit_two_on_missing_path(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT_PATH),
            "--paths",
            str(tmp_path / "does-not-exist"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2


def test_lint_cli_exit_two_on_no_args() -> None:
    result = subprocess.run(
        [sys.executable, str(_SCRIPT_PATH)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2


# --------------------------------------------------------------------------- #
# Edge cases that must NOT regress                                              #
# --------------------------------------------------------------------------- #


def test_lint_partial_event_keys_zero_findings(tmp_path: Path) -> None:
    # A dict with only one of {event_type, payload} is not an event shape.
    findings = _lint_source(
        tmp_path,
        """
        def f():
            return {"event_type": "X"}
        """,
    )
    # CP001 requires both keys present.
    assert "CP001" not in [f.code for f in findings]


def test_lint_dict_str_any_partial_event_key_still_fires_cp002(tmp_path: Path) -> None:
    # CP002's "event-shaped" bar is intentionally lower -- ANY event key in
    # the body of a dict[str, Any] return is enough to flag, because the
    # documented hand-rolled drift case is "I made up a dict and forgot one
    # of the canonical keys."
    findings = _lint_source(
        tmp_path,
        """
        from typing import Any

        def f() -> dict[str, Any]:
            return {"event_type": "X"}
        """,
    )
    assert "CP002" in [f.code for f in findings]


def test_lint_skips_unparseable_file(tmp_path: Path) -> None:
    _write(tmp_path, "broken.py", "def f(:\n    pass\n")
    # Bad syntax -- lint refuses to emit canonical-producer findings on a
    # tree it can't parse. The other lints catch the syntax error.
    findings = lint.lint_paths([tmp_path])
    assert findings == []


def test_lint_call_with_payload_kwarg_non_emit_zero_findings(tmp_path: Path) -> None:
    # An inline dict passed as payload= to a function NOT matching the
    # emit_* / enqueue_* / send_event patterns must NOT fire.
    findings = _lint_source(
        tmp_path,
        """
        def f(thing):
            thing.set_metadata(payload={"event_type": "X", "payload": {}})
        """,
    )
    assert "CP003" not in [f.code for f in findings]


# --------------------------------------------------------------------------- #
# Baseline (ratchet) behavior                                                  #
# --------------------------------------------------------------------------- #


def test_lint_cli_update_baseline_writes_findings_and_exits_zero(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path,
        "dirty.py",
        """
        x = {"event_type": "X", "payload": {"k": "v"}}
        """,
    )
    baseline = tmp_path / "baseline.txt"
    result = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT_PATH),
            "--paths",
            str(tmp_path),
            "--update-baseline",
            str(baseline),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert baseline.exists()
    text = baseline.read_text()
    assert "CP001" in text
    assert "dirty.py" in text


def test_lint_cli_baseline_silences_known_violations(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "dirty.py",
        """
        x = {"event_type": "X", "payload": {"k": "v"}}
        """,
    )
    baseline = tmp_path / "baseline.txt"
    # First seed the baseline.
    subprocess.run(
        [
            sys.executable,
            str(_SCRIPT_PATH),
            "--paths",
            str(tmp_path),
            "--update-baseline",
            str(baseline),
        ],
        check=True,
        capture_output=True,
    )
    # Now lint with the baseline -- should exit clean.
    result = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT_PATH),
            "--paths",
            str(tmp_path),
            "--baseline",
            str(baseline),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_lint_cli_baseline_does_not_silence_new_file_violations(
    tmp_path: Path,
) -> None:
    _write(
        tmp_path,
        "old.py",
        """
        x = {"event_type": "X", "payload": {"k": "v"}}
        """,
    )
    baseline = tmp_path / "baseline.txt"
    subprocess.run(
        [
            sys.executable,
            str(_SCRIPT_PATH),
            "--paths",
            str(tmp_path),
            "--update-baseline",
            str(baseline),
        ],
        check=True,
        capture_output=True,
    )
    # Add a NEW file with a new violation -- it must NOT be silenced.
    _write(
        tmp_path,
        "new.py",
        """
        y = {"event_type": "Y", "payload": {"k": "v"}}
        """,
    )
    result = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT_PATH),
            "--paths",
            str(tmp_path),
            "--baseline",
            str(baseline),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "new.py" in result.stdout
    assert "old.py" not in result.stdout  # silenced by baseline


def test_lint_cli_baseline_warns_on_stale_entries(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.txt"
    # Pre-seed a stale entry pointing at a path that won't be re-found.
    baseline.write_text(
        f"# header\n{tmp_path / 'ghost.py'}::CP001\n",
        encoding="utf-8",
    )
    _write(
        tmp_path,
        "clean.py",
        """
        x = 1
        """,
    )
    result = subprocess.run(
        [
            sys.executable,
            str(_SCRIPT_PATH),
            "--paths",
            str(tmp_path),
            "--baseline",
            str(baseline),
        ],
        capture_output=True,
        text=True,
    )
    # Clean tree, only a stale baseline entry -> exits 0 but warns.
    assert result.returncode == 0
    assert "no longer correspond" in result.stderr
    assert "ghost.py" in result.stderr
