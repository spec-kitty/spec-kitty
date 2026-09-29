---
work_package_id: WP04
title: Guidance matches the unforced loop
dependencies:
- WP02
- WP03
requirement_refs:
- FR-007
planning_base_branch: issue-5196-rework-is-not-an-override
merge_target_branch: issue-5196-rework-is-not-an-override
branch_strategy: Planning artifacts for this mission were generated on issue-5196-rework-is-not-an-override. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5196-rework-is-not-an-override unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-rework-is-not-an-override-01M3MQV6
base_commit: 59502db6825305687ecd04cc4262a05cdca0c52c
created_at: '2026-09-28T21:10:27.385407+00:00'
subtasks:
- T017
- T018
- T019
- T020
- T021
phase: Phase 3 - Guidance
history:
- at: '2026-09-28T20:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: doctrine-daphne
authoritative_surface: src/charter/offering/skills/
create_intent:
- tests/doctrine/test_rework_guidance_unforced.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/charter/offering/skills/spec-kitty-implement-review/SKILL.md
- src/charter/offering/skills/spec-kitty-runtime-review/SKILL.md
- src/charter/offering/skills/spec-kitty-runtime-review/references/review-checklist.md
- docs/guides/how-to/missions/review-work-package.md
- tests/doctrine/test_rework_guidance_unforced.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Guidance matches the unforced loop

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `doctrine-daphne`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⛔ HARD RULE — no heavy full suites during the mission

During implement and **every WP review** (by you AND every implementer/reviewer subagent you dispatch), NEVER run full or heavy suites:
- no whole `tests/architectural/`, no e2e or full-integration suites, no performance/stress/timing suites;
- no `make test-full`, no whole-repo pytest.

Per WP, run only:
- the test files covering the files the WP touches;
- the owning module's fast tier;
- the specific NAMED architectural gate files the change implicates.

