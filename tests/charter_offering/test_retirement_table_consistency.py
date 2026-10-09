"""The consumer retirement table agrees with the shipped built-in doctrine.

``RETIREMENTS`` (migration ``m_4_0_0rc5_retire_single_owner_doctrine_ids``) is
the single source of truth for the retired single-owner doctrine ids. This module
imports it -- it never re-derives the table -- and checks three things against
the shipped pack:

1. every retired ``(kind, stem)`` no longer resolves in built-in doctrine
   (the fail-closed compile path raises ``UnknownArtifactIdError`` for it);
2. every successor resolves, and the built-in ``default`` preset keeps the
   successors of the retired ids the old default pack used to activate
   effective (it lists none of the retired ids; a kind it does not list is
   unrestricted, and a kind it lists carries the successors);
3. a fixture consumer project that activates EVERY retired id compiles its
   activation roots after the migration's ``apply``, with each successor
   activated -- and fails to compile before it (the negative control).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.activation.compiler import resolve_config_activated_roots
from charter.activation.kind_vocabulary import UnknownArtifactIdError
from specify_cli.upgrade.migrations._retired_activation import Retirement
from specify_cli.upgrade.migrations.m_4_0_0rc5_retire_single_owner_doctrine_ids import (
    RETIREMENTS,
    RetireSingleOwnerDoctrineIdsMigration,
)

pytestmark = [pytest.mark.doctrine, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_PRESET = _REPO_ROOT / "packs/built-in/presets/default.yaml"

#: The retired ids the default pack used to activate (the other retired ids were
#: never in the default pack). Each must be a real ``RETIREMENTS`` row: the
#: parametrized test below looks the row up and fails on a name that drifted.
_DEFAULT_PACK_RETIRED: tuple[tuple[str, str], ...] = (
    ("activated_tactics", "behavior-driven-development"),
    ("activated_tactics", "boring-code-review"),
    ("activated_tactics", "bug-fixing-checklist"),
    ("activated_tactics", "locality-of-change"),
)
_ROWS: dict[tuple[str, str], Retirement] = {(r.kind_key, r.stem): r for r in RETIREMENTS}

#: A seed entry per activation list, so the migration's successor activation
#: (which never creates a missing list) has a list to extend.
_SEED: dict[str, str] = {
    "activated_directives": "010-specification-fidelity-requirement",
    "activated_tactics": "acceptance-test-first",
    "activated_styleguides": "testing-principles",
    "activated_procedures": "refactoring",
}


def _write_config(root: Path, activation: dict[str, list[str]]) -> None:
    config = root / ".kittify" / "config.yaml"
    config.parent.mkdir(parents=True, exist_ok=True)
    lines = ["mission_type_activations:", "  - software-dev"]
    for key, values in activation.items():
        lines.append(f"{key}:")
        lines.extend(f"  - {v}" for v in values)
    config.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_config(root: Path) -> dict[str, list[str]]:
    data = YAML(typ="safe").load((root / ".kittify" / "config.yaml").read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _id(retirement: Retirement) -> str:
    return f"{retirement.kind_key}:{retirement.stem}"


def test_table_is_non_empty() -> None:
    """Guard against a vacuous pass if the table were ever emptied."""
    assert RETIREMENTS


@pytest.mark.parametrize("retirement", RETIREMENTS, ids=_id)
def test_retired_id_no_longer_resolves(tmp_path: Path, retirement: Retirement) -> None:
    _write_config(tmp_path, {retirement.kind_key: [retirement.stem]})
    with pytest.raises(UnknownArtifactIdError):
        resolve_config_activated_roots(repo_root=tmp_path)


_SUCCESSORS: list[tuple[str, str]] = sorted({s for r in RETIREMENTS for s in r.successors})


@pytest.mark.parametrize(("kind_key", "stem"), _SUCCESSORS, ids=[f"{k}:{s}" for k, s in _SUCCESSORS])
def test_successor_resolves(tmp_path: Path, kind_key: str, stem: str) -> None:
    _write_config(tmp_path, {kind_key: [stem]})
    roots = resolve_config_activated_roots(repo_root=tmp_path)
    field = kind_key.removeprefix("activated_")
    assert stem in getattr(roots, field)


@pytest.mark.parametrize("row_key", _DEFAULT_PACK_RETIRED, ids=lambda k: f"{k[0]}:{k[1]}")
def test_default_preset_keeps_successors_effective(row_key: tuple[str, str]) -> None:
    retirement = _ROWS[row_key]
    preset = YAML(typ="safe").load(_DEFAULT_PRESET.read_text(encoding="utf-8"))
    assert retirement.stem not in (preset.get(retirement.kind_key) or [])
    for kind_key, stem in retirement.successors:
        # An absent key leaves the kind unrestricted, so the successor is effective.
        if kind_key in preset:
            assert stem in (preset.get(kind_key) or []), f"{stem} missing from the default preset's {kind_key}"


def _all_retired_activation() -> dict[str, list[str]]:
    activation: dict[str, list[str]] = {key: [seed] for key, seed in _SEED.items()}
    for retirement in RETIREMENTS:
        activation.setdefault(retirement.kind_key, []).append(retirement.stem)
    return activation


def test_fixture_project_fails_to_compile_before_the_migration(tmp_path: Path) -> None:
    """Negative control: the stale activations really do break compilation."""
    _write_config(tmp_path, _all_retired_activation())
    with pytest.raises(UnknownArtifactIdError):
        resolve_config_activated_roots(repo_root=tmp_path)


def test_fixture_project_compiles_after_the_migration(tmp_path: Path) -> None:
    _write_config(tmp_path, _all_retired_activation())

    result = RetireSingleOwnerDoctrineIdsMigration().apply(tmp_path)
    assert result.success, result

    roots = resolve_config_activated_roots(repo_root=tmp_path)
    config = _load_config(tmp_path)
    for retirement in RETIREMENTS:
        assert retirement.stem not in (config.get(retirement.kind_key) or [])
        for kind_key, stem in retirement.successors:
            assert stem in (config.get(kind_key) or []), f"successor {stem} not activated"
            assert stem in getattr(roots, kind_key.removeprefix("activated_"))
