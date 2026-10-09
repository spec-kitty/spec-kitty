---
title: Bulk-edit gate reference
description: Reference schema for Spec Kitty bulk-edit gates. Learn how to configure occurrence_map.yaml for renaming operations, actions, and validation.
doc_status: active
updated: '2026-06-09'
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
7. (review phase) A changed file matches a category whose action is
   `do_not_change`, with no per-file exception.

Each failure prints a structured error starting with
`Bulk Edit Gate: BLOCKED:` (planning gate) or
`Bulk Edit Review: Diff Compliance:` (post-implementation gate). The triggering message also activates the
`spk-practice-bulk-edit` skill, which walks the agent through
remediation.

## See also

- The skill `spk-practice-bulk-edit` (loaded automatically when
  `meta.json` declares `change_mode: bulk_edit`).
- Existing missions that exercised this gate:
  `kitty-specs/charter-ux-and-org-pack-vocabulary-01KSAF14/occurrence_map.yaml`,
  `kitty-specs/release-3-2-0a5-tranche-1-01KQ7YXH/occurrence_map.yaml`.
