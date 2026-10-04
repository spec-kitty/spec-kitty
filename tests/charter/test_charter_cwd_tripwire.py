"""Self-mutation tests for the charter working-directory tripwire (#5317).

The tripwire (``tests/_support/charter_cwd_tripwire.py``) fails any test that
reaches a guarded charter write command while the **process working directory**
is inside the **repository root checkout** (or linked worktree) pytest was
started from, instead of in a **test tmp project**. These tests plant one
offender per shape in a synthetic test file and run it in its own pytest
session, so the planted failures cannot trip the outer test. ``pytester`` is
deliberately not enabled in this repository; the session is a plain subprocess,
following ``tests/_support/test_p0_repro.py``.
"""

from __future__ import annotations

import ast
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from types import ModuleType

import pytest

from tests._support.charter_cwd_tripwire import (
    AUTOUSE_FIXTURE_NAME,
    CHARTER_PACKAGE,
    GUARD_NAME,
    INVOKING_CHECKOUT,
    WATCHED_MODULES,
    _AfterExecLoader,
    _GuardWrapper,
    _is_inside_invoking_checkout,
    _make_wrapper,
    _Tripwire,
    _WrapAfterCharterImport,
    build_violation_message,
)

_REPO_ROOT = Path(__file__).resolve().parents[2]

pytestmark = [pytest.mark.non_sandbox]

#: Every planted test imports ``specify_cli`` lazily, inside its own body. The
#: session therefore starts with the charter command package NOT imported, and
#: ``test_late_import`` -- deliberately the first test of the file -- is the one
#: that imports it. Later tests find the package already imported. Both start
#: states are exercised by a single session.
_PLANTED = '''
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

PACKAGE = "specify_cli.cli.commands.charter"


def _stop_after_the_guard():
    """Make the command stop right after the guard, so nothing is ever written."""
    from specify_cli.task_utils import TaskCliError

    return TaskCliError("planted: stop after the guard")


def _invoke(*argv):
    from typer.testing import CliRunner

    from specify_cli.cli.commands.charter import app

    return CliRunner().invoke(app, list(argv))


# The package is NOT imported before this test: it imports it inside its body.
def test_late_import(tmp_path):
    from typer.testing import CliRunner

    from specify_cli.cli.commands.charter import app  # the first import of the package in this session

    with patch(f"{PACKAGE}.find_repo_root", side_effect=_stop_after_the_guard()):
        CliRunner().invoke(app, ["generate", "--no-from-interview"])


def test_synthesize_offender(tmp_path):
    with patch(f"{PACKAGE}.find_repo_root", side_effect=_stop_after_the_guard()):
        _invoke("synthesize")


def test_resynthesize_offender(tmp_path):
    with patch(f"{PACKAGE}.find_repo_root", side_effect=_stop_after_the_guard()):
        _invoke("resynthesize", "--list-topics")


def test_undo_offender(tmp_path, monkeypatch):
    monkeypatch.undo()  # a test body undoing every patch of the shared monkeypatch fixture
    with patch(f"{PACKAGE}.find_repo_root", side_effect=_stop_after_the_guard()):
        _invoke("generate", "--no-from-interview")


def test_reload_offender(tmp_path):
    import importlib

    # Re-executing a watched module re-binds the guard to the real function in the same module dict.
    importlib.reload(importlib.import_module(f"{PACKAGE}.generate"))
    with patch(f"{PACKAGE}.find_repo_root", side_effect=_stop_after_the_guard()):
        _invoke("generate", "--no-from-interview")


def test_activate_offender(tmp_path):
    # No --repo-root: the guard probes "." and the invalid cascade token fails right after it, so nothing is written.
    result = _invoke("activate", "directive", "DIRECTIVE_001", "--cascade", "not-a-kind")
    assert "Unknown artifact kind token" in result.output or "Refusing charter write" in result.output


def test_deactivate_offender(tmp_path):
    # deactivate resolves its root through the guard binding that activate.py owns.
    result = _invoke("deactivate", "directive", "DIRECTIVE_001", "--cascade", "not-a-kind")
    assert "Unknown artifact kind token" in result.output or "Refusing charter write" in result.output


def test_isolated_neighbour(tmp_path, charter_cwd_isolation):
    project = tmp_path / "project"
    project.mkdir()
    charter_cwd_isolation(project)
    with patch(f"{PACKAGE}.find_repo_root", side_effect=_stop_after_the_guard()):
        _invoke("generate", "--no-from-interview")


def test_loader_is_restored_after_the_imports(tmp_path):
    import sys

    from tests._support.charter_cwd_tripwire import _AfterExecLoader

    # The package was first imported by test_late_import, and one watched module was reloaded by test_reload_offender.
    for name in (PACKAGE, f"{PACKAGE}.generate", f"{PACKAGE}.synthesize", f"{PACKAGE}.resynthesize"):
        module = sys.modules[name]
        assert not isinstance(module.__spec__.loader, _AfterExecLoader), name
        assert not isinstance(module.__loader__, _AfterExecLoader), name


def test_no_guard(tmp_path):
    assert Path(tmp_path).is_dir()
'''

