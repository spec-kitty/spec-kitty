"""Shrink-only ratchet over the flake8-pytest-style (PT) weak-oracle baseline.

Issue #5351: `pytest.raises(ValueError)` without ``match=``, a ``raises`` block
where any of several statements can satisfy it, and an assertion inside an
``except`` that never runs when nothing raises all let a test pass on a broken
product (DIRECTIVE_041 integrity rule 1). Ruff can reject those shapes before a
single test runs, so the PT weak-oracle rules are selected in
``pyproject.toml`` and the legacy hits are frozen per file in ``ruff.toml``'s
``[lint.extend-per-file-ignores]`` baseline.

This guard keeps that baseline honest in both directions, the same way
``test_ruff_format_exclude_ratchet.py`` guards the formatter-debt list:

* it cannot grow without a visible bump of ``_BASELINE_PT_PAIRS``;
* an entry whose file no longer trips the listed code must be removed; and
* the rules are really live: a planted weak oracle in a fresh test file is
  flagged under the repository's own ruff config.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_RUFF_TOML = _REPO_ROOT / "ruff.toml"
_PYPROJECT = _REPO_ROOT / "pyproject.toml"

# The PT rules selected in pyproject.toml as weak-oracle gates.
_WEAK_ORACLE_RULES = ("PT010", "PT011", "PT012", "PT015", "PT016", "PT017", "PT030", "PT031")

# Shrink-only high-water mark of (file, PT code) baseline pairs, as of the
# 2026-09-29 enablement (123 files). Lower it when you clean a file; raising it
# needs a reviewed reason the new test cannot simply name its expected failure.
_BASELINE_PT_PAIRS = 125


def _pt_baseline() -> dict[str, list[str]]:
    config = tomllib.loads(_RUFF_TOML.read_text(encoding="utf-8"))
    ignores = config["lint"]["extend-per-file-ignores"]
    return {path: sorted(code for code in codes if code.startswith("PT")) for path, codes in ignores.items() if any(code.startswith("PT") for code in codes)}


def _ruff_hits(paths: list[str], rules: tuple[str, ...]) -> set[tuple[str, str]]:
    """(path, code) pairs ruff reports for ``rules`` on ``paths``, ignoring the baseline."""
    proc = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--isolated", "--no-cache", "--select", ",".join(rules), "--output-format", "json", *paths],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode in (0, 1), f"ruff failed before reporting findings (rc={proc.returncode}):\n{proc.stderr}"
    return {(str(Path(item["filename"]).resolve().relative_to(_REPO_ROOT)), item["code"]) for item in json.loads(proc.stdout or "[]")}


def test_weak_oracle_rules_are_selected() -> None:
    """Every weak-oracle PT rule stays in the enforced ``select`` list."""
    config = tomllib.loads(_PYPROJECT.read_text(encoding="utf-8"))
    selected = set(config["tool"]["ruff"]["lint"]["select"])
    missing = [rule for rule in _WEAK_ORACLE_RULES if rule not in selected]
    assert not missing, f"PT weak-oracle rules dropped from [tool.ruff.lint].select: {missing}"


def test_pt_baseline_does_not_exceed_high_water_mark() -> None:
    """Growth requires an explicit, reviewed bump of ``_BASELINE_PT_PAIRS``."""
    pairs = sum(len(codes) for codes in _pt_baseline().values())
    assert pairs <= _BASELINE_PT_PAIRS, (
        f"The ruff.toml PT baseline grew to {pairs} (file, code) pairs, above {_BASELINE_PT_PAIRS}. "
        "Give the new pytest.raises/warns a match= or a single statement instead of baselining it."
    )


def test_pt_baseline_has_no_glob_entries() -> None:
    """A glob would silently exempt every present and future file under it."""
    globs = [path for path in _pt_baseline() if "*" in path]
    assert not globs, f"PT baseline entries must be exact paths, not globs: {globs}"


def test_every_pt_baseline_entry_still_fires() -> None:
    """A cleaned file's PT codes must leave the baseline in the same commit."""
    baseline = _pt_baseline()
    missing_files = [path for path in baseline if not (_REPO_ROOT / path).exists()]
    assert not missing_files, f"PT baseline names files that no longer exist: {missing_files}"

    live = _ruff_hits(sorted(baseline), _WEAK_ORACLE_RULES)
    stale = sorted((path, code) for path, codes in baseline.items() for code in codes if (path, code) not in live)
    assert not stale, f"{len(stale)} PT baseline entries no longer fire; drop them from ruff.toml: {stale[:20]}"


# (planted snippet, the weak-oracle rule it must trip under the repo config).
# Spans more than one rule so a single rule silently moved to [lint].ignore
# (still "selected", so test_weak_oracle_rules_are_selected stays green) is
# caught here by its planted oracle no longer firing.
_PLANTED_WEAK_ORACLES = (
    ("PT011", "import pytest\n\n\ndef test_planted() -> None:\n    with pytest.raises(ValueError):\n        int('x')\n"),
    (
        "PT030",
        "import warnings\n\nimport pytest\n\n\ndef test_planted() -> None:\n    with pytest.warns(Warning):\n        warnings.warn('x', stacklevel=2)\n",
    ),
    (
        "PT017",
        "def test_planted() -> None:\n    try:\n        int('x')\n    except ValueError as exc:\n        assert str(exc)\n",
    ),
)


@pytest.mark.parametrize(("rule", "planted"), _PLANTED_WEAK_ORACLES, ids=[rule for rule, _ in _PLANTED_WEAK_ORACLES])
def test_planted_weak_oracle_is_flagged_under_repo_config(rule: str, planted: str) -> None:
    """Non-vacuity: the live config rejects a fresh weak oracle for each guarded rule."""
    proc = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--no-cache", "--output-format", "json", "--stdin-filename", "tests/unit/test_planted_weak_oracle.py", "-"],
        cwd=_REPO_ROOT,
        input=planted,
        capture_output=True,
        text=True,
        check=False,
    )
    codes = {item["code"] for item in json.loads(proc.stdout or "[]")}
    assert rule in codes, f"{rule} did not fire on its planted weak oracle; got {sorted(codes)}\n{proc.stderr}"
