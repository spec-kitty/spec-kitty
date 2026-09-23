"""WP05 / FR-003 (#2102): the record-analysis self-bookkeeping allowlist.

spec-kitty's own bookkeeping files (``meta.json`` and the encoding-provenance
``.kittify/encoding-provenance/global.jsonl``) classify ``kind=None`` against the
mission-artifact partition, so before this WP the record-analysis dirty-tree
preflight (:func:`_enforce_analysis_report_write_preflight`) treated their churn as
"real dirt" and **falsely blocked** the write. FR-003 adds a *self-bookkeeping
allowlist*, kept **DISJOINT** from the coord-residue partition.

The invariant under test (contract G-5, debbie's hazard): the allowlist contains
ONLY spec-kitty's own metadata. A stale **primary** ``spec.md`` is a PRIMARY-partition
planning artifact — it is **NOT** allowlisted and remains "real dirt" that still blocks.
Conflating the two sets is the failure mode this suite pins.

Both arms drive the REAL preflight entry point (``_enforce_analysis_report_write_preflight``)
on a real git repo with production-shaped fixtures (26-char ULID ``mission_id``).

lifecycle-gate-execution-context-01KY72GQ WP11 (IC-07a): the standalone
``mission_runtime.artifacts.is_self_bookkeeping_path`` mechanism this suite pinned is
retired onto the canonical churn owner's self-bookkeeping leg
(:func:`specify_cli.coordination.coherence.is_self_bookkeeping_churn`) — the pure-
predicate arm below now asserts on that owner/classifier behaviour instead of the
retired mechanism (T062); the real-preflight arm was already behaviour-level and is
unchanged.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import typer

from specify_cli.coordination.coherence import is_self_bookkeeping_churn
from specify_cli.cli.commands.agent.mission import (
    _enforce_analysis_report_write_preflight,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# Production-shaped identity (real 26-char ULID mission_id, 8-char mid8).
_MISSION_ID = "01KVW9B0SELFBOOKKEEPINGTST"  # 26 chars
_MID8 = "01KVW9B0"  # first 8 chars
_MISSION_SLUG = f"gate-read-surface-completion-{_MID8}"


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo_root, check=True, capture_output=True)


def _init_repo(tmp_path: Path) -> Path:
    repo_root = tmp_path
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "test@example.com")
    _git(repo_root, "config", "user.name", "Test")
    return repo_root


def _seed_committed_mission(repo_root: Path) -> Path:
    """Create + commit a production-shaped mission so the tree starts clean."""
    feature_dir = repo_root / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    meta = (
        "{\n"
        f'  "created_at": "2026-06-24T00:00:00+00:00",\n'
        f'  "friendly_name": "Gate Read Surface Completion",\n'
        f'  "mid8": "{_MID8}",\n'
        f'  "mission_id": "{_MISSION_ID}",\n'
        f'  "mission_slug": "{_MISSION_SLUG}",\n'
        f'  "mission_type": "software-dev",\n'
        f'  "slug": "{_MISSION_SLUG}",\n'
        f'  "target_branch": "feat/gate-read-surface-completion"\n'
        "}\n"
    )
    (feature_dir / "meta.json").write_text(meta, encoding="utf-8")
    (feature_dir / "spec.md").write_text("# Spec\n\nFR-003.\n", encoding="utf-8")
    provenance = repo_root / ".kittify" / "encoding-provenance"
    provenance.mkdir(parents=True)
    (provenance / "global.jsonl").write_text(
        '{"path": "kitty-specs/x/spec.md", "encoding": "utf-8"}\n', encoding="utf-8"
    )
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", "seed mission")
    return feature_dir


# ---------------------------------------------------------------------------
# Pure predicate (the allowlist authority) — disjoint-set contract.
# ---------------------------------------------------------------------------


class TestSelfBookkeepingPredicate:
    def test_meta_json_is_self_bookkeeping(self) -> None:
        assert is_self_bookkeeping_churn(f"kitty-specs/{_MISSION_SLUG}/meta.json")

    def test_provenance_jsonl_is_self_bookkeeping(self) -> None:
        assert is_self_bookkeeping_churn(".kittify/encoding-provenance/global.jsonl")

    def test_primary_spec_is_not_self_bookkeeping(self) -> None:
        # G-5 invariant: a stale primary spec.md is planning dirt, NOT bookkeeping.
        assert not is_self_bookkeeping_churn(f"kitty-specs/{_MISSION_SLUG}/spec.md")

    def test_unrelated_global_jsonl_is_not_over_allowlisted(self) -> None:
        # Suffix match is anchored on the provenance path, so a bare global.jsonl
        # elsewhere must NOT be over-allowlisted.
        assert not is_self_bookkeeping_churn("some/other/dir/global.jsonl")

    # ------------------------------------------------------------------
    # FR-001 / #2251 — kitty-ops Op-record arm
    # ------------------------------------------------------------------

    def test_kitty_ops_ulid_jsonl_is_self_bookkeeping(self) -> None:
        """A ``kitty-ops/<26-char-ULID>.jsonl`` Op-record is bookkeeping (#2251)."""
        # Production-shaped: 26-char Crockford base32 ULID, no I/L/O/U.
        assert is_self_bookkeeping_churn("kitty-ops/01KWD0V5ABCDEFGHJKMNPQRSTV.jsonl")

    def test_kitty_ops_ulid_jsonl_with_leading_prefix_is_self_bookkeeping(
        self,
    ) -> None:
        """Repo-relative prefix before ``kitty-ops/`` is handled (path component)."""
        assert is_self_bookkeeping_churn(
            "some/prefix/kitty-ops/01KWD0V5ABCDEFGHJKMNPQRSTV.jsonl"
        )

    def test_kitty_ops_non_ulid_basename_is_not_self_bookkeeping(self) -> None:
        """G-5: ``kitty-ops/notes.txt`` (non-ULID) is NOT self-bookkeeping."""
        assert not is_self_bookkeeping_churn("kitty-ops/notes.txt")

    def test_kitty_ops_ops_index_is_not_self_bookkeeping(self) -> None:
        """G-5: ``kitty-ops/ops-index.jsonl`` is NOT a ULID Op-record — must block."""
        assert not is_self_bookkeeping_churn("kitty-ops/ops-index.jsonl")

    def test_kitty_ops_short_ulid_is_not_self_bookkeeping(self) -> None:
        """G-5: a filename shorter than 26 chars + .jsonl is NOT matched."""
        # 8-char mid8 only — too short.
        assert not is_self_bookkeeping_churn("kitty-ops/01KWD0V5.jsonl")

    def test_kitty_ops_long_ulid_is_not_self_bookkeeping(self) -> None:
        """G-5: a filename longer than 26 chars + .jsonl is NOT matched."""
        # 27 chars.
        assert not is_self_bookkeeping_churn("kitty-ops/01KWD0V5ABCDEFGHJKMNPQRSTVX.jsonl")

    # ------------------------------------------------------------------
    # #4928 — mission-state repair audit trail arm
    # ------------------------------------------------------------------

    def test_audit_manifest_is_self_bookkeeping(self) -> None:
        """#4928: a tracked repair manifest under .kittify/mission-state-audit/
        is spec-kitty's own bookkeeping — a --fix before accept must not gate."""
        assert is_self_bookkeeping_churn(
            ".kittify/mission-state-audit/01M37PWGWRFNZY8X2Y7P7KJJGK.json"
        )

    def test_audit_quarantine_is_self_bookkeeping(self) -> None:
        """#4928: the quarantine subtree is likewise self-bookkeeping churn."""
        assert is_self_bookkeeping_churn(
            ".kittify/mission-state-audit/quarantine/RUNID/042-slug/status.events.jsonl"
        )

    def test_audit_root_with_leading_prefix_is_self_bookkeeping(self) -> None:
        """A repo-relative prefix before .kittify/mission-state-audit/ is handled."""
        assert is_self_bookkeeping_churn(
            "some/prefix/.kittify/mission-state-audit/01M37PWG.json"
        )

    def test_legacy_migrations_path_is_not_over_allowlisted(self) -> None:
        """The matcher is scoped to mission-state-audit/, NOT the legacy
        .kittify/migrations/ tree — a stray file there must not be whitelisted."""
        assert not is_self_bookkeeping_churn(
            ".kittify/migrations/mission-state/legacy.json"
        )

    def test_unrelated_kittify_path_is_not_over_allowlisted(self) -> None:
        """A sibling .kittify/ path must NOT be swept in by the audit matcher."""
        assert not is_self_bookkeeping_churn(".kittify/mission-state-audit-notes.txt")


# ---------------------------------------------------------------------------
# The real dirty-tree preflight — FR-003 false-block fix + G-5 invariant.
# ---------------------------------------------------------------------------


def _modify_self_bookkeeping(feature_dir: Path, repo_root: Path) -> None:
    """Make the self-bookkeeping files dirty (the false-block trigger)."""
    (feature_dir / "meta.json").write_text(
        (feature_dir / "meta.json").read_text(encoding="utf-8").replace(
            "Gate Read Surface Completion", "Gate Read Surface Completion (touched)"
        ),
        encoding="utf-8",
    )
    (repo_root / ".kittify" / "encoding-provenance" / "global.jsonl").write_text(
        '{"path": "kitty-specs/x/spec.md", "encoding": "utf-8"}\n'
        '{"path": "kitty-specs/y/plan.md", "encoding": "utf-8"}\n',
        encoding="utf-8",
    )


def test_preflight_does_not_block_on_self_bookkeeping_churn(tmp_path: Path) -> None:
    """FR-003: dirty meta.json + provenance jsonl no longer falsely block.

    The allowlist is consulted regardless of topology (these are spec-kitty's own
    metadata, not coord residue) — so the preflight returns cleanly.
    """
    repo_root = _init_repo(tmp_path)
    feature_dir = _seed_committed_mission(repo_root)
    _modify_self_bookkeeping(feature_dir, repo_root)

    # No exception => preflight passed (self-bookkeeping churn is allowlisted).
    _enforce_analysis_report_write_preflight(
        repo_root,
        json_output=True,
        placement_ref=None,
        mission_slug=_MISSION_SLUG,
    )


def test_preflight_still_blocks_on_stale_primary_spec(tmp_path: Path) -> None:
    """G-5 invariant: a stale primary spec.md is real dirt and STILL blocks.

    The allowlist is DISJOINT from planning artifacts — spec.md is never allowlisted.
    """
    repo_root = _init_repo(tmp_path)
    feature_dir = _seed_committed_mission(repo_root)
    # Self-bookkeeping churn is allowlisted, but the stale primary spec.md is NOT.
    _modify_self_bookkeeping(feature_dir, repo_root)
    (feature_dir / "spec.md").write_text("# Spec\n\nFR-003 EDITED.\n", encoding="utf-8")

    with pytest.raises(typer.Exit):
        _enforce_analysis_report_write_preflight(
            repo_root,
            json_output=True,
            placement_ref=None,
            mission_slug=_MISSION_SLUG,
        )
