"""Meta-test for architectural ratchet baselines (Slice F WP01, FR-110/FR-111).

This test is the canonical executable contract for the burn-down policy
pinned by C-004 / C-006 of the Slice F charter pack. It loads
``tests/architectural/_baselines.yaml`` and compares the recorded
per-test, per-category allowlist size against the live size of each
gated test module's allowlist symbol. Every comparison is one row of the
module-level ``_SIZE_RATCHETS`` table, and every YAML leaf must have a row
(FR-011: ``test_every_baseline_leaf_is_enforced_by_a_size_ratchet``).

Failure semantics
-----------------
* **Growth above baseline** -> ``pytest.fail`` with a remediation hint
  (either remove the new allowlist entry or edit ``_baselines.yaml`` in
  the same PR with a justification comment).
* **Shrinkage below baseline** -> ``record_property`` (informational; the
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

import copy
import importlib
import subprocess
import sys
import warnings
from collections.abc import Callable
from dataclasses import dataclass
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
                    raise ValueError(f"Per-category baseline {k!r} must be a non-negative integer; got {v!r}")
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


# ---------------------------------------------------------------------------
# The ONE size-ratchet comparison table (FR-011, DIRECTIVE_044)
# ---------------------------------------------------------------------------
# Each row binds one ``_baselines.yaml`` leaf (``section.leaf``) to the live
# gated symbol (``module.attr``) whose ``len()`` it caps. A leaf is ENFORCED
# iff it has a row here: both comparison arms iterate this table, so there is
# no second list to keep in step. Modules are stored as dotted strings and
# resolved lazily through ``_import_module_attr`` (never a module object), so
# importing this fast-tier gate never drags in the round-trip corpus.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _SizeRatchet:
    """One enforced baseline leaf: ``len(module.attr) > yaml[section][leaf]`` fails."""

    section: str
    leaf: str
    module: str
    attr: str


_NO_DEAD_MODULES_MODULE = "tests.architectural.test_no_dead_modules"
_DEAD_SYMBOL_ALLOWLIST_MODULE = "tests.architectural._dead_symbol_allowlist"

_SIZE_RATCHETS: tuple[_SizeRatchet, ...] = (
    # test_no_dead_modules: per-category comparison (FR-112 refactor).
    _SizeRatchet(
        "test_no_dead_modules",
        "category_2_build_schema_generators",
        _NO_DEAD_MODULES_MODULE,
        "_CATEGORY_2_BUILD_SCHEMA_GENERATORS",
    ),
    _SizeRatchet(
        "test_no_dead_modules",
        "category_3_external_cli_entrypoints",
        _NO_DEAD_MODULES_MODULE,
        "_CATEGORY_3_EXTERNAL_CLI_ENTRYPOINTS",
    ),
    _SizeRatchet(
        "test_no_dead_modules",
        "category_4_backcompat_shims",
        _NO_DEAD_MODULES_MODULE,
        "_CATEGORY_4_BACKCOMPAT_SHIMS",
    ),
    _SizeRatchet(
        "test_no_dead_modules",
        "category_5_wp_in_flight_adapters",
        _NO_DEAD_MODULES_MODULE,
        "_CATEGORY_5_WP_IN_FLIGHT_ADAPTERS",
    ),
    _SizeRatchet(
        "test_no_dead_modules",
        "category_6_frozen_runtime_reexports",
        _NO_DEAD_MODULES_MODULE,
        "_CATEGORY_6_FROZEN_RUNTIME_REEXPORTS",
    ),
    _SizeRatchet(
        "test_no_dead_modules",
        "category_7_grandfathered_orphans",
        _NO_DEAD_MODULES_MODULE,
        "_CATEGORY_7_GRANDFATHERED_ORPHANS",
    ),
    # Runtime outbound ledgers (PR #3888): independent caps, not derived from
    # the live import sets.
    _SizeRatchet(
        "test_layer_rules",
        "mission_runtime_allowed_specify_cli",
        "tests.architectural.test_layer_rules",
        "_MISSION_RUNTIME_ALLOWED_SPECIFY_CLI",
    ),
    _SizeRatchet(
        "test_layer_rules",
        "runtime_allowed_specify_cli",
        "tests.architectural.test_layer_rules",
        "_RUNTIME_ALLOWED_SPECIFY_CLI",
    ),
    _SizeRatchet(
        "test_runtime_charter_doctrine_boundary",
        "lazy_baseline_allowlist",
        "tests.architectural.test_runtime_charter_doctrine_boundary",
        "_LAZY_BASELINE_ALLOWLIST",
    ),
    _SizeRatchet(
        "test_doctrine_census",
        "orphan_reached_exceptions",
        "tests.architectural.test_doctrine_census",
        "ORPHAN_REACHED_EXCEPTIONS",
    ),
    _SizeRatchet(
        "test_migration_chain_integrity",
        "known_line_jumps",
        "tests.architectural.test_migration_chain_integrity",
        "_KNOWN_LINE_JUMPS",
    ),
    _SizeRatchet(
        "test_auth_transport_singleton",
        "allowed_direct_httpx_files",
        "tests.architectural.test_auth_transport_singleton",
        "_TRANSPORT_ALLOWLIST",
    ),
    # FR-141: legacy contract allowlist for the round-trip gate.
    _SizeRatchet(
        "test_example_round_trip",
        "legacy_contract_allowlist",
        "tests.contract.test_example_round_trip",
        "_LEGACY_CONTRACT_ALLOWLIST",
    ),
    # doctrine-silence-guards-01KYFV7Q WP01: frozen shrink-only baseline of
    # declared doctrine slots that nothing populates. Debt with named owners,
    # not an allowlist -- the module's own ALLOWLIST is permanently empty.
    _SizeRatchet(
        "test_no_inert_schema_slots",
        "baseline_entries",
        "tests.architectural._inert_slots",
        "BASELINE_SLOTS",
    ),
    # Charter Burn-down Policy (a): the four `<kind>_reference.type` enum
    # baselines, flattened to one slot per permitted member. Shrink-only --
    # the 9-vs-7 split is unadjudicated (#2976), so it should narrow.
    _SizeRatchet(
        "test_reference_enum_ratchet",
        "baseline_members",
        "tests.architectural.test_reference_enum_ratchet",
        "BASELINE_MEMBER_SLOTS",
    ),
    # #3030 egress boundary. Both sets are registered, not just the
    # work-list: the allowlist is the surface an author would edit to
    # silence that gate, so growing it must cost the same visible diff.
    _SizeRatchet(
        "test_egress_consent_boundary",
        "egress_allowlist_files",
        "tests.architectural.test_egress_consent_boundary",
        "_EGRESS_ALLOWLIST_FILES",
    ),
    # Shrink-only: growth here would mean a NEW unconsented egress path,
    # which is the P0 that mission exists to close. Never record one.
    _SizeRatchet(
        "test_egress_consent_boundary",
        "known_ungated_files",
        "tests.architectural.test_egress_consent_boundary",
        "_KNOWN_UNGATED_FILES",
    ),
    # FR-011 (#4746/#2899) construction gate: the justified raw-read
    # residuals allowlist is the surface an author would edit to silence
    # the gate's Part (b) scan, so growing it must cost this same diff; fixing
    # one residual should be locked in as a lower baseline.
    _SizeRatchet(
        "test_cli_error_surface_seam",
        "justified_raw_read_residuals",
        "tests.architectural.test_cli_error_surface_seam",
        "_JUSTIFIED_RESIDUALS",
    ),
    # WP09 non-vacuous FS-op ownership-routing gate: the frozen allowlist of
    # genuinely-safe raw destructive ops is the surface an author would edit
    # to silence the census, so growing it must cost the same visible diff.
    _SizeRatchet(
        "test_mutation_ownership_routing",
        "destructive_op_allowlist",
        "tests.architectural.test_mutation_ownership_routing",
        "_ALLOWLIST",
    ),
    # hosted-opt-in-drain-ledger WP04 (NFR-002): hosted relay/gateway edges
    # exempt from the drain gate. Empty; growth means an ungated hosted edge.
    _SizeRatchet(
        "test_hosted_drain_gate",
        "ungated_edge_allowlist",
        "tests.architectural.test_hosted_drain_gate",
        "_UNGATED_EDGE_ALLOWLIST",
    ),
    # #5108 four-leg worktree-name gate: each leg's allow-list is the surface
    # an author would edit to silence that leg, so growing it must cost the
    # same visible diff. Registered here (not the retired `single_baselines`
    # list #5104 replaced with this table) so every _baselines.yaml leaf is
    # enforced by a size ratchet (FR-011).
    _SizeRatchet(
        "test_no_worktree_name_guess",
        "signature_allowlist",
        "tests.architectural.test_no_worktree_name_guess",
        "_SIGNATURE_ALLOWLIST",
    ),
    _SizeRatchet(
        "test_no_worktree_name_guess",
        "compose_allowlist",
        "tests.architectural.test_no_worktree_name_guess",
        "_COMPOSE_ALLOWLIST",
    ),
    _SizeRatchet(
        "test_no_worktree_name_guess",
        "match_allowlist",
        "tests.architectural.test_no_worktree_name_guess",
        "_MATCH_ALLOWLIST",
    ),
    _SizeRatchet(
        "test_no_worktree_name_guess",
        "def_use_allowlist",
        "tests.architectural.test_no_worktree_name_guess",
        "_DEF_USE_ALLOWLIST",
    ),
    _SizeRatchet(
        "test_owned_checkout_single_authority",
        "owned_root_bare_path_params",
        "tests.architectural.test_owned_checkout_single_authority",
        "_OWNED_ROOT_BARE_PATH_ALLOWLIST",
    ),
    # Burn-down (a) / FR-009 (#5346): the first cap on the (module, name)
    # dead-symbol allowlist (test_no_dead_symbols.py); value = live count at
    # landing, read only from the loader module (one authority per count).
    _SizeRatchet(
        "test_no_dead_symbols",
        "allowlist_entries",
        _DEAD_SYMBOL_ALLOWLIST_MODULE,
        "SYMBOL_ALLOWLIST",
    ),
    # RK-6 ruling: the widened-scope #470 grandfathered list is also a
    # mutable architectural allowlist (Burn-down (a)); cap it with a second
    # leaf in the SAME section (no new top-level key).
    _SizeRatchet(
        "test_no_dead_symbols",
        "widened_grandfathered_470",
        _DEAD_SYMBOL_ALLOWLIST_MODULE,
        "WIDENED_SCOPE_GRANDFATHERED_470",
    ),
)


def _enforced_leaves() -> frozenset[tuple[str, str]]:
    """Every ``(section, leaf)`` a size comparison enforces, derived from the table."""
    return frozenset((r.section, r.leaf) for r in _SIZE_RATCHETS)


def _yaml_leaves(data: dict[str, Any]) -> frozenset[tuple[str, str]]:
    """Flatten a baselines mapping into its ``(section, leaf)`` pairs.

    Every top-level value must be a mapping of leaves; a scalar section has no
    leaf a comparison could read, so it is refused rather than silently skipped.
    """
    leaves: set[tuple[str, str]] = set()
    for section, body in data.items():
        if not isinstance(body, dict):
            raise ValueError(f"`_baselines.yaml::{section}` must be a mapping of leaf -> integer baseline; got {type(body).__name__}.")
        leaves.update((section, leaf) for leaf in body)
    return frozenset(leaves)


def _leaf_drift(data: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Return ``(unenforced, missing)`` as sorted ``"section.leaf"`` strings.

    *unenforced*: leaves in the YAML that no ``_SIZE_RATCHETS`` row compares.
    *missing*: rows whose leaf the YAML does not carry.
    """
    yaml_leaves = _yaml_leaves(data)
    enforced = _enforced_leaves()
    unenforced = sorted(f"{s}.{leaf}" for s, leaf in yaml_leaves - enforced)
    missing = sorted(f"{s}.{leaf}" for s, leaf in enforced - yaml_leaves)
    return unenforced, missing