_OFFENDERS = (
    "test_late_import",
    "test_synthesize_offender",
    "test_resynthesize_offender",
    "test_undo_offender",
    "test_reload_offender",
    "test_activate_offender",
    "test_deactivate_offender",
)
_CLEAN = ("test_isolated_neighbour", "test_loader_is_restored_after_the_imports", "test_no_guard")


def _run_planted(tmp_path: Path) -> tuple[subprocess.CompletedProcess[str], Path]:
    """Run the planted file in its own pytest session started from the invoking checkout."""
    planted = tmp_path / "planted"
    planted.mkdir()
    test_file = planted / "test_planted.py"
    test_file.write_text(_PLANTED, encoding="utf-8")
    junit = tmp_path / "junit.xml"
    env = {key: value for key, value in os.environ.items() if key != "PYTEST_ADDOPTS"}
    # ``pythonpath = src`` from pytest.ini is not applied under ``-c os.devnull``.
    env["PYTHONPATH"] = os.pathsep.join([str(_REPO_ROOT), str(_REPO_ROOT / "src")])
    argv = [
        sys.executable,
        "-m",
        "pytest",
        "-c",
        os.devnull,
        "--rootdir",
        str(planted),
        "-p",
        "tests._support.charter_cwd_tripwire",
        "-p",
        "tests._support.charter_cwd",
        "-p",
        "no:cacheprovider",
        "-p",
        "no:randomly",
        "-q",
        f"--junitxml={junit}",
        str(test_file),
    ]
    proc = subprocess.run(argv, cwd=_REPO_ROOT, env=env, capture_output=True, text=True, timeout=300, check=False)
    return proc, junit


def _outcomes(junit: Path) -> dict[str, tuple[str, str]]:
    """Map each planted test name to ``(outcome, message text)`` from the junit report."""
    outcomes: dict[str, tuple[str, str]] = {}
    for case in ET.parse(junit).getroot().iter("testcase"):
        name = case.get("name") or ""
        outcome, text = "passed", ""
        for child in case:
            if child.tag in {"failure", "error", "skipped"}:
                outcome = child.tag
                text += (child.get("message") or "") + (child.text or "")
        outcomes[name] = (outcome, text)
    return outcomes


@pytest.fixture(scope="module")
def planted_session(tmp_path_factory: pytest.TempPathFactory) -> tuple[subprocess.CompletedProcess[str], dict[str, tuple[str, str]]]:
    proc, junit = _run_planted(tmp_path_factory.mktemp("planted_session"))
    assert junit.is_file(), proc.stdout + proc.stderr
    return proc, _outcomes(junit)


@pytest.mark.integration
@pytest.mark.parametrize("name", _OFFENDERS)
def test_planted_offender_is_caught(planted_session: tuple[subprocess.CompletedProcess[str], dict[str, tuple[str, str]]], name: str) -> None:
    proc, outcomes = planted_session
    outcome, text = outcomes[name]

    assert outcome in {"failure", "error"}, proc.stdout + proc.stderr
    # One message that names the test and the fix (NFR-004).
    assert f"test_planted.py::{name}" in text
    assert "charter_cwd_isolation" in text


