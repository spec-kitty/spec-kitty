---
work_package_id: WP09
title: Close-out evidence (pre-tag) and tracer assessment
dependencies:
- WP07
- WP08
requirement_refs:
- SC-001
- SC-002
- SC-003
- SC-004
- SC-005
- SC-006
- SC-007
- SC-008
- C-003
- C-004
planning_base_branch: issue-5625-mission-status-contract-1-1
merge_target_branch: issue-5625-mission-status-contract-1-1
branch_strategy: Planning artifacts for this mission were generated on issue-5625-mission-status-contract-1-1. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5625-mission-status-contract-1-1 unless the human explicitly redirects the landing branch.
subtasks:
- T050
- T051
- T052
history: []
agent_profile: scribe-sally
authoritative_surface: kitty-specs/mission-status-contract-1-1-01M42XJC/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- kitty-specs/mission-status-contract-1-1-01M42XJC/tracer-approach.md
- kitty-specs/mission-status-contract-1-1-01M42XJC/tracer-design-decisions.md
- kitty-specs/mission-status-contract-1-1-01M42XJC/tracer-tooling-friction.md
role: documentarian
tags: []
tracker_refs: []
---

# Work Package Prompt: WP09 – Close-out evidence (pre-tag) and tracer assessment

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `scribe-sally`
- **Role**: `documentarian`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Append the pre-tag close-out evidence and the orchestrator-reported records to the three tracer files, add-only, and write the tracer assessment. Execution mode is `planning_artifact`: this WP owns only files under the Mission directory.

## Context

Plan IC-09 and "Record-keeping and write scope" (Standing Order 3). It is the only work package with a file under `kitty-specs/` in its scope; it runs on `lane-planning` (the repository root checkout) and depends on WP07 and WP08. It needs no tag. Evidence recorded here is labelled pre-tag and pre-rebase; the final evidence is wrap-up W-7. The orchestrator appends records between dispatches and never while this WP is in progress. `kitty-specs/` on `main` is frozen: this Mission's own files are add-only on the branch, so every edit here only appends. Append with a plain add-only edit of the three owned files and commit them with `spec-kitty safe-commit`. Do NOT use `spec-kitty agent tracer-append`: it writes to a different surface (`traces/<category>.md`, a separate file the planning phase already created), outside this work package's write scope, and would leave two competing records.

Decisions honoured: none of the spec's CL, AD, AC, OQ or OD rows is mapped to this work package (spec.md remains reference material).

Plan concern: IC-09 (plan section Implementation Concern Map). Requirement refs: SC-001, SC-002, SC-003, SC-004, SC-005, SC-006, SC-007, SC-008, C-003, C-004. Dependencies: WP07, WP08. Branch contract: planning base and merge target are `issue-5625-mission-status-contract-1-1`; work runs in the lane workspace `spec-kitty agent action implement` resolves for you (never reconstruct a path by hand).

## Owned files (write scope)

Edit only these paths (declared shared-file exceptions are dependency chains, never concurrent; plan section Lanes):

- `kitty-specs/mission-status-contract-1-1-01M42XJC/tracer-approach.md`
- `kitty-specs/mission-status-contract-1-1-01M42XJC/tracer-design-decisions.md`
- `kitty-specs/mission-status-contract-1-1-01M42XJC/tracer-tooling-friction.md`

Every owned path is under the Mission directory; every edit is an append. Nothing outside the three tracer files may change.

### Subtask T050: Append the pre-tag evidence record to tracer-approach.md

**Purpose**: The pre-tag evidence record.

**Steps**:

1. Append to `tracer-approach.md` a dated entry: per work package the commands run and counts (from the hand-off reports the orchestrator hands you), the `--baseline-root` recipe result of WP07, the corpus job timing of WP08, and the baseline record of WP01. Label every figure pre-tag and pre-rebase.
2. Add the close-out assessment: what held, what the plan got wrong or sharpened, lane outcome versus the plan's expected lane picture (a finalised manifest that differs is recorded here).

**Files**: `kitty-specs/mission-status-contract-1-1-01M42XJC/tracer-approach.md` (append only).

**Validation**: Entry present, labelled, append-only (`git diff` shows only added lines).

### Subtask T051: Append the orchestrator-reported records, add-only, to the other two tracer files

**Purpose**: The records other work packages reported.

**Steps**:

1. Append to `tracer-design-decisions.md` every contract-note refinement and design decision the hand-off reports name (for example the D-P3 fallback decision if it was taken) that the orchestrator has not already appended; append to `tracer-tooling-friction.md` every friction observation not yet recorded. Continue the numbering of the existing entries (F-n, D-n).
2. Use only what the reports say; add no claim you cannot trace to a report or a command.

**Files**: `tracer-design-decisions.md`, `tracer-tooling-friction.md` (append only).

**Validation**: Each appended entry names its source (WP and report).

### Subtask T052: Verify add-only and leak-free, and write the hand-off report

**Purpose**: Verify and hand off.

**Steps**:

1. `git diff --name-status` over the three tracer files shows only `M`, and `git diff` shows only added lines for each.
2. Run the public-hygiene scan over the Mission directory as the plan states: `leak_patterns.leak_codes(line, HUMAN)` over every line of every file of the directory (`reviews/` and the status log excluded) returns zero hits; no absolute home path, user name or address was written.
3. Hand-off report: the appended entries, the scan result and the commit hash.

**Files**: None.

**Validation**: Add-only proven; scan zero hits.

