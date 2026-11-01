# Contract: prose-only exemption from the heavy-battery subtraction (#6999)

Owner: `scripts/ci/gate_selection.py` (selection), `scripts/ci/battery_scope.py`
(CLI), `.github/workflows/ci-router.yml` (wiring). This file records the
contract the three must keep; it is not a second source of truth for any list.

## Inputs

| Name | Source | Meaning |
| --- | --- | --- |
| `paths` | `battery_scope.changed_paths(base, head)` — `git diff --name-only --no-renames` | the diff's paths, or `None` when no trustworthy diff exists |
| `mode` | router input mode (`pr` \| `full`) | `full` always means the whole leg |
| `prose_only` | `needs.prose-scan.outputs.prose_only` (passes `--prose-only`) | the PR-level, fail-closed #4842 verdict; absent/`false` means "not prose" |
| `scan_scope_match` | `needs.prose-scan.outputs.scan_scope_match` | true when a changed path matches the router's `arch_scan_scope` group (the test-pinned transcription of the declared scopes); the battery `if:` reads this, never a second reference to the `changes` group |
| `part` | `--battery-part <n/m>` | the leg whose gates are wanted |

## Guarantees

1. **Fail-safe (never narrows on doubt).** `paths is None`, `mode == "full"`, or
   any git/selection error answers `mode=full`, `run=true` — the whole leg.
   `prose_only` never changes this.
2. **Non-prose is unchanged.** With `prose_only=false` the answer is exactly
   today's: `None`/whole battery for a battery code group match, an unmatched
   `src/**` path, or a battery code helper; otherwise the declared scan-scope
   matches.
3. **Prose narrows to declarations.** With `prose_only=true`:
   - the answer is never `None` and never the whole leg;
   - it is exactly `{gate : any declared scan_scopes glob of gate matches any
     changed path}`, minus always-on gates (they run on every PR shape);
   - a code-group path, an unmatched `src/**` path or a battery code helper does
     not widen it (prose-only proves no behaviour change).
4. **Per-leg partition.** Each selected gate satisfies
   `gates_file(leg) = selection ∩ part_files(leg)`. The union over the two heavy
   legs equals the selection; the intersection is empty. A leg with no selected
   gate answers `run=false` and the job skips pytest, pack sync and the universe
   pre-step (existing #6996 behaviour).
5. **Router group model intact.** The battery `if:` names no new
   `needs.changes.outputs.<group>`, and it names the `arch_scan_scope` group
   exactly once: the prose exemption reads `prose-scan`'s `scan_scope_match`
   companion instead, so dropping the group's own OR term still reds the #6994
   planted control. `HEAVY_BATTERY_NON_SRC_GROUPS` stays `{architectural,
   ci_config, arch_scan_scope}`.
6. **No gate weakening.** Nothing disables, skips, xfails or narrows a gate for
   a diff its declaration matches; this contract only adds runs to a prose diff
   and removes the whole-battery subtraction for a declared match.

## Battery `if:` shape

```
(<existing group OR>) &&
(needs.prose-scan.outputs.prose_only != 'true' ||
 needs.prose-scan.outputs.scan_scope_match == 'true')
```

Truth table (routing group lit, i.e. a declared-scope diff):

| `prose_only` | `scan_scope_match` | battery |
| --- | --- | --- |
| `false` / absent | any | selected by the group OR (unchanged) |
| `true` | `true` | selected, scoped to declared matches |
| `true` | `false` | skipped (#4842 down-route, unchanged) |

The companion exists so the battery `if:` does not name
`needs.changes.outputs.arch_scan_scope` a second time: a second reference keeps
the group in the parsed job-gate set even when its own OR term is deleted, which
would make the #6994 planted control vacuous. `scan_scope_match` reads the same
parsed group (through `gate_selection.matches_declared_scan_scope`) in the job
that already holds the diff.

## Planted controls a test must keep red-capable

- Remove the `|| scan_scope_match == 'true'` exemption from a copy of the `if:`
  → the prose-only + declared-scope evaluation must flip to `false`.
- Delete the `changes.arch_scan_scope` OR term from a copy of the `if:` → the
  #6994 property must still red (the companion must not keep the group alive).
- Remove the `prose_only` branch from `select_battery_gates` → a code-group path
  under a prose verdict must return `None` (whole battery) and the pin must fail.
- Drop one declared gate from the selection → the "comment-scanning gate
  selected" pin must fail.
