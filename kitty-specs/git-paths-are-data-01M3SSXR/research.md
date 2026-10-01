# Research: Git paths are data, not text

Grounding squad (architect lens, 2026-09-30) on base `74373ec9`, git 2.43 scratch repro.

## R1 — Why `core.quotePath=false` is not enough
- **Decision**: request `-z` output for every path listing.
- **Rationale**: `git status --porcelain` quotes a path containing a space even with `core.quotePath=false`; `ls-tree`, `ls-files`, `diff --name-*` do not. Non-ASCII, `"`, `\` and control characters are quoted on every verb unless `-z`. Only `-z` is lossless everywhere.
- **Alternatives**: decode C-style quoting (`"\303\251"`) in each parser — rejected: a second encoding to get right in N places, and `" -> "` rename splitting stays ambiguous.

## R2 — Decode rule
- **Decision**: `bytes.decode("utf-8", "surrogateescape")` in one function.
- **Rationale**: lossless round trip to the filesystem (`os.fsencode` on POSIX); git for Windows emits UTF-8. Seven existing `-z` parsers disagree (`surrogateescape`, `errors="replace"`, `os.fsdecode`, strict).
- **Alternatives**: `os.fsdecode` — platform-dependent on Windows (mbcs); `errors="replace"` — lossy.

## R3 — Where the "how" lives
- **Decision**: `src/kernel/git/` package, beside `kernel/git_topology.py`.
- **Rationale**: `ref_advance` must import zero `specify_cli` (NFR-004 ratchet, `tests/architectural/test_layer_rules.py:755`); kernel already shells out to git (`git_topology.py`); no kernel purity rule bans subprocess. `test_git_topology_one_copy.py` pins `git_topology.py`, so it is not moved.
- **Alternatives**: `specify_cli/core/vcs/queries.py` for everything — rejected: unreachable from `ref_advance` without relaxing NFR-004.

## R4 — Where the "what" lives
- **Decision**: intent-named listing queries in `kernel.git.listing`; the specify_cli-facing helpers in `specify_cli/core/vcs/git.py` (`git_diff_names*`, `git_ls_tree_names_checked`, `merge_base_changed_files`, 9 importers) are re-based onto them; domain rules stay with their owners (the reset-obstruction rule stays in `ref_advance`, the single authority T019 protects).
- **Rationale**: avoids a thin speculative wrapper module whose names would fail the dead-symbol gate, while callers still state intent and never touch argv.
- **Alternatives**: a new `core/vcs/queries.py` re-exporting kernel queries 1:1 — rejected as a duplicate surface. A domain query that carries specify_cli rules (for example residue-aware dirtiness) may be added to `core/vcs` during migration when two callers need it.

## R5 — #5400 containment
- **Decision**: `GitPath.overlaps(other)`: equal, ancestor or descendant on components.
- **Rationale**: PR #5437's `path.startswith(target + "/")` is correct; expressing it on components removes the class (`store` vs `storehouse`, trailing slashes).
- **Note**: the ancestor case only appears when git reports the file itself (a file-pattern ignore); a fully ignored directory collapses to `!! src/store/`, which the old check already matched.

## R6 — Output shapes (real git 2.43)
- `status --porcelain=v1 -z`: `XY<sp>path\0`; renames/copies: `XY<sp>new\0old\0`.
- `diff --name-status -z`: `R100\0old\0new\0`; others `M\0path\0`.
- `ls-tree -r --name-only -z`, `ls-files -z`, `diff --name-only -z`, `show --name-only --format= -z`: `path\0`.
- All available at the git 2.25 floor. `worktree list --porcelain -z` needs 2.36 → out of scope.

## R7 — Scope census (base)
- 85 regex hits: 13 `worktree list` (out of scope), 11 already `-z` (runner/decode unification), 6 existence checks (`ls-files --error-unmatch`), ~27 boolean "anything dirty", ~25 genuine path parsing.
- Destructive or wrong-decision sites beyond `ref_advance`: `tasks_move_task` `.strip('"')` half-decoder; `commit_guard_hook` staged-path check (possible fail-open); `bulk_edit/gate` and `post_merge/stale_assertions` (fail-open classification); `git_probes` squash content axis (false REFUSE); leading-space `.strip()` hazard at `mission_finalize:2653`, `tasks_parsing_validation:555`.

## R8 — PR #5437
- **Decision**: cherry-pick with `-x` (authorship kept); its tests are the #5400 oracle.
- **Rationale**: either landing order rebases cleanly (identical patch drops out).

## R9 — Ratchet policy
- **Decision**: this mission adds no ratchet; its gate ships with an empty allowlist. Ruling recorded in `docs/adr/4.x/` (relates to `docs/adr/3.x/2026-09-14-1-census-floor-ratchet-adjudication.md`), charter standing order 5 and Burn-down Policy, `packs/built-in/tactics/frozen-baseline-shrink-only-ratchet.tactic.yaml` (generic caveat), `packs/internal/` (CI-cost rationale).
