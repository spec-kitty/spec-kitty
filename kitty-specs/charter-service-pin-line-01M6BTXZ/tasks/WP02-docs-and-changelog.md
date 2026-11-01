---
work_package_id: WP02
title: 'Docs: per-service release homes, provenance check, changelog'
dependencies:
- WP01
requirement_refs:
- FR-004
- SC-004
planning_base_branch: issue-6909-charter-service-pin-line
merge_target_branch: issue-6909-charter-service-pin-line
branch_strategy: Planning artifacts for this mission were generated on issue-6909-charter-service-pin-line. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6909-charter-service-pin-line unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-service-pin-line-01M6BTXZ
base_commit: 5489d40d772dadf93c43ed5c81e786728185ce10
created_at: '2026-11-01T16:46:52.397668+00:00'
subtasks:
- T008
- T009
- T010
- T011
phase: Phase 2 - Documentation
history:
- at: '2026-11-01T15:22:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- pins/README.md
- docs/development/how-to/service-pins.md
- docs/changelog/CHANGELOG.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Docs: per-service release homes, provenance check, changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``. Use language identifiers in code blocks: ````bash`, ````yaml`.

---

## Objectives & Success Criteria

An operator reading the pins README or the service-pins how-to learns, without guessing:

- each service's `service-v*` release comes from that service's own repository
  (`spec-kitty-events` for the two events services, `spec-kitty-charter` for the charter
  service);
- a bump verifies build provenance with `gh attestation verify` (signer workflow and source
  tag ref) before the lockfile is written, and `--no-attestation` is the explicit escape for
  an offline mirror or a rehearsal, never for a real bump;
- the stable refusal codes and what to do about them;
- what did not change (tag rule, targets, jar fallback, pin schema, `launchable`).

**Definition of Done**: the prose matches the shipped behaviour from WP01 (re-read the code
and `service vendor --help` before writing), `docs/changelog/CHANGELOG.md` has an
`[Unreleased]` entry under 1,200 characters, and T011's checks are green.

## Context & Constraints

- Read `kitty-specs/charter-service-pin-line-01M6BTXZ/spec.md` (FR-004, SC-004),
  `plan.md` (Phase 1 "Naming and docs") and `research.md` (D1-D3).
- External sources of truth: spec-kitty-charter ADR-0046 decisions 4 and 6;
  spec-kitty-events ADR 0003. Do **not** edit either ADR (they live in other repositories),
  and do not edit `docs/adr/2026-10-29-1` here: the change is documentation of the shipped
  surface, not a new decision.
- The root `CHANGELOG.md` is a symlink to `docs/changelog/CHANGELOG.md`; edit the target
  only.
- Every user-facing statement must be true of the code on this branch: WP01 has landed
  before this WP runs.

## Branch Strategy

- **Strategy**: docs land on `issue-6909-charter-service-pin-line`; the PR targets `main`.
- **Planning base branch**: `issue-6909-charter-service-pin-line`
- **Merge target branch**: `issue-6909-charter-service-pin-line`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

## Subtasks & Detailed Guidance

### Subtask T008 – `pins/README.md`

- **Purpose**: the directory README is the first thing an operator opens before a bump.
- **Steps**:
  - Replace the "spec-kitty-events `service-v*` tag" wording with the service's own
    repository, and name all three homes explicitly.
  - Update the "Empty until the first release" section so it does not claim only
    spec-kitty-events has a release line (the charter repository has its own).
  - Add a short "Provenance" section: a GitHub bump verifies every recorded asset with
    `gh attestation verify ... --signer-workflow .../.github/workflows/service-release.yml
    --source-ref refs/tags/<tag>` before writing the pin; `--no-attestation` is the explicit
    escape; a `file://` mirror is skipped.
- **Files**: `pins/README.md`.
- **Notes**: keep the existing rules (bump only with the vendor command, never hand-edit a
  digest) and the references list.

