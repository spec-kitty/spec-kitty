"""One owner for the decisions lock and its refusal (#6763, DIRECTIVE_044).

``src/specify_cli/decisions/lock.py`` owns the decisions sidecar lock: its file name, its
waits, the lock context managers and the one ``DECISION_LOCK_TIMEOUT`` refusal. Before
#6763 the doctor kept its own copy of the file name and the 10 s bound and took the raw
``machine_file_lock``, while ``next`` and ``repair-runtime-lock`` took it raw too, so a
busy lock escaped three commands as a traceback and the write path built the refusal
message twice.

This gate closes that defect class. Under ``src/``, a module that is not the owner may not:

* spell the sidecar file name ``index.json.lock`` as a string of its own;
* build a ``DecisionError`` with the ``LOCK_TIMEOUT`` code (every caller re-raises or
  renders the owner's refusal);
* import a ``kernel.locks`` primitive while also importing from ``specify_cli.decisions``
  (a decisions holder that locks by hand).

Each rule is non-vacuous twice: it must flag the owner itself (a concrete floor) and a
planted offender (a self-mutation probe).
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
OWNER_RELPATH = "src/specify_cli/decisions/lock.py"
LOCK_FILENAME = "index.json.lock"
_LOCK_PRIMITIVES = frozenset({"machine_file_lock", "LockAcquireTimeout", "SyncMachineFileLock"})


def _spells_lock_filename(tree: ast.AST) -> int | None:
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and node.value == LOCK_FILENAME:
            return node.lineno
    return None


def _is_lock_timeout_code(node: ast.expr) -> bool:
    return isinstance(node, ast.Attribute) and node.attr == "LOCK_TIMEOUT"


def _builds_lock_timeout_error(tree: ast.AST) -> int | None:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
        if name != "DecisionError":
            continue
        codes = [kw.value for kw in node.keywords if kw.arg == "code"] + list(node.args[:1])
        if any(_is_lock_timeout_code(code) for code in codes):
            return node.lineno
    return None


def _locks_by_hand(tree: ast.AST) -> int | None:
    imports_decisions = False
    primitive_line: int | None = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "specify_cli.decisions" or node.module.startswith("specify_cli.decisions."):
                imports_decisions = True
            if node.module == "kernel.locks" and any(alias.name in _LOCK_PRIMITIVES for alias in node.names):
                primitive_line = primitive_line or node.lineno
            if node.module == "kernel" and any(alias.name == "locks" for alias in node.names):
                primitive_line = primitive_line or node.lineno
        elif isinstance(node, ast.Import):
            if any(alias.name.startswith("specify_cli.decisions") for alias in node.names):
                imports_decisions = True
            if any(alias.name == "kernel.locks" for alias in node.names):
                primitive_line = primitive_line or node.lineno
    return primitive_line if imports_decisions else None


_RULES: dict[str, Callable[[ast.AST], int | None]] = {
    "spells the decisions lock file name": _spells_lock_filename,
    "builds a DECISION_LOCK_TIMEOUT refusal": _builds_lock_timeout_error,
    "takes a kernel.locks primitive beside a decisions import": _locks_by_hand,
}


#: A module can only break a rule if its text holds one of these, so only those are parsed.
_CANDIDATE_MARKERS = (LOCK_FILENAME, "LOCK_TIMEOUT", "kernel.locks", "import locks")


def _src_trees() -> dict[str, ast.AST]:
    trees: dict[str, ast.AST] = {}
    for path in sorted(SRC_ROOT.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if any(marker in text for marker in _CANDIDATE_MARKERS):
            trees[path.relative_to(REPO_ROOT).as_posix()] = ast.parse(text, filename=str(path))
    return trees


@pytest.fixture(scope="module")
def src_trees() -> dict[str, ast.AST]:
    return _src_trees()


@pytest.mark.parametrize("rule", sorted(_RULES))
def test_only_the_owner_breaks_the_rule(rule: str, src_trees: dict[str, ast.AST]) -> None:
    detector = _RULES[rule]
    offenders = {relpath: line for relpath, tree in src_trees.items() if (line := detector(tree)) is not None}

    # Concrete floor: the owner itself is what the rule describes, so a detector that
    # stopped matching anything would fail here instead of passing vacuously.
    assert OWNER_RELPATH in offenders, f"detector for {rule!r} no longer matches the owner"
    others = {relpath: line for relpath, line in offenders.items() if relpath != OWNER_RELPATH}
    found = ", ".join(f"{relpath}:{line}" for relpath, line in sorted(others.items()))
    assert not others, f"only {OWNER_RELPATH} may do this ({rule}); also found: {found}"


_PLANTED = {
    "spells the decisions lock file name": '_LOCK_FILENAME = "index.json.lock"\n',
    "builds a DECISION_LOCK_TIMEOUT refusal": (
        "from specify_cli.decisions.models import DecisionError, DecisionErrorCode\nraise DecisionError(code=DecisionErrorCode.LOCK_TIMEOUT, message='busy')\n"
    ),
    "takes a kernel.locks primitive beside a decisions import": (
        "from kernel.locks import machine_file_lock\nfrom specify_cli.decisions.service import _ledger_dir\n"
    ),
}


#: Other spellings of a hand-taken lock the third rule must also see.
_PLANTED_IMPORT_FORMS = (
    "import kernel.locks as kl\nfrom specify_cli.decisions import store\n",
    "from kernel import locks\nimport specify_cli.decisions.service\n",
)


@pytest.mark.parametrize("source", _PLANTED_IMPORT_FORMS)
def test_every_import_form_of_kernel_locks_is_seen(source: str) -> None:
    assert _locks_by_hand(ast.parse(source)) is not None


@pytest.mark.parametrize("rule", sorted(_RULES))
def test_each_detector_catches_a_planted_offender(rule: str) -> None:
    assert _RULES[rule](ast.parse(_PLANTED[rule])) is not None


def test_a_decisions_import_alone_is_not_an_offence() -> None:
    clean = "from specify_cli.decisions import lock as _lock\nfrom kernel.event_log_append import event_log_lock\n"
    assert all(detector(ast.parse(clean)) is None for detector in _RULES.values())
