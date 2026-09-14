"""Shard registry — ``arch`` group row (data-model E1), registered via the seam.

Originated as the single-source arch-adversarial pole shard-assignment table
(mission ``ci-health-charter-path-and-arch-shard-01KWRTB2`` WP02, #2397), then
generalized into an N-group registry (mission
``ci-test-topology-performance-01KXBJRT`` WP01, FR-002/C-003/D-044): ``arch``
and ``next`` (registered by the sibling ``tests/_next_shard_map.py``) are two
rows of *one* mechanism.

Mission ``test-suite-friction-remediation-01KXDKBX`` WP16 (FR-011, #2621)
replaced the shared ``SHARD_GROUPS`` dict this module used to own and mutate
directly with the explicit ``register()``/``all_groups()`` seam in
``tests/_shard_registry.py`` — see that module's docstring for the rationale
(diagnosable failure on a missing group, no import-side-effect dict
mutation). This module now owns only the ``arch`` row's data and registers it
through the seam; it holds no registry mechanism of its own.

The ``arch-adversarial`` CI job runs the 4 pole roots — ``tests/adversarial``,
``tests/architectural``, ``tests/architecture``, ``tests/lint`` — as a single
matrix leg. This module owns that group's row: 3 balanced, disjoint shards,
keyed by whole test-file (for ``tests/architectural/*.py``) or whole directory
(for the other three pole roots, folded in as functional units per the
operator's "whole test files kept intact, not split" steer, Decision Moment
``DM-01KWRWB0PPF5TQPNYF5D07XY3W``).

The concrete assignment below is copied **verbatim** from
``kitty-specs/ci-health-charter-path-and-arch-shard-01KWRTB2/data-model.md``
(a 216 / 215 / 215 greedy bin-packing result balanced by a ``def test_`` count
proxy — see ``research.md`` R2 for the honesty caveat that this is a structural
projection, not a live-duration measurement) and reshaped into the
``ShardGroup`` row **byte-for-byte** — no relpath moves shard as part of this
generalization. Rebalance by editing this table directly if a future CI run
shows material drift.

``tests/conftest.py``'s ``pytest_collection_modifyitems`` hook applies the
matching ``<marker_prefix>_<N>`` marker to every collected test whose file
falls under one of a registered group's roots, driven by iterating
``tests._shard_registry.all_groups()``, looked up via
``tests._shard_registry.shard_for``. Nothing outside a group's roots is
touched: ``shard_for`` returns ``None`` for any path not covered by the
requested group and not auto-covered by the fallback described below, which
is what keeps the hook scoped (enforced by
``tests/architectural/test_arch_shard_marker_completeness.py`` /
``test_next_shard_marker_completeness.py``, GC-1).

**Auto-cover fallback (FR-011, #2671) — new files no longer require a manual
edit to keep main green.** Before this WP, a new ``tests/architectural/*.py``
file that was not appended to one of the ``_ARCH_SHARD_N_FILES`` tuples below
resolved to ``shard_for(...) is None``: the collection hook applied no
``arch_shard_N`` marker, and both the GC-1 completeness gate and the
zero-gate-orphan gate (``tests/architectural/test_ci_collection_completeness.py``) went
red. This landing gap recurred 3+ times (see the "Added post-data-model.md"
annotations scattered through the tables below — each one documents a prior
occurrence that had to be hand-patched). This module's ``arch`` row now sets
``default_fallback=True`` on its ``ShardGroup`` (``tests/_shard_registry.py``
owns the mechanism): any under-root file that misses every explicit
``dir_assignment`` / ``file_assignment`` entry is assigned a deterministic
hash-bucket shard instead of ``None``, so a brand-new file is auto-covered by
construction — **no manual table edit is required just to keep main green.**

The explicit ``_ARCH_SHARD_N_FILES`` / ``_ARCH_SHARD_N_DIRS`` tables below
remain the **authoritative balance control**, not a keep-green obligation:
add a file here only when you want to pin it to a specific shard for load
balance (or to keep a related family of tests on one leg, as several of the
comments below do) — an explicit entry always overrides the hash-bucket
fallback. The ``next`` group (``tests/_next_shard_map.py``) has deliberately
NOT opted into the fallback (``default_fallback`` is omitted there, so it
stays ``False``) — this generalization is scoped to ``arch`` only.

This module is pure data + one ``register()`` call at import time — no
pytest import — so it stays trivially unit-testable and reviewable as "just a
table."
"""

