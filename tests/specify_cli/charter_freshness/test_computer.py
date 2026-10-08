"""Unit tests for ``specify_cli.charter_runtime.freshness.computer``
(WP02 / FR-005, FR-009; re-pointed at ``charter.yaml`` by
consolidate-charter-bundle WP06 / FR-003, FR-011, NFR-001, NFR-002).

Covers each documented sub-state:

* ``fresh`` — ``charter.yaml`` exists and parses (``charter_source`` /
  ``synced_bundle``); the synthesis manifest's stored ``bundle_content_hash``
  matches a fresh recompute (``synthesized_drg``).
* ``stale`` — ``synthesized_drg`` only: the stored hash diverges from a
  fresh recompute, or the upstream ``synced_bundle`` is not itself fresh.
  ``charter_source`` NEVER returns ``stale`` post-Landmine-2 (the
  ``charter.md``-hash staleness mechanism is retired outright — see
  ``computer.py``'s module docstring).
* ``missing`` — when the synthesized DRG file is absent and the manifest
  does not opt into ``built_in_only=true`` (or ``charter.yaml`` itself is
  absent, for ``charter_source``/``synced_bundle``).
* ``built_in_only`` — when the manifest declares ``built_in_only: true``.
  A residual ``graph.yaml`` the manifest disowns is *stale graph residue*
  (FR-006 / C2-f): still ``built_in_only`` + a non-blocking diagnostic, never
  the formerly-terminal ``invalid`` state.
* ``invalid`` — a genuine inconsistency from ``_compute_charter_source``:
  ``charter.yaml`` exists but cannot be parsed. (No ``synthesized_drg``
  producer returns ``invalid`` after FR-006.)
"""

from __future__ import annotations

import os
from kernel.clock import now_epoch
from pathlib import Path
from textwrap import dedent

import pytest

from specify_cli.charter_runtime.freshness import (
    CharterFreshness,
    FreshnessSubState,
    compute_freshness,
)
from charter.bundle import BUNDLE_CONTENT_HASH_FILES, compute_bundle_content_hash
from charter.activation.synthesizer import (
    FixtureAdapter,
    SynthesisRequest,
    SynthesisTarget,
    synthesize,
)
from charter.activation.synthesizer.resynthesize_pipeline import run as resynthesize_run


pytestmark = [pytest.mark.fast]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_CHARTER_YAML_BODY = (
    "schema_version: '2.0.0'\n"
    "governance: {}\n"
    "directives:\n"
    "  directives: []\n"
    "catalog:\n"
    "  mission: test-mission\n"
    "  template_set: default\n"
    "  languages: []\n"
    "  references: []\n"
    "metadata:\n"
    "  generated_at: '2026-01-01T00:00:00+00:00'\n"
    "  bundle_schema_version: 2\n"
)


def _seed_charter_yaml(repo: Path, body: str = _CHARTER_YAML_BODY) -> Path:
    """Write ``.kittify/charter/charter.yaml`` and return its path."""
    charter_dir = repo / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    charter_path = charter_dir / "charter.yaml"
    charter_path.write_text(body, encoding="utf-8")
    return charter_path


def _seed_manifest(
    repo: Path,
    *,
    built_in_only: bool,
    created_at: str = "2099-01-01T00:00:00+00:00",
    bundle_content_hash: str | None = None,
) -> Path:
    manifest_path = repo / ".kittify" / "charter" / "synthesis-manifest.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    hash_line = (
        f"bundle_content_hash: {bundle_content_hash}\n"
        if bundle_content_hash is not None
        else "bundle_content_hash: null\n"
    )
    manifest_path.write_text(
        dedent(
            f"""\
            schema_version: '2'
            mission_id: null
            created_at: '{created_at}'
            run_id: 01JTESTRUNIDXXXXXXXXXXXXXX
            adapter_id: test
            adapter_version: '0.0.0'
            synthesizer_version: '0.0.0'
            manifest_hash: {"a" * 64}
            artifacts: []
            built_in_only: {str(built_in_only).lower()}
            """
        )
        + hash_line,
        encoding="utf-8",
    )
    return manifest_path


def _seed_fresh_bundle_and_manifest(repo: Path) -> Path:
    """Seed ``charter.yaml`` + a manifest whose ``bundle_content_hash``
    genuinely matches a fresh recompute of it."""
    charter_path = _seed_charter_yaml(repo)
    real_hash = compute_bundle_content_hash(repo)
    assert real_hash is not None
    _seed_manifest(repo, built_in_only=False, bundle_content_hash=real_hash)
    return charter_path


def _seed_graph(repo: Path) -> Path:
    graph_path = repo / ".kittify" / "charter-packs" / "graph.yaml"
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.write_text("schema_version: '1.0'\nnodes: []\nedges: []\n", encoding="utf-8")
    return graph_path


def _bump_bundle_mtimes_to_future(repo: Path, *, offset_seconds: float = 100.0) -> None:
    """Simulate a git checkout/rebase/clone/machine-migration bumping bundle
    mtimes into the future with NO content change — the exact #2681 symptom.
    A deterministic future offset (rather than relying on real elapsed
    wall-clock time between calls) keeps the reproduction stable regardless
    of how fast the test machine runs."""
    bump = now_epoch() + offset_seconds
    for name in BUNDLE_CONTENT_HASH_FILES:
        os.utime(repo / ".kittify" / "charter" / name, (bump, bump))


