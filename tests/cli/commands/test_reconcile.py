"""Tests for the ``spec-kitty reconcile`` CLI surface + stable library API (WP04).

Executable contract for FR-007 and NFR-002 of mission
``dossier-parity-reconciler-01KXYXVP``.

WP04 exposes the pure WP03 :class:`DossierReconciler` as:

  (a) a CLI operation — ``spec-kitty reconcile --mission <slug>`` — that exits
      ``0`` on PARITY and non-zero on DIVERGENCE, NAMING the differing
      artifact(s) in its output (FR-007), with a ``--json`` machine surface;
  (b) a stable, narrow library API — :func:`reconcile_mission_dossier` returning
      a WP03 :class:`ReconciliationResult` — that import-history (#2262) gates
      materialization on (a contract, never reconciler internals).

These tests drive the wrapper only: the hash/compare authority stays in WP01/WP03
(C-001) and is never re-implemented here. The mission dossier is seeded on disk,
a recorded snapshot is persisted, and the mission-dir read seam is monkeypatched
so the test never depends on the topology resolver.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests._perf_helpers import assert_timing_budget

pytestmark = [pytest.mark.integration]


# ── Helpers ─────────────────────────────────────────────────────────────────


def _seed_mission(feature_dir: Path, *, extra_artifacts: int = 0) -> str:
    """Create a mission dossier on disk and persist its recorded snapshot.

    Returns the mission slug (the feature-dir name). After this call, a fresh
    reconcile of ``feature_dir`` against the saved snapshot is PARITY until a
    source file is mutated.
    """
    from specify_cli.dossier.indexer import Indexer
    from specify_cli.dossier.manifest import ManifestRegistry
    from specify_cli.dossier.snapshot import compute_snapshot, save_snapshot

    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "spec.md").write_text("# Spec\n\nreconciler mission\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n\nrebuild + verify\n", encoding="utf-8")
    tasks = feature_dir / "tasks"
    tasks.mkdir(exist_ok=True)
    (tasks / "WP01.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Seed\ntask_type: implement\n---\nbody\n",
        encoding="utf-8",
    )
    for i in range(extra_artifacts):
        (feature_dir / f"note-{i:04d}.md").write_text(f"# Note {i}\n", encoding="utf-8")

    dossier = Indexer(ManifestRegistry()).index_feature(feature_dir, "software-dev")
    snapshot = compute_snapshot(dossier)
    save_snapshot(snapshot, feature_dir)
    return feature_dir.name


def _patch_feature_dir(monkeypatch: pytest.MonkeyPatch, feature_dir: Path) -> None:
    """Point the reconcile module's mission-dir read seam at ``feature_dir``."""
    import specify_cli.cli.commands.reconcile as reconcile_module

    monkeypatch.setattr(
        reconcile_module,
        "candidate_feature_dir_for_mission",
        lambda repo_root, mission_slug, **kw: feature_dir,
    )


# ── T017: stable library API contract ────────────────────────────────────────


