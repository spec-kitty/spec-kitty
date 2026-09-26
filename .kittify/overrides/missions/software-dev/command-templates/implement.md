---
description: Execute a work package implementation
---
# /spec-kitty.implement - Execute Work Package Implementation

**Version**: 0.12.0+

<!-- spdd:reasons-block:start -->

### REASONS Guidance — Implement WP<id>

Before coding, load the WP-scoped REASONS section from
`kitty-specs/<mission>/reasons-canvas.md`:

- Requirements (WP-scoped)
- Entities (WP-relevant)
- Approach (chosen strategy for this WP)
- Structure (files this WP owns)
- Operations (ordered steps)
- Norms (testing, observability, style)
- Safeguards (hard constraints — what not to break)

If the canvas is missing, invoke the `spec-kitty-spdd-reasons` skill to
generate it before continuing.

Do not invent files, entities, or scope outside the canvas without recording a
deviation.

<!-- spdd:reasons-block:end -->

## Purpose

Execute the implementation of a work package according to its prompt file.
Follow TDD practices, respect file ownership boundaries, and apply safety
guardrails for bulk operations.

---

## Working Directory

**IMPORTANT**: This step works inside the execution workspace (worktree)
allocated by `spec-kitty agent action implement WPxx --agent <name>`. Prefer to stay within
your `owned_files` boundaries. If a small, well-justified change to a file outside the map is
genuinely needed to deliver the WP (e.g. a one-line prerequisite or a stale assertion that
pins a now-deleted internal), make it and record a one-line rationale in the commit message —
that is better than a convoluted in-bounds workaround or a duplicated local re-implementation.
The finalize ownership-overlap gate remains the guard against *parallel* WPs colliding on the
same file.

**In repos with multiple missions, always pass `--mission <handle>` to every spec-kitty command.** The `<handle>` can be the mission's `mission_id` (ULID), `mid8` (first 8 chars of the ULID), or `mission_slug`. The resolver disambiguates by `mission_id` and returns a structured `MISSION_AMBIGUOUS_SELECTOR` error on ambiguity — there is no silent fallback.

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding (if not empty).

## Governance Payload Contract

The prompt produced by `spec-kitty agent action implement` is guaranteed to
carry the following surfaces. Trust the prompt; do not consult external
governance sources unless explicitly cited by a fetch command + when-doing
rule in the prompt.

**Guaranteed bodies** (verbatim in the prompt when under the token budget; the
resolver substitutes a `spec-kitty charter context --include section:<slug>`
fetch + when-doing stanza only when the budget would otherwise be exceeded):

- **Terminology Canon** — from `.kittify/charter/charter.md` — governs every
  identifier rename or new term you introduce.
- **Code Review Checklist** — from `.kittify/charter/charter.md` — enumerates
  the gates the reviewer will measure your diff against.
- **Regression Vigilance** — from `.kittify/charter/charter.md` — the project's
  explicit guard against terminology and structural drift.
- Any additional action-critical sections the mission declares are appended
  automatically.

**Guaranteed citations** (catalog IDs always present in the prompt when the
WP frontmatter selects an `agent_profile`):

- Every `DIRECTIVE_NNN` declared in the loaded agent profile's
  `directive-references` list (for example, `python-pedro` cites
  `DIRECTIVE_010` — Specification Fidelity Requirement, `DIRECTIVE_024` —
  Locality of Change, `DIRECTIVE_030` — Test and Typecheck Quality Gate).
- Every tactic-id declared in the loaded agent profile's `tactic-references`
  list.

**Guaranteed authority pointers** (path + when-doing conditional):

- `docs/context/` — canonical terminology. Consult when you encounter a
  domain term in the diff or are about to introduce a new one.
- `docs/adr/3.x/` — architectural intent. Consult when you change a
  structural boundary (package layout, public API surface, dependency edges).
- Any additional paths declared in the charter's `authority_paths:` block are
  emitted alongside these defaults.

**Fetch commands** (the prompt may substitute these for bodies that exceed the
token budget; whenever a fetch command appears, the accompanying
"When you <verb>, run this and apply" line specifies the trigger):

- `spec-kitty charter context --include directive:DIRECTIVE_NNN`
- `spec-kitty charter context --include tactic:<id>`
- `spec-kitty charter context --include section:<slug>`

## Execution Steps

### 1. Setup

Run:

```bash
spec-kitty agent context resolve --action implement --mission <handle> --json
```

Then execute the returned `check_prerequisites` command and capture
`feature_dir`. All paths must be absolute.

The output of `spec-kitty agent action implement ...` is the authoritative work
package prompt and execution context. Do **not** separately call
`spec-kitty charter context` or rummage through unrelated files looking for a
"newer" prompt unless the command output tells you to. The
**Governance Payload Contract** section above documents what the prompt is
guaranteed to carry.

### 2. Load Work Package Prompt