# ---------------------------------------------------------------------------
# Real synthesize/resynthesize pipeline fixtures (AS-5 / SC-003 e2e proofs)
#
# ``synthesize()``/``resynthesize`` do not themselves write
# ``.kittify/charter/charter.yaml`` (that is authored / ``charter sync``'s
# output), so tests that need a real ``bundle_content_hash`` must seed it
# directly. These fixtures duplicate (rather than import) the pattern used
# by ``tests/charter/synthesizer/test_orchestrator_resynthesize.py`` — a
# sibling WP06-owned file does not import from another owned-elsewhere WP.
# ---------------------------------------------------------------------------


_SYNTH_FIXTURE_ROOT = Path(__file__).resolve().parent.parent.parent / "charter" / "fixtures" / "synthesizer"


def _seed_pipeline_bundle_files(repo: Path) -> None:
    """Seed ``charter.yaml`` ahead of a real pipeline run."""
    _seed_charter_yaml(repo)


def _synth_adapter() -> FixtureAdapter:
    return FixtureAdapter(fixture_root=_SYNTH_FIXTURE_ROOT)


def _base_synthesis_request(run_id: str) -> SynthesisRequest:
    target = SynthesisTarget(
        kind="directive",
        slug="mission-type-scope-directive",
        title="Mission Type Scope Directive",
        artifact_id="PROJECT_001",
        source_section="mission_type",
    )
    return SynthesisRequest(
        target=target,
        interview_snapshot={
            "mission_type": "software_dev",
            "language_scope": ["python"],
            "testing_philosophy": "test-driven development with high coverage",
            "neutrality_posture": "balanced",
            "selected_directives": ["DIRECTIVE_003"],
            "risk_appetite": "moderate",
        },
        doctrine_snapshot={
            "directives": {
                "DIRECTIVE_003": {
                    "id": "DIRECTIVE_003",
                    "title": "Decision Documentation",
                    "body": "Document significant architectural decisions via ADRs.",
                }
            },
            "tactics": {},
            "styleguides": {},
        },
        drg_snapshot={
            "nodes": [
                {"urn": "directive:DIRECTIVE_003", "kind": "directive"},
            ],
            "edges": [],
            "schema_version": "1",
        },
        run_id=run_id,
        adapter_hints={"language": "python"},
    )


# ---------------------------------------------------------------------------
# Fresh / stale / missing / built_in_only / invalid cases
# ---------------------------------------------------------------------------


def test_bundle_file_lists_stay_in_sync() -> None:
    """The reader's ``_BUNDLE_FILES`` must equal the canonical bundle hash set.

    ``charter.bundle.BUNDLE_CONTENT_HASH_FILES`` (the content-identity input
    set, drives the ``synthesized_drg`` hash) and
    ``computer._BUNDLE_FILES`` (drives ``synced_bundle`` existence + mtime) are
    deliberately duplicated tuples in different modules to keep the
    ``charter``→``specify_cli`` dependency direction intact (data-model
    Decision 5). This pins them equal so a future edit to one that silently
    drifts from the other — which would let the two freshness sub-states track
    different file sets — is caught, honoring the single-canonical-authority
    principle without inverting the import direction.
    """
    from specify_cli.charter_runtime.freshness.computer import _BUNDLE_FILES

    assert tuple(_BUNDLE_FILES) == tuple(BUNDLE_CONTENT_HASH_FILES)
    assert tuple(_BUNDLE_FILES) == ("charter.yaml",)


def test_legacy_bundle_file_lists_stay_in_sync() -> None:
    """The reader's ``_LEGACY_BUNDLE_FILENAMES`` must equal the canonical
    migration-owned constant.

    WP05 (review-cycle-1.md Issue 2) mirrors — deliberately does NOT
    import — ``m_unify_charter_activation_finalize.LEGACY_BUNDLE_FILENAMES``:
    importing that migration module pulls the ``MigrationRegistry`` onto
    this module's hot import path (NFR-003), the same cost
    ``test_bundle_file_lists_stay_in_sync`` above avoids for
    ``_BUNDLE_FILES``/``BUNDLE_CONTENT_HASH_FILES``. This test imports the
    canonical constant here — in the test file only, never in
    ``computer.py`` — so the two four-file lists cannot silently drift
    apart (e.g. a fifth legacy file discovered, or a rename) without a loud
    failure, following the exact precedent set by the ``_BUNDLE_FILES`` pin.
    """
    from specify_cli.charter_runtime.freshness.computer import _LEGACY_BUNDLE_FILENAMES
    from specify_cli.upgrade.migrations.m_unify_charter_activation_finalize import (
        LEGACY_BUNDLE_FILENAMES,
    )

    assert set(_LEGACY_BUNDLE_FILENAMES) == set(LEGACY_BUNDLE_FILENAMES)
    assert set(_LEGACY_BUNDLE_FILENAMES) == {
        "governance.yaml",
        "directives.yaml",
        "metadata.yaml",
        "references.yaml",
    }


