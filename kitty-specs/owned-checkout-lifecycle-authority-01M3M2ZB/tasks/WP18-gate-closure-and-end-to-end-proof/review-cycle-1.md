---
affected_files: []
cycle_number: 1
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-30T00:35:18Z'
reviewer_agent: claude
wp_id: WP18
---

# WP18 review, cycle 1: changes requested

Reviewer: reviewer-renata (claude). Lane-q tip 3e2862b5c. Gate closure (T095 to T097), marker retirement, the ratchet, dead symbols, mypy and ruff all pass (evidence is at the end). Two defects remain, both in the SC-001 / NFR-001 end-to-end proof (T098). T098 is the mission's end-state oracle, so both must be fixed.

## Issue 1 [MEDIUM]: the stale-copy path exemption matches by value anywhere in the payload, which hides the O4 regression in every stale cell

`tests/integration/test_owned_lifecycle_acceptance_e2e.py:206-220` (`_assert_paths_under_p`), at line 217:

```python
if stale_path is not None and Path(candidate).resolve() == Path(stale_path).resolve():
    continue
```

The check skips any candidate path, under any key, that equals `stale_repository_root_copy.path`. That path is `R/kitty-specs/<slug>` (`_owned_checkout.py:316`). This is also exactly the value a stale-copy-wins regression (O4) would put in `feature_dir`, `mission_dir` or a similar key.

Mutation proof: I called `_assert_paths_under_p` with `{"feature_dir": "<R>/kitty-specs/demo-01ABCDEF", "stale_repository_root_copy": {"path": "<R>/kitty-specs/demo-01ABCDEF", ...}}` and the call passed. The same payload with `stale_repository_root_copy: None` was caught. So the per-PR cell (`P-stale-copy`), and every stale cell, cannot detect the defect it exists to catch.

data-model.md:79 sanctions the stale path in `stale_repository_root_copy.path` and in the human text in `warnings[]`. It sanctions nothing else.

**Required fix:**
- Scope the exemption by key, not by value:
  - `stale_repository_root_copy` is already stripped;
  - additionally skip only strings inside the top-level `warnings` list, and ideally only when the string is the rendered `STALE_COPY_WARNING`.
- Every other key must be under P.
- Add a committed non-vacuity unit test: a payload whose `feature_dir` (or any other non-`warnings` key) equals the stale path must raise `AssertionError`.

## Issue 2 [MEDIUM]: the R snapshot leaves out `SPEC_KITTY_HOME`, against NFR-001, and the module docstring says it is covered

`tests/integration/test_owned_lifecycle_acceptance_e2e.py:405` and `:497` build `RSnapshotter(site.r, site.p, None)`, so `home_files` is always empty.

The spec binds the snapshot to include "an isolated `SPEC_KITTY_HOME`" with exactly one named tolerance, the per-mission status mutex:
- spec.md:53 ("NFR-001 … is the single authority for what the R snapshot covers");
- NFR-001, spec.md:232;
- research.md:153.

The module docstring (lines 21-24) states that "R is unchanged (… the shared lock root and SPEC_KITTY_HOME …)". The code does not do that.

In the same way, `allowed_roots.append(site.home)` (line 212) widens the rule that every payload path is under P.

The cause is real: `next` writes the prompt file under `SPEC_KITTY_HOME/spec-kitty-prompts/<sha256(P)[:16]>` (`runtime/next/_tmp_namespace.py`). A blanket exclusion of the whole home, however, also hides any other home write, for example a prompt directory keyed on R or runtime state.

**Required fix (either option is acceptable):**
- (a) Snapshot the home again: pass `_home_for_snapshot()` or `site.home`. Tolerate only the P-keyed prompt subtree `spec-kitty-prompts/<identity(P)>/`, as a second named tolerance defined once in `tests/_owned_fixtures.py`. Because NFR-001 says "exactly one named tolerance", record this with the orchestrator as a spec/NFR-001 amendment in the Activity Log.
- (b) Escalate to the orchestrator for a ruling before merging.

In both cases:
- correct the docstring;
- restrict the payload-path allowance for `site.home` to that same P-keyed prompt subtree (the `prompt_file` key).

