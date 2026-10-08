---
work_package_id: WP10
title: Close-out evidence, pre-rebase
dependencies:
- WP09
requirement_refs:
- NFR-006
- C-001
- C-004
- C-005
planning_base_branch: issue-5776-mission-status-contract-health-drift-ops
merge_target_branch: issue-5776-mission-status-contract-health-drift-ops
branch_strategy: Planning artifacts for this mission were generated on issue-5776-mission-status-contract-health-drift-ops. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5776-mission-status-contract-health-drift-ops unless the human explicitly redirects the landing branch.
subtasks:
- T053
- T054
- T055
history: []
agent_profile: curator-carla
authoritative_surface: kitty-specs/mission-status-health-drift-ops-01M464D3/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- kitty-specs/mission-status-health-drift-ops-01M464D3/tracer-approach.md
- kitty-specs/mission-status-health-drift-ops-01M464D3/tracer-design-decisions.md
- kitty-specs/mission-status-health-drift-ops-01M464D3/tracer-tooling-friction.md
role: curator
tags: []
tracker_refs: []
---
# Work Package Prompt: WP10 - Close-out evidence, pre-rebase

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `curator-carla`
- **Role**: `curator`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Append the close-out assessment (what held, what the plan got wrong, what the next Mission should do differently) to the three tracer files, after every record the orchestrator collected, labelled pre-rebase.

## Context

This is the only work package with files under `kitty-specs/` in its write scope, and it is a `planning_artifact` package (the mode is set explicitly in the frontmatter: inference reads the body, and a mention of a test path or a Python file would make it `code_change`). The files are APPEND-ONLY: add text at the end, never edit or delete an existing line (`kitty-specs/` is archive-frozen on `main` and the Mission directory is add-only on the branch, measured over the diff against the merge base, which is what T055 checks; a hit found by the hygiene scan is never fixed by you: report it in the hand-off, and the orchestrator fixes or rules it at W-5). The orchestrator appended all other records between dispatches; it appends nothing while this package is in progress. The final evidence is W-7, not this package: label everything pre-rebase.

**Where this package works (orchestrator Step PD in `tasks.md`, operator ruling 13).** WP10 is `lane-planning`: it works in the planning branch itself (the repository root checkout of `issue-5776-mission-status-contract-health-drift-ops`), where the orchestrator committed every record add-only, so nothing is merged into a lane for it and there is no append-versus-append conflict. Before you start, grep in the tracer files of that checkout for the headings `## Record: Step 0`, `## Record: Hygiene counts` and `## Record: Hand-off WPxx (` for each of WP01 to WP09 (all in `tracer-approach.md`) and `## Record: J-1 (` (in `tracer-design-decisions.md`); if any is missing, stop and report it. Never run `--refresh-planning-commit`.

Plan concern: IC-10 of `kitty-specs/mission-status-health-drift-ops-01M464D3/plan.md`. Read, in this order, before writing anything: `.kittify/charter/charter.md`, `AGENTS.md` (for conventions only), the Mission's `spec.md` (the requirement ids in the frontmatter), `plan.md` sections named below, `research.md`, `data-model.md`, `quickstart.md` and `contracts/*.md` in `kitty-specs/mission-status-health-drift-ops-01M464D3/`.

## Owned files (write scope; final, explicit, no directory-wide glob)

- `kitty-specs/mission-status-health-drift-ops-01M464D3/tracer-approach.md`
- `kitty-specs/mission-status-health-drift-ops-01M464D3/tracer-design-decisions.md`
- `kitty-specs/mission-status-health-drift-ops-01M464D3/tracer-tooling-friction.md`

## Implementation concern (plan section IC-10, verbatim)

- **Purpose**: The close-out assessment of the three tracer files (what held, what the plan got wrong), appended after every record the orchestrator collected. Labelled pre-rebase; the final evidence is W-7.
- **Write scope**: `tracer-approach.md`, `tracer-design-decisions.md`, `tracer-tooling-friction.md` of this directory (append-only); the only work package with a file under `kitty-specs/` in its scope. **Execution mode: `planning_artifact`, set explicitly in its frontmatter** (inference reads the body: a mention of `tests/` or a `.py` file would make it `code_change`). Expected placement: `lane-planning`, depending on the code lane. **Sequencing**: after IC-09.

## Hygiene scan of the Mission directory (run at the end; zero problems)

The Mission directory joins the corpus the new reads run over, so it must hold nothing they refuse and nothing the human leak patterns flag:

