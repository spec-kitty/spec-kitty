# Tasks: Cheap nightly reds remediation

**Mission**: `nightly-reds-remediation-01M6VYS1` | **Branch**: `issue-7183-nightly-reds-remediation` | **Topology**: `single_branch`
**Inputs**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md)

Four independent work packages, run one after the other in the write checkout. Every WP follows RED first, then re-pin, then GREEN. The nodes are nightly-only, so the recorded local run IS the verification.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Pin `--dependency-ref` in the consolidate flag golden (#7177) | WP01 | |
| T002 | Rewrite the orchestrator-api migration-actor test to seed in-process (#7111) | WP01 | |
| T003 | RED/GREEN evidence and neighbour guards for WP01 | WP01 | |
| T004 | Add `checkout_file_recipe` to `_git_remedies.py` (#7178) | WP02 | |
| T005 | Route `tracked_meta_notice.py` through it, drop `_RESTORE` (#7178) | WP02 | |
| T006 | Unit tests for the new renderer (#7178) | WP02 | |
| T007 | RED/GREEN evidence, notice pins and gate neighbours for WP02 | WP02 | |
| T008 | Re-pin `test_status_json_error_is_parseable` to the typed envelope (#7181) | WP03 | |
| T009 | Re-pin the unparseable-`charter.yaml` freshness test to the typed refusal (#7181) | WP03 | [P] |
| T010 | Seed present activation lists in the six activate tests (#7182) | WP03 | [P] |
| T011 | Re-pin the two ambiguous-directive interview nodes to the collision refusal (#7182) | WP03 | [P] |
| T012 | RED/GREEN evidence and neighbour guards for WP03 | WP03 | |
| T013 | Merge done-transition actor, 4-key dict (#7183 n1) | WP04 | [P] |
| T014 | `mission_id` in the tasks-status default fixture (#7183 n2) | WP04 | [P] |
| T015 | Cutover git-call budget `2 + 4 x real` (#7183 n3) | WP04 | [P] |
| T016 | Ignore runtime locks in pack-skill lifecycle snapshots (#7183 n4) | WP04 | [P] |
| T017 | Single-branch residue bookkeeping assertions (#7183 n5) | WP04 | [P] |
| T018 | Changelog fragment and drafted follow-up for the per-Mission git cost | WP04 | |
| T019 | RED/GREEN evidence, owning files and format check for WP04 | WP04 | |

## WP01 - Test re-pins without production change (#7177, #7111)

**Goal**: two stale pins re-pinned. **Priority**: P1. **Prompt**: [tasks/WP01-test-repins-7177-7111.md](tasks/WP01-test-repins-7177-7111.md)
**Independent test**: `test_merge_cli_golden.py` 11 passed; `test_wp_lifecycle_structured_actor_6400.py` 9 passed.

T001 Pin `--dependency-ref` in the consolidate flag golden (WP01)
T002 Rewrite the orchestrator-api migration-actor test to seed in-process (WP01)
T003 RED/GREEN evidence and neighbour guards for WP01 (WP01)

Dependencies: none. Risks: the #7111 rewrite expects role `system`, not `implementer`.

## WP02 - Git-remedies checkout renderer (#7178)

**Goal**: gate passes with an empty allowlist; notice text byte-identical. **Priority**: P1. **Prompt**: [tasks/WP02-checkout-file-recipe-7178.md](tasks/WP02-checkout-file-recipe-7178.md)
**Independent test**: `test_git_remedies.py` green (gate plus new unit tests); `test_read_tracked_meta_6673.py` unchanged and green.

T004 Add `checkout_file_recipe` to `_git_remedies.py` (WP02)
T005 Route `tracked_meta_notice.py` through it, drop `_RESTORE` (WP02)
T006 Unit tests for the new renderer (WP02)
T007 RED/GREEN evidence, notice pins and gate neighbours for WP02 (WP02)

Dependencies: none. Risks: import cycle (deferred import); never substitute `restore_recipe`.

## WP03 - Charter status and activation re-pins (#7181, #7182)

**Goal**: ten nodes aligned to the typed refusal, the absent-key rule and the collision refusal. **Priority**: P2. **Prompt**: [tasks/WP03-charter-repins-7181-7182.md](tasks/WP03-charter-repins-7181-7182.md)
**Independent test**: the four owning files green; the #6557, #6527, #6685 sibling files green.

T008 Re-pin `test_status_json_error_is_parseable` to the typed envelope (WP03)
T009 Re-pin the unparseable-`charter.yaml` freshness test to the typed refusal (WP03)
T010 Seed present activation lists in the six activate tests (WP03)
T011 Re-pin the two ambiguous-directive interview nodes to the collision refusal (WP03)
T012 RED/GREEN evidence and neighbour guards for WP03 (WP03)

Dependencies: none. Risks: interview keeps its own `_emit_error` JSON shape; the cascade file takes about two minutes.

## WP04 - The six nodes of #7183 and the record (#7183)

**Goal**: five independent contract re-pins plus changelog fragment and drafted follow-up. **Priority**: P2. **Prompt**: [tasks/WP04-nightly-7183-five-repins.md](tasks/WP04-nightly-7183-five-repins.md)
**Independent test**: the five owning files green.

T013 Merge done-transition actor, 4-key dict (WP04)
T014 `mission_id` in the tasks-status default fixture (WP04)
T015 Cutover git-call budget `2 + 4 x real` (WP04)
T016 Ignore runtime locks in pack-skill lifecycle snapshots (WP04)
T017 Single-branch residue bookkeeping assertions (WP04)
T018 Changelog fragment and drafted follow-up for the per-Mission git cost (WP04)
T019 RED/GREEN evidence, owning files and format check for WP04 (WP04)

Dependencies: none. Risks: a one-off venv-rebuild red on the pack-skill lifecycle test must be reported, never retried to green silently.
