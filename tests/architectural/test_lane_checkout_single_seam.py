"""Every lane ``git worktree add`` lives in the one lane-checkout helper.

Mission ``lane-worktree-model-hardening-01M6QY1M`` WP09 (FR-021, FR-022, C-013;
ADR 2026-04-03-1 Amendment 2026-11-06, ADR 2026-07-29-1 Amendment 2026-11-06).

The scan walks every ``src/`` module's AST and finds each ``git worktree add``
invocation in three shapes:

* an argv sequence: a list/tuple literal, or a call's own positional
  arguments, holding the consecutive tokens ``worktree`` then ``add`` (a name
  bound at module level to the string ``"worktree"`` counts, so a hoisted
  constant cannot hide one);
* a shell string: an f-string or string passed as the command to
  ``subprocess.run`` / ``check_output`` / ``check_call`` / ``call`` /
  ``Popen`` / ``os.system``.

Known limits: a ``worktree`` constant imported from another module, and a
shell string built by concatenation (``"git worktree add " + path``), are out
of reach; a module with neither a quoted ``worktree`` token nor ``worktree
add`` text is skipped unparsed.

An invocation is allowed only when it is:

1. inside ``specify_cli/lanes/lane_checkout.py`` (the seam);
2. detached (``--detach`` in the same argv or shell string): a detached
   worktree is a scratch checkout, never a lane checkout, which the helper
   requires to be attached;
3. inside one of the modules in :data:`_NON_LANE_WORKTREE_MODULES`, each of
   which creates (or prints) a checkout that is NOT a lane checkout, with its
   justification.

There is no allowlist for a lane checkout outside the seam: the former WP
code-change worktree creators (``core/worktree.py::create_wp_workspace`` /
``create_feature_worktree`` and ``core/vcs/git.py::GitVCS.create_workspace``)
had no production caller and were deleted (Mission WP09 review cycle 1). The
planted violations below (raw list, f-string, hoisted-constant helper alias)
prove the scan is non-vacuous, the scan floor proves it still reads the tree,
and every non-lane entry must still match a real invocation (no stale
entries).
"""

from __future__ import annotations

import ast
import re
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"
_SEAM = "specify_cli/lanes/lane_checkout.py"

#: Modules allowed to run ``git worktree add`` for a checkout that is NOT a
#: lane checkout. Each entry must still match at least one invocation.
_NON_LANE_WORKTREE_MODULES: dict[str, str] = {
    "specify_cli/coordination/workspace.py": (
        "CoordinationWorkspace.resolve materializes the coordination worktree (`.worktrees/<slug>-<mid8>-coord`), the status surface itself, never a lane"
    ),
    "specify_cli/cli/commands/_coordination_doctor.py": ("`recovery_args` names the coordination worktree re-materialization for doctor output"),
    "specify_cli/workspace/landed_worktrees.py": ("builds the printed recreate HINT for `doctor workspaces --prune`; spec-kitty never runs it"),
}

#: Measured 2026-11-06: 1421 ``src/**/*.py`` files. The floor keeps a broken
#: glob (or a moved tree) from passing on zero files.
_SCAN_FLOOR = 1200
_TIME_BUDGET_S = 5.0  # NFR-006: wall clock (measured 2026-11-06: about 1.2 s)

_WORKTREE_ADD_TEXT = re.compile(r"\bworktree\s+add\b")
_PREFILTER = re.compile(r"[\"']worktree[\"']|\bworktree\s+add\b")
_SHELL_CALLS = frozenset({"run", "check_output", "check_call", "call", "Popen", "system"})


@dataclass(frozen=True)
class Invocation:
    module: str
    lineno: int
    detached: bool

    def __str__(self) -> str:
        return f"{self.module}:{self.lineno}"


def _string_constants(tree: ast.Module) -> dict[str, str]:
    constants: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = node.value.value
    return constants


def _token(node: ast.expr, constants: dict[str, str]) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return constants.get(node.id)
    return None


def _argv_invocation(elements: list[ast.expr], constants: dict[str, str]) -> bool | None:
    """``None`` when ``elements`` hold no ``worktree add``; else whether it is detached."""
    tokens = [_token(element, constants) for element in elements]
    for first, second in zip(tokens, tokens[1:], strict=False):
        if first == "worktree" and second == "add":
            return "--detach" in tokens
    return None


