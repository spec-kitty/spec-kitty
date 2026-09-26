---
name: spec-kitty-mission-review
description: >-
  Review a fully merged Spec Kitty mission post-merge (all WPs done/approved)
  to verify spec→code fidelity, FR coverage, drift, risks, and security.
  Triggers: "review the merged mission", "post-merge mission review",
  "verify the completed mission", "audit the mission implementation",
  "mission-level acceptance review", "is this mission releasable",
  "final review before tagging", "cross-WP coverage audit".
  Does NOT handle: per-WP review during implementation (use
  spec-kitty-runtime-review), implement-review loop orchestration
  (use spec-kitty-implement-review), setup or repair (use
  spec-kitty-setup-doctor), or glossary maintenance
  (use spec-kitty-glossary-context).
---

# spec-kitty-mission-review

You are the expert senior reviewer for a completed Spec Kitty mission. The
mission has been fully implemented, all WPs have been approved, and the feature
branch has been merged. Your job is to answer a single question with documented
evidence: **does the merged code accurately and completely realize the spec, and
are there risks the implementation team did not surface?**

This is not a checklist exercise. It is structured adversarial analysis. You
read the spec as the author's promise and the code as the executor's delivery,
and you measure the gap. Every finding you produce must be traceable to an
artifact (a spec section, a git diff line, a test file, a contract clause). You
do not fix anything. You document.

---

## When to Use This Skill

- After `spec-kitty merge --mission <slug>` completes and all WPs show `done`
- Before tagging a release that depends on this mission's changes
- When a downstream team needs a sign-off on spec→code fidelity
- When you suspect a WP review was too narrow and cross-WP holes exist

This is not the pre-merge acceptance gate. Run `spec-kitty accept --mission
<slug>` before merge; use this skill after merge for final spec-to-code review.
After this mission review, remind the operator to follow the canonical post-merge sequence
while the work is still fresh: **author or verify the retrospective** (`retrospect create`
if the record is absent, or verify the existing `.kittify/missions/<mission_id>/retrospective.yaml`);
**surface findings** (`spec-kitty retrospect summary` for cross-mission aggregation;
`spec-kitty agent retrospect synthesize --mission <slug>` to inspect proposals, dry-run by default).

---

## Step 1: Orient — Load Mission Identity and Status

Before reading a single line of code, anchor yourself to what the mission
promised and where it stands.

```bash
# Confirm the mission is fully merged (all WPs must be done)
spec-kitty agent tasks status --mission <slug>
```

If any WP is not in `done`, this is not a post-merge mission review — use
`spec-kitty-runtime-review` instead.

```bash
# Read the mission identity
cat kitty-specs/<slug>/meta.json
```

Note the `baseline_merge_commit` (the SHA of the PR that preceded this mission,
if present) and `mission_type`. These anchor every git diff you will run.

```bash
# Scan the event log for the full state machine history
cat kitty-specs/<slug>/status.events.jsonl
```

The event log tells you: how many rejection cycles each WP had, which WPs were
forced (unusual transitions that bypassed normal flow), whether any WPs were
approved by arbiter override rather than clean review, and whether any WP has a
`ReviewerSelfApproval` event. A WP with 3+ rejection cycles that ended in an
arbiter-forced approval is a high-priority target for your analysis — the
disagreement history is a signal. A WP with `ReviewerSelfApproval` is also
high-priority: flag it as an independence/process risk and verify whether an
independent reviewer later re-reviewed it.

---

## Step 2: Absorb the Full Mission Contract

You cannot review what you do not understand. Read the full specification and
all contract artifacts before looking at code.

```bash
# The specification: goals, non-goals, locked decisions, FRs, NFRs, constraints
cat kitty-specs/<slug>/spec.md

# The technical design per track
cat kitty-specs/<slug>/plan.md

# The WP breakdown: subtasks, FR references, DoD per WP, FR coverage table
cat kitty-specs/<slug>/tasks.md

# Acceptance test scenarios (canonical test contract layer)
cat kitty-specs/<slug>/contracts/test-contracts.md

# CLI behavior contracts (what commands must and must not do)
cat kitty-specs/<slug>/contracts/cli-contracts.md

# File format contracts (schema expectations, migration story)
cat kitty-specs/<slug>/contracts/file-format-contracts.md
```

As you read, build a mental model of:

