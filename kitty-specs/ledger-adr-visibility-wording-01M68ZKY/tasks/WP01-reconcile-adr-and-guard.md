---
work_package_id: WP01
title: Reconcile ADR §5/#E and add the visibility guard
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-003
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-004
planning_base_branch: issue-6362-adr-visibility-wording
merge_target_branch: issue-6362-adr-visibility-wording
branch_strategy: Planning artifacts for this mission were generated on issue-6362-adr-visibility-wording. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6362-adr-visibility-wording unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Reconciliation
history:
- at: '2026-10-31T12:45:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/adr/4.x/
create_intent:
- tests/docs/test_migration_ledger_adr_visibility.py
execution_mode: code_change
model: ''
owned_files:
- docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md
- docs/adr/4.x/index.md
- docs/development/page-inventory.yaml
- docs/development/docs-retrieval-index.yaml
- tests/docs/test_migration_ledger_adr_visibility.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Reconcile ADR §5/#E and add the visibility guard

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter,
and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi`

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status`) before starting.

---

## Objectives & Success Criteria

The accepted migration-ledger ADR must state the visibility decision that actually shipped, and a
docs guard must stop the current decision from naming a command that does not exist again.

Done when:

- `tests/docs/test_migration_ledger_adr_visibility.py` exists and **fails** on the unedited ADR
  (red-first proof): `spec-kitty doctor migrations` is not a registered command path.
- §5 of `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md` names
  `spec-kitty migrate ledger` (and its `--json` flag) as the shipped read surface and names the
  single pending source `VersionDetector.applicable_migrations`.
- The #E deliverable bullet names the same shipped command.
- The original `doctor migrations` / `upgrade --list-applied` proposal is still present but
  explicitly labelled historical/rejected, with the reason it was not built (one read surface
  cannot diverge from itself).
- The guard passes after the edit; `check_docs_freshness --ci` reports `errors=0`; the ADR
  structural tests pass.
- No file under `src/` changes; no command alias is added.

## Context & Constraints

- Ground truth for behaviour: `src/specify_cli/cli/commands/migrate_cmd.py` (`ledger` command,
  `--json` payload, `_ledger_step_state`, `_STATE_*`, `_DRIFT_HUMAN`) and
  `tests/specify_cli/upgrade/test_migrate_ledger_cmd.py`.
- The ADR already contains a closeout note (~lines 391-395) recording the divergence; keep it but
  make it read as the record of why one surface shipped, not as two equally-current statements.
- Do **not** implement `spec-kitty doctor migrations` or `upgrade --list-applied` (C-001), and do
  not touch the ledger, the registry or any migration module (C-002).
- Section vocabulary must stay canonical: "read surface", "pending source", "tracked/clone-local
  partition", "audit-only drift" (grep `docs/context/` before inventing a term).
- Shared machine state: other agents work other missions on this host. Regenerate only this page's
  derived surfaces and verify with the freshness check; do not rebuild the whole CLI reference.

## Branch Strategy

- **Strategy**: single-branch mission; planning base and merge target are the same branch.
- **Planning base branch**: `issue-6362-adr-visibility-wording`
- **Merge target branch**: `issue-6362-adr-visibility-wording`

> Populated by `spec-kitty agent mission finalize-tasks`.

## Subtasks & Detailed Guidance

### T001 – Red-first docs guard

- **Purpose**: Make the defect executable so the fix has a proof.
- **Steps**: Create `tests/docs/test_migration_ledger_adr_visibility.py`:
  - read `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md`;
  - slice §5's body (from the `### 5. ` heading to the next `### ` heading) and the `- **#E` bullet
    from the "Follow-up child issues" list;
  - extract `spec-kitty …` code-span command paths from those slices with
    `scripts.docs.check_cli_reference_freshness.extract_referenced_paths` (reuse it, do not
    re-implement the regex);
  - assert every extracted path is present in the live Typer surface from
    `scripts.docs._typer_walker.walk(specify_cli.app...)`, and that `("migrate", "ledger")` is among
    them;
  - set `SPEC_KITTY_ENABLE_SAAS_SYNC=1` and `SPEC_KITTY_NO_UPGRADE_CHECK=1` in `os.environ`
    **before** importing `specify_cli` (same as `tests/architectural/test_docs_cli_reference_parity.py`).
  Give the module a docstring stating the invariant and why the scan is scoped to these two
  sections (other ADRs legitimately record never-shipped proposals).
- **Files**: `tests/docs/test_migration_ledger_adr_visibility.py`
- **Parallel?**: No — the red proof must precede T002.
- **Notes**: Run `uv run pytest tests/docs/test_migration_ledger_adr_visibility.py -q` and capture
  the failure output for the PR body.

### T002 – Rewrite §5's visibility decision

