"""Acceptance + unit tests for the one-time snapshot-hash re-baseline (WP05).

Covers FR-009 (recompute recorded snapshot hashes under the canonical
definition so unchanged content is not flagged divergent after the WP02
cutover) and NFR-003 (zero false-divergence across the local backlog).

Key invariants exercised:

- After re-baseline, a reconcile of *unchanged* content reads as PARITY
  (the recorded hash equals a freshly recomputed canonical snapshot hash).
- Content that *genuinely* changed after re-baseline still DIVERGES.
- The re-baseline is idempotent (safe to re-run) and read-only over source
  artifacts (respects the no-dirty-tree invariant #2263).

See: kitty-specs/dossier-parity-reconciler-01KXYXVP/spec.md (FR-009, NFR-003,
A-003) and tasks/WP05-rebaseline-migration.md (T019-T021).

``TestRebaselineOrgAwareness`` below covers a SEPARATE, later mission
(``cascade-org-inert-01M07E9P``, FR-003, WP01): making rebaseline consult a
configured org pack's ``expected-artifacts.yaml`` override by deriving
``repo_root`` per-snapshot inside ``rebaseline_snapshot_file``, instead of the
permanent ``Indexer(ManifestRegistry())`` (``repo_root=None``) that predates
it. See ``kitty-specs/cascade-org-inert-01M07E9P/spec.md`` (FR-003) and
``tasks/WP01-rebaseline-org-awareness.md``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from specify_cli.dossier.indexer import Indexer
from specify_cli.dossier.manifest import ManifestRegistry
from specify_cli.dossier.snapshot import compute_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ── helpers ─────────────────────────────────────────────────────────────────


def _reconcile_parity_hash(feature_dir: Path, mission_type: str = "software-dev") -> str:
    """Freshly index + snapshot a feature dir; return its canonical parity hash.

    This is the exact pipeline the live drift/reconcile path uses
    (``Indexer.index_feature`` → ``compute_snapshot``), so equality with a
    recorded hash means a reconcile would read PARITY.
    """
    dossier = Indexer(ManifestRegistry()).index_feature(feature_dir, mission_type)
    return compute_snapshot(dossier).parity_hash_sha256


def _write_source_mission(feature_dir: Path) -> None:
    """Create a representative mission source tree (spec/plan/WP artifacts)."""
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "spec.md").write_text("# Spec\n\nRequirements here.\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n\nImplementation plan.\n", encoding="utf-8")
    tasks = feature_dir / "tasks"
    tasks.mkdir(exist_ok=True)
    # A WP file with runtime-mutable frontmatter — WP01 hashes its static
    # projection, so raw-byte churn in lane/agent/history must not move the hash.
    (tasks / "WP01-first.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: First work package\n"
        "dependencies: []\n"
        "subtasks:\n"
        "- T001\n"
        "lane: in_progress\n"
        "agent: claude\n"
        "shell_pid: '12345'\n"
        "---\n\n# WP01\n\nDo the first thing.\n",
        encoding="utf-8",
    )


def _record_old_form_snapshot(feature_dir: Path, mission_slug: str) -> Path:
    """Write a recorded snapshot in the retired bare-hex (pre-WP02) form.

    Models a snapshot persisted under the OLD concat-of-hashes formula: the
    per-artifact content hashes are joined and SHA256'd, yielding a *bare*
    64-hex digest (no ``sha256:`` prefix).
    """
    dossier = Indexer(ManifestRegistry()).index_feature(feature_dir, "software-dev")
    snapshot = compute_snapshot(dossier)
    data = snapshot.model_dump(mode="json")

    # Old formula: sha256 over the concatenation of the sorted component hashes.
    components = sorted(data.get("parity_hash_components", []))
    # noqa: TID251 — deliberately reproduces the RETIRED pre-WP02 concat/bare-hex
    # formula to model a legacy recorded snapshot; not the canonical hash.
    old_digest = hashlib.sha256("".join(components).encode("utf-8")).hexdigest()  # noqa: TID251
    assert not old_digest.startswith("sha256:")
    data["parity_hash_sha256"] = old_digest

    dossier_dir = feature_dir / ".kittify" / "dossiers" / mission_slug
    dossier_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = dossier_dir / "snapshot-latest.json"
    snapshot_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return snapshot_path


def _recorded_hash(snapshot_path: Path) -> str:
    return json.loads(snapshot_path.read_text(encoding="utf-8"))["parity_hash_sha256"]


# ── T019: acceptance — parity after re-baseline, divergence on real change ────


class TestRebaselineParity:
    def test_recompute_yields_canonical_prefixed_hash(self, tmp_path: Path) -> None:
        """Re-baseline rewrites a bare-hex recorded hash to the canonical form."""
        from specify_cli.dossier.rebaseline import rebaseline_snapshot_file

        feature_dir = tmp_path / "042-example-mission"
        _write_source_mission(feature_dir)
        snapshot_path = _record_old_form_snapshot(feature_dir, "042-example-mission")

        old_hash = _recorded_hash(snapshot_path)
        assert not old_hash.startswith("sha256:")  # precondition: OLD form

        outcome = rebaseline_snapshot_file(snapshot_path)

        assert outcome.changed is True
        assert outcome.old_hash == old_hash
        assert outcome.new_hash.startswith("sha256:")
        # Persisted to disk.
        assert _recorded_hash(snapshot_path) == outcome.new_hash

    def test_unchanged_content_reconciles_as_parity(self, tmp_path: Path) -> None:
        """NFR-003: after re-baseline, unchanged content shows zero divergence."""
        from specify_cli.dossier.rebaseline import rebaseline_snapshot_file

        feature_dir = tmp_path / "042-example-mission"
        _write_source_mission(feature_dir)
        snapshot_path = _record_old_form_snapshot(feature_dir, "042-example-mission")

        rebaseline_snapshot_file(snapshot_path)

        # A reconcile of the UNCHANGED source must equal the recorded hash.
        recorded = _recorded_hash(snapshot_path)
        reconciled = _reconcile_parity_hash(feature_dir)
        assert reconciled == recorded, "unchanged content must read as PARITY"

    def test_genuine_change_still_diverges(self, tmp_path: Path) -> None:
        """Content that genuinely changed after re-baseline must still diverge."""
        from specify_cli.dossier.rebaseline import rebaseline_snapshot_file

        feature_dir = tmp_path / "042-example-mission"
        _write_source_mission(feature_dir)
        snapshot_path = _record_old_form_snapshot(feature_dir, "042-example-mission")

        rebaseline_snapshot_file(snapshot_path)
        recorded = _recorded_hash(snapshot_path)

        # Mutate a source artifact — a real content change.
        (feature_dir / "spec.md").write_text("# Spec\n\nDIFFERENT requirements.\n", encoding="utf-8")

        reconciled = _reconcile_parity_hash(feature_dir)
        assert reconciled != recorded, "genuine content change must DIVERGE"

    def test_wp_runtime_churn_does_not_diverge(self, tmp_path: Path) -> None:
        """Runtime-mutable WP frontmatter churn must NOT read as divergence.

        This is why the re-baseline recomputes from source under the canonical
        (WP01 projection) definition rather than transforming recorded raw-byte
        component hashes.
        """
        from specify_cli.dossier.rebaseline import rebaseline_snapshot_file

        feature_dir = tmp_path / "042-example-mission"
        _write_source_mission(feature_dir)
        snapshot_path = _record_old_form_snapshot(feature_dir, "042-example-mission")

        rebaseline_snapshot_file(snapshot_path)
        recorded = _recorded_hash(snapshot_path)

        # Churn only runtime-mutable frontmatter (lane/agent/shell_pid/history).
        wp = feature_dir / "tasks" / "WP01-first.md"
        wp.write_text(
            "---\n"
            "work_package_id: WP01\n"
            "title: First work package\n"
            "dependencies: []\n"
            "subtasks:\n"
            "- T001\n"
            "lane: done\n"
            "agent: codex\n"
            "shell_pid: '99999'\n"
            "history:\n"
            "- at: '2026-07-20T00:00:00Z'\n"
            "  actor: system\n"
            "  action: churn\n"
            "---\n\n# WP01\n\nDo the first thing.\n",
            encoding="utf-8",
        )

        reconciled = _reconcile_parity_hash(feature_dir)
        assert reconciled == recorded, "runtime-state churn must not read as divergence"


# ── T020: idempotency + read-only-over-source ─────────────────────────────────


class TestRebaselineIdempotentAndReadOnly:
    def test_idempotent_second_run_is_noop(self, tmp_path: Path) -> None:
        from specify_cli.dossier.rebaseline import rebaseline_snapshot_file

        feature_dir = tmp_path / "042-example-mission"
        _write_source_mission(feature_dir)
        snapshot_path = _record_old_form_snapshot(feature_dir, "042-example-mission")

        first = rebaseline_snapshot_file(snapshot_path)
        assert first.changed is True

        second = rebaseline_snapshot_file(snapshot_path)
        assert second.changed is False, "already-canonical snapshot must be a no-op"
        assert second.old_hash == second.new_hash == first.new_hash
        assert _recorded_hash(snapshot_path) == first.new_hash

    def test_already_canonical_is_left_untouched(self, tmp_path: Path) -> None:
        from specify_cli.dossier.rebaseline import rebaseline_snapshot_file

        feature_dir = tmp_path / "042-example-mission"
        _write_source_mission(feature_dir)
        snapshot_path = _record_old_form_snapshot(feature_dir, "042-example-mission")
        rebaseline_snapshot_file(snapshot_path)

        before = snapshot_path.read_text(encoding="utf-8")
        outcome = rebaseline_snapshot_file(snapshot_path)
        after = snapshot_path.read_text(encoding="utf-8")

        assert outcome.changed is False
        assert before == after, "canonical snapshot must not be rewritten"

    def test_source_artifacts_are_not_mutated(self, tmp_path: Path) -> None:
        """#2263: the re-baseline must be read-only over source artifacts."""
        from specify_cli.dossier.rebaseline import rebaseline_snapshot_file

        feature_dir = tmp_path / "042-example-mission"
        _write_source_mission(feature_dir)
        snapshot_path = _record_old_form_snapshot(feature_dir, "042-example-mission")

        source_files = sorted(p for p in feature_dir.rglob("*") if p.is_file() and ".kittify" not in p.parts)
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}  # noqa: TID251 — file-integrity check, not the dossier hash

        rebaseline_snapshot_file(snapshot_path)

        after = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files}  # noqa: TID251 — file-integrity check, not the dossier hash
        assert before == after, "source artifacts must be untouched"

    def test_dry_run_does_not_write(self, tmp_path: Path) -> None:
        from specify_cli.dossier.rebaseline import rebaseline_snapshot_file

        feature_dir = tmp_path / "042-example-mission"
        _write_source_mission(feature_dir)
        snapshot_path = _record_old_form_snapshot(feature_dir, "042-example-mission")
        before = snapshot_path.read_text(encoding="utf-8")

        outcome = rebaseline_snapshot_file(snapshot_path, dry_run=True)

        assert outcome.changed is True  # it WOULD change
        assert outcome.new_hash.startswith("sha256:")
        assert snapshot_path.read_text(encoding="utf-8") == before, "dry-run must not write"


