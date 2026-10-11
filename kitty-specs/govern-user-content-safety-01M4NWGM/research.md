# Research: Governed ops never destroy or mis-report user content

## Squad provenance

Research & grounding squad (2026-10-11, base `main` `3498b426`, after PR #6038 merged): three parallel grounding agents reproducing each issue red-first at HEAD and mapping loci, plus orchestrator codegraph mapping of the #6020 residue/ownership predicate family. Operator sign-off on the #5964 approach and the 3-WP structure captured via in-session decision (2026-10-11): scope the upgrade untrack to manifest-owned paths (do NOT extend `is_self_bookkeeping_churn`); one Mission, three independent WPs.

Base carries both #6020 (mission `destructive-residue-context-01M4KBPS`, the `ResidueContext`/`_is_disposable_residue` guard API) and #6038 (#5968/#5967/#5969/#5863 consolidation/teardown integrity). This mission is the point-fix layer of the #3129 ambient-write-boundary class; the structural ADR is already merged — no shadow-workspace rewrite.

## Decisions

### D1 — #5964 is fixed at the upgrade-migration ownership seam, NOT the residue predicate
- **Decision**: scope `m_3_2_5_agents_skills_gitignore_backfill._untrack_tracked_paths` to untrack only spec-kitty-projected `.agents/skills/` paths, reusing the existing manifest-ownership authority (`skills/command_installer.py` stable `spec-kitty.*` command pattern + `_is_canonical_rel_path`; `skills/manifest.py` `ManagedFileEntry.installed_path`; `command-skills-manifest.json`). Do **not** route #5964 through `coordination.coherence.is_self_bookkeeping_churn`.
- **Rationale**: `is_self_bookkeeping_churn` is a path-pattern predicate for spec-kitty's *disposable* bookkeeping and feeds the consolidate/accept/review destructive-op guards; it has no wire to the upgrade migration. Extending it to match `.agents/skills/**` would make `consolidate` treat team skills as disposable (`reset --hard` / `worktree remove --force`) — re-creating the data-loss in a strictly wider blast radius (the #4933 "invisible to one gate, fatal at another" class the predicate's own docstring warns about). `.agents/skills/` ownership is a manifest question, not a path pattern (team vs pack skills share the prefix; pack namespaces are config-variable). The charter "User Customization Preservation / Proof Trail" already states `command_installer.py` codifies "third-party paths under `.agents/skills/` are never touched unless manifest-owned."
- **Alternatives**: extend `is_self_bookkeeping_churn` (rejected — widens the bug, operator-confirmed); a new shared manifest-ownership predicate (deferred — a second authority unless a second caller appears; reuse the existing one, C-001).

### D2 — #5434 is independent of the residue predicate: fix the exclude write location
- **Decision**: call `core/git_ops.py::exclude_from_git_index(repo_root, [".spec-kitty/"])` at the single code-lane choke point in `allocate_lane_worktree` (`worktree_allocator.py:~1087`, before both `_validate_worktree_clean` calls, covering reuse/crash-recovery/fresh). Add a migration `m_4_0_0rcX_exclude_spec_kitty` modeled on `m_0_13_1_exclude_worktrees`. Delete the dead per-worktree writer `core/worktree.py::_ensure_spec_kitty_exclude` + its two call sites and drop its dead-symbol-allowlist rows.
- **Rationale**: `_validate_worktree_clean` fails on any `git status` entry and does not consult `is_self_bookkeeping_churn`; `.spec-kitty/` is not in that predicate's exempt set. The only coupling to the residue family is thematic. The per-worktree `info/exclude` git never reads; only the common-dir exclude (shared across all worktrees) is honoured.
- **Alternatives**: classify the lock as self-bookkeeping churn in the predicate (rejected — wrong seam, wouldn't fix the untracked-status the allocator trips on, and widens a predicate used elsewhere); write to tracked `.gitignore` (rejected — spec-kitty must not write a consumer's tracked `.gitignore`; FR-016 chose local `info/exclude` for exactly this).

### D3 — #4796 is in the #6020 family: hoist a pre-mutation preflight to parity
- **Decision**: in `orchestrator_api/consolidation.py::_execute_lane_merge`, after retention resolution (`:566-571`) and before the first `consolidate_lane_into_mission` (`:588`), run the shared `consolidation/entry_preflight.py::_pre_mutation_safety_preflight` (or extract its lane-worktree leg), gated on the same resolved `remove_worktree`/`teardown_coordination`. The raised `DestructiveOpRefused` is still caught at `:859` and enveloped `PREFLIGHT_FAILED`, now truthfully pre-mutation.
- **Rationale**: the CLI path already preflights before any mutation (`executor.py:873`); the orchestrator path received only the refusal-envelope half of the fix. #6038's snapshot/rollback lives in `consolidation/executor.py`+`rollback.py` and the orchestrator code-lane path never builds that state — so today it has neither a pre-mutation preflight nor a rollback door. Reuse the existing preflight (C-001), do not write a new check.
- **Alternatives**: wrap the whole orchestrator path in the executor snapshot/rollback machinery (rejected — far larger than the point-fix; the preflight parity is the minimal correct fix).

## Red-first reproduction evidence (at `3498b426`)

- **#5964 — PRESENT**: calling `AgentsSkillsGitignoreBackfillMigration().apply()` on a repo with a tracked, non-manifest `.agents/skills/team-review/SKILL.md` stages `D .agents/skills/team-review/SKILL.md`; `migration_index_untracks` returns that path and `safe_commit(index_deletions=...)` lands it in the upgrade commit. Matches the issue's rc6 / origin-main evidence.
- **#5434 — PRESENT**: a populated per-worktree `.git/worktrees/<n>/info/exclude` leaves `git -C <wt> status --porcelain` still listing `?? .spec-kitty/`; the same pattern in the common-dir `.git/info/exclude` makes it disappear. (Dogfood caveat: this repo's own `.gitignore:213` has `.spec-kitty/`, masking it — tests must build a consumer-like repo.)
- **#4796 — PRESENT (by airtight sequential code reading)**: `_execute_lane_merge` mutations at `consolidation.py:588-607` (lane consolidation, target integration, done-stamping, push) precede the first lane-worktree dirty check at `:611`→`_apply_lane_merge_cleanup`→`guarded_worktree_remove`→`destructive_guard.py:280`; the refusal is enveloped `PREFLIGHT_FAILED` at `:168/:195`. No existing test pins the timing (the refusal test mocks `_execute_lane_merge` to raise).

## Sources

- GitHub issues #5964, #5434, #4796 (bodies read in full via REST).
- Grounding-agent reproductions + file:line maps (this mission's three grounding agents, 2026-10-11).
- Codegraph (index at repo root, `3498b426`): `coordination/coherence.py` residue family, `consolidation/entry_preflight.py`, `orchestrator_api/consolidation.py`.
- Sibling mission #6020 `destructive-residue-context-01M4KBPS` (merged) — the `ResidueContext`/`_is_disposable_residue` authority this mission does NOT extend for #5964.
- Charter: "User Customization Preservation / Proof Trail"; Standing Orders #1 (adversarial squad), #4 (red-first), #6 (canonical sources).