1. **What the spec explicitly forbids** (Non-Goals and "MUST NOT" clauses) — these
   are the easiest violations to detect and the most expensive to have shipped.
2. **What the spec locks** (Decisions) — any code that re-opens a locked decision
   is a drift finding regardless of whether the code "works".
3. **What the spec assumes but never states** ("invisible holes") — read Goals and
   Acceptance Criteria looking for implicit assumptions. For example, a goal
   that says "a fresh install works" assumes the version in `metadata.yaml`
   matches `pyproject.toml` — but if the spec never stated that as an FR, no
   test will catch it. These are your highest-value findings.

---

## Step 3: Load the Git Timeline

Establish a clean baseline-to-HEAD picture. Every code change since baseline
is the implementation's evidence. Anything in the spec that produced no diff
is suspect.

```bash
# What changed since the baseline commit?
# Use baseline_merge_commit from meta.json
git log <baseline_merge_commit>..HEAD --oneline

# Summary of changed files — use this to build your review coverage map
git diff <baseline_merge_commit>..HEAD --stat

# Full diff (for large missions, scope by directory first)
git diff <baseline_merge_commit>..HEAD -- src/
git diff <baseline_merge_commit>..HEAD -- tests/
git diff <baseline_merge_commit>..HEAD -- docs/
```

Build a **coverage map** from the diff stat: which files changed, and which
spec tracks they correspond to. Then invert the map: are there files that a
spec track required to change that do NOT appear in the diff? Missing changes
are often more important than the changes that exist.

For each WP, cross-reference owned files from its frontmatter:

```bash
# Read each WP's owned_files declaration
cat kitty-specs/<slug>/tasks/WP01-*.md | head -40
```

Then verify the claimed owned files actually appear in the diff:

```bash
git diff <baseline_merge_commit>..HEAD -- <owned_file_path>
```

A WP that declares ownership of a file that shows no diff is either incomplete
or its work was done in a different file than declared. Determine which.

---

## Step 4: Read the WP Review History

The WP review cycle files are a goldmine of documented problems. Every issue a
per-WP reviewer raised is a partial constraint on what was shipped. Your job is
to verify resolutions, not re-do the work.

```bash
# For each WP that had review cycles, read all cycle files
ls kitty-specs/<slug>/tasks/WP*/
cat kitty-specs/<slug>/tasks/WP01-*/review-cycle-*.md
cat kitty-specs/<slug>/tasks/WP02-*/review-cycle-*.md
# ... repeat for each WP
```

For each rejection cycle, identify:

- **What was flagged**: the blocking issues
- **What was promised**: the fix summary / remediation
- **What actually shipped**: verify against the diff

Issues that were flagged but then "resolved" via a forced approval or an arbiter
override warrant special scrutiny. Read the git commit that fixed each blocker:

```bash
# Find the commit message that addressed a specific review issue
git log --oneline --all | grep -i "WP0X"
git show <commit_sha> -- <file_flagged_in_review>
```

Deferred issues are a category of their own. A review cycle may have closed
with "deferred to follow-up issue #NNN" — if that deferral is not documented
anywhere post-merge (no GitHub issue, no CHANGELOG note), it is a silent
hole in the delivery.

---

## Step 5: FR Trace — Each FR from Spec to Test to Code

This is the core of the review. For every Functional Requirement, you need
a closed chain: **spec stated it → WP owned it → test verifies it → code
implements it**. A chain with any broken link is a finding.

Start from the FR coverage table in `tasks.md`:

```
| WP    | Spec FRs |
|-------|---------|
| WP01  | FR-001, FR-002, FR-003, ... |
```

For each FR:

```bash
# 1. Find the test(s) for this FR
grep -r "FR-NNN\|T<track>.<n>" tests/ --include="*.py" -l

# 2. Read the test — does it actually test what the FR requires?
# (Not just name it in a comment)
grep -n "FR-NNN" tests/<relevant_test_file>.py -A 10

# 3. Find the code that satisfies the FR
git diff <baseline_merge_commit>..HEAD -- src/ | grep -A 10 -B 5 "<key_symbol>"
```

The question for each test is not "does the test pass?" (you can assume it
does — the mission merged). The question is: **does the test actually constrain
the behavior the FR requires?**

A test that creates a synthetic fixture with `status: done` in frontmatter
when real status is stored in `status.events.jsonl` does not test what the FR
requires. It tests an imagined model that does not exist in production. This is
the "passing test, failing system" failure mode.