@pytest.mark.integration
@pytest.mark.parametrize("name", _CLEAN)
def test_planted_clean_test_is_not_caught(planted_session: tuple[subprocess.CompletedProcess[str], dict[str, tuple[str, str]]], name: str) -> None:
    proc, outcomes = planted_session

    assert outcomes[name][0] == "passed", proc.stdout + proc.stderr


@pytest.mark.integration
def test_planted_session_has_exactly_the_planted_tests(
    planted_session: tuple[subprocess.CompletedProcess[str], dict[str, tuple[str, str]]],
) -> None:
    """Non-vacuity: a renamed or dropped planted test must not pass unnoticed."""
    _, outcomes = planted_session

    assert set(outcomes) == {*_OFFENDERS, *_CLEAN}


# ---------------------------------------------------------------------------
# The inside-the-invoking-checkout predicate and the failure message (pure)
# ---------------------------------------------------------------------------

_CHECKOUT = Path("/work/checkout")


@pytest.mark.fast
@pytest.mark.unit
@pytest.mark.parametrize(
    ("probed", "expected"),
    [
        (_CHECKOUT, True),
        (_CHECKOUT / "src" / "pkg", True),
        (_CHECKOUT / ".worktrees" / "lane-a", True),
        (Path("/work/checkout-sibling"), False),
        (Path("/work"), False),
        (Path("/elsewhere/project"), False),
    ],
    ids=["root", "below", "nested-worktree", "sibling-prefix", "parent", "unrelated"],
)
def test_predicate_flags_only_paths_inside_the_checkout(probed: Path, expected: bool) -> None:
    assert _is_inside_invoking_checkout(probed, checkout=_CHECKOUT) is expected


@pytest.mark.fast
@pytest.mark.unit
def test_predicate_excludes_a_pytest_temp_root_that_sits_inside_the_checkout() -> None:
    temp_root = _CHECKOUT / ".pytest-tmp"

    assert _is_inside_invoking_checkout(temp_root / "t0" / "project", temp_root, _CHECKOUT) is False
    # Only the temp root is carved out; the rest of the checkout is still the leak.
    assert _is_inside_invoking_checkout(_CHECKOUT / "src", temp_root, _CHECKOUT) is True
    # The carve-out is not a way around the check for the temp root itself being unset.
    assert _is_inside_invoking_checkout(temp_root / "t0" / "project", None, _CHECKOUT) is True


@pytest.mark.fast
@pytest.mark.unit
def test_predicate_ignores_a_temp_root_that_contains_the_checkout() -> None:
    """A temp root above the checkout must not make the checkout itself exempt."""
    temp_root = _CHECKOUT.parent

    assert _is_inside_invoking_checkout(_CHECKOUT / "src", temp_root, _CHECKOUT) is True


@pytest.mark.fast
@pytest.mark.unit
def test_predicate_resolves_symlinks(tmp_path: Path) -> None:
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(checkout, target_is_directory=True)

    assert _is_inside_invoking_checkout(alias, checkout=checkout.resolve()) is True


@pytest.mark.fast
@pytest.mark.unit
def test_message_deduplicates_and_sorts_the_probed_paths() -> None:
    message = build_violation_message("tests/x/test_y.py::test_z", [Path("/b"), Path("/a"), Path("/b")])

    assert "/a, /b" in message


@pytest.mark.fast
@pytest.mark.unit
def test_wrapper_propagates_the_real_guards_exception_unchanged() -> None:
    refusal = RuntimeError("refused by the real guard")
    violations: list[Path] = []

    def real(start: Path) -> Path:
        raise refusal

    wrapper = _make_wrapper(real, violations, None)

    with pytest.raises(RuntimeError) as raised:
        wrapper(INVOKING_CHECKOUT)

    assert raised.value is refusal
    assert violations == [INVOKING_CHECKOUT]


# ---------------------------------------------------------------------------
# The tripwire's own wrap bookkeeping (pure, on a synthetic watched module)
# ---------------------------------------------------------------------------


def _synthetic_watched_module(monkeypatch: pytest.MonkeyPatch, real: object) -> ModuleType:
    """A stand-in for a watched charter command module, registered under its real name."""
    module = ModuleType(WATCHED_MODULES[0])
    setattr(module, GUARD_NAME, real)
    monkeypatch.setitem(sys.modules, WATCHED_MODULES[0], module)
    return module