Read the WP prompt file from `feature_dir/tasks/WPxx-slug.md`.
Parse frontmatter for:
- `owned_files` -- prefer to modify files matching these globs; out-of-map edits are allowed when small and well-justified (record a one-line rationale)
- `authoritative_surface` -- primary directory for this WP
- `execution_mode` -- `code_change` or `planning_artifact`
- `subtasks` -- ordered list of subtask IDs
- `dependencies` -- WPs that must be done first
- `agent_profile` -- agent profile identifier to load (e.g., `implementer-ivan`)
- `role` -- role within the profile (e.g., `implementer`)
- `agent` -- CLI agent/tool identifier (e.g., `claude`, `codex`)
- `model` -- optional model override (e.g., `claude-sonnet-4-6`)

### 2a. Load Agent Profile

Before proceeding, load the agent profile from the WP frontmatter using the `/ad-hoc-profile-load` skill (or `spec-kitty agent profile list` to find user-defined profiles). Apply the profile's guidance for the rest of this implementation session.

If `agent_profile` is empty, run `spec-kitty agent profile list` and select the best
available profile for the WP's `task_type` and `authoritative_surface`.

### 3. Verify Dependencies

Confirm all dependency WPs are in `approved` or `done` status before proceeding.
If any are not approved or done, stop and report which dependencies are blocking.

### 4. Implement Subtasks

Work through each subtask in order:
1. Read the subtask guidance from the WP prompt
2. Write tests first (TDD) when the subtask involves code changes
3. Implement the code to pass the tests
4. Verify tests pass before moving to the next subtask

### 4a. Supply-Chain Security Check (dependency changes)

If this WP adds, upgrades, or removes a dependency (any ecosystem — npm/yarn/pnpm, pip/uv, Maven/Gradle, etc.), run the `supply-chain-install-safety` tactic checklist before the quality gate — this mirrors the `supply_chain_security_check` step already present in the `implement` step contract:

- **Registry authenticity**: confirm the resolved package/version comes from the approved official registry, not an unexpected mirror or namespace.
- **Package freshness**: record first-publish/latest-publish timestamps; flag a suspiciously new version for operator acknowledgment instead of accepting it silently.
- **Lifecycle-script discipline (deny-by-default)**: never auto-approve `preinstall`/`install`/`postinstall` scripts. If a legitimate native build genuinely needs one, add an explicit, justified allowlist entry — never a blanket script-safety bypass.
- **Node Active LTS awareness**: check the project's declared/runtime Node version against current Active LTS; disclose any skew with a documented rationale rather than leaving it unacknowledged.
- **Risk disclosure**: record what was checked and the resulting decision (per the `051-supply-chain-install-safety` directive) in the WP implementation notes or commit message, so a reviewer does not have to re-derive the analysis.

This is advisory in v1 — it does not add a new fail-closed gate — but skipping the checklist for a dependency change is a gap the reviewer will flag, not a neutral outcome.

### 5. Self-Check

After all subtasks are complete:
- All tests pass
- Any files modified outside `owned_files` are small, justified, and have a one-line rationale in the commit message
- Code follows project conventions (run linter if configured)
- **Diff-scoped ruff sweep (MANDATORY before moving to `for_review`)** —
  catches lint regressions before they reach the cycle-1 reviewer. The WP06
  cycle-1 `textwrap` F401 in `tests/specify_cli/doctrine/test_missing_pack_policy.py`
  would have been caught by this step. Scope is the diff only so the implementer
  does not drown in pre-existing warnings owned by other WPs.
  ```bash
  CHANGED_PY=$(git diff --name-only --diff-filter=AMR HEAD | grep -E '[.]py$' || true)
  if [ -n "$CHANGED_PY" ]; then
    .venv/bin/ruff check $CHANGED_PY
  fi
  ```
  - The command MUST exit 0. If it does not, fix or `ruff check --fix` and re-run.
  - Paste the final command + exit code into your handoff note
    (e.g. `"ruff diff-scoped check: 0 issues, exit 0"`).
  - On cycle-N re-implementation, diff against the WP's planning base instead
    of `HEAD`: `git diff --name-only $(git merge-base HEAD main)`.

---

## Bulk Edit Occurrence Classification

If this mission has `change_mode: bulk_edit` in its `meta.json`, an occurrence
classification artifact is required before implementation can begin.

**What to check**:
1. Read `meta.json` in the feature directory — look for `"change_mode": "bulk_edit"`
2. If present, verify `occurrence_map.yaml` exists in the same directory
3. The occurrence map classifies the target term by semantic category with
   per-category actions: `rename`, `manual_review`, `do_not_change`, `rename_if_user_visible`

**During implementation**:
- Consult the occurrence map before modifying any file
- Respect category actions: do NOT modify occurrences in categories marked `do_not_change`
- For `manual_review` categories, document your decision in the WP review notes
- For `rename_if_user_visible`, only change user-facing text (docs, UI, error messages)
- Check the `exceptions` section for files/patterns with overriding rules

**If the gate blocks you**:
The system will refuse to start implementation if the occurrence map is missing or
incomplete. Create `occurrence_map.yaml` following the schema with `target`, `categories`
(3+ with actions), and optionally `exceptions`. Re-run the implement command.