For every FR that maps to a test, ask: if someone deleted the implementation
code this test is supposed to cover, would the test fail? If the answer is "no,
the test would still pass because it uses a synthetic fixture," the test is a
false positive and the FR is effectively untested in production.

---

## Step 6: Drift and Gap Analysis

After the FR trace, step back and look at the mission as a whole. Drift is
when the implementation deviates from what the spec locked. Gaps are things the
spec required that no WP delivered.

### Non-goal invasion

Re-read every Non-Goal (NG-N). Then search the diff for anything that touches
the territory those non-goals define:

```bash
# Example: if NG-2 says "no backfill of historical missions"
# Search for any code that iterates existing kitty-specs/
git diff <baseline_merge_commit>..HEAD -- src/ | grep -n "kitty-specs\|missions_dir\|glob\|walk"
```

Code that touches out-of-scope territory is either a scope violation or needs
clear justification in the review record. Absent documentation, assume violation.

### Locked decision violations

For each locked Decision (D-N), identify the key invariant it establishes. Then
grep for code patterns that contradict it:

```bash
# Example: D-1 says "init MUST NOT initialize git, under any flag combination"
# Verify no git init call paths remain
git diff <baseline_merge_commit>..HEAD -- src/ | grep -n "git init\|init_git_repo\|subprocess.*git"
```

Locked decisions often have both positive requirements (the new behavior) and
negative requirements (the forbidden old behavior). Reviewers frequently verify
the positive side and forget the negative side. Verify both.

### Punted FRs

Cross-reference the FR list with the test files. An FR that appears in
`tasks.md`'s requirements coverage table but produces no `grep` hit in `tests/`
is a punted FR:

```bash
# For each FR-NNN in spec.md, check test coverage
grep -r "FR-NNN" tests/ --include="*.py" -l
```

A punted FR that was marked "Proposed" in the spec and never upgraded to
"Approved" in plan review is documentation drift only. A punted FR that was
marked "Approved" (accepted into the delivery contract) with no test coverage
is a delivery gap.

### NFR verification

For each Non-Functional Requirement (NFR) with a measurable threshold:

```bash
# Example: NFR-004 — new tests < 60s in aggregate
# Count new test files and estimate
git diff <baseline_merge_commit>..HEAD --stat | grep "tests/"

# Example: NFR-006 — project type-checking clean
# Check if any type-check suppression directives were added
git diff <baseline_merge_commit>..HEAD -- src/ | grep -n "type: ignore\|noqa"
```

Pay particular attention to performance NFRs — they rarely have automated
enforcement and are easy to skip.

### Recurring anti-patterns that have shipped past WP reviews

These are the patterns that per-WP review tends to miss and that mission review
reliably catches. When you are looking for drift, look here first:

**1. Tests pass against synthetic fixtures that do not exist in production.**
A WP claims to test FR-NNN but the test constructs a dict with the expected
shape instead of invoking the production code path that would produce that
shape. The test passes because the fixture is what the assertion expects;
production would never generate that shape. Ask: if I delete the
implementation code, does this test still pass? If yes, the FR is untested.
*Past cases*: a "decision resolution" test that built `{"status": "resolved"}`
as a literal instead of calling the resolver; a "widen response" test that
asserted `result["slack_thread_status"]` without verifying anything ever set
that field in the atomic block.

**2. New module has no live caller from a production entry point.**
A WP creates `src/<feature>/<new_module>.py` with full coverage tests, but
`grep -r "from <feature>.<new_module> import" src/ --include="*.py"` (excluding
the tests themselves) returns zero hits. The module is dead code, regardless
of test quality. *Past cases*: `run_specify_interview` and `run_plan_interview`
functions added by a WP that were never wired into the actual `specify` /
`plan` slash-command entry points. *Fix pattern*: the mission review
surfaces the dead code; a post-merge follow-up PR wires it into the real
entry point.

**3. FR is listed in a WP's `requirement_refs` frontmatter but no live
test asserts that FR's behavior.** The WP review sees the ref and assumes
coverage; the FR never appears in the assertion body of any test. Grep
each `FR-NNN` from the coverage matrix against `tests/`. Zero hits (excluding
comments) is a delivery gap, not a documentation gap. *Past cases*: a
mission shipped with FR-025 mapped to a WP whose tests asserted only that
`/widen` returned 200, never that `slack_thread_status == "pending"` appeared
in the response body.

