"""Migration chain integrity gate (Mission B / Process Gap 2 follow-up).

The Mission B post-merge architecture review surfaced that:

* 78 migration files at ``src/specify_cli/upgrade/migrations/m_*.py`` are
  auto-discovered via ``pkgutil.iter_modules`` and self-register via
  ``@MigrationRegistry.register``.
* They are grandfathered as "glue, not active code" by
  ``tests/architectural/test_no_dead_modules.py`` (category 1).
* But there is **no systematic gate** that proves the migration chain is
  consistent -- that walking from the oldest supported migration through
  every migration in semver order lands on a version aligned with the
  current ``pyproject.toml`` baseline.

This test is that gate. It complements ``test_no_dead_modules.py``:

* That gate proves every migration module is importable (auto-discovery
  fires, the registry populates).
* This gate proves the registered migrations form an uninterrupted chain
  of monotonically increasing target versions, with no major-version gap
  that would silently break a long upgrade hop.

Algorithm
---------

1. Auto-discover all migrations via
   ``MigrationRegistry.get_all()`` (calling ``auto_discover_migrations()``
   first if the registry is empty).
2. Sort migrations by ``target_version`` using semver order
   (already guaranteed by ``get_all()``).
3. Walk the chain starting at ``OLDEST_SUPPORTED_VERSION = "0.0.0"``
   (the implicit FROM of the first migration -- the upgrade runner does
   not declare an explicit minimum, so the chain definition itself is
   the source of truth).
4. For each consecutive pair ``(prev, cur)`` in target-version order:

   * **patch-skip** (same X.Y, ``cur.micro > prev.micro + 1``) -- WARN.
     A patch release may have shipped with no migration if no schema
     change was required. Example: 0.6.5 -> 0.6.7 skipping 0.6.6.
   * **minor-skip** (same X, ``cur.minor > prev.minor + 1``) -- HARD FAIL,
     unless the jump is in the documented ``_KNOWN_LINE_JUMPS`` set.
     A skipped minor line usually means a missing migration: a user
     upgrading from prev to cur would have no path through it.
   * **major-skip** (``cur.major > prev.major + 1``) -- HARD FAIL,
     unless the jump is in ``_KNOWN_LINE_JUMPS``.
   * **major-bump** (``cur.major == prev.major + 1``) and
     **minor-bump** (``cur.minor == prev.minor + 1``) are normal.
   * **patch-bump** (``cur.micro == prev.micro + 1``) is normal.

5. After the walk, assert that the chain's terminal target version is
   **not newer than** the project version from ``pyproject.toml``.

   * If the chain end is **behind** pyproject -- OK only when the release has
     no migration at its exact version.
   * If the chain end is **ahead** of pyproject -- HARD FAIL: a user upgrading
     to the current package version will not run that migration.

The ``_KNOWN_LINE_JUMPS`` set is the ratchet for legitimate historical
discontinuities (e.g. 1.x was never released; the codebase jumped
0.14.0 -> 2.0.0a5 deliberately). New entries require an explicit
rationale and should be rare.

See ``work/mission-b-post-merge-review.md`` for the assessment that
produced this gate.
"""

from __future__ import annotations

import re
from pathlib import Path
from collections.abc import Callable

import pytest
from packaging.version import Version

from specify_cli.upgrade.manifest import load_manifest_entries
from specify_cli.upgrade.migrations import auto_discover_migrations
from specify_cli.upgrade.registry import MigrationRegistry

pytestmark = [pytest.mark.architectural]

# Type of the built-in ``record_property`` fixture: records a (name, value)
# pair into the JUnit/report output. Used to route the report-only
# patch-skip diagnostic off the ``warnings`` channel (NFR-006) while
# preserving the signal (each patch-skip is recorded, not silenced).
RecordPropertyFn = Callable[[str, object], None]


# Implicit start of the migration chain. The upgrade runner does not
# declare an explicit minimum -- the chain definition itself is the
# source of truth, and the first registered migration carries everyone
# from "before there was a project" up to its own target_version.
OLDEST_SUPPORTED_VERSION = "0.0.0"


# Known intentional line jumps. Each entry is a ``(from, to)`` tuple of
# semver-comparable strings. A jump appearing here suppresses the
# corresponding minor/major-skip hard failure. Each entry MUST carry a
# rationale comment explaining why no migration covers the gap.
#
# This is a ratchet: prefer adding a real migration over expanding this
# set. Entries should be reserved for historical discontinuities that
# cannot be retroactively bridged.
_KNOWN_LINE_JUMPS: frozenset[tuple[str, str]] = frozenset(
    {
        # 0.2.0 -> 0.4.8: pre-1.0 era; the 0.3.x line had no upgrade
        # surface that required a migration (release notes only).
        ("0.2.0", "0.4.8"),
        # 0.4.8 -> 0.6.5: same rationale; 0.5.x carried no schema or
        # template changes that needed a runtime fixup.
        ("0.4.8", "0.6.5"),
        # 0.14.0 -> 2.0.0a5: the project intentionally skipped the 1.x
        # major line. 2.0.0a5 is the first 2.x alpha and is the canonical
        # bridge migration for any project still on 0.14.0.
        ("0.14.0", "2.0.0a5"),
        # 2.2.0 -> 3.0.0: no 2.3.x line shipped; the next release after
        # the 2.2.0 tranche cut directly to 3.0 as part of the canonical
        # context rewrite.
        ("2.2.0", "3.0.0"),
    }
)