```text
<synced-python> -I - <<'PY'
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("leak_patterns", "contracts/tools/leak_patterns.py")
lp = importlib.util.module_from_spec(spec)
sys.modules["leak_patterns"] = lp
spec.loader.exec_module(lp)
root = Path("kitty-specs/mission-status-health-drift-ops-01M464D3")
FLOOR = 28  # scanned files at tasks time; raise to the exempt-count of the `## Record: Hygiene counts` record (see below)
assert root.is_dir(), "run from the repository root"
problems = files = 0
for f in sorted(root.rglob("*")):
    rel = f.relative_to(root).as_posix()
    if f.is_dir() or rel.startswith("reviews/") or rel in ("status.events.jsonl", "status.json"):
        continue
    files += 1
    if f.is_symlink():
        print("SYMLINK", rel)
        problems += 1
        continue
    raw = f.read_bytes()
    if len(raw) > 262144:
        print("TOO_BIG", rel, len(raw))
        problems += 1
    if b"\0" in raw:
        print("NUL", rel)
        problems += 1
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        print("NOT_UTF8", rel)
        problems += 1
        continue
    for number, line in enumerate(text.splitlines(), 1):
        if line.strip() and lp.leak_codes(line, lp.HUMAN):
            print("LEAK", rel, number, lp.leak_codes(line, lp.HUMAN))
            problems += 1
assert files >= FLOOR, f"the walk found {files} files, fewer than the floor {FLOOR}: wrong directory or a vacuous pass"
print(f"files={files} problems={problems}")
PY
```

**Interpreter and floor.** `<synced-python>` is the interpreter defined once in item 2 of the Step 0 block of `tasks.md` (the hand-built `.venv/bin/python` is not used here either; the script needs only the standard library and `contracts/tools/leak_patterns.py`, run from the repository root, so no import check is needed; this package runs no `cutover-guard`, so `<synced-spec-kitty>` is not used here, the one exception to the substitution rule of the code work packages). Before this package is dispatched the orchestrator appends to `tracer-approach.md` the record headed `## Record: Hygiene counts` (Step PD item 6 of `tasks.md`) with two lines, `exempt-count: <n>` (the `files=` value of THIS script, unmodified) and `whole-directory-count: <m>` (the `files=` value of the same script with the exemption removed, the W-5 variant); set `FLOOR` to the `exempt-count`. The record is read in the planning checkout with `grep -n "^## Record: Hygiene counts" tracer-approach.md`.

A placeholder home path quoted in a sentence trips the host-path pattern: describe such a rule in words, never type the literal.

**Why `reviews/` and the event log are exempt, and who reads them.** The `reviews/` directory holds the review squad's findings files, which quote leak-shaped tokens as evidence of what they checked; `status.events.jsonl` is the append-only status log (byte-identical by rule; line 1 carries a no-reply attribution address) and `status.json` is generated. A mechanical zero would either fail on those quotations or tempt an edit of a file that must not change. They are not skipped: the orchestrator's hygiene scan at W-5 and W-7 of `tasks.md` (this script with the skip condition reduced to `f.is_dir()`, so `reviews/` and the status log are scanned, and `FLOOR` the `whole-directory-count` of the `## Record: Hygiene counts` record, not the smaller `exempt-count` this script uses) reads them, and each hit there is judged by a person (a no-reply address and quoted pattern examples are not private). The `files >= FLOOR` assertion guards the script above against a vacuous `files=0 problems=0` from a wrong working directory. The sentence before the fence is prose, not a command.

### Subtask T053: Read every record first

**Purpose**: Read the three tracer files in full and the hand-off records the orchestrator appended (Step 0 baseline, WP01 re-measurements, J-1, floors, timed minima and margins, friction observations).

**Steps**:
1. First confirm the `## Record: Hygiene counts` record exists and that running the hygiene script (below, with `FLOOR` set to its `exempt-count`) before your own additions prints `files=` equal to that `exempt-count`; report any difference.
2. Note which plan assumptions held and which did not, with the evidence line that shows it.

**Files**: none

**Validation**: A list of items for each file.

### Subtask T054: Append the assessments

**Purpose**: Append, per file and under a new dated heading `Close-out assessment (IC-10, pre-rebase)`: in `tracer-approach.md` what held, what the plan got wrong, what the next Mission should do differently; in `tracer-design-decisions.md` the decisions that were refined or reversed and why; in `tracer-tooling-friction.md` the friction observed, each with its remedy.

**Steps**:
1. Concrete and cited (a work package, a commit, a record id), not general. No absolute path, user name, address or private reference: use repository-relative paths and placeholders.

**Files**: kitty-specs/mission-status-health-drift-ops-01M464D3/tracer-*.md (append only)

**Validation**: Existing lines unchanged (`git diff` shows additions only).

### Subtask T055: Hygiene scan and add-only check

**Purpose**: Run the hygiene scan of the Mission directory (below) and the add-only check against the merge base; both must be clean.

