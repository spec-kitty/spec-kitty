"""No living surface names a charter config key as a ``charter.offering`` module path (#4836).

Why this gate exists
--------------------
The ``src/doctrine`` → ``src/charter/offering`` module move rewrote the token
``doctrine.`` to ``charter.offering.``. Prose that named *config keys* under
the old ``doctrine`` key was rewritten with it, so operator surfaces sent
people to keys that do not exist:

* ``doctor doctrine`` told operators to add a ``'charter.offering.org'`` block
  to ``.kittify/config.yaml`` (the key is ``charter_packs.org``);
* shipped skills cited ``governance.charter.offering.governance_references``
  and ``charter.offering.selected_paradigms`` (the keys live under
  ``governance.charter``);
* the runtime doctor said "Set charter.offering.template_set in charter".

Rule: ``charter.offering.<name>`` must never appear on a living surface when
``<name>`` is a charter config key. The key set is derived from the schema
(:class:`DoctrineSelectionConfig` fields plus the ``charter_packs`` tier
keys), so there is nothing to hand-maintain and no allowlist. Real module
references (``charter.offering.artifact_kinds``) and mentions of retired
modules are untouched.

Scope: ``src/``, ``packs/`` and the living docs. The immutable record roots
(ADRs, dated reports, the archive, migration runbooks, archival plans) are out
of scope per ``docs/development/reference/terminology-exemptions.md``, and so
is ``docs/changelog/``: its entries quote the old wrong text as the "Before".
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from charter.activation.schemas import DoctrineSelectionConfig

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCAN_ROOTS = ("src", "packs", "docs")
_SUFFIXES = frozenset({".py", ".md", ".yaml", ".yml", ".toml", ".txt"})

#: Immutable record roots (terminology-exemptions.md) and the changelog.
_EXCLUDED_PREFIXES = (
    "docs/adr/",
    "docs/reports/",
    "docs/archive/",
    "docs/migrations/",
    "docs/plans/engineering-notes/",
    "docs/plans/initiatives/",
    "docs/changelog/",
)

#: ``charter_packs.<tier>`` keys in ``.kittify/config.yaml``.
_PACK_TIER_KEYS = frozenset({"org", "project"})
_CONFIG_KEYS = frozenset(DoctrineSelectionConfig.model_fields) | _PACK_TIER_KEYS

_TOKEN = re.compile(r"charter\.offering\.([A-Za-z_][A-Za-z0-9_]*)")

#: Non-vacuity floor: a scan that stopped reaching the trees passes over nothing.
_MIN_FILES_SCANNED = 2000


def _scanned_files() -> list[Path]:
    files: list[Path] = []
    for root in _SCAN_ROOTS:
        for path in sorted((_REPO_ROOT / root).rglob("*")):
            rel = path.relative_to(_REPO_ROOT).as_posix()
            if path.suffix not in _SUFFIXES or not path.is_file():
                continue
            if rel.startswith(_EXCLUDED_PREFIXES) or "/__pycache__/" in rel:
                continue
            files.append(path)
    return files


def _offenders(text: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in _TOKEN.finditer(line):
            if match.group(1) in _CONFIG_KEYS:
                found.append((lineno, match.group(0)))
    return found


def test_no_config_key_is_spelled_as_a_module_path() -> None:
    violations: list[str] = []
    for path in _scanned_files():
        rel = path.relative_to(_REPO_ROOT).as_posix()
        for lineno, token in _offenders(path.read_text(encoding="utf-8", errors="replace")):
            violations.append(f"{rel}:{lineno}  {token}")
    assert not violations, (
        "These name a charter config key as a `charter.offering.*` module path. "
        "Selection keys live under `governance.charter.<key>` in charter.yaml; "
        "pack tiers under `charter_packs.<tier>` in .kittify/config.yaml:\n  " + "\n  ".join(violations)
    )


def test_gate_reaches_a_real_file_count() -> None:
    assert len(_scanned_files()) >= _MIN_FILES_SCANNED


def test_config_key_set_is_derived_and_non_empty() -> None:
    assert {"selected_directives", "template_set", "governance_references"} <= _CONFIG_KEYS


@pytest.mark.parametrize(
    "line",
    [
        "Add a 'charter.offering.org' block to .kittify/config.yaml",
        "`governance.charter.offering.governance_references` points at them",
        "Set charter.offering.template_set in charter",
        "| `charter.offering.selected_paradigms` | list |",
    ],
)
def test_gate_flags_a_planted_config_key_path(line: str) -> None:
    """Self-mutation: each shape the #4836 defect took is caught."""
    assert _offenders(line)


@pytest.mark.parametrize(
    "line",
    [
        "from charter.offering.artifact_kinds import ArtifactKind",
        'files("charter.offering.schemas")',
        "imported from ``charter.offering.mission_step_contracts`` (now retired)",
        "`governance.charter.selected_paradigms`",
    ],
)
def test_gate_leaves_module_paths_and_correct_keys_alone(line: str) -> None:
    assert _offenders(line) == []
