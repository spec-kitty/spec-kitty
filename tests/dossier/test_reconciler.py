"""Acceptance + unit tests for the DossierReconciler (WP03).

Executable contract for FR-004, FR-005, FR-006, NFR-004, C-005 and acceptance
scenarios AS-2/AS-3/AS-4 of mission ``dossier-parity-reconciler-01KXYXVP``.

The reconciler is a *pure* component (no request/DB coupling). It rebuilds a
dossier projection from source, computes its canonical snapshot hash via WP01's
:func:`compute_dossier_snapshot_hash`, compares it against the recorded/emitted
projection, and returns a structured :class:`ReconciliationResult`:

    PARITY      — rebuilt hash equals recorded hash; zero differing artifacts.
    DIVERGENCE  — hashes differ; the specific differing artifact paths are NAMED
                  (NFR-004: never a bare "mismatch").
    ERROR       — any inability to compute or compare (fail-closed, C-005/FR-006):
                  never a default "parity".

AS-4 (churn immunity) is proven *through* WP01's projection input: two WPs that
differ only in runtime-mutable frontmatter project to the same content hash, so
the reconciler reports PARITY.
"""

from __future__ import annotations

import pytest

from specify_cli.dossier.hasher import (
    compute_dossier_snapshot_hash,
    hash_wp_static_projection,
)
from specify_cli.dossier.reconciler import (
    ArtifactDivergence,
    DivergenceKind,
    DossierReconciler,
    ReconciliationResult,
    ReconciliationStatus,
)
from specify_cli.status.wp_metadata import WPMetadata

# Pure-function tests (mirrors tests/dossier/test_canonical_hash.py) so the
# fast-tests-core-misc CI gate selects this module.
pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ── Fixtures / helpers ──────────────────────────────────────────────────────


def _source_projection() -> list[tuple[str, str | None]]:
    """A small, deterministic source dossier projection (path, content_hash)."""
    return [
        ("plan.md", "a" * 64),
        ("spec.md", "b" * 64),
        ("tasks/WP01.md", "c" * 64),
    ]


def _make_wp(**overrides) -> WPMetadata:
    """Build a WPMetadata with realistic static + runtime fields.

    Mirrors the fixture shape used by tests/dossier/test_canonical_hash.py so
    the churn axis is exercised the same way WP01 defined it.
    """
    data = {
        "work_package_id": "WP03",
        "title": "DossierReconciler — Rebuild and Verify",
        "dependencies": ["WP01"],
        "requirement_refs": ["FR-004", "FR-005", "FR-006"],
        "tracker_refs": ["#2180"],
        "owned_files": [
            "src/specify_cli/dossier/reconciler.py",
            "tests/dossier/test_reconciler.py",
        ],
        "phase": "Phase 2 - Reconciler",
        "task_type": "implement",
        "subtasks": ["T010", "T011", "T012", "T013", "T014"],
        # Runtime-mutable state that MUST NOT influence the content hash:
        "lane": "in_progress",
        "agent": "claude:sonnet:python-pedro:implementer",
        "shell_pid": 2839700,
        "assignee": "someone",
        "review_status": "pending",
        "history": [{"at": "2026-07-20T06:13:30Z", "actor": "system"}],
    }
    data.update(overrides)
    return WPMetadata.model_validate(data)


# ── AS-2: unchanged projection → PARITY, zero differing artifacts ────────────


class TestParity:
    def test_as2_unchanged_projection_reports_parity(self):
        source = _source_projection()
        recorded = list(source)  # byte-identical projection

        result = DossierReconciler().reconcile(source, recorded)

        assert isinstance(result, ReconciliationResult)
        assert result.status is ReconciliationStatus.PARITY
        assert result.is_parity is True
        assert result.is_divergence is False
        assert result.is_error is False
        assert result.differing_artifacts == ()
        assert result.rebuilt_hash == result.recorded_hash
        assert result.error is None

    def test_as2_parity_hash_is_the_canonical_wp01_hash(self):
        source = _source_projection()
        result = DossierReconciler().reconcile(source, list(source))
        # The reconciler MUST reuse WP01's canonical definition, not a private one.
        assert result.rebuilt_hash == compute_dossier_snapshot_hash(source)

    def test_parity_is_order_independent(self):
        source = _source_projection()
        shuffled = list(reversed(source))
        result = DossierReconciler().reconcile(source, shuffled)
        assert result.is_parity is True
        assert result.differing_artifacts == ()

    def test_empty_dossier_is_parity(self):
        result = DossierReconciler().reconcile([], [])
        assert result.is_parity is True
        assert result.differing_artifacts == ()

    def test_explicit_recorded_hash_that_matches_reports_parity(self):
        source = _source_projection()
        recorded = list(source)
        recorded_hash = compute_dossier_snapshot_hash(recorded)
        result = DossierReconciler().reconcile(source, recorded, recorded_hash=recorded_hash)
        assert result.is_parity is True


# ── AS-3: one artifact differs → DIVERGENCE naming it, fail-loud not success ─