from __future__ import annotations

from tests._shard_registry import ShardGroup, register

# Whole-directory pole roots folded in as single functional units (never
# split across shards).
_ARCH_SHARD_1_DIRS: tuple[str, ...] = ("tests/adversarial",)
_ARCH_SHARD_2_DIRS: tuple[str, ...] = ("tests/lint",)
_ARCH_SHARD_3_DIRS: tuple[str, ...] = ("tests/architecture",)

# Individual `tests/architectural/*.py` file assignments — copied verbatim from
# data-model.md's committed 216 / 215 / 215 split.
_ARCH_SHARD_1_FILES: tuple[str, ...] = (
    # Added post-data-model.md (new file, mission
    # verification-trust-3115-01KYVYWM WP03, FR-003/#3115 — the CLI console
    # render-width guard). shard_1 and shard_2 were tied lightest by file
    # count (36 vs 36/39) when this file landed; shard_1 is the convention's
    # default first pick on a tie (see the neighboring picks below for the
    # same rule applied repeatedly).
    # Added post-data-model.md (new file at implementation time, mission
    # ci-test-topology-performance-01KXBJRT WP01, FR-002 — the ``next`` group's
    # completeness guard, sibling to test_arch_shard_marker_completeness.py).
    # shard_1 was the lightest by file count (33 vs 34/34) when this file
    # landed, so it lands here.
    # Added post-data-model.md (new file, mission
    # ci-test-topology-performance-01KXBJRT WP04, #2590 — the GC-5
    # marker-baseline guard). WP04 landed this file without registering it in
    # this shard map, leaving it selected by zero arch_shard_N marker (GC-1
    # violation); WP06 (T014/T020, sole owner of ci-quality.yml and the
    # cross-lane roster pass) closes the gap as a follow-on data edit. All
    # three shards were tied at 34 files each when this fix landed; shard_1
    # was picked first (alphabetically paired with test_workflow_dist_lint.py
    # in shard_2 below) to keep the pick auditable.
    # Added post-data-model.md (new file, mission
    # resolver-seam-completion / #2651 commit 96e225d07 — the C-003
    # ``*parity_scaffold*`` reappearance guard). That commit landed the file
    # without registering it in this shard map, leaving it selected by zero
    # ``arch_shard_N`` marker (GC-1 violation) AND absent from the
    # gate-coverage baseline (a zero-gate orphan) — main went red on both
    # ``test_arch_shard_marker_completeness`` and ``test_no_new_orphan_surfaces``.
    # Folded here during the #2670 landing pass (campsite cleaning). shard_1
    # and shard_2 were tied lightest by file count (35 vs 35/39) when this fix
    # landed; shard_1 is the convention's default first pick on a tie.
    # Added post-data-model.md (new file at implementation time, mission
    # cmd-output-file-leak-guard-01KWVZX7 #2169 WP01). All three shards were
    # tied at 30 files each when this guard landed; shard_1 was picked
    # arbitrarily to keep the table's insertion order alphabetical-ish and
    # the pick auditable.
    "tests/architectural/test_docs_cli_reference_parity.py",
    # Added by mission rc3-execution-mode-consolidation-01M0GGX1 (M7, WP02): the
    # ExecutionMode/WorkProductKind re-drift guard (4 tests). shard_1 was the
    # lightest by file count (17 vs 22/30) when this file landed.
    "tests/architectural/test_execution_mode_no_redrift.py",
    "tests/architectural/test_integration_boundary.py",
    "tests/architectural/test_marker_job_completeness.py",
    "tests/architectural/test_no_dead_symbols.py",
    "tests/architectural/test_no_invalid_windows_filenames.py",
    "tests/architectural/test_no_legacy_status_emit_callers.py",
    "tests/architectural/test_no_legacy_terminology.py",
    "tests/architectural/test_no_write_side_rederivation.py",
    "tests/architectural/test_quarantine_marker.py",
    "tests/architectural/test_runtime_charter_doctrine_boundary.py",
    "tests/architectural/test_session_reaper.py",
    "tests/architectural/test_shared_package_boundary.py",
    "tests/architectural/test_single_mission_surface_resolver.py",
    "tests/architectural/test_status_module_boundary.py",
    "tests/architectural/test_topology_inference_retired.py",
    "tests/architectural/test_unregistered_shim_scanner.py",
    # Added post-data-model.md (new file, mission
    # review-cycle-verdict-seam-rebuild-01KZ2W7W WP02, FR-014/SC-013 -- the
    # absolute-event-timestamp mixture guard closing #3157's class of
    # defect). Recounted by `def test_` after WP01's own append to shard_3
    # landed: shard_1=288, shard_2=312,
    # shard_3=308 -- shard_1 was the lightest, so this 10-test file lands
    # here (note: a naive grep for `^def test_` over this file's own text
    # returns 17, not 10 -- 7 of those lines are `def test_...` occurrences
    # embedded inside this file's own synthetic fixture *source strings*,
    # not real pytest-collected functions; `pytest --collect-only` confirms
    # 10 real tests, which is the weight used for this placement decision).
    # Added 2026-08-08 (PR #3252 landing pass -- the repo-wide patch-seam gate
    # salvaged from #3252 after its module-local `_sleep` alias fix was
    # superseded by main's #3187 instance seam). shard_1 and shard_2 were tied
    # lightest by file count (38 vs 38/45) when this file landed; shard_1 is
    # the convention's default first pick on a tie.
    # Added by mission tidy-charter-cutover-surface-01M18R5B WP01 (#3818): the
    # stale charter path-literal guardrail (mock-target/allowlist/doc-link
    # stragglers the C-004 import gate misses). shard_1 was the lightest by
    # file count (18 vs 21/29) when this file landed, so it lands here.
    "tests/architectural/test_no_stale_charter_path_literals.py",
)