### Subtask T009 – `docs/development/how-to/service-pins.md`

- **Purpose**: the how-to is the operational guide; the current "cross-check out of band"
  note becomes the automatic check plus a manual second source.
- **Steps**:
  - In the intro, say each pin's tag comes from the service's own repository; keep the
    charter/events distinction.
  - In "Bump a pin", document that the repository defaults per service (charter ->
    spec-kitty-charter, events -> spec-kitty-events), that a GitHub bump verifies each
    asset's build attestation, and show the `--no-attestation` escape with its "never for a
    real bump" warning.
  - Rework the maintainer note: the check is automatic now; the manual `gh attestation
    verify` command stays as the independent second source.
  - Add the three new refusal codes to the refusal table with their remedies
    (`SERVICE_ATTESTATION_UNSUPPORTED`, `SERVICE_ATTESTATION_UNAVAILABLE`,
    `SERVICE_ATTESTATION_FAILED`) and note the charter-service fixture proof under "What a
    user does" only if it changes user-facing behaviour (it does not; skip if not).
  - Update the front-matter `updated:` date and, if useful, the description.
- **Files**: `docs/development/how-to/service-pins.md`.
- **Notes**: match the exact codes in the code (`grep SERVICE_ATTESTATION src/`); do not
  invent remedies.

### Subtask T010 – Changelog

- **Purpose**: a user-facing change needs an `[Unreleased]` entry.
- **Steps**: add one entry under `## [Unreleased]` in `docs/changelog/CHANGELOG.md`:
  a bold impact-first lead ending in `(#6909)`, then before/after, under 1,200 characters.
  Example shape (rewrite in your own words, do not copy verbatim if the facts differ):
  "**Pinning the charter service needs no `--repository`, and a bump now verifies the
  release's build provenance before it writes the pin.** Before: every service defaulted to
  spec-kitty-events and the pin trusted `SHA256SUMS` alone. After: ...".
- **Files**: `docs/changelog/CHANGELOG.md`.
- **Notes**: place it at the top of the Unreleased list, matching the file's existing style
  (see the nearest entries). Keep it under 1,200 characters including the lead.

### Subtask T011 – Freshness and terminology checks

- **Purpose**: prove the docs are consistent with the tree.
- **Commands**:
  ```bash
  uv run python -m scripts.docs.check_docs_freshness --ci
  uv run pytest tests/architectural/test_no_legacy_terminology.py -q
  ```
- **Files**: none new.
- **Notes**: the docs retrieval/index files are generated host state shared with other
  agents. Regenerate only the surface your diff changes
  (`uv run python -m scripts.docs.docs_index --write` if the how-to's headings changed), and
  report `errors=0`. If a generator reads or writes a path outside the clone and the output
  looks non-deterministic, say so in your WP history and the PR's `## Deferred`; do not
  sweep in unrelated regeneration.

## Test Strategy

No new executable behaviour in this WP. Verification is the freshness check, the
terminology guard, and a manual read of the prose against `grep` of the shipped codes and
help text.

## Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| Prose claims a behaviour WP01 did not ship | Re-read `service vendor --help` and `grep SERVICE_ATTESTATION src/` before writing |
| Generated docs index churn from a shared cache | Regenerate only the touched surface; verify with the freshness check, report non-determinism |
| Changelog entry over the limit | Count characters including the lead; keep before/after to two sentences |

## Review Guidance

- Does every repository name in the docs match `DEFAULT_REPOSITORIES`?
- Are the refusal codes exactly the code constants, with the right exit behaviour?
- Is `--no-attestation` described as an escape hatch, not a normal path?
- Does the changelog lead land the user impact first and cite `(#6909)`?

## Progress & Status

Record each subtask's completion with
`spec-kitty agent tasks mark-status T00N --status done` and note the check output with
`spec-kitty agent tasks add-history WP02 --note "..."`.