**Steps**:
1. `git diff --name-status --no-renames <merge-base>..HEAD -- kitty-specs/` shows only additions under this Mission's directory, plus modifications confined to the three append-only tracer files by additions of lines.

**Files**: none

**Validation**: `files=<n> problems=0` with `<n>` at or above the floor (the assertion fires otherwise).

## Dispatch hygiene (binding for this work package)

- **No sub-agents.** You work alone: do not start, fork, brief or message other agents.
- **A denied command means STOP and report it** in the hand-off; never retry a denied command in another form.
- **No pattern kills** (`pkill`, `killall`), **no `git stash`**, **no `rm` with a variable or wildcard glob**, no checkout, switch, restore, reset, clean or rebase of the shared checkout. Work in the lane workspace the orchestrator assigns; do not move HEAD of any other workspace.
- **Repository-relative paths only** in every file, commit message and report; placeholders such as `<repo>`, `<scratch>`, `<tmp>`, `<user>` elsewhere. This repository is PUBLIC: no absolute path under a home directory, no drive path, no user name, e-mail address, private identifier, chat mention or credential in any file, test, fixture, commit message or report. Leaking values a test needs (host paths, addresses, tokens, an at-sign file name) are assembled from fragments at run time and never typed as literals; no shared-temp literal in any plant.
- **Unicode-escape hazard:** editing tools decode a backslash-u sequence typed into a file into the raw character. Write a NUL as `\x00` in a contract pattern, build NUL with `chr(0)` and a backslash with `chr(92)` in tests, and check every new file for raw NUL bytes after writing.
- **Commit locally. NEVER push, never open a pull request, never comment on an issue, never merge.** Conventional commit subjects ending with `(#5776)`; end each commit message with the attribution trailers the dispatch brief supplies. Commit through `spec-kitty safe-commit` where a guarded branch requires it; never bypass a guard.
- **Never hand-edit** `status.events.jsonl`, `meta.json`, `status.json`, `lanes.json`, issue-matrix files or work package frontmatter; never call `materialize`.
- **Baseline-red binning against the Step 0 record.** Before your first change run this work package's targeted commands once on the unchanged lane base and reconcile with the orchestrator's Step 0 record in `tracer-approach.md` (read it; the orchestrator appends it before any dispatch). Bin every red: (1) pre-existing known-P0 (nightly lane only), (2) CI-environment, (3) stale install, (4) stale venv (resync, then retry), (5) introduced. Only a failure red on your branch and green on the base is yours. A pre-existing red: STOP and report it (command, failure summary, why you believe it is pre-existing); the orchestrator owns the tracker issue (Pre-existing Failure Reporting Rule). Do not absorb it, never retry until green. A red on your lane base but green at the Mission baseline came from an earlier work package of this Mission: report it against that work package, do not bin it as pre-existing.
- Terminology: Mission, never feature; say which sense of lane (status lane versus code lane). New code passes `ruff check` and `ruff format --check` with no suppression added; complexity ceiling 15; a literal used three or more times in a module becomes a constant; new code is annotated to pass `mypy --strict` as local discipline.

## Hand-off report (your final message)

The commit hash and subject; the three files appended to and the heading used; the hygiene-scan output (`files=<n> problems=0`); the add-only check output; anything not done and why. You write only the three tracer files; nothing else.

## Definition of Done

- The assessment is appended to all three files, labelled pre-rebase, existing lines untouched.
- The hygiene scan prints `problems=0`.
- No file outside the three tracer files is changed.
- Per-subtask completion evidence is a `spec-kitty agent tasks mark-status <Txxx> --status done` record (event-sourced), not a ticked checkbox.
- Nothing pushed; no pull request; no tracker write.

## Risks

- A placeholder home path quoted in a sentence trips the host-path pattern: describe such a rule in words, never type the literal.
- Editing instead of appending breaks the add-only rule.

## Reviewer Guidance

The reviewer is a separate role from the implementer. Review the diff of this work package against its owned files and its full targeted test surface, plus the named gate files and census files above; never a full sweep.
- Verify the change is append-only (additions of lines at the end of the three files, no other file) and the hygiene scan is clean.

## Wrap-up reference (orchestrator-owned, NOT part of this work package)

After every work package is approved the orchestrator runs W-1 (accept, local lane consolidation, registration and scope check over the real diff), W-2 (J-1 confirmation), W-3 (dev-assist cleanup), W-4 (issue-verdict evidence, aggregate adversarial squad, terminal #5776 verdict), W-5 (history compaction), W-6 (rebase onto upstream `main`) and W-7 (final evidence); then the draft pull request. You do none of this.

## Implementation command

`spec-kitty agent action implement WP10 --agent claude`