**4. API-level input whitelist rejects valid new event types before the
reducer sees them.** The reducer is wired correctly; the gate upstream of it
has a hard-coded allow-list that was not updated. All the reducer tests pass
(they invoke the reducer directly, bypassing the gate). Production POSTs to
the endpoint return 400 on the new event type. *Past case*: a projection
mission added `DecisionPointOpened` / `DecisionPointResolved` event types
but the `/events/` endpoint's `validate_event_schema()` allow-list was not
extended — 100% of production events would have been rejected despite 100%
of unit tests passing.

**5. TOCTOU between an ORM `create` and an external-API side effect.**
The task calls an external API, then writes a DB row to record what happened.
If the DB write fails for any reason (transient DB error, Celery worker
killed mid-task, retry boundary), the next retry calls the external API
**a second time** with no record of the first call. *Detection*: walk every
Celery task that calls an external API followed by `Model.objects.create()`
and ask "what happens if the task dies between these two lines?" *Past case*:
`create_widen_slack_thread` posted the Slack opener before persisting the
`SlackThread` row; a transient DB error would have produced a duplicate
opener in the Slack channel on retry. *Fix pattern*: persist a placeholder
row BEFORE the external call, update it after.

**6. Silent empty-result return on hidden error.** A function wraps its
external dependency in `try: ... except Exception: return ""` (or `None`,
`[]`, `{}`). Tests that mock the happy path pass; production encounters a
transient error and the function returns an empty value that the caller
treats as valid. *Past case*: a "fetch permalink" helper returned empty
string on any Slack API error, which downstream code passed to a Slack
message template as the permalink field — users got opener messages with
an empty permalink and no error surfaced. *Detection*: grep for
`except Exception:` followed by `return ""`, `return None`, `return []`, or
`pass` inside any module changed by the mission.

**7. Locked Decision violated in a new code path.** The spec's Decisions
section says `MUST NOT do X under any flag combination`. A WP adds a new
flag-off branch that does X because "the flag is off so the invariant
doesn't apply" — but Locked Decisions are absolute, not flag-gated.
*Detection*: for each `MUST NOT` clause, grep the diff for code patterns
the clause forbids. *Past case*: a migration bug where a flag-off branch
re-ran `git init` despite a locked decision that init must never re-init.

**8. Ownership drift at file boundaries shared across WPs.** When WP07 and
WP08 each add a class to `apps/<feature>/serializers/__init__.py`, or when
WP04 and WP06 each add routes to `urls.py`, the add/add conflict is
resolved in the merge step but the *logical* ownership is ambiguous. Neither
WP's reviewer sees the other's additions. *Detection*: `git log --oneline`
on each shared file, look for multiple WPs in the same merge. The fix is
usually fine; the risk is hidden ownership ambiguity for future changes.

---

## Step 7: Risk Identification

This step requires active adversarial imagination. You are looking for things
that could go wrong that neither the spec nor the WP reviews anticipated.

### Boundary conditions

For every "MUST NOT happen under any flag combination" clause in the spec, the
implementation will have conditional logic to enforce it. Find that logic and
ask: is there a code path that bypasses the condition?

```bash
# Find all conditional branches near a key enforced behavior
git diff <baseline_merge_commit>..HEAD -- src/<key_file>.py | grep -B 5 -A 10 "if\|else\|try\|except"
```

The most common boundary failure: a guard that protects the "happy path" but
has an exception handler that silently re-enables the forbidden behavior.

### Error paths

For every new function introduced by this mission, trace what happens when it
fails. An error path that silently swallows exceptions and returns `None` or `""`
is a silent failure candidate:

```bash
# Find all try/except blocks in new code
git diff <baseline_merge_commit>..HEAD -- src/ | grep -n "except\|raise\|log\."
```

The pattern to look for: `try: <critical operation> except Exception: pass` or
`except Exception: return ""`. A function that returns an empty string when
something goes wrong (e.g., a function that builds a changelog block) will pass
its tests but produce wrong output in production. This is the "silent empty
result" anti-pattern.

### Dead code

A module with passing tests but no callers from live entry points is dead code.
The most common post-merge defect in this codebase:

```bash
# For every new module/class introduced, verify at least one live caller
# Example: verify new module is imported from live command path
git diff <baseline_merge_commit>..HEAD -- src/ | grep "^+.*def \|^+.*class " | head -30
```

