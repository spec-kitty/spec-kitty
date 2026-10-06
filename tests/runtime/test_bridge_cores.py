"""Pure-core unit tests for ``runtime_bridge_cores`` (#2531 WP06, T024).

Three independent concerns, all in-memory / no I/O (NFR-003, SC-004):

1. **Non-vacuousness / compat-guard checks** — the seam actually defines the
   relocated tasks.md parse family and the guard-evaluation cluster. The
   per-file native-delegate assertion for the tracked guard/parse symbols
   (``_check_cli_guards`` / ``_check_composed_action_guard`` / the tracked
   parse helpers) was RETIRED in the #2557 dev-assist cleanup: that invariant
   was then covered family-wide by a dedicated frozen bridge compat-surface
   guard (itself later retired in #3285), so duplicating it here was redundant.
   This file now
   retains only the UNTRACKED parse-family identity check — the five helpers
   nothing patches ARE plain re-exports and DO satisfy the identity check
   (unique coverage the family guard's ``_``-private inventory does not track).

2. **Parse family** — realistic tasks.md fragments (production-shaped WP ids
   / headings / requirement refs) -> assert parsed structures, exercised
   directly against ``runtime_bridge_cores`` (no filesystem).

3. **``evaluate_guards`` fixtures** — one ``ArtifactPresenceSnapshot`` per
   mission family x guard branch (SC-007: content AND order asserted),
   including the two SC-007 highest-risk fixtures the WP prompt names
   explicitly: **both fail-closed defaults** (research's and documentation's
   unknown-action branches) and the **4-way ``tasks`` ``legacy_step_id``
   union** (``tasks_outline`` / ``tasks_packages`` / ``tasks_finalize`` /
   ``None``, all composed-vocabulary, contrasted against the CLI-native
   vocabulary for the same three substeps — the two vocabularies produce
   DIFFERENT messages for the same substep; see
   ``test_cli_native_and_composed_tasks_vocabularies_diverge``).
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from runtime.next import runtime_bridge as rb
from runtime.next import runtime_bridge_cores as cores
from runtime.next.runtime_bridge_io import ArtifactPresenceSnapshot
from specify_cli.requirement_mapping import grammar

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# ---------------------------------------------------------------------------
# 1. Non-vacuousness / compat-guard checks
# ---------------------------------------------------------------------------

# WP18 (#2561): the five ``runtime_bridge_cores`` parse-family helpers no
# longer carry a ``runtime_bridge`` façade re-export — every caller reaches
# them directly on ``cores`` (nothing patched them via the façade path). The
# retired ``test_untracked_parse_helpers_are_identity_reexports`` asserted the
# now-removed re-export identity; the parse family stays covered below via the
# ``cores.<name>`` call surface.


def test_parse_helpers_are_defined_on_the_cores_seam() -> None:
    """Non-vacuousness: the parse family lives on the ``cores`` seam (their
    canonical home after WP18 retired the runtime_bridge re-exports)."""
    for name in (
        "_extract_wp_heading",
        "_collect_requirement_refs_for_section",
        "_iter_requirement_refs",
        "_requirement_inline_refs_suffix",
        "_is_requirement_heading",
    ):
        assert callable(getattr(cores, name)), f"{name} is not defined on the cores seam"
        assert not hasattr(rb, name), f"{name} unexpectedly still re-exported on runtime_bridge"


def test_evaluate_guards_is_a_real_function_on_cores() -> None:
    assert callable(cores.evaluate_guards)
    assert cores.evaluate_guards.__module__ == cores.__name__


# ---------------------------------------------------------------------------
# 2. Parse family — realistic tasks.md fragments
# ---------------------------------------------------------------------------

_REALISTIC_TASKS_MD = """\
## WP01: Writeside placement strangler

### Requirement Refs
- FR-001
- FR-002, NFR-003

Some prose in between.

## WP02 - Rawjoin adoption

Requirement: FR-004

## WP03: Docs