# ── T021: verify across a representative backlog slice (NFR-003) ──────────────


class TestRebaselineBacklog:
    def test_discovers_recorded_snapshots(self, tmp_path: Path) -> None:
        from specify_cli.dossier.rebaseline import iter_recorded_snapshot_files

        slugs = ["062-alpha", "063-beta", "064-gamma"]
        for slug in slugs:
            feature_dir = tmp_path / slug
            _write_source_mission(feature_dir)
            _record_old_form_snapshot(feature_dir, slug)

        found = list(iter_recorded_snapshot_files(tmp_path))
        assert len(found) == len(slugs)
        assert all(p.name == "snapshot-latest.json" for p in found)

    def test_backlog_zero_false_divergence(self, tmp_path: Path) -> None:
        """NFR-003: across a representative backlog, unchanged content is PARITY."""
        from specify_cli.dossier.rebaseline import rebaseline_recorded_snapshots

        slugs = ["062-alpha", "063-beta", "064-gamma", "065-delta"]
        feature_dirs = {}
        for slug in slugs:
            feature_dir = tmp_path / slug
            _write_source_mission(feature_dir)
            _record_old_form_snapshot(feature_dir, slug)
            feature_dirs[slug] = feature_dir

        outcomes = rebaseline_recorded_snapshots(tmp_path)

        assert len(outcomes) == len(slugs)
        assert all(o.changed for o in outcomes)
        assert all(o.error is None for o in outcomes)

        # Zero false-divergence: every mission reconciles as PARITY unchanged.
        divergent = []
        for o in outcomes:
            reconciled = _reconcile_parity_hash(feature_dirs[o.mission_slug])
            if reconciled != o.new_hash:
                divergent.append(o.mission_slug)
        assert divergent == [], f"false-divergence on: {divergent}"

    def test_backlog_dry_run_reports_without_writing(self, tmp_path: Path) -> None:
        from specify_cli.dossier.rebaseline import rebaseline_recorded_snapshots

        slug = "062-alpha"
        feature_dir = tmp_path / slug
        _write_source_mission(feature_dir)
        snapshot_path = _record_old_form_snapshot(feature_dir, slug)
        before = snapshot_path.read_text(encoding="utf-8")

        outcomes = rebaseline_recorded_snapshots(tmp_path, dry_run=True)

        assert len(outcomes) == 1
        assert outcomes[0].changed is True
        assert snapshot_path.read_text(encoding="utf-8") == before