Leave the broad sweeps to the END of the mission (closeout, and only the targeted set listed below) or to CI. This is the internal-pack directive NO_FULL_HEAVY_SUITES_IN_MISSION.

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?** Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`) or the Activity Log below.
- **You must address all feedback** before your work is complete.

---

## Objectives & Success Criteria

FR-007: the shipped guidance currently teaches reviewers and orchestrators to run `move-task … --to planned --force` for an ordinary rejection. After WP02/WP03 no `--force` is needed anywhere in the ordinary loop, and forced moves feed hollow-review proxies (#3010). Rewrite the ordinary-loop steps to be unforced and to pass the actor's own `--agent` identity. **Keep** the legitimate forced guidance: the arbiter override (planned → approved with `--note`), the self-review fallback (`--self-review-fallback --force`), the done override, and genuine takeover.

Done when:
- `tests/doctrine/test_rework_guidance_unforced.py` was RED on the base and is GREEN now;
- the skill-content tests pass;
- the terminology guard and docs freshness are clean.

## Context & Constraints

- Read `spec.md` (FR-007, Assumptions), `research.md` R-07 (residuals: **do not overclaim reviewer independence**; the guard is tool-scoped and a same-tool pair is not checked), and `contracts/ownership-role-allowance.md` (what is now allowed unforced).
- Shipped behaviour after WP02:
  - A reviewer whose tool differs from the latest implementer's can claim, approve or reject from `for_review` unforced when it passes its own `--agent`.
  - The latest implementer resumes and resubmits unforced with its own `--agent`.
  - `in_review` verdicts belong to the review-claim holder.
- Pack tiers: these are **consumer** skills (`src/charter/offering/skills/`) and a consumer how-to (`docs/guides/`). Do not mention spec-kitty repo-internal paths, issue numbers or mission ids in the skill prose. The built-in provenance ratchet forbids them in shipped doctrine; check `tests/architectural/test_builtin_pack_provenance_ratchet.py` for whether it also scans `src/charter/offering/skills/`.
- Do **not** edit `packs/built-in/missions/mission-steps/software-dev/review/prompt.md`: it already uses unforced `--to in_progress` (post-plan finding). Do not edit generated agent copies (`.claude/`, `.agents/`, …).
- Terminology canon: Mission, never "feature"; see `CLAUDE.md`.

## Branch Strategy

- **Strategy**: lanes (populated by finalize-tasks)
- **Planning base branch**: `issue-5196-rework-is-not-an-override`
- **Merge target branch**: `issue-5196-rework-is-not-an-override`

Start with `spec-kitty agent action implement WP04 --agent <you>`. This lane depends on WP02 and WP03.

## Subtasks & Detailed Guidance

### Subtask T017 – RED guard test (commit first)

- **File**: `tests/doctrine/test_rework_guidance_unforced.py` (new). Match the marker convention of `tests/doctrine/test_spec_kitty_skill_content.py`.
- **Behaviour**: for each of the four owned guidance files, find every shell line containing `move-task` together with `--force` (join backslash-continued lines first). Classify each hit by the command's own flags:
  - **allowed**: the command also contains `--self-review-fallback`, `--done-override-reason`, or `--to approved`/`--to done` inside an explicitly arbiter-labelled block. Anchor on the surrounding heading or comment mentioning "arbiter"/"override", or on `--note` + `--to approved`.
  - **forbidden**: `--to planned` with `--review-feedback-file` (the ordinary rejection), `--to for_review`, `--to in_progress`, `--to claimed`, `--to in_review`.
- Assert zero forbidden hits, and report file:line in the failure message.
- Add a **positive control**: a test proving the classifier flags a synthetic forbidden line and passes a synthetic arbiter line (the non-vacuity tactic).
- Run it on the base; it must fail on the known hits:
  - `spec-kitty-implement-review/SKILL.md` ≈ lines 429, 498, 535;
  - `spec-kitty-runtime-review/SKILL.md:~120`;
  - `references/review-checklist.md:~26`;
  - `docs/guides/how-to/missions/review-work-package.md:~142`.

  Paste the red summary into the Activity Log.
- Commit alone: `test(doctrine): red guard for forced ordinary-loop guidance (#5196)`.

### Subtask T018 – implement-review skill

- **File**: `src/charter/offering/skills/spec-kitty-implement-review/SKILL.md`.
- **Edits**:
  - Both reviewer prompt templates (~429 and ~498): `spec-kitty agent tasks move-task WP## --to planned --review-feedback-file <path> --agent <reviewer-agent-id>`, with no `--force`. At the Tier-3 note (~498), tell the orchestrator to act **as** the reviewer (`--agent <reviewer>`) when relaying a verdict.
  - "What Happens on Rejection" (~535): the same unforced command. Add one sentence: the implementer resumes the rework with its own `--agent`, and the resubmission and re-review need no `--force`, so they are not recorded as an override.
  - Troubleshooting (~932-934): replace "The reviewer may need `--force`…" with guidance that distinguishes an "Illegal transition" (use the canonical lane path, e.g. claim `in_review` before a verdict) from an "Agent mismatch" (pass your own `--agent`; `--force` is only for a genuine takeover, and it is recorded).
  - **Keep unchanged**: the self-review fallback (~479), the arbiter options (~587/593/599), the done override (~866).

### Subtask T019 – runtime-review skill + checklist

- `src/charter/offering/skills/spec-kitty-runtime-review/SKILL.md:~120`: the unforced reject command with `--agent <your reviewer id>`.
- `src/charter/offering/skills/spec-kitty-runtime-review/references/review-checklist.md:~26`: the same.

### Subtask T020 – how-to guide

- `docs/guides/how-to/missions/review-work-package.md:~142`: the unforced reject example with `--agent`. Bump the frontmatter `updated:` date to the implementation date (docs freshness SLA). Keep the Divio type unchanged.

### Subtask T021 – Green-up and gates

```bash
uv run --frozen pytest tests/doctrine/test_rework_guidance_unforced.py tests/doctrine/test_codex_dispatch_flags.py tests/doctrine/test_command_template_cleanliness.py tests/doctrine/test_issue_matrix_json_migration_completeness.py tests/doctrine/test_spk_skill_pack.py -q
uv run --frozen pytest tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen python scripts/docs/check_docs_freshness.py --ci                        # if present; errors must be 0
uv run --frozen ruff check tests/doctrine/test_rework_guidance_unforced.py && uv run --frozen ruff format --check tests/doctrine/test_rework_guidance_unforced.py
grep -rl "spec-kitty-implement-review\|spec-kitty-runtime-review" tests/ --include=*.py   # run any other skill tests that pin these files' content
```

- If a skill manifest or hash (e.g. under `.kittify/command-skills-manifest.json` or a skill-pack manifest test) pins content hashes, regenerate it with the canonical command named in the failing test's message. Never hand-edit the hashes.

## Risks & Mitigations

- **Over-broad classifier**: the test must allow the legitimate forced flows; the T017 positive control covers this.
- **Overclaiming**: do not state that the CLI enforces reviewer independence. The guard is tool-scoped (research R-07).

## Review Guidance

- Verify every ordinary-loop command is unforced and passes the actor's `--agent`, and that the arbiter, self-review and done-override flows are untouched.
- Verify the RED commit precedes the edits.
- Verify there are no repo-internal paths or issue numbers in skill prose.
- Reviewer ≠ implementer. Respect the HARD RULE.

## Hardening (post-tasks squad — binding)

- **The T017 classifier scans every line, not only fenced blocks**: `SKILL.md:~535` and `review-checklist.md:~26` are inline code.
- Treat `--to blocked` (the arbiter's Option B, `SKILL.md:~593`) as **allowed**.
- The troubleshooting prose at `SKILL.md:~932-934` has no `move-task` token. Add an explicit assertion that the phrase "may need `--force`" is absent from that file.
- Existing content pins on these skills: `tests/doctrine/test_codex_dispatch_flags.py`, `test_command_template_cleanliness.py:~406`, `test_issue_matrix_json_migration_completeness.py:~275` (implement-review must keep mentioning `issue-matrix.json`). The provenance ratchet scans `packs/built-in` only, and there are no generated skill copies in the repo.
- The refusal-hint line (FR-007's CLI surface) is delivered by WP02, not here.

## Activity Log

- 2026-09-28T20:30:00Z – system – Prompt created.
