"""WP06 T035 — `charter synthesize` works on a fresh project (issue #839).

These integration tests lock in Spec Assumption A2: the public CLI
``spec-kitty charter synthesize`` succeeds on a fresh project (no
hand-seeded ``.kittify/charter-packs/``, no LLM-authored YAML under
``.kittify/charter/generated/``) and produces the minimal artifact set
documented in T031.
"""

from __future__ import annotations

import json
import subprocess
from contextlib import chdir
from pathlib import Path

import pytest
from typer.testing import CliRunner

from charter.activation.synthesizer.manifest import load_yaml, verify_manifest_hash
from specify_cli.cli.commands.charter import app as charter_app


pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git_init(repo: Path) -> None:
    """Initialize a minimal git repo with identity configured."""
    subprocess.run(
        ["git", "init", "--initial-branch=main"],
        cwd=repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "commit.gpgsign", "false"],
        cwd=repo, check=True, capture_output=True,
    )


def _write_minimal_interview(repo: Path) -> None:
    interview_dir = repo / ".kittify" / "charter" / "interview"
    interview_dir.mkdir(parents=True, exist_ok=True)
    (interview_dir / "answers.yaml").write_text(
        "mission: software-dev\n"
        "profile: minimal\n"
        "selected_paradigms: []\n"
        "selected_directives: []\n"
        "available_tools: []\n"
        "answers:\n"
        "  purpose: Test charter for fresh-project synthesize.\n",
        encoding="utf-8",
    )


def _run_generate(project: Path) -> None:
    """Run ``charter generate`` against the project's cwd."""
    with chdir(project):
        result = runner.invoke(
            charter_app, ["generate", "--from-interview"],
            catch_exceptions=False,
        )
    assert result.exit_code == 0, (
        f"charter generate failed: {result.stdout!r}"
    )


def _run_synthesize(project: Path, *args: str) -> object:
    """Run ``charter synthesize`` with extra args, returning the Result."""
    with chdir(project):
        return runner.invoke(
            charter_app, ["synthesize", *args],
            catch_exceptions=False,
        )


# ---------------------------------------------------------------------------
# T035a — synthesize on fresh project via public CLI succeeds
# ---------------------------------------------------------------------------


