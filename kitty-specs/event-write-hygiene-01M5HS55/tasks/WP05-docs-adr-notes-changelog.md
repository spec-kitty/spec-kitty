---
work_package_id: WP05
title: Docs, ADR amendment notes, changelog
dependencies:
- WP02
- WP03
- WP04
requirement_refs:
- FR-010
subtasks:
- T018
- T019
- T020
- T021
phase: Phase 4 - Docs
assignee: ''
agent: claude
shell_pid: ''
history:
- at: '2026-10-22T13:30:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: architect-alphonso
authoritative_surface: docs/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- docs/architecture/event-ledger-writers-and-readers.md
- docs/adr/4.x/2026-10-13-2-the-event-ledger-is-the-publication-seam-default-on-with-local-retention.md
- docs/adr/4.x/2026-10-14-1-event-native-core-one-canonical-event-writer.md
- docs/adr/3.x/2026-04-25-1-shared-package-boundary.md
- docs/adr/3.x/2026-06-26-2-core-integration-boundary.md
- docs/api/batch-api-contract.md
- docs/api/environment-variables.md
- docs/changelog/CHANGELOG.md
role: implementer
task_type: implement
---

# Work Package Prompt: WP05 – Docs, ADR amendment notes, changelog

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile named in the frontmatter. Follow its guidance before you read the rest of this prompt.

