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


def _run_generate_through_helper(arguments):
    return _invoke(*arguments)


# The package is NOT imported before this test: it imports it inside its body.
def test_late_import(tmp_path):
    from typer.testing import CliRunner

    from specify_cli.cli.commands.charter import app  # the first import of the package in this session

    with patch(f"{PACKAGE}.find_repo_root", side_effect=_stop_after_the_guard()):
        CliRunner().invoke(app, ["generate", "--no-from-interview"])


def test_direct(tmp_path):
    project = tmp_path / "project"
    with patch(f"{PACKAGE}.find_repo_root") as lookup:
        lookup.return_value = project
        lookup.side_effect = _stop_after_the_guard()
        _invoke("generate", "--no-from-interview")


def test_via_helper(tmp_path):
    arguments = ["generate", "--no-from-interview"]
    with patch(f"{PACKAGE}.find_repo_root", side_effect=_stop_after_the_guard()):
        _run_generate_through_helper(arguments)


def test_setattr_spelling(tmp_path, monkeypatch):
    error = _stop_after_the_guard()

    def lookup(*args, **kwargs):
        raise error

    monkeypatch.setattr(f"{PACKAGE}.find_repo_root", lookup)
    _invoke("generate", "--no-from-interview")


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
    "test_direct",
    "test_via_helper",
    "test_setattr_spelling",
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
def test_invoking_checkout_is_the_checkout_that_contains_this_tests_tree() -> None:
    assert _REPO_ROOT.resolve() == INVOKING_CHECKOUT
    assert (INVOKING_CHECKOUT / "tests" / "_support" / "charter_cwd_tripwire.py").is_file()


@pytest.mark.fast
@pytest.mark.unit
def test_message_names_the_test_the_path_and_the_fixture() -> None:
    message = build_violation_message("tests/x/test_y.py::test_z", [Path("/a"), Path("/a"), Path("/b")])

    assert "tests/x/test_y.py::test_z" in message
    assert "/a, /b" in message  # de-duplicated, sorted
    assert "`charter_cwd_isolation`" in message
    assert "process working directory" in message
    assert "invoking checkout" in message


@pytest.mark.fast
@pytest.mark.unit
def test_wrapper_records_a_probe_inside_the_checkout_and_returns_the_real_result() -> None:
    violations: list[Path] = []
    sentinel = Path("/real/result")
    wrapper = _make_wrapper(lambda start: sentinel, violations, None)

    assert wrapper(INVOKING_CHECKOUT) == sentinel
    assert violations == [INVOKING_CHECKOUT]


@pytest.mark.fast
@pytest.mark.unit
def test_wrapper_does_not_record_a_probe_outside_the_checkout(tmp_path: Path) -> None:
    violations: list[Path] = []
    wrapper = _make_wrapper(lambda start: start, violations, None)

    assert wrapper(tmp_path) == tmp_path
    assert violations == []


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


@pytest.mark.fast
@pytest.mark.unit
def test_after_exec_loader_hands_the_real_loader_back_once_the_module_has_executed(tmp_path: Path) -> None:
    import importlib.util

    source = tmp_path / "synthetic_charter_module.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    spec = importlib.util.spec_from_file_location("synthetic_charter_module", source)
    assert spec is not None
    assert spec.loader is not None
    real_loader = spec.loader
    calls: list[str] = []
    spec.loader = _AfterExecLoader(real_loader, lambda: calls.append("after"))
    module = importlib.util.module_from_spec(spec)
    assert module.__loader__ is spec.loader  # the import machinery points the module at the proxy

    spec.loader.exec_module(module)

    assert calls == ["after"]
    assert module.VALUE == 1
    assert spec.loader is real_loader
    assert module.__loader__ is real_loader
    assert module.__spec__ is spec


# ---------------------------------------------------------------------------
# Coverage: every guard call that probes the process working directory is watched
# ---------------------------------------------------------------------------

_CHARTER_SOURCE_DIR = _REPO_ROOT / "src" / "specify_cli" / "cli" / "commands" / "charter"


def _calls_the_guard(source: str) -> bool:
    """Whether ``source`` calls the guard at all, under its own name or as ``module.<name>``."""
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        callee = node.func
        called = callee.id if isinstance(callee, ast.Name) else callee.attr if isinstance(callee, ast.Attribute) else ""
        if called == GUARD_NAME:
            return True
    return False


def _modules_calling_the_guard() -> set[str]:
    """Dotted names of every module in the charter commands package, at any depth, that calls the guard."""
    modules: set[str] = set()
    for path in sorted(_CHARTER_SOURCE_DIR.rglob("*.py")):
        if _calls_the_guard(path.read_text(encoding="utf-8")):
            parts = path.relative_to(_CHARTER_SOURCE_DIR).with_suffix("").parts
            modules.add(".".join([CHARTER_PACKAGE, *(part for part in parts if part != "__init__")]))
    return modules


@pytest.mark.fast
@pytest.mark.unit
@pytest.mark.parametrize(
    "source",
    [
        f"from pathlib import Path\n\ndef run():\n    {GUARD_NAME}(Path.cwd())\n",
        f"import pathlib\n\ndef run():\n    mod.{GUARD_NAME}(Path.cwd())\n",
        f"def run(root):\n    {GUARD_NAME}(root)\n",  # a root passed in, as activate.py does
        f"def run():\n    {GUARD_NAME}(Path.cwd().parent)\n",
        f"def run():\n    {GUARD_NAME}()\n",
    ],
    ids=["cwd", "qualified", "passed-in-root", "derived-from-cwd", "no-argument"],
)
def test_collector_finds_any_call_of_the_guard(source: str) -> None:
    assert _calls_the_guard(source) is True


