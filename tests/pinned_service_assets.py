"""The one test-side reader of the pinned service extras (#6915).

The conformance fixtures, contract bundles and contract tools that core's tests read
come from the spec-kitty-events release pinned in ``pins/read-service.source.yaml``
(ADR 2026-10-29-1 D-6), not from a copy in this repository. ``make sync-services``
(``make dev-setup`` runs it with ``--extras-only``) and the ``sync-services`` CI action
fetch, verify and unpack them into the shared cache; this module only asks
``scripts/sync_services.py`` where an extra is unpacked.

It fails closed. A test that needs a pinned extra that is absent or does not match its
pin fails with the ``SERVICE_*`` code and the remedy ``run `make sync-services```; it
never skips, so a missing fetch cannot pass as green.

The cache is resolved from the real environment, not from the per-worker test HOME
(``tests/conftest.py`` redirects ``HOME`` but leaves ``XDG_CACHE_HOME`` alone and records
the real home in ``SPEC_KITTY_REAL_HOME_FOR_TESTS``): ``$XDG_CACHE_HOME`` when set, else
``<real home>/.cache``, the same place ``kernel.service_artifacts.default_cache_root`` uses
outside the test run.
"""

from __future__ import annotations

import functools
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

import pytest

from kernel.service_pin import PINS_DIR, load_service_pin, pin_file

__all__ = [
    "REPO_ROOT",
    "READ_SERVICE",
    "conformance_fixtures_root",
    "contract_bundle_dir",
    "contract_tools_dir",
    "expected_extra_root",
    "pinned_extra",
    "require_pinned_extra",
    "service_cache_root",
]

REPO_ROOT = Path(__file__).resolve().parents[1]
READ_SERVICE = "read-service"
_SCRIPT = REPO_ROOT / "scripts" / "sync_services.py"
_MODULE_NAME = "_sync_services_for_tests"
_REAL_HOME_ENV_VAR = "SPEC_KITTY_REAL_HOME_FOR_TESTS"
_SERVICES_CACHE = Path("spec-kitty") / "services"


@functools.cache
def _sync_services() -> ModuleType:
    """``scripts/sync_services.py``, loaded once by file path (it is a script, not a package module)."""
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module  # dataclasses resolve their module through sys.modules
    spec.loader.exec_module(module)
    return module


def service_cache_root() -> Path:
    """The shared service cache of the real environment (see the module docstring)."""
    xdg = os.environ.get("XDG_CACHE_HOME")
    if xdg:
        return Path(xdg) / _SERVICES_CACHE
    home = os.environ.get(_REAL_HOME_ENV_VAR) or str(Path.home())
    return Path(home) / ".cache" / _SERVICES_CACHE


def pinned_extra(extra: str, *, service: str = READ_SERVICE, cache_root: Path | None = None) -> Path:
    """Where *service*'s pinned *extra* is unpacked; fails the test (never skips) when it is not fetched."""
    module = _sync_services()
    root = service_cache_root() if cache_root is None else cache_root
    try:
        path: Path = module.extras_root(REPO_ROOT, service, extra, cache_root=root)
    except module.SyncServicesError as exc:
        pytest.fail(f"{exc} (pinned {service} extra {extra!r}, cache {root})", pytrace=False)
    return path


def expected_extra_root(extra: str, *, service: str = READ_SERVICE) -> Path:
    """Where *service*'s pinned *extra* is (or will be) unpacked, computed from the pin alone.

    Pure path arithmetic: nothing is read from the cache and nothing fails. For module-level
    constants; pair it with :func:`require_pinned_extra` (a module-scoped autouse fixture) so a
    test fails closed before it reads the path.
    """
    module = _sync_services()
    pin = load_service_pin(pin_file(REPO_ROOT / PINS_DIR, service))
    path: Path = module.extraction_dir(pin, pin.extras[extra], service_cache_root())
    return path


def require_pinned_extra(extra: str, *, service: str = READ_SERVICE) -> Path:
    """:func:`pinned_extra` that also proves it equals :func:`expected_extra_root` (for an autouse fixture)."""
    path = pinned_extra(extra, service=service)
    assert path == expected_extra_root(extra, service=service), (path, expected_extra_root(extra, service=service))
    return path


def conformance_fixtures_root() -> Path:
    """The unpacked ``conformance-fixtures`` asset: ``conformance/``, ``artifact-conformance/``, ``event-log/``, ``leak-patterns.json``."""
    return pinned_extra("fixtures")


def contract_bundle_dir(module: str) -> Path:
    """The bundled contract module directory (``bundle/<module>/openapi.yaml``, no ``$ref``)."""
    return pinned_extra("contracts") / "bundle" / module


def contract_tools_dir() -> Path:
    """The pinned contract tools (``contracts/tools/*.py``)."""
    return pinned_extra("contract_tools") / "contracts" / "tools"