_ARCH_SHARD_2_FILES: tuple[str, ...] = (
    # Added post-data-model.md (new file, mission
    # ci-test-topology-performance-01KXBJRT WP04, #2590 — the GC-4
    # workflow-dist lint guard). Same landing gap as
    # test_marker_baseline.py above (WP04 forgot to register it in this shard
    # map); WP06 closes it as a follow-on data edit. Paired into shard_2
    # (sibling of shard_1's pick above) while shards were still tied at 34
    # files each.
    # Added post-data-model.md (new file at implementation time — data-model.md
    # §"Any tests/architectural/*.py file not listed above ... is an
    # assignment gap the completeness guard must catch"). shard_2 was the
    # lightest by file count (29 vs 30/30) at the time this WP was
    # implemented, so it lands here.
    "tests/architectural/test_arch_shard_marker_completeness.py",
    # Added post-data-model.md (new file, mission
    # coord-authority-trio-degod-01KX7094 WP05 -- the trio seam-only +
    # cores-no-I/O gates, FR-004/FR-007). shard_2 was the lightest by file
    # count (32 vs 33/34) when this file landed, so it lands here.
    "tests/architectural/test_trio_seam_only.py",
    "tests/architectural/test_coord_read_residuals_closeout.py",
    "tests/architectural/test_execution_context_parity.py",
    # Added post-data-model.md (new file, mission mission-resolver-port-01KX1C05
    # WP07 #2447 doctrine-phantom guard). shard_2 was tied lightest by file
    # count (31 vs 33/31) when this file landed, so it lands here.
    "tests/architectural/test_git_matrix_paths_resolve.py",
    # Added post-data-model.md (new file from mission
    # read-surface-ssot-closeout-01KWZV91, the inline meta-read gate). shard_2
    # was the lightest by both file count (30 vs 33/31) and test-fn count
    # (223 vs 287/232) when this file landed, so it lands here.
    "tests/architectural/test_merge_pipeline_ratchets.py",
    "tests/architectural/test_migration_chain_integrity.py",
    "tests/architectural/test_mission_runtime_surface.py",
    "tests/architectural/test_no_op_stable_writes.py",
    "tests/architectural/test_no_runtime_pypi_dep.py",
    "tests/architectural/test_org_activation_seam.py",
    "tests/architectural/test_pyproject_shape.py",
    "tests/architectural/test_ratchet_baselines.py",
    # Added post-data-model.md (new file at implementation time, mission
    # content-address-ratchet-allowlists-01KX8M4D WP05, #2469/#2495 IC-METAGUARD
    # standing positional-anchor ban). shard_2 was the lightest by file count
    # (32 vs 33/34) when this file landed, so it lands here.
    "tests/architectural/test_ratchet_positional_anchor_ban.py",
    "tests/architectural/test_tid251_enforcement.py",
    "tests/architectural/test_untrusted_path_containment.py",
    "tests/architectural/test_write_surface_placement_guard.py",
    # Added post-data-model.md (new file, mission
    # mission-type-single-source-gate-wiring-01KXKHVZ WP05, #2666 — the FR-013
    # built-in cross-grain-scan structural gate). shard_1 and shard_2 were
    # tied lightest by file count (35 vs 35/39) when this file landed;
    # shard_2 was picked to keep the split even.
    # Added post-data-model.md (new file, mission
    # verification-trust-3115-01KYVYWM landing fold — the WP12 --timeout
    # gate, closing the #3143 follow-up: nothing asserted the ~17
    # --timeout=240 flags WP12 added to ci-quality.yml's fast-tier jobs
    # stayed present). shard_2 was the lightest by file count (36 vs 37/39)
    # when this file landed, so it lands here.
    # Added post-data-model.md (new file, mission
    # review-cycle-verdict-seam-rebuild-01KZ2W7W WP16, FR-017/SC-007 — the
    # test-name-truthfulness audit over the touched-union-keyword-matched
    # denominator). shard_2 was the lightest by file count (37 vs 38/40) when
    # this file landed (4 real tests by `pytest --collect-only`), so it lands
    # here.
    # Added 2026-08-08 (PR #3252 landing pass, sibling of
    # test_shared_module_object_patches.py above -- the census control fixture
    # this gate's predicate is consumed from, SC-015). shard_1 and shard_2 were
    # tied lightest by file count (38 vs 38/45, before the sibling above's
    # shard_1 append) when this file landed, so it lands here to keep the two
    # new siblings balanced across shards rather than both on one leg.
    # Added 2026-08-14 (PR #3437 landing pass, mission
    # write-path-integrity-01KZZD69 WP01 -- the git_topology one-copy gate,
    # SC-007/SC-008). New file left unregistered by the mission; joins shard_2
    # (its WP04 sibling test_wp_integrity_partition_call_shape.py lands in
    # shard_3 to keep the split even).
    "tests/architectural/test_git_topology_one_copy.py",
)

