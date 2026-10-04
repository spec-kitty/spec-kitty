"""Recurrence tripwire for charter working-directory leaks (#5317).

The charter commands ``generate``, ``synthesize`` and ``resynthesize`` call
``resolve_charter_write_root(Path.cwd())``; ``activate`` and ``deactivate`` call
it through ``resolve_write_root_or_exit`` with their ``--repo-root`` option,
which defaults to ``.``, the process working directory. That guard probes the
given path and refuses when it is a linked worktree. A test that aims a command
at a **test tmp project** by patching ``specify_cli.cli.commands.charter.find_repo_root``
but never changes the process working directory is silently depending on where
pytest was started: green from a repository root checkout, red from a linked
worktree.

This autouse plugin makes that dependency visible from every checkout. It
wraps the guard at each watched charter command module, records every call
whose probed path is inside the **invoking checkout** (the checkout that
contains this ``tests/`` tree), always calls through to the real guard, and
fails the offending test at fixture teardown with one message that names the
test and ``charter_cwd_isolation``. A test passes by requesting that fixture,
which moves the process working directory to a test tmp project, or by passing
its test tmp project as ``--repo-root``.

Relation to ``_neutralize_worktree_detection`` in ``tests/conftest.py``: that
autouse fixture makes a test location-independent by stubbing
``detect_execution_context``. This tripwire is the pattern that keeps the real
guard: nothing here ever stubs ``resolve_charter_write_root``, a leaking test is
failed and fixed with ``charter_cwd_isolation`` instead.

Blind spots, stated so nobody mistakes silence for proof: the tripwire is a
function-scoped fixture, so it does not see a guard call made from a module- or
session-scoped fixture (those run before it is installed, or outside any test),
and it does not see a command started as a separate process (``subprocess``, a
``spec-kitty`` child), because the wrapper lives only in this process.

There is no way to switch it off: no marker, no environment variable, no
allowlist (FR-006). A test that legitimately runs a guarded command from a real
linked worktree builds that worktree under its tmp path, outside the invoking
checkout, so it never trips.

Why the wrapper always calls through, and why failure is at teardown
---------------------------------------------------------------------
The real guard must keep running (C-002): the wrapper returns, or raises,
exactly what the real guard does. Raising from inside the wrapper would be
swallowed by ``CliRunner`` into ``result.exception`` and surface as a confusing
exit-code assertion, so the violation is recorded and raised at teardown.

How modules imported *later* in a test are still watched
--------------------------------------------------------
``pytest_plugins`` modules are imported while ``tests/conftest.py`` loads,
before ``pytest_configure`` sets the isolated per-worker HOME. Importing
``specify_cli`` here would bind modules such as
``specify_cli.core.tool_checker`` to the developer's real home, and would add
the cost of the charter command package (about 0.4 s and 700 modules) to every
session, including sessions that never touch the charter commands. So this
module imports nothing from ``specify_cli`` and wraps only what is already in
``sys.modules``. Options evaluated for a package imported during a test:

* Wrap at the source, ``_charter_write_root.resolve_charter_write_root``:
  rejected. Importing that submodule runs the charter package ``__init__``,
  which imports all the command modules first, so the source cannot be
  patched before they bind it by name.
* Look at ``sys.modules`` again at teardown: rejected. The guard call has
  already happened unwatched by then.
* A ``sys.meta_path`` finder, chosen. For the duration of each test a finder
  sits first on ``sys.meta_path``. It acts only on the charter command package
  name and each watched module name, and delegates everything else to the
  finders behind it. It hands back the real spec with a loader that runs the real
  loader and then wraps the watched modules that are imported by then. The finder
  also catches a package re-imported after the test removed it from
  ``sys.modules``, and a watched module re-executed by ``importlib.reload``, which
  finds its spec through ``sys.meta_path`` and re-binds the guard to the real
  function. Once a module has executed, the proxy loader is replaced on its
  ``__spec__`` and ``__loader__`` by the real one, so it does not outlive the
  import. The finder is removed at teardown, and the wrapping is undone through a
  private ``pytest.MonkeyPatch`` owned by the tripwire, never the test's own
  ``monkeypatch`` fixture, so nothing outlives the test and a test body that calls
  ``monkeypatch.undo()`` cannot take the tripwire off.

The per-test cost is an ``insert`` and a ``remove`` on ``sys.meta_path`` plus
one ``setattr`` per watched module when the package is already imported; it is measured in
the work package record.
"""

