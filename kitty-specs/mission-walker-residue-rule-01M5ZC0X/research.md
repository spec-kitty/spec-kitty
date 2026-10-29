# Research: Mission walkers share one residue rule (#5875)

Phase 0 grounding, recorded before the spec. Base: `origin/main` @ `143a39fc`.

## 1. Code grounding (re-verified on current main)

| Issue claim | Current main | Verdict |
|---|---|---|
| `_build_index` counts `spec.md` OR `meta.json` as a Mission | `mission_resolver.py:483` `_build_index` → `_index_entry` (`:452`) needs a `meta.json` with a non-empty `mission_id` | **Stale.** The resolver index already excludes spec.md-only folders. No change; the docstring stays accurate. |
| `list_missions_for_selection` counts `spec.md` OR `meta.json` | `mission_resolver.py:525-565`, the test at `:551` | **Holds.** It is the live defect. |
| `status/identity_audit.py` ~219, ~296 use `safe_is_dir` | `audit_repo` `:215-222`, `find_duplicate_prefixes` `:293-300` | **Holds.** |
| `_mission_type_audit.py` ~320 uses `safe_is_dir` | `audit_mission_types` `:318-324` | **Holds.** |
| The parity test in `tests/context/test_is_mission_dir.py` is missing | the file has only predicate-level cases | **Holds.** |

Also found (not in the issue): `cli/commands/agent/mission_feature_resolution.py:333`
`_list_feature_spec_candidates` uses the same spec.md-OR-meta.json rule, and its docstring
twin in `list_missions_for_selection` promises the two "never disagree on the count". This
one feeds `setup-plan`'s sole-mission auto-select, `agent tasks status`'s default Mission
and the detection-error payload, so it must change with selection.

### Red-first probe (git repo, one committed Mission + one untracked spec.md-only folder)

```
selection      ['legacy-spec-only', 'real']   # lists residue as a Mission
index          ['real']
is_mission_dir False                          # predicate: residue
identity       [('legacy-spec-only', 'orphan'), ('real', 'pending')]
mtype          [('legacy-spec-only', 'typeless'), ...]  # mislabelled
```

### Remedy gap (drives an operator decision)

`migrate backfill-identity` (`migration/backfill_identity.py:122`) and
`migrate normalize-lifecycle` (`normalize_mission_lifecycle.py:84`) both skip folders
with no `meta.json`. Only the 2.0.6 sweep (`m_2_0_6_consistency_sweep._repair_feature_meta`)
writes a baseline `meta.json`, and on existing projects the migration ledger already
records it as settled. So no existing command turns a spec.md-only folder into a Mission.

## 2. Architectural alignment

- **Mission Identity Model:** `mission_id` is the only runtime identity, and selectors fail
  closed on ambiguity. Selection that requires a `meta.json` (with identity, or tracked)
  matches it. Residue never reaches `find_ambiguous_selectors`, so it cannot fake an ambiguity.
- **ADR 2026-10-17-1 (migration ledger):** untouched. No migration is added, and no ledger
  partition changes.
- **#6680 residue rule:** `is_kitty_specs_residue` is the *write-seam* rule. A `spec.md` on
  disk stops it calling a folder residue, so the upgrade sweep can still repair the folder. The
  operator ruling makes the *selection/read* rule stricter: a spec.md-only folder is residue there.
  That is deliberate. The read side reuses `is_mission_dir` (`#5856`), plus a `meta.json` on disk,
  and leaves `is_kitty_specs_residue` unchanged. `RESIDUE_NOTICE`'s text ("no spec.md or meta.json
  on disk or in git") does not describe a spec.md-only folder, so the doctor finding uses its own
  remedy text next to it and does not reword the shared notice (the notice is regex-parsed by
  `residue_notice_path`).
- **Mission Status Read API (#5528, `services/mission-status-api`):** finds a Mission by reading
  `meta.json` for `mission_id` (`ArtifactAllowlist.java:30`). A spec.md-only folder is already
  not a Mission there, so the change brings the CLI closer to the read service.
- **Walker gate:** `tests/architectural/test_mission_resolver_walker_gate.py` allowlists
  `status/identity_audit.py`, `_identity_audit.py` and `_mission_type_audit.py` as distinct
  corpus walks. They stay raw walks, so the allowlist entries stay valid. They only add a
  per-directory predicate.

Nothing already done would be redone.

## 3. Related issues and surfaces

- #6627 / #6662 / #6680: the upgrade-migration route is fixed (the residue-safe sweep, plus a doctor
  finding for fabricated identities). Already noted on #5875 by the claim comment.
- #6673 (upgrade mints a `mission_id` when a tracked `meta.json` is missing): a separate concern
  in write seams. With this change, such a folder shows as `residue` in `doctor identity`, and
  the remedy offers a restore from git.
- In-flight sessions #6715 (approval guard), #6675 / #6193 (write API), events #92: no overlap
  with these files.
- No open PR touches `mission_resolver.py`, `identity_audit.py` or `_mission_type_audit.py`.
- `tests/specify_cli/migration/test_corpus_wp_snapshot_parity.py` and
  `tests/contract/test_mission_status_reality.py` walk the corpus directly. The dogfood
  `kitty-specs/` has 0 folders without a `meta.json` (647 checked), so none of their skips changes.

