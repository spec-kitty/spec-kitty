---
title: 'Pre-spec research — CSF #2670 landing-pass campsite follow-ups'
description: 'Closeout of the pre-spec research squad for CSF #2670: root-cause findings on the shard-map gap, xdist flake, sync remediation-guard, and mypy debt tickets.'
doc_status: closeout
type: explanation
updated: '2026-08-10'
---
# Pre-spec research — CSF #2670 landing-pass campsite follow-ups

Base: `upstream/main` @ `c6b70d22e` (research worktree `research/csf-2670-followups`, read-only).
Squad: researcher-robbie (related-issue hunt), paula-patterns (SSOT/duplication root-cause), architect-alphonso (design decisions). All claims verified against current code, not ticket text alone.

## Scope tickets (all OPEN, children of epic #1928 ruff/mypy/Sonar debt)
- **#2671** — recurring shard-map registration gap (design decision)
- **#2673** — bite-battery `_SourceMutation` xdist flake (isolation fix)
- **#2674** — sync remediation-guard escape + duplication (SSOT hardening)
- **#2675** — 17 pre-existing mypy errors / 8 files (type debt)

## Root-cause findings (not error counts)

### #2671 — one seam, two reds
A new `tests/architectural/*.py` trips **both** GC-1 completeness (`test_arch_shard_marker_completeness.py:100`) **and** the orphan ratchet (`test_gate_coverage.py:571`) from the *same* missing entry. Both resolve from **one seam**: `shard_for()` in `tests/_shard_registry.py:129` (marker applied iff non-None). NOT a false-green — the `arch-adversarial` job runs `if: always()` with no path filter, so it is caught on the PR, but as an expensive confusing double-red needing a non-obvious manual table edit + re-push. A reminder-based fix has already failed 4×.
- **Recommendation (alphonso): Direction A, refined** — per-group opt-in `default_fallback` field on `ShardGroup`; unassigned arch files route via a **stable hash-bucket** (`sha1(relpath) % n + 1`, NOT "lightest" — lightest piles all fallbacks on one shard); explicit `_ARCH_SHARD_*` entries still win; keep the GC-1 **union invariant** as the fallback's correctness net. One red-first WP. Seams: `tests/_shard_registry.py:129` + `tests/_arch_shard_map.py` (opt-in flag + header-doctrine rewrite).
- **Ticket-text correction (robbie):** it is **3** shard-map *registration* appends (`test_marker_baseline.py` #2590, `test_workflow_dist_lint.py` #2590, `test_no_parity_scaffold.py` #2651), plus a 4th *golden-count annotation* (`c6b70d22e`) which is a different mechanism. Spec should say "3 registration appends across ~3 incidents."

### #2673 — shared mutable real-file state
`_SourceMutation` (`test_single_mission_surface_resolver.py:822`) mutates the **real** `src/specify_cli/core/mission_creation.py` on disk; a concurrent xdist worker's `discover_rows()` scanner reads it mid-mutation → false RED on an uninventoried `_wp04_bite_witness` sink. CI-safe today (injector shard_1, scanner shard_2 = separate checkouts); the flake is the **local `-n auto`** run only.
- **Recommendation (alphonso): Option (i)** — mutate an isolated **tmp copy** + process-local monkeypatch of `audit.SRC_ROOT`; xdist workers are separate processes so the sibling scanner keeps reading the never-mutated real tree. Preserves what the battery proves (real detector code path, root-agnostic). Option (ii) serialize is blocked: `xdist_group` needs `--dist loadgroup` but repo mandates `--dist loadfile`. There are ~6 sibling `_SourceMutation` sites (a whack-a-mole class) — fix the #2673 pair now, leave a tracked note.
- **Duplicate (robbie): #2638** is a de-facto duplicate — a *second* scanner victim (`test_surface_resolution_audit.py`) of the same injection. One fix closes both; close #2638 as fixed-by.
- **Theme-twin (robbie): #2672** — same "tests must not mutate real repo files" hygiene root (pollutes real `synthesis-manifest.yaml` + ANSI). Cheap `NO_COLOR=1`+tmp-isolate fold candidate.

### #2674 — one structural root (split surface + half-blind guard)
Guard `test_no_unknown_commands_in_hints` iterates **only** `_REMEDIATION_HINTS` dict (`test_preflight_remediation_hints.py:118,182`); the inline `_build_remediation_lines()` (`preflight.py:307-334`) emits `orphan-daemons`, `sync migrate`, `auth login` that are **never** validated to resolve under `--help` — a typo ships green. Plus `daemon_server_url`/`team_or_user` remedies are byte-identical duplicates across dict + inline (S1192 is **semantic not lexical** — different line-wrap points, so grep misses them).
- **Recommendation (paula): one registry** — hoist all remedy prose to named constants; both the dict and the builder reference them; expose `ALL_REMEDIATION_TEXTS`; **repoint the command-resolution guard at the registry** (not the dict). Closes duplication + coverage in one seam. Small blast radius (one module + one test file). **Whack-a-field trap:** hoisting the 2 literals without widening the guard leaves orphan/migrate/auth-login unvalidated — incomplete.

### #2675 — 11 target-file errors collapse to 6 roots
- **Cluster 1 (str→Lane, 4 errors @ workflow_executor 807/816/837/1232) → 1 root:** `get_wp_lane` (`status/lane_reader.py:50`) returns `Lane | str` only because of legacy string sentinel `LEGACY_UNINITIALIZED_SENTINEL`. **Fix-once:** promote the sentinel to a `Lane` member (enum is `StrEnum`; `Lane.GENESIS` already models unseeded) → loader returns pure `Lane`, all 4 vanish, and `get_all_wp_lanes` annotation is corrected for free. Aligns with no-legacy-resolver-paths. (Pragmatic alt: `Lane(...)` coerce at 2 call sites 770/1209 — leaves the union leak.)
- **Cluster 2 (no-any-return, 2 @ 428/1372) → 1 root:** `_wf().locate_work_package` leaks `Any` via `ModuleType` accessor. One typed wrapper `_locate_wp(...) -> WorkPackage`.
- **Cluster 3 (decision_id str|None→str, 2 @ specify_interview.py:181 / plan_interview.py:181) → 1 root replicated by duplication:** narrowing captured into an intermediate bool mypy can't carry; the two files are **byte-identical blocks**. Consolidate into shared `widen/interview_helpers.py` + narrow once.
- **Cluster 4 (3 independent Optional narrowings @ workflow_executor 668/873, status_transition.py:854) → 3 roots, NO shared boundary.** Local narrowing on a genuine invariant each. Do NOT invent a shared seam or blanket-cast.
- **Traps:** blanket `cast(Lane,...)` / per-site `cast(WorkPackage,...)` / per-file decision_id narrowing all re-open the leak. Charter: fix the code, not suppress.
- **Other files (mechanical, 6 redundant-cast):** `_read_path_resolver.py:1473`, `mission_type_profiles.py:577/581/876`, `status/emit.py:302`, `m_2_1_4_enforce_command_file_state.py:78` — drop cast, watch unused import.

## Collision with in-flight #2651 / mission-type-single-source-gate-wiring / S0
**No production-code collision.** Contention is **test-surface** only:
- **#2671** edits `tests/_arch_shard_map.py` — contended (#2651 already appends there; HEAD `c6b70d22e` is shard-map-adjacent; S0 adds arch tests). Landing #2671's fallback *first* removes the exact friction those missions keep hitting.
- **#2673** edits `tests/architectural/test_single_mission_surface_resolver.py` — this **is the resolver-seam mission's PRIMARY test file** (dense #2651 tags; S0 is SPECCED+PLANNED, still adding tests). **Sharper collision** — sequence #2673 for a quiescent window or fold into that mission's lane.
- `mission_type_profiles.py` (6 redundant-cast in #2675) is owned by the mission-type work — coordinate those 3 cast-drops or defer them.

## Related-issue verdicts (robbie)
| # | Verdict | Why |
|---|---|---|
| #2638 | FOLD-IN → #2673 | duplicate root (2nd scanner victim); close as fixed-by |
| #2672 | FOLD (theme-twin of #2673) | same real-file-mutation hygiene root; cheap |
| #2475 | ADJACENT | arch marker vacuous under `.worktrees/` — different mechanism |
| #2476 | ADJACENT/OUT | proto-spec local arch-pole parity CLI — bigger, under #1931 |
| #2607 | ADJACENT | GC-2b abs-path ids — different surface |
| #2625, #2631, #1843 | OUT | different surfaces / strategic |
| #1928 | PARENT | home epic for #2675 + cluster; link, don't scope |

## Recommended mission shape
ONE quick-follow mission, theme "campsite-clean the #2670-landing residue so main stops going red for process reasons," with two rigour tiers:
- **Mechanical burn-down:** #2674 (SSOT), #2675 (6 roots), #2673 (+#2638 dup, opt #2672).
- **One design decision:** #2671 (Direction A) — its own decision-moment WP.

Open forks for the operator (below) before speccing.
