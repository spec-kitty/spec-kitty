---
work_package_id: WP01
title: 'Kernel: one owner of remote contact'
dependencies: []
requirement_refs:
- FR-017
- NFR-001
- NFR-002
- C-001
planning_base_branch: claude/happy-keller-r38xig
merge_target_branch: claude/happy-keller-r38xig
branch_strategy: Planning artifacts for this mission were generated on claude/happy-keller-r38xig. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/happy-keller-r38xig unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-second-clone-origin-reconciliation-01M48V8W
base_commit: 823ac378c636a6483fbae6f99a4941508de9b8ba
created_at: '2026-10-06T15:28:07.865655+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Foundation
history:
- at: '2026-10-06T15:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/kernel/git/
create_intent:
- src/kernel/git/remote.py
- tests/kernel/test_git_remote.py
- tests/terminus/two_clone_support.py
execution_mode: code_change
model: ''
owned_files:
- src/kernel/git/remote.py
- src/kernel/git/__init__.py
- src/kernel/git/runner.py
- tests/kernel/test_git_remote.py
- tests/terminus/two_clone_support.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Kernel: one owner of remote contact

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission second-clone-origin-reconciliation-01M48V8W`). If this WP was returned from review, every feedback item is your TODO list.

---

## Objectives & Success Criteria

Create `src/kernel/git/remote.py`: the ONE place in `src/` that runs a git command contacting a remote, plus the ref-level helpers the evidence gates need. It is the "how" layer (mission git-paths-are-data split): it knows refs and remotes, never Missions, lanes or status (C-001).

Done when:
- every function in `contracts/kernel-git-remote.md` exists, is typed, bounded (timeout) and non-prompting;
- `tests/kernel/test_git_remote.py` passes against a REAL bare `file://` remote, and was red before the implementation (commit the tests first);
- `tests/terminus/two_clone_support.py` provides the shared bare-remote + second-clone helper the three regression tests (WP04, WP06, WP07) will use;
- ruff, ruff format (`--force-exclude`), mypy clean on the new files; every function C901 ≤ 15.

## Context & Constraints

