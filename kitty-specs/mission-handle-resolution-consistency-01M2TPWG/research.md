# Research: Consistent Mission-Handle Resolution

Phase 0 consolidation. Root causes and fix surface were established by two
adversarial research passes (researcher-robbie) over the working tree; the
decisions below are the load-bearing conclusions carried into the design.

## Decision 1 — Fix at the callers, not the shared seam

- **Decision**: Keep `mission_runtime/resolution.py::read_dir` lenient (it only
  *composes* `kitty-specs/<raw>`, no existence check). Add `.exists()` gating at
  each command call-site.
- **Rationale**: The leniency is depended on — `merge --abort` uses the
  non-raising raw fallback to clean up a broken coordination window
  (`merge/resolve.py` else-branch). Changing the seam would break that recovery
  and ripple through every caller. The correct commands already gate at the
  caller (`materialize.py:88-102`: resolve → `if not feature_dir.exists(): emit "Mission not found: <slug>"; exit`). That is the house pattern to converge on.
- **Alternatives considered**: (a) Add existence checking inside `read_dir` —
  rejected: breaks `--abort` and the lenient scaffold-new-mission callers.
  (b) A single central resolver all commands must route through — rejected as
  too large a refactor for an MVP fix; the four bugs bypass gating at *different*
  layers, so per-caller gates plus one shared message is the smaller, safer diff.

## Decision 2 — One shared discovery helper in `context/mission_resolver.py`

- **Decision**: Add `discover_missions(main_repo)` returning
  `{mission_slug, mid8, friendly_name}` per mission, built on the public
  `FsMissionResolver.all_missions()` (already yields `mission_slug`, `mid8`,
  `feature_dir`) plus a `meta.json` read for `friendly_name`.
- **Rationale**: The agent layer already has the behavior
  (`_sole_mission_slug_or_none` for single-mission auto-select — the FR-004
  convention — and `_list_feature_spec_candidates` for enumeration) but as
  private `_`-helpers inside `cli/commands/agent/`. `next` living in
  `cli/commands/` should not import agent-layer privates; co-locating a public
  helper with the resolver is cleaner and reusable.
- **`friendly_name` note**: it is **not** a field on `ResolvedMission`; it is
  read from `meta.json`. Confirmed via the #4682 brief (`ResolvedMission` carries
  `mission_id`, `mission_slug`, `feature_dir`, `mid8`).
- **Alternatives**: promote the agent-layer privates (cross-package coupling) —
  rejected. Bare-slug listing (no mid8/friendly_name) — rejected by the DM2
  decision (opaque ULID legibility).

## Decision 3 — Canonical not-found message

- **Decision**: One template, `mission not found: <handle>`, naming the handle
  verbatim, adopted by the four fixed commands and by the already-correct
  commands (a small constant swap), satisfying NFR-002.
- **Rationale**: Today the "correct" commands each phrase it differently
  (`No mission found for handle "X"`, `Mission not found: 'X'`,
  `Mission not found: X`). The mission's primary domain is exactly this
  legibility, so unifying the wording is in-domain Boy-Scout work, not scope
  creep. `next_cmd.py` already has `_emit_mission_not_found_error` (human+JSON)
  to model the dual-shape emitter on.
- **Contested/deferred**: Fully re-standardizing *every* correct command's exact
  bytes may generate broad test churn. Disposition: **accepted** for the shared
  constant + the four fixed commands and `next`; for the other correct commands
  the wording swap is folded where it is a one-line constant change, and any
  command whose unification proves to require disproportionate test rewrites is
  recorded and deferred with rationale rather than silently skipped. No contested
  finding dropped.

## Decision 4 — Root-cause map (per command)

- **plan/tasks**: `_build_setup_plan_detection_error`
  (`agent/mission_feature_resolution.py`) was written for the *no-handle*
  auto-detect-failed case and emits "N missions found, pass --mission to
  disambiguate"; both call-sites (`mission_setup_plan.py`,
  `mission_check_prerequisites.py`) *catch and overwrite* the clean
  `FEATURE_CONTEXT_UNRESOLVED "Mission not found for handle '<h>'"` that
  `_find_feature_directory` already raises. Fix: branch on the explicit handle —
  when a non-empty handle was given and the inbound error is a not-found, emit
  the canonical message and skip the disambiguate branch. The *no-handle*
  multi-mission case must still produce the disambiguate message.
- **research**: `research.py` resolves via the lenient seam
  (`_read_mission_dir_or_exit`, guards only path-safety) then `mkdir(...)` — no
  existence check. Fix: `.exists()` gate immediately after resolve, before any
  `mkdir`/scaffold.
- **merge**: `merge/resolve.py::_resolve_mission_slug` deliberately returns the
  raw slug for an unresolvable handle → downstream `MissingLanesError`
  ("lanes.json is required…"). Fix: in the fresh/resume entry
  (`cli/commands/merge.py`), when the resolved candidate does not exist, emit the
  canonical not-found; keep the raw fallback for `--abort`.

## Decision 5 — `next` missing vs nonexistent handle

- **Decision**: `next_cmd.py::_resolve_mission_slug` — the **empty/None** branch
  (`raise typer.BadParameter("--mission <slug> is required")`) becomes discovery
  (auto-select 1 / list N / nudge 0). The **nonexistent-but-present** branch
  (returns raw → downstream `MissionNotFoundError`) keeps its clean not-found and
  is regression-guarded.
- **Rationale**: `--mission` is already declared *optional* at the Typer layer;
  the hard requirement is imperative and uses the fragile `typer.BadParameter`
  Rich-panel path that sibling commands abandoned. Discovery is the onboarding
  fix #4682 asks for.

## Coordination gotcha (verified)

`next` deliberately skips the racy global-agent-command startup gate
(`__init__.py` `next_fast_path`); the missing-handle handling stays in the
command body and must not be moved into the root callback.