**If an inference warning fires**:
The system may warn that spec content looks like a bulk edit even without `change_mode` set.
Either set `change_mode: "bulk_edit"` in meta.json, or re-run with `--acknowledge-not-bulk-edit`.

---

## Bulk Edit Safety

**WHEN THIS APPLIES**: Any work package that performs bulk renaming, terminology
cutover, or mass find-and-replace across multiple files. If your WP does NOT
involve bulk text replacement, skip this section.

### Pre-Edit: Occurrence Classification

Before performing bulk renames or term replacements:

1. **Search** the codebase for ALL occurrences of the target term:
   ```bash
   grep -rn "target_term" src/ tests/ docs/ --include="*.py" --include="*.md" --include="*.yaml" --include="*.json"
   ```

2. **Classify** each occurrence into one of these categories:

   | Category | Example Pattern | Typical Action |
   |----------|----------------|----------------|
   | `import_path` | `from module.old_name import` | RENAME |
   | `class_name` | `class OldName:` | RENAME |
   | `function_name` | `def old_name():` | RENAME |
   | `variable` | `old_name = ...` | RENAME |
   | `dict_key` | `"old_name": value` | RENAME |
   | `file_path` | `src/old_name/` | RENAME (with filesystem move) |
   | `config_value` | `setting: old_name` | RENAME |
   | `log_message` | `log("Processing old_name")` | UPDATE (human-readable) |
   | `comment` | `# old_name does X` | UPDATE |
   | `documentation` | `The old_name module...` | UPDATE |
   | `test_fixture` | `test_old_name_works` | RENAME |
   | `external_ref` | URL or external API name | PRESERVE |

3. **Produce a classification report** as a markdown table in the WP
   implementation notes. Example:

   | File | Line | Occurrence | Category | Action |
   |------|------|-----------|----------|--------|
   | `src/foo.py` | 12 | `from old_name import` | `import_path` | RENAME |
   | `docs/api.md` | 45 | `The old_name module` | `documentation` | UPDATE |
   | `src/config.yaml` | 8 | `endpoint: https://api.old_name.com` | `external_ref` | PRESERVE |

4. **Get classification confirmed** before proceeding with edits.

5. **Apply edits category by category**, verifying each category independently.

### Post-Edit: Verification

After completing bulk renames:

1. **Search for remaining occurrences** of the old term:
   ```bash
   grep -rn "old_term" src/ tests/ docs/ --include="*.py" --include="*.md" --include="*.yaml" --include="*.json"
   ```

2. **For each remaining occurrence**, classify it:
   - **Intentional preservation**: Document why it was kept (e.g., external API name, backward compat)
   - **Missed rename**: Fix it
   - **New occurrence**: Introduced by parallel work -- rename if appropriate

3. **Search command template and agent directories** explicitly:
   ```bash
   grep -rn "old_term" src/specify_cli/missions/*/command-templates/
   grep -rn "old_term" .claude/commands/ .agents/skills/ .opencode/command/
   grep -rn "old_term" .github/prompts/ .gemini/commands/ .cursor/commands/
   grep -rn "old_term" .qwen/commands/ .kilocode/workflows/ .windsurf/workflows/
   grep -rn "old_term" .augment/commands/ .roo/commands/ .amazonq/prompts/
   ```

4. **Produce a verification report**:
   - Total occurrences found: N
   - Intentionally preserved: M (with reasons for each)
   - Missed renames fixed: K
   - Template directories checked: yes/no
   - Agent directories checked: yes/no
   - Doc directories checked: yes/no

---

### 6. Prepare for Review Hand-off

Before moving this WP to `for_review`, update the `agent_profile` field in the WP
prompt frontmatter to a reviewer profile so the reviewing agent loads the correct
persona automatically.

1. Identify the appropriate reviewer profile:
   ```bash
   spec-kitty agent profile list --json | grep reviewer
   ```
   The default reviewer profile is `reviewer-renata`. Use it unless the mission or
   charter specifies a different reviewer.

2. Update the WP frontmatter:
   ```yaml
   agent_profile: "reviewer-renata"
   role: "reviewer"
   ```

3. Commit the updated frontmatter together with your implementation changes **before**
   running `spec-kitty agent tasks move-task WPxx --to for_review`.

### GitHub Actions Workflow Changes

If this WP adds or modifies `.github/workflows/*`, use a draft PR before review hand-off:

1. Push the WP branch.
2. Open a draft PR so the workflow runs on a real GitHub Actions runner.
3. Iterate on the draft PR until the changed workflow has a successful run.
4. Record the successful run ID or Actions URL in `kitty-specs/<mission>/workflow-evidence.md`.
5. Only then move the WP to `for_review`.

The reviewer will then use `/ad-hoc-profile-load` with the reviewer profile and apply
its self-review gates automatically.

---

## Output

After completing implementation:
- All subtasks done with passing tests
- Bulk edit classification and verification reports (if applicable)
- Commit changes with a descriptive message

**Next step**: `spec-kitty next --agent <name>` will advance to review.
