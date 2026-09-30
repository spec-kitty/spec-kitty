---
title: '01 — Ticket Capture: Failure Modes & Suggested Implementations'
description: 'Ticket capture (2026-06-03) for the runtime and state overhaul: the failure modes, cited evidence, and proposed implementations drawn from GitHub issues.'
doc_status: deprecated
updated: '2026-06-03'
---
# 01 — Ticket Capture: Failure Modes & Suggested Implementations

Captured from GitHub issues on 2026-06-03. This document records *what the tickets say* — the
observed failure modes, the evidence cited, and the implementations proposed — with minimal
editorializing. Architectural interpretation lives in `05`.

---

## #1619 (parent, OPEN) — Unify mission execution context across coord/main/lane topology

Labels: `workflow, release, epic, launch-blocker, reliability, git, priority:P1`

### Thesis

> "Spec Kitty now has coordination-branch transactional truth, but command surfaces still resolve
> mission state, branch destination, worktree root, and prompt locations independently. Agents are
> becoming the reconciliation layer between main checkout, coordination worktree, lane worktree,
> current CWD, target branch, and prompt text."

### Failure class (recurring symptoms)

- Agents manually switching between main, coordination branch, and lane worktrees.
- Dependency checks reading stale state.
- `status.json` / `lanes.json` visibility differing by branch.
- `safe_commit` telling agents to checkout branches that conflict with orchestration topology.
- Prompts saying status commits to the target branch while modern lifecycle writes to the coordination branch.
- Agents bypassing normal Spec Kitty flow and dispatching implementation subagents directly.

### Root cause (as stated)

> "There is no canonical `MissionExecutionContext` or `MissionOperationContext` resolved once and
> passed through claim, implement, review, finalize, status, runtime, and orchestrator flows."

Split authority: writes treat the coord branch/worktree as truth; many reads and prompts treat main
checkout or target branch as truth; lane worktrees intentionally lack status files; agents reconcile manually.

### Acceptance criteria (verbatim intent)

1. Introduce **one explicit context object** (`MissionExecutionContext`) containing at least:
   `primary_root`, `current_cwd`, `mission_slug`, `mission_id`, `mid8`, `target_branch`,
   `coordination_branch`, `coord_worktree`, `execution_workspace`, `status_read_dir`,
   `status_write_dir`, `destination_ref`, `allowed_command_cwd`, `prompt_source_dir`.
2. All claim/implement/review/finalize/status/runtime/orchestrator paths consume this context rather than rebuilding raw paths.
3. **No raw mission-state reads** from `repo_root / "kitty-specs" / mission_slug` remain outside the context resolver, except explicitly documented legacy fallback paths.
4. Prompts/help render **from the context** and do not describe the target branch as status authority for modern coord-topology missions.
5. Add an **end-to-end regression**: clean repo → modern mission with coord branch/worktree → sparse lane worktree → run `next → implement → move-task → review → status` from **both main and lane CWD** → assert same WP state everywhere → assert no dirty partial status/decision/WP artifacts remain.

### Owner notes (from comments)

- Child issues #1615–#1618 were opened from the same five-paradigm "Debugger Debbie" investigation.
- **PR #1627 merged and closed #1615–#1618.** The parent stays open for the broader structural acceptance criteria.
- Stijn (2026-06-03): using this issue as the **main tracking point for CLI / execution-related problems** — "executions do not match intent" and "branching approach is causing issues".

---

## #1615 (CLOSED by #1627) — Status readers bypass coord-aware read path

**Failure:** Modern lifecycle writes status to the coordination worktree/branch, but several
readers inspect the main checkout mission directory directly → agents see stale/empty status →
false `dependencies_not_satisfied`, "missing canonical status", or "no-reviewable-WP" failures.

**Evidence (pre-fix):**
- Coord-aware path *existed* (`agent/workflow.py:233-240` `_canonical_status_feature_dir()`; used at `:1198-1203`; `agent/tasks.py:3709-3736`) but adoption was incomplete.
- `implement.py:747-753` dependency gate read `reduce(read_events(feature_dir))` where `feature_dir` was the **main checkout** → dependency WPs already `approved` in coord were seen as stale.
- `agent/workflow.py:1998-2004` review path read raw main-checkout events.
- `runtime/next/runtime_bridge.py:2033` used `repo_root / "kitty-specs" / mission_slug`.
- `agent/status.py:318-323` and `agent_utils/status.py:113-119` constructed main-checkout feature dirs.

