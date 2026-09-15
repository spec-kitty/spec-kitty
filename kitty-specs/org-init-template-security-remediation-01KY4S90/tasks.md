# Tasks: Org Init Template Security Remediation

**Input**: Design documents from `/kitty-specs/org-init-template-security-remediation-01KY4S90/`  
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | RED: HTTPS template resolve must not inject GIT_TOKEN | WP01 | [P] |
| T002 | Add `inject_token` to GitSource; template path passes False | WP01 | |
| T003 | RED+green: reject `http://` / `git://` with `template.scheme_rejected` | WP01 | [P] |
| T004 | Wire resolve scheme guard before fetch; keep HTTPS/SSH/local | WP01 | |
| T005 | RED: symlink-to-host-file must not land as file bytes in dest | WP02 | [P] |
| T006 | Skip symlink entries in `copy_template_tree` | WP02 | |
| T007 | RED: path-component `{{ORG_NAME}}`/`{{LOCAL_PATH}}` → `substitute.path_token` | WP02 | [P] |
| T008 | Path-token scan + single-pass content leftover detection | WP02 | |
| T009 | RED+green: atomic `--force` move-aside-then-swap | WP03 | |
| T010 | Replace `assert`/bare RuntimeError with PipelineError guards | WP03 | |
| T011 | Docs: credential skip policy + fnmatch `*` crosses `/` | WP03 | [P] |

## Phase 1 – Credential + scheme (WP01)

### WP01 – Skip GIT_TOKEN on template path + reject plaintext schemes

**Prompt**: [`tasks/WP01-template-credential-and-scheme.md`](./tasks/WP01-template-credential-and-scheme.md)  
**Goal**: FR-001, FR-007 — template resolve never injects `GIT_TOKEN`; `http://`/`git://` fail closed.  
**Priority**: P1  
**Independent test**: pytest on resolve + GitSource inject flag  
**Requirements**: FR-001, FR-007, NFR-002  
**Dependencies**: none  

T001 RED: HTTPS template resolve must not inject GIT_TOKEN (WP01)
T002 Add `inject_token` to GitSource; template path passes False (WP01)
T003 RED+green: reject `http://` / `git://` with `template.scheme_rejected` (WP01)
T004 Wire resolve scheme guard before fetch; keep HTTPS/SSH/local (WP01)

## Phase 2 – Copy + substitute (WP02)

### WP02 – Symlink skip + path-token reject + single-pass leftovers

**Prompt**: [`tasks/WP02-symlink-and-path-tokens.md`](./tasks/WP02-symlink-and-path-tokens.md)  
**Goal**: FR-003–006, FR-010 — no host exfil via symlink; fail-closed path tokens; single-pass content leftovers.  
**Priority**: P1  
**Independent test**: ignore_copy + substitute unit tests  
**Requirements**: FR-003, FR-004, FR-005, FR-006, FR-010, NFR-002, NFR-003  
**Dependencies**: none (parallel with WP01)  

T005 RED: symlink-to-host-file must not land as file bytes in dest (WP02)
T006 Skip symlink entries in `copy_template_tree` (WP02)
T007 RED: path-component tokens → `substitute.path_token` (WP02)
T008 Path-token scan + single-pass content leftover detection (WP02)

## Phase 3 – Install guards + docs (WP03)

### WP03 – Atomic force install, PipelineError guards, docs

**Prompt**: [`tasks/WP03-atomic-install-and-docs.md`](./tasks/WP03-atomic-install-and-docs.md)  
**Goal**: FR-002, FR-008, FR-009, FR-011 — safe force install; no assert-only guards; document policy + fnmatch.  
**Priority**: P2  
**Independent test**: pipeline unit tests + doc review  
**Requirements**: FR-002, FR-008, FR-009, FR-011  
**Dependencies**: none (code surfaces disjoint; can parallel)  

T009 RED+green: atomic `--force` move-aside-then-swap (WP03)
T010 Replace `assert`/bare RuntimeError with PipelineError guards (WP03)
T011 Docs: credential skip policy + fnmatch `*` crosses `/` (WP03)

## Parallelization

- WP01 ∥ WP02 (disjoint owned_files).
- WP03 ∥ WP01/WP02 on code (pipeline/docs only); prefer after WP01+WP02 if reviewing end-to-end render.

## MVP

WP01 + WP02 clear the blocking review findings; WP03 completes hardening + docs for SC-004.
