---
title: 'Issue #2007 — Debbie RE-INVESTIGATION: the "missed path" behind the wrongly-"fixed" five'
description: "Debugger Debbie's re-investigation of #2007: the missed code path behind the five bugs that were wrongly marked fixed (2026-06-16)."
doc_status: deprecated
updated: '2026-06-16'
---
# Issue #2007 — Debbie RE-INVESTIGATION: the "missed path" behind the wrongly-"fixed" five

**Author:** Debugger Debbie
**Date:** 2026-06-16
**Branch / HEAD:** `pr/tool-surface-contract-residuals` @ `f6199ce9c` (`v3.2.0-22-gf6199ce9c`; the 22 commits past `v3.2.0` are ALL docs/planning — no code change, so HEAD behavior == `v3.2.0` behavior for these bugs).
**Robert's binary:** `spec-kitty-cli 3.2.0rc45` (`v3.2.0rc45` = `d630c219`, which is BEFORE `v3.2.0` final).

## Binding correction honored

The prior triage (`debbie-repro-triage.md`) classed **#6, #7, #9, #10, #11** as ALREADY-FIXED / read-path-fixed by reading code statically. **That conclusion is REJECTED.** This pass traces from the CLI entrypoint to the fix (not from the fix outward), constructs the exact failing inputs, and — where it can — reproduces the live failure on HEAD. **Zero closures recommended. Every bug below is OPEN.**

### Version facts that kill the easy excuses (H4)

