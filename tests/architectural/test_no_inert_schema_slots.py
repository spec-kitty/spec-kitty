"""Reject newly declared doctrine slots with no live producer.

The frozen ledger remains migration debt, not a second test surface.  This file
keeps only the live shrink-only gate and a two-sided controlled fault over the
same scanner.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest

from tests.architectural._inert_slots import (
    MINIMUM_MODEL_SLOT_NAMES,
    MINIMUM_SCHEMA_SLOT_NAMES,
    BaselineError,
    InertSlot,
    find_inert_slots,
    is_schema_declared,
    load_baseline,
    ratchet,
    scanned_slots,
)

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _plant(root: Path, *, slot: str, produced: bool) -> None:
    schema_dir = root / "src" / "charter" / "offering" / "schemas"
    schema_dir.mkdir(parents=True, exist_ok=True)
    (schema_dir / "probe.schema.yaml").write_text(
        f"type: object\nproperties:\n  {slot}:\n    type: string\n",
        encoding="utf-8",
    )
    if produced:
        artifact_dir = root / "src" / "charter" / "offering" / "styleguides" / "built-in"
        artifact_dir.mkdir(parents=True)
        (artifact_dir / "probe.styleguide.yaml").write_text(
            f"id: probe\n{slot}: live\n",
            encoding="utf-8",
        )


def test_inert_slot_scanner_has_two_sided_fault_bite(tmp_path: Path) -> None:
    _plant(tmp_path, slot="live_slot", produced=True)
    assert find_inert_slots(tmp_path) == []

    _plant(tmp_path, slot="missing_producer", produced=False)
    assert [slot.name for slot in find_inert_slots(tmp_path)] == ["missing_producer"]


def test_schema_definitions_are_not_mistaken_for_data_slots(tmp_path: Path) -> None:
    schema_dir = tmp_path / "src" / "charter" / "offering" / "schemas"
    schema_dir.mkdir(parents=True)
    (schema_dir / "probe.schema.yaml").write_text(
        "type: object\ndefinitions:\n  helper:\n    type: object\nproperties: {}\n",
        encoding="utf-8",
    )
    assert find_inert_slots(tmp_path) == []


_PRUNED_ROW = (
    "  - name: probe_slot\n    declared_at: src/charter/offering/schemas/probe.schema.yaml\n    disposition: wire-the-producer\n    note: planted probe row\n"
)


#: One legal-looking value per retired key, keyed by where it would sit.
_RETIRED_LINES = {
    "owner": "    owner: WP01\n",
    "provisional": "    provisional: false\n",
    "mission": "mission: some-mission-01ABCDEF\n",
    "code_only_suppressions": "code_only_suppressions: []\n",
}


@pytest.mark.parametrize(
    ("where", "key"),
    [
        ("entry", "owner"),
        ("entry", "provisional"),
        ("top", "mission"),
        ("top", "code_only_suppressions"),
    ],
)
def test_load_baseline_rejects_retired_keys(tmp_path: Path, where: str, key: str) -> None:
    """A retired inert-slot key is refused loudly, never silently carried."""
    retired_line = _RETIRED_LINES[key]
    entries = "entries:\n" + _PRUNED_ROW
    text = entries + retired_line if where == "entry" else retired_line + entries
    path = tmp_path / "baseline.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(BaselineError, match=rf"unknown key '{key}'"):
        load_baseline(path)


def _walk_floor_shortfalls(slots: set[InertSlot]) -> list[str]:
    """One message per walk whose distinct slot names fall below its floor."""
    schema_names = {slot.name for slot in slots if is_schema_declared(slot)}
    model_names = {slot.name for slot in slots if not is_schema_declared(slot)}
    walks = (
        ("schema", MINIMUM_SCHEMA_SLOT_NAMES, len(schema_names)),
        ("model", MINIMUM_MODEL_SLOT_NAMES, len(model_names)),
    )
    return [f"{walk} walk saw {count} distinct slot names, below its floor of {floor}" for walk, floor, count in walks if count < floor]


def test_live_scan_meets_per_walk_floors() -> None:
    assert _walk_floor_shortfalls(scanned_slots(_REPO_ROOT)) == []


def test_walk_floors_fail_on_a_collapsed_walk(tmp_path: Path) -> None:
    _plant(tmp_path, slot="lonely_slot", produced=False)
    shortfalls = _walk_floor_shortfalls(scanned_slots(tmp_path))
    assert len(shortfalls) == 2
    assert shortfalls[0].startswith("schema walk saw 1 distinct slot names")
    assert shortfalls[1].startswith("model walk saw 0 distinct slot names")


def test_live_tree_has_no_new_inert_slots() -> None:
    found = find_inert_slots(_REPO_ROOT)
    assert found, "inert-slot scan collected no live schema/model corpus"
    new, cleared = ratchet(found, load_baseline())
    if cleared:
        warnings.warn(
            "inert-slot baseline shrank; delete cleared ledger rows: " + ", ".join(entry.name for entry in cleared),
            stacklevel=1,
        )
    assert new == [], (
        "new schema/model slots declared with no live producer -- a real "
        'store-site (e.g. cfg["key"] = value) somewhere under src/ that actually '
        "WRITES the slot, not merely a class-body annotation or a schema "
        "declaration. Wire a real producer for the slot, or delete the unused "
        "declaration. New: " + ", ".join(f"{slot.name} ({slot.declared_at})" for slot in new)
    )