# Required top-level keys and ``test_no_dead_modules`` categories are DERIVED
# from ``_SIZE_RATCHETS`` (DIRECTIVE_044: one authority, not parallel lists).
# Adding a gated ratchet means adding ONE ``_SIZE_RATCHETS`` row; the former
# closed ``_GRANDFATHERED_UNREGISTERED_KEYS`` set is retired because an
# unregistered top-level key now surfaces as unenforced leaves in
# ``test_every_baseline_leaf_is_enforced_by_a_size_ratchet``.
_REQUIRED_TOP_LEVEL_KEYS: frozenset[str] = frozenset(r.section for r in _SIZE_RATCHETS)

# Per-category sub-keys for test_no_dead_modules (FR-112 refactor).
_REQUIRED_NO_DEAD_MODULES_CATEGORIES: frozenset[str] = frozenset(r.leaf for r in _SIZE_RATCHETS if r.section == "test_no_dead_modules")


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
        raise ValueError(f"`tests/architectural/_baselines.yaml` is malformed: top level must be a mapping, got {type(data).__name__}.")
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

    The required sections and ``test_no_dead_modules`` categories are derived
    from ``_SIZE_RATCHETS``; there is no second list to register in. The
    schema is defined in
    ``kitty-specs/slice-f-multi-context-extensibility-01KRX5C8/contracts/
    ratchet-baseline-format.md`` and pinned by C-004.
    """
    data = _load_baselines()

    missing = _REQUIRED_TOP_LEVEL_KEYS - set(data.keys())
    assert not missing, (
        f"`_baselines.yaml` is missing required top-level key(s): "
        f"{sorted(missing)}. Each `_SIZE_RATCHETS` section must be recorded "
        f"so the meta-test can compare current size against the baseline. "
        f"To add a gated ratchet, add one `_SIZE_RATCHETS` row plus its YAML "
        f"leaf."
    )

    # test_no_dead_modules must carry per-category sub-keys (FR-112).
    nd_section = data["test_no_dead_modules"]
    assert isinstance(nd_section, dict), "`_baselines.yaml::test_no_dead_modules` must be a mapping of per-category integers (FR-112 refactor)."
    missing_cats = _REQUIRED_NO_DEAD_MODULES_CATEGORIES - set(nd_section.keys())
    assert not missing_cats, (
        f"`_baselines.yaml::test_no_dead_modules` is missing per-category "
        f"key(s): {sorted(missing_cats)}. The FR-112 refactor splits the "
        f"single `_ALLOWLIST` into per-category frozensets so growth in one "
        f"category cannot disguise Cat-7 grandfathered-orphan regression; "
        f"each category is one `_SIZE_RATCHETS` row."
    )


def test_every_baseline_leaf_is_enforced_by_a_size_ratchet() -> None:
    """FR-011 (#3026 defect class): every ``_baselines.yaml`` leaf is enforced.

    A leaf is enforced iff it has a ``_SIZE_RATCHETS`` row, and every row is
    compared by the growth arm with a failing ``>``. Enforcement is therefore by
    construction -- not a key-name search, not a hand registry of allowed keys.
    Both directions are checked: a YAML leaf with no row (unenforced), and a
    row whose leaf the YAML no longer carries (missing).
    """
    unenforced, missing = _leaf_drift(_load_baselines())
    assert (unenforced, missing) == ([], []), (
        f"`_baselines.yaml` leaf drift.\n"
        f"Unenforced leaves {unenforced}: no comparison fails when the live "
        f"size exceeds it: make it enforcing by adding a `_SIZE_RATCHETS` row, "
        f"or delete it.\n"
        f"Missing leaves {missing}: a `_SIZE_RATCHETS` row reads a leaf the "
        f"YAML does not carry: restore the leaf or remove the row."
    )


def _size_comparisons(data: dict[str, Any]) -> list[tuple[_SizeRatchet, int, int]]:
    """Return ``(row, baseline, current)`` for every ``_SIZE_RATCHETS`` row.

    The single comparison source for BOTH arms: each arm only filters (``>`` or
    ``<``) and formats, so the two can never disagree about what is compared.
    """
    return [
        (
            row,
            data[row.section][row.leaf],
            len(_import_module_attr(row.module, row.attr)),
        )
        for row in _SIZE_RATCHETS
    ]


def test_growing_an_allowlist_above_baseline_fails() -> None:
    """Scenario 6 / AC-6: any ratchet growing above its baseline fails this test.

    Iterates ``_SIZE_RATCHETS``: for each row it reads the live allowlist size
    and compares it against ``_baselines.yaml[section][leaf]``.
    ``current > baseline`` => failure naming ``section.leaf`` and the attr.
    Shrinkage (``current < baseline``) is handled by
    ``test_growth_fails_shrinkage_warns`` below.
    """
    growth_failures = [
        f"  - {row.section}.{row.leaf} ({row.attr}): baseline={baseline} "
        f"current={current}. Remove the new entry OR edit _baselines.yaml "
        f"from {baseline} to {current} with a justification comment in the PR."
        for row, baseline, current in _size_comparisons(_load_baselines())
        if current > baseline
    ]

    assert not growth_failures, (
        "Ratchet baseline GROWTH detected (FR-111 violation). The following "
        "allowlists exceeded their pinned baselines:\n" + "\n".join(growth_failures) + "\n\nPer the burn-down policy (Slice F C-004), each growth requires "
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
    shrinkage_messages = [
        f"{row.section}.{row.leaf} ({row.attr}): baseline={baseline} current={current}. Edit _baselines.yaml to lock in the shrinkage."
        for row, baseline, current in _size_comparisons(data)
        if current < baseline
    ]

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


def test_leaf_drift_detects_planted_unenforced_leaf() -> None:
    """NFR-002 self-mutation: ``_leaf_drift`` -- the same pure helper the
    production leaf test calls -- catches planted drift in both directions.

    (a) an extra leaf under an existing section, and (b) a wholly new section
    with no enforcing row at all, are both reported unenforced; removing an
    enforced leaf is reported missing. The synthetic section name
    (``test_never_enforced_section``) must never collide with a real
    ``_SIZE_RATCHETS`` section -- ``test_no_dead_symbols`` is now legitimately
    enforced (WP14, test-suite-remediation-01M3SSDW #5346) and would no
    longer serve as an unenforced-section stand-in.
    """
    planted = copy.deepcopy(_load_baselines())
    planted["test_layer_rules"]["planted_leaf"] = 1
    planted["test_never_enforced_section"] = {"x": 1}
    assert _leaf_drift(planted) == (
        ["test_layer_rules.planted_leaf", "test_never_enforced_section.x"],
        [],
    )

    removed = copy.deepcopy(_load_baselines())
    del removed["test_mutation_ownership_routing"]["destructive_op_allowlist"]
    assert _leaf_drift(removed) == (
        [],
        ["test_mutation_ownership_routing.destructive_op_allowlist"],
    )


@pytest.mark.parametrize("row", _SIZE_RATCHETS, ids=[f"{r.section}.{r.leaf}" for r in _SIZE_RATCHETS])
def test_lowering_an_enforced_leaf_below_live_fails(monkeypatch: pytest.MonkeyPatch, row: _SizeRatchet) -> None:
    """US2-AS4: each ``_SIZE_RATCHETS`` row reads ITS OWN leaf.

    Lowering the row's leaf to ``live - 1`` must make the real growth arm fail
    on a line naming both ``section.leaf`` and the row's attr. A row wired to
    the wrong leaf would not red here. For live-0 rows (e.g.
    ``known_ungated_files``) the leaf becomes ``-1`` and ``0 > -1`` still fails,
    so no special case is needed.
    """
    live = len(_import_module_attr(row.module, row.attr))
    lowered = copy.deepcopy(_load_baselines())
    lowered[row.section][row.leaf] = live - 1
    monkeypatch.setattr(sys.modules[__name__], "_load_baselines", lambda: lowered)

    with pytest.raises(AssertionError) as excinfo:
        test_growing_an_allowlist_above_baseline_fails()

    # The row's own failure line names `section.leaf (attr)` together, and NO
    # other row fails: a second row reading the same leaf, or a row pair with
    # swapped leaves, would surface as an extra failing row.
    message = str(excinfo.value)
    assert f"{row.section}.{row.leaf} ({row.attr})" in message, (
        f"Lowering {row.section}.{row.leaf} below live did not produce a growth failure naming it and {row.attr}:\n{message}"
    )
    others = [f"{r.section}.{r.leaf}" for r in _SIZE_RATCHETS if r != row and f"{r.section}.{r.leaf} ({r.attr})" in message]
    assert not others, f"Lowering {row.section}.{row.leaf} also redded {others}"


def test_size_ratchet_table_meets_floor() -> None:
    """NFR-002 floor: the table cannot silently lose rows or duplicate a leaf."""
    assert len(_SIZE_RATCHETS) >= 19, len(_SIZE_RATCHETS)
    keys = [(r.section, r.leaf) for r in _SIZE_RATCHETS]
    assert len(keys) == len(set(keys)), f"duplicate (section, leaf) rows: {keys}"
    # Shrink-only non-vacuity floor on the gated-section set (FR-006/FR-007,
    # test-suite-remediation-01M3SSDW #5346): a legitimate section addition
    # needs 0 edits here (NFR-003) because the floor is `>=`, not `==`. A
    # legitimate section retirement tightens this floor as a deliberate
    # ratchet step (spec Edge Case 4). `test_no_dead_symbols` (this mission's
    # dead-symbol allowlist cap, which also carries the RK-6
    # `widened_grandfathered_470` leaf in the same section) is one of the
    # gated sections counted here.
    assert len(_REQUIRED_TOP_LEVEL_KEYS) >= 16, sorted(_REQUIRED_TOP_LEVEL_KEYS)


def test_yaml_leaves_refuses_a_scalar_section() -> None:
    """A top-level scalar has no leaf a comparison could read: refuse it."""
    with pytest.raises(ValueError, match="test_no_dead_symbols"):
        _yaml_leaves({"test_no_dead_symbols": 1})


def _synthetic_frozenset(size: int) -> frozenset[str]:
    """A frozenset of *size* distinct sentinels — a stand-in whose only salient
    property to the ratchet is its ``len()``."""
    return frozenset(f"synthetic::{index}" for index in range(size))


def test_non_derived_category_growth_still_reds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-vacuity control (growth): a ``test_no_dead_modules`` category grown
    above its YAML baseline reds the growth arm -- every category row in
    ``_SIZE_RATCHETS`` keeps its teeth.
    """
    nd_module = importlib.import_module(_NO_DEAD_MODULES_MODULE)
    monkeypatch.setattr(nd_module, "_CATEGORY_6_FROZEN_RUNTIME_REEXPORTS", _synthetic_frozenset(500))
    with pytest.raises(AssertionError, match="category_6_frozen_runtime_reexports"):
        test_growing_an_allowlist_above_baseline_fails()


def test_non_derived_category_shrink_still_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Non-vacuity control (shrink): a ``test_no_dead_modules`` category shrunk
    below its YAML baseline IS recorded by the shrink arm.
    """
    nd_module = importlib.import_module(_NO_DEAD_MODULES_MODULE)
    # Probe a category with a non-zero baseline (category 6 drained to 0 in the
    # 2026-09-30 dead-code sweep, so it can no longer shrink).
    monkeypatch.setattr(nd_module, "_CATEGORY_2_BUILD_SCHEMA_GENERATORS", frozenset())
    recorded: list[tuple[str, object]] = []
    test_growth_fails_shrinkage_warns(lambda name, value: recorded.append((name, value)))
    assert any("category_2_build_schema_generators" in str(value) for _, value in recorded), recorded


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
    extra = {(f"src/runtime/baseline_probe_{i}.py", "charter.offering.new_dependency") for i in range(max(1, baseline - len(allowed) + 1))}
    assert not allowed & extra
    monkeypatch.setattr(module, symbol, allowed | extra)
    with pytest.raises(AssertionError, match=symbol):
        test_growing_an_allowlist_above_baseline_fails()
    monkeypatch.setattr(module, symbol, frozenset())
    recorded: list[tuple[str, object]] = []
    test_growth_fails_shrinkage_warns(lambda name, value: recorded.append((name, value)))
    assert any(symbol in str(value) for _, value in recorded), recorded


def test_legacy_contract_allowlist_growth_still_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """FR-003 NFR-003 / Contract B: retiring the advisory `skip_marker_blocks`
    leaf did NOT loosen the C-001 sibling. `legacy_contract_allowlist` stays
    pinned at 151 AND its growth still reds the growth arm (the retirement was
    scoped to the skip-marker leaf only).
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
