"""Meta-test for architectural ratchet baselines (Slice F WP01, FR-110/FR-111).

This test is the canonical executable contract for the burn-down policy
pinned by C-004 / C-006 of the Slice F charter pack. It loads
``tests/architectural/_baselines.yaml`` and compares the recorded
per-test, per-category allowlist size against the live size of each
gated test module's allowlist symbol.

Failure semantics
-----------------
* **Growth above baseline** -> ``pytest.fail`` with a remediation hint
  (either remove the new allowlist entry or edit ``_baselines.yaml`` in
  the same PR with a justification comment).
* **Shrinkage below baseline** -> ``warnings.warn`` (informational; the
  ratchet does not fail on shrinkage so legitimate cleanup is not
  blocked, but it nudges the PR author to lock in the new lower bound).

The full schema and per-test invariants live in
``kitty-specs/slice-f-multi-context-extensibility-01KRX5C8/contracts/
ratchet-baseline-format.md``.

ATDD anchors (per ``atdd-coverage.md``):

* Scenario 6: ``test_growing_an_allowlist_above_baseline_fails``
* AC-6:       ``test_baseline_file_exists_with_required_keys``
              AND ``test_growth_fails_shrinkage_warns``
* AC-7:       ``test_no_dead_modules.test_category_7_grandfathered_at_most_seven_entries``
              (lives in the gated test module itself; see T007)

This file is committed RED in the WP01 T001 commit and turns GREEN as
T002-T007 land the baseline file, the per-category refactor, the three
Cat-7 deletions, and the Cat-7 baseline at 7.
"""

from __future__ import annotations

import importlib
import subprocess
import sys
import warnings
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest
import yaml
from pydantic import BaseModel

# FR-006: `fast` marks this sub-second gate for the fast tier. `architectural`
# is retained as the gate's home marker. Dual-marking here adds a routing
# home; it removes none.
pytestmark = [pytest.mark.architectural, pytest.mark.fast]

# Type of the built-in ``record_property`` fixture: records a (name, value)
# pair into the JUnit/report output. Used to route the report-only shrinkage
# diagnostic off the ``warnings`` channel (NFR-006) while preserving the signal.
RecordPropertyFn = Callable[[str, object], None]

# Dotted path of the round-trip contract module whose module-level
# ``_discover_examples()`` emits the legacy-contract-backfill ``UserWarning``s
# (``# pydantic_model:`` convention not yet backfilled on ~14 legacy contracts).
# That backfill is DEFERRED and out of this arch suite's scope (tracked in
# GH #2553); the diagnostic remains load-bearing when the contract suite runs
# directly (``pytest tests/contract/test_example_round_trip.py``). We import
# this module here only to read two integer-sized ratchet constants, so we
# scope-suppress its import-time warnings to keep the arch-suite warnings
# channel first-party-clean (NFR-006) WITHOUT silencing the signal at source.
_ROUND_TRIP_CONTRACT_MODULE = "tests.contract.test_example_round_trip"


# ---------------------------------------------------------------------------
# BaselinesFile Pydantic model (FR-141 / ratchet-baseline-format.md)
# ---------------------------------------------------------------------------
# This model is referenced by the FR-140 round-trip gate in
# ``tests/contract/test_example_round_trip.py`` via:
#   pydantic_model: tests.architectural.test_ratchet_baselines.BaselinesFile
#
# The schema is intentionally permissive at the top level (dict[str, Any])
# so it tolerates new per-test entries without requiring changes here.
# The individual values MUST be non-negative integers or mappings of them.
# ---------------------------------------------------------------------------

class _PerCategorySection(BaseModel):
    """A section with per-category integer baselines."""

    model_config = {"extra": "allow"}

    @classmethod
    def model_validate(cls, obj: Any, **kwargs: Any) -> _PerCategorySection:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if not isinstance(v, int) or v < 0:
                    raise ValueError(
                        f"Per-category baseline {k!r} must be a non-negative integer; got {v!r}"
                    )
        return super().model_validate(obj, **kwargs)


class BaselinesFile(BaseModel):
    """Pydantic model for ``tests/architectural/_baselines.yaml``.

    Each top-level key names a gated test module.  Values are either a
    single integer (for tests with one allowlist) or a mapping of
    per-category integer baselines (for tests with categorised allowlists).

    The schema is permissive (``extra="allow"``) to tolerate future gated
    test additions without requiring changes here.

    Slice F FR-141 / ratchet-baseline-format.md.
    """

    model_config = {"extra": "allow"}

    test_no_dead_modules: dict[str, int]
    test_migration_chain_integrity: dict[str, int]
    test_auth_transport_singleton: dict[str, int]
    test_example_round_trip: dict[str, int]


_BASELINES_PATH = Path(__file__).parent / "_baselines.yaml"

# Required top-level keys. Each names a test module whose ratchet is
# tracked. Sub-keys (per-category integers OR a single integer) are
# defined by the contract.
_REQUIRED_TOP_LEVEL_KEYS: frozenset[str] = frozenset(
    {
        "test_no_dead_modules",
        "test_migration_chain_integrity",
        "test_auth_transport_singleton",
        "test_example_round_trip",
        "test_no_inert_schema_slots",
        "test_reference_enum_ratchet",
        "test_egress_consent_boundary",
        "test_layer_rules",
        "test_runtime_charter_doctrine_boundary",
        "test_doctrine_census",
        "test_cli_error_surface_seam",
    }
)