_ARCH_SHARD_3_FILES: tuple[str, ...] = (
    # Added post-data-model.md (new file, mission
    # test-suite-friction-remediation-01KXDKBX WP11, #2076/FR-014 -- the
    # golden-count recurrence guard). shard_3 was the lightest by file count
    # (34 vs 35/35) when this file landed, so it lands here. NOTE: WP16 (this
    # mission, #2621/FR-011) is the downstream serial dependent that replaces
    # this SHARD_GROUPS-dict idiom with the `register()` seam described in
    # this module's docstring -- WP11 registers under the CURRENT idiom (the
    # only one that exists at WP11's landing time) and WP16 carries this exact
    # entry forward into the new seam. This is a recorded out-of-map append to
    # WP16's owned file, not a cross-lane trivial-merge conflict to resolve.
    "tests/architectural/test_auth_transport_singleton.py",
    "tests/architectural/test_builtin_override_policy.py",
    "tests/architectural/test_ci_quality_path_filters.py",
    "tests/architectural/test_events_tracker_public_imports.py",
    "tests/architectural/_gate_read_callshape.py",
    "tests/architectural/test_guard_capability_call_sites.py",
    "tests/architectural/test_layer_rules.py",
    # Added post-data-model.md (new file at implementation time, mission
    # mission-resolver-port-01KX1C05 WP04, #2173 FR-007). shard_3 was the
    # lightest by def-test_ count (232 vs 287/251) when this file landed.
    "tests/architectural/test_mission_resolver_walker_gate.py",
    "tests/architectural/test_no_dead_modules.py",
    "tests/architectural/test_no_shipped_layer_label.py",
    "tests/architectural/test_no_tmp_paths_in_tests.py",
    "tests/architectural/test_no_worktree_name_guess.py",
    # Added post-data-model.md (new file at implementation time, mission
    # review-regression-gate-01KWX6DF WP01, #572/#1979/#2283). shard_3 was the
    # lightest by file count (30 vs 31/31) when this file landed.
    "tests/architectural/test_protection_resolver_call_sites.py",
    "tests/architectural/test_real_home_isolation_guard.py",
    # Added post-data-model.md (new file — mission
    # contract-ownership-boundary-01KWYRE5 WP02, #2441). shard_3 and shard_2
    # were tied at 30 files each when this landed; shard_3 was picked to keep
    # the driver near its content-anchoring siblings and the pick auditable.
    "tests/architectural/test_safety_registry_completeness.py",
    "tests/architectural/test_same_tier_uniqueness.py",
    "tests/architectural/test_shim_registry_schema.py",
    # Added post-data-model.md (new files, mission
    # test-suite-friction-remediation-01KXDKBX WP17, #2622/#2623 -- the
    # quality-gate.needs containment guard (FR-012) and the Sonar UI-e2e
    # coverage-discovery wiring guard (FR-013). All three shards were tied at
    # 35 files each when these landed; shard_3 was the lightest by
    # def-test_ count (258 vs 261/296), so both land here.
    "tests/architectural/test_suite_jobs_gate_blocking.py",
    # Added post-data-model.md (new file, mission
    # sonar-per-pr-coverage-reuse-01M2FR32 WP04, #4334 -- the permanent
    # fault-injection battery against duplicate per-change suite execution,
    # 24 tests). shard_3 was the lightest by def-test_ count (84 vs 182/160)
    # when this file landed, and it is the direct sibling of
    # test_suite_jobs_gate_blocking.py above (same workflow surface, same
    # _gate_coverage substrate), so keeping the family on one leg is free.
    "tests/architectural/test_no_duplicate_suite_execution.py",
    # Added post-data-model.md (new files, mission
    # test-suite-friction-remediation-01KXDKBX review-remediation / #2632 --
    # the allow_worktree_context blast-radius guard (squad finding, alphonso)
    # and the CliConsole single-seam guard (#2632). shard_3 remained the
    # lightest by def-test_ count when these landed, matching the WP11/WP17
    # appends above.
    "tests/architectural/test_no_production_worktree_guard_bypass.py",
    "tests/architectural/test_cli_console_single_seam.py",
    # Added post-data-model.md (new files, mission
    # charter-sole-door-bypass-closure-01KZ3WAA landing-fold gate hardening --
    # the five sole-door durability gates (agent-profile repository, raw
    # DoctrineService, charter.offering.resolver import ban, missions-root hardcode
    # ban, ._inner reach-around ban) were never appended to this map when
    # WP04/WP06/WP09 landed them, leaving them selected by zero arch_shard_N
    # marker until the default_fallback hash-bucket auto-cover picked them up
    # (FR-011/#2671) -- registering them explicitly here is the authoritative
    # balance-control pin the fallback intentionally does not replace. shard_3
    # was the lightest by def-test_ count (215 vs 274/295) when this fold
    # landed, so all five land here; the sixth new module this fold ships,
    # tests/architectural/_sole_door_scan.py, is a non-test helper library
    # (zero `def test_` functions) and is deliberately NOT registered --
    # `pytest_collection_modifyitems` only marks collected test items, so an
    # unregistered helper module with no tests never needs (or gets) a shard
    # marker.
    "tests/architectural/test_charter_sole_door_agent_profile_repository.py",
    "tests/architectural/test_charter_sole_door_doctrine_service.py",
    "tests/architectural/test_charter_sole_door_resolver_imports.py",
    "tests/architectural/test_charter_sole_door_hardcoded_paths.py",
    "tests/architectural/test_charter_sole_door_inner_reacharound.py",
    # Added post-data-model.md (new file, mission
    # review-cycle-verdict-seam-rebuild-01KZ2W7W WP01, NFR-007/FR-020 -- the
    # verdict-seam census check). Measured at implementation time by `def
    # test_` count: shard_1=288, shard_2=312, shard_3=286 -- shard_3 was the
    # lightest, so this 18-test file lands here.
    # Added 2026-08-14 (PR #3437 landing pass, mission
    # write-path-integrity-01KZZD69 WP04 -- the FR-011 partition call-shape
    # gate). New file left unregistered by the mission; lands in shard_3 (its
    # WP01 sibling test_git_topology_one_copy.py lands in shard_2 to keep the
    # split even).
    "tests/architectural/test_wp_integrity_partition_call_shape.py",
)

