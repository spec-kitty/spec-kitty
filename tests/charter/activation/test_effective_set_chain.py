"""Behavioural positive controls for the pack-chain authority consumers (#6006).

A two-pack fixture where an artifact id lives only in pack 2
must be observable through ``effective_set`` and ``preset_application``; the same
project declaring only pack 1 must not see them.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from charter.activation import preset_application as presets
from charter.activation.preset_application import PresetIdUnresolvedError
from charter.activation.effective_set import resolve_effective_sets
from charter.offering.packs.presets import ActivationPreset

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

PACK2_TACTIC = "pack-two-only-tactic"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _config(repo: Path, packs: list[tuple[str, Path]]) -> None:
    lines = ["charter_packs:", "  org:", "    packs:"]
    for name, local_path in packs:
        lines += [f"      - name: {name}", f"        local_path: {local_path}"]
    _write(repo / ".kittify" / "config.yaml", "\n".join(lines) + "\n")


def _build(tmp_path: Path, *, declare_pack2: bool) -> Path:
    repo = tmp_path / "repo"
    pack1 = repo / "org-packs" / "one"
    pack2 = repo / "org-packs" / "two"
    _write(
        pack1 / "tactics" / "pack-one-tactic.tactic.yaml",
        'schema_version: "1.0"\nid: pack-one-tactic\nname: one\npurpose: x\nsteps:\n  - title: A\n    description: d\n',
    )
    _write(
        pack2 / "tactics" / f"{PACK2_TACTIC}.tactic.yaml",
        f'schema_version: "1.0"\nid: {PACK2_TACTIC}\nname: two\npurpose: x\nsteps:\n  - title: A\n    description: d\n',
    )
    packs = [("one", pack1)] + ([("two", pack2)] if declare_pack2 else [])
    _config(repo, packs)
    return repo


def _preset() -> ActivationPreset:
    """A preset that lists the pack-2-only tactic by id (the id check walks the chain)."""
    return ActivationPreset(
        name="p",
        description="",
        activations={"activated_tactics": (PACK2_TACTIC,)},
        activated_kinds=None,
        mission_type_activations=None,
        source=Path("preset.yaml"),
    )


@pytest.mark.regression
def test_pack_two_artifacts_observable_through_effective_set_and_presets(tmp_path: Path) -> None:
    """#6006: the chain authority exposes pack 2 to every migrated surface."""
    repo = _build(tmp_path, declare_pack2=True)

    entry = resolve_effective_sets(repo, ["activated_tactics"])["activated_tactics"]
    assert entry.resolved
    assert PACK2_TACTIC in entry.ids and "pack-one-tactic" in entry.ids

    assert len(presets._org_roots_or_refuse(repo, _preset())) == 2
    presets._resolve_preset_ids(repo, _preset())  # resolves through pack 2: no refusal


@pytest.mark.regression
def test_negative_control_pack_two_absent_when_only_pack_one_declared(tmp_path: Path) -> None:
    repo = _build(tmp_path, declare_pack2=False)

    entry = resolve_effective_sets(repo, ["activated_tactics"])["activated_tactics"]
    assert PACK2_TACTIC not in entry.ids

    assert len(presets._org_roots_or_refuse(repo, _preset())) == 1
    with pytest.raises(PresetIdUnresolvedError):
        presets._resolve_preset_ids(repo, _preset())


def test_effective_set_stays_fail_closed_when_a_declared_pack_is_unfetched(tmp_path: Path) -> None:
    repo = _build(tmp_path, declare_pack2=True)
    (repo / "org-packs" / "two" / "tactics" / f"{PACK2_TACTIC}.tactic.yaml").unlink()

    shutil.rmtree(repo / "org-packs" / "two")

    entry = resolve_effective_sets(repo, ["activated_tactics"])["activated_tactics"]
    assert not entry.resolved
    assert "pack-one-tactic" in entry.fallback_ids