# CLOSED grandfather set for top-level keys that no comparison reads. Now
# DRAINED to empty (FR-005): the sole tenant, `test_no_dead_symbols`, was an
# inert YAML block read by no comparison (RL-030), and both it and its whole
# YAML block were removed by mission `frozen-baseline-toll-reduction-01M0A42D`
# WP03. With the set empty, `test_no_unregistered_baseline_keys_are_added`
# rejects ANY unregistered top-level key: re-adding `test_no_dead_symbols`
# (or any inert key) now reds instead of being silently tolerated. The set is
# pinned empty by frozenset equality below, so re-widening it costs a visible
# diff in this file rather than a silent one in the YAML.
_GRANDFATHERED_UNREGISTERED_KEYS: frozenset[str] = frozenset()

# Per-category sub-keys for test_no_dead_modules (FR-112 refactor).
_REQUIRED_NO_DEAD_MODULES_CATEGORIES: frozenset[str] = frozenset(
    {
        "category_1_auto_discovered_migrations",
        "category_2_build_schema_generators",
        "category_3_external_cli_entrypoints",
        "category_4_backcompat_shims",
        "category_5_wp_in_flight_adapters",
        "category_6_frozen_runtime_reexports",
        "category_7_grandfathered_orphans",
    }
)

# Dotted path of the gated dead-module test whose per-category frozensets this
# meta-test introspects.
_NO_DEAD_MODULES_MODULE = "tests.architectural.test_no_dead_modules"

# FR-004: ``category_1`` is DERIVED, not YAML-pinned. The count of
# auto-discovered migration modules with no static importer is validated for
# *membership correctness* by ``test_no_dead_modules`` (which owns the
# hand-curated frozenset). Pinning its size here too was a double-charge: a
# routine new migration would red this ratchet with nothing to fix. So this
# meta-test derives the ``category_1`` baseline from the live frozenset length,
# making the growth/shrink check for that one category a no-op while the
# frozenset itself remains the single authority. The ``category_1_...`` integer
# in ``_baselines.yaml`` is retained as a decorative audit value, pinned to the
# frozenset length by ``test_decorative_category_1_yaml_matches_frozenset``.
_CATEGORY_1_YAML_KEY = "category_1_auto_discovered_migrations"
_CATEGORY_1_ATTR = "_CATEGORY_1_AUTO_DISCOVERED_MIGRATIONS"

# FR-003: JUnit property names for the skip-marker delta backstop. Growth is
# REVIEWABLE (routed here, surfaced in the report, reviewed via the co-located
# ``# round-trip: skip: <reason>`` diff line) rather than a hard CI failure.
_SKIP_MARKER_GROWTH_PROP = "skip_marker_blocks_growth"
_SKIP_MARKER_SHRINK_PROP = "skip_marker_blocks_shrinkage"


def _category_baseline(cat_key: str, yaml_value: int, nd_module: str) -> int:
    """Return the baseline size for a ``test_no_dead_modules`` category.

    FR-004: for ``category_1`` the baseline is DERIVED from the live
    ``_CATEGORY_1_AUTO_DISCOVERED_MIGRATIONS`` frozenset length (single
    authority — never re-globbed, which would fork a ``_has_caller``
    split-brain). Every other category reads its recorded YAML integer. This
    one helper is reused by BOTH the growth and shrinkage arms so the two can
    never disagree about how ``category_1`` is derived.
    """
    if cat_key == _CATEGORY_1_YAML_KEY:
        return len(_import_module_attr(nd_module, _CATEGORY_1_ATTR))
    return yaml_value


def _emit_skip_marker_delta(
    baseline: int, current: int, record_property: RecordPropertyFn
) -> None:
    """Route a skip-marker-block count delta to ``record_property`` (FR-003).

    Growth is REVIEWABLE-not-blocking: a new ``# round-trip: skip: <reason>``
    block is caught by human review of the co-located reason line (enforced by
    the unmodified ``_SKIP_MARKER_RE``), not by a ``pytest.fail`` here. Shrinkage
    locks in a lower high-water mark. This helper NEVER raises — that is the
    whole point of draining the hard-fail toll.

    #3560 finding 2 (advisory-by-design, not a gap): the ``record_property``
    values emitted below land in pytest's JUnit ``user_properties``, which is
    write-only in this repo (nothing reads it back to gate CI) — so this
    numeric count is intentionally NOT machine-enforced. The count-bump was
    pure bookkeeping toll; draining it here does not remove any teeth. The
    actual machine-enforced gate for a new skip-marker block is per-block and
    lives in ``tests/contract/test_example_round_trip.py``
    (``_SKIP_MARKER_RE``): a block with neither a ``# pydantic_model:`` tag nor
    a ``# round-trip: skip: <reason>`` marker carrying a non-empty reason fails
    that gate directly, independent of this advisory count.
    """
    if current > baseline:
        record_property(
            _SKIP_MARKER_GROWTH_PROP,
            f"Skip-marker blocks grew {baseline} -> {current}. FR-003: reviewable "
            f"via the co-located `# round-trip: skip: <reason>` diff line, NOT a CI "
            f"failure. Lock in the new high-water mark by bumping "
            f"`_baselines.yaml::test_example_round_trip.skip_marker_blocks`.",
        )
    elif current < baseline:
        record_property(
            _SKIP_MARKER_SHRINK_PROP,
            f"Skip-marker blocks shrank {baseline} -> {current}. Lock in the lower "
            f"bound in `_baselines.yaml`.",
        )


def _load_baselines() -> dict[str, Any]:
    """Load and parse the baselines YAML. Raise FileNotFoundError if missing."""
    if not _BASELINES_PATH.exists():
        raise FileNotFoundError(
            f"`tests/architectural/_baselines.yaml` is missing. This file is a "
            f"binding ratchet artefact per C-004 (Slice F charter pack). Restore "
            f"it from the previous commit OR run the WP01 bootstrap. Expected at: "
            f"{_BASELINES_PATH}"
        )
    text = _BASELINES_PATH.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(
            f"`tests/architectural/_baselines.yaml` is malformed: top level must "
            f"be a mapping, got {type(data).__name__}."
        )
    return data


