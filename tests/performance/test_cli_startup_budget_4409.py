"""#4409: `spec-kitty --help` must not re-acquire its import-time tax.

Before this guard, a bare ``--help`` cost ~3.2 s while importing the package
itself cost ~0.2 s. Almost all of the difference was one transitive import:
``jsonschema`` eagerly loads its format checkers, and one of those
(``rfc3987_syntax.syntax_helpers``, which builds a Lark grammar at import
time) costs ~1.8 s on its own. Eight modules imported ``jsonschema`` at module
scope, so whichever the CLI touched first paid for all of them — on a path
that validates nothing.

Deferring those imports to their single call sites took ``--help`` to ~1.0 s.
The tax is easy to reintroduce by accident: one ``import jsonschema`` at the
top of a module the CLI imports is enough. This test is the ratchet.

It lives in the ``performance`` lane (nightly) rather than the per-PR gate —
wall-clock budgets are environment-sensitive, and a shared runner under load
should not turn a green change red. The structural half of the guard (no
module-scope ``jsonschema`` import in the CLI's import graph) is cheap and
deterministic, so that half runs everywhere.
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests._perf_helpers import assert_timing_budget

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Modules that must not import ``jsonschema`` at module scope: each one is
#: reachable from the CLI's own import graph, and each uses it in exactly one
#: function. Deferring is what bought the ~2.2 s.
_DEFERRED_JSONSCHEMA_MODULES = (
    "src/charter/offering/agent_profiles/validation.py",
    "src/charter/offering/directives/validation.py",
    "src/charter/offering/paradigms/validation.py",
    "src/charter/offering/styleguides/validation.py",
    "src/charter/offering/tactics/validation.py",
    "src/charter/offering/toolguides/validation.py",
    "src/specify_cli/bulk_edit/occurrence_map.py",
    "src/specify_cli/skills/manifest_store.py",
)

#: Generous enough to absorb a loaded laptop or CI runner, tight enough to
#: catch the ~1.8 s regression this issue removed (pre-fix was ~3.2 s).
_HELP_BUDGET_SECONDS = 2.5


@pytest.mark.parametrize("relative_path", _DEFERRED_JSONSCHEMA_MODULES)
def test_jsonschema_stays_out_of_module_scope(relative_path: str) -> None:
    """The structural half: deterministic, and it is what actually regresses.

    A module-scope ``import jsonschema`` anywhere in this set silently
    reintroduces the whole format-checker chain for every CLI invocation.
    """
    source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")

    offending = [line for line in source.splitlines() if line.startswith(("import jsonschema", "from jsonschema"))]

    assert not offending, (
        f"#4409: {relative_path} imports jsonschema at module scope ({offending}). "
        "That pulls jsonschema._format -> rfc3987_syntax (~1.8s) into every "
        "`spec-kitty` invocation. Import it inside the function that validates."
    )


@pytest.mark.performance
def test_help_stays_inside_its_startup_budget() -> None:
    """The wall-clock half: nightly-only, measured through the real entry point."""
    started = time.monotonic()
    completed = subprocess.run(
        [sys.executable, "-m", "specify_cli.__init__", "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=60,
    )
    elapsed = time.monotonic() - started

    assert completed.returncode == 0, completed.stderr[-2000:]
    assert_timing_budget(elapsed, _HELP_BUDGET_SECONDS, name="spec-kitty --help startup")