| Fix commit | What it fixed | In `v3.2.0rc45` (Robert)? | In `v3.2.0` final? | In HEAD? |
|---|---|---|---|---|
| `8431dd931` (#1944/#1965) | submodule root in `locate_project_root` | **NO** | YES | YES |
| `8544012fa` (#1850) | `primary_feature_dir_for_mission` reads (#7 placement, #11 read-surface) | **YES (rc43+)** | YES | YES |

So:
- For **#7 / #11** Robert's rc45 **already carried the fix** — H4 (stale binary) is RULED OUT. The fix is present and still wrong/incomplete.
- For **#6** the `locate_project_root` fix was NOT in rc45, but that is irrelevant: the live specify/plan/tasks guard does **not** call `locate_project_root`. It calls `resolve_canonical_root`, which carries the submodule-misresolution bug in rc45 **AND v3.2.0 AND HEAD**. Upgrading Robert to v3.2.0 would NOT fix #6.

---

## Per-bug findings

### #6 — Submodule/`.git`-file root → `SPEC_KITTY_REPO_NOT_INITIALIZED` — **OPEN (reproduced live on HEAD)**

- **Present fix:** `src/specify_cli/core/paths.py:99-133` (`locate_project_root`) — for a submodule `.git` file (`gitdir: ../.git/modules/<name>`) it does NOT follow the pointer (correct) and its per-candidate `.kittify` check (`:126-131`, current-first) returns the submodule. The #1944/#1965 fix lives HERE.
- **Hypothesis that explains the live failure:** **H3 — second authority (split resolver).** The specify/plan/tasks guard `assert_initialized` (`src/specify_cli/workspace/assert_initialized.py:96-104`) does NOT call `locate_project_root`. It calls **`resolve_canonical_root`** (`src/specify_cli/core/paths.py:247-292`).
- **STILL-FAILING path (concrete `file:line`):** `src/specify_cli/core/paths.py:284-288`. For a submodule `.git` file, `_read_worktree_gitdir(git_path) is None` (not worktree topology) → executes **`continue`**, walking UP into the parent repo. It has **no `.kittify` boundary check and no submodule-boundary stop**. So it returns the parent repo (`econcept-next`) whose `.git` is a directory (`:280-282`). `assert_initialized` then checks `econcept-next/.kittify/config.yaml` → missing → `SpecKittyNotInitialized` / `SPEC_KITTY_REPO_NOT_INITIALIZED`.
- **Live repro (HEAD):** parent `econcept-next` (git repo) containing submodule `elissar-api` (`.git` file → `../.git/modules/elissar-api`) with `elissar-api/.kittify/config.yaml`:
  - `resolve_canonical_root(elissar-api)` → **`/tmp/.../econcept-next`** (PARENT — wrong; exactly Robert's symptom)
  - `locate_project_root(elissar-api)` → `/tmp/.../econcept-next/elissar-api` (correct)
  - `assert_initialized()` from inside the submodule → `SPEC_KITTY_REPO_NOT_INITIALIZED`, `resolved root: /tmp/.../econcept-next`, `missing: econcept-next/.kittify/config.yaml`.
- **What we missed:** WP05/IC-04 "collapsed to a single worktree-pointer parser" but the two resolvers are NOT behavior-equivalent on the submodule input. `locate_project_root` has a `.kittify`-boundary fallback; `resolve_canonical_root` has none and blindly ascends. The #1944/#1965 fix was applied to the resolver the live guard does NOT use.
- **Disposition: OPEN.** Fix belongs at `paths.py:284-288`: when a `.git` file is a non-worktree pointer (submodule/separate-git-dir), treat the directory as a candidate boundary (check `.kittify` / `kitty-specs`) before ascending — and/or stop ascent at a submodule boundary. Live repro is sufficient; no Robert-env needed.

### #7 — `spec_committed: false` while spec IS committed — **OPEN (reproduced live on HEAD)**

- **Present fix:** `src/specify_cli/cli/commands/agent/mission.py:2107-2114` — `is_committed(spec_file, repo_root, placement=_spec_placement)` with coord-aware placement (#1884). `is_committed` coord fast-path: `src/specify_cli/missions/_substantive.py` (`cat-file -e {coord_ref}:{tree_path}`, then HEAD check).
- **Hypothesis:** **H1 (incomplete coverage) + H3 (the read-path coord-priority feeds the wrong artifact path into the committedness check).**
- **STILL-FAILING path (concrete):**
  1. `spec_file = feature_dir / "spec.md"` at `mission.py:2074`, where `feature_dir` came from `_find_feature_directory → resolve_mission_read_path` — which returns the **coordination worktree** path once it is materialized (topology-aware priority, `_read_path_resolver.py:137-175`).
  2. `is_committed(coord_spec_path, repo_root, placement=COORD)` checks, in order: `{coord_ref}:{tree_path}`, then HEAD of the **coord worktree** (= the coord branch). It **never checks the PRIMARY checkout's target-branch HEAD.**
  3. When the spec was auto-committed to the **target/primary branch** but the **coord branch lacks it** (coord branch created before the spec landed, or spec auto-commit went to main), the spec is genuinely committed on primary HEAD yet `is_committed` returns **False**.
- **Live repro (HEAD, `/tmp/debbie7c`):** meta committed to main; coord branch created BEFORE spec; spec then committed to **main only**.
  - `main:kitty-specs/<slug>/spec.md` → present; `coord:...spec.md` → absent.
  - `feature_dir` resolves to the coord worktree; `is_committed(coord_path, placement=COORD)` → **False**.
  - `is_committed(primary_path, placement=COORD)` → **True**.
  - Matches Robert exactly: `spec_committed: false` + `SpecifyStarted` without `SpecifyCompleted` (the false gate blocks the `SPECIFY_COMPLETED` emission at `mission.py:2170-2176`).
- **Secondary trigger to chase (operator H3, auto-commit-not-firing):** the specify/plan auto-commit goes through `_commit_to_branch` (`mission.py:1118-1209`), which **silently swallows** `CalledProcessError`/`RuntimeError` containing "nothing to commit"/empty-changeset (`:1178-1195`) and returns `None` with no `commit_created` tracking. If `_resolve_planning_placement` raised (caught → `placement=None`, `:2110-2112`) or `_planning_commit_worktree` fell back to primary on a missing `mid8` (`:770-774`), a coord-destined commit can no-op against the wrong worktree and the artifact stays untracked — producing `commit_created: None` + untracked `plan.md`/`spec.md`. This second authority is real and unchased by the prior triage.
- **What we missed:** the committedness check has no **primary-target-branch HEAD** leg. The fix added coord-ref + coord-worktree-HEAD but the read-path's coord-priority hands `is_committed` a coord artifact path, so a spec committed on primary/target is invisible to the gate.
- **Disposition: OPEN.** `is_committed` must check the spec on the **primary artifact path against the target-branch ref** in addition to the coord ref (true OR across all sanctioned refs/surfaces), and emit diagnostics listing every ref checked (issue's own fix direction). Live repro covers the coord-vs-primary split; a Robert-env run would pin which of the two triggers (false-gate vs silent no-op commit) he hit first.

### #9 — Raw `python -c "from specify_cli.core.templates import ..."` — **OPEN (cannot disprove; guard absent)**

- **Present state:** `src/specify_cli/core/templates` **does not exist** (confirmed). The canonical template API is `specify_cli.runtime.resolver.resolve_template` (`src/specify_cli/runtime/resolver.py:255`). No prompt/skill in `src/doctrine/` currently emits that import snippet.
- **Hypothesis:** **H2 (unwired) is moot — there is nothing to wire; the failure is a prompt-hygiene / guard gap.** The agent (Robert's session) hand-rolled a raw out-of-venv `python -c` import — a behavior the prompts implicitly invite by ever suggesting Python imports over CLI surfaces.
- **STILL-FAILING reality:** there is **no guard test** forbidding stale `specify_cli.*` import snippets in prompts/docs/skills. `tests/specify_cli/tool_surface/test_docs.py` lints *registered CLI surface paths*, not Python import snippets. So a future prompt re-introducing a stale import path has zero protection, and nothing keeps prompts on CLI surfaces.
- **What we missed:** classing this "ALREADY-FIXED in SOURCE" treats absence-today as a fix. The issue's fix direction (guard test + keep prompts on CLI) is **unimplemented**. The defect class (drift toward raw imports) is live.
- **Disposition: OPEN.** Add a snippet guard (forbid `from specify_cli` / `python -c` import patterns in `src/doctrine/` prompts + docs) and keep prompts on CLI surfaces. Cannot be "closed" while the guard is missing.

### #10 — `finalize-tasks --validate-only` exit 1 on zero-match globs — **OPEN (glob path verified; the failing surface is elsewhere)**

- **Present fix:** `src/specify_cli/ownership/validation.py:319-385` (`validate_glob_matches`) — glob zero-match → warning; literal zero-match → error; `create_intent` suppresses literal-path errors. Routed at `mission.py:3347-3371`.
- **Verified by repro:** `is_glob_pattern("elissar-api/src/modules/econcept/psc-auth/**")` → glob → **warning, NOT error** (passes). Literal future file zero-match → error; in `create_intent` → suppressed. So the *glob-vs-error semantics themselves are correct on HEAD.*
- **Hypothesis that still explains the exit-1:** **H3 (a different gate) + H1 (validate-only create_intent staleness).** Two distinct exit-1 gates run before/around the glob check:
  1. `validate_all` (overlap + `validate_authoritative_surface`, `mission.py:3333`) — exit 1, and it **does NOT consult `create_intent`**. `validate_authoritative_surface` (`validation.py:166-196`) is a pure string-prefix check, so a future-only surface still passes — but an **overlap** between WPs (common when several WPs target the same not-yet-existing `psc-auth/**` subtree) fails here with exit 1, independent of the glob fix.
  2. The glob gate's `create_intent` is built from `wp_frontmatters` at `mission.py:3347`. In `--validate-only` the bootstrap loop infers fields **in memory** (`_inmemory_frontmatter`), so an agent who *just* added `create_intent` to a WP file may be validated against a frontmatter snapshot that does not reflect it — re-surfacing the literal-path hard error the agent thought they'd suppressed.
- **What we missed:** the prior triage proved the glob branch and stopped. Robert's exit-1 on a `--validate-only` run with visible zero-match globs is consistent with the **overlap gate** (which never sees `create_intent`) or the **validate-only frontmatter-snapshot timing**, neither of which the glob fix touches. The issue's core ask — make future-file-vs-glob semantics explicit in prompt/schema and put `create_intent` diagnostics in JSON — is also still a doc/contract gap.
- **Disposition: OPEN.** Cannot disprove statically that Robert's exit-1 came from the glob path; the live evidence (exit-1 WITH visible zero-match globs + agent forced into `create_intent`) points at the overlap gate / validate-only snapshot, not the (correct) glob classifier. Needs a Robert-env `--validate-only --json` capture to read which gate set exit 1.

### #11 — `finalize-tasks` reads planning artifacts from wrong (coord) surface — **OPEN (cannot reproduce on HEAD; second-trigger unresolved)**

- **Present fix:** `mission.py:2714` `repo_root = locate_project_root()` (recovers primary from a coord worktree via `.git/worktrees/<name>` topology), then `_primary_dir = primary_feature_dir_for_mission(repo_root, mission_slug)` (`mission.py:2798`; resolver `_read_path_resolver.py:397-416`) anchors reads on the **primary** dir. In rc45 AND HEAD.
- **Live test (HEAD, `/tmp/debbie7c`, run FROM the coord worktree):** `locate_project_root()` → primary; `planning_dir = primary_feature_dir_for_mission(...)` → primary dir; `spec.md`/`meta.json` resolve on the **primary** surface. The read-surface IS correct on HEAD for the standard coord topology.
- **Hypothesis for the live failure:** **H1 (an input class HEAD still mis-resolves), NOT H4.** Robert's rc45 contained the primary-read fix, yet he hit `meta.json not found` then `spec.md not found` under the coord path. The unhandled class is the **fail-closed `require_exists=True`** step that runs FIRST: `_find_feature_directory → resolve_mission_read_path(..., require_exists=True)` (`mission.py:2752-2756`, resolver `_read_path_resolver.py:316-367`). When the coord worktree is materialized but its mission dir is absent (the #1718 fail-closed condition), it raises `StatusReadPathNotFound` BEFORE the primary read is ever reached — surfacing as the coord-path-not-found symptom Robert saw. This is the same coord-topology class as #14.
- **What we missed:** "read surface is fixed" is true for the path that gets *reached*; the prior triage did not chase the **pre-read `require_exists` fail-closed** gate that can abort with a coord-path error before the primary read runs. Robert's exact mid8/coord-dir-presence state is needed to confirm whether he tripped fail-closed or an older code path.
- **Disposition: OPEN.** Cannot reproduce the literal `meta.json not found`/`spec.md not found` on HEAD's primary-read path; the surviving trigger is the fail-closed pre-read on a materialized-but-empty coord worktree. Needs a Robert-env repro (his coord worktree + mid8 + mission-dir presence) to pin.

---

## Bonus — re-opened adjacents

- **#2 (PARTIAL → OPEN):** status side-effects confirmed still present — `_collect_charter_sync_status` calls `GlossaryEntityPageRenderer(...).generate_all()` and the mutating `ensure_charter_bundle_fresh(...)` inside a read-only status (`src/specify_cli/cli/commands/charter/_status_collectors.py:36-42`). Hash-unification (sync vs status) remains unverified. OPEN.
- **#12 / #14 / #15** are the same coord-read-path / error-fidelity class that explains the *secondary* triggers behind #7 and #11 (read-path resolves coord, callers either fail-closed or reclassify the typed code). They reinforce that #7/#11 are NOT isolated and NOT closable.

## Structural verdict

The five "fixed" bugs share ONE structural root with the rest of #2007: **a single typed mission-context/read-path resolver was introduced (`resolve_mission_read_path` / `resolve_canonical_root` / `primary_feature_dir_for_mission`), but the fixes are NOT behavior-equivalent across the resolvers and NOT complete across the input classes**:

- **#6** = the collapse left TWO root resolvers (`locate_project_root` vs `resolve_canonical_root`); only ONE got the submodule fix, and the live guard uses the other.
- **#7** = the committedness check trusts the coord-priority read-path artifact and has no primary-target-branch leg.
- **#11** = the primary-read fix is reached only AFTER a fail-closed `require_exists` gate that can abort on a coord-topology edge first.
- **#9 / #10** = the "fix" is real but the guard/contract the issue actually asks for is absent (snippet guard; future-file-vs-glob schema + JSON `create_intent` diagnostics; overlap-gate `create_intent` awareness).

NONE should be closed.