def _import_module_attr(module_dotted: str, attr_name: str) -> frozenset[Any]:
    """Import *module_dotted* and return its *attr_name* attribute.

    Used to look up gated test modules' allowlist symbols by name.

    The round-trip contract module emits DEFERRED, out-of-arch-scope
    legacy-backfill ``UserWarning``s at import time (GH #2553). We only read
    its ratchet-size constants here, so we scope-suppress warnings originating
    from that specific module during its import — preserving the signal at its
    real home (the contract suite) while keeping the arch-suite warnings
    channel first-party-clean (NFR-006). This is a narrow, module-scoped
    filter, not a blanket ignore.
    """
    if module_dotted == _ROUND_TRIP_CONTRACT_MODULE:
        # Tight block scope: the only code that runs here is this single
        # import, whose sole warning output is the deferred #2553
        # legacy-backfill subset. category=UserWarning keeps the filter
        # narrow (not a blanket ``ignore``).
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=UserWarning)
            module = importlib.import_module(module_dotted)
    else:
        module = importlib.import_module(module_dotted)
    if not hasattr(module, attr_name):
        raise AttributeError(
            f"Module `{module_dotted}` does not export `{attr_name}`. The "
            f"FR-112 per-category refactor must publish this attribute at "
            f"module scope so the ratchet baseline meta-test can introspect "
            f"its size."
        )
    return cast("frozenset[Any]", getattr(module, attr_name))


def test_baseline_file_exists_with_required_keys() -> None:
    """AC-6: `_baselines.yaml` must exist with one section per gated test.

    The schema is defined in
    ``kitty-specs/slice-f-multi-context-extensibility-01KRX5C8/contracts/
    ratchet-baseline-format.md`` and pinned by C-004.
    """
    data = _load_baselines()

    missing = _REQUIRED_TOP_LEVEL_KEYS - set(data.keys())
    assert not missing, (
        f"`_baselines.yaml` is missing required top-level key(s): "
        f"{sorted(missing)}. Each gated test module's ratchet must be "
        f"recorded so the meta-test can compare current size against the "
        f"baseline."
    )

    # test_no_dead_modules must carry per-category sub-keys (FR-112).
    nd_section = data["test_no_dead_modules"]
    assert isinstance(nd_section, dict), (
        "`_baselines.yaml::test_no_dead_modules` must be a mapping of "
        "per-category integers (FR-112 refactor)."
    )
    missing_cats = _REQUIRED_NO_DEAD_MODULES_CATEGORIES - set(nd_section.keys())
    assert not missing_cats, (
        f"`_baselines.yaml::test_no_dead_modules` is missing per-category "
        f"key(s): {sorted(missing_cats)}. The FR-112 refactor splits the "
        f"single `_ALLOWLIST` into per-category frozensets so growth in "
        f"Cat-1 (auto-discovered migrations) cannot disguise Cat-7 "
        f"grandfathered-orphan regression."
    )