from __future__ import annotations

import importlib.abc
import sys
from collections.abc import Callable, Iterator, Sequence
from importlib.machinery import ModuleSpec
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

#: The checkout that contains this ``tests/`` tree: the repository root checkout, or the linked worktree pytest runs from.
INVOKING_CHECKOUT = Path(__file__).resolve().parents[2]

CHARTER_PACKAGE = "specify_cli.cli.commands.charter"

#: Name each watched module binds the guard under (``from ._charter_write_root import ...``).
GUARD_NAME = "resolve_charter_write_root"

#: Charter command modules that bind the guard: ``generate``, ``synthesize`` and ``resynthesize`` call it with the process
#: working directory; ``activate`` calls it for ``activate`` and ``deactivate`` with a root that is cwd-derived unless
#: the test passes ``--repo-root``. The violation test is on the probed path, so every caller is watched alike.
WATCHED_MODULES = (
    f"{CHARTER_PACKAGE}.generate",
    f"{CHARTER_PACKAGE}.synthesize",
    f"{CHARTER_PACKAGE}.resynthesize",
    f"{CHARTER_PACKAGE}.activate",
)

FIXTURE_NAME = "charter_cwd_isolation"

#: Name of this plugin's autouse fixture. A fixture of the same name defined anywhere else in the test tree overrides it
#: and switches the tripwire off for that scope; the tripwire test file scans for that.
AUTOUSE_FIXTURE_NAME = "_charter_cwd_tripwire"


def _contains(root: Path, candidate: Path) -> bool:
    """Whether ``candidate`` is ``root`` or below it. Both must be resolved."""
    return candidate == root or root in candidate.parents


def _is_inside_invoking_checkout(path: Path, basetemp: Path | None = None, checkout: Path = INVOKING_CHECKOUT) -> bool:
    """Whether the guard was probed at a path inside the invoking checkout.

    ``basetemp`` (pytest's session temp root) is carved out so a temp root
    configured inside the checkout does not make every test tmp project look
    like a leak. The carve-out applies only when the temp root is strictly
    inside the checkout: a temp root that contains the checkout must not make
    the checkout itself exempt.
    """
    resolved = path.resolve()
    if basetemp is not None:
        temp_root = basetemp.resolve()
        if _contains(temp_root, resolved) and not _contains(temp_root, checkout):
            return False
    return _contains(checkout, resolved)


def build_violation_message(nodeid: str, probed: Sequence[Path]) -> str:
    """The one failure message: names the test, the probed path and the fixture to request."""
    where = ", ".join(sorted({str(path) for path in probed}))
    return (
        f"{nodeid} reached the charter write guard with the process working directory inside "
        f"the invoking checkout ({where}). The test passes from a repository root checkout and "
        f"fails from a linked worktree. Request the `{FIXTURE_NAME}` fixture and call it with the "
        f"test tmp project before invoking a charter write command."
    )


class _GuardWrapper:
    """The tripwire's wrapper of the guard: records a probe inside the invoking checkout, then calls through."""

    def __init__(self, real: Callable[[Path], Path], violations: list[Path], basetemp: Path | None) -> None:
        self.real = real
        self.violations = violations
        self.basetemp = basetemp

    def __call__(self, start: Path) -> Path:
        probed = Path(start).resolve()
        if _is_inside_invoking_checkout(probed, self.basetemp):
            self.violations.append(probed)
        return self.real(start)


def _make_wrapper(real: Callable[[Path], Path], violations: list[Path], basetemp: Path | None) -> _GuardWrapper:
    """Wrap the guard: record a probe inside the invoking checkout, then always call through."""
    return _GuardWrapper(real, violations, basetemp)


