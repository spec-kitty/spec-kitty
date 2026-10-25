---
work_package_id: WP06
title: Fabricated-identity doctor finding
dependencies: []
requirement_refs:
- FR-010
- FR-011
- FR-012
- NFR-002
- C-001
planning_base_branch: fix/residue-safe-migration-sweep
merge_target_branch: fix/residue-safe-migration-sweep
branch_strategy: Planning artifacts for this mission were generated on fix/residue-safe-migration-sweep. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/residue-safe-migration-sweep unless the human explicitly redirects the landing branch.
subtasks:
- T023
- T024
- T025
- T026
phase: Phase 3 - Audit
history:
- at: '2026-10-25T15:55:03Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/audit/
create_intent:
- src/specify_cli/audit/classifiers/fabricated_identity.py
- tests/audit/test_fabricated_identity_finding.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/upgrade/feature_meta.py
- src/specify_cli/audit/classifiers/fabricated_identity.py
- src/specify_cli/audit/models.py
- src/specify_cli/audit/engine.py
- tests/audit/test_fabricated_identity_finding.py
- tests/audit/test_residue_directory_finding.py
- tests/upgrade/test_feature_meta.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Fabricated-identity doctor finding

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

- `spec-kitty doctor mission-state --audit` reports `FABRICATED_IDENTITY_SUSPECTED`, severity **WARNING**, outside `TEAMSPACE_BLOCKER_CODES`, with `artifact_path="meta.json"`. It fires for a folder only when all three signals hold (FR-010):
  1. `meta.json` is git-tracked, and the folder holds nothing outside the allow-list `{meta.json, status.json, status.events.jsonl, decisions/**, *.lock}`.
  2. `meta.json`'s slug-derived fields equal `baseline_slug_fields(slug)`. Blank means `""`, `null` or absent; a numeric slug prefix matches as text (`"007"`) or int (`7`).
  3. `mission_runtime.identity.mid8_from_slug(slug)` is non-empty and differs from `mission_id[:8]`. Do **not** use `resolve_mid8`, which always returns the declared prefix.
- The detail lists the three matched signals and the remedy ("remove this folder's meta.json and status.json in a commit"), with no run-varying values. Nothing is written or deleted (FR-011, C-001).
- Thresholds: the finding does not fail `--fail-on teamspace-blocker` or `--fail-on error`, and it does fail `--fail-on warning` (FR-011).
- One owner for the baseline shape: `baseline_slug_fields()` in `upgrade/feature_meta.py`, used by `build_baseline_feature_meta` and by the classifier (FR-012).
- `RESIDUE_DIRECTORY`'s detail gives a remedy that works. It currently points at `migrate backfill-identity`, which needs `meta.json`. The new text: "add a spec.md or meta.json to make it a Mission, or remove the folder" (spec Edge Cases).
- 0 findings across this repository's `kitty-specs/` (NFR-002).
- Requirement refs: FR-010, FR-011, FR-012, NFR-002, C-001.

## Context & Constraints

- The audit engine is `src/specify_cli/audit/engine.py`:
  - `_scan_missions` builds `tracked` once and filters with `is_mission_dir`;
  - `_residue_result` produces `RESIDUE_DIRECTORY`;
  - classifiers live in `src/specify_cli/audit/classifiers/`;
  - severities and codes are in `models.py`.
- `doctor mission-state --audit` CI runs use `--fail-on teamspace-blocker` (`ci-router.yml`).
- **Import direction**: `audit` may import `specify_cli.upgrade.feature_meta`. Check for a cycle (`feature_meta` imports `context.mission_resolver` and `core`). If one appears, move `baseline_slug_fields` to a neutral module (e.g. `specify_cli/mission_metadata.py`) and import it from both.
- This WP is independent of WP01–WP05 and can run in parallel.

## Branch Strategy

- **Planning base branch**: fix/residue-safe-migration-sweep
- **Merge target branch**: fix/residue-safe-migration-sweep

```bash
spec-kitty agent action implement WP06 --agent claude --mission residue-safe-migration-sweep-01M5SS0F
```