def test_growing_an_allowlist_above_baseline_fails() -> None:
    """Scenario 6 / AC-6: any ratchet growing above its baseline fails this test.

    The test imports each gated module dynamically, reads the live
    allowlist size, and compares it against the baseline integer in
    ``_baselines.yaml``. ``current > baseline`` => ``pytest.fail``.
    Shrinkage (``current < baseline``) is handled by the
    ``test_growth_fails_shrinkage_warns`` test below.
    """
    data = _load_baselines()
    growth_failures: list[str] = []

    # test_no_dead_modules: per-category comparison.
    nd_cats = data["test_no_dead_modules"]
    nd_module = _NO_DEAD_MODULES_MODULE
    per_category_attrs = {
        "category_1_auto_discovered_migrations": "_CATEGORY_1_AUTO_DISCOVERED_MIGRATIONS",
        "category_2_build_schema_generators": "_CATEGORY_2_BUILD_SCHEMA_GENERATORS",
        "category_3_external_cli_entrypoints": "_CATEGORY_3_EXTERNAL_CLI_ENTRYPOINTS",
        "category_4_backcompat_shims": "_CATEGORY_4_BACKCOMPAT_SHIMS",
        "category_5_wp_in_flight_adapters": "_CATEGORY_5_WP_IN_FLIGHT_ADAPTERS",
        "category_6_frozen_runtime_reexports": "_CATEGORY_6_FROZEN_RUNTIME_REEXPORTS",
        "category_7_grandfathered_orphans": "_CATEGORY_7_GRANDFATHERED_ORPHANS",
    }
    for cat_key, attr_name in per_category_attrs.items():
        # FR-004: category_1 is derived from the frozenset, not YAML-pinned.
        baseline = _category_baseline(cat_key, nd_cats[cat_key], nd_module)
        current = len(_import_module_attr(nd_module, attr_name))
        if current > baseline:
            growth_failures.append(
                f"  - test_no_dead_modules.{cat_key}: baseline={baseline} "
                f"current={current}. Remove the new entry OR edit "
                f"_baselines.yaml from {baseline} to {current} with a "
                f"justification comment in the PR."
            )

    # Single-integer ratchets.
    single_baselines: list[tuple[str, str, str, int]] = [
        (
            "test_layer_rules",
            "tests.architectural.test_layer_rules",
            "_MISSION_RUNTIME_ALLOWED_SPECIFY_CLI",
            data["test_layer_rules"]["mission_runtime_allowed_specify_cli"],
        ),
        (
            "test_layer_rules",
            "tests.architectural.test_layer_rules",
            "_RUNTIME_ALLOWED_SPECIFY_CLI",
            data["test_layer_rules"]["runtime_allowed_specify_cli"],
        ),
        (
            "test_runtime_charter_doctrine_boundary",
            "tests.architectural.test_runtime_charter_doctrine_boundary",
            "_LAZY_BASELINE_ALLOWLIST",
            data["test_runtime_charter_doctrine_boundary"]["lazy_baseline_allowlist"],
        ),
        (
            "test_doctrine_census",
            "tests.architectural.test_doctrine_census",
            "ORPHAN_REACHED_EXCEPTIONS",
            data["test_doctrine_census"]["orphan_reached_exceptions"],
        ),
        (
            "test_migration_chain_integrity",
            "tests.architectural.test_migration_chain_integrity",
            "_KNOWN_LINE_JUMPS",
            data["test_migration_chain_integrity"]["known_line_jumps"],
        ),
        (
            "test_auth_transport_singleton",
            "tests.architectural.test_auth_transport_singleton",
            "_TRANSPORT_ALLOWLIST",
            data["test_auth_transport_singleton"]["allowed_direct_httpx_files"],
        ),
        # FR-141: legacy contract allowlist for the round-trip gate.
        (
            "test_example_round_trip",
            "tests.contract.test_example_round_trip",
            "_LEGACY_CONTRACT_ALLOWLIST",
            data["test_example_round_trip"]["legacy_contract_allowlist"],
        ),
        # FR-003: `_SKIP_MARKED_BLOCKS` is intentionally ABSENT from this
        # hard-fail list. Skip-marker growth is now reviewable-not-blocking,
        # routed through `record_property` by
        # `test_skip_marker_growth_is_recorded_not_failed`. (The removed toll
        # made every legitimate new permanent skip a red build until the
        # baseline was bumped — pure bookkeeping, since the review-forcing signal
        # is the co-located `# round-trip: skip: <reason>` diff line.)
        # doctrine-silence-guards-01KYFV7Q WP01: frozen shrink-only baseline of
        # declared doctrine slots that nothing populates. Debt with named owners,
        # not an allowlist -- the module's own ALLOWLIST is permanently empty.
        (
            "test_no_inert_schema_slots",
            "tests.architectural._inert_slots",
            "BASELINE_SLOTS",
            data["test_no_inert_schema_slots"]["baseline_entries"],
        ),
        # Charter Burn-down Policy (a): the four `<kind>_reference.type` enum
        # baselines, flattened to one slot per permitted member. Shrink-only --
        # the 12-vs-7 split is unadjudicated (#2976), so it should narrow.
        (
            "test_reference_enum_ratchet",
            "tests.architectural.test_reference_enum_ratchet",
            "BASELINE_MEMBER_SLOTS",
            data["test_reference_enum_ratchet"]["baseline_members"],
        ),
        # #3030 egress boundary. Both sets are registered, not just the
        # work-list: the allowlist is the surface an author would edit to
        # silence that gate, so growing it must cost the same visible diff.
        (
            "test_egress_consent_boundary",
            "tests.architectural.test_egress_consent_boundary",
            "_EGRESS_ALLOWLIST_FILES",
            data["test_egress_consent_boundary"]["egress_allowlist_files"],
        ),
        # Shrink-only: growth here would mean a NEW unconsented egress path,
        # which is the P0 that mission exists to close. Never record one.
        (
            "test_egress_consent_boundary",
            "tests.architectural.test_egress_consent_boundary",
            "_KNOWN_UNGATED_FILES",
            data["test_egress_consent_boundary"]["known_ungated_files"],
        ),
        # FR-011 (#4746/#2899) construction gate: the justified raw-read
        # residuals allowlist is the surface an author would edit to silence
        # the gate's Part (b) scan, so growing it must cost this same diff.
        (
            "test_cli_error_surface_seam",
            "tests.architectural.test_cli_error_surface_seam",
            "_JUSTIFIED_RESIDUALS",
            data["test_cli_error_surface_seam"]["justified_raw_read_residuals"],
        ),
    ]
    for label, module_dotted, attr_name, baseline in single_baselines:
        current = len(_import_module_attr(module_dotted, attr_name))
        if current > baseline:
            growth_failures.append(
                f"  - {label}.{attr_name}: baseline={baseline} current={current}. "
                f"Remove the new entry OR edit _baselines.yaml from {baseline} "
                f"to {current} with a justification comment in the PR."
            )

    assert not growth_failures, (
        "Ratchet baseline GROWTH detected (FR-111 violation). The following "
        "allowlists exceeded their pinned baselines:\n"
        + "\n".join(growth_failures)
        + "\n\nPer the burn-down policy (Slice F C-004), each growth requires "
        "a one-line YAML diff to _baselines.yaml in the same PR plus a "
        "`# justification:` comment naming why the growth is acceptable."
    )


