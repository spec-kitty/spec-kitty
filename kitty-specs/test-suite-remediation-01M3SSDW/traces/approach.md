# Approach: test-suite-remediation-01M3SSDW

Running log, with dated entries of 1–3 sentences each.

- 2026-09-30: The operator narrowed the scope to two tracks: (1) masked greens and (2) architectural pin honesty (#5346). Integration-harness honesty is out of scope while #5417 is in flight.
- 2026-09-30: Planning research ran as three profile-loaded Opus lenses (masked-green dispositions, exact-count pin inventory, dead-symbol re-key design). Together they covered the post-spec adversarial check and the brownfield scout point-cut.
- 2026-09-30: The masked-green research found more than the triage did:
  - **Doctrine tests.** Unmasking them exposes a small product defect: `pack_validator` ignores `drg/fragment.yaml` intent. That's FR-005, fixed in-mission.
  - **Quarantined accept tests.** They are collected by no lane at all: the quarantine lane was deleted, and the file sits outside the test matrix.
  - **Contract round-trips.** 10 of them skip forever because archived contract docs name moved modules.
  The plan-authoring pass (architect lens) folds all three into the concern map.
- 2026-09-30: Closeout fold list from the per-WP reviews (non-blocking):
  - WP03: the `test_acceptance_support.py:139` docstring still says "quarantined".
  - WP02: `test_saas_sync_gate_selection_invariance.py:63` and `:133-141` still state the old #3213 premise, in the docstring and the failure message.
  - WP02: awkward wording at `test_egress_consent_boundary.py:173-174`.
  - WP01: the evidence `kind: RUN` is not in the data-model kind enum. Reconcile when evidence is materialized.
- 2026-09-30: Closeout fold list, WP04 review nits:
  - Stale "pre-WP04" prose in `test_real_home_isolation_guard.py`: the `_detect_worker_homes` docstring (~:192), the comment at ~:62, the comment at ~:216-218, and the transport-test docstring.
  - The name `test_matches_upstream_registry_when_available` is misleading.
  - The budget test does not check that the emit run succeeded (the correctness sibling covers it).
- 2026-09-30: Closeout fold list, WP01 review:
  - **Fold red-first before the PR.** A `drg/fragment.yaml` edge with bare-id endpoints (declared under `nodes:`) still emits the spurious `same_id_collision`, because `_urn_to_plural` drops non-`kind:id` endpoints. This is the same bug class as #5494.
  - **Minor:** `load_org_pack` now runs twice per `validate_pack` call.
  - **Evidence corrections:** EV-IC01-02 misstates the red-commit contents, and the `kind: RUN` vocabulary still needs reconciling.
- 2026-09-30: Two cycle-1 rejections, both reviewer catches of gaps a planted break exposes:
  - **WP05:** a longest-prefix test re-computed the production sort itself. The `reverse=False` mutant survived.
  - **WP06, row 6:** converting full-signature mock pins to identity asserts dropped the `mission_branch` threading contract, the only guard for it (C-002). The gap came from the pin inventory in the plan.
  Lesson: when a full-signature pin becomes an identity assert, enumerate every keyword the old pin held, and keep or replace each one that carries a contract.
- 2026-10-01: Closeout fold list, WP09 review advisories:
  - **FR-007 class, to fold:** `tests/agent/test_agent_config_migration.py:85` and `:103` still assert `len(agent_dirs) == 13`, which is really `len(AGENT_DIRS)`.
  - **Stale docstring:** `test_occurrence_map_field_paths.py:5-8`.
  - **Redundant filter:** the F5 expected-count filter copies `glossary_linker.py:129`.
  - **Loose match:** the F4 `fnmatch` path check; `PurePosixPath.match` would be stricter.
- 2026-10-01: Closeout fold list, WP07 review:
  - **Relational check (to fold):** in `test_tasks_compat_surface.py`, assert `set(_SEAM_GROUPS) == set(_SEAM_MODULES) ==` the six seam names. This closes the whole-group drop that the old count caught.
  - **mypy (to fold):** `tests/ci/test_recapture_charter_shard_timings.py:502`, the lambda recorder raises `func-returns-value` under `mypy --strict`. Replace it with a 3-line `def`.
- 2026-10-01: Closeout fold list, WP08 cycle-2 note: the history paragraph at ~:63 of `test_remediation_effectiveness.py` credits `test_exemption_set_meets_floor` with the removed sum pin. It is historical narrative; reword it.
- 2026-10-01: WP12 leftover, going into WP13's brief as a sanctioned out-of-map YAML prose edit: the `category_c_mission_type_drg_edges…` rationale (~line 306 of `dead_symbol_allowlist.yaml`) still cites the deleted `_compute_dangling` refresh guidance.
- 2026-10-01: WP12 approved after 11 adversarial plants against the old and new gates. The new gate is stricter in 3 places: move detection, no false red on a byte-identical twin, and star-import MOOT. Follow-up issue at closeout: a new dead name in a star-imported module with no allowlist entries is silent on both gates (predates WP12).
- 2026-10-01: Closeout fold list, WP14 nits: the floor comment still carries a '15 pre-#5346 sections' landing sentence, which the WP asked to delete, and `len(_SIZE_RATCHETS) >= 19` sits well below the live 27. That second one is outside scope and only noted.
- 2026-10-01: Closeout fold list, WP13 nits: the comment at `test_symbol_key.py:661-675` says 'six deleted tests' where 7 were deleted, and it omits where G5 is covered. Follow-up candidate: `SymbolKey.as_tuple` has no caller outside the tests.
- 2026-10-01: Closeout fold list, WP15 nits: in `ci-gate-mechanics.md`, an entry's rationale is optional (it falls back to the category rationale); the ADR's 'Chosen option 1.' lacks its 'because' clause; how-to §2c does not say how to declare a new category.
