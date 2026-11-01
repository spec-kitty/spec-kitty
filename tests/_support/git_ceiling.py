"""Make the test run's own temp roots a git ceiling (#7022, #5356).

Placeholder: the red-first commit adds only the API surface; the next commit
implements it and wires it into ``tests/conftest.py``.
"""

from __future__ import annotations

from collections.abc import Iterable, MutableMapping
from pathlib import Path
from typing import Any

#: The variable git (and ``specify_cli.core.paths``) reads for discovery ceilings.
GIT_CEILING_ENV = "GIT_CEILING_DIRECTORIES"


def harness_git_ceilings(config: Any, home_base: Path) -> list[Path]:
    raise NotImplementedError


def install_git_ceilings(dirs: Iterable[Path], environ: MutableMapping[str, str]) -> None:
    raise NotImplementedError