def test_growth_fails_shrinkage_warns(
    record_property: RecordPropertyFn,
) -> None:
    """AC-6: shrinkage below baseline is REPORTED, never fails.

    The report nudges the PR author to lock in the new lower bound by
    editing ``_baselines.yaml`` in the same PR. Shrinkage is good news
    (a previously-grandfathered orphan got wired or deleted) so it must
    not block CI. Routed off the ``warnings`` channel via ``record_property``
    (was ``warnings.warn``) so the diagnostic surfaces in the JUnit/report
    output without polluting the arch-suite warnings channel that NFR-006
    requires to stay first-party-clean.
    """
    data = _load_baselines()
    shrinkage_messages: list[str] = []

    # Per-category for test_no_dead_modules.
    nd_cats = data["test_no_dead_modules"]
    nd_module = _NO_DEAD_MODULES_MODULE
    per_category_attrs = {
        "category_1_auto_discovered_migrations": "_CATEGORY_1_AUTO_DISCOVERED_MIGRATIONS",
        "category_2_build_schema_generators": "_CATEGORY_2_BUILD_SCHEMA_GENERATORS",
        "category_3_external_cli_entrypoints": "_CATEGORY_3_EXTERNAL_CLI_ENTRYPOINTS",
        "category_4_backcompat_shims": "_CATEGORY_4_BACKCOMPAT_SHIMS",
        "category_5_wp_in_flight_adapters": "_CATEGORY_5_WP_IN_FLIGHT_ADAPTERS",
        "category_6_frozen_runtime_reexports": "_CATEGORY_6_FROZEN_RUNTIME_REEXPORTS",
        "category_7_grandfathered_orphans": "_CATEGORY_7_GRANDFATHERED_ORPHANS",
    }
    for cat_key, attr_name in per_category_attrs.items():
        # FR-004: category_1 is derived from the frozenset, not YAML-pinned, so
        # its derived baseline always equals current — no spurious shrink noise.
        baseline = _category_baseline(cat_key, nd_cats[cat_key], nd_module)
        current = len(_import_module_attr(nd_module, attr_name))
        if current < baseline:
            shrinkage_messages.append(
                f"test_no_dead_modules.{cat_key}: baseline={baseline} "
                f"current={current}. Edit _baselines.yaml to lock in the "
                f"shrinkage."
            )

    # Single-integer ratchets.
    single_baselines: list[tuple[str, str, str, int]] = [
        (
            "test_layer_rules",
            "tests.architectural.test_layer_rules",
            "_MISSION_RUNTIME_ALLOWED_SPECIFY_CLI",
            data["test_layer_rules"]["mission_runtime_allowed_specify_cli"],
        ),
        (
            "test_layer_rules",
            "tests.architectural.test_layer_rules",
            "_RUNTIME_ALLOWED_SPECIFY_CLI",
            data["test_layer_rules"]["runtime_allowed_specify_cli"],
        ),
        (
            "test_runtime_charter_doctrine_boundary",
            "tests.architectural.test_runtime_charter_doctrine_boundary",
            "_LAZY_BASELINE_ALLOWLIST",
            data["test_runtime_charter_doctrine_boundary"]["lazy_baseline_allowlist"],
        ),
        (
            "test_doctrine_census",
            "tests.architectural.test_doctrine_census",
            "ORPHAN_REACHED_EXCEPTIONS",
            data["test_doctrine_census"]["orphan_reached_exceptions"],
        ),
        (
            "test_migration_chain_integrity",
            "tests.architectural.test_migration_chain_integrity",
            "_KNOWN_LINE_JUMPS",
            data["test_migration_chain_integrity"]["known_line_jumps"],
        ),
        (
            "test_auth_transport_singleton",
            "tests.architectural.test_auth_transport_singleton",
            "_TRANSPORT_ALLOWLIST",
            data["test_auth_transport_singleton"]["allowed_direct_httpx_files"],
        ),
        # FR-141: legacy contract allowlist for the round-trip gate.
        (
            "test_example_round_trip",
            "tests.contract.test_example_round_trip",
            "_LEGACY_CONTRACT_ALLOWLIST",
            data["test_example_round_trip"]["legacy_contract_allowlist"],
        ),
        # FR-003: `_SKIP_MARKED_BLOCKS` removed from BOTH arms in lockstep.
        # Skip-marker shrinkage is tracked by
        # `test_skip_marker_growth_is_recorded_not_failed` via `record_property`,
        # not this warn-arm (which only ever reported and never blocked anyway).
        # doctrine-silence-guards-01KYFV7Q WP01: frozen shrink-only baseline of
        # declared doctrine slots that nothing populates. Debt with named owners,
        # not an allowlist -- the module's own ALLOWLIST is permanently empty.
        (
            "test_no_inert_schema_slots",
            "tests.architectural._inert_slots",
            "BASELINE_SLOTS",
            data["test_no_inert_schema_slots"]["baseline_entries"],
        ),
        # Charter Burn-down Policy (a): the four `<kind>_reference.type` enum
        # baselines, flattened to one slot per permitted member. Shrink-only --
        # the 12-vs-7 split is unadjudicated (#2976), so it should narrow.
        (
            "test_reference_enum_ratchet",
            "tests.architectural.test_reference_enum_ratchet",
            "BASELINE_MEMBER_SLOTS",
            data["test_reference_enum_ratchet"]["baseline_members"],
        ),
        # #3030 egress boundary. Both sets are registered, not just the
        # work-list: the allowlist is the surface an author would edit to
        # silence that gate, so growing it must cost the same visible diff.
        (
            "test_egress_consent_boundary",
            "tests.architectural.test_egress_consent_boundary",
            "_EGRESS_ALLOWLIST_FILES",
            data["test_egress_consent_boundary"]["egress_allowlist_files"],
        ),
        # Shrink-only: growth here would mean a NEW unconsented egress path,
        # which is the P0 that mission exists to close. Never record one.
        (
            "test_egress_consent_boundary",
            "tests.architectural.test_egress_consent_boundary",
            "_KNOWN_UNGATED_FILES",
            data["test_egress_consent_boundary"]["known_ungated_files"],
        ),
        # FR-011 (#4746/#2899) construction gate: participates in the
        # shrinkage arm too — fixing one of the 7 justified residuals (e.g.
        # routing it through read_guarded after all) should be locked in as
        # a lower baseline, not silently tolerated.
        (
            "test_cli_error_surface_seam",
            "tests.architectural.test_cli_error_surface_seam",
            "_JUSTIFIED_RESIDUALS",
            data["test_cli_error_surface_seam"]["justified_raw_read_residuals"],
        ),
    ]
    for label, module_dotted, attr_name, baseline in single_baselines:
        current = len(_import_module_attr(module_dotted, attr_name))
        if current < baseline:
            shrinkage_messages.append(
                f"{label}.{attr_name}: baseline={baseline} current={current}. "
                f"Edit _baselines.yaml to lock in the shrinkage."
            )

    # Record each shrinkage (one property per shrinkage) so pytest surfaces
    # them in the report output without emitting on the warnings channel.
    for idx, msg in enumerate(shrinkage_messages):
        record_property(
            f"ratchet_baseline_shrinkage[{idx}]",
            f"Ratchet baseline SHRINKAGE (informational, not failing): {msg}",
        )

    # This test never fails on shrinkage. It exists to (a) record the
    # shrinkage surface, and (b) assert that the contract API holds (i.e.
    # the baselines load and the ratchets are introspectable).
    assert isinstance(data, dict)


