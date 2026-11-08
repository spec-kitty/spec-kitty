# Discovery: route the remaining `kitty-specs/` walkers through the Mission predicate

Issue: spec-kitty/spec-kitty#6758 (follow-up from the pre-merge squad on #5875).

## Grounding: the issue still reproduces on current `main`

`main` was at `512567eee7` when this Mission started. #5875 is merged (its predicate,
`context/mission_resolver.is_selectable_mission_dir`, and the `doctor identity` /
`doctor mission-type` re-points are in the tree). The six walkers the issue names are
still raw: each enumerates every directory child of `kitty-specs/` and decides for
itself whether the child is a Mission.

A reproduction on a scratch git repository holding one real Mission
(`001-real-mission/meta.json` with a `mission_id`) and one residue folder
(`residue-leftover/spec.md` plus `tasks/WP01-leftover.md`, no `meta.json`) gave:

| Walker | Before |
| --- | --- |
| `doctor topology` (`_collect_topology_rows`) | 2 rows; `residue-leftover` reported with `error: "meta.json not found"` |
| `_coordination_doctor._resolve_mission_dirs` | `['001-real-mission', 'residue-leftover']` |
| `_review_cycle_reconcile_doctor._mission_dirs_for` | `['001-real-mission', 'residue-leftover']` |
| `materialize._mission_dirs_to_process` | `['001-real-mission', 'residue-leftover']` (derived-view targets, and a coordination-worktree probe, for a folder that is not a Mission) |
| `charter_activate._collect_inflight_missions` | scans the residue folder too (no event log today, so no warning, but the walk itself is unconditional) |
| `release.changelog.build_changelog_block` | `['residue-leftover']` — a residue folder entered the release-notes mission list |

The `doctor topology` line is the user-visible one: `spec-kitty doctor topology` prints
residue as a Mission with a `null` topology and no remedy, while `doctor identity`
already reports the same folder as `residue` with a reason and a remedy (#5875).

## Decisions

### D1 — all six walkers are read-surface, so all six use the read-side predicate

Each of the six names a *Mission* it is about to read, report or write derived
artifacts about. None of them writes into a `kitty-specs/` child, mints an identity
there, or repairs one. The read-side rule
(`is_selectable_mission_dir`, "read-side residue" in the #6759 glossary proposal) is
therefore the right one authority for all six; none needs the write-seam
`is_kitty_specs_residue`, whose looser rule exists so the upgrade sweep can still
repair a `spec.md`-only folder. Decision recorded so a later walker that *does* write
into `kitty-specs/` does not copy this routing by analogy.

### D2 — filter the existing walk; do not swap in a shared iterator

The walkers have deliberately different listing postures:

* `_coordination_doctor._resolve_mission_dirs` uses `safe_is_dir` per candidate and
  **raises** on an unstattable one (#3194, pinned by its own tests);
* `materialize._mission_dirs_to_process` skips dot-directories;
* `_review_cycle_reconcile_doctor` and `release.changelog` use plain `Path.is_dir()`;
* `charter_activate` uses `Path.is_dir()` and is best-effort.

Swapping all six onto `mission_resolver.iter_kitty_specs_children` (the fail-soft raw
walk `doctor identity` / `doctor mission-type` share) would silently change the
`#3194` raise into a skip. So each walker keeps its own enumeration and adds exactly
one predicate call per child, with one `TrackedMissionPaths` memo per walk (at most one
`git ls-files` per walk, none when every child carries a `mission_id`). This is the
smallest viable diff (DIRECTIVE_024 locality, `change-apply-smallest-viable-diff`) and
keeps every existing posture pin green.

### D3 — the predicate, not `FsMissionResolver.all_missions()`

The resolver index (`_index_entry`) requires a `mission_id`, so routing these walks
through `MissionResolver` would make them blind to legacy, id-less Missions that
selection *does* list when git tracks their `meta.json`/`spec.md`. #5875 chose
`is_selectable_mission_dir` for exactly this reason in `doctor mission-type`
(its docstring records the carve-out). The same reasoning applies to all six.

### D4 — `doctor topology` excludes residue instead of rendering it

`doctor topology`'s job is stored-topology validation of Missions, not residue
reporting. A residue folder has no stored topology, so its row is noise (a `null`
topology, no finding, no remedy). The residue reporter is `doctor identity`, which
already lists it with a reason and a remedy; the fix removes the duplicate, weaker
report rather than growing a second one. The change is visible: the `--json`
`missions` list no longer contains residue rows, and the human table's count drops.

### D5 — pin the routing architecturally, and each walker behaviourally

`tests/architectural/test_mission_resolver_walker_gate.py` allowlists these six modules
as reviewed raw walkers. That allowlist says "raw enumeration is tolerated here" and
nothing more, so a future edit could drop the predicate again silently. This Mission
adds a shrink-only ledger of the six (`(module, function)`) plus an AST check that each
of those functions calls `is_selectable_mission_dir`; a walker that loses the call
fails the gate. Each walker also gets a behavioural test with a residue child
(git-aware: a folder holding only `tasks/`, untracked) that must not appear and a
selectable Mission that must.

The audit engine (`src/specify_cli/audit/engine.py`) is deliberately **not** touched:
it keeps its own looser rule by operator ruling, and #6757 owns that change.

## Evidence

* `src/specify_cli/context/mission_resolver.py` — `is_selectable_mission_dir` (docstring
  "the read-side Mission test", operator ruling 2026-10-27), `TrackedMissionPaths`,
  `is_kitty_specs_residue` (write seam), `iter_kitty_specs_children` (fail-soft raw walk).
* `src/specify_cli/cli/commands/_mission_type_audit.py:313` — the #5875 pattern this
  Mission mirrors (`TrackedMissionPaths` + `is_selectable_mission_dir` filter).
* `src/specify_cli/status/identity_audit.py:245` — `classify_walk_entry`, the same
  predicate used to split Missions from residue.
* `tests/architectural/test_mission_resolver_walker_gate.py` — the six modules are
  allowlisted here; there is no predicate pin for them today.
* Reproduction script output, recorded in the table above (scratch git repo, current
  `main`).

## Open questions for specify/plan

* Which of the six merit a doc touch beyond the changelog? `doctor topology` behaviour
  is the user-visible one; the CLI reference for `doctor` should say residue folders are
  reported by `doctor identity` only. The other five are internal surfaces.
* Does `materialize` need a note for the derived-view change (no `.kittify/derived/`
  entry for a residue folder)? Judged not user-facing: the folder is not a Mission and
  `materialize --mission <residue>` already refuses.
* Row-shape compatibility of `doctor topology --json`: no consumer keys on a residue row
  (its fields are all `null`); the mission list stays a list of Mission rows.
