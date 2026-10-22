"""The pack-skill fixture builder seeds activation the way production stores it (#6596)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from kernel.activation_ledger_store import activation_ledger_path
from tests._factories.activation_ledger import read_activation_ledger
from tests.charter import skill_pack_support as support

pytestmark = [pytest.mark.fast]


def _config(root: Path) -> dict[str, object]:
    return dict(yaml.safe_load((root / ".kittify" / "config.yaml").read_text(encoding="utf-8")) or {})


def test_activation_lands_on_the_ledger_and_never_in_config(tmp_path: Path) -> None:
    support.write_config(tmp_path, None, extra="agents:\n  available:\n    - claude\n", ledger={"activated_skills": ["x"]})

    assert read_activation_ledger(tmp_path) == {"mission_type_activations": ["software-dev"], "activated_skills": ["x"]}
    assert _config(tmp_path) == {"agents": {"available": ["claude"]}}


def test_a_second_call_replaces_the_ledger_rather_than_merging(tmp_path: Path) -> None:
    support.write_config(tmp_path, None, ledger={"activated_skills": ["x"], "deactivated_skills": ["y"]})
    support.write_config(tmp_path, None)

    assert read_activation_ledger(tmp_path) == {"mission_type_activations": ["software-dev"]}


def test_an_activation_key_in_extra_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"\['activated_skills'\].*ledger="):
        support.write_config(tmp_path, None, extra="activated_skills: []\n")
    assert not (tmp_path / ".kittify").exists()


def test_legacy_writes_the_unmigrated_config_surface_and_no_ledger(tmp_path: Path) -> None:
    support.write_config(tmp_path, None, ledger={"activated_skills": []}, legacy=True)
    support.write_config(tmp_path, None, ledger={"activated_skills": ["x"]}, legacy=True)

    assert _config(tmp_path) == {"mission_type_activations": ["software-dev"], "activated_skills": ["x"]}
    assert not activation_ledger_path(tmp_path).exists()