## Validation: gates and targeted test surface

Charter: no full `tests/architectural/`, end-to-end, performance or `make test-full` sweep in mission work (`NO_FULL_HEAVY_SUITES_IN_MISSION`); run exactly the commands below, record each command and its passed/failed counts in the hand-off report. Use the checkout's own environment (`.venv/bin/...`), never a bare `uv run`. `<scratch>` means a scratch directory outside the repository.

Targeted surface for this work package:

- No test suite applies (planning artifacts only). Run `.venv/bin/spec-kitty agent mission check-prerequisites --include-tasks --mission mission-status-contract-1-1-01M42XJC --json` to confirm the Mission directory is still valid.

## Baseline rule: pre-existing red versus introduced red

Before your first change, run this work package's targeted commands once on the unchanged lane base. Any red is binned before work continues: (1) pre-existing known-P0 red on `main` (leave it red, never green-wash), (2) CI-environment failure (auth, opt-out variables; passes locally), (3) stale install, (4) stale venv (re-run `uv sync --frozen --all-extras`, then retry), or (5) introduced by you. Only a red that is red on your branch AND green on the base is yours to fix. A pre-existing red: STOP and report to the orchestrator in your hand-off (command, failure summary, why you believe it is pre-existing); the orchestrator owns the tracker issue (Pre-existing Failure Reporting Rule). Do not open an issue or post a comment yourself, do not absorb it, do not retry until green.

## Git, commits and public-repo hygiene

- **Commit locally. NEVER push, never open a pull request, never comment on an issue, never merge.** One pull request per Mission is opened by the orchestrator after the wrap-up sequence.
- Conventional commit subjects ending with `(#5625)`; end each commit message with the attribution trailers the orchestrator supplies. Commit through `spec-kitty safe-commit` where a guarded branch requires it; never bypass a guard with raw git or an environment override.
- **This repository is PUBLIC**: everything you write ships visibly and permanently. No absolute path under a home directory and no drive path, no user name, no e-mail address, no private reference, no credential in any file, test, fixture, commit message or report. Use repo-relative paths and placeholders such as `<repo>`, `<scratch>`, `<user>`. A username-leak is folded before anything leaves the machine; report any you find.
- Leaking values a test needs (host paths, addresses, tokens, an at-sign file name) are assembled from fragments at run time and never typed as literals. Editing tools decode a unicode escape typed into a file into the raw character: write NUL as `chr(0)` and backslash as `chr(92)` in tests, use the hex escape in contract patterns, and check every new file for raw NUL bytes.
- Terminology: Mission, never feature; say which sense of lane (status lane versus code lane); no `--feature` flag text. New code passes `ruff check` and `ruff format --check` with no suppression added; complexity ceiling 15; literals used three or more times in a module become constants.
- `kitty-specs/` is archive-frozen on `main`: this Mission's own files are add-only on the branch. Never hand-edit `meta.json`, `status.events.jsonl`, `lanes.json` or work package frontmatter; never call `materialize`. Never run a pattern kill (`pkill`/`killall`), `git stash`, or `rm` with a variable glob.
- **Subagents dispatch nothing**: you work alone; do not start, fork or brief other agents. A denied command means STOP and report it; never retry a denied command.

## Hand-off report (your final message)

Commits (hash and subject, in order; this work package has no red-first commit, it only appends records), every command run with its result, any refinement of a contract note or design decision you appended, any friction observation, anything not done and why. This work package writes the three tracer files under `kitty-specs/`, add-only: append, never edit or delete an existing line, and never touch another file under `kitty-specs/`.

## Definition of Done

- Three tracer files changed append-only; entries labelled pre-tag and pre-rebase where they are evidence.
- Close-out assessment present in `tracer-approach.md` (lane outcome versus plan).
- Hygiene scan zero hits; no other file touched.
- Per-subtask completion evidence is a `spec-kitty agent tasks mark-status <Txxx> --status done` record (event-sourced), not a ticked checkbox.
- Nothing pushed; no pull request; no tracker write.

## Risks

- Writing a figure no report supports: cite the report or omit it.
- A literal at-sign file name or host path typed into the prose trips the Mission-directory scan: describe in words.

## Reviewer Guidance

The reviewer is a separate role from the implementer. Review the diff of this work package against its owned files and its full targeted test surface (every file the change touches), plus the specific named architectural gate files it implicates; never a full sweep.

- Confirm append-only (no deleted or rewritten line) and that each figure traces to a hand-off report.
- Re-run the hygiene scan over the Mission directory.
- Check public hygiene: no absolute path, user name, address, credential or private detail in any added line or commit message; no leaking literal.

## Wrap-up reference (orchestrator-owned, NOT part of this work package)

After every work package is approved the orchestrator runs plan steps W-1 to W-7 in this order: W-1 accept, then lane consolidation (`spec-kitty consolidate`, strategy `rebase` recommended), then registration and wiring check, scripted scope check and issue-matrix rows; W-2 JVM shake-out; W-3 dev-assist cleanup; W-4 aggregate adversarial squad (report-only, pre-rebase tree); W-5 history compaction; W-6 rebase onto upstream including the 1.0.0 release commit; W-7 final evidence. Only then is the draft pull request opened, and it needs the `contract-mission-status-v1.0.0` tag. Evidence recorded earlier is labelled pre-tag or pre-rebase. You do none of this.

## Implementation command

`spec-kitty agent action implement WP09 --agent claude`
