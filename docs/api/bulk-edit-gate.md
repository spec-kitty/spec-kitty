---
title: Bulk-edit gate reference
description: Reference schema for Spec Kitty bulk-edit gates. Learn how to configure occurrence_map.yaml for renaming operations, actions, and validation.
doc_status: active
updated: '2026-10-19'
---
# Bulk-edit gate reference

When a mission's `meta.json` declares `change_mode: bulk_edit`, the planning
phase MUST author `kitty-specs/<slug>/occurrence_map.yaml`. The bulk-edit
gate validates that file before `/spec-kitty.implement` can claim the first
WP workspace.

This document is the **schema reference** for that file. For a tour of the
workflow and the human-side decisions, see the
`spk-practice-bulk-edit` skill.

## Required schema

```yaml
schema_version: "1.0"
mission: <mission-slug>

target:
  term: "<the literal string being renamed>"
  operation: <rename | remove>
  replacement: "<the new literal string, or null if operation=remove>"

categories:
  code_symbols:
    action: <do_not_change | manual_review | rename | rename_if_user_visible>
    # optional per-category fields...
  import_paths:
    action: ...
  filesystem_paths:
    action: ...
  serialized_keys:
    action: ...
  cli_commands:
    action: ...
  user_facing_strings:
    action: ...
  tests_fixtures:
    action: ...
  logs_telemetry:
    action: ...

# Optional. Narrows a category verdict for specific files, or for a single
# field inside them.
exceptions:
- path: "<file path or glob>"
  action: <do_not_change | manual_review | rename | rename_if_user_visible>
  reason: "<why this path deviates from its category verdict>"
  # Optional. Dot-separated YAML field path, e.g. "specialization-context.languages".
  field_path: "<field>"
```

All eight categories MUST be present. Omitting a category fails the gate; it
is not a default-deny.

### `exceptions` (optional)

Each entry requires `path` and `action`; `reason` and `field_path` are
optional. No other keys are accepted.

`field_path` scopes an exception to **one field** inside the files matching
`path`, instead of overriding the whole file's verdict. It exists for the case
where a governed file carries both fields that must not change and fields that
must — for example an agent profile whose `directive-references` must stay
fixed while `specialization-context.languages` in the *same* file migrates.

When `field_path` is present the file's category-level action still governs the
whole file; the reviewer-facing diff check *additionally* records that this one
field is pinned to `action`. It is a review-surface annotation, not an
enforcement mechanism — mission B2 in particular must not read a
`do_not_change` here as enforcement.

Omitting `exceptions` entirely, or omitting `field_path` within an entry,
leaves legacy single-term maps validating unchanged.

## Top-level `target:` block

The `target:` block names the literal string being changed. It is required
when `operation: rename`; for `operation: remove` the `replacement` field
must be `null`. Both `term` and `replacement` are matched as **exact
strings**; word-boundary or case-insensitive matching is the agent's
responsibility per-category.

| Field | Type | Meaning |
|---|---|---|
| `term` | string | Old literal string. Required. |
| `operation` | enum | `rename` (term → replacement) or `remove` (term goes away). |
| `replacement` | string \| null | New literal string. `null` only when `operation: remove`. |

## Allowed `action` values

The bulk-edit gate recognises exactly **four** values for `action` per
category. Anything else fails the gate with `unknown_action`.

| Action | Meaning |
|---|---|
| `do_not_change` | Preserve as-is (historical text, dead-code-after-rename, snapshot artefacts, etc.). Files matched by this category MUST NOT be touched by the implementer. |
| `manual_review` | Implementer must inspect per-occurrence (e.g., dead-code that should be deleted, not renamed). The runtime does not auto-rename; the WP must add an explicit per-file decision and evidence. |
| `rename` | Mechanical `s/old/new/` across the matched files. The implementer applies the substitution; the review gate verifies no instances of `term` survive in renamed files. |
| `rename_if_user_visible` | Rename only on public CLI surfaces / JSON keys / docs; preserve in internal text. The category-level rule typically encodes which sub-shapes count as "user visible". |

## Category cookbook

The eight categories cover the standard surfaces touched by a rename. The
table below is the canonical mapping; deviating from it requires an explicit
per-mission exception with rationale captured in `plan.md`.

| Category | Typical action | Why |
|---|---|---|
| `code_symbols` | `rename` | Class / function / variable identifiers — purely internal. |
| `import_paths` | `rename` | Follows from `code_symbols`. |
| `filesystem_paths` | `rename` | Module/package paths follow `code_symbols`. |
| `serialized_keys` | `rename_if_user_visible` | JSON/YAML keys leaving the process boundary need renaming; in-memory dict keys often do not. |
| `cli_commands` | `rename_if_user_visible` | User-typed surface — rename, but keep deprecated aliases per the agent's policy. |
| `user_facing_strings` | `rename_if_user_visible` | Docs, help text, error messages. |
| `tests_fixtures` | `manual_review` | Fixtures may encode the OLD name on purpose (regression captures) — review per-occurrence. |
| `logs_telemetry` | `do_not_change` | Renaming log keys breaks downstream dashboards; keep the wire format stable unless explicitly versioned. |