def test_synthesize_on_fresh_project_via_public_cli(tmp_path: Path) -> None:
    """Full chain on tmp_path: init -> interview -> generate -> synthesize.

    No hand seeding of ``.kittify/charter-packs/``. The public CLI surface MUST
    succeed and produce the minimal artifact set documented in T031.
    """
    _git_init(tmp_path)
    _write_minimal_interview(tmp_path)
    _run_generate(tmp_path)

    # Pre-condition: doctrine tree does NOT exist yet (no hand seeding).
    doctrine_dir = tmp_path / ".kittify" / "charter-packs"
    assert not doctrine_dir.exists(), (
        "Test pre-condition violated: .kittify/charter-packs/ already exists"
    )

    # Pre-condition: no agent-authored YAML under generated/.
    generated_dir = tmp_path / ".kittify" / "charter" / "generated"
    if generated_dir.exists():
        for sub in ("directives", "tactics", "styleguides"):
            sub_dir = generated_dir / sub
            if sub_dir.exists():
                yaml_files = list(sub_dir.glob("*.yaml"))
                assert not yaml_files, (
                    f"Test pre-condition violated: agent YAMLs in {sub_dir}"
                )

    # Public CLI: charter synthesize (default 'generated' adapter).
    result = _run_synthesize(tmp_path, "--json")
    assert result.exit_code == 0, (
        f"synthesize failed on fresh project: {result.stdout!r}"
    )

    # Minimal artifact set per T031:
    # 1. .kittify/charter-packs/ directory exists.
    assert doctrine_dir.is_dir(), (
        "FR-015: .kittify/charter-packs/ must exist after charter synthesize"
    )
    # 2. PROVENANCE.md is present (records the seed source).
    provenance = doctrine_dir / "PROVENANCE.md"
    assert provenance.is_file(), (
        f"FR-015: minimal artifact set must include PROVENANCE.md; "
        f"got contents: {list(doctrine_dir.iterdir())}"
    )

    # The JSON envelope advertises the fresh-project mode for tooling.
    # WP02 / FR-001: the FULL stdout parses as one JSON document — no
    # warning leakage prefix, no progress noise.
    payload = json.loads(result.stdout)
    assert payload.get("result") == "success"
    assert payload.get("success") is True
    assert payload.get("mode") == "fresh_project_seed"
    assert ".kittify/charter-packs/PROVENANCE.md" in payload.get("files_written", [])
    assert ".kittify/charter/synthesis-manifest.yaml" in payload.get("files_written", [])

    manifest_path = tmp_path / ".kittify" / "charter" / "synthesis-manifest.yaml"
    assert manifest_path.is_file(), (
        "fresh-project synthesize must write the built-in-only manifest "
        "that charter preflight uses as its freshness marker"
    )
    assert "built_in_only: true" in manifest_path.read_text(encoding="utf-8")

    # WP01 (synthesized-drg-stale-refresh) T006(d) — production-path pin:
    # the REAL _fresh_seed_manifest_text output (routed through
    # finalize_manifest) must load and self-verify. Without the T005
    # reroute, the raw-hashlib path desyncs the moment
    # bundle_content_hash exists as a model field (fact #15) — this
    # assertion would go RED on the un-rerouted implementation.
    loaded_manifest = load_yaml(manifest_path)
    verify_manifest_hash(loaded_manifest)  # must not raise

    # WP02 / FR-002: the four contracted envelope fields are present
    # unconditionally — even on the fresh-project seed code path
    # (data-model §E-1 / INV-E-2: empty list != absent field).
    assert "result" in payload
    assert "adapter" in payload
    assert "written_artifacts" in payload
    assert "warnings" in payload
    assert isinstance(payload["adapter"], dict)
    assert isinstance(payload["adapter"].get("id"), str)
    assert payload["adapter"]["id"], "AdapterRef.id must be non-empty"
    assert isinstance(payload["adapter"].get("version"), str)
    assert payload["adapter"]["version"], "AdapterRef.version must be non-empty"
    assert isinstance(payload["written_artifacts"], list)
    assert isinstance(payload["warnings"], list)

    # WP02 / FR-003: every ``written_artifacts[*].path`` must resolve to a
    # file the run actually wrote. The fresh-seed mode wrote PROVENANCE.md
    # so we expect at least one entry; each entry's ``path`` MUST point to
    # a real file under tmp_path.
    assert len(payload["written_artifacts"]) >= 1
    for entry in payload["written_artifacts"]:
        assert isinstance(entry, dict)
        # Required WrittenArtifact fields per data-model §E-3:
        assert "path" in entry
        assert "kind" in entry
        assert "slug" in entry
        assert "artifact_id" in entry  # may be None
        assert isinstance(entry["path"], str) and entry["path"]
        assert isinstance(entry["kind"], str) and entry["kind"]
        assert isinstance(entry["slug"], str) and entry["slug"]
        # FR-005: never the placeholder.
        assert entry["artifact_id"] != "PROJECT_000"
        # Path resolves under the test project root.
        resolved = tmp_path / entry["path"]
        assert resolved.is_file(), (
            f"FR-003: written_artifacts entry path does not resolve to "
            f"an actual file on disk: {entry['path']!r} -> {resolved}"
        )

    # FR-005: no PROJECT_000 anywhere in the JSON envelope.
    assert "PROJECT_000" not in json.dumps(payload)


# ---------------------------------------------------------------------------
# #839 follow-up: --dry-run on a fresh project is covered by the intercept
# ---------------------------------------------------------------------------


