# Discovery: one answer for a Mission's human slug (#6278)

## Decisions

### D1 — Adopt the issue's first option: the identity resolver learns the human slug

The issue offers two ways to make the commands agree: teach
`resolve_mission` the human-slug form, or refuse the form everywhere. We take the first.

Rationale: the human slug is already a supported handle. `agent tasks status` and
`agent status` reach it through the read-path placement seam
(`specify_cli.missions._read_path_resolver.resolve_bare_modern_mission_dir_name`, the
"bare modern slug" primitive added for #2050/#4723), and `docs/` tells operators to name a
Mission by its slug. Refusing it everywhere would be a behavior removal for a shipped,
documented surface, and would leave the two commands disagreeing in the opposite
direction. Widening the identity resolver fixes the reported command and every other
caller of the same seam at once, which is the smaller blast radius (DIRECTIVE_024).

### D2 — The fold lives in `_resolve_from_index`, not in a new ladder

`specify_cli/context/mission_resolver.py::_resolve_from_index` is the single
fail-closed-loud ladder shared by `FsMissionResolver` (a fresh `kitty-specs/` walk) and
`FakeMissionResolver` (a caller-supplied list). The fix belongs in its existing
"human slug" rung (priority 4), not in a parallel function, so every consumer of the
resolver — `resolve_mission_handle`, `resolve_selector`, `agent tasks`, `implement`,
`migrate`, `issue-verdict`, `acceptance-verdict`, `next` — inherits one answer
(C-001 in the spec).

### D3 — Strip the trailing `-<mid8>` only when it is that Mission's own mid8

`ResolvedMission` already carries `mid8` (first 8 characters of `mission_id`), so the
rung can compare indexed fields only and add no `meta.json` read (NFR-001).

The guard matters: `smoke-test-01M6BTQX` whose `mission_id` starts `01ZZZZZZ` must not
have `-01M6BTQX` stripped, because that tail is not an identity marker for it. This is
the same rule `specify_cli/lanes/branch_naming.py::_human_slug_for_mid8_branch` already
applies when composing branch names ("Strip the embedded mid8 only when it matches
mission_id's mid8; mismatched mid8 is not stripped"), so the two places that derive a
human slug from a composed one agree.

### D4 — Ambiguity stays loud

`_resolve_or_raise` already raises `AmbiguousHandleError` (with the full candidate list)
when a rung matches more than one Mission. The new matching goes through the same helper,
so two Missions sharing a human slug keep the no-silent-fallback refusal the issue and
the charter require.

### D5 — Precedence is untouched

Only the body of the existing priority-4 comparison changes. The full-ULID rung, the
`mid8` rung, the exact-directory rung (priority 3) and the numeric-prefix rung (priority 5)
answer exactly as before, so a Mission whose directory is literally named `smoke-test`
still wins over any fold of a composed sibling (spec, Edge Cases).

## Evidence

### Reproduction on current `main` (`287a226cfe`, CLI 4.0.0rc8)

Scratch project (`/tmp/repro6278/p`), issue recipe:

```
spec-kitty agent mission create smoke-test --json
  -> kitty-specs/smoke-test-01M6BTQX  (mission_id 01M6BTQXBFZMBKVGB8VXBRQW07)
spec-kitty agent tasks status --mission smoke-test      -> exit 0, resolves
spec-kitty implement WP01 --mission smoke-test          -> exit 2
   Error: No mission found for handle "smoke-test". Check that the handle is correct
   and that the mission exists in kitty-specs/.
spec-kitty implement WP01 --mission smoke-test-01M6BTQX -> resolves (WP file not found)
```

The issue reproduces exactly, with a mid8-minted slug.

### The two paths, as they exist today

| Path | Entry point | Human-slug behavior |
| --- | --- | --- |
| Read-path fold | `missions/_read_path_resolver.py::resolve_bare_modern_mission_dir_name`, reached from `tasks_shared.py` and `agent/status.py` via `placement_seam` | globs `kitty-specs/<slug>-*/meta.json`, requires a valid mid8 tail, raises `MissionSelectorAmbiguous` on >1 |
| Identity resolver | `cli/selector_resolution.py::resolve_mission_handle` → `context/mission_resolver.py::resolve_mission` | priority 4 compares `strip_numeric_prefix(mission_slug) == handle`; `strip_numeric_prefix` removes only `^NNN-`, so a `-<mid8>` tail can never match |

`cli/commands/implement_phases.py::detect_mission_context` calls `resolve_mission_handle`
directly, which is why `implement` is the command that refuses. `selector_resolution.py`
also hosts `resolve_mission_dir_with_bare_modern_fold` (the #4723 wrapper), but
`implement` does not call it — the wrapper exists for read commands and is not the seam
that decides `implement`'s Mission.

### Prior art and related work

- `#2050` / `#4723`: the bare-modern-slug fold and its ambiguity refusal, on the read
  path. This mission is the identity-resolver half of the same fold.
- `#4745`: folding the agent-layer Mission-resolution path onto the selection seam. Not a
  duplicate and not a blocker; this issue is a concrete user-visible case of the drift it
  describes. Its wider refactor is out of scope.
- `#6517`: `_resolve_exact_directory` short-circuit — the reason the ladder resolves a
  handle that names an indexed directory exactly before walking. Unaffected.
- `#6517`/`#5875` selection notes and the module docstring's priority list: the docstring
  example for priority 4 (`"foo-bar"` for `"083-foo-bar"`) describes the older slug shape
  and is updated by this mission.

## Open questions

- None blocking. The one judgement call — refuse vs accept the human slug — is the
  issue's own question and is answered by D1 with the reasoning above.
- The issue's "Also seen" note (status reads with `--owned-checkout` failing to find a
  Mission by short handle) is not reproduced here. It may be this same split or a second
  instance on the owned-checkout read path; C-003 keeps it out of scope unless the shared
  resolver fix already covers it, in which case the fix is noted in the PR.

## Plan-phase findings (Phase 0)

### The guard needs no new read

`ResolvedMission.mid8` is `mission_id[:8]`, populated by `_build_index` from the one
`meta.json` per Mission the walk already reads. The rung can therefore decide
"is this tail this Mission's own mid8?" from fields already in memory. No extra
`meta.json` read, no extra `kitty-specs/` scan — NFR-001 holds by construction.

### The same rule already exists privately, and must stay private there

`specify_cli/lanes/branch_naming.py::_human_slug_for_mid8_branch` implements exactly this
rule ("strip the embedded mid8 only when it matches mission_id's mid8") for branch
composition. It is private and `branch_naming` sits above `context/` in the import
direction, so the resolver must not import it — doing so would invert the layer and
create a cycle. The resolver shares the *rule*, not the symbol: the two definitions stay
independently readable, and the parity test is what keeps their behaviour aligned. This
is the honest trade: one duplicated three-line predicate rather than a new cross-layer
dependency or a new public symbol (NFR-003).

### Two ambiguity types, one rendered outcome

The identity resolver raises `AmbiguousHandleError`; the read-path fold raises
`MissionSelectorAmbiguous`. `cli/selector_resolution.py` renders both into the same CLI
envelope, and `resolve_mission_dir_with_bare_modern_fold` does the same translation. The
parity test therefore asserts on the CLI outcome (exit code + rendered message + the
candidate set), not on the exception class, so it pins what the operator sees rather
than an internal type choice.

### Red-first plan

1. `tests/context/test_mission_resolver.py`: add the human-slug row
   (`smoke-test-01M6BTQX` with mission_id `01M6BTQX…` resolves from `smoke-test`), the
   coincidental-tail negative row, and the ambiguity row. These fail with
   `MissionNotFoundError` on the current ladder.
2. `tests/specify_cli/cli/commands/test_selector_resolution.py`: the two-path matrix over
   the handle forms. The human-slug cell fails on `resolve_mission_handle` before the fix.
3. A CLI-level test that `implement` resolves the human slug through
   `detect_mission_context` (the pre-existing entry point the operator hits).

Each is red before the production edit and green after; none is written after the fix.