## Subtasks & Detailed Guidance

### Subtask T023 – `baseline_slug_fields(slug)`

- Extract the slug-derived defaults from `build_baseline_feature_meta`: `mission_number` (the numeric prefix or `""`), `slug`, `mission_slug`, `friendly_name` (the slug tail with `-` replaced by spaces, or the slug). Return them as a dict.
- The builder uses the helper for those fields. Its output must be byte-identical for every existing test of `tests/upgrade/test_feature_meta.py`; add a parametrized equality test over several slugs (`042-x`, `my-mission-01M5JYRC`, `single`).

### Subtask T024 – Classifier `audit/classifiers/fabricated_identity.py`

- Write a pure function `fabricated_identity_signals(folder: Path, *, repo_root: Path, tracked: frozenset[str] | None, meta: dict | None) -> tuple[str, ...] | None`. It returns the matched signal names when all three hold, else `None`.
- Signal 1 uses `tracked` (no extra git call); outside git (`tracked is None`) it returns `None`.
- Signal 2's comparisons:
  - blank equivalence covers `""`, `None` and an absent key;
  - number equivalence: `"042"` matches `42` and `"042"`.
- Signal 3 uses `mid8_from_slug` (Crockford).
- Keep complexity ≤ 15; one helper per signal.

### Subtask T025 – Code, severity and engine wiring

- Add `FABRICATED_IDENTITY_SUSPECTED` to `models.py`, not in `TEAMSPACE_BLOCKER_CODES`, with WARNING severity.
- In `_scan_missions`, for each candidate that **is** a Mission per `is_mission_dir` and has `repo_root` set, run the classifier. On a match, append the finding to that Mission's results without dropping other findings.
- Update the `_residue_result` detail text (remedy) and its test in `tests/audit/test_residue_directory_finding.py`.

### Subtask T026 – Tests

- **File**: `tests/audit/test_fabricated_identity_finding.py` (`git_repo`).
- **Cases**:
  1. **Positive**: a committed folder `my-mission-01M5JYRC/` with a baseline-shaped `meta.json` (`mission_id` `01M5JZWS…`), a `status.json` and `decisions/index.json`. Running the audit via the CLI (`doctor mission-state --audit --json`) gives exactly one `FABRICATED_IDENTITY_SUSPECTED` with severity warning.
  2. **Negatives**, one per missing signal:
     - an extra `research.md` (signal 1);
     - a non-baseline `friendly_name` (signal 2);
     - a matching mid8 (signal 3);
     - a slug with no mid8 (signal 3);
     - an untracked `meta.json` (signal 1);
     - a project outside git.
  3. **Thresholds**: the CLI exit code with `--fail-on teamspace-blocker` and `--fail-on error` is 0 on the positive fixture, and non-zero with `--fail-on warning`.
  4. **Corpus**: run the classifier over this repository's own `kitty-specs/` at HEAD (read-only; `repo_root` = the repo) and assert 0 matches. Mark it `slow` if it exceeds a few seconds.

## Test Strategy

```bash
uv run --frozen pytest tests/audit tests/upgrade/test_feature_meta.py tests/integration/migration/test_residue_dir_not_treated_as_mission.py -q
uv run --frozen mypy --strict src/specify_cli/audit/classifiers/fabricated_identity.py src/specify_cli/audit/engine.py src/specify_cli/audit/models.py src/specify_cli/upgrade/feature_meta.py
```

## Risks & Mitigations

- **False positives**: all three signals plus the corpus test.
- **Builder drift**: the shared helper plus the equality tests.
- **Engine complexity**: `_scan_missions` may already be near 15, so extract a helper for the classifier call.

## Review Guidance

- Check signal 3 uses `mid8_from_slug`, and that nothing writes to disk.
- Check the `--fail-on` contract test exists and the remedy text is accurate.

## Progress & Status

- `spec-kitty agent tasks add-history WP06 --note "..."`, `spec-kitty agent tasks move-task WP06 --to <status>`, `spec-kitty agent tasks status`.