@pytest.mark.fast
@pytest.mark.unit
def test_release_takes_off_a_wrap_that_is_still_the_tripwires_own(monkeypatch: pytest.MonkeyPatch) -> None:
    def real(start: Path) -> Path:
        return start

    module = _synthetic_watched_module(monkeypatch, real)
    tripwire = _Tripwire(None)

    tripwire.watch()
    assert isinstance(getattr(module, GUARD_NAME), _GuardWrapper)
    tripwire.release()

    assert getattr(module, GUARD_NAME) is real


@pytest.mark.fast
@pytest.mark.unit
def test_release_leaves_a_value_that_replaced_the_wrap_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    def real(start: Path) -> Path:
        return start

    def replacement(start: Path) -> Path:
        return start

    module = _synthetic_watched_module(monkeypatch, real)
    tripwire = _Tripwire(None)
    tripwire.watch()
    setattr(module, GUARD_NAME, replacement)  # a reload, or a test's own stub, replaced the wrap

    tripwire.release()

    assert getattr(module, GUARD_NAME) is replacement


@pytest.mark.fast
@pytest.mark.unit
def test_a_second_tripwire_unwraps_a_wrapper_left_behind_instead_of_stacking(monkeypatch: pytest.MonkeyPatch) -> None:
    def real(start: Path) -> Path:
        return start

    module = _synthetic_watched_module(monkeypatch, real)
    _Tripwire(None).watch()  # never released: stands for a wrapper an earlier test left behind
    second = _Tripwire(None)

    second.watch()

    wrapper = getattr(module, GUARD_NAME)
    assert isinstance(wrapper, _GuardWrapper)
    assert wrapper.real is real
    assert wrapper.violations is second.violations
    second.release()
    assert getattr(module, GUARD_NAME) is real


# ---------------------------------------------------------------------------
# The import finder, in-process, against a controlled finder chain
# ---------------------------------------------------------------------------


class _LegacyFinder:
    """A ``sys.meta_path`` entry with no ``find_spec`` at all; the import system skips such entries."""


@pytest.mark.fast
@pytest.mark.unit
def test_finder_skips_a_meta_path_entry_that_has_no_find_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib

    parent_path = list(importlib.import_module(CHARTER_PACKAGE.rpartition(".")[0]).__path__)
    finder = _WrapAfterCharterImport(lambda: None)
    real_finders = [entry for entry in sys.meta_path if not isinstance(entry, _WrapAfterCharterImport)]
    monkeypatch.setattr(sys, "meta_path", [_LegacyFinder(), finder, *real_finders])

    spec = finder.find_spec(CHARTER_PACKAGE, parent_path)

    assert spec is not None
    assert isinstance(spec.loader, _AfterExecLoader)


# ---------------------------------------------------------------------------
# Coverage: every module that calls the guard is watched
# ---------------------------------------------------------------------------

_SRC_DIR = _REPO_ROOT / "src"


def _guard_usage(source: str) -> tuple[bool, list[int]]:
    """Whether ``source`` calls the guard, and the lines that import it under another name.

    A call is ``resolve_charter_write_root(...)`` or ``module.resolve_charter_write_root(...)``.
    An aliased import (``from x import resolve_charter_write_root as guard``) is invisible to this scan
    and to the plugin's ``getattr(module, GUARD_NAME)``, so it is reported instead of trusted.
    """
    calls = False
    aliased: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            callee = node.func
            called = callee.id if isinstance(callee, ast.Name) else callee.attr if isinstance(callee, ast.Attribute) else ""
            calls = calls or called == GUARD_NAME
        elif isinstance(node, ast.ImportFrom):
            aliased.extend(node.lineno for alias in node.names if alias.name == GUARD_NAME and alias.asname not in (None, GUARD_NAME))
    return calls, aliased


