# Tasks: One authority for per-user cache and state locations (#6488)

**Mission**: `per-user-locations-single-authority-01M68JF2` · **Topology**: `coord`
(WPs land on lanes, then the coordination branch) · **Target**:
`issue-6488-per-user-locations-single-authority`

Each WP follows ATDD-first (charter C-011): the failing test is committed before the
implementation commit of that WP. Validation per `CLAUDE.md` test policy and
`NO_FULL_HEAVY_SUITES_IN_MISSION` — the named test modules and the named architectural
gates, never a full sweep.

Red-first entry point for the defect: **the six production resolvers themselves**
(`specify_cli.core.upgrade_notifier._default_cache_path`,
`charter.offering.packs.pack_fetch.default_cache_root`,
`kernel.service_artifacts.default_cache_root`,
`specify_cli.compat.cache._resolve_cache_dir`,
`specify_cli.compat.config._resolve_config_dir`,
`runtime.next._runtime_pkg_notice._marker_path`), not a helper underneath them.
`tests/kernel/test_user_dirs_convergence.py` (WP02/T005) is the guard that must be red on
the pre-fix tree.

## WP01 — The resolution authority (IC-01)

Owns FR-001, FR-002, FR-004, FR-008, NFR-002. Depends: none.

- **T001** Red-first: rewrite `tests/kernel/test_user_dirs.py` as the branch pins for the
  new contract — `user_cache_dir`, `user_state_dir`, `user_config_dir`, each per platform
  (linux/darwin/windows faked), with XDG precedence, empty-variable fallback, and
  `appauthor=False` on Windows. The pins assert the macOS `~/Library/Caches/spec-kitty`
  and `~/Library/Application Support/spec-kitty` defaults that the pre-fix helper cannot
  produce, so the module is red before T002.
- **T002** `src/kernel/user_dirs.py`: build the `platformdirs` class explicitly
  (`Windows`/`MacOS`/`Unix`) from `kernel.paths.is_windows()` and `sys.platform`; expose
  cache/state/config as the *app* directory with `appname="spec-kitty"`,
  `appauthor=False`; delete `windows_local_appdata`; rewrite the module docstring to state
  the rule and to name `platformdirs` as the authority. (FR-001, FR-002, FR-004, FR-008)
- **T003** `tests/kernel/_user_dirs_pins.py`: extend the fake-platform fixture to clear
  `XDG_CONFIG_HOME`, `APPDATA`, `LOCALAPPDATA` and the `WIN_PD_OVERRIDE_*` variables the
  `platformdirs` Windows class reads off `win32`, and to set `USERPROFILE`, so one fixture
  drives all three platforms. (FR-004)
- **T004** Purity pin: resolving any kind into a non-existent base creates nothing and
  raises nothing (NFR-002), and the kernel module imports no `charter`/`specify_cli`
  symbol (NFR-001) — the existing architectural gate stays green unchanged.

## WP02 — Caller convergence (IC-02, IC-03)

Owns FR-003, FR-005, FR-006, FR-007, FR-011 (docstring half). Depends: WP01.

- **T005** Red-first: `tests/kernel/test_user_dirs_convergence.py` — enumerate the six
  callers, resolve each under one faked platform, and assert every path is under the
  authority's directory for its kind (Invariant C1). Fails on the pre-fix tree for the
  macOS case, naming the divergent callers.
- **T006** Route the six callers: drop the literal `"spec-kitty"` segment and the
  `windows_local_appdata=False` argument from `upgrade_notifier`, `pack_fetch`,
  `service_artifacts`, `compat/cache`, `compat/config` (via the new config resolver) and
  `_runtime_pkg_notice`; update the five per-caller pin tests to the new locations.
  (FR-003, FR-005, FR-007)
- **T007** Delete the unreachable `platformdirs`-`ImportError` fallbacks and their now-dead
  imports in `specify_cli/compat/cache.py` and `specify_cli/compat/config.py`; retarget
  `tests/specify_cli/compat/test_config.py` accordingly. (FR-007)
- **T008** Correct the `_runtime_pkg_notice._marker_path` docstring and the
  `NagCache.default` docstring so each states the rule the code follows. (FR-011)

## WP03 — Legacy location discard (IC-04)

Owns FR-009, FR-010, NFR-003. Depends: WP01.

- **T009** Red-first: `tests/kernel/test_user_dirs_legacy.py` — on one fixture, a planted
  macOS legacy root is removed while a root that is current for some kind survives; the
  Linux case removes nothing; a symlinked candidate and a candidate holding a git checkout
  survive; a removal failure leaves stdout and the exit code unchanged.
- **T010** `src/kernel/user_dirs_legacy.py`: enumerate the legacy cache/state/config roots
  from the pre-fix rules, skip any candidate that is current for any kind, and remove the
  rest through `kernel.tree_removal.remove_tool_owned_tree(..., best_effort=True)` with a
  symlink guard and debug-level logging. (FR-009, FR-010, NFR-003)
- **T011** Wire it as a fourth owner in the CLI startup list
  (`prepare_startup_assets` in `src/specify_cli/__init__.py`) so it runs at most once per
  process and cannot fail a command; add the registration assertion. (FR-009, NFR-003)
- **T012** Record the discard policy in the module docstrings and in
  `data-model.md`'s invariants (L1–L4); no behaviour beyond T010.

## WP04 — Mutation proof, docs and changelog (IC-05)

Owns FR-011 (docs half), SC-003, SC-005. Depends: WP02, WP03.

- **T013** Mutation proof of the guard: revert each of the six callers to its pre-Mission
  rule in turn and confirm `test_user_dirs_convergence.py` goes red each time (6/6);
  record the per-caller result in `traces/approach.md`. (SC-003)
- **T014** `docs/changelog/CHANGELOG.md` `[Unreleased]`: one entry citing `(#6488)`,
  impact-first, before/after, the per-platform locations and the fact that nothing is
  migrated; under 1,200 characters. (SC-005)
- **T015** Update the docs that name a cache path —
  `docs/development/how-to/sync-packs.md`, `docs/development/how-to/service-pins.md`,
  `docs/guides/how-to/installation/install-and-upgrade.md` — to state the platform rule
  instead of a single Linux path. (FR-011)
- **T016** Verification sweep: `check_docs_freshness --ci` (errors=0),
  `tests/architectural/test_no_legacy_terminology.py`, ruff and mypy on the touched
  files, and the issue-matrix verdict for #6488.

## Requirement mapping

| WP | requirement_refs |
|----|------------------|
| WP01 | FR-001, FR-002, FR-004, FR-008, NFR-001, NFR-002, SC-002 |
| WP02 | FR-003, FR-005, FR-006, FR-007, FR-011, SC-001, SC-003 |
| WP03 | FR-009, FR-010, NFR-003, SC-004 |
| WP04 | FR-011, NFR-004, NFR-005, SC-005 |
