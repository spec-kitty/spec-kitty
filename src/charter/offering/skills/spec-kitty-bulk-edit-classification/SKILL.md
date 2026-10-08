---
name: spec-kitty-bulk-edit-classification
description: >-
  Recognize when a mission is a bulk edit and drive the occurrence-classification
  guardrail on the user's behalf. Triggers: user says any variant of "rename X
  to Y", "change the terminology", "migrate all occurrences", "replace across
  the codebase", "the X feature is now the Y feature", "sed everywhere", or any
  request that touches the same identifier/path/key in many files. Also
  triggers on gate errors mentioning "change_mode", "occurrence_map.yaml",
  "Bulk Edit Gate: BLOCKED", or "Bulk Edit Review: Diff Compliance".
  Does NOT handle: line-level semantic refactors inside one file, adding a new
  feature that creates new identifiers without changing existing ones, or
  reviewing finished missions for fidelity.
---

# spec-kitty-bulk-edit-classification

Drive the occurrence-classification guardrail (shipped in #393, DIRECTIVE_035)
so users never have to know it exists. A bulk edit is any change that touches
the **same string** in many places — a rename, a terminology migration, a
package-path move, a feature-label swap. Those changes look mechanical but
aren't: the same token carries different meaning depending on where it appears
(code symbol, import path, filesystem literal, serialized key, CLI command,
user-facing string, test fixture, log/telemetry label). Treating them uniformly
is how silent breakage happens.

**The user will not say "bulk edit".** They will say "rename Coffee to Tea" or
"the Blue feature is now the Red feature." Your job is to recognize that
shape, turn on `change_mode: bulk_edit`, and drive the classification workflow
before any code changes.

---

## When to activate

Apply this skill during **specify** or **plan** when the user's description
matches any of these patterns:

| Pattern | Example phrasing |
|---|---|
| Explicit rename | "Rename `Customer` to `Account` across the codebase" |
| Terminology migration | "We're calling it 'channels' now, not 'streams'" |
| Feature relabel | "The Blue feature is now the Red feature" |
| Path/module move | "Move `src/legacy/auth` to `src/auth`" |
| API surface rename | "Rename the `/users` endpoint to `/accounts`" |
| Config key rename | "Change `max_connections` to `connection_limit` everywhere" |
| Brand / product rename | "Replace ACME with GlobalCorp in all docs and UI" |

Also apply when the implement or review command prints a message starting
with **"Bulk Edit Gate: BLOCKED"** or **"Bulk Edit Review: Diff Compliance"** —
these are the runtime gates' failure output; this skill tells you how to
respond.

**Do NOT apply when** the user is:

- Adding a genuinely new feature (new identifiers, new files) — no existing
  identifiers change
- Refactoring the internals of one file or one function — no cross-cutting
  string change
- Fixing a bug where the surface names stay the same

---

## The core decision tree

At the start of `specify` or `plan`, after you understand the user's intent,
ask yourself this one question:

> Does fulfilling this request require changing the **same existing string**
> (identifier, path, key, label) in more than one file?

If **yes**: this is a bulk edit. Set `change_mode: bulk_edit` and run the
classification workflow below.

If **no**: proceed normally. The guardrail stays dormant.

If **uncertain**: treat as bulk edit. The cost of a false positive is drafting
an occurrence map the user can approve in one pass. The cost of a false
negative is the silent-breakage class of bugs #393 was created to prevent.

---

## What to do during specify

1. **Detect intent.** Read the user's feature description. If it matches the
   patterns above, you have a bulk edit.

2. **Set `change_mode` in `meta.json`.** Use the CLI helper — do not hand-edit
   JSON:

   ```python
   from specify_cli.mission_metadata import locked_update_meta
   locked_update_meta(feature_dir, lambda meta: meta.update(change_mode="bulk_edit"))
   ```

   Or via shell after `mission create`:

   ```bash
   python -c "from pathlib import Path; from specify_cli.mission_metadata import locked_update_meta; \
              locked_update_meta(Path('<feature_dir>'), lambda meta: meta.update(change_mode='bulk_edit'))"
   ```

3. **Name the target in the spec.** In `spec.md`, state explicitly what's
   being renamed and to what:

   > "This mission renames `Customer` (old term) to `Account` (new term)
   > across the codebase, with per-category rules captured in
   > `occurrence_map.yaml`."

   Do NOT rely on the reviewer inferring the rename from prose. Make it an
   explicit claim that the occurrence map must satisfy.

4. **Tell the user, briefly**, that you're turning on the classification
   workflow. Use plain language — they don't need to know the field name:

   > "This is a cross-cutting rename, so I'm going to produce an
   > `occurrence_map.yaml` during planning that decides which kinds of
   > occurrences get renamed vs. left alone (API response keys, CLI commands,
   > and metric labels are typically left alone to avoid breaking consumers).
   > You'll review and approve that map before any code changes."

---

## What to do during plan

Produce `kitty-specs/<mission>/occurrence_map.yaml` with **all 8 standard
categories present**. Leaving a category out is an error the gate rejects —
every standard risk surface must have an explicit action assignment.

### The template to fill

The starter template lives in `src/charter/offering/templates/occurrence-map-template.yaml`
and the machine-enforced schema lives in `src/charter/offering/schemas/occurrence-map.schema.yaml`.
Do not copy the shape from prose — load the actual file so you never drift from
the contract that the runtime gate enforces:

```python
from specify_cli.bulk_edit.occurrence_map import (
    load_template_text,     # starter YAML text to seed occurrence_map.yaml
    load_schema,             # JSON Schema dict (Draft 2020-12)
    validate_against_schema, # raw dict -> ValidationResult
)

# Seed the file:
(feature_dir / "occurrence_map.yaml").write_text(load_template_text())
```

The template is a complete, syntactically valid occurrence map with sane
category defaults and placeholders only for `target.term`/`target.replacement`.
Adjust per-category actions to fit the mission, then validate:

```python
import yaml
from specify_cli.bulk_edit.occurrence_map import validate_against_schema

raw = yaml.safe_load((feature_dir / "occurrence_map.yaml").read_text())
result = validate_against_schema(raw)
assert result.valid, result.errors
```

### Valid actions (exact strings — the gate rejects typos)

| Action | When to use |
|---|---|
| `rename` | Safe to mechanically replace old → new |
| `manual_review` | Each occurrence needs case-by-case judgment |
| `do_not_change` | Must not be modified; renaming breaks external consumers |
| `rename_if_user_visible` | Rename where the string is shown to a user; preserve otherwise |

### Default posture per category

This is a starting point to propose to the user. Tune per-project.

| Category | Typical default | Why |
|---|---|---|
| `code_symbols` | `rename` | Internal implementation — safe to change |
| `import_paths` | `rename` | Must track symbol renames |
| `filesystem_paths` | `manual_review` | On-disk locations may be referenced externally |
| `serialized_keys` | `do_not_change` | API/schema/config keys are contracts |
| `cli_commands` | `do_not_change` | Users have scripts; need deprecation cycle |
| `user_facing_strings` | `rename_if_user_visible` | Rename in UI/docs, preserve internal labels |
| `tests_fixtures` | `rename` | Tests should reflect new terminology |
| `logs_telemetry` | `do_not_change` | Dashboards and alerts depend on exact label strings |

### Multi-path structural moves (the `moves:` block)

The eight categories classify a single-term rename. They cannot express a
**structural relocation** — moving one or more source paths to a single
destination (`src/legacy/auth/*` → `src/auth/`). For those, add an optional
top-level `moves:` block alongside the categories:

```yaml
moves:
  - from:
      - src/legacy/auth/login.py
      - src/legacy/auth/session.py
    to: src/auth
    reason: "Consolidate auth modules under the canonical package"
  - from:
      - docs/old-guide.md
    to: docs/guides/getting-started.md
    reason: "Relocate and rename the onboarding guide"
```

Rules for `moves:`:

- Each entry has a non-empty `from` list (one or more source paths) and a
  single `to` destination. `reason` is optional but recommended.
- Source and destination paths may be exact paths, globs (`*`/`**`), or a
  directory prefix (`to: src/auth` covers `src/auth/login.py`).
- A path that participates in a declared move is treated as a
  reviewer-approved relocation. At review time it is **exempt** from the
  `do_not_change` path heuristic — moving it is the whole point.
- The block is **optional**. A map with only the eight categories and no
  `moves:` validates and gates exactly as before — there is nothing new to
  fill in unless your mission actually relocates paths.

Use `moves:` when single-term renames cannot capture the change — for example
when a paused restructure could only be described as path-to-path mappings.
The categories still govern in-file string occurrences; `moves:` governs the
relocation of whole paths.

### Interviewing the user

The user knows the domain; you know the mechanics. For each category where the
default is not obviously right, ask one concrete question. Keep the
conversation short — for a typical rename, you need 2–4 questions.

Good question style:

> "The rename will touch `Customer` inside API response bodies — e.g.,
> `{\"customer_id\": ...}`. Changing those keys would break any client
> that has already integrated. I'd recommend keeping the JSON keys as
> `customer_id` (do_not_change) and only renaming the Python class. Sound
> right, or should we also do a versioned API migration?"

Bad question style:

> "What action should I set for serialized_keys?"
> — (jargon the user doesn't have)

---

## What to do when the gate blocks at implement time

If the user runs `spec-kitty agent action implement WP##` and sees a
**"Bulk Edit Gate: BLOCKED"** panel, this means either:

- the occurrence map is missing (the author never set `change_mode` or skipped
  planning), or
- it fails structural validation (malformed YAML, missing required sections), or
- it fails admissibility (placeholder target, < 3 categories, missing any of
  the 8 standard categories).

Read the error panel. It names the specific problem. Fix the map, save, rerun
the command. Do not use `--force` or any bypass.

## What to do when diff compliance blocks at review time

If you're reviewing a WP and the command rejects with **"Bulk Edit Review:
Diff Compliance Violations"**, read the table. Each row shows one changed
file, the category our path heuristic inferred, the action the map specified,
and the verdict. `BLOCK` rows are the ones you need to address.

Three remediations, in order of preference:

1. **Revert the offending change.** If the file genuinely shouldn't have been
   touched (API schema, metric labels, historical migration), the
   implementation is wrong. Revert, rebuild, resubmit.

2. **Narrow or add an exception** in the occurrence map. When the category
   rule is too coarse (e.g., `migrations/*.py: do_not_change` blocks the new
   migration that implements the rename), refine the exception and re-commit
   the map.

3. **Change the category rule.** Only when the original category-level
   decision was genuinely wrong. Requires reviewer + user agreement;
   document the reason in `exceptions[].reason`.

Never:

- Edit the diff check to skip files (the check is the contract).
- Use `git commit --no-verify`-style bypasses (the gate lives at review claim,
  not at commit).
- Silently work around by splitting into smaller WPs so each one stays under
  the radar. The map applies across the whole mission.

---

## Relationship to the inference warning

At `implement` time, if a mission is **not** marked `bulk_edit` but the spec
content matches rename/migration keywords, the system prints a
`Bulk Edit Inference Warning`. This is a nudge, not a block. If you see this
warning, treat it as a signal that **you (the agent) missed the detection
during specify/plan** and should have set `change_mode` earlier. Two options:

1. **Upgrade the mission.** Set `change_mode: bulk_edit`, draft the occurrence
   map, and ask the user to review before implementation resumes. This is
   usually the right call.

2. **Explicitly dismiss** only when you have read the spec and are certain
   this is NOT a bulk edit (e.g., the inference fired on a spec that happens
   to mention "rename" incidentally — "users can rename their own profile"
   describes a product feature, not a codebase rename). Pass
   `--acknowledge-not-bulk-edit` to proceed.

Dismissing carelessly defeats the guardrail. When in doubt, upgrade.

---

## Quick reference

| Question | Answer |
|---|---|
| Who decides to turn on bulk_edit? | The agent, during specify/plan. Users don't know this flag exists. |
| Where is it set? | `meta.json` via `locked_update_meta(feature_dir, lambda meta: meta.update(change_mode="bulk_edit"))`. |
| What artifact is required? | `kitty-specs/<mission>/occurrence_map.yaml` |
| How many categories must the map classify? | All 8 standard categories. |
| What blocks implement? | Missing, malformed, or inadmissible map. |
| What blocks review? | Any changed file classified into a `do_not_change` category, or any file matching no category and no exception. |
| How do I respond to a diff-check block? | Revert, refine exception, or (last resort) change category rule. |
| What if I'm not sure this is a bulk edit? | Treat as bulk edit. Cost of false positive is small. |

---

## Files you'll touch

| File | Role |
|---|---|
| `kitty-specs/<mission>/meta.json` | Set `change_mode: bulk_edit` |
| `kitty-specs/<mission>/occurrence_map.yaml` | The classification artifact (required) |
| `kitty-specs/<mission>/spec.md` | Name the rename target explicitly |
| `kitty-specs/<mission>/plan.md` | Note the classification workflow was run |

## Reference

The schema for `occurrence_map.yaml` — the required top-level `target:` block,
the eight categories, and the four-value `action` vocabulary
(`do_not_change`, `manual_review`, `rename`, `rename_if_user_visible`) — is
documented in [`docs/api/bulk-edit-gate.md`](../../../../docs/api/bulk-edit-gate.md).
Consult that file when:

- You need to look up exactly what an `action` value means.
- The gate prints `Bulk Edit Gate: BLOCKED` and the failure mode lists in
  this skill don't match the message verbatim.
- You're authoring a new `occurrence_map.yaml` and need the canonical
  category-to-action cookbook.

## Related skills

- `spec-kitty-runtime-next` — the loop that runs implement/review; this skill
  produces the prerequisites it checks.
- `spec-kitty-runtime-review` — the review workflow that invokes the diff
  compliance check this skill's artifact governs.
- `spec-kitty-glossary-context` — closely related for terminology normalization;
  the glossary tells you what the canonical terms are, this skill governs how
  you migrate *to* them.
