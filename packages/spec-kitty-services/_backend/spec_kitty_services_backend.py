"""In-tree PEP 517 build backend of ``spec-kitty-services`` (standard library only, #6904).

It builds the binary-free fallback wheel (``py3-none-any``), an editable wheel and
an sdist. The platform wheels that carry the pinned service binaries are built
by core's ``scripts/build_services_wheel.py`` with the same writer
(``spec_kitty_services/wheel.py``), loaded here by path so there is one writer.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
_WRITER = _ROOT / "spec_kitty_services" / "wheel.py"
_WRITER_MODULE = "spec_kitty_services_backend_wheel"


def _writer() -> ModuleType:
    spec = importlib.util.spec_from_file_location(_WRITER_MODULE, _WRITER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load the wheel writer from {_WRITER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_WRITER_MODULE] = module  # dataclasses resolve their module through sys.modules
    spec.loader.exec_module(module)
    return module


# PEP 517 fixes these hook signatures and frontends pass the arguments by keyword, so the
# names stay; the hooks below take no settings, and ``del`` says so explicitly.


def get_requires_for_build_wheel(config_settings: dict[str, Any] | None = None) -> list[str]:
    del config_settings
    return []


def get_requires_for_build_editable(config_settings: dict[str, Any] | None = None) -> list[str]:
    del config_settings
    return []


def get_requires_for_build_sdist(config_settings: dict[str, Any] | None = None) -> list[str]:
    del config_settings
    return []


def build_wheel(wheel_directory: str, config_settings: dict[str, Any] | None = None, metadata_directory: str | None = None) -> str:
    """The binary-free fallback wheel."""
    del config_settings, metadata_directory
    writer = _writer()
    path: Path = writer.build_companion_wheel(Path(wheel_directory), project_root=_ROOT, version=writer.project_version(_ROOT), target=None, binaries={})
    return path.name


def build_editable(wheel_directory: str, config_settings: dict[str, Any] | None = None, metadata_directory: str | None = None) -> str:
    """An editable wheel pointing at this source tree."""
    del config_settings, metadata_directory
    writer = _writer()
    path: Path = writer.build_editable_wheel(Path(wheel_directory), project_root=_ROOT, version=writer.project_version(_ROOT))
    return path.name


def build_sdist(sdist_directory: str, config_settings: dict[str, Any] | None = None) -> str:
    """A reproducible sdist of this source tree."""
    del config_settings
    writer = _writer()
    path: Path = writer.build_sdist(Path(sdist_directory), project_root=_ROOT, version=writer.project_version(_ROOT), backend_files=[Path(__file__).resolve()])
    return path.name
