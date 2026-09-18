"""Unit tests for the canonical OS-detection seam: ``kernel.paths.is_windows``.

FR-004/FR-005, C-003 (cross-os-primitive-unification-01M2T1CM WP01). The seam
promotes the former private ``kernel.paths._is_windows`` to a public,
patchable ``is_windows() -> bool``. These tests prove:

1. The seam's real (unpatched) body still reads ``os.name`` faithfully.
2. It is patchable via ``monkeypatch.setattr("kernel.paths.is_windows", ...)``
   for callers WITHIN ``kernel.paths`` itself (module-global name lookup at
   call time honours the patch).
3. A ROUTED EXTERNAL consumer -- one that does
   ``from kernel.paths import is_windows`` and calls ``is_windows()`` -- is
   overridable too, but only by patching ITS OWN bound name (a from-import
   copies the reference at import time; patching the origin module's
   attribute afterwards does not reach back into an already-bound name in a
   different module's namespace). ``specify_cli.runtime.home`` is used as the
   real, already-routed external consumer for this proof.

No test in this module ever fakes ``os.name`` (C-003): doing so flips
``pathlib``'s ``Path`` to ``WindowsPath`` mid-test-run and crashes pytest.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import kernel.paths as kernel_paths
from kernel.paths import is_windows


pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_is_windows_reflects_real_os_name() -> None:
    """Unpatched, ``is_windows()`` matches the real ``os.name`` on this host."""
    assert is_windows() == (os.name == "nt")


def test_is_windows_is_a_public_module_attribute() -> None:
    """The seam is exported as a public name -- not the old private ``_is_windows``."""
    assert hasattr(kernel_paths, "is_windows")
    assert not hasattr(kernel_paths, "_is_windows")
    assert "is_windows" in kernel_paths.__all__


def test_patching_the_seam_overrides_an_in_module_caller(monkeypatch: pytest.MonkeyPatch) -> None:
    """C-003: monkeypatching ``kernel.paths.is_windows`` overrides a caller INSIDE kernel.paths.

    ``get_kittify_home`` calls the bare (module-global) name ``is_windows()``
    from within ``kernel/paths.py`` itself, so Python resolves it via the
    module's own namespace at call time -- exactly what
    ``monkeypatch.setattr`` mutates.
    """
    monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
    monkeypatch.setattr("kernel.paths.is_windows", lambda: False)

    assert kernel_paths.get_kittify_home() == Path.home() / ".kittify"


def test_patching_the_seam_true_flips_an_in_module_caller(monkeypatch: pytest.MonkeyPatch) -> None:
    """The same seam, patched the other way, flips the in-module caller to the Windows branch."""
    monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
    monkeypatch.setattr("kernel.paths.is_windows", lambda: True)
    monkeypatch.setattr(
        "platformdirs.user_data_dir",
        lambda *_a, **_kw: r"C:\Users\test\AppData\Local\spec-kitty",
    )

    assert kernel_paths.get_kittify_home() == Path(r"C:\Users\test\AppData\Local\spec-kitty")


def test_routed_external_consumer_honours_its_own_bound_patch(monkeypatch: pytest.MonkeyPatch) -> None:
    """A routed consumer (``specify_cli.runtime.home``) is overridable via ITS OWN name.

    ``specify_cli.runtime.home`` does ``from kernel.paths import is_windows``
    at module scope (OS1: never an inline literal). That import binds a
    fresh reference into ``specify_cli.runtime.home``'s own namespace, so the
    override target for THIS consumer is
    ``specify_cli.runtime.home.is_windows`` -- not ``kernel.paths.is_windows``,
    which the consumer no longer consults after import time.
    """
    from specify_cli.runtime import home

    monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
    monkeypatch.setattr("specify_cli.runtime.home.is_windows", lambda: False)

    assert home.get_kittify_home() == Path.home() / ".kittify"


def test_routed_external_consumer_windows_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """The routed consumer's Windows branch is reachable via the same per-module override."""
    from specify_cli.runtime import home

    monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
    monkeypatch.setattr("specify_cli.runtime.home.is_windows", lambda: True)

    class _FakeRuntimeRoot:
        base = Path("/fake/runtime/root")

    monkeypatch.setattr(
        "specify_cli.paths.get_runtime_root",
        lambda: _FakeRuntimeRoot(),
    )

    assert home.get_kittify_home() == Path("/fake/runtime/root")


def test_is_windows_call_signature_is_patchable_with_a_zero_arg_callable(monkeypatch: pytest.MonkeyPatch) -> None:
    """The seam is called with no arguments -- a monkeypatch replacement must be a zero-arg callable."""
    calls: list[bool] = []

    def _fake() -> bool:
        calls.append(True)
        return False

    monkeypatch.setattr("kernel.paths.is_windows", _fake)
    kernel_paths.is_windows()

    assert calls == [True]