class _Tripwire:
    """The wrapping state of one test: what it wrapped, and how to take it off again.

    Each wrap owns a private ``pytest.MonkeyPatch``, never the test's own
    ``monkeypatch`` fixture, so a test body that calls ``monkeypatch.undo()``
    cannot take the tripwire off. A wrap is taken off only while the module
    attribute is still this tripwire's wrapper; if something else has replaced
    it since (a reload, a test's own stub), that newer value is left alone.
    """

    def __init__(self, basetemp: Path | None) -> None:
        self.violations: list[Path] = []
        self._basetemp = basetemp
        self._installed: list[tuple[ModuleType, _GuardWrapper, pytest.MonkeyPatch]] = []

    def watch(self) -> None:
        """Wrap the guard on every watched module that is imported right now."""
        for name in WATCHED_MODULES:
            module = sys.modules.get(name)
            if module is not None:
                self._wrap(module)

    def _wrap(self, module: ModuleType) -> None:
        current = getattr(module, GUARD_NAME, None)
        if current is None:
            return
        if isinstance(current, _GuardWrapper):
            if current.violations is self.violations:
                return
            # A wrapper left by an earlier test: unwrap it, never stack on it.
            current = current.real
            setattr(module, GUARD_NAME, current)
        wrapper = _make_wrapper(current, self.violations, self._basetemp)
        patch = pytest.MonkeyPatch()
        patch.setattr(module, GUARD_NAME, wrapper)
        self._installed.append((module, wrapper, patch))

    def release(self) -> None:
        """Take off every wrap that is still this tripwire's own."""
        for module, wrapper, patch in reversed(self._installed):
            if getattr(module, GUARD_NAME, None) is wrapper:
                patch.undo()
        self._installed.clear()


class _AfterExecLoader(importlib.abc.Loader):
    """Run the real loader, then ``after``. Everything else is the real loader's."""

    def __init__(self, inner: importlib.abc.Loader, after: Callable[[], None]) -> None:
        self._inner = inner
        self._after = after

    def create_module(self, spec: ModuleSpec) -> ModuleType | None:
        return self._inner.create_module(spec)

    def exec_module(self, module: ModuleType) -> None:
        try:
            self._inner.exec_module(module)
        finally:
            self._hand_back_real_loader(module)
        self._after()

    def _hand_back_real_loader(self, module: ModuleType) -> None:
        """Point the module and its spec at the real loader again, so this proxy does not outlive the import."""
        spec = getattr(module, "__spec__", None)
        if spec is not None and spec.loader is self:
            spec.loader = self._inner
        if getattr(module, "__loader__", None) is self:
            module.__loader__ = self._inner

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)


#: Names whose (re-)execution re-binds the guard: the package, whose ``__init__`` imports the command modules, and each
#: watched module itself, which ``importlib.reload`` re-executes in place after finding its spec through ``sys.meta_path``.
_REBINDING_NAMES = frozenset({CHARTER_PACKAGE, *WATCHED_MODULES})


class _WrapAfterCharterImport(importlib.abc.MetaPathFinder):
    """Wrap the watched modules as soon as the charter command package, or one of them, finishes (re-)executing."""

    def __init__(self, after: Callable[[], None]) -> None:
        self._after = after

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: ModuleType | None = None,
    ) -> ModuleSpec | None:
        if fullname not in _REBINDING_NAMES:
            return None
        for finder in sys.meta_path:
            if finder is self:
                continue
            # Like the import system, tolerate an entry that has no ``find_spec``.
            find_spec = getattr(finder, "find_spec", None)
            if find_spec is None:
                continue
            spec: ModuleSpec | None = find_spec(fullname, path, target)
            if spec is not None and spec.loader is not None:
                spec.loader = _AfterExecLoader(spec.loader, self._after)
                return spec
        return None


@pytest.fixture(autouse=True)
def _charter_cwd_tripwire(
    request: pytest.FixtureRequest,
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[None]:
    tripwire = _Tripwire(tmp_path_factory.getbasetemp())
    tripwire.watch()
    finder = _WrapAfterCharterImport(tripwire.watch)
    sys.meta_path.insert(0, finder)
    try:
        yield
    finally:
        if finder in sys.meta_path:
            sys.meta_path.remove(finder)
        tripwire.release()
    if tripwire.violations:
        pytest.fail(build_violation_message(request.node.nodeid, tripwire.violations), pytrace=False)