# ── Fail-closed error branches (each returns error + changed=False, no write) ─


class TestRebaselineErrorBranches:
    """Every rebaseline failure is captured (error set, changed=False) and never
    rewrites the recorded snapshot — the sweep must not abort or silently pass.
    """

    def test_unreadable_snapshot_is_error_and_left_untouched(self, tmp_path: Path) -> None:
        from specify_cli.dossier.rebaseline import rebaseline_snapshot_file

        dossier_dir = tmp_path / "042-broken" / ".kittify" / "dossiers" / "042-broken"
        dossier_dir.mkdir(parents=True)
        snapshot_path = dossier_dir / "snapshot-latest.json"
        snapshot_path.write_text("{ this is not valid json", encoding="utf-8")
        before = snapshot_path.read_text(encoding="utf-8")

        outcome = rebaseline_snapshot_file(snapshot_path)

        assert outcome.error == "unreadable_snapshot"
        assert outcome.changed is False
        assert snapshot_path.read_text(encoding="utf-8") == before  # not rewritten

    def test_source_missing_is_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import specify_cli.dossier.rebaseline as rb
        from specify_cli.dossier.rebaseline import rebaseline_snapshot_file

        feature_dir = tmp_path / "042-example-mission"
        _write_source_mission(feature_dir)
        snapshot_path = _record_old_form_snapshot(feature_dir, "042-example-mission")
        before = snapshot_path.read_text(encoding="utf-8")

        # Simulate the source tree having vanished between discovery and re-index.
        monkeypatch.setattr(rb, "_resolve_feature_dir", lambda _p: tmp_path / "gone")

        outcome = rebaseline_snapshot_file(snapshot_path)

        assert outcome.error == "source_missing"
        assert outcome.changed is False
        assert snapshot_path.read_text(encoding="utf-8") == before  # not rewritten

    def test_reindex_failure_is_error_and_does_not_write(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import specify_cli.dossier.rebaseline as rb
        from specify_cli.dossier.rebaseline import rebaseline_snapshot_file

        feature_dir = tmp_path / "042-example-mission"
        _write_source_mission(feature_dir)
        snapshot_path = _record_old_form_snapshot(feature_dir, "042-example-mission")
        before = snapshot_path.read_text(encoding="utf-8")

        def _boom(_dossier):
            raise RuntimeError("indexer exploded")

        monkeypatch.setattr(rb, "compute_snapshot", _boom)

        outcome = rebaseline_snapshot_file(snapshot_path)

        assert outcome.error is not None
        assert outcome.error.startswith("reindex_failed")
        assert outcome.changed is False
        assert snapshot_path.read_text(encoding="utf-8") == before  # not rewritten

    def test_rebaseline_skips_one_mission_on_malformed_manifest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """WP01 (FR-016, AS5): one bad mission must not abort the backlog sweep.

        Exercises rebaseline.py's own pre-existing `except Exception` at
        dossier/rebaseline.py:168-170 ("one bad mission must not abort the
        backlog sweep") — no new exception handling is added to rebaseline.py
        itself (tracer-design-decisions.md Decision 3). One of two missions in
        the sweep resolves to a malformed manifest (routed through the real
        `ManifestRegistry.load_manifest()` via the T002 typo'd fixture, same
        `_doctrine_repository` seam); pre-T006/T007 the typo is silently
        swallowed (manifest=None) and both missions rebaseline cleanly;
        post-T006 the raised `ValidationError` propagates through
        `Indexer.index_feature()` for the bad mission only, captured here as a
        per-mission `error="reindex_failed: ..."` while the other mission's
        outcome is unaffected (sweep continues).

        WP01 (#3770) relocated the `_doctrine_repository` seam from
        `specify_cli.dossier.manifest` into `charter.activation.manifest_loader`
        alongside the load+cache logic that owns it, so the monkeypatch below
        targets the new module.
        """
        import ruamel.yaml

        import charter.activation.manifest_loader as manifest_loader_module
        import specify_cli.mission as mission_module
        from charter.offering.missions.repository import ConfigResult
        from specify_cli.dossier.manifest import ManifestRegistry
        from specify_cli.dossier.rebaseline import rebaseline_recorded_snapshots

        good_slug = "062-alpha-good"
        bad_slug = "062-beta-bad"
        good_dir = tmp_path / good_slug
        bad_dir = tmp_path / bad_slug
        _write_source_mission(good_dir)
        _write_source_mission(bad_dir)
        _record_old_form_snapshot(good_dir, good_slug)
        _record_old_form_snapshot(bad_dir, bad_slug)
        ManifestRegistry.clear_cache()

        fixture_path = Path(__file__).parent / "fixtures" / "expected_artifacts_typo.yaml"
        content = fixture_path.read_text(encoding="utf-8")
        yaml = ruamel.yaml.YAML(typ="safe")
        parsed = yaml.load(content)
        real_repository = manifest_loader_module._doctrine_repository()

        class _FakeRepository:
            def get_expected_artifacts(self, mission: str) -> ConfigResult | None:
                if mission == "typo-fixture":
                    return ConfigResult(content=content, origin="test-fixture", parsed=parsed)
                return real_repository.get_expected_artifacts(mission)

        monkeypatch.setattr(manifest_loader_module, "_doctrine_repository", lambda: _FakeRepository())

        def _fake_mission_type(feature_dir: Path) -> str:
            return "typo-fixture" if feature_dir.name == bad_slug else "software-dev"

        monkeypatch.setattr(mission_module, "get_mission_type", _fake_mission_type)

        outcomes = rebaseline_recorded_snapshots(tmp_path)

        assert len(outcomes) == 2
        by_slug = {o.mission_slug: o for o in outcomes}

        bad_outcome = by_slug[bad_slug]
        assert bad_outcome.error is not None
        assert bad_outcome.error.startswith("reindex_failed")
        assert bad_outcome.changed is False

        good_outcome = by_slug[good_slug]
        assert good_outcome.error is None  # sweep continued past the bad mission


# ── FR-003 (cascade-org-inert-01M07E9P, WP01): org-awareness ──────────────────
#
# T001 investigation finding (see rebaseline.py's ``_derive_repo_root``
# docstring for the full evidence trail): every production writer of a
# recorded dossier snapshot resolves ``feature_dir``/``repo_root`` through
# ``locate_project_root()`` (or the placement seam's PRIMARY-partition
# ``TASKS_INDEX`` kind) -- both fold worktree paths back to the MAIN/primary
# checkout. ``.kittify/dossiers/`` is also gitignored, so a worktree checkout
# never inherits one via git either. Outcome (a): worktrees never carry their
# own dossier snapshots, so derivation (B) -- ``repo_root =
# feature_dir.parent.parent``, per-snapshot -- is correct as specced, with a
# fail-safe fallback (``repo_root=None``) when the fixed
# ``<repo_root>/kitty-specs/<slug>/...`` layout is not recognized.


def _write_org_pack_config(repo_root: Path, *, packs: list[tuple[str, Path]]) -> None:
    """Write ``<repo_root>/.kittify/config.yaml`` with a ``doctrine.org.packs``
    registry -- mirrors ``tests/dossier/test_manifest.py``'s helper of the
    same name/shape (duplicated locally to keep this owned test file
    self-contained rather than cross-importing another test module's
    private helper).
    """
    config_dir = repo_root / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    lines: list[str] = ["doctrine:", "  org:", "    packs:"]
    for name, local_path in packs:
        lines.append(f"      - name: {name}")
        lines.append(f"        local_path: {local_path}")
    (config_dir / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_org_manifest(org_root: Path, mission_type: str, data: dict) -> None:
    """Write ``<org_root>/missions/<mission_type>/expected-artifacts.yaml`` (raw-root shape)."""
    target_dir = org_root / "missions" / mission_type
    target_dir.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    yaml.default_flow_style = False
    with (target_dir / "expected-artifacts.yaml").open("w") as fh:
        yaml.dump(data, fh)


_ORG_REQUIRED_KEY = "policy.org-required"


def _org_manifest_data(manifest_version: str) -> dict:
    """An org-tier manifest declaring one extra required artifact absent from
    every fixture mission tree built by ``_write_source_mission`` -- so its
    presence as a "ghost" (``is_present=False``) entry in the rebaselined
    snapshot's ``artifact_summaries`` is a direct, non-inert proof that
    ``load_manifest`` actually consulted the org pack (not merely that a
    ``repo_root`` parameter is now threaded through unused).
    """
    return {
        "schema_version": "1.0",
        "mission_type": "software-dev",
        "manifest_version": manifest_version,
        "required_always": [
            {
                "artifact_key": _ORG_REQUIRED_KEY,
                "artifact_class": "policy",
                "path_pattern": "org-policy.md",
                "blocking": True,
            }
        ],
    }


def _snapshot_artifact_keys(snapshot_path: Path) -> set[str]:
    data = json.loads(snapshot_path.read_text(encoding="utf-8"))
    return {a["artifact_key"] for a in data["artifact_summaries"]}


class TestRebaselineOrgAwareness:
    """FR-003: `rebaseline_snapshot_file` derives `repo_root` per-snapshot and
    threads it into `Indexer`, so a configured org pack is consulted instead
    of silently falling back to built-in-only (the pre-fix, permanently
    `repo_root=None` behavior).
    """

    def setup_method(self):
        ManifestRegistry.clear_cache()

    def teardown_method(self):
        ManifestRegistry.clear_cache()

    def test_indexer_receives_repo_root_matching_project_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SC-005 / AC1 / T004: red-first — `Indexer` must receive a non-`None`
        `repo_root` matching the real project root after
        `rebaseline_snapshot_file` runs.

        RED on this WP's starting commit: `Indexer(ManifestRegistry())` is
        called with no `repo_root` kwarg at all, so the spy captures `[None]`
        and this assertion fails. GREEN once `repo_root` is threaded.
        """
        import specify_cli.dossier.rebaseline as rb
        from specify_cli.dossier.rebaseline import rebaseline_snapshot_file

        real_indexer_cls = rb.Indexer

        project_root = tmp_path / "project"
        slug = "042-example-mission"
        feature_dir = project_root / "kitty-specs" / slug
        _write_source_mission(feature_dir)
        snapshot_path = _record_old_form_snapshot(feature_dir, slug)

        captured_repo_roots: list[Path | None] = []

        class _SpyIndexer(real_indexer_cls):  # type: ignore[misc, valid-type]
            def __init__(self, manifest_registry, repo_root=None):  # noqa: ANN001
                captured_repo_roots.append(repo_root)
                super().__init__(manifest_registry, repo_root=repo_root)

        monkeypatch.setattr(rb, "Indexer", _SpyIndexer)

        rebaseline_snapshot_file(snapshot_path)

        assert captured_repo_roots == [project_root], (
            f"Indexer must receive repo_root={project_root!r}, got {captured_repo_roots!r}"
        )

    def test_org_pack_required_artifact_reaches_rebaselined_snapshot(
        self, tmp_path: Path
    ) -> None:
        """AC1 / T004 non-inert proof: a healthy org pack's extra required
        artifact must surface as a missing ("ghost") entry in the rebaselined
        snapshot's `artifact_summaries` — proving the org pack was actually
        *consulted* (`load_manifest` reached the override), not merely that a
        `repo_root` parameter is now silently passed through unused.
        """
        from specify_cli.dossier.rebaseline import rebaseline_snapshot_file

        project_root = tmp_path / "project"
        slug = "042-example-mission"
        feature_dir = project_root / "kitty-specs" / slug
        _write_source_mission(feature_dir)
        snapshot_path = _record_old_form_snapshot(feature_dir, slug)

        org_root = tmp_path / "org-pack"
        _write_org_manifest(org_root, "software-dev", _org_manifest_data("org-1"))
        _write_org_pack_config(project_root, packs=[("acme", org_root)])

        rebaseline_snapshot_file(snapshot_path)

        assert _ORG_REQUIRED_KEY in _snapshot_artifact_keys(snapshot_path), (
            "org-pack-required artifact must appear in the rebaselined snapshot "
            "— the org pack was not consulted"
        )

    def test_no_org_pack_configured_matches_org_blind_behavior(
        self, tmp_path: Path
    ) -> None:
        """FR-003 AC2 (revert-discipline companion): with `repo_root` now
        threaded but NO org pack configured, rebaseline output must be
        byte-identical to the pre-fix, permanently org-blind
        (`repo_root=None`) path — a required regression check, not merely a
        nice-to-have.
        """
        from specify_cli.dossier.rebaseline import rebaseline_snapshot_file

        project_root = tmp_path / "project"
        slug = "042-example-mission"
        feature_dir = project_root / "kitty-specs" / slug
        _write_source_mission(feature_dir)
        # No `.kittify/config.yaml` at project_root at all — org-agnostic project.

        org_blind_dossier = Indexer(ManifestRegistry(), repo_root=None).index_feature(
            feature_dir, "software-dev"
        )
        org_blind_hash = compute_snapshot(org_blind_dossier).parity_hash_sha256

        snapshot_path = _record_old_form_snapshot(feature_dir, slug)
        rebaseline_snapshot_file(snapshot_path)

        assert _recorded_hash(snapshot_path) == org_blind_hash, (
            "no-org-pack rebaseline must match the org-blind reindex exactly"
        )
        assert _ORG_REQUIRED_KEY not in _snapshot_artifact_keys(snapshot_path)

    def test_malformed_org_pack_does_not_abort_the_operator_command(
        self, tmp_path: Path
    ) -> None:
        """FR-003 AC4 (as widened by #3412/WP03's org-tier fail-loud fix):
        a malformed org pack must not raise an UNHANDLED exception out of
        the operator's `migrate` command — but it must no longer silently
        degrade to "no org override" either. Rebaseline's org-pack lookup
        (`ManifestRegistry.load_manifest` -> `resolve_org_expected_artifacts`
        -> `_read_yaml_mapping`) now raises `MalformedManifestError` for a
        present-but-broken file (C-006: an operator authored this override
        and expects it to take effect, so masking it behind the built-in
        manifest would hide a genuine misconfiguration). That raise is
        caught by `rebaseline_snapshot_file`'s own pre-existing
        `except Exception` (`dossier/rebaseline.py:348-350`, "one bad
        mission must not abort the backlog sweep") exactly like the
        schema-invalid sibling case in
        `test_rebaseline_skips_one_mission_on_malformed_manifest` above —
        so the command itself never crashes, but this mission's snapshot is
        now correctly reported as failed rather than silently rebaselined
        against the wrong (built-in-only) manifest.
        """
        from specify_cli.dossier.rebaseline import rebaseline_snapshot_file

        project_root = tmp_path / "project"
        slug = "042-example-mission"
        feature_dir = project_root / "kitty-specs" / slug
        _write_source_mission(feature_dir)
        snapshot_path = _record_old_form_snapshot(feature_dir, slug)
        before = snapshot_path.read_text(encoding="utf-8")

        org_root = tmp_path / "org-pack"
        # Constructed directly rather than via `_write_org_manifest` -- that
        # helper YAML-dumps a well-formed mapping, so it cannot express this
        # fixture's malformed content anyway. Pinning the corrected
        # `missions/<type>/` anchor here (mirroring the equivalent repair in
        # `tests/charter/test_org_expected_artifacts.py`, commit 0c554ca65)
        # keeps this test's fixture independent of any future retarget of
        # `_write_org_manifest`, instead of coupling to it only to be
        # stranded again the next time that helper's join changes.
        malformed_dir = org_root / "missions" / "software-dev"
        malformed_dir.mkdir(parents=True, exist_ok=True)
        # Malformed: not a YAML mapping (unbalanced flow sequence) — this
        # must not raise UNHANDLED out of `rebaseline_snapshot_file`; it
        # must be captured as a per-mission `reindex_failed` error instead.
        (malformed_dir / "expected-artifacts.yaml").write_text(
            "required_always: [this, is, not: valid\n", encoding="utf-8"
        )
        _write_org_pack_config(project_root, packs=[("acme", org_root)])

        outcome = rebaseline_snapshot_file(snapshot_path)  # must not raise

        assert outcome.error is not None
        assert outcome.error.startswith("reindex_failed")
        assert outcome.changed is False
        assert snapshot_path.read_text(encoding="utf-8") == before  # not rewritten

    def test_two_pack_chain_second_pack_reaches_rebaseline(self, tmp_path: Path) -> None:
        """FR-003 AC3 / T007: `ManifestRegistry.load_manifest` already calls
        the PLURAL `_resolve_existing_org_roots(repo_root)` once `repo_root`
        is non-`None` — confirm this delivers pack-2 content once this WP's
        fix threads `repo_root` in, i.e. multi-pack chain support for
        rebaseline is inherited for free rather than needing separate
        implementation. Pack 1 declares no override for this mission type at
        all (a real chain, not a single-pack disguise); pack 2 (later in
        declaration order) is the one that actually supplies the override.
        """
        from specify_cli.dossier.rebaseline import rebaseline_snapshot_file

        project_root = tmp_path / "project"
        slug = "042-example-mission"
        feature_dir = project_root / "kitty-specs" / slug
        _write_source_mission(feature_dir)
        snapshot_path = _record_old_form_snapshot(feature_dir, slug)

        org_root_1 = tmp_path / "org-pack-1"
        org_root_1.mkdir(parents=True, exist_ok=True)  # exists, no override for software-dev
        org_root_2 = tmp_path / "org-pack-2"
        _write_org_manifest(org_root_2, "software-dev", _org_manifest_data("org-2"))
        _write_org_pack_config(
            project_root, packs=[("pack-one", org_root_1), ("pack-two", org_root_2)]
        )

        rebaseline_snapshot_file(snapshot_path)

        assert _ORG_REQUIRED_KEY in _snapshot_artifact_keys(snapshot_path), (
            "second (pack-2) org root in the chain must be reached, proving "
            "the full chain is walked, not just the first configured org root"
        )

    def test_unrecognized_layout_does_not_derive_bogus_repo_root(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Negative case: a snapshot NOT nested under the fixed
        `<repo_root>/kitty-specs/<slug>/...` layout must fail SAFE
        (`repo_root=None`, today's org-blind behavior) rather than deriving a
        bogus `repo_root` two parents up. A wrong `repo_root` is worse than
        none — it would read a *different* project's org config.

        The two-hops-up ancestor deliberately DOES have an org pack
        configured, to prove it is never consulted: a naive
        `feature_dir.parent.parent` derivation with no layout check would
        silently read this unrelated config.
        """
        import specify_cli.dossier.rebaseline as rb
        from specify_cli.dossier.rebaseline import rebaseline_snapshot_file

        real_indexer_cls = rb.Indexer

        # Legacy/unrecognized layout: feature_dir is NOT under a `kitty-specs`
        # parent (mirrors this file's own pre-existing `tmp_path / slug`
        # fixture convention used throughout the rest of this test module).
        # Nested one level under `tmp_path` (rather than placing feature_dir
        # directly in `tmp_path`) so "two hops up" below lands on `tmp_path`
        # itself — this test's own isolated directory — never on the
        # pytest-xdist worker basetemp that is a *parent* of every sibling
        # test's `tmp_path` (that leak caused four `agent_context_resolve-*`
        # nodes in an unrelated module to fail when their own Tier-3
        # `.kittify` walk-up hit this stray config; see #160).
        feature_dir = tmp_path / "nested" / "042-example-mission"
        _write_source_mission(feature_dir)
        snapshot_path = _record_old_form_snapshot(feature_dir, "042-example-mission")

        # An org pack IS configured two hops up from feature_dir — the naive
        # derivation's landing spot — but must never be reached.
        org_root = tmp_path / "org-pack"
        _write_org_manifest(org_root, "software-dev", _org_manifest_data("wrong-project-org"))
        _write_org_pack_config(tmp_path, packs=[("acme", org_root)])

        captured_repo_roots: list[Path | None] = []

        class _SpyIndexer(real_indexer_cls):  # type: ignore[misc, valid-type]
            def __init__(self, manifest_registry, repo_root=None):  # noqa: ANN001
                captured_repo_roots.append(repo_root)
                super().__init__(manifest_registry, repo_root=repo_root)

        monkeypatch.setattr(rb, "Indexer", _SpyIndexer)

        rebaseline_snapshot_file(snapshot_path)

        assert captured_repo_roots == [None], (
            f"unrecognized layout must fail safe to repo_root=None, got {captured_repo_roots!r}"
        )
        assert _ORG_REQUIRED_KEY not in _snapshot_artifact_keys(snapshot_path), (
            "the wrong-project org pack must never be consulted"
        )