- **Purpose**: The reader who lands on §5 must be told the command that exists.
- **Steps**: Replace the two-surface proposal paragraph with the shipped decision: the read surface
  is `spec-kitty migrate ledger` (`--json` emits the same report), it renders the declared set
  (manifest), the applied set (both ledgers), the pending set, the tracked/clone-local partition
  and drift flags, and it consumes the single pending source
  `VersionDetector.applicable_migrations` so the reported pending set cannot diverge from the
  applied set. Add a short marked-historical paragraph: the earlier proposal for a `doctor
  migrations` sub-surface plus an `upgrade --list-applied` flag was **not built**; one read surface
  replaced the two proposed consumers, which removes the divergence risk the two-surface design
  would have carried.
- **Files**: `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md`
- **Parallel?**: No.
- **Notes**: Keep the prose style of neighbouring decisions (short declarative paragraphs, code
  spans for paths). Do not restate drift/partition semantics differently from `migrate_cmd.py`.

### T003 – Rewrite the #E deliverable and re-frame the closeout note

- **Purpose**: A maintainer re-planning #E must not re-commission the retired surface.
- **Steps**: Change the #E bullet to name `spec-kitty migrate ledger` (`--json`) via
  `detector.applicable_migrations`; keep its dependency note. Adjust the closeout note
  (incidental notes, item "Visibility surface command name") so it records the decision (one read
  surface shipped instead of the two proposed) instead of reading as a live disagreement between
  the decision and reality.
- **Files**: `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md`
- **Parallel?**: Yes, with T002 (same file, one pass).
- **Notes**: A bare `doctor migrations` / `upgrade --list-applied` mention without the `spec-kitty`
  prefix is fine in the historical paragraph; the guard only scans `spec-kitty …` snippets.

### T004 – Heading and vocabulary alignment

- **Purpose**: A heading that promises "two read surfaces" contradicts the shipped single surface.
- **Steps**: Rename §5's heading to "5. Visibility — one pending-source, one read surface". Confirm
  the partition/pending/drift sentences still match `migrate_ledger`'s tokens (`in-place`,
  `recorded-elsewhere`, `pending`; drift reported, never re-applied). Update the frontmatter
  `updated:` date to `2026-10-31`.
- **Files**: `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md`
- **Parallel?**: No.
- **Notes**: Section 2's "Recorded elsewhere vs pending" note and Amendment text stay as they are —
  they already describe the shipped behaviour.

### T005 – Regenerate the page's derived surfaces

- **Steps**:
  ```bash
  uv run python -m scripts.docs.docs_index --write
  uv run python -m scripts.docs.freshen_adr_inventory docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md
  git diff --stat
  ```
  Confirm the diff is confined to this page's retrieve-index anchors
  (`docs/development/docs-retrieval-index.yaml`) and that `page-inventory.yaml` and
  `docs/adr/4.x/index.md` are unchanged (the ADR already has its row/title).
- **Files**: `docs/development/docs-retrieval-index.yaml` (only if the regenerator changes it)
- **Parallel?**: No — after T002–T004.
- **Notes**: The regenerators read only the docs tree in this checkout; the result is
  deterministic. Do not run a full CLI-reference rebuild.

### T006 – Verify

- **Steps**:
  ```bash
  uv run pytest tests/docs/test_migration_ledger_adr_visibility.py -q
  uv run pytest tests/docs/test_adr_content_invariance.py tests/docs/test_architecture_docs_consistency.py tests/docs/test_docs_structural_lint.py -q
  uv run python -m scripts.docs.check_docs_freshness --ci
  ```
  Record every result (pass counts, errors=0) in the WP history note.
- **Files**: n/a
- **Parallel?**: No.
- **Notes**: If a gate reports an unrelated pre-existing red, cite the existing issue in the PR's
  `## Deferred` rather than papering over it.

## Test Strategy

The guard is the mission's red-first proof and its permanent ratchet: it fails on the pre-fix ADR
and passes afterwards. The docs tests around it (`test_adr_content_invariance`,
`test_architecture_docs_consistency`, `test_docs_structural_lint`) confirm the page is still a
well-formed ADR after the edit.

## Risks & Mitigations

- Heading rename drifts the committed retrieval index → T005 regenerates it; the freshness gate
  reports `DOCS-INDEX-DRIFT` if missed.
- Over-editing the ADR → restrict edits to §5, the #E bullet, the closeout note and the frontmatter
  date.
- The guard becoming a general ADR-prose rule → keep it scoped to §5 + #E and say so in the
  module docstring.

## Review Guidance

- Does §5 state the shipped command and the single pending source, and is the old proposal clearly
  historical (with a reason)?
- Does the guard fail for a genuine declaration of a phantom command (not merely pin prose)?
- Are partition/pending/drift statements still true of `migrate ledger`'s output?
- No `src/` change, no new command alias.

## Progress & Status

- First: `spec-kitty agent action implement WP01 --agent <name> --mission ledger-adr-visibility-wording-01M68ZKY`
- Record progress with `spec-kitty agent tasks add-history WP01 --note "…"`.