## Failure modes the gate detects

1. `change_mode: bulk_edit` set, but `occurrence_map.yaml` missing.
2. `occurrence_map.yaml` present, but `target:` block missing or malformed.
3. `target.operation: rename` but `replacement` is `null`.
4. `target.operation: remove` but `replacement` is non-null.
5. Fewer than eight categories declared.
6. Any category with an `action` outside the four-value vocabulary.
7. (review phase) A file the diff **modified, deleted or renamed** matches a
   category whose action is `do_not_change`, or matches no category at all
   (FR-008), with no per-file exception. A file the diff **created** is not
   judged against the map — see the next section.

Each failure prints a structured error starting with
`Bulk Edit Gate: BLOCKED:` (planning gate) or
`Bulk Edit Review: Diff Compliance:` (post-implementation gate). The triggering message also activates the
`spk-practice-bulk-edit` skill, which walks the agent through
remediation.

## What the review gate exempts

The review-phase check reads `git diff --name-status`, so it knows whether a
path was created, modified, deleted or renamed. An occurrence map governs
occurrences in content that **already exists**, which is why these cases pass
without an exception. Every exemption is reported as a note, never silently.

| Case | Verdict | Why |
|---|---|---|
| File **created** by the diff (`A`) | pass, listed as *created by this diff* | No pre-existing occurrence for the map to protect. Deletions and renames are still judged; an unknown status is treated as a modification. Creating a file under **another** mission's `kitty-specs/<slug>/` still blocks (C-004). |
| The mission's **own** runtime state (`status.json`, `status.events.jsonl`, lifecycle logs) | pass, listed as *own bookkeeping* | Written by spec-kitty itself during the review. Anchored on the canonical `kitty-specs/<slug>` whatever worktree the mission's `feature_dir` resolves to, and tested **before** the map's exceptions, so `kitty-specs/**: do_not_change` cannot pre-empt it. |
| Files that **cannot carry a textual occurrence**: webfonts, raster images, audio/video, compiled objects, generated lockfiles the diff **creates** (`Gemfile.lock`, `uv.lock`, `yarn.lock`, …), `.keep`/`.gitkeep` | pass, listed as *no occurrences* | Not text, or resolver output regenerated rather than edited. A lockfile the diff **edits** is not exempt, because an edit can rename a package. `.svg` is not exempt either: it is XML text and carries ids and classes. Opaque **data** files (`.dat`, `.bin`, `.db`, `.sqlite`, `.pkl`, archives) are deliberately **not** exempt: they can carry serialized keys, so they block as unclassified until the map names them. |

An explicit `exceptions:` entry always wins over the last row: a reviewer who
names a binary keeps whatever action they chose.

Two behaviours are deliberate, so plan your map around them:

- **Creating a file is exempt even under a protected path.** A file the work
  package creates passes even when an explicit `do_not_change` category,
  path or exception covers it. This gate cannot forbid creating files in a
  protected tree; it only judges edits, deletions and renames there.
- **Own bookkeeping outranks the map's exceptions.** The mission's own
  `notes.md` and `review-cycle-*.md` files, under the mission's own
  directory, are exempt before the map's exceptions are consulted. An
  exception such as `kitty-specs/**: do_not_change` does not block them.

Templates, stylesheets and build DSLs (`.erb`, `.haml`, `.slim`, `.heex`,
`.vue`, `.svelte`, `.css`, `.scss`, `.rake`, `Rakefile`, `Gemfile`,
`.gemspec`) classify as `code_symbols`; container recipes (`Dockerfile`,
`Containerfile`, compose files) classify as `filesystem_paths`. A template
under `docs/` still reads as `user_facing_strings`.

When the check fails, the table lists the rows that block or ask for manual
review and summarises the rest by the reason they passed. When it passes with
notes, the notes are grouped by kind, judgement-first: paths needing manual
review and structural-target bypasses are listed in full; created files,
non-occurrence files and own bookkeeping are shown as a count plus a sample.

## See also

- The skill `spk-practice-bulk-edit` (loaded automatically when
  `meta.json` declares `change_mode: bulk_edit`).
- Existing missions that exercised this gate:
  `kitty-specs/charter-ux-and-org-pack-vocabulary-01KSAF14/occurrence_map.yaml`,
  `kitty-specs/release-3-2-0a5-tranche-1-01KQ7YXH/occurrence_map.yaml`.