## 4. Operator decisions (2026-10-27)

| # | Decision | Ruling |
|---|---|---|
| D1 | Folders with only a `spec.md` | **Residue**, not Missions. Selection and the resolver do not list them. |
| D2 | Selection rule | `meta.json` on disk **and** `is_mission_dir` (identity, or git-tracked markers). |
| D3 | Remedy | Documentation only, no new command: delete the residue folder, or restore `meta.json` from git, or re-create it with `spec-kitty agent mission create` and move the `spec.md` in. |
| D4 | Doctor shape | A new `residue` state in `doctor identity` (section, JSON count, `--fail-on` value) carries the remedy. `doctor mission-type` skips residue. |

## 5. Tidy-first

Do first, behaviour-preserving: extract one shared kitty-specs child-walk helper for the
two identity-audit walkers and the mission-type walker. It keeps the `safe_is_dir` and fail-soft
`OSError` posture exactly. The residue filter then lands in one place.

## 6. Pre-merge adversarial squad (2026-10-29)

Three profile-loaded lenses, each read-only: architecture (`architect-alphonso`), failure modes (`debugger-debbie`) and spec fidelity (`analyst-annie`). All three returned **SHIP-WITH-FIXES**. The fold landed in `6ef843f8`, `c551b5f1`, `51cf5db4`, `1dc87c5e` and `6e715e34`, and was re-reviewed before push.

### Operator decisions (2026-10-29), amending the spec

| # | Decision | Ruling |
|---|---|---|
| D5 | `meta.json` present but unreadable or unparseable | It stays **residue** (not listed). `doctor identity` must say the Mission content is **corrupt** (reason `corrupt_meta`, read error kept), not "delete it". |
| D6 | `backfill-wp-status` scope (`--mission`, evidence manifest) | Use the command's own write-seam walker rule, so the repair command agrees with itself. Mission selection is unchanged. |
| D7 | `RESIDUE_NOTICE` wording | Reword it in this PR. C-002 is lifted for the notice text only; the `is_kitty_specs_residue` logic is unchanged. |
| D8 | Follow-up issues | File four, labelled `status:triage` (operator rule for every follow-up): #6757, #6758, #6759, #6760. |

### Finding dispositions

| Finding (lens) | Disposition |
|---|---|
| SR-2 status-facade gate red; status↔context import cycle (architecture, MAJOR) | **Fixed** (`6ef843f8`): `iter_kitty_specs_children` moved to `mission_resolver.py`, one `TrackedMissionPaths` memo with an injectable probe, facade-only imports. |
| Two near-identical memo classes; `classify_walk_entry` re-encoded the predicate (architecture) | **Fixed** (`6ef843f8`). |
| `tracked=None` means different things in the two predicates (architecture) | **Changed**: documented in both docstrings. |
| Broken-index posture differs between doctors (architecture) | **Accepted**, documented: `doctor identity` is a reporter (it errors); mission-type degrades. |
| Engine reports a fake collision on a healthy Mission (architecture) | **Deferred** → #6757. |
| "Residue" has three senses and no glossary entry (architecture) | **Deferred** → #6759. |
| `doctor topology` and other walkers are out of scope (architecture) | **Deferred** → #6758. |
| Corrupt or unreadable uncommitted `meta.json` shown as residue with a "delete" remedy (failure modes) | **Fixed** per D5 (`6ef843f8`). |
| Untracked id-less legacy Mission given the wrong remedy (failure modes, spec) | **Fixed**: per-reason remedies, including `backfill-identity` (`6ef843f8`). |
| Broken index gives a traceback and no JSON (failure modes, spec) | **Fixed**: one-line error and a `GIT_INDEX_UNREADABLE` envelope (`6ef843f8`). |
| Git restore recipe fails for an uncommitted deletion; `^` breaks Windows cmd (spec, MAJOR) | **Fixed**: `git restore`, `~1` (`6ef843f8`). |
| `backfill-wp-status` contradicts itself; the promised test was missing (spec, MAJOR) | **Fixed** per D6, with a red-first test (`c551b5f1`). |
| A mutant ("only a tracked meta.json counts") survives the tests (spec) | **Fixed**: the parity corpus gained three children (`6ef843f8`). |
| Header counts residue as Missions (spec) | **Fixed** (`6ef843f8`). |
| NFR-002 timing test skipped the residue path (spec) | **Fixed** (`6ef843f8`). |
| `RESIDUE_NOTICE` reuse deviation not confirmed by the operator (spec) | **Resolved** by D7 (`51cf5db4`). |
| Changelog, help and docs wording too broad (spec) | **Fixed** (`6e715e34`). |
| Leftover `feature` naming in `_list_feature_spec_candidates` (spec) | **Fixed**: renamed (`1dc87c5e`). |
| Migration guide state list out of date (spec) | **Deferred** → #6760. |
| Acceptance matrix was boilerplate, and its evidence SHAs predated the history rebuild (spec) | **Fixed** in the Mission record. |
| Symlink outside the repo, case-insensitive filesystem, coordination-worktree root (failure modes, NIT) | **Accepted**: behaviour predates #5812 and does not reach the CLI. |