def test_returns_three_sub_objects(tmp_path: Path) -> None:
    """The result always exposes all three layers."""
    result = compute_freshness(tmp_path)
    assert isinstance(result, CharterFreshness)
    for sub in (result.charter_source, result.synced_bundle, result.synthesized_drg):
        assert isinstance(sub, FreshnessSubState)
        assert sub.state in {"fresh", "stale", "missing", "built_in_only", "invalid"}


def test_charter_source_missing_when_charter_yaml_absent(tmp_path: Path) -> None:
    result = compute_freshness(tmp_path)
    assert result.charter_source.state == "missing"
    # WP02 (#2831 P0): `charter sync` never writes (src/charter/sync.py:18) so
    # it could never clear this state. `charter generate --no-from-interview`
    # is proven effective (missing -> fresh) against a realistic legacy-bundle
    # fixture — see contracts/remediation-effectiveness.md C-EFF-1/C-EFF-7 and
    # tests/architectural/test_remediation_effectiveness.py.
    assert result.charter_source.remediation == "spec-kitty charter generate --no-from-interview"
    # charter-preflight-remediation WP05 (FR-005, out-of-map edit to this
    # WP02 file — narrow, consequence-of-computer.py-change only): F1 ("no
    # charter at all") must be distinguishable from F2 (legacy bundle
    # present, no charter.yaml) even though both report state="missing".
    assert result.charter_source.detail == (
        "no charter.yaml and no legacy charter bundle files; this project "
        "has no charter at all"
    )
    assert result.synced_bundle.detail == result.charter_source.detail


def test_charter_source_missing_reads_as_legacy_bundle_present_for_f2(
    tmp_path: Path,
) -> None:
    """FR-005 / WP05: a legacy-bundle project (governance.yaml /
    directives.yaml / metadata.yaml / references.yaml present, no
    charter.yaml — F2) still reports state="missing" (unchanged, WP05 does
    not add a new state value), but its ``detail`` must read differently
    from F1's — the operator has a charter, just not in the required form.
    """
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    for name in ("governance.yaml", "directives.yaml", "metadata.yaml", "references.yaml"):
        (charter_dir / name).write_text("schema_version: '1'\n", encoding="utf-8")

    result = compute_freshness(tmp_path)

    assert result.charter_source.state == "missing"
    assert result.charter_source.detail is not None
    assert "no charter at all" not in result.charter_source.detail
    assert "legacy charter bundle" in result.charter_source.detail
    assert result.charter_source.detail == (
        "no charter.yaml, but legacy charter bundle files "
        "(governance.yaml/directives.yaml/metadata.yaml/references.yaml) "
        "are present; this project has a charter, just not in the "
        "required form"
    )
    # synced_bundle mirrors charter_source's F1/F2 answer rather than
    # recomputing it (both inspect the same charter.yaml absence).
    assert result.synced_bundle.detail == result.charter_source.detail


def test_charter_source_missing_detail_names_charter_md_for_the_2831_shape(
    tmp_path: Path,
) -> None:
    """#2831's ACTUAL reported shape: ``charter.md`` present, nothing else.

    The issue reads *"despite it existing at .kittify/charter/charter.md"*, and
    its central complaint is that every diagnostic reported healthy while the
    gate refused. Before this, that operator got the F1 text — "this project has
    no charter at all" — because ``charter.md`` was absent from
    ``_LEGACY_BUNDLE_FILENAMES``, so the most common legacy shape of all was
    misclassified as *no charter*.

    Pinned as its own case rather than folded into the four-file F2 test: those
    fixtures seed only the ``.yaml`` files, so they stayed green throughout and
    could never have caught this. The gate's *verdict* is deliberately unchanged
    — still ``missing``, still remediable by ``charter generate`` — because
    charter.yaml remains the required form. Only the sentence changes, from a
    false one to a true one.
    """
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "charter.md").write_text("# Project Charter\n", encoding="utf-8")

    result = compute_freshness(tmp_path)

    assert result.charter_source.state == "missing"
    detail = result.charter_source.detail
    assert detail is not None
    assert "no charter at all" not in detail, (
        "charter.md is present — telling the operator they have no charter is the "
        "diagnostic-vs-reality contradiction #2831 reported"
    )
    assert detail == (
        "no charter.yaml, but a legacy charter bundle file (charter.md) "
        "is present; this project has a charter, just not in the "
        "required form"
    )
    # The exit stays open: naming the shape correctly must not cost the operator
    # the remediation that provably clears it.
    assert result.charter_source.remediation == "spec-kitty charter generate --no-from-interview"
    assert result.synced_bundle.detail == detail