class TestLibraryApi:
    def test_returns_reconciliation_result_on_parity(self, tmp_path, monkeypatch):
        from specify_cli.cli.commands.reconcile import reconcile_mission_dossier
        from specify_cli.dossier.reconciler import ReconciliationResult, ReconciliationStatus

        feature_dir = tmp_path / "demo-mission-01AAAA"
        slug = _seed_mission(feature_dir)
        _patch_feature_dir(monkeypatch, feature_dir)

        result = reconcile_mission_dossier(slug, repo_root=tmp_path)

        assert isinstance(result, ReconciliationResult)
        assert result.status is ReconciliationStatus.PARITY
        assert result.is_parity
        assert bool(result) is True  # fail-closed truthiness: parity-only
        assert result.differing_artifacts == ()

    def test_names_divergent_artifact_after_source_mutation(self, tmp_path, monkeypatch):
        from specify_cli.cli.commands.reconcile import reconcile_mission_dossier

        feature_dir = tmp_path / "demo-mission-01BBBB"
        slug = _seed_mission(feature_dir)
        _patch_feature_dir(monkeypatch, feature_dir)

        # Mutate source AFTER the snapshot was recorded → divergence on spec.md.
        (feature_dir / "spec.md").write_text("# Spec\n\nMUTATED\n", encoding="utf-8")

        result = reconcile_mission_dossier(slug, repo_root=tmp_path)

        assert result.is_divergence
        assert bool(result) is False
        assert "spec.md" in result.differing_paths

    def test_missing_snapshot_is_fail_closed_error(self, tmp_path, monkeypatch):
        from specify_cli.cli.commands.reconcile import reconcile_mission_dossier

        feature_dir = tmp_path / "demo-mission-01CCCC"
        feature_dir.mkdir(parents=True)
        (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
        _patch_feature_dir(monkeypatch, feature_dir)

        result = reconcile_mission_dossier("demo-mission-01CCCC", repo_root=tmp_path)

        # No recorded snapshot to verify against — never a default parity.
        assert result.is_error
        assert bool(result) is False
        assert result.error

    def test_reconcile_reports_error_on_malformed_manifest(self, tmp_path, monkeypatch):
        """WP01 (FR-016, AS5): a malformed manifest is a structured ERROR, not a crash.

        Exercises reconcile.py's own pre-existing `except Exception` at
        cli/commands/reconcile.py:151-160 ("fail-closed: any rebuild failure is
        an ERROR") — no new exception handling is added to reconcile.py itself
        (tracer-design-decisions.md Decision 3). Routes the T002 typo'd fixture
        through the real `ManifestRegistry.load_manifest()` (by monkeypatching
        `_offering_template_repository`, the same seam T002 uses) for the seeded
        mission's own mission type, so this test genuinely exercises
        `load_manifest()`'s own exception handling, not a bypass of it: pre-T006
        the typo is silently swallowed (manifest=None, PARITY); post-T006 the
        raised `ValidationError` propagates through `Indexer.index_feature()`
        (Decision 3: the indexer adds no catch of its own) up to this
        pre-existing reconcile.py wrapper.

        WP01 (#3770) relocated the `_offering_template_repository` seam from
        `specify_cli.dossier.manifest` into `charter.activation.manifest_loader`
        alongside the load+cache logic that owns it, so the monkeypatch below
        targets the new module.
        """
        import ruamel.yaml

        import charter.activation.manifest_loader as manifest_loader_module
        from charter.offering.missions.repository import ConfigResult
        from specify_cli.cli.commands.reconcile import (
            _DEFAULT_MISSION_TYPE,
            reconcile_mission_dossier,
        )
        from specify_cli.dossier.manifest import ManifestRegistry

        feature_dir = tmp_path / "demo-mission-01KKKK"
        slug = _seed_mission(feature_dir)
        _patch_feature_dir(monkeypatch, feature_dir)
        ManifestRegistry.clear_cache()

        fixture_path = Path(__file__).parent.parent.parent / "dossier" / "fixtures" / "expected_artifacts_typo.yaml"
        content = fixture_path.read_text(encoding="utf-8")
        yaml = ruamel.yaml.YAML(typ="safe")
        parsed = yaml.load(content)

        class _FakeRepository:
            def get_expected_artifacts(self, mission: str) -> ConfigResult | None:
                return ConfigResult(content=content, origin="test-fixture", parsed=parsed)

        monkeypatch.setattr(manifest_loader_module, "_offering_template_repository", lambda: _FakeRepository())

        result = reconcile_mission_dossier(slug, repo_root=tmp_path, mission_type=_DEFAULT_MISSION_TYPE)

        assert result.is_error
        assert bool(result) is False
        assert "validation error" in result.error.lower()
        # Adversarial-review MAJOR fix (#3542 x domain-exception rework): the
        # error surfaced here comes from `ManifestRegistry.load_manifest`
        # raising `ManifestSchemaError` (not a raw `pydantic.ValidationError`)
        # through `Indexer.index_feature`, caught by reconcile.py's
        # pre-existing generic `except Exception as exc: ... f"...: {exc}"`.
        # `ManifestSchemaError.__str__` names the manifest's origin
        # ("test-fixture", per the fake repository above) alongside the
        # validation detail, so an operator debugging this failure can find
        # *which* file was schema-invalid, not just that some key was wrong.
        assert "test-fixture" in result.error


# ── T015/T016: CLI exit codes + named divergence ─────────────────────────────


class TestCli:
    def _run(self, args, monkeypatch, feature_dir):
        from specify_cli import app

        _patch_feature_dir(monkeypatch, feature_dir)
        return CliRunner().invoke(app, args)

    def test_command_is_wired_into_the_app(self, tmp_path, monkeypatch):
        """Integration-wiring: ``reconcile`` is a live, callable command.

        Runs --help in an isolated filesystem so the readiness banner (emitted
        for a connected-but-logged-out teamspace, e.g. the CI checkout) doesn't
        pre-empt help rendering — this asserts wiring, not auth state.
        """
        import re

        from specify_cli import app

        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(app, ["reconcile", "--help"])
        assert result.exit_code == 0
        # Strip ANSI so the assertion survives Rich colorizing the help in CI
        # (the flag renders as `\x1b[..m--mission\x1b[0m`, breaking a raw substring).
        plain = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
        assert "--mission" in plain

    def test_exits_zero_on_parity(self, tmp_path, monkeypatch):
        feature_dir = tmp_path / "demo-mission-01DDDD"
        slug = _seed_mission(feature_dir)
        result = self._run(["reconcile", "--mission", slug], monkeypatch, feature_dir)
        assert result.exit_code == 0

    def test_nonzero_and_names_artifact_on_divergence(self, tmp_path, monkeypatch):
        feature_dir = tmp_path / "demo-mission-01EEEE"
        slug = _seed_mission(feature_dir)
        (feature_dir / "plan.md").write_text("# Plan\n\nMUTATED\n", encoding="utf-8")
        result = self._run(["reconcile", "--mission", slug], monkeypatch, feature_dir)
        assert result.exit_code == 1  # DIVERGENCE is exit 1, distinct from ERROR (2)
        assert "plan.md" in result.output  # divergence NAMES the artifact (NFR-004)

    def test_json_output_is_machine_readable(self, tmp_path, monkeypatch):
        feature_dir = tmp_path / "demo-mission-01FFFF"
        slug = _seed_mission(feature_dir)
        (feature_dir / "spec.md").write_text("# Spec\n\nMUTATED\n", encoding="utf-8")
        result = self._run(["reconcile", "--mission", slug, "--json"], monkeypatch, feature_dir)
        assert result.exit_code == 1  # DIVERGENCE is exit 1
        payload = json.loads(result.stdout)
        assert payload["status"] == "divergence"
        assert "spec.md" in [d["artifact_path"] for d in payload["differing_artifacts"]]

    def test_error_status_exits_nonzero(self, tmp_path, monkeypatch):
        feature_dir = tmp_path / "demo-mission-01GGGG"
        feature_dir.mkdir(parents=True)
        (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
        result = self._run(["reconcile", "--mission", "demo-mission-01GGGG"], monkeypatch, feature_dir)
        assert result.exit_code == 2  # ERROR (fail-closed) is exit 2, distinct from DIVERGENCE (1)

    def test_exit_code_contract_is_zero_one_two(self):
        """Pin the 0/1/2 exit-code contract so a value swap can't stay green.

        CI distinguishes "content drifted" (1) from "could not compute" (2);
        collapsing or swapping them silently breaks that signal (NFR-004 / FR-007).
        """
        from specify_cli.cli.commands.reconcile import (
            _EXIT_DIVERGENCE,
            _EXIT_ERROR,
            _EXIT_PARITY,
        )

        assert (_EXIT_PARITY, _EXIT_DIVERGENCE, _EXIT_ERROR) == (0, 1, 2)


# ── T018: NFR-002 — reconcile one mission dossier ≤ 2 s ──────────────────────


class TestNfr002:
    def test_single_mission_reconcile_reports_parity(self, tmp_path, monkeypatch):
        """Functional companion to test_single_mission_reconciles_under_two_seconds
        (split, #4015): reconciling a freshly-seeded dossier reports PARITY.
        Timing budget lives in the @performance sibling below."""
        from specify_cli.cli.commands.reconcile import reconcile_mission_dossier

        feature_dir = tmp_path / "demo-mission-01HHHH"
        slug = _seed_mission(feature_dir, extra_artifacts=50)
        _patch_feature_dir(monkeypatch, feature_dir)

        result = reconcile_mission_dossier(slug, repo_root=tmp_path)

        assert result.is_parity

    @pytest.mark.performance
    def test_single_mission_reconciles_under_two_seconds(self, tmp_path, monkeypatch):
        """NFR-002 timing budget only (split, #4015): reconciling one mission
        dossier (50 extra artifacts) completes <= 2s. Functional coverage
        moved to test_single_mission_reconcile_reports_parity, above."""
        from specify_cli.cli.commands.reconcile import reconcile_mission_dossier

        feature_dir = tmp_path / "demo-mission-01HHHH"
        slug = _seed_mission(feature_dir, extra_artifacts=50)
        _patch_feature_dir(monkeypatch, feature_dir)

        start = time.perf_counter()
        reconcile_mission_dossier(slug, repo_root=tmp_path)
        elapsed = time.perf_counter() - start

        assert_timing_budget(elapsed, 2.0, name="reconcile_single_mission")
