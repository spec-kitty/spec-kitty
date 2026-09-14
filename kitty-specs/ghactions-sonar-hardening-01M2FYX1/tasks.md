# Tasks: GitHub Actions Sonar hardening (validatable workflows)

**Mission**: ghactions-sonar-hardening-01M2FYX1 | **Issue**: #4342

## Subtask Index
| ID | Description | WP | Parallel |
|----|-------------|----|----|
| T001 | Convert 9 S7630 input-injection sites to env-indirection (module-tests.yml) | WP01 | [P] |
| T002 | Validate module-tests.yml (actionlint/YAML, behavior-identical) | WP01 | |
| T003 | SHA-pin S7637 actions (ci-quality setup-uv ×4, ci-windows paths-filter) | WP02 | [P] |
| T004 | Fold ci-windows S8264 perm + validate | WP02 | |
| T005 | Relocate S8264/S8233 permissions to needing jobs (ci-aggregate, ci-fleet-verdict) | WP03 | [P] |
| T006 | Pin ci-aggregate 3rd-party installs + validate | WP03 | |
| T007 | Pin pyyaml/packaging/claude-code (ci-modules, events-alignment, packs) | WP04 | [P] |
| T008 | Validate WP04 files | WP04 | |
| T009 | Author adjudication.md (safe-as-written + FP rationale, no edits) | WP05 | [P] |

## Work Packages

### WP01 — S7630 input-injection env-indirection (module-tests.yml)
Goal: close the script-injection class behavior-identically. Independent test: actionlint + diff-review shows same commands/values. Subtasks: T001, T002. Prompt: tasks/WP01-input-injection-env-indirection.md

### WP02 — S7637 action SHA-pinning (ci-quality.yml, ci-windows.yml)
Goal: pin flagged actions to own-version SHAs; fold ci-windows perm. Subtasks: T003, T004. Prompt: tasks/WP02-action-sha-pinning.md

### WP03 — Least-privilege permissions + ci-aggregate installs
Goal: relocate permissions to needing jobs; pin ci-aggregate installs. Subtasks: T005, T006. Prompt: tasks/WP03-permissions-and-aggregate-installs.md

### WP04 — 3rd-party install hardening (ci-modules, events-alignment, packs)
Goal: pin pyyaml/packaging/claude-code; leave uv-sync + npm-lifecycle. Subtasks: T007, T008. Prompt: tasks/WP04-thirdparty-install-hardening.md

### WP05 — Adjudication dossier (no code edits)
Goal: won't-fix rationale for the 46 uv-sync hotspots + FPs. Subtask: T009. Prompt: tasks/WP05-adjudication-dossier.md

## Parallelization
All five WPs own disjoint files → fully parallel. Integration gate: the PR's own CI run over the eight edited workflows is green (NFR-001).