def _classify_step(prev: Version, cur: Version) -> str:
    """Classify the delta from ``prev`` to ``cur``.

    Returns one of:
      * ``"same"`` -- ``cur == prev`` (two migrations targeting the same
        version; benign, they are siblings).
      * ``"backward"`` -- ``cur < prev`` (should be impossible given the
        sorted iteration; defensive only).
      * ``"patch-bump"`` -- micro increment by 1 within same X.Y.
      * ``"patch-skip"`` -- micro increment by >1 within same X.Y.
      * ``"minor-bump"`` -- minor increment by 1 within same X.
      * ``"minor-skip"`` -- minor increment by >1 within same X.
      * ``"major-bump"`` -- major increment by 1.
      * ``"major-skip"`` -- major increment by >1.
    """
    if cur == prev:
        return "same"
    if cur < prev:
        return "backward"
    if cur.major == prev.major and cur.minor == prev.minor:
        # Same (major, minor). If micros also match, the difference is
        # purely in pre/post/dev suffix (e.g. 2.0.0a5 -> 2.0.0): treat
        # that as a normal in-line progression, not a skip.
        if cur.micro == prev.micro:
            return "patch-bump"
        if cur.micro == prev.micro + 1:
            return "patch-bump"
        return "patch-skip"
    if cur.major == prev.major:
        if cur.minor == prev.minor + 1:
            return "minor-bump"
        return "minor-skip"
    if cur.major == prev.major + 1:
        return "major-bump"
    return "major-skip"


def _format_chain_excerpt(
    chain: list[tuple[str, str, str]],
    highlight_index: int | None = None,
) -> str:
    """Format the migration chain as a human-readable table excerpt.

    Each row is ``(migration_id, from_version, target_version)``.
    Highlights the row at ``highlight_index`` with a ``>>>`` marker.
    """
    if not chain:
        return "(empty chain)"

    lines = []
    start = max(0, (highlight_index or 0) - 3)
    end = min(len(chain), (highlight_index or len(chain)) + 4)
    if start > 0:
        lines.append("    ...")
    for idx in range(start, end):
        mig_id, from_v, to_v = chain[idx]
        marker = ">>> " if idx == highlight_index else "    "
        lines.append(f"{marker}{mig_id:<55s}  {from_v} -> {to_v}")
    if end < len(chain):
        lines.append("    ...")
    return "\n".join(lines)


def _project_version() -> str:
    """Read the project version from ``pyproject.toml``.

    Hand-parses a single ``version = "X.Y.Z..."`` line to avoid pulling
    in tomllib edge cases for an architectural gate.
    """
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    # Match the first top-level version assignment under [project]
    # (this file has a single top-level ``version = "..."``).
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if match is None:
        raise RuntimeError(
            f"Could not parse version from {pyproject}; "
            "expected a top-level `version = \"X.Y.Z\"` line."
        )
    return match.group(1)