**Suggested fix (and what #1627 did):** route all reads through `resolve_mission_read_path`.

---

## #1616 (CLOSED by #1627) — Agent prompts/help describe stale branch/status/lifecycle rules

**Failure:** Prompt/help strings are **active runtime surfaces** agents treat as truth, and they
described pre-coordination topology → agents instructed to switch dirs/branches and enforce rules
that contradict the CLI.

**Evidence (pre-fix):**
- `agent/workflow.py:787-793` — prompt: "Spec, plan, tasks, and status live in main repo: …/kitty-specs/…" (lanes intentionally sparse-exclude status).
- `agent/workflow.py:1549-1552` — prompt: "status is tracked in `{target_branch}` … auto-commit to `{target_branch}`" (contradicts `BookkeepingTransaction` → coord branch).
- `agent/workflow.py:1955` — docstring: "moves WP from `for_review` to `in_progress`" (canonical lifecycle uses `in_review`).
- `doctrine/missions/mission-steps/software-dev/implement/prompt.md:145-146` — "dependencies must be `done`" while `core/dependency_graph.py:55-59` accepts `approved` **or** `done`.

**Observed user impact:** agents reported "I need to be on main for workspace creation", "coord worktree is the right context", "checkout the coordination branch in the main repo", "sync coord branch status files to main", "dispatch implementation subagent".

---

## #1617 (CLOSED by #1627) — Runtime decision logging writes main checkout, commits to coord branch

**Failure:** `decisions.events.jsonl` written under the **main checkout**, then `safe_commit` called
with a **coord-branch** destination using the main checkout as `worktree_root`. `safe_commit`
requires `worktree_root` HEAD == `destination_ref`, so the path fails with a head mismatch **or
silently leaves uncommitted decision events** (the error is caught + logged WARNING so execution continues).

**Evidence (pre-fix):**
- `events/decision_log.py:86-88` rooted `_decisions_file` at `repo_root`.
- `events/decision_log.py:192-198` committed with injected `worktree_root`/`destination_ref`.
- `runtime/next/runtime_bridge.py:101-110` `_wrap_with_decision_git_log(...)` built the log from runtime state, not an explicit context.
- `git/commit_helpers.py:858-865` strict head-mismatch guard.

**Suggested fix (verbatim options):**
- write decision events into the coordination worktree path before committing, **or**
- route decision persistence through `BookkeepingTransaction.write_artifact`, **or**
- have `MissionExecutionContext` provide the correct worktree/destination pair.

---

## #1618 (CLOSED by #1627) — Post-transition side commits leave partial state

**Failure:** Some paths emit a status transition **transactionally** (coord), then perform a
**separate** direct WP/status write + `safe_commit` against the **target branch/main checkout**. If
the second step fails after the first succeeds, coord says the WP moved while main WP
history/frontmatter/status snapshot is dirty/refused/stale.

**Evidence (pre-fix):**
- `agent/tasks.py:2048-2056` emits via `emit_status_transition_transactional(...)`.
- `agent/tasks.py:2127-2137` then writes the WP file + `_collect_status_artifacts(feature_dir)` and commits via direct `safe_commit(... destination_ref=target_branch ...)`.
- `agent/tasks.py:734-744` protected-branch preflight remediation ("run from an allowed coordination/lane branch, or `--no-auto-commit`") **conflicts** with the prompt that says status is target-branch visible.

**Key framing — two atomicity domains:**
1. `BookkeepingTransaction` commits status to the coordination branch.
2. Direct `safe_commit` commits WP/frontmatter/history/status artifacts to the target branch/main worktree.

If domain 2 fails after domain 1 succeeds → partial state.

---

## #1602 (CLOSED) — lifecycle_events & status store share a file path with incompatible schemas

**Failure (architectural root of the lane-loop desync):** Two subsystems write the **same path**
`<feature_dir>/status.events.jsonl` with **incompatible schemas**:

| Writer | Schema |
|--------|--------|
| `status/store.py` (canonical) | `StatusEvent` — `wp_id`, `from_lane`, `to_lane`, `actor`, … |
| `status/lifecycle_events.py` | envelope — `aggregate_id`, `aggregate_type`, `event_type`, `payload`, `schema_version: 5.0.0` |

The reducer only understands `StatusEvent`, so once the envelope stream lands in that file the
materialized snapshot is **empty** → `read_events()` returns 0 → "WP has no canonical status — run
finalize-tasks" → implement→review loop wedged. The flip was observed at the review-claim commit
driven by `agent/workflow.py` (`start_review_status` → `_commit_workflow_change(...)`).

> **Note for the overhaul:** this is a *file-path/ownership collision* inside the status domain —
> distinct from the cross-surface split-authority class, but the same underlying disease: shared
> mutable state with no single owner. Related: #1588, #1589, #1597, #1598.

---

## #1348 (CLOSED) — Protected-branch guard: inconsistent commit bypass during implement

**Failure:** During `agent action implement`, two classes of commit happen on the **main checkout**:
1. "Planning artifacts" commits **silently land on the protected branch** (e.g. `decisions/index.json`, `issue-matrix.md`).
2. "WP transition" commits get **rejected** by the protected-branch guard.

User-visible: implement "breaks loudly" (hard exit) **after** already silently committing planning
artifacts to main. The user can't tell which commits succeeded without `git log`.

**Evidence:** `git/commit_helpers.py` `_PROTECTED_BRANCH_COMMIT_EXCEPTIONS` does not match
`"chore: planning artifacts for ..."`, so that commit uses a *different* bypass than the
(rejected) transition commits.

**Proposals (verbatim):**
1. Make the bypass rule consistent and visible — **all** implement-side commits land on main, **or all** land on the lane branch. No partial state.
2. If both classes are intentional, document the rule and surface in implement output what went where.

---

## #1627 (MERGED) — fix: eliminate split-authority failures in coord-branch topology

Closed #1615–#1618 via 5 WPs. Commit map:
- `737fbd3bb` **WP01** — stale prompt strings (#1616) + review-path reader (#1615)
- `6e536ba53` **WP02** — implement dependency gate + orchestrator-api coord-aware resolver (#1615)
- `3ac0e8957` **WP03** — DecisionGitLog coord worktree path + `worktree_root` (#1617); runtime_bridge `feature_dir` (#1615)
- `769e46d45` **WP04** — skip second `safe_commit` in move-task on coord+protected (#1618)
- `887b46dab` / `2e6810e12` **WP05** — 51 unit+regression tests + NFR-004 fallback guard

**Follow-on cleanups in the same PR:**
- DRY: extracted `mid8_from_slug()` into `branch_naming.py`, replacing 10 inline copies.
- Edge-case fix: inline `str.isupper()` heuristic returned `False` for all-digit ULID tails → replaced with Crockford base32 regex `_MID8_RE`.

**Crucial limitation:** #1627 made specific *read* sites coord-aware and corrected specific prompt
strings. It did **not** introduce a unified context object, and it left many surfaces still
deriving context independently (see `02`, §4). That residue is what epic #1619 still tracks.

---

## Cross-ticket pattern summary

| Pattern | Tickets | One-line essence |
|---------|---------|------------------|
| **Split read authority** | #1615 | Reads hit main/lane; writes hit coord |
| **Stale agent-facing contract** | #1616 | Prompts are runtime surfaces describing the wrong topology |
| **Wrong worktree/branch pairing on commit** | #1617, #1348 | `worktree_root` ≠ `destination_ref`; inconsistent protected-branch bypass |
| **Multiple atomicity domains** | #1618 | Transactional coord emit + separate direct main commit = partial state |
| **Shared mutable file, no owner** | #1602 | Two schemas, one `status.events.jsonl` path → log clobber |
| **No single context authority** | #1619 | The structural root all of the above mask |
