"""No-op-path import-footprint regression guard for ``spec-kitty next`` (WP01).

Mission ``next-latency-durable-fix-01M14RM3``, WP01 (import-graph trim).

**Honest scope (squad finding B2 — see
``kitty-specs/next-latency-durable-fix-01M14RM3/research/post-tasks-squad-findings.md``):**
a real ``next --json`` query re-pulls the entire heavy foundation
(doctrine/charter/events/pydantic/status.models) via
``_run_query_mode -> runtime_bridge`` (``next_cmd.py:185``), so deferring an
import inside ``next_cmd.py`` cannot and does not shrink that path. The only
honest, measurable win is on the **no-op / startup path** — e.g. ``next
--help`` — where ``next_cmd.py`` is imported (paying its module-scope import
graph) but the command body never runs, so a module-scope import that is only
reachable behind ``owned_checkout is not None`` (the ``--owned-checkout``
opt-in) is pure waste.

This test spawns ``python -X importtime -m specify_cli next --help`` as a
subprocess and inspects the emitted import trace. It does **not** assert
anything about a real query's import graph (that would be unsatisfiable per
B2 and is explicitly out of scope for this WP).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SRC = _REPO_ROOT / "src"

# The deferred import (T002): reachable only via the --owned-checkout opt-in
# branch of `next_step`, never on the no-op/--help path. Measured delta at
# authoring time: `next --help` imported 1080 modules after the deferral vs
# 1092 before (checkout_ownership pulls specify_cli.coordination.* and a
# unique-to-it commit_helpers subtree). We assert the specific-module ABSENCE
# below rather than an absolute module count, because the count is
# environment-dependent (it grows with installed optional extras — e.g. CI's
# `uv sync --all-extras`) and would false-red without proving anything the
# absence check doesn't prove directly.
_DEFERRED_MODULE = "specify_cli.core.checkout_ownership"


def _run_importtime_next_help() -> str:
    """Spawn ``python -X importtime -m specify_cli next --help`` and return stderr.

    ``-X importtime`` writes its trace to stderr; ``next --help`` is served by
    the existing ``_is_next_fast_path`` fast path (``cli/commands/__init__.py``)
    so only ``next_cmd`` is imported — the fast path itself is verified by
    ``test_next_fast_path_registers_only_next_command`` below.
    """
    env = {"PYTHONPATH": str(_SRC)}
    import os

    env.update(os.environ)
    env["PYTHONPATH"] = str(_SRC)
    result = subprocess.run(
        [sys.executable, "-X", "importtime", "-m", "specify_cli", "next", "--help"],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert result.returncode == 0, f"`next --help` failed unexpectedly.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    return result.stderr


def _imported_module_names(importtime_stderr: str) -> list[str]:
    names: list[str] = []
    for line in importtime_stderr.splitlines():
        if not line.startswith("import time:"):
            continue
        # Format: "import time:   <self> |  <cumulative> | <indent>module.name"
        _, _, tail = line.partition("|")
        _, _, module_field = tail.partition("|")
        names.append(module_field.strip())
    return names


def test_deferred_import_absent_on_no_op_path() -> None:
    """T004: `checkout_ownership` must not load on the `next --help` no-op path.

    This is the honest in-diff DoD (B2): it would fail if `checkout_ownership`
    (or its `resolve_ownership_claim` / `error_for_claim` imports) were moved
    back to module scope in `next_cmd.py`, since `--help` never enters the
    `owned_checkout is not None` branch that is the only reachable use.
    """
    stderr = _run_importtime_next_help()
    modules = _imported_module_names(stderr)

    assert _DEFERRED_MODULE not in modules, (
        f"{_DEFERRED_MODULE} loaded on the no-op `next --help` path; it must "
        "stay deferred to the `owned_checkout is not None` branch of "
        "next_step (see next_cmd.py T002)."
    )


def test_next_fast_path_registers_only_next_command() -> None:
    """T003: verify (do not re-implement) the existing `next` fast path.

    `register_commands` (`cli/commands/__init__.py:176`) already branches on
    `_is_next_fast_path(sys.argv)` and, on that branch, registers only
    `next_cmd` — not the full command surface. This locks that behavior so a
    future refactor can't silently reinstate importing every command module
    on the `next` path (which would reintroduce the "503ms `_build_app`"
    isolation artifact the mission brief originally (mis)blamed — see B2).
    """
    script = (
        "import sys, typer\n"
        "from specify_cli.cli.commands import register_commands\n"
        "sys.argv = ['spec-kitty', 'next', '--help']\n"
        "app = typer.Typer()\n"
        "register_commands(app)\n"
        "heavy = [m for m in sys.modules if m == 'specify_cli.cli.commands.consolidate' "
        "or m == 'specify_cli.cli.commands.init' or m == 'specify_cli.cli.commands.upgrade']\n"
        "sys.stderr.write('HEAVY=' + repr(sorted(heavy)))\n"
    )
    env = {"PYTHONPATH": str(_SRC)}
    import os

    env.update(os.environ)
    env["PYTHONPATH"] = str(_SRC)
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert result.returncode == 0, f"registering commands on the next fast path failed.\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert "HEAVY=[]" in result.stderr, f"register_commands imported sibling command modules (merge/init/upgrade) on the `next` fast path: {result.stderr}"


# #5991 / FR-010: modules only the ``next`` command bodies need. ``next_cmd`` once imported them at module
# scope, dragging them onto every ``--help`` (about 230 ms).
FORBIDDEN_ON_HELP: tuple[str, ...] = (
    "charter.activation",
    "runtime.next._internal_runtime.schema",
    "runtime.next.decision",
    "status.dup_key_repair",
)

# Child program: record every ``import`` statement executed by ``next_cmd``'s module body. Recording the
# *statement* (not whether the module loaded) keeps the check independent of what other modules already put
# in ``sys.modules``.
_MODULE_SCOPE_PROBE = r"""
import builtins, json, sys
module_scope = []
real_import = builtins.__import__