def test_charter_source_missing_detail_true_for_single_stray_legacy_file(
    tmp_path: Path,
) -> None:
    """WP05 cycle 2 (review-cycle-1.md Issue 1 — BLOCKING): a lone stray
    legacy file (a plausible real state — a leftover from a partially
    completed migration, a hand-edit, or a project mid-upgrade) must NOT be
    reported as if all four legacy files were present. ``_legacy_bundle_present``
    returns True on ANY of the four files existing, so a fixed four-file
    claim overclaims here — a confidently-wrong inventory of the operator's
    own ``.kittify/charter/`` directory. This is a red-first regression: it
    fails against the cycle-1 implementation, which always named all four
    files regardless of what was actually on disk.
    """
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "references.yaml").write_text("schema_version: '1'\n", encoding="utf-8")

    result = compute_freshness(tmp_path)

    assert result.charter_source.state == "missing"
    detail = result.charter_source.detail
    assert detail is not None
    assert detail == (
        "no charter.yaml, but a legacy charter bundle file (references.yaml) "
        "is present; this project has a charter, just not in the required form"
    )
    # The three files NOT on disk must not be named as present.
    for absent_name in ("governance.yaml", "directives.yaml", "metadata.yaml"):
        assert absent_name not in detail


def test_charter_source_missing_detail_true_for_two_of_four_legacy_files(
    tmp_path: Path,
) -> None:
    """WP05 cycle 2 (review-cycle-1.md Issue 1): a 2-of-4 partial bundle must
    name only the two files actually present, not the two that are absent."""
    charter_dir = tmp_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "directives.yaml").write_text("schema_version: '1'\n", encoding="utf-8")
    (charter_dir / "references.yaml").write_text("schema_version: '1'\n", encoding="utf-8")

    result = compute_freshness(tmp_path)

    assert result.charter_source.state == "missing"
    detail = result.charter_source.detail
    assert detail is not None
    assert detail == (
        "no charter.yaml, but legacy charter bundle files "
        "(directives.yaml/references.yaml) are present; this project has a "
        "charter, just not in the required form"
    )
    for absent_name in ("governance.yaml", "metadata.yaml"):
        assert absent_name not in detail


def test_charter_source_missing_detail_differs_between_f1_and_f2(tmp_path: Path) -> None:
    """A single-file regression pin: the F1 and F2 ``detail`` strings must
    never collapse back to the same (or both-empty) text — that would
    silently reintroduce the FR-005 gap this WP closes."""
    f1_result = compute_freshness(tmp_path)

    f2_path = tmp_path / "f2-sibling"
    charter_dir = f2_path / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    (charter_dir / "governance.yaml").write_text("schema_version: '1'\n", encoding="utf-8")
    f2_result = compute_freshness(f2_path)

    assert f1_result.charter_source.detail
    assert f2_result.charter_source.detail
    assert f1_result.charter_source.detail != f2_result.charter_source.detail


def test_charter_source_fresh_when_charter_yaml_parses(tmp_path: Path) -> None:
    _seed_charter_yaml(tmp_path)
    result = compute_freshness(tmp_path)
    assert result.charter_source.state == "fresh"
    assert result.charter_source.last_change is not None


def test_charter_source_invalid_when_unparseable(tmp_path: Path) -> None:
    """A genuinely malformed ``charter.yaml`` is ``invalid``, never ``stale``
    (Landmine 2: the ``charter.md``-hash staleness mechanism no longer
    exists at this layer)."""
    _seed_charter_yaml(tmp_path, body="not: [valid: yaml: at: all")
    result = compute_freshness(tmp_path)
    assert result.charter_source.state == "invalid"
    # WP02 (#2831 P0): `charter sync` never writes and could never clear this
    # state either. `charter generate` looked like the best available next
    # step (it is the doctrinally-intended remediation per
    # charter/bundle.py:199's docstring), but T008's empirical investigation
    # found NO command in the current codebase that can repair syntactically
    # broken YAML in one step — every write path merges into the existing
    # file via a round-trip parse, so it requires the file to already parse.
    # WP03 acted on this finding: `invalid` is now a declared exemption-set
    # member (C-EFF-2, out-of-map edit to this WP02 file — narrow,
    # consequence-of-computer.py-change only) and emits `remediation=None`
    # rather than a command proven ineffective; `detail` still explains why.
    assert result.charter_source.remediation is None
    assert "cannot be parsed" in (result.charter_source.detail or "")


def test_charter_source_invalid_when_empty_mapping(tmp_path: Path) -> None:
    """H5 (#2831 HIGH finding): ``charter.yaml: {}`` parses cleanly as YAML
    but is not a charter bundle by any consumer's standard (no
    ``schema_version``, no ``catalog``) — it must not read ``fresh``.
    Before this fix, ``_safe_load_yaml`` accepted any mapping including the
    empty one, so preflight greenlit a charter no other consumer would
    accept.
    """
    _seed_charter_yaml(tmp_path, body="{}\n")
    result = compute_freshness(tmp_path)
    assert result.charter_source.state == "invalid"
    assert result.charter_source.remediation is None
    assert "bundle contract" in (result.charter_source.detail or "")


@pytest.mark.parametrize("schema_version", ["1.0.0", "3.0.0", "not-a-version"])
def test_charter_source_invalid_when_schema_version_unsupported(
    tmp_path: Path, schema_version: str
) -> None:
    """H5 (#2831 HIGH finding): a ``schema_version`` this build's bundle
    contract does not understand (a pre-inversion ``1.0.0`` shape, a
    hypothetical future major, or a non-semver string) parses cleanly but
    must not read ``fresh`` — only the ``"2.x.x"`` series this build's
    ``charter.schemas.CharterYaml``/``charter.bundle.SCHEMA_VERSION``
    actually supports may pass.
    """
    _seed_charter_yaml(tmp_path, body=f"schema_version: '{schema_version}'\ncatalog: {{}}\n")
    result = compute_freshness(tmp_path)
    assert result.charter_source.state == "invalid"
    assert result.charter_source.remediation is None


