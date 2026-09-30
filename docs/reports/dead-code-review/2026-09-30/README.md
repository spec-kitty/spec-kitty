---
doc_status: active
updated: '2026-09-30'
---

# Dead-code review (2026-09-30)

A read-only research pass over `src/` of the core CLI. It looked for dead code, then took a second, deeper look at every symbol that only tests still reach. No code was changed. What to clean up, and in which order, is an owner decision; this report is the input for it.

| | |
|---|---|
| Analysed at | `origin/main` `bd1577a3` (4.0.0rc5). The two scripted headline checks were re-run on `ed74cd671` with the same result |
| Scope | `src/`: 1,344 modules, ~443k lines (`charter`, `glossary`, `kernel`, `mission_runtime`, `runtime`, `specify_cli`, `doctrine.py`) |
| Pass 1: dead-code sweep | ~2,000 candidates: 798 vulture hits, ~530 dead-symbol gate allowlist entries, 169 ruff hits, 42 mypy-unreachable, 22 unreachable modules. Four domain reviewers checked each one with grep/AST evidence |
| Pass 1 result | ~180 DEAD symbols (~157 High confidence, ~2,800 removable lines), ~220 TEST-ONLY, ~110 API/dynamic (keep), ~340 tool false positives |
| Pass 2: test-only deep dive | The TEST-ONLY set grouped into **59 slices**. Each slice traced for history, replacement, keeping tests, open intent and deletion risk |
| Pass 2 result | ~10,200 lines of `src/` and ~15k lines of tests are involved. **25 slices** are a straight delete, or a delete once tests move to the live path. **15** need per-symbol handling. **13** are owner decisions. **2** should be wired. **2** are live CI gates that belong in `tests/`. **2** stay |
| Bug candidates found | **16** places where the dead copy does something the live path does not, or where the dead code hides a live defect (§1) |

## Contents

