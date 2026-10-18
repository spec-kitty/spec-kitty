"""Build-time gate for the migration execution-order manifest (WP01 / IC-02, FR-007, SC-004).

The gate enforces four rules over ``order_manifest.txt`` and the registered
migration set:

1. exactly-once — every registered ``migration_id`` appears in the manifest
   exactly once (no orphan, no duplicate);
2. resolves — every manifest entry resolves to a registered migration (no
   dangling entry);
3. version-monotonic save annotated ties — target_versions are non-decreasing
   down the manifest (the single runs-first lead excepted), and an
   equal-version adjacency is allowed only when annotated ``# tie:``;
4. at most one ``runs_first`` migration.

This module asserts the REAL manifest passes all four, and that each rule FAILs
over a planted-fixture negative (orphan / dangling / non-monotonic / two
runs_first).
"""

from __future__ import annotations

import pytest
from packaging.version import Version

from specify_cli.upgrade.manifest import MANIFEST_PATH, ManifestEntry, load_manifest_entries
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.registry import MigrationRegistry

pytestmark = [pytest.mark.architectural]


# --------------------------------------------------------------------------- #
# Gate rules (pure; fed either the live registry or a planted fixture)         #
# --------------------------------------------------------------------------- #


def check_resolution(manifest_ids: list[str], registry_ids: list[str]) -> tuple[set[str], set[str], list[str]]:
    """Return (orphans, danglers, duplicate_ids)."""
    orphans = set(registry_ids) - set(manifest_ids)
    danglers = set(manifest_ids) - set(registry_ids)
    duplicates = sorted({mid for mid in manifest_ids if manifest_ids.count(mid) > 1})
    return orphans, danglers, duplicates


def check_monotonic(entries: list[ManifestEntry], version_of: dict[str, str]) -> list[str]:
    """Return a list of ordering violations (empty = passes)."""
    failures: list[str] = []
    leads = [e for e in entries if e.runs_first_reason is not None]
    if len(leads) > 1:
        failures.append(f"more than one runs-first lead: {[e.id for e in leads]}")
    has_valid_lead = bool(leads) and entries and entries[0].runs_first_reason is not None and len(leads) == 1
    if leads and not (entries and entries[0] is leads[0]):
        failures.append("a runs-first lead is not the first manifest entry")
    body = entries[1:] if has_valid_lead else entries
    for prev, cur in zip(body, body[1:], strict=False):
        vp, vc = Version(version_of[prev.id]), Version(version_of[cur.id])
        if vc < vp:
            failures.append(f"non-monotonic: {cur.id} ({vc}) precedes nothing but sorts below {prev.id} ({vp})")
        elif vc == vp and cur.tie_reason is None:
            failures.append(f"unannotated tie: {cur.id} shares target_version {vc} with {prev.id}")
    return failures


def runs_first_count(migrations: list[object]) -> int:
    return sum(1 for m in migrations if getattr(m, "runs_first", False))


# --------------------------------------------------------------------------- #
# Real manifest passes                                                          #
# --------------------------------------------------------------------------- #


def _live_registry() -> list:
    auto_discover_migrations()
    return MigrationRegistry.get_all()


def test_real_manifest_passes_every_rule() -> None:
    migrations = _live_registry()
    registry_ids = [m.migration_id for m in migrations]
    version_of = {m.migration_id: m.target_version for m in migrations}
    entries = load_manifest_entries(MANIFEST_PATH)
    manifest_ids = [e.id for e in entries]

    orphans, danglers, duplicates = check_resolution(manifest_ids, registry_ids)
    assert not orphans, f"registered migrations missing from the manifest: {sorted(orphans)}"
    assert not danglers, f"manifest entries with no registered migration: {sorted(danglers)}"
    assert not duplicates, f"duplicate manifest entries: {duplicates}"
    assert check_monotonic(entries, version_of) == []
    assert runs_first_count(migrations) <= 1


def test_real_registry_has_exactly_one_runs_first_lead() -> None:
    migrations = _live_registry()
    first = [m.migration_id for m in migrations if getattr(m, "runs_first", False)]
    assert first == ["charter_pack_cutover"]


# --------------------------------------------------------------------------- #
# Planted-fixture negatives — one per rule                                      #
# --------------------------------------------------------------------------- #


def _entry(mid: str, *, tie: str | None = None, lead: str | None = None, line_no: int = 1) -> ManifestEntry:
    return ManifestEntry(id=mid, tie_reason=tie, runs_first_reason=lead, line_no=line_no)


def test_planted_orphan_fails_the_gate() -> None:
    registry_ids = ["a", "b", "c"]
    manifest_ids = ["a", "b"]  # c is registered but absent from the manifest
    orphans, _, _ = check_resolution(manifest_ids, registry_ids)
    assert orphans == {"c"}


def test_planted_dangling_entry_fails_the_gate() -> None:
    registry_ids = ["a", "b"]
    manifest_ids = ["a", "b", "ghost"]  # ghost resolves to no migration
    _, danglers, _ = check_resolution(manifest_ids, registry_ids)
    assert danglers == {"ghost"}


def test_planted_duplicate_entry_fails_the_gate() -> None:
    _, _, duplicates = check_resolution(["a", "b", "a"], ["a", "b"])
    assert duplicates == ["a"]


def test_planted_non_monotonic_order_fails_the_gate() -> None:
    entries = [_entry("hi", line_no=1), _entry("lo", line_no=2)]
    version_of = {"hi": "2.0.0", "lo": "1.0.0"}  # unannotated version decrease
    failures = check_monotonic(entries, version_of)
    assert any("non-monotonic" in f for f in failures)


def test_planted_unannotated_tie_fails_the_gate() -> None:
    entries = [_entry("one", line_no=1), _entry("two", line_no=2)]  # two has no tie annotation
    version_of = {"one": "1.0.0", "two": "1.0.0"}
    failures = check_monotonic(entries, version_of)
    assert any("unannotated tie" in f for f in failures)


def test_planted_two_runs_first_fails_the_gate() -> None:
    class _RunsFirst:
        runs_first = True

    assert runs_first_count([_RunsFirst(), _RunsFirst()]) == 2  # > 1 trips the gate
    assert runs_first_count([_RunsFirst()]) <= 1  # one is fine
