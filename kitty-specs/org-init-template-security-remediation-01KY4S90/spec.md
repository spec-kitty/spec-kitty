# Org Init Template Security Remediation

**Mission ID:** 01KY4S90DHE3Q7XHXC08K228SW  
**Mission slug:** org-init-template-security-remediation-01KY4S90  
**Mission type:** software-dev  
**Status:** Proposed  
**Parent PR:** [#2719](https://github.com/Priivacy-ai/spec-kitty/pull/2719) (`feat/doctrine-org-init-from-template`)  
**Supersedes / remediates:** security and correctness findings from the maintainer readiness review on the doctrine `--template` path (mission `doctrine-org-init-from-template-01KXNA6P`).

## Purpose

The doctrine `org init --template` feature can fetch and render an arbitrary third-party tree. Maintainer review on PR #2719 found blocking gaps under that threat model: `GIT_TOKEN` can be injected into any HTTPS template URL; symlink-following copy can exfiltrate host files into the rendered pack; and `{{ORG_NAME}}` / `{{LOCAL_PATH}}` leftovers in **file or directory names** are neither substituted nor rejected. This mission remediates those blockers and the agreed hardening items so the PR can clear `pr:needs-revision` readiness (not `pr:deferred` / merge to `main`).

Omitting `--template` keeps the legacy three-file scaffold unchanged.

## Domain Language

| Canonical term | Meaning | Synonyms to avoid |
|---|---|---|
| template path | The doctrine `--template` resolve + render pipeline for `org init` | “GitSource generally”, “all clones” |
| token injection | Embedding `GIT_TOKEN` as HTTPS userinfo for authenticated fetch | “always authenticate”, “OAuth for every host” |
| symlink entry | A filesystem entry where `is_symlink()` is true in the template tree | “shortcut”, “alias file” |
| path token | `{{ORG_NAME}}` or `{{LOCAL_PATH}}` appearing in a file or directory **name** | “content token” only |
| trusted host | Documented host allowed to receive injected credentials (if allowlist strategy is used) | “any git remote” |

## Functional Requirements

### Blocking (must land for review clearance)

| ID | Description | Status |
|---|---|---|
| FR-001 | On the doctrine `org init --template` resolve path, the system MUST NOT inject `GIT_TOKEN` (or equivalent credentials) into HTTPS URLs for arbitrary hosts. Either skip credential injection for this path entirely, or inject only for hosts on a documented trusted-host allowlist. | Proposed |
| FR-002 | Operator-facing documentation MUST describe the chosen credential policy for `--template` (skip vs allowlist) so packagers know when authenticated fetch applies. | Proposed |
| FR-003 | When copying a template tree, the system MUST NOT follow symlinks into host filesystem content for the purpose of writing file bytes into the rendered pack (no `shutil.copy2`-style follow of symlink-to-file targets such as `~/.ssh/id_rsa`). | Proposed |
| FR-004 | Symlink entries in the template MUST be skipped or rejected with a clear structured error; absolute or escaping symlink targets MUST NOT cause host file contents to appear under PACK_PATH. | Proposed |
| FR-005 | After render, no path component (file or directory **name**) under PACK_PATH may contain unsubstituted `{{ORG_NAME}}` or `{{LOCAL_PATH}}`. Confirmed product choice: **reject** templates whose entry names contain those tokens (fail-closed with a structured rule id); content substitution remains the only place tokens are rewritten. | Proposed |
| FR-006 | Content leftover detection for `{{ORG_NAME}}` / `{{LOCAL_PATH}}` remains mandatory and MUST continue to fail the render when content tokens survive. | Proposed |

### Hardening (in scope)

| ID | Description | Status |
|---|---|---|
| FR-007 | Template location classification MUST reject `http://` and `git://` schemes for `--template`. Only HTTPS and SSH (and local filesystem directories) are accepted; plaintext/unauthenticated remote schemes fail closed with a clear error. | Proposed |
| FR-008 | When `--force` replaces an existing PACK_PATH, install MUST be atomic from the operator’s perspective: move-aside (or equivalent) then swap so a failure mid-install does not destroy the prior pack without a recoverable prior tree. | Proposed |
| FR-009 | Control-flow guards that currently rely on `assert` for required resolve results MUST use explicit runtime checks that remain effective under `python -O`. Staging/install re-check failures that are part of the pipeline MUST raise the same structured pipeline error type used elsewhere (not a bare `RuntimeError`). | Proposed |
| FR-010 | Token substitution over file contents SHOULD detect leftover tokens in the same pass as replacement (no mandatory second full-tree read solely for leftover scan), without weakening FR-006. | Proposed |
| FR-011 | Documentation for `.templateignore` matching MUST state that `fnmatch` semantics allow `*` to cross `/`, and that this is a documented subset of gitignore—not full gitignore equivalence. | Proposed |

## Non-Functional Requirements

| ID | Description | Threshold | Status |
|---|---|---|---|
| NFR-001 | Stock / legacy init without `--template` is behaviourally unchanged. | Existing no-template acceptance coverage remains green. | Proposed |
| NFR-002 | Security regressions for FR-001 and FR-003 are covered by automated tests. | At least one test proves no credential userinfo on a non-allowlisted HTTPS template URL; at least one test proves a symlink-to-sensitive-file is not copied as file bytes into PACK_PATH. | Proposed |
| NFR-003 | Path-token rejection (FR-005) is covered by automated tests. | A fixture tree with `{{ORG_NAME}}` in a filename fails render with a structured rule id and leaves no successful pack presented as success. | Proposed |
| NFR-004 | New/changed modules pass project static gates. | Zero new ruff/mypy issues on owned remediation files; no blanket suppressions. | Proposed |

## Constraints

| ID | Description | Status |
|---|---|---|
| C-001 | Do not clear `pr:deferred` or merge this work to `main` as part of this mission; land on `feat/doctrine-org-init-from-template` only. | Active |
| C-002 | Do not redesign the existing seam decomposition (validation / resolve / ignore_copy / substitute / pipeline); remediate within those seams. | Active |
| C-003 | Confirmed decisions: (1) skip `GIT_TOKEN` injection on the doctrine `--template` resolve path (document; other GitSource callers unchanged unless they share this entry); (2) skip symlink entries during copy; (3) reject path-level `{{…}}` tokens rather than renaming paths. | Active |
| C-004 | Timing/rebase assessment vs later doctrine asset/template/glossary work is out of scope for this mission. | Active |
| C-005 | Whether to stop committing append-only mission status logs (`status.events.jsonl`, etc.) to the PR is a hygiene confirmation for maintainers—not a code-change requirement unless plan elevates it. | Active |

## User Scenarios & Testing

### Scenario 1 — Malicious HTTPS template URL does not receive GIT_TOKEN
Given `GIT_TOKEN` is set in the environment and the operator passes `--template https://attacker.example/repo.git`, when resolve runs, then the fetch URL MUST NOT contain the token as userinfo (skip injection on this path).

### Scenario 2 — Symlink to host secret is not materialised
Given a template containing a symlink whose target is a host file outside the template, when render copies the tree, then PACK_PATH MUST NOT contain that host file’s contents as a regular copied file.

### Scenario 3 — Path token in filename fails closed
Given a template file named `{{ORG_NAME}}.yaml` (or a directory name containing `{{LOCAL_PATH}}`), when render runs with valid org/local values, then the command fails with a structured rule id and does not present a successful pack.

### Scenario 4 — Content tokens still substitute
Given content containing `{{ORG_NAME}}` / `{{LOCAL_PATH}}` and clean entry names, when render succeeds, then contents are substituted and no content leftovers remain.

### Scenario 5 — Plaintext remote schemes rejected
Given `--template http://example.invalid/repo` or `git://…`, when classify/resolve runs, then the command fails closed before fetch.

### Scenario 6 — Legacy scaffold unchanged
Given no `--template`, when `org init` runs, then the three-file scaffold behaviour matches pre-remediation.

## Success Criteria

- **SC-001**: Reviewer can no longer reproduce GIT_TOKEN leakage to an arbitrary HTTPS host via `--template`.
- **SC-002**: Reviewer can no longer reproduce host-file exfiltration via a template symlink.
- **SC-003**: Reviewer can no longer ship an unflagged `{{ORG_NAME}}` / `{{LOCAL_PATH}}` in an entry name.
- **SC-004**: `http://` / `git://` template URLs are rejected; `--force` install no longer destroys the prior pack on mid-failure; docs cover credential policy and fnmatch subset.
- **SC-005**: PR #2719 can drop `pr:needs-revision` for these findings (deferred freeze label may remain).

## Assumptions

- The existing template-render modules and CLI wiring from mission `doctrine-org-init-from-template-01KXNA6P` remain the implementation surface.
- “Skip injection on template path” is sufficient for FR-001 without requiring a global GitSource allowlist in this mission.
- Skipping symlink entries (omit from copy) is acceptable; operators should not rely on symlinks inside doctrine templates.

## Out of Scope

- Clearing `pr:deferred` or merging to `origin/main`.
- Broad rewrite of `GitSource` for all non-template callers (unless required to implement the template-path skip cleanly).
- Full gitignore-compatible ignore semantics (document subset only).
- Full path-renaming substitution engine (rejected in favour of fail-closed on path tokens).
- Separate timing/rebase strategy assessment against later doctrine workstreams.
