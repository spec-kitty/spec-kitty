---
affected_files: []
cycle_number: 1
mission_slug: coord-artifact-single-home-01M3V4BE
reproduction_command:
reviewed_at: '2026-10-01T10:45:39Z'
reviewer_agent: claude
wp_id: WP02
---

# WP02 review: changes requested (reviewer-renata, claude/opus)

Commit reviewed: 763d44aaf3 on lane-b (base kitty/mission-coord-artifact-single-home-01M3V4BE).

## What is good (keep)

- ruff check, ruff format --check, and mypy --strict are clean on all 3 files. No `src/` changes.
- 35/35 tests pass (`tests/coordination/test_coord_mission_factory.py` + `tests/_factories/`). The new module has 95% coverage. The whole `tests/coordination/` directory passes (266/266), so there are no fixture-name clashes.
- `materialized=True` is correct. It uses a real `git worktree add` through `CoordinationWorkspace.resolve`, it seeds `status.events.jsonl` only (never `meta.json`), and its commit has no `Spec-Kitty-Coordination-Seed` trailer. `probe_coord_state` checks for MATERIALIZED inside the builder.
- The DELETED and remote-only variants follow the binding correction. The probes are pure git plumbing (`git show`, `git ls-tree`, `git log --format=%H`). `lamports` tolerates a missing field.
- Fork fixture (d) bypasses `placement_seam`, and that is a faithful reproduction of the pre-fix #3928 placement. It uses the production `decisions.store` primitives, so `index.json` and `DM-*.md` are production-shaped. They are committed only on the coordination branch and are absent from the root checkout and the target branch.

## Findings

### H1 (blocking): the pre-fix builder is not built explicitly and breaks once WP06 lands
- **Where:** `tests/_factories/coord_mission.py:512-549` (`make_prefix_coord_mission`), including its docstring at L525-531.
- **Problem:** the builder calls `create_mission_core` and then only asserts that the result is already pre-fix-shaped. It never rewrites anything.
- **What the WP requires:**
  - Objectives: "built explicitly, so it stays valid after WP06 changes create".
  - T009 step 2: "call `create_mission_core`, then rewrite the outcome into the pre-fix shape"; "reset it to the pre-create commit if create seeded it".
  - Review Guidance #3: "the pre-fix builder does not depend on create's current status-log placement".
  - Risks: "the pre-fix builder rewrites create's output into an explicit shape".
- **Impact:** WP06 makes create seed the coordination branch and stop writing the root log (scout §WP06: `status_dir` parameter, seed before `_commit_create_scaffold`). After that, `_assert_prefix_shape` raises on every call.
  - Every `make_fork_fixture` shape is built on this builder, so all four fork fixtures break too.
  - WP09 (prompt L142) relies on it explicitly: "Use WP02's make_prefix_coord_mission(worktree="absent") so the test stays meaningful after WP06 changes create".
  - WP06 needs it for the R6 legacy control. WP17, WP18 and WP21 consume it once WP06 has merged.
- **Required fix:** after create, transform the result into the pre-fix shape explicitly, whatever create produced:
  1. If the root checkout has no `status.events.jsonl` with `MissionCreated` and `SpecifyStarted`, write those rows there (carry them from the coordination copy, or emit them through the production emitter). Commit them on the target branch.
  2. If the coordination branch tree contains `kitty-specs/<dir>/`, tear down the coordination worktree, run `git worktree prune`, and reset the coordination branch to `creation_base_sha` (or the pre-create tip).
  3. Then apply the variants.
- **Proof required:** add a self-test that runs the rewrite step on a simulated post-fix create output (coordination branch seeded, root log absent). It must reach the documented shape, so the builder is proven independent of create's current placement.

### H2 (blocking): fork fixtures (a)/(b) have no per-stream variants (binding correction)
- **Where:** `coord_mission.py:605-637` and `make_fork_fixture` (L723-746).
- **Binding correction:** "Fork fixtures (a) and (b) must say which stream diverges; provide per-stream variants, because WP03's prefix rule runs per stream."
- **Problem:** only the `status.events.jsonl` stream diverges (DecisionPointOpened rows through `open_decision`). I checked this: no `decisions.events.jsonl` is written on either surface. The docstrings do not name the diverging stream.
- **Who needs it:**
  - WP03 (prompt L211, L317) classifies `status.events.jsonl` and `decisions.events.jsonl` per stream.
  - WP17 (L179-180) reports `forked` per stream.
- **Required fix:**
  - Add a stream selector to the (a)/(b) shapes (and to (c), which derives from (b)): status log, `decisions.events.jsonl`, or both. Name it in the docstring.
  - Add self-tests asserting that the selected stream is forked on both surfaces and that the other stream is absent or single-home.
  - Expose the selector through the `fork_fixture` indirect parametrization.

### H3 (high): the (a)/(b) builders depend on the decision write path under test
- **Where:** `coord_mission.py:580-591` and `:615-636`.
- **Problem:** decision events are produced by `open_decision`, so where they land is decided by the live surface resolver at write time: the first while UNMATERIALIZED, the second after a hand `mkdir` of the coordination Mission dir.
- **What the WP requires:** Risks says "the fork builders write events into an explicit dir through low-level append helpers, so they never depend on the routing under test". T010 step 2 gives the fallback (`append_event` / the decision event writer into a chosen dir).
- **Impact:** once WP03, WP04 and WP09 land (seed on write, fork refusal, `write_dir`), the second `open_decision` will seed or refuse instead of forking. The fixture would then silently change shape or raise.
- **Also:** the builder does not check its own fork shape. Only the self-tests check it, so a mis-built fixture is not caught at construction (compare the fail-loud rule T009 applies to the pre-fix builder).
- **Required fix:**
  - Write the DecisionPoint* rows (and the `decisions.events.jsonl` rows, see H2) with production-shaped events and production ULID minting, directly into explicitly chosen dirs: the root Mission dir and `coord_mission_dir`.
  - Inside the builder, assert that both sequences are non-empty and that neither is a prefix of the other.