class TestDivergence:
    def test_as3_single_differing_artifact_is_named(self):
        source = _source_projection()
        recorded = list(source)
        # Exactly one artifact's content differs.
        recorded[1] = ("spec.md", "d" * 64)

        result = DossierReconciler().reconcile(source, recorded)

        # Fail-loud: NOT success.
        assert result.is_parity is False
        assert result.status is ReconciliationStatus.DIVERGENCE
        assert result.is_divergence is True
        # NFR-004: the specific artifact is NAMED (never a bare mismatch).
        assert len(result.differing_artifacts) == 1
        div = result.differing_artifacts[0]
        assert isinstance(div, ArtifactDivergence)
        assert div.artifact_path == "spec.md"
        assert div.kind is DivergenceKind.CONTENT_MISMATCH
        assert div.source_hash == "b" * 64
        assert div.recorded_hash == "d" * 64
        # And the named path is discoverable via a convenience accessor.
        assert result.differing_paths == ("spec.md",)

    def test_artifact_present_in_source_absent_in_projection_is_named(self):
        source = _source_projection()
        recorded = [e for e in source if e[0] != "tasks/WP01.md"]

        result = DossierReconciler().reconcile(source, recorded)

        assert result.is_divergence is True
        assert result.differing_paths == ("tasks/WP01.md",)
        div = result.differing_artifacts[0]
        assert div.kind is DivergenceKind.MISSING_IN_PROJECTION
        assert div.source_hash == "c" * 64
        assert div.recorded_hash is None

    def test_artifact_present_in_projection_absent_in_source_is_named(self):
        source = _source_projection()
        recorded = list(source) + [("extra.md", "e" * 64)]

        result = DossierReconciler().reconcile(source, recorded)

        assert result.is_divergence is True
        assert result.differing_paths == ("extra.md",)
        div = result.differing_artifacts[0]
        assert div.kind is DivergenceKind.MISSING_IN_SOURCE
        assert div.source_hash is None
        assert div.recorded_hash == "e" * 64

    def test_multiple_divergences_all_named_and_sorted(self):
        source = _source_projection()
        recorded = [
            ("plan.md", "a" * 64),
            ("spec.md", "z" * 64),  # content mismatch
            ("extra.md", "e" * 64),  # missing in source
            # tasks/WP01.md dropped -> missing in projection
        ]
        result = DossierReconciler().reconcile(source, recorded)
        assert result.is_divergence is True
        # Named, and stably sorted by path.
        assert result.differing_paths == ("extra.md", "spec.md", "tasks/WP01.md")

    def test_divergence_never_reports_success_even_with_explicit_hash(self):
        source = _source_projection()
        recorded = list(source)
        recorded[0] = ("plan.md", "9" * 64)
        recorded_hash = compute_dossier_snapshot_hash(recorded)
        result = DossierReconciler().reconcile(source, recorded, recorded_hash=recorded_hash)
        assert result.is_parity is False
        assert result.is_divergence is True
        assert result.differing_paths == ("plan.md",)


# ── AS-4: churn-only change → still PARITY via WP01's projection input ────────


class TestChurnImmunity:
    def test_as4_runtime_churn_only_still_reports_parity(self):
        base = _make_wp()
        # Same authored content, only runtime-mutable fields churned.
        churned = base.update(shell_pid=999999, assignee="another", review_status="approved")

        source = [("tasks/WP03.md", hash_wp_static_projection(base))]
        recorded = [("tasks/WP03.md", hash_wp_static_projection(churned))]

        result = DossierReconciler().reconcile(source, recorded)

        assert result.is_parity is True
        assert result.differing_artifacts == ()

    def test_as4_real_content_change_does_diverge(self):
        base = _make_wp()
        edited = base.update(title="A genuinely different authored title")

        source = [("tasks/WP03.md", hash_wp_static_projection(base))]
        recorded = [("tasks/WP03.md", hash_wp_static_projection(edited))]

        result = DossierReconciler().reconcile(source, recorded)

        # Guards against over-broad churn immunity: authored change MUST diverge.
        assert result.is_divergence is True
        assert result.differing_paths == ("tasks/WP03.md",)


# ── Fail-closed enforcement (FR-006, C-005): never a default parity ──────────


class TestFailClosed:
    def test_compute_failure_surfaces_error_never_parity(self):
        def _boom(_entries):
            raise RuntimeError("hash backend unavailable")

        reconciler = DossierReconciler(hash_fn=_boom)
        result = reconciler.reconcile(_source_projection(), _source_projection())

        assert result.status is ReconciliationStatus.ERROR
        assert result.is_error is True
        assert result.is_parity is False
        assert result.is_divergence is False
        assert result.error is not None and "hash backend unavailable" in result.error
        assert result.differing_artifacts == ()

    def test_recorded_hash_inconsistent_with_recorded_projection_is_error(self):
        source = _source_projection()
        recorded = list(source)
        # The emitted/recorded hash disagrees with the recorded projection itself:
        # the record is internally inconsistent and cannot be trusted -> fail-closed.
        result = DossierReconciler().reconcile(source, recorded, recorded_hash="sha256:" + ("0" * 64))
        assert result.is_error is True
        assert result.is_parity is False
        assert result.error is not None

    def test_malformed_source_entry_is_error_never_parity(self):
        # A source entry that is neither a (path, hash) pair nor a projectable
        # object cannot be rebuilt -> explicit error, never a default parity.
        result = DossierReconciler().reconcile([object()], _source_projection())
        assert result.is_error is True
        assert result.is_parity is False
        assert result.error is not None

    def test_error_result_is_falsey_for_gating(self):
        # Consumers gate on truthiness; an error must never read as pass.
        def _boom(_entries):
            raise ValueError("nope")

        result = DossierReconciler(hash_fn=_boom).reconcile([], [])
        assert bool(result) is False