def test_no_unregistered_baseline_keys_are_added() -> None:
    """Reverse containment: `test_baseline_file_exists_with_required_keys`
    checks only for MISSING keys, never for extra.

    A key can therefore sit in `_baselines.yaml` read by no comparison, its
    growth failing nothing, with this suite green — which is exactly how
    `test_no_dead_symbols` went unnoticed. This arm closes that.

    **Now fully closed (FR-005).** The `test_no_dead_symbols` inert key and its
    whole YAML block (RL-030) were removed by mission
    `frozen-baseline-toll-reduction-01M0A42D` WP03, and
    `_GRANDFATHERED_UNREGISTERED_KEYS` was drained to empty in lockstep. With
    the grandfather set empty, ANY unregistered top-level key now reds: a new
    key that a comparison COULD read must be registered in
    `_REQUIRED_TOP_LEVEL_KEYS` and in BOTH `single_baselines` lists; a key read
    by no comparison by design must not be added at all. The set is pinned empty
    by frozenset equality below, so re-widening it costs a visible diff here
    instead of a silent one in the YAML.
    """
    data = _load_baselines()
    unregistered = set(data) - _REQUIRED_TOP_LEVEL_KEYS

    assert frozenset() == _GRANDFATHERED_UNREGISTERED_KEYS, (
        "`_GRANDFATHERED_UNREGISTERED_KEYS` is CLOSED and drained to empty "
        f"(FR-005). Observed {sorted(_GRANDFATHERED_UNREGISTERED_KEYS)}. A new "
        "inert key that a comparison COULD read must be registered in "
        "`_REQUIRED_TOP_LEVEL_KEYS` and in BOTH `single_baselines` lists, not "
        "grandfathered here. Grandfathering is no longer available: an inert key "
        "read by no comparison must not be added to the YAML at all."
    )
    assert unregistered <= _GRANDFATHERED_UNREGISTERED_KEYS, (
        f"`_baselines.yaml` carries top-level key(s) no comparison reads: "
        f"{sorted(unregistered - _GRANDFATHERED_UNREGISTERED_KEYS)}. Adding a key "
        "does NOT make its growth fail anything -- both comparisons run off the "
        "hardcoded `single_baselines` lists. Register it in "
        "`_REQUIRED_TOP_LEVEL_KEYS` AND in both lists, or remove it from the YAML."
    )


def test_readding_inert_dead_symbols_key_is_now_rejected() -> None:
    """FR-005 / US4-AC1: with `_GRANDFATHERED_UNREGISTERED_KEYS` drained, the
    reverse-containment arm now REJECTS a re-added `test_no_dead_symbols` key.

    Exercises the same containment predicate the production arm runs against a
    synthetic YAML shape carrying the inert key — proving re-entry reds rather
    than being silently grandfathered (as it was before this WP).
    """
    assert not _GRANDFATHERED_UNREGISTERED_KEYS
    synthetic = dict.fromkeys(_REQUIRED_TOP_LEVEL_KEYS, 0)
    synthetic["test_no_dead_symbols"] = 1
    unregistered = set(synthetic) - _REQUIRED_TOP_LEVEL_KEYS
    assert unregistered == {"test_no_dead_symbols"}
    assert not (unregistered <= _GRANDFATHERED_UNREGISTERED_KEYS), (
        "Re-adding `test_no_dead_symbols` must now be REJECTED by the "
        "reverse-containment arm (grandfather set is empty)."
    )


def test_decorative_category_1_yaml_matches_frozenset() -> None:
    """FR-004 (pedro-nit): the now-decorative `category_1` YAML integer must
    equal the live frozenset length so the non-load-bearing audit value cannot
    silently drift away from the single authority.
    """
    data = _load_baselines()
    recorded = data["test_no_dead_modules"][_CATEGORY_1_YAML_KEY]
    live = len(_import_module_attr(_NO_DEAD_MODULES_MODULE, _CATEGORY_1_ATTR))
    assert recorded == live, (
        f"`_baselines.yaml::test_no_dead_modules.{_CATEGORY_1_YAML_KEY}` = "
        f"{recorded} but the live `{_CATEGORY_1_ATTR}` frozenset has {live} "
        f"members. The category_1 baseline is DERIVED (FR-004); the YAML integer "
        f"is a decorative audit value that must track the frozenset in lockstep."
    )


def _synthetic_frozenset(size: int) -> frozenset[str]:
    """A frozenset of *size* distinct sentinels — a stand-in whose only salient
    property to the ratchet is its ``len()``."""
    return frozenset(f"synthetic::{index}" for index in range(size))