For each new public function or class:

```bash
grep -r "from.*<new_module> import\|import <new_module>" src/ --include="*.py"
```

Zero grep hits on a new module from `src/` (not just from `tests/`) means the
feature is dead code, regardless of test coverage.

### Cross-WP integration gaps

Each WP was reviewed in isolation. The mission review is the first opportunity
to verify that all WPs integrate correctly. For missions with parallel WPs that
modified the same subsystem:

```bash
# Find files touched by multiple WPs (use owned_files from WP frontmatter)
# These are integration risk points
git diff <baseline_merge_commit>..HEAD -- src/<shared_file>.py
```

Pay special attention to `__init__.py` exports — multiple parallel WPs
commonly introduce conflicts here that are resolved at merge time but may
drop an export.

---

## Step 8: Security Review

For missions that touch CLI input handling, file I/O, subprocess execution,
authentication, or network calls, perform a focused security pass.

```bash
# Find all subprocess calls introduced by this mission
git diff <baseline_merge_commit>..HEAD -- src/ | grep -n "subprocess\|shell=True\|Popen\|run("

# Find all file path operations
git diff <baseline_merge_commit>..HEAD -- src/ | grep -n "open(\|Path(\|os.path\|glob("

# Find all HTTP/network calls
git diff <baseline_merge_commit>..HEAD -- src/ | grep -n "httpx\|requests\|urllib\|socket"

# Find all authentication / credential operations
git diff <baseline_merge_commit>..HEAD -- src/ | grep -n "credentials\|token\|password\|secret\|auth"
```

For each hit, ask:

- **CLI input validation**: Is user-supplied CLI argument used directly in a
  file path, subprocess command, or SQL-equivalent? Typer validation helps, but
  check that it is actually applied to the parameter being used.
- **Path traversal**: Any `Path(user_input)` that is not anchored to a known safe
  base directory (e.g., `tmp_path / user_input` without validation) can be
  exploited with `../../etc/passwd` style inputs.
- **Subprocess injection**: Any `shell=True` with dynamic content is a command
  injection risk. In a mission that modifies git operations, verify that branch
  names and commit messages are passed as list arguments, not formatted into a
  shell string.
- **Lock semantics**: For missions that touch file locking (e.g., auth refresh
  races), verify the lock scope covers the full critical section. A lock that
  wraps only the I/O operations but not the read-modify-write transaction
  creates a TOCTOU (time-of-check-time-of-use) window.
- **HTTP timeouts**: Any new HTTP call without an explicit timeout will hang
  indefinitely under network failure and block all other CLI invocations that
  depend on the same lock.
- **Credential clearing under failure**: Any path that clears credentials on
  error must verify those credentials are the same credentials that initiated
  the failing request. Clearing credentials that a concurrent process has
  already refreshed is data destruction.

---

## Step 8.5: Enforce the Hard Gates (Contract / Architectural / Cross-Repo E2E / Issue Matrix)

As of 2026-04-26 (mission `stability-and-hygiene-hardening-2026-04-01KQ4ARB`,
ADR `docs/adr/3.x/2026-04-26-3-e2e-hard-gate.md`), mission review
runs four hard gates in order. A FAIL on any gate produces a FAIL verdict
in Step 9 unless the operator-exception path documented below is used.

The CLI-to-SaaS sync transport these gates once exercised (the old daemon,
offline queue, and `SPEC_KITTY_ENABLE_SAAS_SYNC` floor scenario) was retired
in The Convergence — see
`docs/adr/3.x/2026-09-06-1-convergence-retirement-and-client-repo-inversion.md`
and [`docs/context/team-kitty.md`](../../../../../docs/context/team-kitty.md).
Do not pin `SPEC_KITTY_ENABLE_SAAS_SYNC` on the gate commands below: Gate 1's
`tests/contract/` suite does not read this flag at all, and none of Gate 3's
surviving E2E scenarios read the outer shell's value for it either.

### Gate 1: Contract tests (FR-023)

```bash
cd <spec-kitty-repo>
<test-runner> tests/contract/ -v
```

Non-zero exit ⇒ **HARD FAIL**. There is no exception path for contract
tests; a contract drift is a code defect by construction.

Record the exit code and any failing test names in your review report
under a new section `## Gate Results — Contract`.

