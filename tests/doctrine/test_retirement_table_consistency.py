"""SC-008: the consumer retirement table agrees with the shipped built-in doctrine.

``RETIREMENTS`` (migration ``m_4_0_0rc5_retire_single_owner_doctrine_ids``) is
the single source of truth for the ids this mission retires. This module
imports it -- it never re-derives the table -- and checks three things against
the shipped pack:

1. every retired ``(kind, stem)`` no longer resolves in built-in doctrine
   (the fail-closed compile path raises ``UnknownArtifactIdError`` for it);
2. every successor resolves, and the shipped ``default.yaml`` activates it
   wherever the pre-mission default pack activated the retired id;
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
_DEFAULT_PACK = _REPO_ROOT / "src/charter/activation/packs/default.yaml"

#: The retired ids the PRE-mission ``default.yaml`` activated (captured with
#: ``git show dccf6aa7:src/charter/activation/packs/default.yaml``; the other
#: four retired ids were never in the default pack). Hard-coded so this test
#: never derives its baseline from a file this mission edits.
_BASE_DEFAULT_ACTIVATED: frozenset[tuple[str, str]] = frozenset(
    {
        ("activated_tactics", "behavior-driven-development"),
        ("activated_tactics", "boring-code-review"),
        ("activated_tactics", "bug-fixing-checklist"),
        ("activated_tactics", "locality-of-change"),
    }
)

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
    assert len(RETIREMENTS) == 8


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


@pytest.mark.parametrize(
    "retirement",
    [r for r in RETIREMENTS if (r.kind_key, r.stem) in _BASE_DEFAULT_ACTIVATED],
    ids=_id,
)
def test_default_pack_swaps_retired_id_for_successors(retirement: Retirement) -> None:
    pack = YAML(typ="safe").load(_DEFAULT_PACK.read_text(encoding="utf-8"))
    assert retirement.stem not in (pack.get(retirement.kind_key) or [])
    for kind_key, stem in retirement.successors:
        assert stem in (pack.get(kind_key) or []), f"{stem} missing from default.yaml {kind_key}"


def test_base_default_activation_literal_is_covered_by_the_table() -> None:
    """Every hard-coded base entry is a real table row (no drift in the literal)."""
    table = {(r.kind_key, r.stem) for r in RETIREMENTS}
    assert table >= _BASE_DEFAULT_ACTIVATED


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