def hook(name, globals=None, locals=None, fromlist=(), level=0):
    if globals is not None and globals.get("__name__") == "specify_cli.cli.commands.next_cmd":
        if sys._getframe(1).f_code.co_name == "<module>":
            module_scope.append(name)
    return real_import(name, globals, locals, fromlist, level)

builtins.__import__ = hook
import specify_cli.cli.commands.next_cmd  # noqa: F401
print(json.dumps({"loaded": "specify_cli.cli.commands.next_cmd" in sys.modules, "module_scope": module_scope}))
"""


def _is_forbidden(name: str) -> bool:
    return any(name == f or name.startswith(f + ".") or name.endswith("." + f) for f in FORBIDDEN_ON_HELP)


def _child_env() -> dict[str, str]:
    import os

    return {**os.environ, "PYTHONPATH": str(_SRC)}


def test_next_cmd_defers_next_runtime_stack() -> None:
    """``next_cmd.py``'s own module body must not import the ``next`` runtime stack (#5991)."""
    result = subprocess.run([sys.executable, "-c", _MODULE_SCOPE_PROBE], cwd=_REPO_ROOT, env=_child_env(), capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stderr[-2000:]
    report = json.loads(result.stdout.strip().splitlines()[-1])
    assert report["loaded"], "next_cmd was not imported: the control is vacuous"
    names: list[str] = report["module_scope"]
    assert "typer" in names, "probe saw no module-scope import in next_cmd: the control is vacuous"
    leaked = sorted({n for n in names if _is_forbidden(n)})
    assert not leaked, f"next_cmd imports at module scope: {leaked}"


@pytest.mark.xfail(reason="whole-app --help still eagerly imports the next runtime stack via other modules; tracked in #5999", strict=True)
def test_whole_app_help_does_not_import_next_runtime_stack() -> None:
    result = subprocess.run(
        [sys.executable, "-X", "importtime", "-m", "specify_cli", "--help"],
        cwd=_REPO_ROOT,
        env=_child_env(),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    imported = set(_imported_module_names(result.stderr))
    assert "specify_cli.cli.commands.next_cmd" in imported
    leaked = sorted(n for n in imported if any(n == f or n.startswith(f + ".") for f in FORBIDDEN_ON_HELP))
    assert not leaked, f"--help eagerly imports: {leaked}"