def test_category_1_derived_baseline_absorbs_growth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-004 / US3-AC1: growing `_CATEGORY_1_AUTO_DISCOVERED_MIGRATIONS` ABOVE
    the decorative YAML value (100) does NOT red the growth arm — proving the
    baseline is derived from the frozenset, not read from YAML. A YAML-pinned
    baseline would fail at 130-vs-100; the derived one self-cancels.

    Drives the REAL production comparison (`test_growing_...`), not two inline
    ``len()``s equated to each other.
    """
    nd_module = importlib.import_module(_NO_DEAD_MODULES_MODULE)
    monkeypatch.setattr(nd_module, _CATEGORY_1_ATTR, _synthetic_frozenset(130))
    # No raise: category_1 derives its own baseline, so 130 == 130 for it.
    test_growing_an_allowlist_above_baseline_fails()


def test_category_1_derived_baseline_absorbs_shrink(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-004 / US3-AC2: a migration gaining a static importer shrinks the
    frozenset below the YAML value; the derived baseline tracks it, so the
    shrink arm records NO category_1 shrinkage and no `_baselines.yaml` edit is
    demanded. Drives the real shrink-arm comparison with a captured
    `record_property`.
    """
    nd_module = importlib.import_module(_NO_DEAD_MODULES_MODULE)
    monkeypatch.setattr(nd_module, _CATEGORY_1_ATTR, _synthetic_frozenset(80))
    recorded: list[tuple[str, object]] = []
    test_growth_fails_shrinkage_warns(
        lambda name, value: recorded.append((name, value))
    )
    assert not any(
        _CATEGORY_1_YAML_KEY in str(value) for _, value in recorded
    ), recorded


def test_non_derived_category_growth_still_reds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-vacuity control (growth): a NON-derived category grown above its YAML
    baseline STILL reds the growth arm — only category_1 was made
    count-independent; the harness keeps its teeth for every other category.
    """
    nd_module = importlib.import_module(_NO_DEAD_MODULES_MODULE)
    monkeypatch.setattr(
        nd_module, "_CATEGORY_6_FROZEN_RUNTIME_REEXPORTS", _synthetic_frozenset(500)
    )
    with pytest.raises(
        AssertionError, match="category_6_frozen_runtime_reexports"
    ):
        test_growing_an_allowlist_above_baseline_fails()


def test_non_derived_category_shrink_still_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-vacuity control (shrink): a NON-derived category shrunk below its YAML
    baseline IS recorded by the shrink arm — the derivation did not silence
    shrink tracking for anything but category_1.
    """
    nd_module = importlib.import_module(_NO_DEAD_MODULES_MODULE)
    monkeypatch.setattr(
        nd_module, "_CATEGORY_6_FROZEN_RUNTIME_REEXPORTS", frozenset()
    )
    recorded: list[tuple[str, object]] = []
    test_growth_fails_shrinkage_warns(
        lambda name, value: recorded.append((name, value))
    )
    assert any(
        "category_6_frozen_runtime_reexports" in str(value)
        for _, value in recorded
    ), recorded


@pytest.mark.parametrize("package", ["runtime", "mission_runtime"])
def test_runtime_ledger_growth_with_live_import_still_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    package: str,
) -> None:
    """Adding an import AND its ledger entry must still trip the independent cap."""
    layer_rules = importlib.import_module("tests.architectural.test_layer_rules")
    runtime = tmp_path / package
    runtime.mkdir()
    (tmp_path / "specify_cli" / "saas_client").mkdir(parents=True)
    symbol = f"_{package.upper()}_ALLOWED_SPECIFY_CLI"
    allowed = getattr(layer_rules, symbol)
    assert "saas_client" not in allowed
    baseline = _load_baselines()["test_layer_rules"][f"{package}_allowed_specify_cli"]
    # Cross the recorded cap even if earlier cleanup has left shrinkage headroom.
    extra = {f"baseline_probe_{i}" for i in range(max(0, baseline - len(allowed)))}
    source = "\n".join(f"import specify_cli{'.' + name if name else ''}" for name in sorted(allowed | extra))
    (runtime / "probe.py").write_text(source + "\nfrom specify_cli import saas_client\n", encoding="utf-8")
    monkeypatch.setattr(layer_rules, "_SRC", tmp_path)
    monkeypatch.setattr(layer_rules, f"_{package.upper()}_ROOT", runtime)
    monkeypatch.setattr(layer_rules, symbol, allowed | extra | {"saas_client"})
    if package == "runtime":
        gate = layer_rules.TestRuntimeSpecifyCliLedger()
        gate.test_runtime_specify_cli_imports_within_ledger()
        gate.test_runtime_ledger_has_no_stale_entries()
    else:
        mission_gate = layer_rules.TestMissionRuntimeBoundary()
        mission_gate.test_mission_runtime_specify_cli_imports_within_ledger()
        mission_gate.test_ledger_has_no_stale_entries()
    with pytest.raises(AssertionError, match=symbol):
        test_growing_an_allowlist_above_baseline_fails()


@pytest.mark.parametrize("package", ["runtime", "mission_runtime"])
def test_runtime_ledger_shrink_is_reported(monkeypatch: pytest.MonkeyPatch, package: str) -> None:
    """The registered runtime cap also participates in the shrinkage arm."""
    layer_rules = importlib.import_module("tests.architectural.test_layer_rules")
    symbol = f"_{package.upper()}_ALLOWED_SPECIFY_CLI"
    monkeypatch.setattr(layer_rules, symbol, frozenset())
    recorded: list[tuple[str, object]] = []
    test_growth_fails_shrinkage_warns(lambda name, value: recorded.append((name, value)))
    assert any(symbol in str(value) for _, value in recorded), recorded