- Read first: `kitty-specs/second-clone-origin-reconciliation-01M48V8W/{spec.md,plan.md,research.md,data-model.md,contracts/kernel-git-remote.md}` and `traces/design-decisions.md`.
- Build ON `kernel.git.runner.run_git(cwd, *args, env=..., timeout=..., check=...)` — do NOT add a second runner (post-plan squad). `GitCommandError(timed_out=True)` already exists.
- Layering: `src/kernel/` must not import `specify_cli`, `charter`, `mission_runtime` (enforced by `tests/architectural/test_layer_rules.py`).
- Charter: every module under `src/kernel/` declares `__all__` (C-007 of the charter); `tests/architectural/test_no_dead_symbols.py` walks `__all__` and wants a `src/` caller for every name. **Expected interim red**: WP02 and WP03 add the callers. Note this in your commit message and the review handoff; do not add fake callers.
- Read `src/specify_cli/git/remote_probes.py` (#4979): its `_no_prompt_env` + `_DEFAULT_SSH_COMMAND` move here VERBATIM as `no_prompt_env()` (WP02 rewires `remote_probes` to import it; do not edit `remote_probes.py` here — WP02 owns it).
- Read `src/specify_cli/consolidation/push_preflight.py:248-275` — its `rev-list --left-right --count a...b` is the shape `divergence()` must reproduce (WP02 re-points it).
- C-006: no "sync" in any identifier or message.

## Branch Strategy

- **Strategy**: lanes; the execution worktree for this WP is allocated by `spec-kitty implement WP01` from `lanes.json`.
- **Planning base branch**: `claude/happy-keller-r38xig`
- **Merge target branch**: `claude/happy-keller-r38xig`

## Subtasks

### T001 — Red-first kernel tests against a real bare remote

**Purpose**: the contract is pinned by behaviour on real git before any code exists (ATDD; charter "ATDD-First Discipline").

**Steps**
1. Create `tests/kernel/test_git_remote.py`, `pytestmark = [pytest.mark.git_repo]` (check `pytest.ini` markers; kernel tests are fast but need git).
2. Fixture: `tmp_path / "origin.git"` via `git init --bare -q`; a working clone `work` with an initial commit on `main` pushed; isolate global config with `monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(tmp_path / "gitconfig"))`, `HOME`, `XDG_CONFIG_HOME` (#5602 hazard) and set `user.name`/`user.email` locally in each repo.
3. Cases (each a separate test):
   - `resolve_remote`: branch with `branch.<b>.remote=up` → `"up"`; no branch config + one remote named `fork` → `"fork"`; two remotes incl. `origin` → `"origin"`; two remotes neither `origin` → `None`; no remotes → `None`.
   - `tracking_ref("origin", "kitty/mission-x-lane-a")` → `"refs/remotes/origin/kitty/mission-x-lane-a"`.
   - `remote_heads(work, "origin", ["main", "absent"])` → `{"main": <sha>}` (absent omitted).
   - `remote_heads` against a remote URL pointing at a deleted path → raises `RemoteUnreachable` (and is not `remote_missing`).
   - `fetch_branches(work, "origin", ["feature"])` after another clone pushed `feature` → `refs/remotes/origin/feature` resolves to the pushed sha; `refs/heads/feature` is NOT created.
   - `fetch_branches` with an unreachable remote → `RemoteUnreachable`.
   - `divergence(work, "main", "refs/remotes/origin/main")` for: equal (0,0), local ahead 1 (ahead=1, behind=0), behind 2, diverged (1,2).
   - `divergence(..., paths=["a/status.events.jsonl"])`: remote-only commits that touch only `b.txt` → `behind == 0`; one that touches the path → `behind == 1`.
   - `no_prompt_env()` sets `GIT_TERMINAL_PROMPT=0` and preserves a pre-set `GIT_SSH_COMMAND` with ` -o BatchMode=yes` appended.
4. Commit the tests alone; run them; they must fail (ImportError is fine as the red).

### T002 — `no_prompt_env`, `RemoteUnreachable`, timeouts

- `LS_REMOTE_TIMEOUT: float = 5.0`, `FETCH_TIMEOUT: float = 15.0` (NFR-001), `CLONE_TIMEOUT` for doctrine (pick a generous bound, e.g. 120.0, document it).
- `no_prompt_env(base: Mapping[str, str] | None = None) -> dict[str, str]` — verbatim semantics of `remote_probes._no_prompt_env` (copy its docstring rationale).
- `class RemoteUnreachable(GitCommandError)` with a `remote: str` attribute; construct it from the caught `GitCommandError` (timeout or non-zero exit). Keep the message one line: `remote <name> unreachable: <first stderr line>`.

### T003 — `resolve_remote`, `tracking_ref`

- `resolve_remote(cwd: Path, branch: str) -> str | None`: FR-017 rule. Read `git config --get branch.<branch>.remote` (exit 1 = unset), else `git remote` list: exactly one → it; `origin` present → `"origin"`; else `None`. Local config reads only — no network. A `branch.<b>.remote` of `.` (local) → treat as unset.
- `tracking_ref(remote: str, branch: str) -> str`.

### T004 — `remote_heads`, `fetch_branches`, `divergence`

- `remote_heads(cwd, remote, branches, *, timeout=LS_REMOTE_TIMEOUT) -> dict[str, str]`: one `ls-remote --heads <remote> refs/heads/<b>...`; parse `<sha>\t<ref>`; exact-ref match only; raise `RemoteUnreachable` on any failure. Empty `branches` → `{}` without contacting.
- `fetch_branches(cwd, remote, branches, *, timeout=FETCH_TIMEOUT) -> None`: one `fetch --no-tags --no-write-fetch-head <remote> +refs/heads/<b>:refs/remotes/<remote>/<b> ...` (check `--no-write-fetch-head` exists in git ≥ 2.25; if not, drop it). Never writes `refs/heads`. Empty list → no contact.
- `@dataclass(frozen=True) class Divergence: ahead: int; behind: int` with `diverged` property.
- `divergence(cwd, local, remote_ref, *, paths=()) -> Divergence`: one `rev-list --left-right --count <local>...<remote_ref>` (`-- <paths>` when given). Left = ahead, right = behind. Document that `ahead` is meaningful only unscoped.

### T005 — `describe_remote_head`, doctrine wrappers, exports

- `describe_remote_head(cwd, remote, *, timeout=LS_REMOTE_TIMEOUT) -> str | None`: the default-branch probe `protection_policy.py:467` does today (`remote show <remote>`, parse `HEAD branch:`); returns `None` on failure (that caller treats failure as unknown — keep that).
- `clone_repository(url, dest, *, branch=None, depth=None, timeout=CLONE_TIMEOUT, env=None) -> GitResult` and `fetch_tags(cwd, remote, *, timeout=FETCH_TIMEOUT, env=None) -> GitResult` — thin bounded wrappers matching the argv `src/specify_cli/doctrine/sources/git_source.py:88` and `:146` build today (read them; mirror their flags exactly so WP02's swap is behaviour-preserving).
- Export everything from `kernel/git/__init__.py` and update its docstring: the package now owns path reading AND remote contact ("callers never build a remote-contacting git argv themselves; `tests/architectural/test_remote_contact_owner.py` enforces that" — WP02 adds that test).

### T006 — Shared two-clone helper (`tests/terminus/two_clone_support.py`)

- Not a test module (no `test_` prefix). Functions:
  - `make_bare_remote(tmp_path) -> Path`
  - `attach_and_push(repo, bare, refs: Sequence[str], name="origin")`
  - `clone_from(bare, dest) -> Path` (sets local `user.name`/`user.email`)
  - `isolated_git_env(monkeypatch, tmp_path)` (HOME, XDG_CONFIG_HOME, GIT_CONFIG_GLOBAL, GIT_TERMINAL_PROMPT=0)
  - `unreachable_remote(repo, name="origin")` (re-point the remote URL at a deleted path)
- Reuse `tests/terminus/conftest.py` helpers (`_git`, `git_rev`) by import where possible; do not duplicate `build_coord_mission`.
- Add one smoke test inside `tests/kernel/test_git_remote.py` that uses the helper (so it is exercised in this WP).

## Test Strategy (run exactly these)

```bash
.venv/bin/python -m pytest -q tests/kernel/test_git_remote.py tests/kernel/test_git_listing.py
.venv/bin/python -m pytest -q tests/architectural/test_layer_rules.py
.venv/bin/ruff check src/kernel/git tests/kernel/test_git_remote.py tests/terminus/two_clone_support.py
.venv/bin/ruff format --check --force-exclude src/kernel/git tests/kernel/test_git_remote.py tests/terminus/two_clone_support.py
.venv/bin/mypy src/kernel/git/remote.py
```
Record commands and counts in the Activity Log. No heavy suites.

## Definition of Done

- [ ] Tests committed before implementation and shown red (note the red run in the Activity Log).
- [ ] All T001 cases green; no network beyond the local `file://` remote.
- [ ] `run_git` reused; no `subprocess` import in `remote.py`.
- [ ] `__all__` declared; docstrings name the requirement IDs (FR-013, FR-017, NFR-001, NFR-002).
- [ ] Interim `test_no_dead_symbols` red for the new names is documented, not papered over.

## Risks

- `--left-right` orientation: verify with the ahead/behind test, do not guess.
- Windows: paths passed to git as `str(path)`; no shell.

## Reviewer Guidance

Verify red→green (tests commit precedes implementation). Check no second runner, no `specify_cli` import, timeouts on every contact, `remote_missing` impossible to infer from a failed contact (`remote_heads` raises instead of returning `{}`).

## Post-tasks squad folds (binding — supersede conflicting text above)

- NFR-002 test: a remote whose URL is `ssh://git@127.0.0.1:1/nonexistent.git` (or an `ext::` / unroutable host) must classify `RemoteUnreachable` within the timeout without prompting (env asserts `GIT_TERMINAL_PROMPT=0` and `BatchMode=yes`); mark it `timing`-free (bound the assertion to < 2 × timeout).

## Activity Log

- 2026-10-06 — prompt generated.
