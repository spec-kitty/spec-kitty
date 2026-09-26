# Tasks: Terminus Integrity Follow-ups

**Mission**: `terminus-integrity-followups-01M393QR` | **Branch**: `fix/terminus-integrity-followups`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md) · **Design**: [data-model.md](./data-model.md), [contracts/invariants.md](./contracts/invariants.md)

6 work packages. Conflict-safe: `executor.py` is single-owned (WP05); every other production file is single-owned by exactly one WP. `tests/terminus/` is owned by WP01 (red-first harness); the existing repros' `xfail(strict)` markers are removed at **integration** (orchestrator, during consolidation) with captured before/after per repro — reviewed by the mandatory pre-merge squad. Each fix WP (WP02–WP05) carries its OWN red-first unit tests in its OWN owned test files, so every fix shows red→green independently (post-plan renata).

Post-plan adversarial squad findings (F1–F14, decomposition A–D) are folded into the subtask guidance and each WP's Definition of Done. See [contracts/adversarial-evidence.md](./contracts/adversarial-evidence.md).

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----|
| T001 | conftest: `blob_present_at` helper + `plant_canceled_commit` returns planted path | WP01 | |
| T002 | default-squash variant of #4977 (blob-presence + pin FAIL cause) | WP01 | [P] |
| T003 | default-squash variants of #4945 + #4981 (blob-presence + pin FAIL cause) | WP01 | [P] |
| T004 | clean-squash positive param (no-false-fail), hard-coupled | WP01 | |
| T005 | verify all target repros present as xfail(strict)-RED at HEAD; record baseline | WP01 | |
| T006 | committed-content probe (placement-authority path / ls-tree; path-drift≠absent) | WP02 | |
| T007 | refuse predicate in `assert_coord_write_materialized` (3-part) | WP02 | |
| T008 | reroute `do_issue_verdict` through `resolve_for_write` | WP02 | |
| T009 | WS3 unit tests (stale-head REFUSE, first-write success, path-drift/unreadable REFUSE, flat/no-coord no-false-refuse) | WP02 | |
| T010 | F11 blast-radius run + record; choose file-existence vs row-level | WP02 | |
| T011 | git_probes: `blob_id_at`, `changed_paths_in_range(--no-renames)`, `first_parent_commits_in_range` propagate error | WP03 | |
| T012 | reconciliation: `authored_blobs` = FINAL blob per (lane,path) | WP03 | |
| T013 | reconciliation: `_unattributable_content_squash` (diff --name-status A/M, REFUSE on ""); reorder None-base/empty-authored REFUSE above squash early-return | WP03 | |
| T014 | test_reconciliation unit: FINAL-blob/second-parent exclusion, unattributable FAIL names path, empty-authored REFUSE, clean pass | WP03 | |
| T015 | test_git_probes_seam unit: deleted vs error, --no-renames, error-propagate | WP03 | |
| T016 | state.py: additive fields + lane-tip CAS helper (object-compare, ancestor-OK, branch-may-be-gone) + absent-base guard | WP04 | |
| T017 | cli/merge.py: resume strategy precedence + H1 flip-REFUSE | WP04 | |
| T018 | test_merge_state unit: precedence table, H1, CAS H3 (ancestor/descendant OK, divergence REFUSE), absent-base H4 | WP04 | |
| T019 | executor: honest squash pass-message (MUST NOT strip enforce_closed_world) | WP05 | |
| T020 | executor: strategy reseed persist (attempt-1's executed value) + resume read wiring | WP05 | |
| T021 | executor: `_resolve_pre_mutation_coord_sha` read-persisted-first + persist lane tips at first capture (F3/F9) | WP05 | |
| T022 | executor: anchor claim coord_base to persisted at consumption site; call WP04 lane-tip CAS on resume | WP05 | |
| T023 | test_executor_terminus_integrity unit: strategy persist+read, coord-base no-re-poison on resume-of-resume, message honesty | WP05 | |
| T024 | CHANGELOG entry (Before/After house style) | WP06 | |
| T025 | doc note: default squash now enforces content axis | WP06 | [P] |

## Work Packages

### WP01 — Red-first terminus harness  *(P1 · debugger-debbie · no deps)*
- **Goal**: extend `tests/terminus/` so every target invariant has a mock-free, red-first repro with a squash-sound observable, before any fix lands.
- **Independent test**: at HEAD, all target repros are `xfail(strict)`; the new default-squash variants FAIL (RED) on the current vacuous squash path via blob-presence, not patch-id.
- **Subtasks**: T001–T005. Prompt: [tasks/WP01-red-first-terminus-harness.md](./tasks/WP01-red-first-terminus-harness.md)
- **Risk**: a variant that passes for the wrong reason (renata/F4) — mitigated by asserting the FAIL cause + hard-coupling the clean-squash positive.

### WP02 — WS3 surface-write self-materialization hardening  *(P3 · python-pedro · no deps · closes #4970)*
- **Goal**: refuse a stale-local-head self-materialization that carries committed matrix content; route `issue-verdict` through the fail-closed write resolver.
- **Independent test**: seed committed matrix on a local-head coord branch, remove the worktree, second verdict → committed rows survive.
- **Subtasks**: T006–T010. Prompt: [tasks/WP02-ws3-surface-write-hardening.md](./tasks/WP02-ws3-surface-write-hardening.md)
- **Risk**: path-drift fail-open (F2); empty-scaffold false-refusal (F11) — both explicitly tested/recorded.

### WP03 — WS1 squash-sound content axis  *(P1 · python-pedro · no deps · unblocks #4945/#4977/#4981 default flow)*
- **Goal**: blob-attribution content axis + git blob probes so the DEFAULT squash merge fails-closed on unattributable content.
- **Independent test**: `_unattributable_content_squash` FAILs on a planted canceled blob, PASSes a clean squash, REFUSEs on probe error / empty authored set.
- **Subtasks**: T011–T015. Prompt: [tasks/WP03-ws1-squash-content-axis.md](./tasks/WP03-ws1-squash-content-axis.md)
- **Risk**: FINAL-blob attribution (F5), fail-open on "" (F1), rename asymmetry (F6) — all tested.

### WP04 — WS2 resume state + CLI strategy authority  *(P2 · python-pedro · no deps)*
- **Goal**: additive `MergeState` fields + lane-tip CAS helper + resume strategy precedence with H1 flip-REFUSE.
- **Independent test**: precedence table + H1 REFUSE + CAS accepts behind-HEAD/descendant, REFUSEs true divergence + absent-base REFUSE — all unit-proven.
- **Subtasks**: T016–T018. Prompt: [tasks/WP04-ws2-resume-state-cli.md](./tasks/WP04-ws2-resume-state-cli.md)
- **Risk**: CAS false-REFUSEs the behind-HEAD window it protects (D/F8) — tested explicitly.

### WP05 — Executor integration  *(P2 · python-pedro · deps WP03, WP04 · closes #4982/#4997/#4985/#4991 with WP03/WP04)*
- **Goal**: the single `executor.py` owner — honest squash message, strategy reseed, read-persisted-first coord/lane-tip anchoring, resume wiring.
- **Independent test**: resume honors persisted strategy; coord base is not re-poisoned on resume-of-resume; message honest.
- **Subtasks**: T019–T023. Prompt: [tasks/WP05-executor-integration.md](./tasks/WP05-executor-integration.md)
- **Risk**: re-poison on resume (F3/F9), stripping enforce_closed_world (architect) — both guarded + tested.

### WP06 — Docs + CHANGELOG  *(curator-carla · deps WP01–WP05)*
- **Goal**: honest CHANGELOG + doc note that the default squash now enforces the content axis. No over-claim of the lane-re-lettering root.
- **Subtasks**: T024–T025. Prompt: [tasks/WP06-docs-changelog.md](./tasks/WP06-docs-changelog.md)

## Integration steps (orchestrator, at consolidation — reviewed by the pre-merge squad)
1. Remove each `tests/terminus/` `xfail(strict)` marker as its fix lands; capture per-repro RED-before / GREEN-after evidence. Any child that cannot fully close stays `xfail(strict)` with an honest reason. The nine tracked files: `test_repro_{4945,4970,4977,4981,4982,4985,4991,4997}.py` + `test_terminus_reconciliation_property.py`. (Marker removal is deliberately an orchestrator step, not a WP — WP01 owns these files to ADD red tests and a WP owning them for removal would statically overlap WP01.)
2. **Red-isolation checkpoint (post-tasks renata):** after WP04 (strategy fix, WS2a) lands but BEFORE WP05 (WS2b lane-tip work), run `test_repro_{4982,4997}.py` and confirm they STILL `xfail`-RED — proving WP05's lane-tip preservation is load-bearing, not dead code. Record the (a)-only baseline alongside the HEAD baseline (WP01 T005).
3. Land the 3-way merge-resolution residual as a dedicated `xfail(strict, reason=…)` that **actually exercises a conflict-resolving squash** (a real 3-way-resolved blob at a path, not a bare never-run marker) — see WP03 T014. C-003, not "leave uncovered".
4. Run the blast-radius gate (`tests/merge tests/coordination tests/git tests/lanes tests/terminus` + `make test-fast`) + ruff/mypy/format.

## MVP
WP03 + WP05 (the squash content axis + its executor wiring) deliver the P0 #5013 default-flow guarantee — the highest-value slice.
