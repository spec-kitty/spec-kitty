"""Anti-drift guard for the ``meta.json`` audit shape registry (#2696, FR-011 / NFR-004).

The audit registry's ``meta.json`` known-key set MUST be derived from the
canonical mission-metadata writer schema (``MissionMetaRequired`` +
``MissionMetaOptional``) plus the coordination write-path keys — never a
hand-rolled second copy that can silently drift and start reporting canonical
keys as ``UNKNOWN_SHAPE`` false positives.

These tests fail loudly the moment the writer schema grows a field the audit
registry does not know about, so the two can never re-diverge (NFR-004).
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from types import FunctionType

import pytest

from specify_cli.audit.shape_registry import (
    KNOWN_TOP_LEVEL_KEYS_BY_ARTIFACT,
    META_COORDINATION_KEYS,
)
from specify_cli.mission_metadata import MissionMetaOptional, MissionMetaRequired
from specify_cli.core.mission_creation_decisions import meta_flag_patch
from specify_cli.core.mission_creation_meta import _build_create_meta
from specify_cli.meta_keys import COORDINATION_KEYS, IDENTITY_KEYS
from specify_cli.migration.backfill_identity import backfill_mission
from specify_cli.migration.backfill_topology import backfill_mission_topology
from specify_cli.mission_metadata import flatten_coordination_metadata

pytestmark = [pytest.mark.unit]


def _writer_keys() -> frozenset[str]:
    return frozenset(MissionMetaRequired.__annotations__) | frozenset(
        MissionMetaOptional.__annotations__
    )


def test_every_writer_key_is_a_known_audit_key() -> None:
    """Writer keys ⊆ audit known keys — the anti-drift invariant (NFR-004)."""
    audit_keys = KNOWN_TOP_LEVEL_KEYS_BY_ARTIFACT["meta.json"]
    missing = _writer_keys() - audit_keys
    assert missing == set(), (
        "meta.json writer schema keys missing from the audit shape registry "
        f"(would be reported as UNKNOWN_SHAPE): {sorted(missing)}"
    )


def test_coordination_write_path_keys_are_known_audit_keys() -> None:
    """Real create and flatten writers cannot add unknown meta.json keys."""
    audit_keys = KNOWN_TOP_LEVEL_KEYS_BY_ARTIFACT["meta.json"]
    written = _literal_and_constant_meta_writes(_build_create_meta)
    written |= _literal_and_constant_meta_writes(flatten_coordination_metadata)
    written |= _literal_and_constant_meta_writes(backfill_mission)
    written |= _literal_and_constant_meta_writes(backfill_mission_topology)
    written |= set(meta_flag_patch(pr_bound=True, retain_branches=True, retain_worktrees=True, commit_to_target=True))
    # mid8 predates this coordination/identity follow-up and has separate schema debt.
    assert written - {"mid8"} <= audit_keys
    assert META_COORDINATION_KEYS == COORDINATION_KEYS
    assert written >= COORDINATION_KEYS


def _literal_and_constant_meta_writes(writer: FunctionType, *, source_override: str | None = None) -> set[str]:
    """Read actual subscript/setdefault write sites, resolving imported key constants."""
    source = textwrap.dedent(source_override if source_override is not None else inspect.getsource(writer))
    tree = ast.parse(source)
    globals_ = writer.__globals__
    keys: set[str] = set()
    for node in ast.walk(tree):
        key: ast.expr | None = None
        if isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store) and isinstance(node.value, ast.Name) and node.value.id == "meta":
            key = node.slice
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "setdefault"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "meta"
            and node.args
        ):
            key = node.args[0]
        if isinstance(key, ast.Constant) and isinstance(key.value, str):
            keys.add(key.value)
        elif isinstance(key, ast.Name) and isinstance(globals_.get(key.id), str):
            keys.add(globals_[key.id])
    return keys


def test_identity_keys_remain_known_audit_keys() -> None:
    """mission_id / mission_number stay known (identity model 083+, not in the TypedDicts)."""
    audit_keys = KNOWN_TOP_LEVEL_KEYS_BY_ARTIFACT["meta.json"]
    assert audit_keys >= IDENTITY_KEYS
    assert _literal_and_constant_meta_writes(_build_create_meta) >= IDENTITY_KEYS


def test_new_create_writer_key_would_be_detected() -> None:
    """An added writer key absent from the registry is observable by the guard."""
    source = 'def added_writer():\n    meta = {}\n    meta["new_coordination_key"] = True\n'
    assert _literal_and_constant_meta_writes(_build_create_meta, source_override=source) - KNOWN_TOP_LEVEL_KEYS_BY_ARTIFACT["meta.json"] == {"new_coordination_key"}