No requirement refs here.
"""


def test_extract_wp_heading_recognizes_wp_prefixed_heading() -> None:
    # matched_prefix_len is the offset of the char just past the WP digits
    # (here: "## WP01" is 7 chars -- '#','#',' ','W','P','0','1').
    assert cores._extract_wp_heading("## WP01: Writeside placement strangler\n") == ("WP01", 7)


def test_extract_wp_heading_rejects_non_wp_heading() -> None:
    assert cores._extract_wp_heading("## Overview\n") is None


def test_parse_wp_sections_from_tasks_md_splits_on_headings() -> None:
    sections = cores._parse_wp_sections_from_tasks_md(_REALISTIC_TASKS_MD)
    assert set(sections) == {"WP01", "WP02", "WP03"}
    assert "Requirement Refs" in sections["WP01"]
    assert "WP03" not in sections["WP01"]


def test_parse_requirement_refs_from_tasks_md_collects_per_wp_refs() -> None:
    refs = cores._parse_requirement_refs_from_tasks_md(_REALISTIC_TASKS_MD, grammar=grammar)
    assert refs["WP01"] == ["FR-001", "FR-002", "NFR-003"]
    assert refs["WP02"] == ["FR-004"]
    assert refs["WP03"] == []


# ---------------------------------------------------------------------------
# 3. RequirementMappingFacts / _evaluate_requirement_mapping
# ---------------------------------------------------------------------------


def test_evaluate_requirement_mapping_all_satisfied_returns_empty() -> None:
    facts = cores.RequirementMappingFacts(
        spec_requirement_ids=frozenset({"FR-001", "FR-002"}),
        functional_requirement_ids=frozenset({"FR-001", "FR-002"}),
        wp_ids=("WP01", "WP02"),
        wp_requirement_refs={"WP01": ("FR-001",), "WP02": ("FR-002",)},
        feature_dir_name="042-compat-guard",
        grammar=grammar,
    )
    assert cores._evaluate_requirement_mapping(facts) == []


def test_evaluate_requirement_mapping_reports_missing_rejected_and_unmapped_in_order() -> None:
    facts = cores.RequirementMappingFacts(
        spec_requirement_ids=frozenset({"FR-001", "FR-002"}),
        functional_requirement_ids=frozenset({"FR-001", "FR-002"}),
        wp_ids=("WP01", "WP02", "WP03"),
        wp_requirement_refs={
            "WP01": (),  # missing
            "WP02": ("FR-999",),  # rejected: unknown_spec_id
            # WP03 absent entirely from the mapping -> also missing
        },
        feature_dir_name="042-compat-guard",
        grammar=grammar,
    )
    [message] = cores._evaluate_requirement_mapping(facts)
    assert message.startswith("Requirement mapping incomplete before finalize-tasks: ")
    # WP02 has NO accepted ref (its only ref, FR-999, is rejected as
    # unknown_spec_id) -- WP04's rule (T021 step 6): a WP whose refs are
    # all rejected for a failing reason fails for that reason AND is
    # reported missing, so WP02 joins WP01/WP03 here too.
    assert "missing refs for WPs: WP01, WP02, WP03" in message
    assert "rejected refs: WP02: FR-999 (unknown_spec_id)" in message
    assert "unmapped FRs: FR-001, FR-002" in message
    assert "--mission 042-compat-guard --json" in message
    # Order: missing, then rejected, then unmapped (verbatim port of the
    # pre-WP04 ``details`` append order; only the middle bucket's wording
    # changed, FR-010).
    missing_idx = message.index("missing refs")
    rejected_idx = message.index("rejected refs")
    unmapped_idx = message.index("unmapped FRs")
    assert missing_idx < rejected_idx < unmapped_idx


# ---------------------------------------------------------------------------
# 3b. #3394 negative-space regression pins — these must stay [] (non-blocking)
# both before and after any requirement-mapping change; that is the whole
# point of #3394's fix (dfec9d7e2/2a1c9b9d7): declared-shape scoping, not a
# doc-wide raw-token block.
# ---------------------------------------------------------------------------


def test_evaluate_requirement_mapping_zero_declared_zero_raw_tokens_does_not_block() -> None:
    """The genuinely empty case (no formal requirements at all -- zero
    declared ids, zero WPs) must NOT block: there is nothing to be missing."""
    facts = cores.RequirementMappingFacts(
        spec_requirement_ids=frozenset(),
        functional_requirement_ids=frozenset(),
        wp_ids=(),
        wp_requirement_refs={},
        feature_dir_name="042-no-requirements",
        grammar=grammar,
    )
    assert cores._evaluate_requirement_mapping(facts) == []


def test_evaluate_requirement_mapping_3394_repro_shape_does_not_block() -> None:
    """THE regression pin: #3394's actual repro shape -- three FRs DECLARED
    in a Requirements table, plus a mid-sentence CITATION of a foreign
    FR-021 elsewhere in prose (never declared) -- must NOT block. Every
    declared FR is mapped to its WP, so the missing/unknown/unmapped checks
    are all silent; the foreign citation is simply not this spec's concern
    (that scoping lives in ``specify_cli.requirement_mapping.
    parse_requirement_ids_from_spec_md``, upstream of this pure core)."""
    facts = cores.RequirementMappingFacts(
        spec_requirement_ids=frozenset({"FR-001", "FR-002", "FR-003"}),
        functional_requirement_ids=frozenset({"FR-001", "FR-002", "FR-003"}),
        wp_ids=("WP01",),
        wp_requirement_refs={"WP01": ("FR-001", "FR-002", "FR-003")},
        feature_dir_name="3394-repro",
        grammar=grammar,
    )
    assert cores._evaluate_requirement_mapping(facts) == []


# ---------------------------------------------------------------------------
# 3c. WP04 (requirement-id-grammar-01M3NRCA) — per-ref verdicts (FR-019), the
# injected-grammar Protocol, and the no-default pin. Every refusal below has
# a same-fixture positive control (Test Strategy: Non-vacuity).
# ---------------------------------------------------------------------------


def test_unknown_sibling_never_unmaps_a_valid_ref() -> None:
    facts = cores.RequirementMappingFacts(
        spec_requirement_ids=frozenset({"FR-001"}),
        functional_requirement_ids=frozenset({"FR-001"}),
        wp_ids=("WP01",),
        wp_requirement_refs={"WP01": ("FR-001", "FR-999")},
        feature_dir_name="042-per-ref",
        grammar=grammar,
    )
    [message] = cores._evaluate_requirement_mapping(facts)
    assert "rejected refs: WP01: FR-999 (unknown_spec_id)" in message
    assert "unmapped FRs" not in message


def test_malformed_sibling_never_unmaps_a_valid_ref() -> None:
    facts = cores.RequirementMappingFacts(
        spec_requirement_ids=frozenset({"FR-001"}),
        functional_requirement_ids=frozenset({"FR-001"}),
        wp_ids=("WP01",),
        wp_requirement_refs={"WP01": ("FR-001", "C-007-mission")},
        feature_dir_name="042-per-ref",
        grammar=grammar,
    )
    [message] = cores._evaluate_requirement_mapping(facts)
    assert "rejected refs: WP01: C-007-mission (malformed)" in message
    assert "unmapped FRs" not in message


def test_foreign_qualified_sibling_never_fails_bare_undeclared_does() -> None:
    """Positive control: the SAME bare id, undeclared, fails as
    ``unknown_spec_id`` -- proving the foreign case above is not vacuous."""
    foreign_facts = cores.RequirementMappingFacts(
        spec_requirement_ids=frozenset({"FR-001"}),
        functional_requirement_ids=frozenset({"FR-001"}),
        wp_ids=("WP01",),
        wp_requirement_refs={"WP01": ("FR-001", "other-mission-01KAAAAA#FR-013")},
        feature_dir_name="042-foreign",
        grammar=grammar,
    )
    assert cores._evaluate_requirement_mapping(foreign_facts) == []

    bare_facts = cores.RequirementMappingFacts(
        spec_requirement_ids=frozenset({"FR-001"}),
        functional_requirement_ids=frozenset({"FR-001"}),
        wp_ids=("WP01",),
        wp_requirement_refs={"WP01": ("FR-001", "FR-013")},
        feature_dir_name="042-foreign",
        grammar=grammar,
    )
    [message] = cores._evaluate_requirement_mapping(bare_facts)
    assert "rejected refs: WP01: FR-013 (unknown_spec_id)" in message


def test_unreferenced_declared_sc_does_not_fail_unmapped_fr_does() -> None:
    """Positive control: an unmapped FR on the same shape still fails --
    proving the clean SC-only pass above is not vacuous."""
    clean_facts = cores.RequirementMappingFacts(
        spec_requirement_ids=frozenset({"FR-001", "SC-001"}),
        functional_requirement_ids=frozenset({"FR-001"}),
        wp_ids=("WP01",),
        wp_requirement_refs={"WP01": ("FR-001",)},
        feature_dir_name="042-sc",
        grammar=grammar,
    )
    assert cores._evaluate_requirement_mapping(clean_facts) == []

    unmapped_facts = cores.RequirementMappingFacts(
        spec_requirement_ids=frozenset({"FR-001", "FR-002", "SC-001"}),
        functional_requirement_ids=frozenset({"FR-001", "FR-002"}),
        wp_ids=("WP01",),
        wp_requirement_refs={"WP01": ("FR-001",)},
        feature_dir_name="042-sc",
        grammar=grammar,
    )
    [message] = cores._evaluate_requirement_mapping(unmapped_facts)
    assert "unmapped FRs: FR-002" in message


def test_uppercase_suffix_ref_matches_lowercase_declared_id() -> None:
    """US2 AS4: an uppercase-suffix ref (``FR-006A``) matches the declared
    lowercase-suffix id (``FR-006a``)."""
    facts = cores.RequirementMappingFacts(
        spec_requirement_ids=frozenset({"FR-006a"}),
        functional_requirement_ids=frozenset({"FR-006a"}),
        wp_ids=("WP01",),
        wp_requirement_refs={"WP01": ("FR-006A",)},
        feature_dir_name="042-suffix",
        grammar=grammar,
    )
    assert cores._evaluate_requirement_mapping(facts) == []


def test_foreign_only_wp_is_missing_sc_only_wp_is_not() -> None:
    """T021 step 6 / Decision Moment ``01M3NYFZ1P6QBD2DX4DVDA323W``: a WP
    whose only ref is foreign-qualified is 'missing' (a citation of another
    mission's id traces nothing here); a WP whose only ref is a declared SC
    is not -- the positive control proving the rule discriminates."""
    foreign_only = cores.RequirementMappingFacts(
        spec_requirement_ids=frozenset({"FR-001"}),
        functional_requirement_ids=frozenset({"FR-001"}),
        wp_ids=("WP01", "WP02"),
        wp_requirement_refs={
            "WP01": ("FR-001",),
            "WP02": ("other-mission-01KAAAAA#FR-013",),
        },
        feature_dir_name="042-missing",
        grammar=grammar,
    )
    [message] = cores._evaluate_requirement_mapping(foreign_only)
    assert "missing refs for WPs: WP02" in message
    assert "rejected refs" not in message

    sc_only = cores.RequirementMappingFacts(
        spec_requirement_ids=frozenset({"FR-001", "SC-001"}),
        functional_requirement_ids=frozenset({"FR-001"}),
        wp_ids=("WP01", "WP02"),
        wp_requirement_refs={
            "WP01": ("FR-001",),
            "WP02": ("SC-001",),
        },
        feature_dir_name="042-missing",
        grammar=grammar,
    )
    assert cores._evaluate_requirement_mapping(sc_only) == []


class _StubRejectAllGrammar:
    """A minimal stub satisfying ``RequirementGrammarLike`` structurally,
    whose ``classify`` rejects every ref as ``unknown_spec_id`` regardless
    of ``declared`` -- proves the verdict flows only through the injected
    object, with no hidden local rule in the cores."""

    FAILING_REASONS = frozenset({"unknown_spec_id"})

    def find_all(self, text: str, *, spec_scan: bool) -> list[Any]:
        return []

    def classify(self, raw: str, declared: object) -> Any:
        return grammar.Rejected(raw, "unknown_spec_id")


def test_injection_is_load_bearing_stub_grammar_rejects_everything() -> None:
    facts = cores.RequirementMappingFacts(
        spec_requirement_ids=frozenset({"FR-001"}),
        functional_requirement_ids=frozenset({"FR-001"}),
        wp_ids=("WP01",),
        wp_requirement_refs={"WP01": ("FR-001",)},
        feature_dir_name="042-stub",
        grammar=_StubRejectAllGrammar(),
    )
    [message] = cores._evaluate_requirement_mapping(facts)
    assert "rejected refs: WP01: FR-001 (unknown_spec_id)" in message
    assert "missing refs for WPs: WP01" in message


def test_requirement_mapping_facts_grammar_field_has_no_default() -> None:
    import dataclasses

    grammar_field = next(f for f in dataclasses.fields(cores.RequirementMappingFacts) if f.name == "grammar")
    assert grammar_field.default is dataclasses.MISSING
    assert grammar_field.default_factory is dataclasses.MISSING


def test_parse_family_grammar_parameter_has_no_default() -> None:
    import inspect

    for fn in (
        cores._parse_requirement_refs_from_tasks_md,
        cores._collect_requirement_refs_for_section,
        cores._iter_requirement_refs,
    ):
        param = inspect.signature(fn).parameters["grammar"]
        assert param.default is inspect.Parameter.empty, f"{fn.__name__} grammar param has a default"


def test_collect_requirement_refs_for_section_real_grammar_canonicalizes() -> None:
    section = "\nRequirement Refs: SC-001, FR-006a, fr-002\n"
    assert cores._collect_requirement_refs_for_section(section, grammar=grammar) == [
        "SC-001",
        "FR-006a",
        "FR-002",
    ]


# ---------------------------------------------------------------------------
# 4. evaluate_guards — software-dev family (CLI-native vocabulary)
# ---------------------------------------------------------------------------


def _snapshot(
    *,
    present_artifacts: frozenset[str] = frozenset(),
    status_facts: Mapping[str, Any] | None = None,
    mission_family: str = "software-dev",
    step_id: str,
    legacy_step_id: str | None = None,
    wp_advance_ready: bool | None = None,
) -> ArtifactPresenceSnapshot:
    base_status_facts: dict[str, Any] = {
        "tasks_dir_is_dir": False,
        "wp_ids": (),
        "wp_lane_raw": {},
        "wp_dependencies_present": {},
        "wp_dependency_records": (),
        "requirement_mapping_failures": (),
        "bare_prose_requirement_failures": (),
        "occurrence_gate_failures": (),
        "source_documented_count": 0,
        "publication_approved": False,
        "has_generated_docs": False,
    }
    if status_facts:
        base_status_facts.update(status_facts)
    return ArtifactPresenceSnapshot(
        present_artifacts=present_artifacts,
        status_facts=base_status_facts,
        mission_family=mission_family,
        step_id=step_id,
        legacy_step_id=legacy_step_id,
        wp_advance_ready=wp_advance_ready,
    )


def test_specify_guard_missing_and_present() -> None:
    assert cores.evaluate_guards(_snapshot(step_id="specify")) == ["Required artifact missing: spec.md"]
    assert cores.evaluate_guards(_snapshot(present_artifacts=frozenset({"spec.md"}), step_id="specify")) == []


def test_plan_guard_missing_and_present() -> None:
    assert cores.evaluate_guards(_snapshot(step_id="plan")) == ["Required artifact missing: plan.md"]
    assert cores.evaluate_guards(_snapshot(present_artifacts=frozenset({"plan.md"}), step_id="plan")) == []


def test_cli_native_tasks_outline_only_checks_tasks_md() -> None:
    assert cores.evaluate_guards(_snapshot(step_id="tasks_outline")) == ["Required artifact missing: tasks.md"]
    assert cores.evaluate_guards(_snapshot(present_artifacts=frozenset({"tasks.md"}), step_id="tasks_outline")) == []


def test_cli_native_tasks_packages_missing_files_message() -> None:
    assert cores.evaluate_guards(_snapshot(step_id="tasks_packages")) == ["Required: at least one tasks/WP*.md file"]


def test_cli_native_tasks_packages_extends_requirement_mapping_failures() -> None:
    snapshot = _snapshot(
        present_artifacts=frozenset({"tasks_wp_files"}),
        status_facts={
            "tasks_dir_is_dir": True,
            "requirement_mapping_failures": ("missing refs for WPs: WP01",),
        },
        step_id="tasks_packages",
    )
    assert cores.evaluate_guards(snapshot) == ["missing refs for WPs: WP01"]


def test_cli_native_tasks_finalize_dir_missing_message_distinct_from_packages() -> None:
    """The dir-missing message for tasks_finalize differs from the
    tasks_packages/composed 'at least one WP*.md file' message -- do not
    unify these two strings."""
    assert cores.evaluate_guards(_snapshot(step_id="tasks_finalize")) == ["Required: tasks/ directory with finalized WP files"]


def test_cli_native_tasks_finalize_empty_wp_files_message() -> None:
    snapshot = _snapshot(status_facts={"tasks_dir_is_dir": True}, step_id="tasks_finalize")
    assert cores.evaluate_guards(snapshot) == ["Required: at least one tasks/WP*.md file"]


def test_cli_native_tasks_finalize_missing_dependency_uses_full_stem_breaks_on_first() -> None:
    snapshot = _snapshot(
        present_artifacts=frozenset({"tasks_wp_files"}),
        status_facts={
            "tasks_dir_is_dir": True,
            "wp_dependency_records": (("WP01-writeside", True), ("WP02-rawjoin", False), ("WP03-docs", False)),
        },
        step_id="tasks_finalize",
    )
    assert cores.evaluate_guards(snapshot) == ["WP WP02-rawjoin missing 'dependencies' in frontmatter (run 'spec-kitty agent mission finalize-tasks')"]


def test_cli_native_tasks_finalize_occurrence_gate_always_appended() -> None:
    snapshot = _snapshot(
        present_artifacts=frozenset({"tasks_wp_files"}),
        status_facts={
            "tasks_dir_is_dir": True,
            "wp_dependency_records": (("WP01-writeside", True),),
            "occurrence_gate_failures": ("occurrence classification incomplete",),
        },
        step_id="tasks_finalize",
    )
    assert cores.evaluate_guards(snapshot) == ["occurrence classification incomplete"]


def test_implement_and_review_use_wp_advance_ready() -> None:
    assert cores.evaluate_guards(_snapshot(step_id="implement", wp_advance_ready=True)) == []
    assert cores.evaluate_guards(_snapshot(step_id="implement", wp_advance_ready=False)) == [
        "Not all work packages have required status (for_review, approved, or done)"
    ]
    assert cores.evaluate_guards(_snapshot(step_id="review", wp_advance_ready=True)) == []
    assert cores.evaluate_guards(_snapshot(step_id="review", wp_advance_ready=False)) == ["Not all work packages are approved or done"]


def test_unmatched_step_id_returns_empty() -> None:
    assert cores.evaluate_guards(_snapshot(step_id="not-a-real-step")) == []


# ---------------------------------------------------------------------------
# 5. evaluate_guards — the composed ``tasks`` vocabulary + the 4-way
#    legacy_step_id union (SC-007 highest-risk fixture, named explicitly)
# ---------------------------------------------------------------------------


def test_composed_tasks_legacy_outline_only_checks_tasks_md() -> None:
    snapshot = _snapshot(step_id="tasks", legacy_step_id="tasks_outline")
    assert cores.evaluate_guards(snapshot) == ["Required artifact missing: tasks.md"]


def test_composed_tasks_legacy_packages_checks_tasks_md_and_requirement_mapping() -> None:
    # tasks.md IS present here, so only the requirement-mapping fact surfaces.
    snapshot = _snapshot(
        present_artifacts=frozenset({"tasks.md", "tasks_wp_files"}),
        status_facts={
            "tasks_dir_is_dir": True,
            "requirement_mapping_failures": ("unmapped FRs: FR-009",),
        },
        step_id="tasks",
        legacy_step_id="tasks_packages",
    )
    assert cores.evaluate_guards(snapshot) == ["unmapped FRs: FR-009"]


def test_composed_tasks_legacy_packages_missing_tasks_md_and_wp_files_both_appended() -> None:
    """Composed tasks_packages appends BOTH the tasks.md-missing message AND
    the WP-files-missing message (two independent checks, not else-if) --
    unlike the CLI-native tasks_packages branch, which only ever emits ONE
    of these two."""
    snapshot = _snapshot(step_id="tasks", legacy_step_id="tasks_packages")
    assert cores.evaluate_guards(snapshot) == [
        "Required artifact missing: tasks.md",
        "Required: at least one tasks/WP*.md file",
    ]


@pytest.mark.parametrize("legacy_step_id", ["tasks_finalize", None])
def test_composed_tasks_terminal_union_of_all_three_legacy_checks(legacy_step_id: str | None) -> None:
    """The 4-way legacy_step_id union's terminal branch (tasks_finalize OR
    the composition-only None) -- SC-007 highest-risk fixture. Demands the
    UNION: tasks.md check + WP-files check + requirement-mapping +
    dependency-field check + occurrence-gate, all in the pinned order."""
    snapshot = _snapshot(
        status_facts={
            "requirement_mapping_failures": ("missing refs for WPs: WP01",),
            "wp_dependency_records": (("WP01-writeside", False),),
            "occurrence_gate_failures": ("occurrence classification incomplete",),
        },
        step_id="tasks",
        legacy_step_id=legacy_step_id,
    )
    assert cores.evaluate_guards(snapshot) == [
        "Required artifact missing: tasks.md",
        "Required: at least one tasks/WP*.md file",
        "occurrence classification incomplete",
    ]


def test_composed_tasks_terminal_ready_reports_requirement_and_dependency_then_occurrence() -> None:
    snapshot = ArtifactPresenceSnapshot(
        present_artifacts=frozenset({"tasks.md", "tasks_wp_files"}),
        status_facts={
            "tasks_dir_is_dir": True,
            "requirement_mapping_failures": ("missing refs for WPs: WP02",),
            "wp_dependency_records": (("WP01-writeside", True), ("WP02-rawjoin", False)),
            "occurrence_gate_failures": ("occurrence classification incomplete",),
        },
        mission_family="software-dev",
        step_id="tasks",
        legacy_step_id=None,
    )
    assert cores.evaluate_guards(snapshot) == [
        "missing refs for WPs: WP02",
        "WP WP02-rawjoin missing 'dependencies' in frontmatter (run 'spec-kitty agent mission finalize-tasks')",
        "occurrence classification incomplete",
    ]


# ---------------------------------------------------------------------------
# 4b. #3396 bare-prose requirement wiring — per-guard teeth tests (WP05,
# FR-002/FR-010/NFR-005). Each of the four guard functions FR-003's audit
# names must read the new ``bare_prose_requirement_failures`` status_facts
# key BEFORE its own dir-readiness short-circuit — this is the exact
# ordering fix the reverted ``3823f2b00``-shaped wiring lacked (that revert
# read the analogous ``requirement_mapping_failures`` fact AFTER
# ``_tasks_dir_ready``, so it was inert whenever zero WP files existed). Each
# test below constructs a snapshot in the "guard would otherwise
# short-circuit" configuration and asserts the bare-prose failure still
# surfaces — it fails if that specific guard's wiring alone is reverted.
# ---------------------------------------------------------------------------

_BARE_PROSE_TEETH_MESSAGE = "Bare-prose requirement id(s) found, uncounted by requirement mapping: FR-001, FR-002."


def test_cli_native_tasks_packages_guard_reads_bare_prose_before_tasks_dir_ready() -> None:
    """Teeth test 1/4 — zero WP files (``_tasks_dir_ready`` is False)."""
    snapshot = _snapshot(
        status_facts={"bare_prose_requirement_failures": (_BARE_PROSE_TEETH_MESSAGE,)},
        step_id="tasks_packages",
    )
    assert cores.evaluate_guards(snapshot) == [
        _BARE_PROSE_TEETH_MESSAGE,
        "Required: at least one tasks/WP*.md file",
    ]


def test_cli_native_tasks_finalize_guard_reads_bare_prose_unconditionally() -> None:
    """Teeth test 2/4 — ``_evaluate_tasks_finalize_guard`` has NO
    ``_tasks_dir_ready`` call today (it uses its own inline
    ``tasks_dir_is_dir``/``tasks_wp_files`` branches); confirm the new fact
    is read as the first statement, independent of those branches."""
    snapshot = _snapshot(
        status_facts={"bare_prose_requirement_failures": (_BARE_PROSE_TEETH_MESSAGE,)},
        step_id="tasks_finalize",
    )
    assert cores.evaluate_guards(snapshot) == [
        _BARE_PROSE_TEETH_MESSAGE,
        "Required: tasks/ directory with finalized WP files",
    ]


def test_composed_tasks_packages_guard_reads_bare_prose_before_tasks_dir_ready() -> None:
    """Teeth test 3/4 — tasks.md present, zero WP files."""
    snapshot = _snapshot(
        present_artifacts=frozenset({"tasks.md"}),
        status_facts={"bare_prose_requirement_failures": (_BARE_PROSE_TEETH_MESSAGE,)},
        step_id="tasks",
        legacy_step_id="tasks_packages",
    )
    assert cores.evaluate_guards(snapshot) == [
        _BARE_PROSE_TEETH_MESSAGE,
        "Required: at least one tasks/WP*.md file",
    ]


def test_composed_tasks_terminal_guard_reads_bare_prose_before_tasks_dir_ready() -> None:
    """Teeth test 4/4 — the composed terminal/union branch, tasks.md absent
    and zero WP files (the highest-risk SC-007 fixture shape)."""
    snapshot = _snapshot(
        status_facts={"bare_prose_requirement_failures": (_BARE_PROSE_TEETH_MESSAGE,)},
        step_id="tasks",
        legacy_step_id="tasks_finalize",
    )
    assert cores.evaluate_guards(snapshot) == [
        _BARE_PROSE_TEETH_MESSAGE,
        "Required artifact missing: tasks.md",
        "Required: at least one tasks/WP*.md file",
    ]


def test_cli_native_and_composed_tasks_vocabularies_diverge_for_same_substep() -> None:
    """tasks_finalize (CLI-native) and tasks/legacy_step_id=tasks_finalize
    (composed) are NOT interchangeable -- the composed branch also checks
    tasks.md existence and requirement-mapping; the CLI-native branch does
    neither. Pinning both distinctly guards against a future "helpful"
    unification that would silently change guard_failures."""
    empty_tasks_dir_status = {"tasks_dir_is_dir": False}
    cli_native = cores.evaluate_guards(_snapshot(status_facts=empty_tasks_dir_status, step_id="tasks_finalize"))
    composed = cores.evaluate_guards(_snapshot(status_facts=empty_tasks_dir_status, step_id="tasks", legacy_step_id="tasks_finalize"))
    assert cli_native == ["Required: tasks/ directory with finalized WP files"]
    assert composed == [
        "Required artifact missing: tasks.md",
        "Required: at least one tasks/WP*.md file",
    ]
    assert cli_native != composed


# ---------------------------------------------------------------------------
# 6. evaluate_guards — research mission family (incl. its fail-closed default)
# ---------------------------------------------------------------------------


def test_research_scoping_methodology_synthesis_single_artifact_checks() -> None:
    assert cores.evaluate_guards(_snapshot(mission_family="research", step_id="scoping")) == ["Required artifact missing: spec.md"]
    assert cores.evaluate_guards(_snapshot(mission_family="research", step_id="methodology")) == ["Required artifact missing: plan.md"]
    assert cores.evaluate_guards(_snapshot(mission_family="research", step_id="synthesis")) == ["Required artifact missing: findings.md"]


def test_research_gathering_both_conditions_independently_appended() -> None:
    snapshot = _snapshot(mission_family="research", step_id="gathering")
    assert cores.evaluate_guards(snapshot) == [
        "Required artifact missing: source-register.csv",
        "Insufficient sources documented (need >=3)",
    ]
    ready = _snapshot(
        present_artifacts=frozenset({"source-register.csv"}),
        status_facts={"source_documented_count": 3},
        mission_family="research",
        step_id="gathering",
    )
    assert cores.evaluate_guards(ready) == []


def test_research_output_both_conditions_independently_appended() -> None:
    snapshot = _snapshot(mission_family="research", step_id="output")
    assert cores.evaluate_guards(snapshot) == [
        "Required artifact missing: report.md",
        "Publication approval gate not passed",
    ]


def test_research_unknown_action_fail_closed_default() -> None:
    """SC-007 highest-risk fixture #1 -- the research fail-closed default
    (v1 P1 silent-pass fix): ANY unrecognized action must produce a
    non-empty failures list, never an empty (silent-pass) one."""
    snapshot = _snapshot(
        present_artifacts=frozenset({"spec.md", "plan.md", "tasks.md", "source-register.csv", "findings.md", "report.md"}),
        status_facts={"source_documented_count": 5, "publication_approved": True},
        mission_family="research",
        step_id="not-a-real-research-action",
    )
    assert cores.evaluate_guards(snapshot) == ["No guard registered for research action: not-a-real-research-action"]


# ---------------------------------------------------------------------------
# 7. evaluate_guards — documentation mission family (its fail-closed default)
# ---------------------------------------------------------------------------


def test_documentation_single_artifact_checks() -> None:
    assert cores.evaluate_guards(_snapshot(mission_family="documentation", step_id="discover")) == ["Required artifact missing: spec.md"]
    assert cores.evaluate_guards(_snapshot(mission_family="documentation", step_id="audit")) == ["Required artifact missing: gap-analysis.md"]
    assert cores.evaluate_guards(_snapshot(mission_family="documentation", step_id="design")) == ["Required artifact missing: plan.md"]
    assert cores.evaluate_guards(_snapshot(mission_family="documentation", step_id="validate")) == ["Required artifact missing: audit-report.md"]
    assert cores.evaluate_guards(_snapshot(mission_family="documentation", step_id="publish")) == ["Required artifact missing: release.md"]


def test_documentation_generate_custom_message() -> None:
    snapshot = _snapshot(mission_family="documentation", step_id="generate")
    assert cores.evaluate_guards(snapshot) == ["Required artifact missing: docs/**/*.md (no Markdown files found under docs/)"]
    ready = _snapshot(status_facts={"has_generated_docs": True}, mission_family="documentation", step_id="generate")
    assert cores.evaluate_guards(ready) == []


def test_documentation_accept_is_terminal_noop() -> None:
    assert cores.evaluate_guards(_snapshot(mission_family="documentation", step_id="accept")) == []


def test_documentation_unknown_action_fail_closed_default() -> None:
    """SC-007 highest-risk fixture #2 -- the documentation fail-closed
    default."""
    snapshot = _snapshot(mission_family="documentation", step_id="not-a-real-doc-action")
    assert cores.evaluate_guards(snapshot) == ["No guard registered for documentation action: not-a-real-doc-action"]


# ---------------------------------------------------------------------------
# 8. evaluate_guards -- "plan" mission family (issue #3386 RED pin, T001/FR-002)
#
# Today, "plan" is not special-cased in ``evaluate_guards``'s dispatch, so it
# falls through to ``_evaluate_software_dev_guards`` -- misfiring for
# ``review`` (the WP-iteration message instead of the terminal `[]`) and for
# ``research`` (an unconditional `[]`, ignoring `research.md`'s real
# presence). T003/T004 register a dedicated "plan" guard table
# (``_evaluate_plan_guards``) that fixes both.
# ---------------------------------------------------------------------------


def test_plan_review_guard_target_shape() -> None:
    """RED at base: 'plan'/'review' falls through to the software-dev
    WP-iteration guard (`wp_advance_ready` unset -> the WP-iteration failure
    message), not the terminal no-op `[]` a dedicated 'plan' guard table
    gives it (issue #3386's own title)."""
    assert cores.evaluate_guards(_snapshot(mission_family="plan", step_id="review")) == []


def test_plan_research_guard_absent_and_present() -> None:
    """RED at base for the absent-artifact case only (TASKS-VERIFY-001):
    'plan'/'research' currently returns `[]` unconditionally (falls through
    to software-dev's bare catch-all `return []`, since "research" is not one
    of software-dev's own step ids) regardless of research.md's real
    presence. The present-artifact assertion below already passes at base
    for that same wrong (unconditional) reason -- it is a companion
    target-shape assertion, not itself RED evidence."""
    assert cores.evaluate_guards(_snapshot(mission_family="plan", step_id="research")) == ["Required artifact missing: research.md"]
    assert (
        cores.evaluate_guards(
            _snapshot(
                mission_family="plan",
                step_id="research",
                present_artifacts=frozenset({"research.md"}),
            )
        )
        == []
    )


def test_plan_guard_specify_and_plan_branches_direct_dispatch() -> None:
    """Direct-dispatch coverage for ``_evaluate_plan_guards`` itself (not the
    full ``evaluate_guards`` dispatch) -- RED today via ``AttributeError``
    since ``_evaluate_plan_guards`` does not exist until T003 lands. A
    full-dispatch assertion alone would NOT catch an implementer swapping
    SPEC_ARTIFACT/PLAN_ARTIFACT between these two branches, because both
    branches coincidentally produce the same shape of output via two
    independent code paths (this function, and software-dev's fallthrough)
    both pre- and post-fix."""
    assert cores._evaluate_plan_guards(_snapshot(mission_family="plan", step_id="specify")) == ["Required artifact missing: spec.md"]
    assert cores._evaluate_plan_guards(_snapshot(mission_family="plan", step_id="specify", present_artifacts=frozenset({"spec.md"}))) == []
    assert cores._evaluate_plan_guards(_snapshot(mission_family="plan", step_id="plan")) == ["Required artifact missing: plan.md"]
    assert cores._evaluate_plan_guards(_snapshot(mission_family="plan", step_id="plan", present_artifacts=frozenset({"plan.md"}))) == []


def test_plan_guard_fail_closed_else_branch() -> None:
    """RED today via ``AttributeError`` (direct-call half) -- once T003
    lands, asserts the fail-closed message. The companion full-dispatch
    assertion is genuinely RED via full dispatch too (falls through to
    software-dev's catch-all `[]` today): it confirms
    ``_evaluate_plan_guards`` is actually *registered* in ``_GUARD_TABLES``
    under "plan", not merely correct in isolation."""
    assert cores._evaluate_plan_guards(_snapshot(mission_family="plan", step_id="not-a-real-plan-action")) == [
        "No guard registered for plan action: not-a-real-plan-action"
    ]
    assert cores.evaluate_guards(_snapshot(mission_family="plan", step_id="not-a-real-plan-action")) == [
        "No guard registered for plan action: not-a-real-plan-action"
    ]


# ---------------------------------------------------------------------------
# 9. evaluate_guards_strict / UnregisteredMissionFamilyError (T002, FR-011)
# ---------------------------------------------------------------------------


def test_evaluate_guards_strict_raises_for_unregistered_mission_family() -> None:
    """RED today via ``AttributeError`` -- neither ``evaluate_guards_strict``
    nor ``UnregisteredMissionFamilyError`` exists until T003 lands."""
    with pytest.raises(cores.UnregisteredMissionFamilyError):
        cores.evaluate_guards_strict(_snapshot(mission_family="totally-unregistered-family", step_id="review"))


def test_evaluate_guards_tolerant_wrapper_degrades_for_unregistered_mission_family() -> None:
    """Companion coverage for the tolerant ``evaluate_guards`` wrapper's own
    ``except UnregisteredMissionFamilyError: return []`` branch (T003) --
    distinct from the strict function above and from
    ``_check_cli_guards``/``_check_composed_action_guard`` (which bypass this
    wrapper entirely per IC-03/IC-04). Kept tolerant/public only for direct
    test callers per its own docstring, so this exercises that contract
    directly."""
    assert cores.evaluate_guards(_snapshot(mission_family="totally-unregistered-family", step_id="review")) == []


def test_check_cli_guards_propagates_unregistered_mission_family_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """RED today: ``_check_cli_guards`` ends with
    ``return _cores.evaluate_guards(snapshot)`` (the tolerant function),
    which currently returns the software-dev misfire (or `[]`), never
    raises. Once T003/T006 land, the strict lookup's
    ``UnregisteredMissionFamilyError`` must propagate OUT of
    ``_check_cli_guards`` itself -- not merely out of an isolated,
    unwired ``evaluate_guards_strict`` call."""

    def _fake_gather(
        feature_dir: Path,
        *,
        mission_family: str,
        step_id: str,
        legacy_step_id: str | None = None,
        repo_root: Path | None = None,
        owned: object | None = None,
    ) -> Any:
        return ArtifactPresenceSnapshot(
            present_artifacts=frozenset(),
            status_facts={},
            mission_family="totally-unregistered-family",
            step_id=step_id,
            legacy_step_id=legacy_step_id,
        )

    monkeypatch.setattr(rb._io_seam, "gather_artifact_presence", _fake_gather)
    with pytest.raises(cores.UnregisteredMissionFamilyError):
        rb._check_cli_guards("review", tmp_path)


# ---------------------------------------------------------------------------
# 10. evaluate_guards_strict — blocking_artifact_names dispatch branch
#     (WP01, FR-001/FR-002/FR-006, #3704 Part 1)
# ---------------------------------------------------------------------------
#
# Once ``_GUARD_TABLES`` misses (``snapshot.mission_family`` is unregistered),
# ``evaluate_guards_strict`` now branches on ``snapshot.blocking_artifact_names``:
# ``None`` (no manifest reachable at any tier) keeps the existing strict raise;
# a real (possibly empty) ``frozenset`` is genuinely evaluated by comparing it
# against ``snapshot.present_artifacts``, restoring the None-vs-frozenset()
# distinction SPEC-FRESH-001 requires (bare falsiness would silently collapse
# it, since ``frozenset()`` is falsy).


def test_evaluate_guards_strict_still_raises_when_blocking_artifact_names_is_none() -> None:
    """FR-002 outcome 1 / AC-3 / C-001 -- unchanged: an unregistered family
    with NO manifest reachable at any tier (``blocking_artifact_names is
    None``) still fails closed via the strict raise, exactly as before this
    WP's new branch existed."""
    snapshot = ArtifactPresenceSnapshot(
        present_artifacts=frozenset(),
        status_facts={},
        mission_family="totally-unregistered-family",
        step_id="whatever",
        blocking_artifact_names=None,
    )

    with pytest.raises(cores.UnregisteredMissionFamilyError):
        cores.evaluate_guards_strict(snapshot)


def test_evaluate_guards_strict_returns_empty_when_blocking_set_is_subset_of_present() -> None:
    """FR-002 outcome 2: a real, EMPTY ``frozenset`` (manifest resolved,
    nothing blocking at this step) must be reached via genuine evaluation --
    not a swallowed exception -- and return ``[]``. This is the crux of the
    None-vs-frozenset() distinction: ``if not snapshot.blocking_artifact_names``
    would treat this identically to the ``None`` case above; ``is None`` does
    not."""
    snapshot = ArtifactPresenceSnapshot(
        present_artifacts=frozenset(),
        status_facts={},
        mission_family="totally-unregistered-family",
        step_id="whatever",
        blocking_artifact_names=frozenset(),
    )

    assert cores.evaluate_guards_strict(snapshot) == []


def test_evaluate_guards_strict_reports_blocking_artifacts_not_yet_present() -> None:
    """FR-002 outcome 3: a non-empty ``blocking_artifact_names`` whose members
    are NOT a subset of ``present_artifacts`` returns a non-empty failure list
    naming the missing artifact(s)."""
    snapshot = ArtifactPresenceSnapshot(
        present_artifacts=frozenset({"already-here.md"}),
        status_facts={},
        mission_family="totally-unregistered-family",
        step_id="whatever",
        blocking_artifact_names=frozenset({"already-here.md", "still-missing.md"}),
    )

    assert cores.evaluate_guards_strict(snapshot) == ["still-missing.md"]