def test_charter_source_fresh_when_schema_version_is_supported_minor_bump(
    tmp_path: Path,
) -> None:
    """A forward-compatible minor/patch bump within the supported major
    series (``2.x.x``) still reads ``fresh`` — H5 tightens on the
    UNSUPPORTED-major/malformed case only, not on any deviation from the
    exact seeded ``2.0.0`` string."""
    _seed_charter_yaml(tmp_path, body=_CHARTER_YAML_BODY.replace("2.0.0", "2.1.0"))
    result = compute_freshness(tmp_path)
    assert result.charter_source.state == "fresh"


def test_synced_bundle_stale_when_charter_source_invalid_via_unsupported_schema(
    tmp_path: Path,
) -> None:
    """H5 corollary: ``synced_bundle`` cascades the same way it already does
    for unparseable YAML — an unsupported ``schema_version`` makes
    ``charter_source`` ``invalid``, which cascades to ``synced_bundle``
    ``stale`` (never independently ``fresh``)."""
    _seed_charter_yaml(tmp_path, body="{}\n")
    result = compute_freshness(tmp_path)
    assert result.charter_source.state == "invalid"
    assert result.synced_bundle.state == "stale"


def test_charter_source_never_reachable_as_stale() -> None:
    """Structural pin for Landmine 2: ``"stale"`` is not among the states
    ``_compute_charter_source`` can produce — the content-drift question
    moved entirely to ``synthesized_drg``."""
    from specify_cli.charter_runtime.freshness import computer as freshness_computer

    assert not hasattr(freshness_computer, "_charter_hash_of")
    assert not hasattr(freshness_computer, "_activation_parity_drift_reason")
    assert not hasattr(freshness_computer, "_PARITY_DRIFT_REMEDIATION")


def test_synced_bundle_missing_when_charter_yaml_absent(tmp_path: Path) -> None:
    result = compute_freshness(tmp_path)
    assert result.synced_bundle.state == "missing"


def test_synced_bundle_fresh_when_charter_yaml_parses(tmp_path: Path) -> None:
    _seed_charter_yaml(tmp_path)
    result = compute_freshness(tmp_path)
    assert result.charter_source.state == "fresh"
    assert result.synced_bundle.state == "fresh"


def test_synced_bundle_stale_when_charter_source_invalid(tmp_path: Path) -> None:
    _seed_charter_yaml(tmp_path, body="not: [valid: yaml: at: all")
    result = compute_freshness(tmp_path)
    assert result.charter_source.state == "invalid"
    assert result.synced_bundle.state == "stale"


def test_synthesized_drg_missing_when_no_graph_no_manifest(tmp_path: Path) -> None:
    """Preserved by the #2681 fix — the ``missing`` branch (no ``graph.yaml``,
    no built-in-only opt-in, no legacy seed marker) sits above the
    content-hash comparison."""
    _seed_charter_yaml(tmp_path)
    result = compute_freshness(tmp_path)
    assert result.synthesized_drg.state == "missing"
    assert result.synthesized_drg.remediation == "spec-kitty charter synthesize"


def test_synthesized_drg_built_in_only_when_manifest_declares_it(tmp_path: Path) -> None:
    """Preserved by the #2681 fix (data-model.md): ``built_in_only`` short-
    circuits BEFORE the content-hash comparison."""
    _seed_charter_yaml(tmp_path)
    _seed_manifest(tmp_path, built_in_only=True)
    result = compute_freshness(tmp_path)
    assert result.synthesized_drg.state == "built_in_only"
    assert result.synthesized_drg.remediation is None


def test_synthesized_drg_built_in_only_for_legacy_fresh_seed(tmp_path: Path) -> None:
    """Preserved by the #2681 fix — the legacy-fresh-seed branch sits above
    the content-hash comparison."""
    _seed_charter_yaml(tmp_path)
    provenance = tmp_path / ".kittify" / "charter-packs" / "PROVENANCE.md"
    provenance.parent.mkdir(parents=True, exist_ok=True)
    provenance.write_text(
        "# Spec Kitty Doctrine — Fresh Project Seed\n\n"
        "No LLM-authored YAML was present; using built-in doctrine.\n",
        encoding="utf-8",
    )

    result = compute_freshness(tmp_path)

    assert result.synthesized_drg.state == "built_in_only"
    assert result.synthesized_drg.remediation is None