- **Profile**: `architect-alphonso`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status --mission event-write-hygiene-01M5HS55` for a `review_ref`. Address every item, and record what you changed with `spec-kitty agent tasks add-history WP05 --note "..."`.

---

## Objectives & Success Criteria

Bring the documentation in line with what WP02–WP04 shipped:
- **Gap table:** update the G-11, G-16 and G-18 rows in `docs/architecture/event-ledger-writers-and-readers.md`.
- **ADR amendment notes:** add dated notes to three ADRs. Do not rewrite their bodies.
- **Env-var reference:** document the renamed env var.
- **Changelog:** add a **breaking** `[Unreleased]` entry.
- **Stale mentions:** fix doc text that names deleted or renamed seam symbols.
- **Gates:** the docs freshness and terminology gates are green.

Requirements covered: FR-010.

## Context & Constraints

- **Read first:**
  - `plan.md` IC-06;
  - `research.md` (squad dispositions);
  - the final diff of WP02–WP04: `git log --oneline` on `feat/event-write-hygiene`, plus `git diff 326d588f -- src tests`.
- **Writing doctrine:** follow the charter's "Writing, Communication & Diagramming Doctrine". Write concrete, factual and dated text. Say "Mission", not "feature".
- **Terminology:** "sync" and "saas" are residue vocabulary. Name them only to say they were removed.
- **Historical content is immutable:** never edit `docs/reports/**`, released changelog sections or `kitty-specs/**` of other missions. The occurrence map exceptions list these.

## Branch Strategy

- **Strategy:** single_branch, on `feat/event-write-hygiene` in the repository root checkout.
- **Planning base branch / merge target:** `feat/event-write-hygiene`.
- **Command:** `spec-kitty agent action implement WP05 --agent claude --mission event-write-hygiene-01M5HS55`

## Subtasks & Detailed Guidance

### Subtask T018 – Gap table rows

Edit `docs/architecture/event-ledger-writers-and-readers.md` (around :206, :211 and :213).

**G-11.** Mark it closed by this Mission:
- the seam is renamed (list the new names);
- there is **no** env alias, per the operator ruling of 2026-10-22, which supersedes the row's "with an env alias" proposal;
- the stub-handler contract test is `tests/status/test_adapters_contract.py`.

**G-16.** Mark it closed:
- doors deleted: `store.append_event`, `append_event_verified`, `append_primary_checkout_event_verified`, `append_event_log` and `append_to_index`;
- enforced by the re-pinned `test_status_unsafe_allowlist.py`, `test_status_events_writes_gate.py` (including the `ops-index.jsonl` single-writer check) and `test_no_dead_symbols.py`.

**G-18.** Mark it closed:
- the importing code (the dead hosted builder) was deleted rather than replaced;
- the gate is `tests/architectural/test_events_tracker_public_imports.py`, not `test_shared_package_boundary.py`, which the row named. It covers all production roots and any private symbol;
- record the upstream ask as "proposed" (a public `known_event_types()` and public `diary` helpers).

Also check:
- the writers table and the "No dependencies, in parallel" ordering list (:220-222);
- any mention of the deleted doors or the old seam names elsewhere on the page.

Keep the page's frontmatter `updated:` current.

### Subtask T019 – ADR amendment notes and stale seam doc mentions

Each note is a short `## Amendment 2026-10-22` section at the end of the ADR, in the style other ADRs in `docs/adr/4.x/` use (look at one that has an Amendment section first).

- **`docs/adr/4.x/2026-10-13-2-...publication-seam...md`:** the rename debt at :165 is discharged; give the new names; there is no alias.
- **`docs/adr/4.x/2026-10-14-1-event-native-core-one-canonical-event-writer.md`:**
  - :56, :67 and :89 name the seam or doors; :67's "gates on hosted drain" claim is already stale.
  - State the facts: the doors are deleted, the seam is renamed, and the produce seam registers no default handler.
  - Do **not** amend D-1/D-2 for the Java writer decision. That is a separate pending ADR (#6608 comment).
- **`docs/adr/3.x/2026-04-25-1-shared-package-boundary.md`:**
  - the boundary now means public **symbols** only, not just the public package (no `_`-prefixed module or name);
  - add `tests/architectural/test_events_tracker_public_imports.py` to its enforcement references (:131).

Stale doc mentions:
- `docs/api/batch-api-contract.md:893` (`_saas_fan_out`): point it at the new name;
- `docs/adr/3.x/2026-06-26-2-core-integration-boundary.md`: add a short amendment note only if it names a renamed symbol as live; otherwise leave it;
- `docs/plans/engineering-notes/2173-infra-logic-separation/00-SYNTHESIS.md`: an engineering note, historical. Leave it unless it claims current state.

### Subtask T020 – Env-var reference and changelog

- **`docs/api/environment-variables.md`:**
  - add `SPEC_KITTY_STATUS_FANOUT_TIMEOUT`: seconds; default 10; non-positive runs handlers inline; non-finite falls back to the default; bounds each produce-seam handler;
  - if `SPEC_KITTY_SAAS_FANOUT_TIMEOUT` is listed, replace it, with a one-line "renamed in 4.0.0rc8+ (#6607); the old name is ignored".
- **`docs/changelog/CHANGELOG.md` `[Unreleased]` (:18):** follow that file's format.
  - The lead is bold and impact-first, with `(#6614, #6607)`, followed by before → after.
  - Mark the seam API and env-var rename as **breaking**: a transport owner calling the old `register_*`/`fire_*` names, or setting the old variable, must switch.
  - Mention:
    - the deleted doors (internal; no user-visible behaviour change);
    - the deleted hosted builder;
    - the widened public-imports gate;
    - the test seeding helper (contributors).

### Subtask T021 – Docs gates

Run:

```bash
.venv/bin/python scripts/docs/check_docs_freshness.py --ci   # errors must be 0
PWHEADLESS=1 .venv/bin/python -m pytest tests/architectural/test_no_legacy_terminology.py -q
```

If any docs index script applies to edited pages, run it as well (`scripts/docs/docs_index.py --write`; check its `--help`; only needed for new pages).

## Risks & Mitigations

- **Rewriting history:** amendment notes only, appended and dated.
- **Freshness gate:** keep `updated:` frontmatter current on every edited page.

## Review Guidance

- The gap rows are factual and point at the real gates.
- The changelog marks the env-var and seam rename as breaking.
- No released changelog section or report was edited.

## Progress & Status

Use `add-history`, `mark-status T018..T021 --status done`, then `move-task WP05 --to for_review`.