## LOW (fix now if convenient; not blocking alone)

- `tests/migration/test_birth_cutover.py:675`, `tests/integration/test_migration_backfill.py:78` and `tests/upgrade/test_placement_abort_report.py:48` carry `# noqa: ARG005` with no inline rationale, which CLAUDE.md requires. Either rename the parameter to `_owned` (then no noqa is needed) or add a one-line reason.
- `tests/specify_cli/cli/commands/agent/test_tasks_ports.py:471`: the comment still names the retired `effective_root_kwargs`.
- The cb51696b8 body and `_SLOW` (e2e:450) say that only the P/stale cell runs per PR. In fact `module-tests.yml:210` selects `-m "not performance and not stress"`, so the five `slow` cells also run per PR in CI. This gives more coverage, not less, but correct the claim.
- a796c4eb4 renamed `_resolve_setup_plan_scope(owned_checkout=)` to `owned_claim=` and left `test_mission_setup_plan_phases.py` red until 8addab0af. For the record only; the tip is green.

## Verified (no action)

- **T095 red-first.** Checked in a scratch detached worktree at 9dbc03f5c (parent bda36867d): 4 failed, 4 passed (G2=2, G4=205, G5=55, TRANSITIONAL markers). The commit contains the gate file only.
- **Planning-base non-vacuity.** Checked at 5e6820d19 with the gate, scanner and `_ast_scan` copied in: 5 failed, 3 passed. Counts: G1=4 (next_cmd:167,170; mission_creation:33,848), G2=8 (incl. status_transition:917), G4=431, G5=109, G6=9/9 missing. The prompt's extra G2 "floor" sites (models:902, bootstrap:183, backfill:1441, resolution:1514) are comments on the planning base, so the gate is right not to count them.
- **Mission-tip greps.** `# bridging:` returns 0 and `TRANSITIONAL(WP18)` returns 0 (only stale `.pyc` hits). `OwnedMission`, `effective_root_kwargs` and `checkout_root_agrees_with_effective_root` are gone from src.
- **Allowlist and ratchet.** `_OWNED_ROOT_BARE_PATH_ALLOWLIST` is empty and the `_baselines.yaml` leaf is 0. The ratchet row was added and the floor goes from 14 to 15.
- **Dead symbols.** The `test_no_dead_symbols` change is a hash re-pin of the existing `append_lifecycle_event` entry only.
- **(a) The scanner's `_mint` exemption is legitimate.** It is FQN-scoped to `OwnedCheckout._mint` in the carrier module, and G3 governs who may call it. Mutation check on the real carrier: an added `helper(owned_root: Path)` and a `_mint` on another class are both flagged. The self-test cases are negative/leak pairs and landed with the rule, which is acceptable for an exemption.
- **(b) Removing `checkout_root_agrees_with_effective_root` is safe.** The only second root it compared (`effective_root`) no longer exists. `_identity_for_request` takes `mission_dir`/`owned_root` from the fact and keeps the slug check. No path pairs a fact with a divergent bare checkout root.
- **(c) Fail-closed on EMPTY coordination is consistent.** An EMPTY coordination worktree fails closed with OWNED_COORDINATION_WORKSPACE_UNAVAILABLE. `tolerate_unmaterialized_coord` tolerates only UNMATERIALIZED (resolution.py:1448). `test_owned_lifecycle_acceptance_next.py` (FR-022 twin) is green.
- **(e) The pyproject format-exclude shrink is clean.** All 24 removed entries are already formatted on bda36867d, and `test_ruff_format_exclude_ratchet` is green.
- **(f) SC-005.** WP18's two removed assert lines are one re-point (`.directory` to `.mission_dir`) and one deletion together with its retired subject (`_transitional_owned_from_legacy`).
- **(g) The `test_implement_preflight` flake is pre-existing.** Its root cause is the process-global ambient-warning dedupe (`charter_runtime/preflight/ambient_warning.py:80-85`, #3971), which `test_implement_preflight.py` never resets. It reproduces on origin/main 5b3bd9cf7 with one poison test run first (1 failed). The mission did not cause it; the mission's `next`-invoking tests are simply more poisoners.
