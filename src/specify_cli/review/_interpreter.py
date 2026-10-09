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


def resolve_pytest_command(pytest_args: Sequence[str], *, repo_root: Path) -> list[str]:
    """Build the ``python -m pytest`` invocation for an interpreter that has pytest.

    Resolution order:

    1. ``uv`` is on ``PATH`` **and** ``<repo_root>/pyproject.toml`` exists ->
       Run ``python -m pytest`` in the project's own managed virtualenv.
       Request ``--extra test`` (or ``--group test``) when declared, so pytest is
       installed there without rejecting projects that have no such extra.
    2. Otherwise -> ``[sys.executable, "-m", "pytest", *pytest_args]``, the
       universal fallback used when ``uv`` is unavailable, or when
       ``repo_root`` is not a ``uv``-managed project (no ``pyproject.toml``
       at its root — a named edge case: the AND's second leg).
    """
    if shutil.which("uv") is not None and (repo_root / "pyproject.toml").is_file():
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
    return [sys.executable, "-m", "pytest", *pytest_args]
