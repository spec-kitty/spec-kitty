# review-s — #5353 slice-3 follow-up S (remove dead ensure_sync_daemon residue)

Reviewer: reviewer-renata (independent). Branch `issue-5353-s-followup` @ 77dbb663, detached.
Op: 01M3SRJHKA39GQAYSEP2A7RMN5

## Verdict: REQUEST-CHANGES (one small blocking item: changelog entry)

## Findings (by severity)

1. **MEDIUM / blocking: breaking public-API change without a CHANGELOG entry.**
   `emit_status_transition`, `start_implementation_status` and `start_review_status` are in
   `specify_cli.status.__all__` (src/specify_cli/status/__init__.py:507-508, :577). `emit_status_transition_batch`,
   `emit_status_transition_(batch_)transactional` and `queue_saas_emission` are public module-level names.
   Before this change, a caller that passed `ensure_sync_daemon=` had it silently ignored. Now that caller gets
   a `TypeError`. Precedent: the same signature keeps `sync_dossier` as a "3.2.6 compatibility" no-op
   (src/specify_cli/status/emit.py:873). CHANGELOG `[Unreleased] - 4.0.0rc5 ### Breaking` also lists
   Python-API removals and renames (for example `DistributionProfile`, `runtime.next.decision`).
   **Fix:** add a Breaking bullet under `[Unreleased] - 4.0.0rc5` in CHANGELOG.md. It should name the removed
   `ensure_sync_daemon` keyword on those functions. Before: accepted, and ignored since the sync transport was
   deleted. After: `TypeError`. Migration: drop the argument. (The alternative, a no-op compatibility keyword
   like `sync_dossier`, would undercut the dead-code goal. The changelog entry is the better fix.)
2. **NIT (no action needed):** commit 362c8f3b alone leaves the tests red, because test call sites still pass
   the kwarg until f52ba662. That follows from the protocol's ordering of product commits before test commits.
   Squash-on-land makes it moot.
3. **NIT (no action needed):** `docs/reports/dead-code-review/2026-09-30/*` still lists this chain as open.
   That report is a dated snapshot, so leave it.

## Verified
- **Deadness.** `saas_moment_handler` (zeitgeist_bridge.py:114) is the only production handler in the
  SaaS fan-out slot (`ensure_zeitgeist_moment_handlers`, adapters.py:216). `_broadcast_status_transition`
  reads only these named keys: wp_id, from_lane, to_lane, actor, mission_slug, metadata, repo_root. It never
  forwards `**kwargs` wholesale. `adapters.fire_saas_fanout` reads wp_id, from_lane, to_lane, force and
  metadata, and sets repo_root. A repo-wide grep for `ensure_daemon` / `ensure_sync_daemon` in src/,
  zeitgeist_client/, tests/, packs/ and docs/ (excluding kitty-specs history and dated reports) finds 0 hits
  after the change. No `kwargs["ensure_daemon"]` and no getattr access anywhere.
- **Deleted TestMergeLightweightEmit.** Its only other assertion was that `emit_status_transition` calls
  `_saas_fan_out` once. `TestFlatShellFanOutSeam::test_single_fan_out_default_fires_after_release` already
  pins that, and break 1 proves it. The "lightweight path" had no meaning beyond the dead kwarg. The deletion
  is a clean RETIRE with an existing guard.
- **Mechanics.** Every removed parameter was keyword-only, so positional arity is unchanged. The `*,` markers
  dropped in `_send_to_saas`, `_fallback_emit_single` and `_fallback_emit_batch` were only there for the removed
  parameter. `queue_saas_emission` keeps `*,` with mission_slug and repo_root. No dangling markers.
- **Gates.** `test_no_dead_symbols` tracks symbols, not parameters, so the implementer's claim holds.
- **Style.** ruff check passes on the touched files. The 4 files `ruff format` would change are all on the
  pyproject format-exclude ratchet (lines 565, 640, 1205, 2362) and were not reformatted, so the ratchet is
  correct. No new noqa or type-ignore. Commit trailers are present.
- **Other.** No orchestrator-api JSON contract change. No docs name the kwarg.

## Breaks re-run (each reverted with `git checkout -- src/`; `git status` clean afterwards)
| # | Mutation | Catching test | Result |
|---|---|---|---|
| 1 | emit.py:1023 `if fan_out:` -> `if False:` (skip fan-out in emit) | tests/status/test_emit.py::TestFlatShellFanOutSeam::test_single_fan_out_default_fires_after_release | RED: `saas_fan_out.assert_called_once()` |
| 2 | emit.py:1581 delete `mission_id=event.mission_id,` (fan-out drops a real kwarg) | tests/status/test_emit.py::TestSaasFanOut::test_saas_called_when_available | RED: dict diff `{'mission_id': None}` |
| 3 | outbound.py:78 `resolved_repo` -> `None` (break outbound forwarding) | tests/specify_cli/coordination/test_outbound.py::test_saas_emission_preserves_mission_slug_and_repo_root | RED: `assert None == PosixPath(.../repo)` |
| 4 (own) | status_transition.py:1068 `queue_saas_emission(` -> no-op lambda (transactional door never queues fan-out) | tests/specify_cli/coordination/test_phantom_fanout.py::test_transactional_door_fans_out_only_after_commit[single], [batch] | RED (2 failed, 23 passed) |

## Tests run
- The 16 edited test files, plus test_no_dead_symbols, test_layer_rules, test_no_retired_subsystems,
  test_ruff_pytest_style_baseline and test_ruff_format_exclude_ratchet, with `-n 8 --dist loadfile`:
  **497 passed, 5 skipped**, 0 failed.
- mypy on the 6 touched src files at HEAD: 5 `no-any-return` errors. None is on a line the diff touches
  (status_transition.py:174/202/789, work_package_lifecycle.py:100/170), and a diff that only deletes lines
  cannot add an `Any` return. The side-by-side run against origin/main was blocked by the sandbox. The command
  was: check out origin/main's 6 files, run `mypy` with the same arguments, then restore HEAD.