# ``relpath -> shard`` for exact-file (architectural) units.
_ARCH_FILE_ASSIGNMENT: dict[str, int] = {
    **dict.fromkeys(_ARCH_SHARD_1_FILES, 1),
    **dict.fromkeys(_ARCH_SHARD_2_FILES, 2),
    **dict.fromkeys(_ARCH_SHARD_3_FILES, 3),
}

# ``dirpath -> shard`` for whole-directory (adversarial / architecture / lint)
# units.
_ARCH_DIR_ASSIGNMENT: dict[str, int] = {
    **dict.fromkeys(_ARCH_SHARD_1_DIRS, 1),
    **dict.fromkeys(_ARCH_SHARD_2_DIRS, 2),
    **dict.fromkeys(_ARCH_SHARD_3_DIRS, 3),
}

# The 4 pole roots the ``arch`` group (and the collection hook, for this
# group) is scoped to. Anything outside these roots must never receive an
# ``arch_shard_N`` marker.
_ARCH_POLE_ROOTS: tuple[str, ...] = (
    "tests/adversarial",
    "tests/architectural",
    "tests/architecture",
    "tests/lint",
)


# Register the ``arch`` row through the explicit seam (`tests/_shard_registry`,
# FR-011/#2621) — the one place this module's row is assembled. No shared
# dict is mutated here; `tests/_next_shard_map.py` registers its own `next`
# row into the SAME seam independently (D-044/C-003 — one registry, not a
# cloned second one), and `tests/conftest.py` / the completeness guard consume
# both rows via `tests._shard_registry.all_groups()` / `get_group()`, never a
# hardcoded group name.
register(
    ShardGroup(
        group="arch",
        roots=_ARCH_POLE_ROOTS,
        shard_count=3,
        marker_prefix="arch_shard",
        dir_assignment=_ARCH_DIR_ASSIGNMENT,
        file_assignment=_ARCH_FILE_ASSIGNMENT,
        default_fallback=True,
    )
)
