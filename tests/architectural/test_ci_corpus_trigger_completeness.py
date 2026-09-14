"""Corpus trigger + marker completeness invariants (#3008, WP01 T007).

Two silent-no-op vectors this file closes -- both folded from the
pre-implement investigate squad (kitty-specs/ci-scoping-gate-reliability-01KZP80D/
investigate-squad-findings.md, R-WP01-a and R-WP01-b):

1. **Gate-0 presence (R-WP01-b, decisive).** ``test_ci_quality_path_filters.py``
   only ever parses the dorny ``filters:`` block (Gate 1). It has zero
   coverage of ``on.pull_request.paths`` / ``on.push.paths`` (Gate 0). An
   implementer who wires the dorny filter + job + gate but forgets the
   ``on.paths`` globs gets every OTHER arch guard green while shipping a
   workflow that never triggers on a corpus-only PR -- #3008 stays inert.
   This file is the ONLY net for that hole.

2. **Marker-completeness (R-WP01-a).** ``pytest -m corpus`` selecting zero
   tests already fails loudly (pytest exit 5 -> job FAILS). But a corpus
   reader that is simply never given ``pytest.mark.corpus`` is neither run
   by ``fast-tests-corpus`` NOR caught by that exit-5 floor -- it just
   silently never re-runs on a corpus-only change. The literal M4 form
   ("every path a ``@corpus`` test reads is matched by the corpus globs") is
   NOT statically computable: readers reach data through loaders/fixtures
   (``load_built_in_graph``, ``packs/built-in`` conftest fixtures) and
   dynamically-built paths. This file implements the decidable PROXY
   instead: pin the marked-module set to a curated, hand-maintained
   registry, so a NEW corpus reader (or one silently un-marked) forces a
   conscious update here rather than reopening #3008 for that module.

The restored interim ``ci-quality.yml`` removes Gate 0 entirely by running on
every pull request and main push, so corpus-only changes cannot silently skip
the producer. The marker-completeness half below stays unchanged.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CI_QUALITY = _REPO_ROOT / ".github" / "workflows" / "ci-quality.yml"


def _load_workflow() -> dict[str, Any]:
    return yaml.safe_load(_CI_QUALITY.read_text(encoding="utf-8"))


def test_corpus_changes_trigger_reduced_ci_quality_live() -> None:
    workflow = _load_workflow()
    on_section = workflow.get("on") or workflow[True]

    for event in ("pull_request", "push"):
        assert "paths" not in on_section[event]

# The authoritative corpus glob set (T001 on.paths / T002 dorny filter) --
# discrete lines only: GitHub `on.paths` does not support `{a,b}` brace
# expansion, so both trigger surfaces enumerate every glob individually.
# Never add bare `kitty-specs/**` or `status.events.jsonl` (C-001) -- that
# would fire on routine WP status-event churn.
_CORPUS_GLOBS = frozenset(
    {
        "packs/**",
        "kitty-specs/**/spec.md",
        "kitty-specs/**/plan.md",
        "kitty-specs/**/tasks/**",
        "kitty-specs/**/contracts/**",
        "kitty-specs/**/acceptance-matrix.json",
        ".kittify/charter/**",
        ".kittify/glossaries/**",
        ".kittify/doctrine/**",
        ".kittify/release/downstream-verified.json",
    }
)

# The corpus data ROOTS every glob above must collectively cover -- a
# coarser, independent second cut at the same coverage claim that would
# catch a glob typo/drift that still parses as valid YAML but no longer
# anchors under its intended root.
_CORPUS_DATA_ROOTS = (
    "packs/",
    "kitty-specs/",
    ".kittify/charter/",
    ".kittify/glossaries/",
    ".kittify/doctrine/",
    ".kittify/release/downstream-verified.json",
)

# Curated registry (R-WP01-a): every test module that reads the real,
# on-disk wheel-shipped doctrine corpus (packs/built-in/**, via the
# tests/doctrine/conftest.py `built_in_graph`/`shipped_drg_graph` fixtures,
# `load_built_in_graph()`/`built_in_graph_source()`, `resolve_pack_root()`,
# `BUILT_IN_MISSIONS_ROOT`, a bare `AgentProfileRepository()`/
# `DoctrineService()`, or a real-`REPO_ROOT`-anchored path) or the narrow
# kitty-specs mission-spec leaves (spec.md/plan.md/tasks/contracts) this
# WP's globs cover. Enumerated from research/corpus-suite-inventory.md plus
# a full grep sweep for these entry points, then hand-verified file-by-file
# to exclude modules whose only "corpus" signal is a synthetic tmp_path
# construction, a literal error-message string assertion, or a stale
# pre-relocation path that no longer resolves to any real content on disk
# (e.g. `src/charter/offering/<kind>/built-in/` -- doctrine content kinds other than
# `skills`/`templates` relocated to `packs/built-in/<kind>/`; several
# compliance tests were never updated and now glob a directory that no
# longer exists -- vacuously passing, a pre-existing staleness bug outside
# this WP's scope, tracked separately, and correctly excluded here since
# they read nothing real today).
_CORPUS_MARKED_MODULES = frozenset(
    {
        "tests/architectural/test_bare_prose_corpus_ratchet.py",
        "tests/architectural/test_transition_guard_shrink_only.py",
        "tests/charter/synthesizer/test_manifest.py",
        "tests/charter/test_action_gate_single_load.py",
        "tests/architectural/test_pack_manifest_no_author_edit.py",
        "tests/contract/test_example_round_trip.py",
        "tests/doctrine/agent_profiles/test_context_sources_migration.py",
        "tests/doctrine/agent_profiles/test_doctrine_daphne_canonical_structure.py",
        "tests/doctrine/agent_profiles/test_profile_resolution.py",
        "tests/doctrine/agent_profiles/test_register_overlay.py",
        "tests/doctrine/agent_profiles/test_supply_chain_profile_bindings.py",
        "tests/doctrine/assets/test_repository.py",
        "tests/doctrine/drg/migration/test_extractor.py",
        "tests/doctrine/drg/migration/test_extractor_projection.py",
        "tests/doctrine/drg/migration/test_governance_scope_e2e.py",
        "tests/doctrine/drg/migration/test_path_ref_resolver.py",
        "tests/doctrine/drg/test_builtin_graph_seam.py",
        "tests/doctrine/drg/test_c4_and_anti_pattern_topology.py",
        "tests/doctrine/drg/test_cross_grain_integrity.py",
        "tests/doctrine/drg/test_glossary_node_kind.py",
        "tests/doctrine/drg/test_graph_sharding_equality.py",
        "tests/doctrine/drg/test_instantiates_edges.py",
        "tests/doctrine/drg/test_mission_type_nodes.py",
        "tests/doctrine/drg/test_model_strictness_roundtrip.py",
        "tests/doctrine/drg/test_org_drg_bridge.py",
        "tests/doctrine/drg/test_org_governance_failloud.py",
        "tests/doctrine/drg/test_profile_suggests_delivery.py",
        "tests/doctrine/drg/test_reachability.py",
        "tests/doctrine/drg/test_regen_roundtrip.py",
        "tests/doctrine/drg/test_resolve_transitive_refs.py",
        "tests/doctrine/drg/test_sharded_layout.py",
        "tests/doctrine/drg/test_sharding_silent_degrade.py",
        "tests/doctrine/drg/test_shipped_graph_valid.py",
        "tests/doctrine/drg/test_tiered_standards_non_orphan.py",
        "tests/doctrine/drg/test_unknown_kind_fails_loudly.py",
        "tests/doctrine/glossary_packs/test_builtin_pack_resolution.py",
        "tests/doctrine/mission_step_contracts/test_declared_commands_parse.py",
        "tests/doctrine/mission_step_contracts/test_repository.py",
        "tests/doctrine/mission_step_contracts/test_shipped_contracts.py",
        "tests/doctrine/missions/test_builtin_mission_type_ids.py",
        "tests/doctrine/missions/test_mission_steps_layout.py",
        "tests/doctrine/missions/test_mission_type_repository.py",
        "tests/doctrine/missions/test_prompt_emptiness.py",
        "tests/doctrine/missions/test_referential_integrity.py",
        "tests/doctrine/test_built_in_location_authority.py",
        "tests/doctrine/test_debugger_debbie_artifacts.py",
        "tests/doctrine/test_directive_consistency.py",
        "tests/doctrine/test_enriched_directives.py",
        "tests/doctrine/test_generic_agent_profile.py",
        "tests/doctrine/test_generic_artifact_language_bias.py",
        "tests/doctrine/test_human_in_charge_profile.py",
        "tests/doctrine/test_loader_fail_closed.py",
        "tests/doctrine/test_mattpocock_skill_doctrine.py",
        "tests/doctrine/test_mission_type_governance_isolation.py",
        "tests/doctrine/test_overlay_precedence.py",
        "tests/doctrine/test_pack_relocation_doctor_gate.py",
        "tests/doctrine/test_pack_relocation_guard.py",
        "tests/doctrine/test_pack_relocation_preflight.py",
        "tests/doctrine/test_package_smoke.py",
        "tests/doctrine/test_packaging_parity.py",
        "tests/doctrine/test_paula_patterns_artifacts.py",
        "tests/doctrine/test_profile_diagnostics.py",
        "tests/doctrine/test_profile_inheritance.py",
        "tests/doctrine/test_relationship_migration.py",
        "tests/doctrine/test_retrospective_drg.py",
        "tests/doctrine/test_service.py",
        "tests/doctrine/test_service_org_layer.py",
        "tests/doctrine/test_shipped_profiles.py",
        "tests/doctrine/test_spdd_reasons_artifacts.py",
        "tests/doctrine/test_supply_chain_security_layer.py",
        "tests/doctrine/test_template_asset_e2e.py",
        "tests/doctrine/test_wheel_packaging.py",
        "tests/doctrine/test_wp_authoring_contract_roundtrip.py",
        "tests/glossary/test_gate_terms.py",
        "tests/integration/test_mission_review_contract_gate.py",
    }
)










def test_every_corpus_data_root_is_covered_by_a_trigger_glob() -> None:
    """Reader-root coverage (decidable proxy for M4): every declared corpus
    data root must be the prefix of at least one corpus trigger glob."""
    uncovered = [root for root in _CORPUS_DATA_ROOTS if not any(glob.startswith(root) for glob in _CORPUS_GLOBS)]
    assert not uncovered, f"corpus data roots with no covering trigger glob: {uncovered}"


def test_no_corpus_glob_is_a_bare_kitty_specs_or_status_events_catch_all() -> None:
    """C-001: never a bare ``kitty-specs/**`` or ``status.events.jsonl`` --
    either would fire on every routine WP status-lane transition."""
    assert "kitty-specs/**" not in _CORPUS_GLOBS
    assert not any(glob.endswith("status.events.jsonl") for glob in _CORPUS_GLOBS)


# Matches an ACTUAL marker application -- a `pytestmark = ...` assignment
# line (module-level list or single mark) or an `@pytest.mark.corpus`
# decorator -- never a docstring/comment/assert-message that merely mentions
# the marker in prose (this file's own docstrings do exactly that, and must
# NOT self-match).
_CORPUS_MARK_APPLICATION_RE = re.compile(
    r"^\s*(?:@pytest\.mark\.corpus\b|pytestmark\s*=.*\bpytest\.mark\.corpus\b)",
    re.MULTILINE,
)


def _scan_corpus_marked_modules() -> frozenset[str]:
    """Statically find every test module carrying ``pytest.mark.corpus``.

    A regex scan (not AST) is sufficient here: every current usage is either
    a module-level ``pytestmark = [...]`` list/single-mark assignment or a
    per-test ``@pytest.mark.corpus`` decorator, both matched at line start by
    :data:`_CORPUS_MARK_APPLICATION_RE` -- a prose mention (e.g. in this very
    file's docstrings) never matches, since it never starts a line with
    either form.
    """
    found: set[str] = set()
    for path in (_REPO_ROOT / "tests").rglob("test_*.py"):
        if _CORPUS_MARK_APPLICATION_RE.search(path.read_text(encoding="utf-8")):
            found.add(str(path.relative_to(_REPO_ROOT)).replace("\\", "/"))
    return frozenset(found)


def test_corpus_marked_modules_match_the_curated_registry() -> None:
    """R-WP01-a: the marked set must equal the curated registry exactly.

    A module newly marked ``pytest.mark.corpus`` (or one dropped) without an
    accompanying update here fails loudly, forcing a reviewer to
    consciously reconcile the registry rather than letting a reader
    silently join or leave the corpus job's blocking coverage.
    """
    actual = _scan_corpus_marked_modules()
    missing_from_registry = actual - _CORPUS_MARKED_MODULES
    missing_from_disk = _CORPUS_MARKED_MODULES - actual
    assert not missing_from_registry, f"modules newly marked pytest.mark.corpus but absent from the curated registry in this file: {sorted(missing_from_registry)}"
    assert not missing_from_disk, f"modules in the curated registry no longer carry pytest.mark.corpus (or were deleted/renamed): {sorted(missing_from_disk)}"


def test_corpus_marked_registry_is_non_empty() -> None:
    """Defense-in-depth floor: a healthy registry is never empty -- catches
    the whole registry being silently emptied out from under the gate."""
    assert len(_CORPUS_MARKED_MODULES) > 0








def test_corpus_marker_is_registered_in_pytest_ini() -> None:
    """T005: the ``corpus`` marker must be registered (pytest.ini, not
    pyproject.toml -- its [tool.pytest.ini_options] block is intentionally
    empty and would be dead config)."""
    pytest_ini = (_REPO_ROOT / "pytest.ini").read_text(encoding="utf-8")
    assert "\n    corpus:" in pytest_ini