### M1 (medium): WP06's "real default path" parametrization cannot be expressed
- **Where:** `coord_mission.py:307-322` (`_cli_create_args` always passes `--topology`) and `make_coord_mission(tmp_path, topology, ...)`, where `topology` is required.
- **What WP06 needs (prompt L159):** `via="cli_pr_bound", protected_primary=True`, with the topology **omitted** (no `--topology`), and then an assertion that `meta.json` `topology == "coord"`.
- **Required fix:** allow `topology=None` for `via="cli_pr_bound"`. Omit `--topology` in that case and return the topology read from `meta.json`, without the requested-topology check. Add a self-test for it.

### M2 (medium): `protected_primary` semantics are inconsistent, and the self-test is a text grep
- **Where:** `coord_mission.py:188-196`, the docstring at L410-412, and the test at `test_coord_mission_factory.py:92-97`.
- **Inconsistency:** I checked with the production `ProtectionPolicy.resolve(repo).is_protected(...)`:
  - for `via="core"` (and `cli_topology`) it protects `topic`, which is the target branch and not the primary branch (`main` is not protected);
  - for `via="cli_pr_bound"` it protects `main`, while the target branch is `topic`.
  - The parameter name says "primary", the docstring says "the created mission's target branch", and the behaviour differs per `via`.
- **Weak test:** it asserts only `"protection" in config_text and "main" in config_text`. That is a substring grep, not the production probe the WP requires.
- **Required fix:**
  - Pick one meaning. Protecting the Primary Branch (`main`) matches the name and WP06 US1.4. Apply it for every `via` and fix the docstring.
  - Assert with `ProtectionPolicy.resolve(coord.repo_root).is_protected("main")`, plus the negative for the unprotected default.

### L1 (low): the 2 `# type: ignore[arg-type]` do not meet the charter bar
- **Where:** `test_coord_mission_factory.py:104` and `:242`.
- **Problem:** mypy is right here, because the calls are deliberately ill-typed. The charter allows a suppression only "when the check is genuinely wrong about correct code". The branches they exercise are also marked `# pragma: no cover` in the source (L431, L746), which contradicts having tests for them.
- **Required fix:** pass the bad value through an `Any`-typed local (`bogus: Any = "bogus"`) and remove both pragmas, or delete the two tests.

### L2 (low): the pure probe tests never run in `make test-fast`
- **Where:** `test_coord_mission_factory.py:40`. The module-level `pytestmark = [integration, git_repo]` also tags the `fast`/`unit` probe tests (L263-304) as `integration`.
- **Problem:** `FAST_TIER_MARKERS` in the Makefile contains `not integration`, so those tests are excluded from the fast tier. T011 asked for `git_repo` on the git-heavy tests and `fast`/`unit` on the pure probes.
- **Required fix:** apply `integration`/`git_repo` per test (or split the module) so the pure probe tests stay in the fast tier.

### L3 (low): the pre-fix self-test is weaker than the documented shape
- **Where:** `test_coord_mission_factory.py:112-114`, which checks only that the event ids are non-empty.
- **Required fix:**
  - Assert that `event_type == "MissionCreated"` (T011: "the root log has `MissionCreated`").
  - Assert that the root log is **committed on the target branch**: `coord_tree_has(repo, target_branch, rel)`, as the docstring claims.
  - This matters more once H1 is fixed.

### L4 (low): the charter is provisioned but never committed
- **Where:** `_init_repo_with_target`.
- **Problem:** in every fixture repo `.kittify/` is untracked (`git status` shows `?? .kittify/`). T008 says "provision the charter (`provision_test_charter`), commit". With `protected_primary`, the protection config is also uncommitted.
- **Required fix:** commit it, or document why an uncommitted charter is intended.

### Nit
`"status.events.jsonl"` appears 3 times in `coord_mission.py` (L371, L372, L595). Hoist it to a constant (S1192).

## Notes for downstream (no action needed in WP02)
- Fork fixture (d) has no companion DecisionPointOpened row in the coordination status log, though a pre-fix `open_decision` would also have written one. WP17's union-orphan rule (an id absent from every stream on both surfaces) will classify that decision as orphaned. Decide whether (d) should also carry the row.
- `ForkFixture.repo_root` and `coord_worktree_path` point at the **base** repo for `fresh_clone`. Consumers must use `clone_root`.
- `_read_source` returns `""` both for a missing path and for a bad ref. A wrong ref therefore makes `index_entry_ids(...) == set()` pass without testing anything. The (d) self-test's target-branch negative (L234-235) should first assert that the ref resolves.

## Anti-pattern checklist
1. Dead code: N/A (test harness; there are no production callers by design).
2. Synthetic fixture: FAIL (M2). The `protected_primary` assertion is a text grep; the other shapes are checked with `probe_coord_state` or git plumbing.
3. Silent empty return: PASS with a note. `_read_source` returning `""` is documented, but see the downstream note on bad refs.
4. FR coverage: FAIL. The NFR-002 per-stream fork variants are missing (H2).
5. Frozen surface: PASS (no `src/` changes).
6. Locked decision: PASS.
7. Shared-file ownership: PASS (only new files owned by WP02).
8. Production fragility: N/A.
