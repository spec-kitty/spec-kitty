# Research — doctor-identity-docs-sync-01M66956

Discovery findings captured before planning. Evidence gathered on
`main@512567eee7` (checkout `/home/exedev/work/sk-6760`, branch
`issue-6760-doctor-identity-docs-sync`). Planning artifacts live in
`kitty-specs/doctor-identity-docs-sync-01M66956/` in the primary checkout on
the topic branch (the coordination worktree
`.worktrees/doctor-identity-docs-sync-01M66956-coord/` carries only the event
streams).

## Decisions

1. **The defect reproduces on current `main`.** The page
   `docs/migrations/mission-id-canonical-identity.md` documents `ok`, `legacy`
   and `conflict` states and a JSON sample with `status`, `total`, `ok`,
   `conflicts`, `dir`, `mission_slug` — none of which the CLI prints. Live
   `spec-kitty doctor identity --json` (run from this checkout, `uv run`)
   prints a different contract (evidence below). Not superseded: the last
   commits touching the page are #5875's residue additions, which explicitly
   left the rest stale (issue body: "#5875 added only the `residue` bullet").
   `git log -S '"status": "legacy_present"'` bottoms out at the 3.x doc
   relocation (#2313), i.e. the sample predates the FR-045 four-state
   contract.
2. **The live JSON contract** (from
   `src/specify_cli/cli/commands/_identity_audit.py::_build_identity_json` and
   `src/specify_cli/status/identity_audit.py`), confirmed by live runs:
   - `summary`: counts for `assigned`, `pending`, `legacy`, `orphan`,
     `residue` (zero-filled, all five always present).
   - `missions[]`: one row per `kitty-specs/` child, fields `path` (absolute),
     `slug`, `mission_id`, `mission_number`, `state`, `error`,
     `residue_reason`.
   - `duplicate_prefixes`: `{prefix: [row, ...]}` for 3-digit prefixes shared
     by ≥ 2 missions (FR-011); residue excluded.
   - `ambiguous_selectors`: `{handle: [row, ...]}` for handles resolving to ≥
     2 missions (FR-012); residue excluded.
   - `fail_on_triggered`: bool — whether `--fail-on` matched any row (exit 1).
   - `residue_remedies`: `{reason: remedy}` — present only when at least one
     `residue` row exists (#5875).
   - The five states and their definitions are identical to the live
     `spec-kitty doctor identity --help` text, which is the same contract
     `docs/api/cli-commands.md` carries (kept fresh by
     `scripts/docs/check_cli_reference_freshness.py`).
3. **Adjacent same-page staleness is in scope** (same defect class: page vs
   live output, same audit flow): the Step 2 prose "If `conflicts > 0`, resolve
   them first" and the Step 3 claim "The backfill refuses to run while
   conflicts are present" reference a conflict gate that no longer exists;
   `migrate backfill-identity` (live, dry-run on a fixture) prints a summary
   table (`Total missions scanned / Written / Skipped / Errors / Number
   coerced`), not the "Scanning kitty-specs/ ... minted ..." transcript on the
   page, and `specify_cli/migration/backfill_identity.py` contains no
   duplicate/conflict refusal.
4. **Drift guard.** `docs/migrations/` pages have no freshness guard (the
   CLI-reference freshness check covers only `docs/api/cli-commands.md`), which
   is how this drift happened. A small structural test in `tests/docs/`
   (precedent: `tests/docs/test_artifact_placement_seam_page.py` — structure
   and citations, never prose) will pin the page's state list and sample keys
   to the imported live contract (`specify_cli.status.IDENTITY_STATES`,
   `IdentityState.to_dict`, `_build_identity_json`), so a future contract
   change that leaves the page behind fails CI. Red-first: the test fails on
   the pre-fix page.
5. **Mission type `software-dev`** (not `documentation`): the change includes a
   red-first test plus docs, and the operator's brief prescribes
   `--mission-type software-dev`.

## Evidence

- Live run on the clone itself (`uv run spec-kitty doctor identity --json`):
  `summary {assigned: 371, pending: 290, legacy: 0, orphan: 0, residue: 0}`,
  661 `missions[]` rows, non-empty `duplicate_prefixes` (e.g. `041`, `080`)
  and matching `ambiguous_selectors`, `fail_on_triggered: false`. Row keys:
  `path, slug, mission_id, mission_number, state, error, residue_reason`.
- Throwaway fixture project `/tmp/sk-fixture-6760` (git repo, `.kittify/`,
  `kitty-specs/001-auth-system` with `mission_number: 1` and no `mission_id`;
  `kitty-specs/002-dashboard` with `mission_id` and `mission_number: null`;
  `kitty-specs/leftover-junk` with no `meta.json`): live output
  `summary {assigned: 0, pending: 1, legacy: 1, orphan: 0, residue: 1}`,
  three `missions[]` rows (legacy / pending / residue with
  `residue_reason: "no_meta"`), empty `duplicate_prefixes` and
  `ambiguous_selectors`, `fail_on_triggered: false`, and a `residue_remedies`
  block with the `no_meta` remedy. This fixture is the shape the page's
  Step 2 sample will mirror.
- `spec-kitty migrate backfill-identity --dry-run` on the same fixture:
  summary table output as quoted in decision 3.

## Open questions

- None blocking. (Resolved during discovery: whether `residue_reason` belongs
  in the documented row fields — yes, it is a row field of the live contract
  and the page's residue section already leans on it.)