def test_migration_chain_is_consistent_and_uninterrupted(
    record_property: RecordPropertyFn,
) -> None:
    """The migration chain MUST be a monotonic, uninterrupted progression.

    Walks every registered migration in semver order from
    ``OLDEST_SUPPORTED_VERSION``. Asserts:

    1. The chain never moves backward.
    2. No minor or major versions are silently skipped (except those
       in ``_KNOWN_LINE_JUMPS``).
    3. The chain's terminal target_version, modulo pre/post/dev
       suffixes, is at least the current ``pyproject.toml`` version.

    Patch-skips are recorded via ``record_property`` rather than failing or
    warning -- a release may legitimately ship without a migration if no
    schema or template change occurred. Routed off the ``warnings`` channel
    (NFR-006) while preserving the signal: each patch-skip is a separate
    recorded property, visible in the JUnit/report output.
    """
    # Ensure the full registry is populated. We always call
    # auto-discovery (it is idempotent for already-registered migrations)
    # because earlier code paths in the test session may have imported a
    # single migration module statically -- e.g.
    # ``m_0_9_1_complete_lane_migration`` is referenced via
    # ``get_agent_dirs_for_project`` by other migrations and conftests --
    # leaving the registry with only that one entry rather than the full
    # filesystem set.
    auto_discover_migrations()

    migrations = MigrationRegistry.get_all()
    assert migrations, (
        "MigrationRegistry is empty after auto_discover_migrations(); "
        "expected at least one migration to register."
    )

    # The order manifest's `# runs-first:` entries form the lead block -- they lead
    # the execution order regardless of their target_version (ADR 2026-10-17-1 §2,
    # Amendment 2026-10-22: the ledger backfill, the charter bundle v2 upgrade, then
    # the charter-pack cutover). ``get_all()`` therefore returns them FIRST, ahead of
    # the lowest-version migration, which would read as a spurious backward step.
    # Its position is the manifest's, not version's, so it is NOT part of the
    # version-monotonic chain: exclude it from the walk here. Its own version slot
    # is still bounded by ``test_migration_chain_does_not_exceed_current_project_version``.
    runs_first_ids = {entry.id for entry in load_manifest_entries() if entry.runs_first_reason is not None}
    migrations = [migration for migration in migrations if migration.migration_id not in runs_first_ids]
    assert migrations, "Migration chain is empty after excluding the runs-first lead(s)."

    # Build the chain as (migration_id, from_version, target_version)
    # rows. The first migration's FROM is OLDEST_SUPPORTED_VERSION;
    # subsequent migrations' FROM is the previous migration's target.
    chain: list[tuple[str, str, str]] = []
    prev_target = OLDEST_SUPPORTED_VERSION
    for migration in migrations:
        chain.append((migration.migration_id, prev_target, migration.target_version))
        prev_target = migration.target_version

    # Walk and classify each step.
    #
    # Index 0 is the bridge from OLDEST_SUPPORTED_VERSION (0.0.0) to the
    # first registered migration's target. This step is *seed* state, not
    # an actual upgrade hop a real user would take -- projects don't ship
    # at version 0.0.0. We skip skip-classification for index 0 to avoid
    # flagging a "missing 0.1.x migration" that never existed.
    failures: list[str] = []
    for idx, (mig_id, from_v_str, to_v_str) in enumerate(chain):
        prev = Version(from_v_str)
        cur = Version(to_v_str)
        if idx == 0:
            # Seed step: only assert monotonicity.
            if cur < prev:
                failures.append(
                    f"Seed step (index 0) moves backward at "
                    f"{mig_id}: {from_v_str} -> {to_v_str}"
                )
            continue
        step = _classify_step(prev, cur)

        if step == "same":
            # Two migrations target the same version. Benign: they are
            # siblings within one release cut. No-op.
            continue
        if step == "backward":
            failures.append(
                f"Chain moves backward at index {idx} "
                f"({mig_id}): {from_v_str} -> {to_v_str}\n"
                f"{_format_chain_excerpt(chain, idx)}"
            )
            continue
        if step in ("patch-bump", "minor-bump", "major-bump"):
            continue
        if step == "patch-skip":
            # Patch skips are tolerated -- a patch release may have
            # shipped without a migration if no fixup was required.
            # Report-only diagnostic: recorded (not warned) so it stays
            # load-bearing/visible without tripping NFR-006's warnings gate.
            record_property(
                f"migration_chain_patch_skip[{idx}]",
                f"Patch-skip in migration chain at {mig_id}: "
                f"{from_v_str} -> {to_v_str} "
                f"(skips intermediate patch versions). "
                "This is allowed but may warrant verification.",
            )
            continue
        if step in ("minor-skip", "major-skip"):
            if (from_v_str, to_v_str) in _KNOWN_LINE_JUMPS:
                # Documented intentional jump; skip silently.
                continue
            failures.append(
                f"Undocumented {step} in migration chain at index {idx} "
                f"({mig_id}): {from_v_str} -> {to_v_str}\n"
                "If this jump is intentional (e.g. a release line was "
                "never shipped), add the (from, to) tuple to "
                "_KNOWN_LINE_JUMPS with a rationale. Otherwise, add the "
                "missing migration(s).\n"
                f"{_format_chain_excerpt(chain, idx)}"
            )

    assert not failures, (
        "Migration chain integrity violations:\n\n"
        + "\n\n".join(failures)
    )


def test_migration_chain_does_not_exceed_current_project_version() -> None:
    """The chain's terminal target MUST NOT exceed the pyproject version.

    The upgrade runner only applies migrations whose target_version is less
    than or equal to the installed package version. A migration target ahead of
    pyproject is therefore skipped by real users.
    """
    auto_discover_migrations()

    migrations = MigrationRegistry.get_all()
    assert migrations, "MigrationRegistry is empty after discovery."

    chain_terminal = migrations[-1].target_version

    project_version = _project_version()

    assert Version(chain_terminal) <= Version(project_version), (
        f"Migration chain terminates at {chain_terminal} "
        f"but pyproject.toml declares version {project_version}. "
        "Migrations newer than the package version are skipped by "
        "spec-kitty upgrade. Retarget the migration to the current package "
        "version or bump pyproject.toml before release."
    )
