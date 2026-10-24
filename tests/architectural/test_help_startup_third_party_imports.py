"""Per-PR architectural gate: a bare ``spec-kitty --help`` loads no heavy, call-time-only library.

Regression guard for #6638 (and #6584, #4409 before it). ``--help`` assembles the whole
Typer app, so every module-scope import in every command module runs on it. A library
that is only needed when a command body runs (an HTTP client for the upgrade nag, a
charset detector for a mis-encoded file, a JSON-schema validator) costs every
invocation its import time when it is imported at module scope anywhere on that path.
#6638 found two: ``specify_cli.compat.provider`` imported ``httpx`` (about 70 ms) and
``charter.encoding_recovery`` imported ``charset_normalizer`` (about 18 ms).

The nightly wall-clock ratio (``tests/performance/test_cli_startup_budget_4409.py``)
catches the sum of such costs only once it crosses ``STARTUP_RATIO_LIMIT``, which it
did twice in a week by about 1 percent (#6584, #6638). This gate is the deterministic
half: it names the libraries and fails on the PR that brings one back, whatever its
size. Import the library inside the function that uses it instead.

The ``jsonschema`` module-scope scan in the 4409 test file stays; it runs only with the
performance directory, and this gate covers ``jsonschema`` per PR as well. The gate runs
in the architectural battery on Linux; it carries no ``windows_ci`` marker, and its
minimal child environment (``PATH``, no ``SYSTEMROOT``) assumes a POSIX host.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"

#: Top-level distributions ``--help`` must not load. Each is needed only when a command
#: body runs. Empty-allowlist invariant: there is no exemption list.
FORBIDDEN_ON_HELP: tuple[str, ...] = (
    "httpx",  # #6638: compat.provider, upgrade probe, simple index
    "charset_normalizer",  # #6638: charter.encoding_recovery
    "jsonschema",  # #4409: format checkers pull rfc3987_syntax
    "rfc3987_syntax",  # #4409: builds a Lark grammar at import (~1.8 s)
    "pytest",  # test-only; never on a product start-up path
    "_pytest",
)

#: Modules that once carried a forbidden import at module scope. They must still load
#: on ``--help``; if one stops loading, the gate no longer covers the edge it was
#: written for and says so instead of passing.
_FORMER_IMPORTERS: tuple[str, ...] = (
    "specify_cli.compat.provider",
    "charter.encoding_recovery",
)

#: Floor on the module count: the whole app is assembled (about 1600 modules at
#: authoring time), not a fast path that registers one command. 1000 sits well below
#: the real count and well above any single-command fast path.
_MIN_HELP_MODULES = 1000

_SENTINEL = "HELP_MODULES="

_HELP_PROBE = r"""
import contextlib, io, json, sys
_SENTINEL = "HELP_MODULES="
sys.argv = ["spec-kitty", "--help"]
import specify_cli
try:
    with contextlib.redirect_stdout(io.StringIO()):
        specify_cli.main()
except SystemExit as exc:
    if exc.code not in (0, None):
        raise
print(_SENTINEL + json.dumps(sorted(sys.modules)))
"""


def forbidden_modules(loaded: Iterable[str]) -> list[str]:
    """Return the loaded modules that belong to a forbidden distribution."""
    return sorted(name for name in loaded if name.split(".", 1)[0] in FORBIDDEN_ON_HELP)


def _modules_loaded_by_help() -> list[str]:
    completed = subprocess.run(
        [sys.executable, "-c", _HELP_PROBE],
        cwd=_REPO_ROOT,
        env={"PYTHONPATH": str(_SRC), "PATH": "/usr/bin:/bin", "HOME": str(_REPO_ROOT / ".nonexistent-home")},
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, f"`spec-kitty --help` probe failed:\n{completed.stderr[-2000:]}"
    lines = [line for line in completed.stdout.splitlines() if line.startswith(_SENTINEL)]
    assert len(lines) == 1, f"probe printed no module list:\n{completed.stdout[-2000:]}"
    loaded: list[str] = json.loads(lines[0].removeprefix(_SENTINEL))
    return loaded


def test_help_loads_no_call_time_only_library() -> None:
    loaded = _modules_loaded_by_help()
    assert len(loaded) > _MIN_HELP_MODULES, f"--help loaded only {len(loaded)} modules: the probe did not assemble the app, so the check is vacuous"
    missing = sorted(set(_FORMER_IMPORTERS) - set(loaded))
    assert not missing, f"{missing} no longer load on --help; update _FORMER_IMPORTERS so the gate still covers a real edge"
    leaked = forbidden_modules(loaded)
    assert not leaked, (
        f"#6638: `spec-kitty --help` loads {leaked}. Every CLI invocation pays that import. "
        "Import the library inside the function that uses it, not at module scope."
    )


@pytest.mark.parametrize("planted", ["httpx", "httpx._client", "charset_normalizer.api", "jsonschema", "_pytest.config"])
def test_planted_forbidden_module_is_detected(planted: str) -> None:
    """Self-mutation: a planted forbidden module (top-level or submodule) is reported."""
    assert forbidden_modules(["typer", "specify_cli", planted]) == [planted]


def test_lookalike_names_are_not_detected() -> None:
    """Matching is by top-level distribution, so a name that merely starts alike is clean."""
    assert forbidden_modules(["httpx_extra", "pytest_helpers", "specify_cli.jsonschema_utils"]) == []