@pytest.mark.parametrize(
    "module_name, symbol, key",
    [
        ("test_runtime_charter_doctrine_boundary", "_LAZY_BASELINE_ALLOWLIST", "lazy_baseline_allowlist"),
        ("test_doctrine_census", "ORPHAN_REACHED_EXCEPTIONS", "orphan_reached_exceptions"),
    ],
)
def test_doctrine_pair_allowlist_growth_fails_and_shrink_is_reported(
    monkeypatch: pytest.MonkeyPatch,
    module_name: str,
    symbol: str,
    key: str,
) -> None:
    """Both exact-pair exception sets must participate in both comparison arms."""
    module = importlib.import_module(f"tests.architectural.{module_name}")
    allowed = getattr(module, symbol)
    baseline = _load_baselines()[module_name][key]
    # Pair arity is the contract, not the number of allowed dependency pairs.
    assert all(isinstance(pair, tuple) and len(pair) == 2 for pair in allowed)
    extra = {
        (f"src/runtime/baseline_probe_{i}.py", "charter.offering.new_dependency")
        for i in range(max(1, baseline - len(allowed) + 1))
    }
    assert not allowed & extra
    monkeypatch.setattr(module, symbol, allowed | extra)
    with pytest.raises(AssertionError, match=symbol):
        test_growing_an_allowlist_above_baseline_fails()
    monkeypatch.setattr(module, symbol, frozenset())
    recorded: list[tuple[str, object]] = []
    test_growth_fails_shrinkage_warns(lambda name, value: recorded.append((name, value)))
    assert any(symbol in str(value) for _, value in recorded), recorded


def test_skip_marker_growth_is_recorded_not_failed(
    request: pytest.FixtureRequest,
    record_property: RecordPropertyFn,
) -> None:
    """FR-003 / SC-003 / US2-AC1: skip-marker GROWTH is routed through
    `record_property` (reviewable via the co-located `# round-trip: skip:
    <reason>` diff line) and does NOT hard-fail.

    `record_property` is write-only in this repo (`grep user_properties tests/`
    is empty), so an unasserted call is an unverified backstop — this test
    ASSERTS the growth property actually fired by inspecting
    `request.node.user_properties`.
    """
    data = _load_baselines()
    baseline = data["test_example_round_trip"]["skip_marker_blocks"]
    # Drive growth with a synthetic current above baseline; must NOT raise
    # (contrast the removed hard-fail `_SKIP_MARKED_BLOCKS` `single_baselines`
    # tuple, which would have failed the whole ratchet on any new skip block).
    _emit_skip_marker_delta(baseline, baseline + 5, record_property)
    props = dict(request.node.user_properties)
    assert _SKIP_MARKER_GROWTH_PROP in props, request.node.user_properties
    assert "reviewable" in str(props[_SKIP_MARKER_GROWTH_PROP]).lower()


def test_skip_marker_shrink_is_recorded(
    request: pytest.FixtureRequest,
    record_property: RecordPropertyFn,
) -> None:
    """FR-003 / US2-AC3: skip-marker shrinkage is tracked as a lowered
    high-water mark (asserted to fire, same rationale as growth)."""
    data = _load_baselines()
    baseline = data["test_example_round_trip"]["skip_marker_blocks"]
    _emit_skip_marker_delta(baseline, max(baseline - 1, 0), record_property)
    props = dict(request.node.user_properties)
    assert _SKIP_MARKER_SHRINK_PROP in props, request.node.user_properties


def test_skip_marker_live_count_never_blocks(
    record_property: RecordPropertyFn,
) -> None:
    """FR-003: against the LIVE `_SKIP_MARKED_BLOCKS` size (real import wiring),
    the delta helper never raises — whatever the current count, skip-marker
    accounting cannot block CI."""
    data = _load_baselines()
    baseline = data["test_example_round_trip"]["skip_marker_blocks"]
    current = len(
        _import_module_attr(_ROUND_TRIP_CONTRACT_MODULE, "_SKIP_MARKED_BLOCKS")
    )
    _emit_skip_marker_delta(baseline, current, record_property)  # must not raise


def test_legacy_contract_allowlist_growth_still_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-003 NFR-003 / Contract B: removing `_SKIP_MARKED_BLOCKS` did NOT loosen
    the C-001 sibling. `legacy_contract_allowlist` stays pinned at 151 AND its
    growth still reds the growth arm (the surgical extraction was scoped to the
    skip-marker row only).
    """
    data = _load_baselines()
    assert data["test_example_round_trip"]["legacy_contract_allowlist"] == 151
    # Ensure the corpus module is imported (and warning-suppressed) via the
    # module-scoped helper before monkeypatching its attribute in place.
    _import_module_attr(_ROUND_TRIP_CONTRACT_MODULE, "_LEGACY_CONTRACT_ALLOWLIST")
    module = sys.modules[_ROUND_TRIP_CONTRACT_MODULE]
    monkeypatch.setattr(module, "_LEGACY_CONTRACT_ALLOWLIST", _synthetic_frozenset(300))
    with pytest.raises(AssertionError, match="_LEGACY_CONTRACT_ALLOWLIST"):
        test_growing_an_allowlist_above_baseline_fails()


def test_fast_collection_does_not_import_round_trip_corpus() -> None:
    """FR-006 / NFR-002: importing this fast-marked gate module must NOT
    transitively import the heavy `test_example_round_trip` corpus module.

    Collection == module import; the corpus import is deferred into function
    bodies via `_import_module_attr`, so it stays out of collection today. A
    refactor that hoisted the corpus import to module scope would silently drag
    the corpus into every `-m fast` collection — this subprocess (a fresh
    interpreter, no shared `sys.modules`) proves it does not.
    """
    repo_root = Path(__file__).resolve().parents[2]
    probe = (
        "import sys, importlib;"
        "importlib.import_module('tests.architectural.test_ratchet_baselines');"
        "corpus = [m for m in sys.modules if 'test_example_round_trip' in m];"
        "assert not corpus, corpus"
    )
    result = subprocess.run(
        [sys.executable, "-c", probe],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, (
        "Importing `test_ratchet_baselines` transitively imported the "
        f"`test_example_round_trip` corpus (fast-tier import-hygiene regression):"
        f"\nstdout={result.stdout}\nstderr={result.stderr}"
    )