def _shell_text(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(part.value for part in node.values if isinstance(part, ast.Constant) and isinstance(part.value, str))
    return None


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _shell_invocation(call: ast.Call) -> bool | None:
    if _call_name(call) not in _SHELL_CALLS or not call.args:
        return None
    text = _shell_text(call.args[0])
    if text is None or not _WORKTREE_ADD_TEXT.search(text):
        return None
    return "--detach" in text


def find_invocations(source: str, module: str) -> list[Invocation]:
    """Every ``git worktree add`` invocation in one module's source."""
    tree = ast.parse(source)
    constants = _string_constants(tree)
    found: list[Invocation] = []
    for node in ast.walk(tree):
        detached: bool | None = None
        if isinstance(node, (ast.List, ast.Tuple)):
            detached = _argv_invocation(list(node.elts), constants)
        elif isinstance(node, ast.Call):
            detached = _argv_invocation(list(node.args), constants)
            if detached is None:
                detached = _shell_invocation(node)
        if detached is not None:
            found.append(Invocation(module, getattr(node, "lineno", 0), detached))
    return found


def violations(invocations: list[Invocation]) -> list[Invocation]:
    return [
        invocation for invocation in invocations if invocation.module != _SEAM and not invocation.detached and invocation.module not in _NON_LANE_WORKTREE_MODULES
    ]


def _scan_src() -> tuple[int, list[Invocation]]:
    files = sorted(_SRC.rglob("*.py"))
    invocations: list[Invocation] = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        # Cheap prefilter (NFR-006): an invocation needs ``worktree`` as a quoted
        # token (an argv element or a hoisted constant) or as shell text.
        if not _PREFILTER.search(text):
            continue
        invocations.extend(find_invocations(text, path.relative_to(_SRC).as_posix()))
    return len(files), invocations


@pytest.fixture(scope="module")
def scan() -> tuple[int, list[Invocation], float]:
    # Wall clock, as NFR-006 states the budget ("completes in at most 5 s").
    started = time.perf_counter()
    count, invocations = _scan_src()
    return count, invocations, time.perf_counter() - started


def test_no_lane_worktree_add_outside_the_helper(scan: tuple[int, list[Invocation], float]) -> None:
    count, invocations, elapsed = scan
    assert count >= _SCAN_FLOOR, f"scanned {count} files, below the floor {_SCAN_FLOOR}: the scan no longer reads src/"
    assert elapsed <= _TIME_BUDGET_S, f"scan took {elapsed:.1f}s wall clock (budget {_TIME_BUDGET_S}s)"
    bad = violations(invocations)
    assert not bad, "lane `git worktree add` outside lanes/lane_checkout.py::open_lane_checkout (route it through the helper):\n" + "\n".join(
        str(item) for item in bad
    )


def test_the_seam_holds_the_lane_worktree_add(scan: tuple[int, list[Invocation], float]) -> None:
    _count, invocations, _elapsed = scan
    assert any(item.module == _SEAM and not item.detached for item in invocations)


def test_every_non_lane_entry_still_matches(scan: tuple[int, list[Invocation], float]) -> None:
    _count, invocations, _elapsed = scan
    matched = {item.module for item in invocations if not item.detached}
    stale = sorted(set(_NON_LANE_WORKTREE_MODULES) - matched)
    assert not stale, f"stale non-lane entries (remove them): {stale}"


_PLANTED_RAW_LIST = """
import subprocess
def make(repo, path, branch):
    subprocess.run(["git", "worktree", "add", str(path), branch], cwd=repo)
"""

_PLANTED_FSTRING = """
import subprocess
def make(path, branch):
    subprocess.run(f"git worktree add {path} {branch}", shell=True)
"""

_PLANTED_HELPER_ALIAS = """
WT = "worktree"
def _git(*args):
    pass
def make(path, branch):
    _git(WT, "add", str(path), branch)
"""

_PLANTED_DETACHED = """
import subprocess
def scratch(path, ref):
    subprocess.run(["git", "worktree", "add", "--detach", str(path), ref])
"""

_PLANTED_HINT_ONLY = """
def hint(branch):
    return [f"git worktree add <path> {branch}"]
"""


@pytest.mark.parametrize("source", [_PLANTED_RAW_LIST, _PLANTED_FSTRING, _PLANTED_HELPER_ALIAS], ids=["raw-list", "f-string", "helper-alias"])
def test_planted_lane_worktree_add_is_flagged(source: str, tmp_path: Path) -> None:
    planted = tmp_path / "planted.py"
    planted.write_text(source, encoding="utf-8")
    found = find_invocations(planted.read_text(encoding="utf-8"), "specify_cli/lanes/planted.py")
    assert len(violations(found)) == 1


def test_detached_scratch_and_hint_text_are_not_lane_checkouts() -> None:
    assert violations(find_invocations(_PLANTED_DETACHED, "specify_cli/x.py")) == []
    assert find_invocations(_PLANTED_HINT_ONLY, "specify_cli/x.py") == []


def test_non_lane_allowance_is_per_module_only() -> None:
    found = find_invocations(_PLANTED_RAW_LIST, "specify_cli/coordination/workspace.py")
    assert violations(found) == []
    assert violations(find_invocations(_PLANTED_RAW_LIST, "specify_cli/lanes/lifecycle_sync.py"))
