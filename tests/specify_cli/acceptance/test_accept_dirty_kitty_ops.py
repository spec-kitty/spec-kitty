"""T001 / T003 / T004 — dirty-tree gate convergence for kitty-ops orphans (FR-001 / #2251).

A stray ``kitty-ops/<ULID>.jsonl`` Op-record orphan must NOT block any of the
four dirty-tree gates.  This module proves:

1. **RED evidence** (T001): the tests were failing on pre-fix code (see commit
   message for the captured output — the assertions below drove the fix).
2. **GREEN (post-fix)**: after T002–T004 all assertions pass.
3. **Counter-contracts**: genuine mission dirt STILL blocks all gates (NFR-003 /
   G-5 invariant).
4. **Tightness**: ``kitty-ops/notes.txt`` (non-ULID basename) is NOT excluded.

Gates covered here:
  - Accept gate:  ``acceptance._accept_dirty_gate`` (T003)
  - Merge gate:   ``merge.git_probes._classify_porcelain_lines`` (T004 arm 1)
  - Review gate:  ``review.dirty_classifier._is_benign`` / ``classify_dirty_paths``
                  (T004 arm 2)

The record-analysis gate (``mission._enforce_analysis_report_write_preflight``)
is covered by ``tests/mission_runtime/test_self_bookkeeping_allowlist.py``
(T005 / original FR-003 suite).

Contract G-5 (data-model.md): the self-bookkeeping allowlist is DISJOINT from
planning artifacts.  A stale ``spec.md`` is planning dirt and MUST still block.

See also: #2102 (original allowlist), #1914 (no-op-stable gates umbrella).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.acceptance import _ENCODING_BACKUP_SUFFIX, _accept_dirty_gate, _is_own_encoding_backup_write
from specify_cli.merge.git_probes import _classify_porcelain_lines
from specify_cli.review.dirty_classifier import _is_benign, classify_dirty_paths

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# Production-shaped 26-char Crockford base32 ULID — valid against the
# invocation-record ULID regex ``[0-9A-HJKMNP-TV-Z]{26}`` (no I, L, O, U).
_OP_ULID = "01KWD0V5ABCDEFGHJKMNPQRSTV"
_OP_JSONL = f"kitty-ops/{_OP_ULID}.jsonl"

# A real mission-relevant dirty path — must block at ALL gates (G-5 / NFR-003).
_REAL_DIRT = "src/specify_cli/acceptance/__init__.py"

# Mission slug used when calling the accept gate (minimal fixture — no dir needed).
_FEATURE = "reliability-papercut-sweep-01KWD0V5"


# ---------------------------------------------------------------------------
# Accept gate  (acceptance.__init__._accept_dirty_gate)
# ---------------------------------------------------------------------------


class TestAcceptGateKittyOps:
    """_accept_dirty_gate must exclude kitty-ops orphans, not real dirt.

    Red-first evidence: before T003 fix, ``_call_accept_gate([_OP_JSONL])``
    returned ``[' M kitty-ops/...jsonl']`` (non-empty → gate blocked).
    """

    def _call_accept_gate(
        self, tmp_path: Path, dirty_paths: list[str]
    ) -> list[str]:
        """Drive _accept_dirty_gate with fabricated porcelain lines.

        tmp_path serves as repo_root.  The mission has no meta.json, so
        topology degrades to SINGLE_BRANCH (non-coordination) — the
        coordination-residue filter is a no-op and only the shared
        is_self_bookkeeping_path arm filters the kitty-ops line.
        """
        # Porcelain v1 format: two status chars + space + path
        raw_lines = [f" M {p}" for p in dirty_paths]
        return _accept_dirty_gate(
            raw_lines,
            repo_root=tmp_path,
            feature=_FEATURE,
        )

    def test_kitty_ops_orphan_does_not_block_accept_gate(
        self, tmp_path: Path
    ) -> None:
        """Accept gate must NOT block on a kitty-ops Op-record orphan (#2251)."""
        result = self._call_accept_gate(tmp_path, [_OP_JSONL])
        assert result == [], (
            f"Accept gate must not block on kitty-ops orphan; got {result!r}"
        )

    def test_real_dirt_still_blocks_accept_gate(self, tmp_path: Path) -> None:
        """Counter-contract (G-5): genuine source dirt MUST still block."""
        result = self._call_accept_gate(tmp_path, [_REAL_DIRT])
        assert len(result) == 1, (
            f"Accept gate must still block on real dirt; result was {result!r}"
        )

    def test_non_ulid_kitty_ops_does_not_bypass_accept_gate(
        self, tmp_path: Path
    ) -> None:
        """Tightness: ``kitty-ops/notes.txt`` (non-ULID) must still block."""
        non_ulid = "kitty-ops/notes.txt"
        result = self._call_accept_gate(tmp_path, [non_ulid])
        assert len(result) == 1, (
            f"Accept gate must block on non-ULID kitty-ops path; got {result!r}"
        )


# ---------------------------------------------------------------------------
# Accept-owned-write scoping (WP17 IC-07g; review-cycle-1 BLOCKER 1 fix)
# ---------------------------------------------------------------------------


class TestAcceptGateOwnWriteScoping:
    """``_is_accept_pipeline_own_write`` must exempt ONLY its own two writes.

    Red-first regression pin for review-cycle-1 BLOCKER 1: a predicate that
    routes on the coarse ``STATUS_STATE`` kind (instead of the specific
    ``status.json`` basename) incorrectly benigns ``status.events.jsonl`` too
    — that kind also carries the append-only lane-state log
    (``mission_runtime/artifacts.py``'s ``_MISSION_FILE_KIND_BY_BASENAME``).
    The accept pipeline only READS ``status.events.jsonl``; it never appends to
    it (the writer is ``status/store.py`` via ``move-task`` / ``mark-status``),
    so a dirty one under a FLAT mission is genuine, uncommitted lane-state and
    MUST still block (C6 / C-010). Reverting the ``_is_accept_pipeline_own_write``
    fix to ``kind in (ACCEPTANCE_MATRIX, STATUS_STATE)`` reddens
    ``test_status_events_jsonl_still_blocks_accept_gate_under_flat_topology``
    below (verified red-then-green during implementation).
    """

    def _call_accept_gate(self, tmp_path: Path, dirty_paths: list[str]) -> list[str]:
        """Same fixture shape as ``TestAcceptGateKittyOps`` (flat / SINGLE_BRANCH).

        No ``meta.json`` under ``tmp_path`` → topology degrades to
        ``SINGLE_BRANCH``, so the coordination-residue filter (arm 3) is a
        no-op and only the accept-owned-write arm (arm 1) can exempt a path —
        isolating exactly the behaviour BLOCKER 1 was about.
        """
        raw_lines = [f" M {p}" for p in dirty_paths]
        return _accept_dirty_gate(
            raw_lines,
            repo_root=tmp_path,
            feature=_FEATURE,
        )

    def test_status_events_jsonl_still_blocks_accept_gate_under_flat_topology(
        self, tmp_path: Path
    ) -> None:
        """RED-FIRST: a dirty ``status.events.jsonl`` is NOT an accept own-write."""
        path = f"kitty-specs/{_FEATURE}/status.events.jsonl"
        result = self._call_accept_gate(tmp_path, [path])
        assert len(result) == 1, (
            f"Accept gate must still block a dirty status.events.jsonl under a "
            f"flat mission (it is read-only for the accept pipeline, not an "
            f"own-write); got {result!r}"
        )

    def test_status_json_is_still_accept_owned(self, tmp_path: Path) -> None:
        """Counter-contract: the daemon-materialized ``status.json`` IS an own-write."""
        path = f"kitty-specs/{_FEATURE}/status.json"
        result = self._call_accept_gate(tmp_path, [path])
        assert result == [], (
            f"status.json is an accept-pipeline own-write and must stay benign; "
            f"got {result!r}"
        )

    def test_acceptance_matrix_json_is_still_accept_owned(self, tmp_path: Path) -> None:
        """Counter-contract: ``acceptance-matrix.json`` IS an own-write."""
        path = f"kitty-specs/{_FEATURE}/acceptance-matrix.json"
        result = self._call_accept_gate(tmp_path, [path])
        assert result == [], (
            f"acceptance-matrix.json is an accept-pipeline own-write and must "
            f"stay benign; got {result!r}"
        )

    def test_unrelated_mission_status_json_still_blocks(self, tmp_path: Path) -> None:
        """Counter-contract: another mission's status.json is NOT this pipeline's write."""
        path = "kitty-specs/other-mission/status.json"
        result = self._call_accept_gate(tmp_path, [path])
        assert len(result) == 1, (
            f"Another mission's status.json must still block; got {result!r}"
        )


# ---------------------------------------------------------------------------
# Merge gate  (merge.git_probes._classify_porcelain_lines)
# ---------------------------------------------------------------------------


class TestMergeGateKittyOps:
    """_classify_porcelain_lines must exclude kitty-ops orphans, not real dirt.

    Red-first evidence: before T004 fix, ``_call_merge_gate([_OP_JSONL])``
    returned offending ``[' M kitty-ops/...jsonl']`` (non-empty → gate blocked).
    """

    def _call_merge_gate(self, dirty_paths: list[str]) -> tuple[list[str], int]:
        """Drive _classify_porcelain_lines with fabricated porcelain lines."""
        lines = [f" M {p}" for p in dirty_paths]
        return _classify_porcelain_lines(lines, expected_paths=set())

    def test_kitty_ops_orphan_does_not_block_merge_gate(self) -> None:
        """Merge gate must NOT block on a kitty-ops Op-record orphan (#2251)."""
        offending, _skipped = self._call_merge_gate([_OP_JSONL])
        assert offending == [], (
            f"Merge gate must not block on kitty-ops orphan; offending={offending!r}"
        )

    def test_real_dirt_still_blocks_merge_gate(self) -> None:
        """Counter-contract (G-5): genuine source dirt MUST still block."""
        offending, _skipped = self._call_merge_gate([_REAL_DIRT])
        assert len(offending) == 1, (
            f"Merge gate must still block on real dirt; offending={offending!r}"
        )

    def test_non_ulid_kitty_ops_does_not_bypass_merge_gate(self) -> None:
        """Tightness: ``kitty-ops/notes.txt`` (non-ULID) must still block."""
        non_ulid = "kitty-ops/notes.txt"
        offending, _skipped = self._call_merge_gate([non_ulid])
        assert len(offending) == 1, (
            f"Merge gate must block on non-ULID kitty-ops path; got {offending!r}"
        )


# ---------------------------------------------------------------------------
# Review / implement-handoff gate  (review.dirty_classifier)
# ---------------------------------------------------------------------------


class TestReviewGateKittyOps:
    """_is_benign / classify_dirty_paths must treat kitty-ops orphans as benign.

    Red-first evidence: before T004 fix, ``_is_benign(_OP_JSONL, 'WP01')``
    returned False (blocking), and classify_dirty_paths put the orphan in
    ``blocking`` not ``benign``.
    """

    _WP_ID = "WP01"

    def test_kitty_ops_orphan_is_benign(self) -> None:
        """Review gate must treat a kitty-ops Op-record orphan as benign (#2251)."""
        assert _is_benign(_OP_JSONL, self._WP_ID), (
            f"_is_benign must return True for kitty-ops orphan; path={_OP_JSONL!r}"
        )

    def test_real_dirt_is_not_benign(self) -> None:
        """Counter-contract (G-5): real source dirt is NOT benign."""
        assert not _is_benign(_REAL_DIRT, self._WP_ID), (
            f"Real dirt must not be benign; path={_REAL_DIRT!r}"
        )

    def test_classify_dirty_paths_kitty_ops_orphan_in_benign(self) -> None:
        """classify_dirty_paths must route kitty-ops orphan to benign bucket."""
        blocking, benign = classify_dirty_paths(
            [_OP_JSONL], wp_id=self._WP_ID, mission_slug=_FEATURE
        )
        assert _OP_JSONL in benign, (
            f"Kitty-ops orphan must be benign; blocking={blocking!r}, benign={benign!r}"
        )
        assert _OP_JSONL not in blocking

    def test_classify_dirty_paths_real_dirt_in_blocking(self) -> None:
        """Counter-contract: classify_dirty_paths puts real dirt in blocking."""
        blocking, benign = classify_dirty_paths(
            [_REAL_DIRT], wp_id=self._WP_ID, mission_slug=_FEATURE
        )
        assert _REAL_DIRT in blocking, (
            f"Real dirt must be blocking; blocking={blocking!r}, benign={benign!r}"
        )

    def test_non_ulid_kitty_ops_path_is_not_benign(self) -> None:
        """Tightness: kitty-ops/notes.txt (non-ULID basename) is NOT benign."""
        non_ulid = "kitty-ops/notes.txt"
        assert not _is_benign(non_ulid, self._WP_ID), (
            f"Non-ULID kitty-ops path must NOT be benign; path={non_ulid!r}"
        )


class TestEncodingBackupSelfWriteScope:
    """#5170 review NOTE (architect-alphonso): dedicated coverage for the two
    fail-closed / narrowing branches of ``_is_own_encoding_backup_write`` that
    the positive integration test only exercised implicitly."""

    _PREFIX = "kitty-specs/my-mission/"

    def test_unresolved_scope_is_never_our_own_write(self) -> None:
        """``feature_dir_prefix is None`` (the fail-closed resolution outcome of
        ``_encoding_backup_scope_prefix``) must never be treated as our own
        backup -- an unresolvable scope blocks, it does not wave the .bak through."""
        assert _is_own_encoding_backup_write(f"kitty-specs/my-mission/spec.md{_ENCODING_BACKUP_SUFFIX}", feature_dir_prefix=None) is False

    def test_out_of_mission_backup_still_blocks(self) -> None:
        """A .bak outside the CURRENT mission's feature-dir prefix (another
        mission, or a sibling-slug prefix collision) is NOT our own write and
        must still block; the in-mission .bak is the positive control, and an
        in-mission non-.bak is excluded by suffix."""
        # positive control: in-mission .bak IS our own write
        assert _is_own_encoding_backup_write(f"{self._PREFIX}spec.md{_ENCODING_BACKUP_SUFFIX}", feature_dir_prefix=self._PREFIX) is True
        # another mission's .bak -> blocks
        assert _is_own_encoding_backup_write(f"kitty-specs/other-mission/spec.md{_ENCODING_BACKUP_SUFFIX}", feature_dir_prefix=self._PREFIX) is False
        # sibling-slug prefix collision (trailing slash guards it) -> blocks
        assert _is_own_encoding_backup_write(f"kitty-specs/my-mission-2/spec.md{_ENCODING_BACKUP_SUFFIX}", feature_dir_prefix=self._PREFIX) is False
        # in-mission but not a .bak -> excluded by suffix
        assert _is_own_encoding_backup_write(f"{self._PREFIX}spec.md", feature_dir_prefix=self._PREFIX) is False
