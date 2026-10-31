# Discovery & Research — centralized-runtime detection is project local

Mission: `centralized-runtime-detection-is-project-local-01M68ZFE`
Issue: spec-kitty/spec-kitty#6551
Branch: `issue-6551-centralized-runtime-detection-is-project-local`
Base: `origin/main` @ `dfe9efb0e8` (fast-forwarded from `6f73b2a98e`, 18 commits)

## 1. The defect still reproduces on current main

Reproduction script (`/tmp/repro6551.py`, kept out of the tree) against the
current checkout, with `SPEC_KITTY_HOME` pointed at an empty directory and a
project whose `.kittify/metadata.yaml` says `version: 4.0.0rc8`:

```text
version.lock exists: False
global_runtime_configured: False
uses_centralized_runtime: False
0.6.7.detect -> True
0.12.0.detect -> True
```

The issue's table is therefore still accurate for this build: the same commit
gives a different answer depending on whether the operator's home has been
bootstrapped. `upgrade` does not bootstrap the home before running migrations
(#3900), so a fresh machine/CI runner hits the `True` branch on its first run.

## 2. Root cause, confirmed by reading the code

- `src/specify_cli/upgrade/compat.py:24-40` — `uses_centralized_runtime()` calls
  `global_runtime_configured()` **first** and returns `False` when the home has no
  `cache/version.lock`. The project's own `metadata.yaml` (the branch two lines
  below) is never reached in that case.
- `src/specify_cli/upgrade/migrations/m_0_6_7_ensure_missions.py:33-35` and
  `src/specify_cli/upgrade/migrations/m_0_12_0_documentation_mission.py:40-42` —
  both `detect()` bodies early-return `False` only via that predicate.
- `src/specify_cli/upgrade/registry.py:96-98` — `get_applicable()` states that a
  `skipped` record is re-evaluated each run and "re-skipped idempotently". That
  is only true while `detect()` is a function of project state.
- ADR `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md` §3 Consequences:
  "`detect()==False` yields a `skipped` record; the skipped record keeps them from
  re-firing." The current predicate breaks that promise on a differently-bootstrapped
  machine.

## 3. Blast radius survey

`uses_centralized_runtime` has exactly **two** call sites in `src/`
(`m_0_6_7_ensure_missions.py`, `m_0_12_0_documentation_mission.py`) — the two
migrations the issue measured. `global_runtime_configured` has exactly **one**
call site: `uses_centralized_runtime` itself. So the predicate change is the
whole fix for these two migrations and cannot leak into anything else.

Three other migrations read the global home directly
(`m_2_1_3_restore_prompt_commands.py:106-118`,
`m_2_1_4_enforce_command_file_state.py:146-156`,
`m_3_1_2_globalize_commands.py:32-77`) but not through
`uses_centralized_runtime`, and the issue did not measure them under this
trigger. Changing their reach would be a second, unreproduced fix inside a
one-line defect; they are recorded as a follow-up in the PR's `## Deferred`
section rather than folded in silently.

## 4. Decisions

**D-1 — Fix the predicate, not the ledger (the issue's first suggestion).**
The issue offers two remedies: (a) make `uses_centralized_runtime` read the
project's `metadata.yaml` before the home; (b) treat `skipped` as settled for
`target_version` below the project's stamped version. Decision: **(a) only.**
Reasoning:

- (b) changes ledger *selection* semantics, which ADR `2026-10-17-1` §3 and
  C-001 in the spec deliberately freeze; it would also make a genuinely
  re-runnable legacy migration permanently un-runnable on a project that is
  still in the legacy shape.
- (a) is a single-predicate change with two call sites, restores exactly the
  property the ledger assumes ("`detect()` is a function of project state"), and
  leaves the ledger contract untouched.
- (b) also only *hides* the non-determinism: `detect()` would still disagree
  between machines, it would just no longer be consulted.

**D-2 — `metadata.yaml` present and `>= 2.0.0` wins outright.**
A readable `metadata.yaml` is the project's own statement of which runtime model
it was created or last migrated under. When it says `>= 2.0.0`, the answer is
`True` with no home consultation. When it is absent, unreadable, or says
something unparseable / pre-2.0, the existing home-based path runs unchanged. The
home check survives *only* for the metadata-less shapes that
`tests/upgrade/test_compat.py` already pins (repo with `.kittify/` → `False`;
worktree without `.kittify/` → `True` under a bootstrapped home).

**D-3 — Invalid/missing version keeps failing closed.**
`InvalidVersion` (including the `"unknown"` default) still returns `False`: a
project we cannot date is not assumed modern. Preserves today's behaviour and
avoids inventing a new assumption.

**D-4 — The regression test must run the production path.**
Per tactic `acceptance-criteria-non-vacuity` ("Exercise the production path, not
only a helper"), the red-first test drives the real `upgrade --project --yes`
command through the existing `typer.testing.CliRunner` harness
(`tests/upgrade/test_upgrade_integration.py` shape) with an empty
`SPEC_KITTY_HOME`, and asserts no tracked change — not merely that a helper
returned `False`. The helper-level cases are added *as well* (they carry the
"why" and the pre-2.0 positive control), not instead.

## 5. Evidence checked for supersession

- `git log -S "uses_centralized_runtime" -- src/specify_cli/upgrade/compat.py`:
  only `1d917d2449` ("Release 2.0.6 upgrade consistency sweep", PR #269) and later
  touch-points that do not change the ordering. The home gate has been there since
  2.0.6 and was correct then (every command, `upgrade` included, bootstrapped the
  home first; the version window never re-offered a 0.x migration to a 2.x project).
  Both premises have since changed.
- `gh pr list --repo spec-kitty/spec-kitty --search 6551 --state all`: no PR
  references or fixes this issue.
- No ADR reverses the centralized-runtime model; ADR `2026-10-17-1` assumes the
  property this mission restores.

## 6. Open questions (resolved before tasks)

- **Q: Should the fix also cover the metadata-less worktree on a fresh machine?**
  A: No. That shape has no project stamp to read, and the issue explicitly leaves
  it to the home check. Recorded as a follow-up, not silently widened.
- **Q: Do already-affected projects need repair in this PR?** A: No — that is
  #6548's repair surface (22 package copies already sitting in
  `.kittify/overrides/missions/`). The issue's own "repair path" bullet is
  recorded in `## Deferred`.
