---
work_package_id: WP02
title: Operator docs and the per-PR changelog fragment
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-004
- FR-006
- NFR-003
- C-004
- SC-001
- SC-002
planning_base_branch: issue-7128-report-only-pinned-pack-inputs
merge_target_branch: issue-7128-report-only-pinned-pack-inputs
branch_strategy: Planning artifacts for this mission were generated on issue-7128-report-only-pinned-pack-inputs. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7128-report-only-pinned-pack-inputs unless the human explicitly redirects the landing branch.
subtasks:
- T006
- T007
- T008
phase: Phase 2 - Documentation
history:
- at: '2026-11-03T13:20:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/
create_intent:
- docs/changelog/unreleased/7128-report-only-pinned-pack-inputs.fixed.md
execution_mode: planning_artifact
owned_files:
- docs/development/analysis-report-transactions.md
- docs/changelog/unreleased/7128-report-only-pinned-pack-inputs.fixed.md
role: implementer
tags: []
task_type: documentation
tracker_refs:
- '#7128'
---

# Work Package Prompt: WP02 – Operator docs and the per-PR changelog fragment

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `pi` (implementation sub-agent)

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete.

---

## Objectives & Success Criteria

An operator who hits this defect needs to know two things: that the fetched pack tree no longer
blocks `--report-only`, and what still does. This WP states that in the one page that owns the
subject, and records the change where this repository now records changes — a per-PR fragment under
`docs/changelog/unreleased/`.

Definition of Done:

- `docs/development/analysis-report-transactions.md` says, under "Material inputs", that a fetched
  `packs/<name>/` tree matching its committed pin is not a dirty input, and that a modified tree, a
  dirty pin, or any other untracked/ignored material input still refuses.
- `docs/changelog/unreleased/7128-report-only-pinned-pack-inputs.fixed.md` exists, is under 1,200
  characters, leads with the impact and `(#7128)`, and passes the changelog-style and spelling
  checks.
- `uv run --frozen python -m scripts.docs.check_docs_freshness --ci` reports `errors=0`.

## Context

- `kitty-specs/report-only-pinned-pack-inputs-01M6GRG8/spec.md` — FR-001..FR-006 and the acceptance
  scenarios are the source of truth for what the shipped behaviour is.
- `docs/changelog/unreleased/README.md` — fragment naming, sections, and the required entry shape.
  **Never** edit `docs/changelog/CHANGELOG.md`; it is assembled from these fragments.
- `docs/development/analysis-report-transactions.md` — the page to edit. It is `doc_status: draft`
  with a `related:` list; keep its frontmatter shape and update `updated:` to the day you write it.
- `docs/api/agent-subcommands.md` also mentions `--report-only`. It is a large reference page: only
  touch it if it states a rule this change makes wrong (it should not — the flag, its exit codes and
  its JSON keys do not change). If it needs no edit, say so in the WP history.

## Detailed Guidance

### T006 — One paragraph under "Material inputs"

Add after the existing "Material inputs" paragraph, in the same voice (present tense, no marketing,
no second person imperative):

- A fetched pack tree (`packs/<name>/`, placed by `make sync-packs`) is a material input, and its
  committed state is the pin in the tracked `packs/<name>.source.yaml`, not a blob in this
  repository.
- The transaction therefore treats a tree whose content verifies against that committed pin as
  clean; it still refuses when the tree no longer matches the pin, when the pin itself is
  uncommitted or missing, and for every other untracked or ignored material input.
- Say it once. Do not restate the pin format or the digest algorithm; link the concept, not the
  implementation.

Keep the page's US spelling and its existing wrapping style.

### T007 — The changelog fragment

`docs/changelog/unreleased/7128-report-only-pinned-pack-inputs.fixed.md`, one entry, the shape the
README pins:

```markdown
- **Lead with the operator-visible effect** (#7128). **Before:** … **After:** …
```

Requirements: impact first, `(#7128)`, before/after, under 1,200 characters, US spelling, no
heading line, no machine-local path. Name the file by issue + branch slug now; the operator run
renames it to `<pr>.fixed.md` once the pull request number exists.

### T008 — Checks

```bash
uv run --frozen python -m scripts.docs.check_changelog_style
uv run --frozen python -m scripts.docs.check_spelling --pass unreleased
uv run --frozen python -m scripts.docs.check_docs_freshness --ci
```

All three must pass for the touched surface. Do not regenerate the CLI reference or the docs index:
this diff changes no command surface and no indexed page inventory, and a full rebuild on this host
reads a cache other agents write concurrently.

## Branch Strategy

Planning artifacts for this mission were generated on `issue-7128-report-only-pinned-pack-inputs`.
Completed changes must merge back into that branch; never push `main`.

## Test Strategy

The checks in T008 are the test for this WP; there is no code path here. If a check fails for a
reason unrelated to this diff, prove it on a pristine `origin/main` checkout and report it — do not
edit the check.

## Definition of Done

- [ ] The Material-inputs paragraph states the exemption and the four remaining refusals.
- [ ] The fragment exists with the required shape and passes style + spelling.
- [ ] `check_docs_freshness --ci` reports `errors=0`.
- [ ] `docs/changelog/CHANGELOG.md` is unmodified.
- [ ] No generated index was rebuilt; no machine-local path in the diff.

## Risks & Mitigations

| Risk | Mitigation |
| --- | --- |
| Someone edits `CHANGELOG.md` by habit | The README and this prompt both forbid it; the review checks the diff |
| Docs over-promise (e.g. "ignored paths are fine now") | State exactly the four refusals; the wording mirrors spec.md FR-001..FR-004 |
| A docs-index rebuild races other agents on this host | Touch no indexed inventory; verify with `check_docs_freshness --ci` |

## Reviewer Guidance

- The page must not claim more than the code does: no "gitignored paths are ignored by the uncommitted-state rule".
- The fragment must be a fragment, not a `CHANGELOG.md` edit, and must stay under 1,200 characters.
- Check `updated:` on the edited page is the day of the change and the frontmatter shape is intact.