def test_synthesized_drg_residue_reports_built_in_only(tmp_path: Path) -> None:
    """FR-006 (C2-f): built_in_only=true ∧ graph.yaml present is read-time residue.

    The manifest is the declared authority (#083): a graph.yaml it disowns is
    residue, NOT a contradiction. The reader reports the authoritative
    ``built_in_only`` state with a non-blocking diagnostic instead of the
    formerly-terminal ``invalid`` state — making the blocking branch
    unreachable for this condition (structural, not reactive).
    """
    _seed_charter_yaml(tmp_path)
    _seed_manifest(tmp_path, built_in_only=True)
    _seed_graph(tmp_path)  # residue: built_in_only=true AND graph.yaml present
    result = compute_freshness(tmp_path)
    assert result.synthesized_drg.state == "built_in_only"
    assert result.synthesized_drg.state != "invalid"
    assert result.synthesized_drg.detail is not None
    assert "stale graph residue" in result.synthesized_drg.detail
    # Read-time normalization is NOT a reactive self-heal: no synthesize push.
    assert result.synthesized_drg.remediation is None


def test_synthesized_drg_stale_when_synced_bundle_not_fresh(tmp_path: Path) -> None:
    """Preserved precedence branch (data-model.md): an upstream-stale
    ``synced_bundle`` short-circuits ``synthesized_drg`` to ``stale`` BEFORE
    any content-hash comparison runs."""
    _seed_charter_yaml(tmp_path, body="not: [valid: yaml: at: all")
    _seed_graph(tmp_path)
    _seed_manifest(tmp_path, built_in_only=False, bundle_content_hash="sha256:" + "0" * 64)

    result = compute_freshness(tmp_path)

    assert result.charter_source.state == "invalid"
    assert result.synced_bundle.state == "stale"
    assert result.synthesized_drg.state == "stale"
    assert result.synthesized_drg.remediation == "spec-kitty charter synthesize"


def test_synthesized_drg_fresh_when_hash_matches(tmp_path: Path) -> None:
    _seed_fresh_bundle_and_manifest(tmp_path)
    _seed_graph(tmp_path)
    result = compute_freshness(tmp_path)
    assert result.synthesized_drg.state == "fresh"


def test_synthesized_drg_legacy_root_read_fallback(tmp_path: Path) -> None:
    """TEMPORARY (FR-011, deleted by WP14 with the read shim).

    A project whose graph is still only under the retired ``.kittify/doctrine/``
    root reads as ``fresh``; with the graph gone it reads as ``missing``.
    """
    _seed_fresh_bundle_and_manifest(tmp_path)
    graph = _seed_graph(tmp_path)
    legacy = tmp_path / ".kittify" / "doctrine"
    graph.parent.rename(legacy)
    assert compute_freshness(tmp_path).synthesized_drg.state == "fresh"
    (legacy / "graph.yaml").unlink()
    assert compute_freshness(tmp_path).synthesized_drg.state == "missing"


# ---------------------------------------------------------------------------
# Content-identity comparison (WP03 / #2681 reader swap; WP06 re-pointed at
# charter.yaml)
# ---------------------------------------------------------------------------


def test_synthesized_drg_fresh_after_mtime_only_bump(tmp_path: Path) -> None:
    """AS-1 (fresh survives mtime perturbation).

    A realistic past-dated ``created_at`` (e.g. ``2026-01-01…``, NOT the
    ``2099-…`` sentinel — NFR-006) loses to a bumped bundle mtime under the
    old ``manifest_ts + 1.0 < bundle_ts`` rule, so a mtime-based reader would
    wrongly report ``stale`` here. GREEN under the content-identity reader.
    """
    _seed_charter_yaml(tmp_path)
    _seed_graph(tmp_path)
    real_hash = compute_bundle_content_hash(tmp_path)
    assert real_hash is not None
    _seed_manifest(
        tmp_path,
        built_in_only=False,
        created_at="2026-01-01T00:00:00+00:00",  # realistic past date, NOT 2099
        bundle_content_hash=real_hash,
    )

    _bump_bundle_mtimes_to_future(tmp_path)

    result = compute_freshness(tmp_path)

    assert result.synthesized_drg.state == "fresh"


def test_synthesized_drg_stale_when_charter_yaml_is_missing(tmp_path: Path) -> None:
    """A missing ``charter.yaml`` yields ``stale`` — never ``fresh``, never a
    crash. ``compute_bundle_content_hash`` fail-safes to ``None`` when the
    file is absent, so the reader reports ``stale`` (via the
    ``synced_bundle``-not-fresh precedence branch)."""
    _seed_charter_yaml(tmp_path)
    _seed_graph(tmp_path)
    real_hash = compute_bundle_content_hash(tmp_path)
    assert real_hash is not None
    _seed_manifest(
        tmp_path,
        built_in_only=False,
        created_at="2026-01-01T00:00:00+00:00",
        bundle_content_hash=real_hash,
    )

    # Remove the bundle file after the manifest was stamped fresh.
    (tmp_path / ".kittify" / "charter" / "charter.yaml").unlink()

    # The recipe fail-safes to None (never raises) on the missing file...
    assert compute_bundle_content_hash(tmp_path) is None
    # ...and the reader maps the incomplete bundle to stale, not fresh/crash.
    assert compute_freshness(tmp_path).synthesized_drg.state == "stale"


