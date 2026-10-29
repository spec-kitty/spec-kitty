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
