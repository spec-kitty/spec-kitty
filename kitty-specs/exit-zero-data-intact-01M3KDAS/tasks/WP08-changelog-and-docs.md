---
work_package_id: WP08
title: Changelog and documentation closeout
dependencies:
- WP01
- WP02
- WP03
- WP04
- WP05
- WP06
- WP07
requirement_refs:
- NFR-003
planning_base_branch: claude/milestone-11-research-0rnnr4
merge_target_branch: claude/milestone-11-research-0rnnr4
branch_strategy: Planning artifacts for this mission were generated on claude/milestone-11-research-0rnnr4. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/milestone-11-research-0rnnr4 unless the human explicitly redirects the landing branch.
subtasks:
- T040
- T041
- T042
phase: Phase 4 - Closeout
history:
- at: '2026-09-28T09:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: docs/changelog/CHANGELOG.md
create_intent: []
execution_mode: planning_artifact
model: claude-sonnet-5
owned_files:
- docs/changelog/CHANGELOG.md
- docs/guides/**
- docs/api/**
- docs/development/3-2-docs-retrieval-index.yaml
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP08 – Changelog and documentation closeout

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` via `/ad-hoc-profile-load` (role `implementer`, agent `claude`); then `spec-kitty charter context --action implement --json`. Apply the writing doctrine (audience-oriented writing, DIRECTIVE_047) and the terminology canon (Mission; "local lane consolidation (`spec-kitty consolidate`)", never bare "merge").

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Feedback items are your TODO list.

---

## Objectives & Success Criteria

Record the six user-visible fixes and update docs for every changed documented contract (C-007, NFR-003). Runs after WP01–WP07 are approved, so describe what actually landed (read each WP's Activity Log and diff; don't paraphrase the plan).

Done means:
- One `[Unreleased]` entry in `docs/changelog/CHANGELOG.md` (the root `CHANGELOG.md` is a symlink to it) following the house style: bold impact-first lead naming the issues `(#4919, #4900, #4933, #4940, #4998, #4964)`, then **Before:** / **After:** per issue, mission slug `exit-zero-data-intact-01M3KDAS`, and "Bug-fix; no CLI version bump."
- Docs updated wherever they describe: `doctor decisions` always exiting 0 (now: `--repair` exits 1 when a decision can't be reconciled), `.claude/settings.json` handling by `agent config sync --sync-hooks` / `live-work install` (undecodable file → refused untouched, re-save as UTF-8; non-UTF-8 provable encodings → merged with a byte backup), and `migrate` group flags (forwarded or usage error).
- Docs index/freshness checks pass; terminology guard passes.

## Context & Constraints

- Owned: `docs/changelog/CHANGELOG.md`, `docs/guides/**` (incl. `docs/guides/how-to/harnesses/setup-lint-hooks.md`), `docs/api/**` (`cli-commands.md`, `agent-subcommands.md`), the docs retrieval index. If a doc that needs updating lives elsewhere under `docs/`, edit it and record a one-line rationale in the Activity Log (ownership-map leeway; no other WP touches docs).
- Find affected docs: `grep -rn "doctor decisions\|sync-hooks\|settings.json\|migrate --dry-run\|mission_number" docs --include=*.md | grep -v changelog`.
- Keep the entry factual and short relative to neighbours (see recent entries at the top of `[Unreleased]`).

## Branch Strategy

- **Strategy**: lanes · **Planning base**: `claude/milestone-11-research-0rnnr4` · **Merge target**: `claude/milestone-11-research-0rnnr4`. `spec-kitty implement WP08` after WP01–WP07.

## Subtasks & Detailed Guidance

### Subtask T040 – CHANGELOG entry

- One bullet under `[Unreleased]` (Fixed/equivalent section used by neighbours). Lead: "**Six commands no longer exit 0 while losing or mis-recording your data** (mission `exit-zero-data-intact-01M3KDAS`; #4919, #4900, #4933, #4940, #4998, #4964)." Then one Before/After sentence pair per issue, using the real behaviour from the WPs (exit codes, backup naming, anchor rule, UTF-32 correction in `recover()` as a side note).

### Subtask T041 – Docs for changed contracts

- Update each doc found by the grep; add a short troubleshooting note for "settings.json is not valid UTF-8" (how to re-save as UTF-8) where agent config / live-work are documented.

### Subtask T042 – Index, freshness, terminology

```bash
uv run --frozen python scripts/docs/docs_index.py --write   # only if a new doc page was added
uv run --frozen python scripts/docs/check_docs_freshness.py --ci   # errors must be 0
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
```

Record commands and results in the Activity Log.

## Review Guidance

- Entry matches what landed (spot-check against WP diffs); issues cited; no "merge" where `consolidate` is meant.
- Docs freshness 0 errors; terminology guard green.

## Activity Log

- 2026-09-28T09:40:00Z – system – Prompt created.
- 2026-09-28T12:00:00Z – claude (python-pedro, implementer) – Verified the six fixes against the real diff (`git diff 45785d2d..HEAD --stat -- src/`) and each WP file/review record rather than paraphrasing the plan: #4919 (`_decisions_doctor.py`/`index_fold.py` — order-independent fold, `malformed_folds`/`status_mismatch` on every run, `--repair` raises `typer.Exit(1)` when `report.malformed_folds`); #4900 (new `consolidation/mission_number.py::is_assigned_mission_number`, unconditional target-tree write, `Assigned` line printed only after `baseline._read_committed_meta_json` read-back verifies, `MissionNumberVerificationError` → `Error:` → exit 1); #4933 (`coherence.py` depth-exact `owned_mission_meta`/`legacy_kittify_meta` regexes replacing the basename-only exemption; `executor.py::_report_pre_mutation_refusal` gates the reset-to-HEAD guidance on `is_pure_behind_head_lag`, not classification alone); #4940 (new `kernel.text_decode.decode_unambiguous`/`normalize_newlines`; `SettingsNotDecodableError` in `claude_code_hook.py`; `backup_before_overwrite` sidecar named `<path>.<timestamp>`; `charter.encoding_recovery._recover_from_bom` now delegates to the shared UTF-32-before-UTF-16 BOM table); #4998 (`skills/command_renderer.py` normalises newlines right after decode in both `ensure_skill_frontmatter` and `render`; `.gitattributes` pins `src/charter/offering/skills/**` and `packs/built-in/missions/mission-steps/**` to `eol=lf`); #4964 (`migrate_cmd.py::_forward_or_refuse_group_flags` forwards a group flag via `ctx.default_map` when the subcommand declares it, else `click.UsageError` exit 2).
- 2026-09-28T12:05:00Z – claude (python-pedro, implementer) – T040: added one `[Unreleased] - 4.0.0rc5` → `### Fixed` bullet to `docs/changelog/CHANGELOG.md` (root `CHANGELOG.md` is a symlink to it) — impact-first lead naming all six issues, one Before:/After: pair per issue using the verified real behaviour above, mission slug `exit-zero-data-intact-01M3KDAS`, "Bug-fix; no CLI version bump." Bumped the file's `updated:` frontmatter to `2026-09-28`.
- 2026-09-28T12:10:00Z – claude (python-pedro, implementer) – T041: `grep -rn "doctor decisions\|sync-hooks\|settings.json\|migrate --dry-run\|mission_number" docs --include=*.md | grep -v changelog` found doc hits outside owned files were plans/ADR/architecture history, not live contract docs — left untouched. Updated the two live contract surfaces: (1) `docs/api/cli-commands.md` — captured live `--help` via `PYTHONPATH=/home/user/spec-kitty/src .venv/bin/spec-kitty doctor decisions --help` and `... migrate --help` (no `uv run`, per env rules) and hand-synced the `## spec-kitty doctor decisions` docstring body and the `## spec-kitty migrate` group's `--dry-run`/`--verbose`/`--force` option help text to match exactly; bumped `updated:` to `2026-09-28`. (2) `docs/guides/how-to/harnesses/setup-lint-hooks.md` — added a `## Troubleshooting` section: "`.claude/settings.json` is not valid UTF-8" (provable-encoding-only decode, byte-identical refusal + re-save-as-UTF-8 remedy for `agent config sync --sync-hooks` and `live-work install`, and the `<path>.<timestamp>` backup sidecar for a provable non-UTF-8 file); bumped `updated:` to `2026-09-28`. No new page added, so `docs_index.py --write` was not required for a new-page reason, but was still run after the section edit because it changed that page's anchors (see T042).
- 2026-09-28T12:20:00Z – claude (python-pedro, implementer) – T042: `PYTHONPATH=/home/user/spec-kitty/src:/home/user/spec-kitty .venv/bin/python scripts/docs/check_docs_freshness.py --ci` first failed with one blocking `ERROR DOCS-INDEX-DRIFT docs/guides/how-to/harnesses/setup-lint-hooks.md` (the new Troubleshooting section's anchors were not yet in the committed retrieval index) plus pre-existing warnings (unrelated `moments drain` HELP-DRIFT bracket-escaping, and `LINK-HEALTH` 403s from the sandboxed proxy on external URLs). Ran `PYTHONPATH=/home/user/spec-kitty/src:/home/user/spec-kitty .venv/bin/python scripts/docs/docs_index.py --write` → `generated=832 committed=832 drift=False (added=0 removed=0 changed=0)` after write (diff limited to the 2 new anchors for the Troubleshooting section). Re-ran `check_docs_freshness.py --ci` → `exit=0 findings=28 errors=0 warnings=28` (all 28 the same pre-existing HELP-DRIFT/LINK-HEALTH warnings, unrelated to this WP; 0 errors). Ran `PYTHONPATH=/home/user/spec-kitty/src .venv/bin/python -m pytest -p no:cacheprovider tests/architectural/test_no_legacy_terminology.py -q` → `96 passed in 116.62s`. Also ran the targeted docs-changelog gate files found via `grep -rl "CHANGELOG" tests --include=*.py`: `pytest tests/docs/test_sync_changelog.py tests/release/test_validate_changelog_entry.py -q` → `19 passed in 0.82s`.