@pytest.mark.fast
@pytest.mark.unit
@pytest.mark.parametrize(
    "source",
    [
        "def run():\n    other(Path.cwd())\n",
        f"from ._charter_write_root import {GUARD_NAME}\n",  # an import is not a call
        f'def run():\n    """Calls {GUARD_NAME}(root) in prose."""\n',
        f"def run():\n    alias = {GUARD_NAME}\n    return alias\n",  # a reference without a call
    ],
    ids=["other-callee", "import-only", "docstring-mention", "reference"],
)
def test_collector_ignores_sources_that_do_not_call_the_guard(source: str) -> None:
    assert _calls_the_guard(source) is False


@pytest.mark.fast
@pytest.mark.unit
def test_every_module_that_calls_the_guard_is_watched() -> None:
    calling = _modules_calling_the_guard()

    # A concrete floor: a pattern that silently matches nothing must not pass.
    assert {f"{CHARTER_PACKAGE}.{name}" for name in ("generate", "synthesize", "resynthesize", "activate")} <= calling
    assert len(calling) >= 4
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
# No exemption of any kind (FR-006)
# ---------------------------------------------------------------------------

#: Names through which a plugin could be told to stand down for a test or a run.
_OPT_OUT_NAMES = frozenset(
    {
        "environ",
        "getenv",
        "iter_markers",
        "get_closest_marker",
        "own_markers",
        "addinivalue_line",
        "addoption",
        "addini",
        "getoption",
        "getini",
        "pytest_addoption",
        "pytest_configure",
    }
)


def _opt_out_mechanisms(source: str) -> list[str]:
    """Names in ``source`` that would let a test or an environment switch the tripwire off."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Attribute) and node.attr in _OPT_OUT_NAMES:
            found.add(node.attr)
        elif isinstance(node, ast.Name) and node.id in _OPT_OUT_NAMES:
            found.add(node.id)
        elif isinstance(node, ast.FunctionDef) and node.name in _OPT_OUT_NAMES:
            found.add(node.name)
    return sorted(found)


@pytest.mark.fast
@pytest.mark.unit
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("import os\nx = os.environ.get('NO_TRIPWIRE')\n", ["environ"]),
        ("import os\nx = os.getenv('NO_TRIPWIRE')\n", ["getenv"]),
        ("def f(request):\n    return request.node.get_closest_marker('no_tripwire')\n", ["get_closest_marker"]),
        ("def f(item):\n    return list(item.iter_markers())\n", ["iter_markers"]),
        ("def pytest_addoption(parser):\n    parser.addoption('--no-tripwire')\n", ["addoption", "pytest_addoption"]),
        ("from os import environ\n", []),  # an import alone names no use; the use above is what is caught
        ("def f():\n    return 1\n", []),
    ],
    ids=["environ", "getenv", "closest-marker", "iter-markers", "addoption", "import-only", "clean"],
)
def test_opt_out_detector_fires_on_a_synthetic_exemption(source: str, expected: list[str]) -> None:
    assert _opt_out_mechanisms(source) == expected


@pytest.mark.fast
@pytest.mark.unit
def test_the_tripwire_module_offers_no_way_to_switch_it_off() -> None:
    source = (INVOKING_CHECKOUT / "tests" / "_support" / "charter_cwd_tripwire.py").read_text(encoding="utf-8")

    assert _opt_out_mechanisms(source) == []


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
@pytest.mark.parametrize(
    "source",
    [
        f"import pytest\n\n@pytest.fixture(autouse=True)\ndef {AUTOUSE_FIXTURE_NAME}():\n    yield\n",
        f"import pytest\n\n@pytest.fixture\nasync def {AUTOUSE_FIXTURE_NAME}():\n    yield\n",
        f"import pytest\n\n@pytest.fixture(name='{AUTOUSE_FIXTURE_NAME}')\ndef quiet():\n    yield\n",
        f"{AUTOUSE_FIXTURE_NAME} = make_fixture()\n",
        f"{AUTOUSE_FIXTURE_NAME}: object = make_fixture()\n",
    ],
    ids=["function", "async-function", "name-alias", "assignment", "annotated-assignment"],
)
def test_override_detector_finds_a_synthetic_override(source: str) -> None:
    assert _defines_name(source, AUTOUSE_FIXTURE_NAME)


@pytest.mark.fast
@pytest.mark.unit
@pytest.mark.parametrize(
    "source",
    [
        f"def test_it(request):\n    assert '{AUTOUSE_FIXTURE_NAME}' in request.fixturenames\n",  # a mention, not a definition
        f"import pytest\n\n@pytest.fixture(name='other')\ndef {AUTOUSE_FIXTURE_NAME}_other():\n    yield\n",
        "def test_it():\n    return 1\n",
    ],
    ids=["mention", "similar-name", "unrelated"],
)
def test_override_detector_ignores_a_mention_or_a_different_name(source: str) -> None:
    assert _defines_name(source, AUTOUSE_FIXTURE_NAME) == []


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
