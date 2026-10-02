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
   by the corpus lane NOR caught by that exit-5 floor -- it just
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

import itertools
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.ci.corpus_select import corpus_selected
from scripts.ci.gate_selection import load_router, select_gates
from tests.architectural import _gate_coverage as gc
from tests.ci._gh_if import eval_gh_if

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CI_QUALITY = _REPO_ROOT / ".github" / "workflows" / "ci-quality.yml"


def _load_workflow() -> dict[Any, Any]:
    return dict(yaml.safe_load(_CI_QUALITY.read_text(encoding="utf-8")))


def test_corpus_changes_trigger_reduced_ci_quality_live() -> None:
    workflow = _load_workflow()
    on_section = workflow.get("on") or workflow[True]

    for event in ("pull_request", "push"):
        assert "paths" not in on_section[event]


# The corpus glob set, derived from the LIVE router `corpus` filter group -- the
# one source (C-003, FR-009): Packs reads it through scripts/ci/corpus_select.py,
# so a hand-maintained copy here would be a second encoding.
# Never add bare `kitty-specs/**` or `status.events.jsonl` (C-001) -- that
# would fire on routine WP status-event churn.
_CORPUS_GLOBS = frozenset(load_router().filters["corpus"])

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
    # (`.kittify/release/downstream-verified.json` was dropped: it is not a tracked
    # file and is not in the router corpus group.)
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
        "tests/contract/test_bundle.py",
        "tests/contract/test_citation_check.py",
        "tests/contract/test_client_smoke.py",
        "tests/contract/test_contract_resolver.py",
        "tests/contract/test_enum_pin_check.py",
        "tests/contract/test_event_mapping_check.py",
        "tests/contract/test_example_check.py",
        "tests/contract/test_example_round_trip.py",
        "tests/contract/test_fixture_builder.py",
        "tests/contract/test_install_tools.py",
        "tests/contract/test_layout_check.py",
        "tests/contract/test_leak_patterns.py",
        "tests/contract/test_leak_scan.py",
        "tests/contract/test_mission_status_examples.py",
        "tests/contract/test_provisional_check.py",
        "tests/contract/test_resolver_parity.py",
        "tests/contract/test_schema_formats.py",
        "tests/contract/test_structure_check.py",
        "tests/contract/test_verify_pins.py",
        "tests/doctrine/agent_profiles/test_builtin_document_memo.py",
        "tests/doctrine/agent_profiles/test_context_sources_migration.py",
        "tests/doctrine/agent_profiles/test_doctrine_daphne_canonical_structure.py",
        "tests/doctrine/agent_profiles/test_drupal_dries_profile.py",
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
        "tests/doctrine/drg/test_drupal_dries_lineage.py",
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
        "tests/doctrine/styleguides/test_drupal_styleguide_presence.py",
        "tests/doctrine/test_acceptance_criteria_non_vacuity_wiring.py",
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


# ---------------------------------------------------------------------------
# FR-009 (WP09): Packs is the SOLE, ADVISORY owner of the `-m corpus` suite.
#
# The router's own `corpus` filter group is the one source of the trigger set
# (C-003); Packs must select the corpus lane on a SUPERSET of it, through the
# shared `scripts/ci/corpus_select.py` helper, and must be advisory on every
# verdict surface (job-level continue-on-error, outside packs-gate.needs).
# ---------------------------------------------------------------------------

_PACKS = gc.WORKFLOWS_DIR / "packs.yml"
_ROUTER = gc.WORKFLOWS_DIR / "ci-router.yml"
_CORPUS_JOB = "built-in-corpus-suite"
_MANIFEST_JOB = "built-in-pack-manifest"
_MANIFEST_TEST = "tests/architectural/test_pack_manifest_no_author_edit.py"
_UNMATCHED_SRC_PROBE = "src/specify_cli/__unmapped_probe__/x.py"
_SELECTION_STEP_ID = "corpus"
_NULL_SHA = "0" * 40
# The one canonical job trigger the advisory corpus run AND the blocking
# pack-manifest guard share: built-in OR the router-derived corpus selection.
_TRIGGER_OUTPUTS = ("changes.built_in", "changes.corpus")


