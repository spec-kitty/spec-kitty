# Tasks: Nightly red: test seams after origin freshness

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Doctrine git-source recorder answers `core.sshCommand` reads as unset; fallback honours `text=` (FR-001) | WP01 | [P] |
| T002 | Consolidate flag golden pins `--origin-check` (FR-002) | WP01 | [P] |
| T003 | Accept decomposition harness fakes `run_origin_gate`; owned test asserts the fact reaches the gate (FR-003) | WP01 | [P] |
| T004 | Owned-checkout accept integration tests parse `result.stdout`; one pins the stderr note + `advisories` (FR-004) | WP01 | [P] |

## WP01 — Re-pin the test seams that drifted with origin freshness

**Goal**: the 16 nightly node ids pass; each failed on the merge base. **Priority**: P1. **Prompt**: [tasks/WP01-repin-origin-freshness-test-seams.md](tasks/WP01-repin-origin-freshness-test-seams.md)

**Independent test**: run the 16 node ids from #5886/#5887/#5888/#5889 on the merge base (red) and on the branch (green).

T001 Doctrine git-source recorder answers `core.sshCommand` reads as unset (WP01)
T002 Consolidate flag golden pins `--origin-check` (WP01)
T003 Accept decomposition harness fakes `run_origin_gate` (WP01)
T004 Owned-checkout accept tests parse stdout (WP01)

**Dependencies**: none. **Risks**: an over-broad recorder filter could hide a real extra git contact (the filter matches only `config … core.sshCommand`).