def test_synthesized_drg_stale_when_bundle_content_genuinely_changed(tmp_path: Path) -> None:
    """AS-2 pin (fact #22): a genuine bundle-content edit is still ``stale``.

    May coincidentally pass on a pre-swap mtime reader too (editing content
    also bumps mtime) — its regression power activates once the
    content-hash reader lands; it is NOT the red-first proof (see AS-1 for
    that).
    """
    _seed_charter_yaml(tmp_path)
    _seed_graph(tmp_path)
    real_hash = compute_bundle_content_hash(tmp_path)
    assert real_hash is not None
    _seed_manifest(
        tmp_path,
        built_in_only=False,
        created_at="2026-01-01T00:00:00+00:00",
        bundle_content_hash=real_hash,
    )

    # Genuinely edit bundle CONTENT (not just mtime) without re-seeding the
    # manifest's stored hash.
    charter_yaml_path = tmp_path / ".kittify" / "charter" / "charter.yaml"
    charter_yaml_path.write_text(
        charter_yaml_path.read_text(encoding="utf-8") + "# drift-marker\n", encoding="utf-8"
    )

    result = compute_freshness(tmp_path)

    assert result.synthesized_drg.state == "stale"


def test_synthesized_drg_2681_repro_cleared_via_synthesize(tmp_path: Path) -> None:
    """AS-5 (#2681 full repro, ``synthesize`` entry point).

    synthesize once -> a no-op-stable run occurs -> a git-style mtime bump
    (content unchanged) -> a mtime-based reader would wrongly report
    ``stale`` and stay stuck ``stale`` even after a ``synthesize``
    remediation attempt. GREEN under the content-identity reader.
    """
    _seed_pipeline_bundle_files(tmp_path)
    adapter = _synth_adapter()
    synthesize(_base_synthesis_request("01AAAAAAAAAAAAAAAAAAAAAAAA"), adapter=adapter, repo_root=tmp_path)
    # No-op-stable run: fresh run_id, identical inputs (#1912/#1914).
    synthesize(_base_synthesis_request("01BBBBBBBBBBBBBBBBBBBBBBBB"), adapter=adapter, repo_root=tmp_path)

    _bump_bundle_mtimes_to_future(tmp_path)

    # Content unchanged by the mtime bump alone -> must already read fresh
    # (AS-1's guarantee, exercised here inside the full #2681 timeline).
    assert compute_freshness(tmp_path).synthesized_drg.state == "fresh"

    # Remediation via `synthesize` -- must not leave the DRG stuck stale.
    synthesize(_base_synthesis_request("01CCCCCCCCCCCCCCCCCCCCCCCC"), adapter=adapter, repo_root=tmp_path)

    assert compute_freshness(tmp_path).synthesized_drg.state == "fresh"


def test_synthesized_drg_2681_repro_cleared_via_resynthesize(tmp_path: Path) -> None:
    """AS-5 (#2681 full repro, ``resynthesize`` entry point) — separate fresh
    fixture, mirrors the ``synthesize`` case above via
    ``resynthesize_pipeline.run``. Covers both entry points (NFR-006)."""
    _seed_pipeline_bundle_files(tmp_path)
    adapter = _synth_adapter()
    synthesize(_base_synthesis_request("01DDDDDDDDDDDDDDDDDDDDDDDD"), adapter=adapter, repo_root=tmp_path)
    synthesize(_base_synthesis_request("01EEEEEEEEEEEEEEEEEEEEEEEE"), adapter=adapter, repo_root=tmp_path)

    _bump_bundle_mtimes_to_future(tmp_path)

    assert compute_freshness(tmp_path).synthesized_drg.state == "fresh"

    resynthesize_run(
        request=_base_synthesis_request("01FFFFFFFFFFFFFFFFFFFFFFFF"),
        adapter=adapter,
        topic="tactic:how-we-apply-directive-003",
        repo_root=tmp_path,
    )

    assert compute_freshness(tmp_path).synthesized_drg.state == "fresh"


def test_synthesized_drg_remediation_clears_genuine_content_change(tmp_path: Path) -> None:
    """Genuine-content-change remediation e2e (SC-003/AS-3 full proof).

    fresh -> edit ``charter.yaml`` CONTENT (the spurious authoring-staleness
    case, data-model.md Landmine 2 extension, decision (b) —
    ``traces/decisions.md``) -> stale -> ``synthesize`` -> fresh; repeat the
    stale -> ``resynthesize`` -> fresh cycle. Proves the writer recompute
    AND this reader compose end-to-end, AND that an authoring-only edit is
    always healable by the very next synth (never a permanent-stale
    dead-end) — fails if either half is broken.
    """
    _seed_pipeline_bundle_files(tmp_path)
    adapter = _synth_adapter()
    synthesize(_base_synthesis_request("01GGGGGGGGGGGGGGGGGGGGGGGG"), adapter=adapter, repo_root=tmp_path)

    assert compute_freshness(tmp_path).synthesized_drg.state == "fresh"

    charter_yaml_path = tmp_path / ".kittify" / "charter" / "charter.yaml"
    charter_yaml_path.write_text(
        charter_yaml_path.read_text(encoding="utf-8") + "# drift-marker\n", encoding="utf-8"
    )
    assert compute_freshness(tmp_path).synthesized_drg.state == "stale"

    synthesize(_base_synthesis_request("01HHHHHHHHHHHHHHHHHHHHHHHH"), adapter=adapter, repo_root=tmp_path)
    assert compute_freshness(tmp_path).synthesized_drg.state == "fresh"

    charter_yaml_path.write_text(
        charter_yaml_path.read_text(encoding="utf-8") + "# drift-marker-2\n", encoding="utf-8"
    )
    assert compute_freshness(tmp_path).synthesized_drg.state == "stale"

    resynthesize_run(
        request=_base_synthesis_request("01JJJJJJJJJJJJJJJJJJJJJJJJ"),
        adapter=adapter,
        topic="tactic:how-we-apply-directive-003",
        repo_root=tmp_path,
    )
    assert compute_freshness(tmp_path).synthesized_drg.state == "fresh"