def _packs_jobs() -> dict[str, Any]:
    return dict(yaml.safe_load(_PACKS.read_text(encoding="utf-8"))["jobs"])


def _trigger_truth_table(raw_if: object) -> dict[tuple[bool, bool], bool]:
    """Evaluate a job ``if:`` over every (built_in, corpus) output combination with the shared GitHub-``if:`` evaluator."""
    return {
        (built_in, corpus): eval_gh_if(str(raw_if), {"changes.built_in": built_in, "changes.corpus": corpus})
        for built_in, corpus in itertools.product((False, True), repeat=2)
    }


def _assert_trigger_is_built_in_or_corpus(raw_if: object, job: str) -> None:
    """The job runs iff `built_in` OR `corpus` is true -- by evaluation, never by substring.

    A substring check accepts an inverted trigger (`!= 'true' && ...`) or one that
    dropped `built_in`; the truth table does not.
    """
    expected = {(built_in, corpus): built_in or corpus for built_in, corpus in itertools.product((False, True), repeat=2)}
    assert _trigger_truth_table(raw_if) == expected, f"{job}: `if:` must evaluate to built_in OR corpus over {_TRIGGER_OUTPUTS}, got {raw_if!r}"


def _probe_for_glob(glob: str) -> str:
    """A concrete tracked-looking path matched by *glob* (``**/`` -> ``m/``, trailing ``**`` -> a file)."""
    probe = glob.replace("**/", "m/")
    if probe.endswith("**"):
        probe = probe[:-2] + "probe.md"
    assert "*" not in probe, f"cannot derive a probe path from {glob!r}"
    return probe


@pytest.mark.parametrize("glob", sorted(_CORPUS_GLOBS))
def test_packs_corpus_lane_covers_every_router_corpus_trigger(glob: str) -> None:
    """For each glob of the LIVE router `corpus` group, Packs selects the lane too."""
    probe = _probe_for_glob(glob)
    assert "corpus" in select_gates([probe]).matched_groups, f"{probe!r} (from {glob!r}) is not in the router corpus group"
    assert corpus_selected([probe], router=load_router()) is True, f"Packs would not select the corpus lane for {probe!r}"


def test_packs_corpus_lane_covers_unmatched_src_fanout_and_full_mode() -> None:
    router = load_router()
    assert select_gates([_UNMATCHED_SRC_PROBE]).unmatched_src is True
    assert corpus_selected([_UNMATCHED_SRC_PROBE], router=router) is True
    assert corpus_selected(["docs/x.md"], router=router, mode="full") is True


def test_packs_corpus_trigger_wiring_folds_full_push_and_the_shared_helper() -> None:
    jobs = _packs_jobs()
    expr = jobs["changes"]["outputs"]["corpus"]
    assert "inputs.mode == 'full'" in expr
    assert "github.event_name == 'push'" in expr
    assert "steps.corpus.outputs.selected" in expr
    _assert_trigger_is_built_in_or_corpus(jobs[_CORPUS_JOB]["if"], _CORPUS_JOB)


def test_packs_corpus_lane_is_advisory_and_sole_owner() -> None:
    jobs = _packs_jobs()
    # JOB-level continue-on-error: the fleet verdict reads the Packs run conclusion.
    assert jobs[_CORPUS_JOB].get("continue-on-error") is True, "the Packs corpus job must be advisory"
    assert _CORPUS_JOB not in jobs["packs-gate"]["needs"], "an advisory corpus job must stay out of packs-gate.needs"
    duplicates = [
        gate.label() for gate in gc.parse_workflow(_ROUTER) if gate.marker_expr and re.search(r"(?<!not )\bcorpus\b", gate.marker_expr) and not gate.paths
    ]
    assert not duplicates, f"a whole-tree router corpus run duplicates the sole Packs owner: {duplicates}"


def test_packs_corpus_command_shape_four_workers_live_cov_no_quiet() -> None:
    job = _packs_jobs()[_CORPUS_JOB]
    run_text = "\n".join(str(step.get("run", "")) for step in job["steps"])
    pytest_line = next(line for line in run_text.splitlines() if "pytest" in line and "corpus" in line)
    assert "-n 4" in pytest_line and "-n auto" not in pytest_line
    assert " -q" not in pytest_line, "no -q: the log must show `created: 4/4 workers`"
    assert "--cov=charter.offering" in pytest_line
    assert "--cov=src/doctrine" not in pytest_line
    assert any(step.get("if") == "failure()" and "::warning::" in str(step.get("run", "")) for step in job["steps"]), "advisory failure notice step missing"