- [§1 Bug candidates](#1-bug-candidates-read-these-first): read these first.
- [§2 What is dead, by kind](#2-what-is-dead-by-kind)
- [§3 Blind spots in the repo's own dead-code gates](#3-blind-spots-in-the-repos-own-dead-code-gates)
- [§4 Recommended cleanup order](#4-recommended-cleanup-order)
- [§5 Owner decisions](#5-owner-decisions)
- [§6 Method and reproduction](#6-method-and-reproduction)

Per-domain detail lives beside this file. Every row in those files carries the evidence behind it:

| Domain | Pass 1 (all dead-code findings) | Pass 2 (test-only deep dive) |
|---|---|---|
| A. charter, glossary, kernel, mission_runtime, runtime, `doctrine.py` | [first-pass/domain-a-charter-runtime.md](first-pass/domain-a-charter-runtime.md) | [test-only-deep-dive/domain-a-charter-runtime.md](test-only-deep-dive/domain-a-charter-runtime.md) |
| B. CLI surface (`cli`, `orchestrator_api`, `dashboard`, `shims`) | [first-pass/domain-b-cli-surface.md](first-pass/domain-b-cli-surface.md) | [test-only-deep-dive/domain-b-cli-surface.md](test-only-deep-dive/domain-b-cli-surface.md) |
| C. Workflow core (status, consolidation, coordination, lanes, core, upgrade, …) | [first-pass/domain-c-workflow-core.md](first-pass/domain-c-workflow-core.md) | [test-only-deep-dive/domain-c-workflow-core.md](test-only-deep-dive/domain-c-workflow-core.md) |
| D. Integrations and the rest (auth, tracker, zeitgeist, retrospective, skills, doc_analysis, …) | [first-pass/domain-d-integrations-rest.md](first-pass/domain-d-integrations-rest.md) | [test-only-deep-dive/domain-d-integrations-rest.md](test-only-deep-dive/domain-d-integrations-rest.md) |

## 1. Bug candidates (read these first)

Dead code is usually harmless. These are the exceptions: a dead copy does something the live path never does, or a dead branch hides a live defect.
- **Status column:**
  - "Reproduced" means we ran it.
  - "Confirmed in code" means we read both paths.
  - "Reported" means one reviewer read the code and nobody reproduced it.
- **Severity** is the reviewer's estimate.
- **Next step:** each item needs its own ticket and a red-first fix; none is a cleanup item.

| # | Where | What goes wrong | Status | Severity |
|---|---|---|---|---|
| 1 | `lanes/worktree_allocator.py` (all three routes) vs dead `core/worktree.py::_ensure_spec_kitty_exclude` | **FR-016's `.spec-kitty/` exclude has never reached a live lane worktree.** The writer was added (976d7169d, #625) to two functions that were already dead. The allocator predates it (#377). The dead writer targets `.git/worktrees/<name>/info/exclude`, **which git does not read**, so wiring it as-is would not help either. `.spec-kitty/review-lock.json` (written at `workflow.py:~1853`) then shows up untracked. A leftover lock makes the allocator's REUSE and CRASH-RECOVERY paths raise `DirtyWorktreeError`, and `git add -A` would commit it. The fix already exists: `core.git_ops.exclude_from_git_index(repo_root, [".spec-kitty/"])` writes the shared `info/exclude`, plus an upgrade migration for existing checkouts | Reproduced (git 2.43): a per-worktree `info/exclude` leaves `?? .spec-kitty/`; the common-dir exclude silences it | High |
| 2 | `cli/commands/agent/tasks_status_cmd.py:386-392` | `extract_scalar()` returns `str \| None`, so the `isinstance(deps_raw, list)` branch is unreachable. `dependencies: []` (1,210 WP files in `kitty-specs/`) becomes a dependency literally named `"[]"`. `[WP01]` becomes `"[WP01]"`, and block lists become none. `tasks status` pre-flight readiness is therefore wrong for every WP. This is advisory display only; the authoritative gate is in-lock | Reproduced: `dependency_readiness_for_wp('WP02', ['[]'], …)` returns `unsatisfied=('[]',)` | Medium |
| 3 | `charter/offering/base.py:411` `_merge` (used by `MissionStepContractRepository`) vs test-only `org_pack_loader.merge_topology_artifact` | The documented rule "an `enhances` overlay may not silently drop steps or strip step I/O" is enforced only in the test-only merger. The live repository merges shallowly with `{**built_in, **overlay}`, so a partial `steps:` overlay replaces the whole list | Confirmed in code | High |
| 4 | `retrospective/generator.py:1191-1365` | `generate_proposals=True` (the policy default) produces zero proposals: the list is sorted but never appended to. The proposal policy is a no-op | Confirmed in code | Medium |
| 5 | `doc_analysis/doc_state.py` setters vs `mission_setup_plan.py:870` | Documentation missions: nothing ever sets `iteration_mode` beyond the create-time `"initial"`, so the setup-plan gap-analysis branch (`gap_filling` / `mission_specific`) cannot run | Confirmed in code | Medium |
| 6 | Research citation validators (`validate_citations`, `validate_source_register`, …) | Research review used to block on citation errors. That gate was dropped on 2026-04-04 (`37484eeb8`/`4eee6aeee`). The validators' status vocabulary has also drifted from the prompt's, so re-wiring as-is would reject compliant rows | Reported | Medium |
| 7 | Glossary DRG layer (`build_glossary_drg_layer`, `GlossaryEntityPageRenderer.generate_all`) | Nothing creates glossary DRG nodes or `vocabulary` edges, and nothing calls `generate_all`. The dashboard's `entity_pages_generated` stays false, and `drg/query.py:232` walks edges that never exist | Reported | Medium |
| 8 | `charter pack apply` (`pack.py:306-323`) | On a migrated project it writes activation keys to `config.yaml`. `pack_context` then reads only `charter.yaml` (via the `charter:` pointer), so the keys are ignored | Reported | Medium |
| 9 | `glossary` `activate_scope` | `GlossaryScopeActivated` is specified but never emitted in production | Reported | Low |
| 10 | Per-kind JSON-schema validators (`validate_directive`, `_paradigm`, `_styleguide`, `_tactic`, `_toolguide`) | Five shipped schemas are never enforced when artifacts load | Reported (maybe intended) | Low |
| 11 | `audit` repo-level findings | The live engine builds repo-level findings inline and has **no tests**. Only its dead twin (the `*_groups_to_findings` adapters) is tested | Reported | Low |
| 12 | `missions` `validate_deliverables_path` | The research deliverables path is never validated before use. This is a security-flavoured owner call | Reported | Medium |
| 13 | `acceptance/post_consolidation.py` and `policy/audit.py` | Docs and contracts promise enforcement that never runs. The CI enforcer `scripts/ci/check_dangling_deferrals.py` is wired into no workflow, and nothing writes `policy-audit.jsonl` | Confirmed in code | Low |
| 14 | `cli/commands/review/_diagnostics.py:29-30` | `MISSION_REVIEW_GATE_RECORD_MISSING` and `MISSION_REVIEW_MISSION_EXCEPTION_INVALID` are documented as operator codes with remediation (`review/ERROR_CODES.md:180-217`) but no code path emits them | Confirmed in code | Low |
| 15 | Zeitgeist `focus_end` | Focus is never ended, so it lingers until the relay TTL | Reported (UX) | Low |
| 16 | `SPEC_KITTY_SUPPRESS_FEATURE_DEPRECATION` | Documented in the user reference `docs/api/environment-variables.md`, but no `src/` code reads it | Confirmed in code | Low |

## 2. What is dead, by kind

### 2.1 Whole packages and modules

| Package / module | Lines | State | Verdict |
|---|---|---|---|
| `specify_cli.proof` | 424 | Imported only by its `__init__` and tests. The docstring calls it "CLI proof/evidence **sync** events"; nothing emits them | DELETE |
| `specify_cli.auth.websocket` | 212 | Its only consumer, `sync/client.py`, was deleted with the sync transport | DELETE |
| `specify_cli.charter_runtime.facade` | 10 | Empty placeholder (`__all__ = []`) | DELETE unless the umbrella shape is still wanted |
| `specify_cli.calibration` | 637 | Never imported at runtime. **But** its 33 tests enforce FR-032 against the real DRG, so it works as a CI gate | MOVE into `tests/` (keep the gate) |
| `src/doctrine.py` shim | 115 | `__removal_release__ = "3.3.0"`; the version is now 4.0.0rc5. No importers | DELETE |
| `runtime.next._internal_runtime.{emitter,lifecycle,models}` | 80 | Called "frozen contract" re-exports, but the contract never names them | DELETE |
| `charter.parser`, `charter.activation.template_resolver` | ~450 | Grandfathered orphans past their own "0 by 4.0" target. `charter/__init__` still lazily exports both | DELETE (Medium) |
| `specify_cli.policy.audit` | 89 | Orphan, and nothing writes its log | DELETE (owner) |
| `specify_cli.auth.transport` | 525 | ADR `2026-05-18-2` says DELETE; blocked only on the owner (Robert) | DELETE (owner-gated) |
| `specify_cli.doctrine.pack_lineage` / `pack_descriptor` | 353 | "WP in flight", but #3511 is blocked and #3518 is open | Timebox (owner) |
| `core/vcs` `GitVCS` / `VCSProtocol` | ~1,360 | Reachable only through the dead `core/worktree.py` cluster | DELETE after bug 1 is fixed |
| `core/worktree.py` legacy workspace creation | ~600 | Replaced by the lane allocator (#377); kept alive by ~1,570 lines of tests | Fix bug 1, then DELETE |

### 2.2 Sync-transport residue (the August 2026 deletion left these behind)

- `sync_dossier` parameter at `status/emit.py:847, 1102`: no `src/` caller passes it; 3 test sites do.
- The `ensure_sync_daemon` → `fire_saas_fanout(ensure_daemon=…)` thread, through `emit.py`, `coordination/outbound.py:119`, `work_package_lifecycle.py` and `orchestrator_api`. No handler reads it.
- `sync_active()` in `core/saas_sync_config.py`: no caller since #3980. It is contract-pinned, so retire it with the next contract version.
- `Event` / `LamportClock` in `events/adapter.py` (~95 lines), `RuntimeRoot.sync_dir` / `daemon_dir`, `generate_build_id`, and the `proof` and `auth.websocket` packages above.
- Stale prose: the "sync, websocket" migration note in `tracker/saas_client.py`, and `docs/operations/sync-drain.md`, which was "scheduled for deletion in 3.2.7".

**These are not dead, only misnamed:** `SPEC_KITTY_ENABLE_SAAS_SYNC` / `is_saas_sync_enabled()` still gate tracker and mission-type behaviour, and `SPEC_KITTY_SYNC_DISABLE` is a live member of the moment-handler gate. Rename them with a contract bump, not in a cleanup.

### 2.3 Re-export tails from god-module splits

`cli/commands/agent/workflow.py` re-exports 40 names "for existing imports and monkeypatches". Five are live: `workflow_executor.py` reads them late through `_wf()`. **The other 35 are dead**, and tests still import 8 of those. The file-wide `F401` ignore in `ruff.toml` hides them all. `agent_retrospect.py` (9 dead imports), `agent/mission.py` (#2056) and `consolidate` (#2057) show the same pattern.

### 2.4 Dead twins kept alive by their tests

In these cases the test pins a copy that production no longer calls, and the live path goes untested:

| Dead twin | Live path |
|---|---|
| `_render_charter_context` | `render_charter_context_text` |
| `_validate_base_ref` | `_resolve_base_ref` (#1917; the #4969 origin preference is untested) |
| `_spec_artifact_dirty_paths` | inlined in `accept.py` |
| `_resolve_claim_commit_target` | Not a replacement. Its fail-close is claimed in 5 comments but no longer exists, and re-wiring it would bring back #610 |
| `_durable_done_wps_on_coordination_ref` | `_durable_coordination_lanes` (#5046) |
| `evaluate_guards` | `evaluate_guards_strict` (#3386) |
| `count_wp_section_subtask_rows` | `iter_wp_section_subtask_rows` |
| The audit adapters | See bug 11 |

This is the source-side mirror of the 2026-09-29 dev-assist test audit. The two cleanups should be paired: **move the test onto the live path, then delete the twin**.

### 2.5 Forward APIs that never got a consumer

Mission-exported "public surfaces" whose consumer never landed:
- delivery-rail measurement helpers (#3063)
- the `ResolvedMissionType` lazy slots
- the workflow-sequence next-action resolver
- `surface_authority` exit mapping (#2160)
- tracker ticket-first origin and the gateway authority report
- Zeitgeist focus verbs
- over-internalised upstream runtime pieces: `TransitionGate`, `JsonlEventLog`, `notify_decision_timeout`, and others (~436 lines)

Almost none of these **ever** had a runtime caller.

### 2.6 Tests that cannot fail

Most of these guard dead code:
- `test_mission_create_phases.py:152` patches the uncalled `_persist_pr_bound_phase`.
- `test_charter_resynthesize.py:182` patches a renderer the function never imports.
- `test_wp_state.py:323` compares two wrappers of the same `guard_for`.
- `test_status_json_safe.py:249` and `test_status_no_op.py:223-239` assert that an uncalled `generate_all` is not called.
- `test_bridge_io.py:143` pins an unused constant.
- `test_coordination_remedy_5113.py` claims to exercise production `implement()`, but `implement()` never calls the helper it drives.

## 3. Blind spots in the repo's own dead-code gates

The repo already gates dead code (`tests/architectural/test_no_dead_symbols.py`, `test_no_dead_modules.py`; both green at the analysed commit). Most of the residue above is what those gates tolerate by design or cannot see:

1. **Package self-re-export.** `test_no_dead_modules` skips `__init__.py` and counts any other `src/` importer as a caller. A package whose `__init__` re-exports its own submodules therefore always looks alive. That is how `calibration`, `proof` and `auth.websocket` survive. Fix: treat a package as dead when every importer of its submodules lives inside it. [`tooling/entrypoint_reachability.py`](tooling/entrypoint_reachability.py) computes this.
2. **No stale ratchet on the widened set.** `_WIDENED_SCOPE_GRANDFATHERED_470` (215 entries) is checked only by `assert any(...)`. Replaying the gate's own widened pass ([`tooling/widened_stale.py`](tooling/widened_stale.py), output in [`raw/widened-stale.txt`](raw/widened-stale.txt)) shows **52 stale entries**:
   - 45 now have a caller, including all 36 `zeitgeist_client.*` entries, `audit_invocation_disagreement` (the gate's own docstring example of a dead symbol) and `mission_terminal_verdict`;
   - 4 are used in their own module;
   - 2 moved into `__all__`;
   - 1 (`charter.offering.hatch_build::DoctrinePacksSiblingBuildHook`) names a module that no longer exists.
3. **Expired rationales.** `_CATEGORY_*` entries have a ratchet for "gained a caller", but nothing notices when the reason itself expires:
   - "WP in flight" for missions that have finished (01KSYE4V, 01KSWJVX, 01KZPDSR, charter_activate wiring, `migrate_lifecycle_envelope`);
   - "0 by 4.0" deadlines that have passed;
   - a shim past its removal release;
   - tickets from before the repository move (#1355/#1356);
   - a superseded lane (#2761).

   Suggested fix: every category carries an `expires:` release or a tracking issue, and a check reds when either lapses.
4. **Over-broad `__all__`.** About 100 allowlist rows cover symbols used only inside their own module but exported to no one. Trimming `__all__` clears them honestly, with no code change.
5. **Tests count as zero callers but keep the symbol alive.** This is by design, but it means a replaced implementation survives as long as its unit tests do. §2.4 and the deep-dive files list every case.
6. **`ruff.toml` per-file `F401` ignores.** The 2026-05-01 legacy baseline hides 74 unused imports. Burn it down per file, the same way the format-exclude ratchet works.

## 4. Recommended cleanup order

1. **Tickets for the bug candidates (§1).** Fix #1 before deleting the `core/worktree.py` cluster: it is the only place the intended behaviour is written down.
2. **Gate hardening** (small, high leverage): §3 items 1, 2 and 6, plus pruning the 52 stale widened entries.
3. **Straight deletions**, no behaviour change, High confidence:
   - the §2.1 packages marked DELETE;
   - the sync residue in §2.2;
   - the 35 dead `workflow.py` re-exports (switch to per-line `noqa` on the 5 live ones);
   - the delete-verdict slices in the deep-dive files.

   Pass 1 put the High-confidence set at about 2,800 lines.
4. **Move-then-delete**: repoint the tests in §2.4 at the live path, then delete the twins. The deep-dive files name each test file and whether it is MOVE, DELETE or SPLIT.
5. **Owner decisions** (§5), then the per-symbol "mixed" slices.

Each step should run the dead-symbol and dead-module gates, because deleting an allowlisted symbol also needs its allowlist row removed. Whole-file deletions also need their `pyproject.toml` format-exclude entries and the `test_egress_consent_boundary.py` allowance rows removed.

## 5. Owner decisions

| Question | Recommendation |
|---|---|
| Delete `auth.transport` per ADR `2026-05-18-2`? (Robert) | Yes. The sync alternatives it cited are gone |
| Wire `set_iteration_mode` so documentation gap analysis can run, or drop the gap-analysis branch? | Wire it (bug 5) |
| Re-wire the research citation gate, or delete the validators? | Re-wire, after reconciling the status vocabulary with the prompt (bug 6) |
| `enhances` step-drop rule: enforce in the live repository, or retract the documented rule? | Enforce it (bug 3) |
| Glossary DRG layer and entity pages: wire or retire the surface? | Decide once. Today the dashboard and query code assume it exists (bug 7) |
| `calibration`: keep as a test-side gate or delete? | Move into `tests/` |
| `GitVCS` / `VCSProtocol` abstraction: keep for a future non-git backend? | Delete after bug 1 is fixed |
| `pack_lineage` / `pack_descriptor` (#3511 blocked) | Timebox it; delete if it has not moved by 4.0 GA |
| `sync_active()` | Retire it with saas_rollout contract v4 |
| `validate_deliverables_path` | Wire it (security) |
| Retrospective proposal pair (`_classify_risk`, `ProposalGeneratedPayload`) | Tie to bug 4: either produce proposals or remove the policy switch |

## 6. Method and reproduction

- **Pass 1: sweep.**
  - Tools:
    - the repo's two dead-code gates (green, 35 tests);
    - `vulture 2.16 --min-confidence 60` over `src/` and over `src/`+`tests/`;
    - `ruff --isolated --select ERA001,F401,F841`, which bypasses the per-file baseline;
    - `mypy --strict --warn-unreachable` ([`raw/mypy-unreachable.txt`](raw/mypy-unreachable.txt));
    - an import-reachability walk from the `spec-kitty = specify_cli:main` entry point ([`raw/unreachable-modules.txt`](raw/unreachable-modules.txt));
    - a `SPEC_KITTY_*` env-var inventory, source against docs;
    - a dependency-use check. Every dependency in `pyproject.toml` is imported somewhere, and no dead `if False:` / constant-flag guards exist.
  - Filtering: 342 framework-registered vulture hits (Typer commands, pydantic validators, `MigrationRegistry` classes, dunder and stdlib hooks) were dropped by [`tooling/candidate_tiers.py`](tooling/candidate_tiers.py) before review.
  - Review: four reviewers, one per domain, verified every remaining candidate with `grep` over `src/ tests/ packs/ scripts/ .github/ pyproject.toml .kittify/`. They included string references (`importlib`, `patch("…")`, `monkeypatch.setattr`), late-bound `_wf()` lookups, Protocol conformance and framework hooks.
  - Verdicts: DEAD, TEST-ONLY, API/DYNAMIC or FALSE-POSITIVE, each with a confidence.
- **Pass 2: test-only deep dive.**
  - Grouping: every TEST-ONLY row was grouped into slices, 59 in all.
  - What each slice records:
    - what it was for;
    - `git log -S` history, meaning who introduced it and which commit removed its last runtime caller (on an unshallowed clone);
    - what replaced it;
    - every keeping test, classified MOVE / DELETE / SPLIT, with the live path's own coverage named;
    - open intent from docstrings, specs and commit messages;
    - deletion risk;
    - a verdict.
  - Test runs: reviewers ran only individual test files. For example, domain B's 14 keeping files ran at 337 passed, 1 skipped, and calibration's two files at 33 passed.
- **Spot checks.** I re-ran the headline claims:
  - bug 1 in a scratch git repo;
  - bug 2 against `dependency_readiness_for_wp`;
  - bugs 3 and 4 by reading both code paths;
  - the widened-set and reachability scripts on current `main`.
- **Counts.** Counts are reviewer tallies over grouped rows. Treat them as ±10%.
- **Reproduction.** Run the scripts in [`tooling/`](tooling/) from the repository root. [`raw/workflow-reexport-scan.txt`](raw/workflow-reexport-scan.txt) holds the per-name evidence for the `workflow.py` re-export analysis.
