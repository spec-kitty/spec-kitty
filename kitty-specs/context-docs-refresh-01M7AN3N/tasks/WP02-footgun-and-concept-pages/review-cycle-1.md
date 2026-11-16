---
affected_files: []
cycle_number: 1
mission_slug: context-docs-refresh-01M7AN3N
reproduction_command:
reviewed_at: '2026-11-13T15:54:51Z'
reviewer_agent: claude-reviewer::reviewer-renata
wp_id: WP02
---

**Issue 1 (medium, FR-004): `orchestration.md:472`, the "Planning base branch" definition, is contradicted by the code.**
The definition says it is "The branch active in the repository root checkout when WP prompts were generated" and is "Stored in every WP prompt's frontmatter and in `lanes.json`". This WP edited that sentence ("main repository" became "repository root checkout") but left the substance unchecked.
- `finalize-tasks` writes `planning_base_branch = target_branch`, not the active branch (`src/specify_cli/cli/commands/agent/mission_finalize_bootstrap.py:187-189`; also `mission_branch_context.py:142`). That is the prep-branch-leak fix the same row describes. This Mission shows it: WP prompts were generated on `kitty/mission-context-docs-refresh-01M7AN3N` and carry `planning_base_branch: issue-7522-context-refresh`.
- `lanes.json` has no `planning_base_branch` key. Its top-level keys are `version`, `mission_slug`, `mission_id`, `mission_branch`, `target_branch`, `lanes`, `computed_at`, `computed_from`, `planning_artifact_wps` and `planning_commit_sha`.

Fix: define it as the WP-frontmatter key that `finalize-tasks` sets to `target_branch`, whichever branch is checked out. Drop the `lanes.json` claim. Log the correction with this evidence. Row 30's evidence can cite the code rather than this Mission's single sample.

**Issue 2 (medium, FR-004): `identity.md`, Engagement "Do NOT use when", calls `project_uuid` "a SaaS-assigned identity".**
U5 is not unverifiable; the code refutes it:
- `ProjectIdentity.project_uuid` is minted locally by `generate_project_uuid()` (`src/specify_cli/identity/project.py:82,141`);
- `spec-kitty init` writes it (`cli/commands/init.py:1404-1407`), and this repository's `.kittify/config.yaml` carries `project.uuid`;
- it is stamped on lifecycle events (`status/lifecycle_events.py:323,335`);
- the "SaaS collaboration binding" it is said to name was removed with #6164.

Fix the row on this page: drop "SaaS collaboration binding" and "SaaS-assigned", and describe `project_uuid` as the locally minted project identity. Move U5 out of "Unverifiable facts" into a correction row, and leave a note for WP03 to fix `identity-fields.md#project_uuid` ("Never locally minted") the same way.

**Issue 3 (low, FR-005): qualify U3, U4 and U6 on the page instead of leaving them as plain statements.**
Each was searched for and found absent, so a reader takes a non-existent mechanism or file as real.
- U3 `execution.md` (Clarification Prompt): "Burst policy: Cap to top 3 high-priority conflicts per prompt burst". No cap exists in `src/glossary/` (`clarification.py`, `middleware.py`) or elsewhere in `src/`. Mark it as an intended policy that is not enforced, or drop the row.
- U4 `execution.md:222-258` (`GovernanceContext`, `InfraContext`, status `canonical`): no such types or "Governance module" / "Execution module" exist in `src/`, unlike the neighbouring `MissionExecutionContext` (`src/mission_runtime/context.py:397`). Mark them as design concepts not implemented today.
- U6 `orchestration.md:301`: "See the SaaS domain glossary at `architecture/domain-glossary.md`" points at a path that does not exist in this repository. Say it lives in the separate SaaS repository, or drop the pointer.

Leaving U1, U2, U7 and U8 as plain flags is fine.

**Issue 4 (low, NFR-003): `execution.md:239` says "feature directory" for the Mission directory.**
The field is `feature_dir` (`src/mission_runtime/context.py:433`). Write "the Mission directory (`feature_dir`)".

**Issue 5 (low, overstatement): `identity.md`, Engagement Examples.**
"an issue title passed to the tracker executable is an engagement name" should read "can carry an engagement name". The cited constant says what is sent *carries* mission and engagement identifiers (`tracker/local_service.py:82`).

Advisory, not required for approval:
- Commit order: `a774169fdc` removes the command-surface phrase from `orchestration.md` while the file stays in `_COMMAND_SURFACE_PHRASE_BASELINE` until `089086492a`, so the ratchet is red on the commits between. Squash or reorder if you rewrite history anyway.
- Add O-rows for drift seen but out of scope:
  - `CLAUDE.md` says `consolidate` "never publishes to the remote", while `--push` runs `git push origin <target>` (your row 24);
  - the comments in `src/specify_cli/tracker/local_service.py:73-80` still cite the deleted `tracker/saas_client.py` and `egress.py`.
- U1: the "one container per team" detail can simply go from the vocabulary table; nothing depends on it.

Verified and fine:
- Rows 17-29 and 31-33 match the source:
  - `make_envelope` with seven keys;
  - `--push` running `git push origin <target_branch>` (`phase_finalize.py`);
  - `TopologySurface` declaring PRIMARY, COORD, LANE, CONSOLIDATED and TEMP, plus `translate_surface` and `assert_surface_totality`;
  - `FreshnessState` with 11 members including `not_checked` in `plan_review_lane`;
  - `charter sync` removed in `0189965d78`;
  - `LOCAL_SUBPROCESS_EGRESS_IDENTIFIER_KINDS` and the `tracker.egress` absent-refuses rule;
  - the hosted CLI entries all fail `--help`.
- The `primary`, `merge`, `routing` and `residue` disambiguations agree with the code: `is_kitty_specs_residue`, `RESIDUE_DIRECTORY`, `is_mission_dir` and `is_selectable_mission_dir` all exist where stated, and so do `consolidate_lane_into_mission` and `integrate_mission_into_target`.
- No heading was changed. All anchors linked from `CLAUDE.md`, `AGENTS.md`, `docs/` and `src/` resolve: 21 for orchestration, 10 for execution, 6 for topology and 4 for identity.
- `team-kitty.md` matches #6164 and `CLAUDE.md`.
- The burn-down is drained of all 11 `context/` pairs (3+4+4 distinct surfaces) with the baseline at 81 -> 70, and the gate passes with the frozen landing set untouched.
- The terminology-baseline removal is a tightening that the shrink-only ratchet requires.
- Contextive files for execution and orchestration are fresh; the stale ones are WP03's.
- WP01 pages, `packs/` and ADRs are untouched. All commits are signed.
