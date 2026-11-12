"""Canonical ``uv run`` pytest-invocation resolver (SSOT D3, #2570.3).

``pytest`` is a test-only optional-dependency extra (see the project's
``pyproject.toml``), so the ambient CLI interpreter (``sys.executable``)
legitimately may not have it installed. The pre-review gate previously
hardcoded ``sys.executable -m pytest`` at its one call site
(``review.pre_review_gate.run_scoped_tests_at_head``); under an interpreter
that lacks the ``test`` extra this fails with ``No module named pytest`` and
the gate silently degrades to a false ``GateOutcome.NO_COVERAGE`` warn — the
exact failure #2570.3 removes.

``uv run --frozen --project <repo_root> ...`` re-resolves the project's own
``uv``-managed environment and requests a declared ``test`` extra, so it is
preferred whenever both ``uv`` is on ``PATH`` and the target looks like a
``uv``-managed project (a ``pyproject.toml`` at its root). There is no other
shared ``uv run`` executor in ``src/`` today — ``compat/`` only carries
``uv tool install`` provenance, a distinct concern (installing spec-kitty
itself via uv, not invoking pytest) — so this module is the single new
canonical seam a later consumer should import rather than re-deriving.

**Consumer history (mission ``doctrine-controlled-transition-gates-01KY51Z7``
WP02/WP03, T007).** WP02 moved the then-sole production consumer to
``specify_cli.review.scope_source.GateCoverageScopeSource.test_command()``,
which injects ``--junitxml``/``-q`` and calls this resolver instead of the
prior direct call from ``review.pre_review_gate.run_scoped_tests_at_head``.
WP03 then repointed that same ``run_scoped_tests_at_head`` back onto this
resolver (see its own docstring's ``#2570.3`` reference), so today both call
sites call this resolver directly — there is no single "sole" consumer, and
neither supersedes the other. This resolver's own behaviour is unchanged;
only who calls it has changed over time.
"""

from __future__ import annotations

import shutil
import sys
import tomllib
from collections.abc import Sequence
from pathlib import Path

__all__ = ["resolve_pytest_command"]


def _test_dependency_flags(pyproject: Path) -> list[str]:
    """Return the ``uv run`` flags that install the project's test dependencies.

    ``[project.optional-dependencies].test`` -> ``--extra test``;
    otherwise a PEP 735 ``[dependency-groups].test`` -> ``--group test``
    (the extra wins when both exist: it is the long-standing declaration).
    Neither, or an unreadable/malformed pyproject -> no flag.
    """
    try:
        with pyproject.open("rb") as stream:
            data = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError):
        return []
    if "test" in data.get("project", {}).get("optional-dependencies", {}):
        return ["--extra", "test"]
    if "test" in data.get("dependency-groups", {}):
        return ["--group", "test"]
    return []


def resolve_pytest_command(
    pytest_args: Sequence[str],
    *,
    repo_root: Path,
    interpreter: str | None = None,
    path: str | None = None,
) -> list[str]:
    """Build the ``python -m pytest`` invocation for an interpreter that has pytest.

    Resolution order:

    1. ``uv`` is on ``PATH`` **and** ``<repo_root>/pyproject.toml`` and
       ``<repo_root>/uv.lock`` exist -> Run ``python -m pytest`` in the
       project's own managed virtualenv. Request ``--extra test`` (or
       ``--group test``) when declared, so pytest is installed there without
       rejecting projects that have no such extra. The lockfile is required
       (#3594): ``uv run --frozen`` refuses without one, so a project with
       only a ``pyproject.toml`` is not proof a frozen run can be built.
    2. Otherwise -> ``[sys.executable, "-m", "pytest", *pytest_args]``, the
       universal fallback used when ``uv`` is unavailable, or when
       ``repo_root`` is not a ``uv``-managed project (no ``pyproject.toml``
       and ``uv.lock`` pair at its root — a named edge case: the AND's
       second leg). This path runs in spec-kitty's own interpreter, so it is
       not isolated to the lane's environment (the #2803 residual when
       ``uv`` is unavailable).

    ``interpreter`` (#7547) replaces ``sys.executable`` in the fallback: a caller
    that probed a specific interpreter (the lane's own ``.venv``) passes it so
    the run uses the interpreter that was probed. ``path`` is the ``PATH`` the
    run will have; ``uv`` is looked up there, not in this process's ``PATH``.
    """
    if shutil.which("uv", path=path) is not None and (repo_root / "pyproject.toml").is_file() and (repo_root / "uv.lock").is_file():
        extra = _test_dependency_flags(repo_root / "pyproject.toml")
        return [
            "uv",
            "run",
            "--frozen",
            *extra,
            "--project",
            str(repo_root),
            "python",
            "-m",
            "pytest",
            *pytest_args,
        ]
    return [interpreter or sys.executable, "-m", "pytest", *pytest_args]