def _scan_src_for_the_guard() -> tuple[set[str], list[str]]:
    """Dotted names of every module under ``src/`` that calls the guard, and every aliased import of it."""
    calling: set[str] = set()
    aliased: list[str] = []
    for path in sorted(_SRC_DIR.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if GUARD_NAME not in text:
            continue
        module = ".".join(part for part in path.relative_to(_SRC_DIR).with_suffix("").parts if part != "__init__")
        calls, lines = _guard_usage(text)
        if calls:
            calling.add(module)
        aliased.extend(f"{module}:{line}" for line in lines)
    return calling, aliased


@pytest.mark.fast
@pytest.mark.unit
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (f"def run():\n    {GUARD_NAME}(Path.cwd())\n", (True, [])),
        (f"from ._charter_write_root import {GUARD_NAME} as guard\n\ndef run():\n    guard(Path.cwd())\n", (False, [1])),
        (f"from ._charter_write_root import {GUARD_NAME}\n", (False, [])),  # an import alone is not a call
    ],
    ids=["call", "aliased-import", "plain-import"],
)
def test_collector_sees_a_call_and_flags_an_aliased_import(source: str, expected: tuple[bool, list[int]]) -> None:
    assert _guard_usage(source) == expected


@pytest.mark.fast
@pytest.mark.unit
def test_every_module_that_calls_the_guard_is_watched() -> None:
    calling, aliased = _scan_src_for_the_guard()

    assert aliased == [], f"bind the guard under its own name: {aliased}"
    # A concrete floor: a pattern that silently matches nothing must not pass.
    assert {f"{CHARTER_PACKAGE}.{name}" for name in ("generate", "synthesize", "resynthesize", "activate")} <= calling
    assert calling == set(WATCHED_MODULES)


@pytest.mark.fast
@pytest.mark.unit
def test_watched_modules_carry_the_wrapper_inside_a_test(tmp_path: Path) -> None:
    """Imported inside the test body, so this also exercises the late-import path in-process."""
    import importlib

    from specify_cli.cli.commands.charter import _charter_write_root

    real = _charter_write_root.resolve_charter_write_root
    for name in WATCHED_MODULES:
        wrapped = getattr(importlib.import_module(name), GUARD_NAME)
        assert wrapped is not real, f"{name} is not watched"
        # Calls through: a path outside the invoking checkout resolves exactly as the real guard does.
        assert wrapped(tmp_path) == real(tmp_path)


# ---------------------------------------------------------------------------
# No test file may override the tripwire's autouse fixture
# ---------------------------------------------------------------------------

_TESTS_DIR = INVOKING_CHECKOUT / "tests"
_PLUGIN_FILE = _TESTS_DIR / "_support" / "charter_cwd_tripwire.py"


def _defines_name(source: str, name: str) -> list[int]:
    """Line numbers where ``source`` defines ``name`` as a function, a fixture ``name=`` alias or a module-level binding."""
    lines: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            aliased = any(
                isinstance(decorator, ast.Call)
                and any(kw.arg == "name" and isinstance(kw.value, ast.Constant) and kw.value.value == name for kw in decorator.keywords)
                for decorator in node.decorator_list
            )
            if node.name == name or aliased:
                lines.append(node.lineno)
        elif isinstance(node, ast.Assign | ast.AnnAssign):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == name for target in targets):
                lines.append(node.lineno)
    return sorted(lines)


def _files_overriding_the_tripwire_fixture() -> list[str]:
    """Every test-tree file but the plugin that defines the plugin's autouse fixture name."""
    offenders: list[str] = []
    for path in sorted(_TESTS_DIR.rglob("*.py")):
        if path == _PLUGIN_FILE:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if AUTOUSE_FIXTURE_NAME in text and _defines_name(text, AUTOUSE_FIXTURE_NAME):
            offenders.append(str(path.relative_to(INVOKING_CHECKOUT)))
    return offenders


@pytest.mark.fast
@pytest.mark.unit
def test_the_plugin_itself_defines_the_autouse_fixture_name() -> None:
    """Non-vacuity: the name the scan guards is really the plugin's fixture."""
    assert _defines_name(_PLUGIN_FILE.read_text(encoding="utf-8"), AUTOUSE_FIXTURE_NAME)


@pytest.mark.fast
@pytest.mark.unit
def test_no_other_test_file_overrides_the_tripwire_fixture() -> None:
    """A same-named fixture anywhere else overrides the autouse one and silently disables the tripwire."""
    assert _files_overriding_the_tripwire_fixture() == []
