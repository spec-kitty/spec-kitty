---
work_package_id: WP01
title: Kernel git owner
dependencies: []
requirement_refs:
- FR-003
- FR-004
- FR-005
- FR-006
- FR-014
- NFR-002
- NFR-003
- NFR-004
- C-001
- C-007
- C-008
planning_base_branch: claude/git-path-remediation-rnrzfz
merge_target_branch: claude/git-path-remediation-rnrzfz
branch_strategy: Planning artifacts for this mission were generated on claude/git-path-remediation-rnrzfz. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/git-path-remediation-rnrzfz unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-git-paths-are-data-01M3SSXR
base_commit: b99f6f41b251862ea70c120c90299665579178ab
created_at: '2026-09-30T19:02:03.209908+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Foundation
history:
- at: '2026-09-30T19:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/kernel/git/
create_intent:
- src/kernel/git/__init__.py
- src/kernel/git/runner.py
- src/kernel/git/paths.py
- src/kernel/git/listing.py
- tests/kernel/test_git_runner.py
- tests/kernel/test_git_paths.py
- tests/kernel/test_git_listing.py
- tests/git/test_kernel_git_real.py
- tests/architectural/_git_path_listing_census.py
- tests/architectural/test_git_path_listing_census.py
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- src/kernel/git/**
- tests/kernel/test_git_runner.py
- tests/kernel/test_git_paths.py
- tests/kernel/test_git_listing.py
- tests/git/test_kernel_git_real.py
- tests/architectural/_git_path_listing_census.py
- tests/architectural/test_git_path_listing_census.py
- src/kernel/README.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP01 – Kernel git owner

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

- **Has review feedback?**: check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission git-paths-are-data-01M3SSXR`).
- Address every feedback item before handing back.

---

## Objectives & Success Criteria

- New package `src/kernel/git/` is the ONE owner of running git for path listings: a command-agnostic runner, NUL-delimited listing, one lossless decode rule, the `GitPath` value type and typed entries (FR-003..FR-006, FR-014).
- Every public function matches `contracts/kernel-git-api.md` and the entities in `data-model.md`.
- Unit tests built from REAL git output (not hand-written strings) cover: a path with a space, a non-ASCII path with `core.quotePath=true`, a file literally named `p -> q`, rename/copy entries in both `status -z` (`XY new\0old\0`) and `diff --name-status -z` (`R100\0old\0new\0`) orders, a collapsed directory entry (`!! dir/`), a literal `*` filename (FR-014), invalid UTF-8 bytes round-tripping via surrogateescape, and git failure raising `GitCommandError` (NFR-004).
- ≥ 90% line coverage of `src/kernel/git/` from these tests (NFR-003).

## Context & Constraints

- Spec: `kitty-specs/git-paths-are-data-01M3SSXR/spec.md`; plan: `plan.md` (Design §1–10); API contract: `contracts/kernel-git-api.md`; data model: `data-model.md`; research: `research.md` (R1–R9).
- Charter: `.kittify/charter/charter.md` — campsite first (standing order 2), red-first (4), gate discipline (5), no heavy suites in mission (run targeted tests + the named gate files only).
- CLAUDE.md code style: ruff, `ruff format --check`, mypy zero issues on changed files; complexity ≤ 15; no new `# noqa` / `# type: ignore`.
- **C-007**: never move a destructive git command (`reset --hard`, `update-ref`, `worktree remove`, `stash`, `clean`) into `kernel.git`; only path *listings* move.
- **FR-013**: when a site today treats git failure as "no paths" (`check=False` then parse stdout, or a helper returning `()`/`None`), decide: a guard (it protects data or gates a transition) lets `GitCommandError` propagate; an advisory/display site catches `GitCommandError` at the call site with a one-line comment giving the reason. Record every decision in the tracer `kitty-specs/git-paths-are-data-01M3SSXR/research/design-decisions.md` (orchestrator appends; list them in your hand-off).
- **Boolean dirtiness** (`bool(stdout.strip())`) becomes `bool(status_entries(...))`; keep the same `untracked`/`ignored` options and pathspecs as the original argv.
- **Paths**: callers that need `str` use `str(entry.path)` / `p.as_posix()`; never re-parse a rendered line.
- Tests: use real temporary git repos (no git mocks) for at least one quoted-path case per migrated guard. Put new test files where listed in `owned_files`; small edits to existing tests of the migrated module are allowed with a one-line rationale in the hand-off.

## Branch Strategy

- **Strategy**: lanes (one worktree per computed lane from `lanes.json`)
- **Planning base branch**: `claude/git-path-remediation-rnrzfz`
- **Merge target branch**: `claude/git-path-remediation-rnrzfz`

> Populated by `spec-kitty agent mission finalize-tasks`. Enter the workspace with `spec-kitty implement WP01 --mission git-paths-are-data-01M3SSXR`; never reconstruct the path.

## Subtasks & Detailed Guidance

### Subtask T001 – `runner.py`

- **Purpose**: the single subprocess seam (C-007: knows no specific command).
- **API**:
  ```python
  @dataclass(frozen=True)
  class GitResult: returncode: int; stdout: bytes; stderr: bytes
  class GitCommandError(RuntimeError):  # argv, cwd, returncode, stderr (decoded text)
  def run_git(cwd: Path, *args: str, env: Mapping[str, str] | None = None,
              timeout: float | None = None, check: bool = True) -> GitResult
  def decode_path(raw: bytes) -> str   # raw.decode("utf-8", "surrogateescape")
  ```
- `env` is passed through **unchanged** (AC-F1: the merge pipeline hands in its own env); `timeout=None` default (ref_advance has none today).
- `FileNotFoundError` (git missing) and `subprocess.TimeoutExpired` become `GitCommandError` (returncode `-1`).
- `check=True` raises on non-zero; `check=False` returns the result (used by `is_tracked`, which interprets exit 1).
- Message format: `git <args> failed in <cwd> (exit N): <stderr first line>`.
- Declare `__all__`. No `shell=True`. `capture_output=True`, bytes (no `text=True`).

### Subtask T002 – `paths.py`: `GitPath`

- Frozen dataclass, `parts: tuple[str, ...]`, `__slots__`-friendly, hashable, orderable (sort by parts).
- `GitPath.parse(text: str) -> GitPath`: strip exactly one trailing `/`; split on `/`; reject a leading `/`, empty inner component, `.` or `..` with `ValueError`; `""` → root (`parts == ()`).
- Relations: `is_ancestor_of(other)` (strict component prefix), `contains(other)` (== or ancestor), `overlaps(other)` (`self.contains(other) or other.contains(self)`), root overlaps nothing and contains nothing (an empty path never obstructs — matches today's `if not path: return False`).
- `__str__`/`as_posix()` → `"/".join(parts)`; `name` → last part or `""`.
- Invariant test: `GitPath.parse(str(p)) == p` (hypothesis not required; parametrize).

### Subtask T003 – `listing.py`: `status_entries` + `StatusEntry`

- `status_entries(cwd, *, pathspecs=(), untracked="normal", ignored=False, glob=False, env=None) -> tuple[StatusEntry, ...]`
  - argv: `[*("--literal-pathspecs",) if not glob, "status", "--porcelain=v1", "-z", f"--untracked-files={untracked}", *(["--ignored"] if ignored), "--", *pathspecs]` (global options go BEFORE the subcommand: `git --literal-pathspecs status ...`). Omit `--` block when no pathspecs.
  - Parse NUL records: `XY<space>path`; when `X` or `Y` is `R` or `C` the NEXT record is the original path.
  - `StatusEntry(xy, path: GitPath, orig_path: GitPath | None, is_directory: bool)`; `is_directory` = raw path ended in `/`.
  - Properties: `is_untracked` (`??`), `is_ignored` (`!!`), `is_conflicted` (`DD AU UD UA DU AA UU`), `index` (`xy[0]`), `worktree` (`xy[1]`), `display()` → `f"{xy} {path}"` plus `f" <- {orig}"` for renames and a trailing `/` when `is_directory` (display only; never parsed back).
- `untracked` accepts `"no" | "normal" | "all"` (validate).

### Subtask T004 – remaining queries

Implement exactly the contract table: `tree_paths` (`ls-tree -r --name-only -z <ref> [-- specs]` → `frozenset[GitPath]`), `changed_paths` (`diff --name-only -z --no-renames [--cached] [--diff-filter=F] *revs [-- specs]` → tuple, git order), `changed_entries` (`diff --name-status -z [--no-renames|-M]` → `NameStatusEntry`; rename/copy records are `status\0old\0new\0` → `path=new, orig_path=old`), `commit_paths` (`show --name-only --format= -z --no-renames <commit>`), `log_paths` (`log -z --name-only --format= <range> [-- specs]`, de-duplicated preserving first-seen order), `tracked_paths` (`ls-files -z [-- specs]`), `index_entries` (`ls-files --stage -z` → `IndexEntry(mode, oid, stage, path)`; record is `mode SP oid SP stage TAB path`), `is_tracked` (`ls-files --error-unmatch -- path`, `check=False`: exit 0 → True, exit 1 → False, else raise).
- Contract additions from the post-tasks squad (each with a fast argv test and, where it changes parsing, a real-git case):
  - `timeout: float | None = None` keyword on every query, passed to `run_git`; `GitCommandError.timed_out: bool` (True only for `TimeoutExpired`). Sites with a timeout today (watcher, occupancy) keep it.
  - `status_entries(untracked=None)` omits `--untracked-files` so git honours `status.showUntrackedFiles` (sites whose argv has no flag today).
  - `status_entries(optional_locks=False)` → `git --no-optional-locks status …` (read-only probes).
  - `changed_paths(renames=False)`: `True` passes `-M` and returns the NEW path only for a rename; about a dozen `--name-only` sites rely on git's default rename detection, so migrate them with `renames=True` to keep NFR-001 behaviour byte-for-byte.
  - `numstat_entries(cwd, *revs, cached=False, pathspecs=(), …)` → `diff --numstat -z --no-renames` → `NumstatEntry(added: int | None, deleted: int | None, path)` (`-` for binary → `None`), for `live_work/watcher.py`.
  - `tree_entry(cwd, ref, path)` → `ls-tree -z <ref> -- <path>` (literal) → `TreeEntry(mode, type, oid, path) | None`, for `consolidation/git_probes.py`.
  - `index_entries(tags=True)` → `ls-files -v --stage -z` fills `IndexEntry.tag` (`H`, `S`, `h`, …) for `git/report_transaction.py`'s skip-worktree check.
  - `commit_paths` docstring: a merge commit lists nothing (combined diff) unless `first_parent=True` (`--first-parent -m`); add that option.
- All path args: `--literal-pathspecs` unless `glob=True`. Only git-2.25 flags (C-008; no `ls-files --format`).
- Export only names a later WP will call. `tests/architectural/test_no_dead_symbols.py` scans every `src/` module and fails on an `__all__` name with no `src/` caller, so WP01 lands with its callers in the same PR (the mission ships as one PR). If WP02 is ever cut alone as a hotfix (C-009), that cut prunes the kernel exports WP02 does not call; the pruning is mechanical.

### Subtask T005 – unit tests

- `tests/kernel/test_git_runner.py`, `test_git_paths.py`, `test_git_listing.py`. Use a `tmp_path` repo helper (init `-b main`, user config, `commit.gpgsign false`). Mark with the repo's usual markers (look at `tests/kernel/test_git_topology_fast.py` for conventions; add `pytest.mark.git_repo` where real git runs).
- Cases listed in Objectives, plus: empty listing → `()`; pathspec filtering; `untracked="all"` vs `"normal"` (collapsed `?? dir/` vs files); `ignored=True` collapsed `!! .venv/`; `is_tracked` for tracked/untracked/missing path; `run_git` failure message contains the subcommand and stderr; env passthrough (set `GIT_AUTHOR_NAME` probe via `git var GIT_AUTHOR_IDENT`).

### Subtask T006 – README + C-007 test

- Add a `kernel.git` bullet to `src/kernel/README.md` (what it owns; "callers never build path-listing argv").
- In `test_git_runner.py`, a test that scans `src/kernel/git/*.py` source for destructive literals (`"reset"`, `"--hard"`, `"update-ref"`, `"worktree"`, `"stash"`, `"clean"`, `"rm"`) and asserts none appear as string constants (AST, not text grep, so docstrings don't count).

### Subtask T006b – shared census module (the "is this site migrated?" check)

- `tests/architectural/_git_path_listing_census.py` (private helper, no test functions): `census(paths: Iterable[Path]) -> list[Hit]` classifies every `ast.Call` whose string-constant arguments (list/tuple literal argv AND positional `Constant` args such as `_git(root, "status", "--porcelain=v1")`; skip `Starred`) form a git path listing without `-z`:
  - `status` with `--porcelain`, `-s` or `--short` (exempt: `--porcelain … -z` only; `--exit-code` is NOT an exemption);
  - `diff`/`show`/`log`/`diff-tree`/`diff-index`/`diff-files` with `--name-only`, `--name-status`, `--numstat`, `--raw`, `--stat` or `--summary`, and bare `diff-tree`/`diff-index`/`diff-files`;
  - `ls-files`, `ls-tree`, `check-ignore` (exempt with `-q`/`--quiet`).
  Plus text-parsing tells in the same function: `" -> " in x` / `.split(" -> ")` / `.rsplit(" -> ")`, `[3:]` slicing of a porcelain line, `.split("\0")`/`.split("\x00")` outside `kernel/git`.
- `tests/architectural/test_git_path_listing_census.py` (fast): planted-hit fixtures for every form above (list argv, positional argv, `-s`, `check-ignore`, `" -> "`, `[3:]`) and planted clean fixtures (`-z`, `check-ignore -q`, kernel queries). Record the base count on the branch point in the hand-off (the prototype found 85 hits in 47 files; recount with the widened rule).
- WP03–WP07 reviewers run `census(owned_files)` and require 0 hits; WP08 wraps it in the empty-allowlist gate.

## Test Strategy

- `uv run --frozen pytest tests/kernel/test_git_runner.py tests/kernel/test_git_paths.py tests/kernel/test_git_listing.py -q --cov=src/kernel/git --cov-report=term-missing` (≥ 90%).
- `uv run --frozen pytest tests/architectural/test_layer_rules.py tests/architectural/test_git_topology_one_copy.py -q` (kernel imports nothing above it; topology primitive untouched).

Always also run: `uv run --frozen ruff check <changed files>`, `uv run --frozen ruff format --check <changed files>`, `uv run --frozen mypy <changed src files>`, and `make test-fast` is NOT required per WP (the orchestrator runs it at closeout).

## Risks & Mitigations

- Windows: git for Windows emits UTF-8 with `-z`; `surrogateescape` keeps undecodable bytes lossless. Do not use `os.fsdecode`.
- `status -z` puts the NEW path first for renames, `diff --name-status -z` puts OLD first — test both from real output.
- A `--` before an empty pathspec list changes nothing, but keep argv minimal.

## Review Guidance

- Verify each contract function against `contracts/kernel-git-api.md` and the real-output tests.
- Verify fail-closed: no query swallows a non-zero exit.
- Verify `GitPath` rejects `..` and absolute paths and that root overlaps nothing.
- Confirm ruff, format and mypy ran on changed files and were clean.
- Confirm no destructive git literal moved into `src/kernel/git/` (C-007).

## Activity Log

- 2026-09-30T19:20:00Z – system – Prompt created.