### Gate 2: Architectural tests

```bash
cd <spec-kitty-repo>
<test-runner> tests/architectural/ -v
```

Non-zero exit ⇒ **HARD FAIL**. Layer-rule, public-import, and
package-boundary violations are code defects by construction.

Record the result under `## Gate Results — Architectural`.

### Gate 3: Cross-repo E2E (FR-038, FR-039, FR-041, C-010)

```bash
cd <spec-kitty-end-to-end-testing-repo>
<test-runner> scenarios/ -v
```

Non-zero exit ⇒ **HARD FAIL** unless an operator-exception artifact
exists at `kitty-specs/<slug>/mission-exception.md` and matches the
required schema (see below).

The three floor scenarios are the current supported cross-repo floor
(`EXPERIMENTAL-spec-kitty-end-to-end-testing`, `scenarios/`). The retired
fourth scenario, `saas_sync_enabled.py` (FR-040), was deleted with the sync
transport (commit `e59564b`, e2e issue #4) and is not part of the floor —
see spec-kitty#4949:

- `dependent_wp_planning_lane.py` — FR-001, FR-005, FR-038
- `uninitialized_repo_fail_loud.py` — FR-032, FR-039
- `contract_drift_caught.py` — FR-041

Future missions touching cross-repo behavior MUST add scenarios that
prove their behavior; verify any new mission-claimed cross-repo
behavior has an e2e scenario, and FAIL the review if it does not.

Record the result under `## Gate Results — Cross-Repo E2E`.

### Gate 4: Issue matrix (FR-037)

```bash
cat kitty-specs/<slug>/issue-matrix.json
```

`issue-matrix.json` is the single canonical artifact (C-008); a legacy
`issue-matrix.md` mission is still read via failover, never re-authored as
markdown. This file is scaffolded automatically during `spec-kitty tasks`
(finalize-tasks) for any mission whose `spec.md` references GitHub issues —
it should already exist by review time. If it is missing, regenerate it with
`spec-kitty agent mission finalize-tasks --mission <slug>` rather than
hand-authoring one; schema and a worked example live at
`src/specify_cli/cli/commands/review/ERROR_CODES.md`.

For every row in the matrix table, assert that the `verdict` cell is one of:

- `fixed`
- `verified-already-fixed`
- `deferred-with-followup`
- `in-mission` — the issue is being closed by a later WP in *this* mission.
  Accepted at per-WP `approved`; **rejected on the `done` transition** (mission
  merge), so it must reach a terminal verdict before the mission lands.

Any empty `verdict`, any literal value `unknown`, or any verdict outside
that allow-list ⇒ **HARD FAIL** with the failing row(s) listed. An `in-mission`
row that survives to mission `done` is likewise a hard fail.

For every `deferred-with-followup` row, assert that the `evidence_ref`
cell names a follow-up issue or a precise narrower follow-up issue
title. A bare "deferred" with no follow-up handle is a FAIL.

Record the result under `## Gate Results — Issue Matrix`.

### Operator exception path (Gate 3 only)

The cross-repo e2e gate has one allowed exception path: the dev SaaS
endpoint or some other environmental dependency is genuinely unreachable
on the reviewer's machine, and the failing scenario is not actually
about a code defect. In that case the operator authors a
`mission-exception.md` artifact under `kitty-specs/<slug>/`. The skill
accepts the exception only if all of the following are present:

| Field | Required content |
|-------|------------------|
| `**Operator**:` | Human name and contact |
| `**Date**:` | ISO date the exception was granted |
| `**Failing scenario**:` | Single scenario file::test, NOT a wildcard |
| `**Failing assertion**:` | The exact assertion line that failed |
| Narrative section | Why the failure is environmental, not a code defect |
| `## Reproduction command` | The exact command the operator ran |
| `## Follow-up` | Either a follow-up issue link or a written retry commitment in a documented window |

Reject the exception artifact (and FAIL the review) if any of these are
missing. Reject the exception if the `Failing scenario:` field names
more than one scenario — a blanket waiver across the whole e2e suite is
not allowed by C-010.

Reject the exception if `mission-exception.md` covers a scenario that
the skill can verify is actually a code defect (e.g., a test-runner
traceback that is not network-related). Operator exceptions are for
environmental blockers, not for deferred bugs.

Full operator runbook for the exception path:
[`docs/migrations/cross-repo-e2e-gate.md`](../../../../../docs/migrations/cross-repo-e2e-gate.md).

### Recording the gate results

The mission review report (Step 9) MUST include a top-level section
`## Gate Results` containing one subsection per gate. Each subsection
records the command run, the exit code, and a one-paragraph rationale.
For Gate 3, if an exception was granted, link to the exception artifact
and quote the operator's narrative.

A mission whose Gate Results show any HARD FAIL with no documented
exception receives the FAIL verdict in Step 9, regardless of how
clean the FR coverage table looks.

---

## Step 9: Generate the Mission Review Report

Produce a single structured markdown report. The report is your deliverable.
It must be self-contained — a reader who has not done any of the prior steps
must be able to understand each finding from the report alone.

```markdown
# Mission Review Report: <slug>

**Reviewer**: <your identity>
**Date**: <ISO date>
**Mission**: `<slug>` — <friendly_name>
**Baseline commit**: `<baseline_merge_commit>`
**HEAD at review**: `<git rev-parse HEAD>`
**WPs reviewed**: WP01..WPN

---

## Gate Results

### Gate 1 — Contract tests
- Command: `<test-runner> tests/contract/ -v`
- Exit code: <0 | non-zero>
- Result: PASS | FAIL
- Notes: <failing test names if any>

### Gate 2 — Architectural tests
- Command: `<test-runner> tests/architectural/ -v`
- Exit code: <0 | non-zero>
- Result: PASS | FAIL
- Notes: ...

### Gate 3 — Cross-repo E2E
- Command: `<test-runner> spec-kitty-end-to-end-testing/scenarios/ -v`
- Exit code: <0 | non-zero>
- Result: PASS | FAIL | EXCEPTION (with link to `kitty-specs/<slug>/mission-exception.md`)
- Notes: <failing scenarios; if EXCEPTION, quote the operator narrative>

### Gate 4 — Issue Matrix
- File: `kitty-specs/<slug>/issue-matrix.json` (or the legacy `issue-matrix.md`
  failover for a pre-migration mission)
- Rows: <count>
- Empty / `unknown` verdicts: <count, ideally 0>
- `deferred-with-followup` rows missing a follow-up handle: <count, ideally 0>
- Result: PASS | FAIL

A FAIL on any of Gates 1, 2, or 4 forces the Final Verdict to FAIL. A
FAIL on Gate 3 forces FAIL unless a valid `mission-exception.md` is
present.

---

## FR Coverage Matrix

| FR ID | Description (brief) | WP Owner | Test File(s) | Test Adequacy | Finding |
|-------|---------------------|----------|--------------|---------------|---------|
| FR-001 | ... | WP01 | tests/init/... | ADEQUATE | — |
| FR-NNN | ... | WPN | — | MISSING | [DRIFT-N] |

**Legend**: ADEQUATE = test constrains the required behavior; PARTIAL = test
exists but uses synthetic fixture that does not match production model;
MISSING = no test found; FALSE_POSITIVE = test passes even when implementation
is deleted.

---

## Drift Findings

### DRIFT-1: <Title>

**Type**: [NON-GOAL INVASION | LOCKED-DECISION VIOLATION | PUNTED-FR | NFR-MISS]
**Severity**: [CRITICAL | HIGH | MEDIUM | LOW]
**Spec reference**: <NG-N | D-N | FR-NNN | NFR-NNN>
**Evidence**:
- `git diff <baseline>..HEAD -- <file>` line NNN: `<exact code>`
- Or: absence of expected change in `<file>`

**Analysis**: <Why this is a drift, not a design choice. Cite the spec clause
that is violated or the expected change that is absent.>

---

## Risk Findings

### RISK-1: <Title>

**Type**: [BOUNDARY-CONDITION | ERROR-PATH | DEAD-CODE | CROSS-WP-INTEGRATION]
**Severity**: [CRITICAL | HIGH | MEDIUM | LOW]
**Location**: `<file>:<line_range>`
**Trigger condition**: <The specific input or state that activates this risk>

**Analysis**: <What happens when triggered, why it was not caught by existing
tests, and what the user-visible impact is.>

---

## Silent Failure Candidates

List every code path where the implementation returns a default value (empty
string, None, False) rather than raising on a condition that indicates
malfunction.

| Location | Condition | Silent result | Spec impact |
|----------|-----------|---------------|-------------|
| `src/.../foo.py:42` | `JSONL has no events` | returns `""` | FR-605: changelog block always empty |

---

## Security Notes

| Finding | Location | Risk class | Recommendation |
|---------|----------|------------|----------------|
| ... | ... | [PATH-TRAVERSAL | SHELL-INJECTION | LOCK-TOCTOU | UNBOUND-HTTP | CREDENTIAL-RACE] | ... |

---

## Final Verdict

**PASS** / **PASS WITH NOTES** / **FAIL**

### Verdict rationale

[One paragraph. State whether all FRs are adequately covered, whether any
locked decisions were violated, whether any release-gating NFRs missed their
threshold, whether any security findings are blocking. If FAIL, name the
specific findings that block release.]

### Open items (non-blocking)

[List findings that are not blocking release but should be addressed in a
follow-up mission.]

## Retrospective Reminder

The canonical post-merge sequence is: **mission review → author or verify retrospective
(`retrospect create`) → surface findings (`summary` aggregates; `synthesize` reviews proposals)**.

Under default 3.2.0 policy, the `retrospective.yaml` record is authored automatically during
merge. Verify it exists:

```bash
cat .kittify/missions/$(jq -r .mission_id kitty-specs/<slug>/meta.json)/retrospective.yaml
```

If the file is absent (older mission, or generation failed), author it:

```bash
spec-kitty retrospect create --mission <slug>
```

Then surface findings:

- `spec-kitty retrospect summary` — cross-mission aggregation (read-only; does NOT author)
- `spec-kitty agent retrospect synthesize --mission <slug>` — inspect proposals (dry-run by default)
- `spec-kitty agent retrospect synthesize --mission <slug> --apply` — apply proposals (mutates)

If the record is absent and `retrospect create` fails, escalate — the terminus facilitator
either did not run or was skipped without a recorded reason. Check `status.events.jsonl` for
`RetrospectiveCaptureFailed` events and their `remediation_hint` field.
```

---

## Key Rules

1. **You do not fix anything.** Your role is to document. If you find a bug,
   describe it precisely and note its severity. Do not patch code, do not amend
   tests, do not modify spec artifacts.

2. **Every finding must cite its evidence.** "I believe the test is inadequate"
   is not a finding. "Test at `tests/foo.py:42` creates a synthetic WP with
   `status: done` in frontmatter; real missions store status in
   `status.events.jsonl`; the test would pass if the implementation code were
   deleted" is a finding.

3. **Absence is evidence.** A file that the spec required to change but shows
   no diff is a finding. An FR that has no test hit is a finding. A locked
   decision whose violation was "approved by arbiter" without a rationale is
   a finding.

4. **Read the invisible holes.** The spec states what the system must do. It
   does not state every assumption it relies on. The reviewer's job includes
   surfacing those assumptions and checking whether the implementation honored
   them even though they were never written down.

5. **The review history is signal.** WPs with 3+ rejection cycles or arbiter
   overrides are high-priority targets. The disagreement that caused those
   cycles often reveals an unstated requirement or a design ambiguity that the
   implementation resolved in a way the spec author did not intend.

6. **Tests that pass are not proof.** A test that passes because it uses a
   synthetic fixture, not because the code is correct, is a liability, not an
   asset. The question is always: does this test constrain the actual runtime
   behavior?

7. **Security findings are never "low priority" for release-gating missions.**
   If the mission modifies auth, file locking, subprocess execution, or HTTP
   calls, any security finding that could affect a user in normal operation is
   at minimum MEDIUM severity.

8. **The verdict is binary for blocking findings.** PASS WITH NOTES is for
   non-blocking findings only. If any CRITICAL or HIGH finding exists that is
   not already documented as an accepted known issue, the verdict is FAIL.

9. **This skill does not use any generated review prompt.** Unlike
   `spec-kitty-runtime-review`, which defers to the CLI-generated prompt as
   the source of truth, this skill produces original analysis. The spec and
   contracts are the source of truth.

10. **Always include the retrospective reminder.** The report must end with a
    `## Retrospective Reminder` section that tells the operator the
    `retrospective.yaml` was authored at the runtime terminus, and that
    `spec-kitty retrospect summary` plus
    `spec-kitty agent retrospect synthesize --mission <slug>` review the
    captured record and apply staged proposals (dry-run by default). If the
    record is missing, escalate rather than proceed.