def test_pack_manifest_guard_fires_on_every_trigger_the_corpus_lane_fires_on() -> None:
    jobs = _packs_jobs()
    _assert_trigger_is_built_in_or_corpus(jobs[_MANIFEST_JOB]["if"], _MANIFEST_JOB)
    # The actual safety invariant: the blocking guard fires on EXACTLY the triggers the corpus lane fires on.
    assert _trigger_truth_table(jobs[_MANIFEST_JOB]["if"]) == _trigger_truth_table(jobs[_CORPUS_JOB]["if"])
    corpus_gate = next(g for g in gc.parse_workflow(_PACKS) if g.job == _CORPUS_JOB)
    assert _MANIFEST_TEST in corpus_gate.ignores, "the advisory corpus run must deselect the blocking pack-manifest guard"


def _run_selection_step(tmp_path: Path, *, event: str, changed_path: str) -> str:
    """Execute the Packs `corpus` selection step's REAL `run:` text in a throwaway git repo; return `selected`."""
    changes = _packs_jobs()["changes"]
    step = next(s for s in changes["steps"] if s.get("id") == _SELECTION_STEP_ID)
    script = str(step["run"]).replace("python3 scripts/ci/corpus_select.py", f"{sys.executable} {_REPO_ROOT / 'scripts' / 'ci' / 'corpus_select.py'}")
    git = shutil.which("git")
    bash = shutil.which("bash")
    assert git and bash

    hermetic_git = {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}  # never inherit the developer's gpgsign/hooks

    def run_git(*args: str) -> str:
        done = subprocess.run([git, *args], cwd=tmp_path, check=True, capture_output=True, text=True, env={**os.environ, **hermetic_git})
        return done.stdout.strip()

    tmp_path.mkdir(parents=True, exist_ok=True)
    run_git("init", "-q")
    run_git("config", "user.email", "ci@example.invalid")
    run_git("config", "user.name", "ci")
    (tmp_path / "README.md").write_text("base\n", encoding="utf-8")
    run_git("add", "-A")
    run_git("commit", "-q", "-m", "base")
    base = run_git("rev-parse", "HEAD")
    target = tmp_path / changed_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("changed\n", encoding="utf-8")
    run_git("add", "-A")
    run_git("commit", "-q", "-m", "change")
    head = run_git("rev-parse", "HEAD")

    github_output = tmp_path / "github_output.txt"
    env = {
        **{k: v for k, v in os.environ.items() if k in {"PATH", "HOME", "LANG", "LC_ALL"}},
        "EVENT_NAME": event,
        "BASE_SHA": base if event == "pull_request" else _NULL_SHA,
        "HEAD_SHA": head,
        "MODE": "pr",
        "PYTHONPATH": str(_REPO_ROOT),
        "GITHUB_OUTPUT": str(github_output),
        **hermetic_git,
    }
    subprocess.run([bash, "-c", script], cwd=tmp_path, env=env, check=True, capture_output=True, text=True)
    outputs = dict(line.split("=", 1) for line in github_output.read_text(encoding="utf-8").splitlines())
    return outputs["selected"]


def test_packs_selection_step_computes_the_diff_on_pull_request_and_fails_closed_otherwise(tmp_path: Path) -> None:
    """Behavioural pin: the step must really diff a pull_request, not fail closed to `true` for everyone.

    A prose-only pull_request selects nothing; the same diff on a push (no usable
    base) must fail closed to `true`; a corpus path on a pull_request still selects.
    If the `pull_request` guard on the diff is mutated away the first case flips to
    `true` and every PR silently runs the advisory corpus suite.
    """
    assert _run_selection_step(tmp_path / "pr_prose", event="pull_request", changed_path="docs/unrelated-note.md") == "false"
    assert _run_selection_step(tmp_path / "pr_corpus", event="pull_request", changed_path="packs/built-in/probe.md") == "true"
    assert _run_selection_step(tmp_path / "push", event="push", changed_path="docs/unrelated-note.md") == "true"