def test_synthesize_dry_run_on_fresh_project_does_not_fall_through(
    tmp_path: Path,
) -> None:
    """``--dry-run --json`` on a fresh project MUST report would-write paths
    and exit 0 without touching the filesystem. Falling through to the
    production adapter would raise ``GeneratedArtifactMissingError`` because
    no agent YAMLs exist yet — that is the bug this guard prevents.
    """
    _git_init(tmp_path)
    _write_minimal_interview(tmp_path)
    _run_generate(tmp_path)

    doctrine_dir = tmp_path / ".kittify" / "charter-packs"
    # Pre-condition: doctrine tree does NOT exist (verifying fresh state).
    assert not doctrine_dir.exists()

    result = _run_synthesize(tmp_path, "--dry-run", "--json")
    assert result.exit_code == 0, (
        f"dry-run synthesize failed on fresh project: {result.stdout!r}"
    )

    payload = json.loads(result.stdout)
    # WP02 / FR-002: dry-run carries ``result == "dry_run"`` per the
    # synthesis envelope contract (contracts/synthesis-envelope.schema.json)
    # — not "success". A pre-WP02 invariant used "success" with a separate
    # ``mode`` flag; the new contract makes ``result`` a discriminated
    # enum {success, failure, dry_run}.
    assert payload.get("result") == "dry_run"
    assert payload.get("success") is True
    assert payload.get("mode") == "fresh_project_seed_dry_run"
    assert ".kittify/charter-packs/PROVENANCE.md" in payload.get("files_planned", [])
    assert ".kittify/charter/synthesis-manifest.yaml" in payload.get("files_planned", [])

    # WP02 / FR-002 contracted-fields presence:
    assert "adapter" in payload
    assert "written_artifacts" in payload
    assert "warnings" in payload
    assert isinstance(payload["written_artifacts"], list)
    assert isinstance(payload["warnings"], list)
    # FR-005: no PROJECT_000 in any envelope value.
    assert "PROJECT_000" not in json.dumps(payload)

    # Dry-run MUST NOT write anything to disk.
    assert not doctrine_dir.exists(), (
        "dry-run on fresh project must not materialize .kittify/charter-packs/"
    )


# ---------------------------------------------------------------------------
# T035b — synthesize is idempotent (T033)
# ---------------------------------------------------------------------------


def test_synthesize_is_idempotent(tmp_path: Path) -> None:
    """Re-running ``charter synthesize`` produces bytewise-equal output."""
    _git_init(tmp_path)
    _write_minimal_interview(tmp_path)
    _run_generate(tmp_path)

    doctrine_dir = tmp_path / ".kittify" / "charter-packs"

    # First run.
    r1 = _run_synthesize(tmp_path)
    assert r1.exit_code == 0, f"first synthesize failed: {r1.stdout!r}"

    listing_1 = sorted(p.relative_to(tmp_path).as_posix() for p in doctrine_dir.rglob("*") if p.is_file())
    contents_1 = {
        rel: (doctrine_dir.parent.parent / rel).read_bytes()
        for rel in listing_1
    }

    # Second run.
    r2 = _run_synthesize(tmp_path)
    assert r2.exit_code == 0, f"second synthesize failed: {r2.stdout!r}"

    listing_2 = sorted(p.relative_to(tmp_path).as_posix() for p in doctrine_dir.rglob("*") if p.is_file())
    contents_2 = {
        rel: (doctrine_dir.parent.parent / rel).read_bytes()
        for rel in listing_2
    }

    assert listing_1 == listing_2, (
        f"file listing changed across runs: {listing_1!r} -> {listing_2!r}"
    )
    for rel in listing_1:
        assert contents_1[rel] == contents_2[rel], (
            f"file content changed across runs for {rel}"
        )


# ---------------------------------------------------------------------------
# T035c — synthesize without charter.md fails actionably
# ---------------------------------------------------------------------------


def test_synthesize_without_charter_md_fails_actionably(tmp_path: Path) -> None:
    """Pre-condition: no charter.md. Synthesize MUST fail with an actionable
    error that names the remediation (run charter generate first)."""
    _git_init(tmp_path)
    _write_minimal_interview(tmp_path)
    # NOTE: we intentionally skip `charter generate` so charter.md is absent.

    charter_md = tmp_path / ".kittify" / "charter" / "charter.md"
    assert not charter_md.exists(), "test pre-condition: charter.md must be absent"

    result = _run_synthesize(tmp_path)
    assert result.exit_code != 0, (
        f"synthesize must fail without charter.md; got exit 0. "
        f"output={result.stdout!r}"
    )
    combined = (result.stdout or "") + (getattr(result, "output", "") or "")
    lowered = combined.lower()
    # Actionable error: names the remediation.
    assert "charter" in lowered, (
        f"error must mention 'charter'. output={combined!r}"
    )
    assert (
        "generate" in lowered or "interview" in lowered
    ), (
        f"error must name a remediation step (generate or interview). "
        f"output={combined!r}"
    )