def test_to_dict_shape_matches_contract(tmp_path: Path) -> None:
    """``CharterFreshness.to_dict`` returns the three documented keys."""
    result = compute_freshness(tmp_path)
    d = result.to_dict()
    assert set(d.keys()) == {"charter_source", "synced_bundle", "synthesized_drg"}
    for layer in d.values():
        assert set(layer.keys()) >= {"state", "last_change", "remediation", "detail"}


@pytest.mark.parametrize(
    "scenario",
    ["fresh", "missing", "built_in_only", "invalid"],
)
def test_states_are_among_documented_vocabulary(scenario: str, tmp_path: Path) -> None:
    """Smoke: every documented state value is reachable by the computer.

    ``"stale"`` is exercised by the dedicated
    ``test_synthesized_drg_stale_when_synced_bundle_not_fresh`` /
    ``test_synthesized_drg_stale_when_bundle_content_genuinely_changed``
    tests above rather than here — post-Landmine-2 it is reachable only via
    ``synthesized_drg``/``synced_bundle``, not as a smoke-level
    ``charter_source`` scenario (that producer is retired).
    """
    if scenario == "missing":
        result = compute_freshness(tmp_path)
        states = {
            result.charter_source.state,
            result.synced_bundle.state,
            result.synthesized_drg.state,
        }
        assert "missing" in states
        return
    if scenario == "fresh":
        _seed_charter_yaml(tmp_path)
        result = compute_freshness(tmp_path)
        assert result.charter_source.state == "fresh"
        return
    if scenario == "built_in_only":
        _seed_charter_yaml(tmp_path)
        _seed_manifest(tmp_path, built_in_only=True)
        result = compute_freshness(tmp_path)
        assert result.synthesized_drg.state == "built_in_only"
        return
    if scenario == "invalid":
        # FR-006 re-pointed this vocabulary smoke-entry: the only ``invalid``
        # producer is ``_compute_charter_source`` ("charter.yaml exists but
        # cannot be parsed"), a genuine inconsistency — NOT the downgraded
        # built_in_only ∧ graph residue case.
        _seed_charter_yaml(tmp_path)
        charter_yaml_path = tmp_path / ".kittify" / "charter" / "charter.yaml"
        charter_yaml_path.unlink()
        charter_yaml_path.mkdir()  # a directory where a file is expected → unparseable
        result = compute_freshness(tmp_path)
        assert result.charter_source.state == "invalid"
        return
    pytest.fail(f"Unhandled scenario {scenario!r}")


# ---------------------------------------------------------------------------
# NFR-002: default freshness read spawns ZERO subprocesses
# ---------------------------------------------------------------------------


def test_compute_freshness_spawns_zero_subprocesses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """NFR-002: a default ``compute_freshness`` read must not spawn any
    synthesis/regenerate subprocess. ``compute_freshness`` is a pure
    observer (module docstring) -- it reads ``charter.yaml``, the synthesis
    manifest, and ``graph.yaml`` from disk only, never shelling out.

    Exercised across a fresh, a stale (content-hash mismatch), and a
    missing-everything repo so the spy covers every branch of the three
    sub-state computers, not just the happy path.
    """
    import subprocess

    call_count = 0
    real_run = subprocess.run
    real_popen = subprocess.Popen

    def _spy_run(*args: object, **kwargs: object) -> object:
        nonlocal call_count
        call_count += 1
        return real_run(*args, **kwargs)  # type: ignore[arg-type]

    def _spy_popen(*args: object, **kwargs: object) -> object:
        nonlocal call_count
        call_count += 1
        return real_popen(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(subprocess, "run", _spy_run)
    monkeypatch.setattr(subprocess, "Popen", _spy_popen)

    # Fresh.
    _seed_fresh_bundle_and_manifest(tmp_path)
    _seed_graph(tmp_path)
    compute_freshness(tmp_path)

    # Stale (genuine content drift, no re-stamp).
    (tmp_path / ".kittify" / "charter" / "charter.yaml").write_text(
        _CHARTER_YAML_BODY.replace("mission: test-mission", "mission: drifted-mission"),
        encoding="utf-8",
    )
    compute_freshness(tmp_path)

    # Missing everything.
    empty_repo = tmp_path / "empty"
    empty_repo.mkdir()
    compute_freshness(empty_repo)

    assert call_count == 0, f"compute_freshness spawned {call_count} subprocess(es) (NFR-002 violation)"
