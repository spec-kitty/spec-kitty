"""The ``charter.yaml`` bootstrap copies legacy allow keys only for a LEGACY source (WP14 T081, holes 4/5, C-003).

``compiler._bootstrap_charter_yaml`` creates ``charter.yaml`` the first time and
mints the ``config.yaml`` ``charter:`` pointer. On an unmigrated no-pointer
project the reads then follow the pointer, so the bootstrap copies the
``config.yaml`` allow keys verbatim (dropping the copy would widen every kind to
"absent = all"). It never copies a deny key, and with a ledger, or on a fresh
project, it copies nothing: the ledger is the authority there, and a copy would
only make stray keys.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from charter.activation.activation_ledger import DENY_KEYS, LEDGER_KEYS
from charter.activation.compiler import _build_metadata_dict, _bootstrap_charter_yaml
from tests._factories.activation_ledger import seed_activation_ledger

pytestmark = [pytest.mark.fast]

_SAFE = YAML(typ="safe")
_CATALOG = {"mission": "software-dev", "template_set": "software-dev-default"}
_D = "024-locality-of-change"


def _config(root: Path, text: str) -> None:
    (root / ".kittify").mkdir(parents=True, exist_ok=True)
    (root / ".kittify" / "config.yaml").write_text(text, encoding="utf-8")


def _bootstrap(root: Path) -> dict[str, Any]:
    target = root / ".kittify" / "charter" / "charter.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    _bootstrap_charter_yaml(target, catalog=_CATALOG, metadata=_build_metadata_dict(), repo_root=root)
    return dict(_SAFE.load(target.read_text(encoding="utf-8")) or {})


def test_positive_control_an_unmigrated_project_gets_its_allow_keys_copied(tmp_path: Path) -> None:
    _config(tmp_path, f"mission_type_activations:\n- software-dev\nactivated_directives:\n- {_D}\n")
    charter = _bootstrap(tmp_path)
    assert charter["activated_directives"] == [_D]
    assert charter["mission_type_activations"] == ["software-dev"]


def test_the_copy_never_carries_a_deny_key(tmp_path: Path) -> None:
    _config(tmp_path, f"activated_directives:\n- {_D}\ndeactivated_directives:\n- {_D}\n")
    charter = _bootstrap(tmp_path)
    assert charter["activated_directives"] == [_D]
    assert set(charter).isdisjoint(DENY_KEYS)


def test_with_a_ledger_stray_config_keys_are_not_copied(tmp_path: Path) -> None:
    _config(tmp_path, f"activated_directives:\n- {_D}\nmission_type_activations:\n- software-dev\n")
    seed_activation_ledger(tmp_path, mission_type_activations=["software-dev"])
    charter = _bootstrap(tmp_path)
    assert set(charter).isdisjoint(LEDGER_KEYS)


def test_a_fresh_project_gets_no_activation_key(tmp_path: Path) -> None:
    _config(tmp_path, "agents: {}\n")
    charter = _bootstrap(tmp_path)
    assert set(charter).isdisjoint(LEDGER_KEYS)