def test_synthesize_fresh_seed_unlinks_preexisting_graph(tmp_path: Path) -> None:
    """#1717 Fix A: a fresh-seed synthesize (built_in_only) must remove a stale
    project-local ``graph.yaml`` so the freshness XOR invariant holds.

    Repro of the terminal "invalid" trap: a project carries a committed
    ``.kittify/charter-packs/graph.yaml`` from a prior synthesis era, but
    ``generated/`` is now empty so synthesize takes the fresh-seed path and
    writes a ``built_in_only: true`` manifest. If it leaves graph.yaml behind,
    ``compute_freshness`` classifies the synthesized DRG as ``invalid`` with no
    working remediation.
    """
    from specify_cli.charter_runtime.freshness import compute_freshness

    _git_init(tmp_path)
    _write_minimal_interview(tmp_path)
    _run_generate(tmp_path)

    # Seed a stale project-local graph.yaml (the orphan residue).
    doctrine_dir = tmp_path / ".kittify" / "charter-packs"
    doctrine_dir.mkdir(parents=True, exist_ok=True)
    stale_graph = doctrine_dir / "graph.yaml"
    stale_graph.write_text("schema_version: '1.0'\nnodes: []\nedges: []\n", encoding="utf-8")

    result = _run_synthesize(tmp_path, "--json")
    assert result.exit_code == 0, f"synthesize failed: {result.stdout!r}"

    # The fresh-seed (built_in_only) path must have removed the stale graph.
    assert not stale_graph.exists(), (
        "fresh-seed synthesize left a stale graph.yaml, producing the "
        "built_in_only ∧ graph-present conflict (#1717)"
    )
    # And freshness must NOT be the terminal 'invalid' state.
    freshness = compute_freshness(tmp_path)
    assert freshness.synthesized_drg.state != "invalid", (
        f"synthesized_drg is {freshness.synthesized_drg.state!r}; "
        "fresh-seed must leave a consistent built_in_only state"
    )


def test_synthesize_preserves_registered_direct_project_artifacts(tmp_path: Path) -> None:
    """No generated inputs must not erase the registered direct-write corpus."""
    from charter.activation.project_registration import plan_project_registration, commit_project_registration
    from charter.activation.synthesizer.manifest import verify
    from specify_cli.charter_runtime.freshness.computer import compute_freshness
    from tests.charter.test_project_registration import author_guidance

    _git_init(tmp_path)
    _write_minimal_interview(tmp_path)
    _run_generate(tmp_path)
    assert _run_synthesize(tmp_path, "--json").exit_code == 0
    sources = author_guidance(tmp_path)
    commit_project_registration(plan_project_registration(tmp_path))
    source_bytes = {path: path.read_bytes() for path in sources.values()}
    sidecars = tmp_path / ".kittify/charter/provenance"
    provenance_bytes = {path: path.read_bytes() for path in sidecars.glob("*.yaml")}
    tracked = [tmp_path / ".kittify/charter/synthesis-manifest.yaml", tmp_path / ".kittify/charter-packs/graph.yaml"]
    before_dry_run = {path: path.read_bytes() for path in tracked}
    preview = _run_synthesize(tmp_path, "--dry-run", "--json")
    assert preview.exit_code == 0, preview.stdout
    assert json.loads(preview.stdout)["planned_deletes"] == []
    assert {path: path.read_bytes() for path in tracked} == before_dry_run
    result = _run_synthesize(tmp_path, "--json")
    assert result.exit_code == 0, result.stdout
    manifest = load_yaml(tmp_path / ".kittify/charter/synthesis-manifest.yaml")
    assert sorted((a.kind, tmp_path / a.path) for a in manifest.artifacts) == sorted(sources.items())
    assert not manifest.built_in_only
    verify(manifest, tmp_path)
    assert (tmp_path / ".kittify/charter-packs/graph.yaml").is_file()
    assert {path: path.read_bytes() for path in source_bytes} == source_bytes
    assert {path: path.read_bytes() for path in provenance_bytes} == provenance_bytes
    assert "intentionally empty" not in (tmp_path / ".kittify/charter-packs/PROVENANCE.md").read_text()
    freshness = compute_freshness(tmp_path).synthesized_drg
    assert freshness.state == "fresh", freshness
    payload = json.loads(result.stdout)
    assert sorted((a["kind"], tmp_path / a["path"]) for a in payload["written_artifacts"]) == sorted(sources.items())
