# Evidence index — test-suite-remediation-01M3SSDW (#5346)

Materialized at closeout (tasks.md "Closeout (orchestrator)" step 1) from each WP's reported
evidence (review notes + final report), per data-model.md §4. Content is copied verbatim from
the scratchpad copies the implementers reported and from the full `reason` text of every
`to_lane: approved` event in `status.events.jsonl`; nothing here was invented, recomputed, or
rounded. Where a source number is simply not recorded (e.g. no `executed_before`/
`executed_after` pair given for an item), the field is left `null` and the gap is listed below.

**Correction (2026-10-01, coordinator-flagged):** the first pass of this index under-tallied
SC-005 because it sourced reviewer re-runs from `tasks/WP*/review-cycle-*.md` alone. Those
files are a short rendering of the approval event and are NOT the full record for most WPs —
the underlying `status.events.jsonl` `to_lane: approved` event's `reason` field (surfaced via
`review_ref: auto-approval:WP<NN>:<date>`) carries each reviewer's full itemized re-run for
**every** WP, often 1,000-3,000 characters of independently-reproduced plants where the
review-cycle file shows only "Approved by claude: approval:WP<NN>". This index now sources
reviewer re-runs from the approval events directly; the per-IC files quote the relevant
sentence of each approval note next to the record it confirms.

## IC index

| File | Concern | WP(s) |
|---|---|---|
| `IC-01-doctrine-probe-and-fragment-intent-fix.md` | Doctrine probe unmask + fragment-intent product fix | WP01 |
| `IC-02-closed-issue-markers.md` | Closed-issue markers: re-point, retire, re-cite | WP02 |
| `IC-03-quarantine-removal-and-lane-relocation.md` | Quarantine removal and lane relocation | WP03 |
| `IC-04-errors-fail-instead-of-skipping.md` | Errors fail instead of skipping | WP04 |
| `IC-05-contract-round-trip-relocation-map.md` | Contract round-trip relocation map | WP05 |
| `IC-06-5346-consolidation-and-compat-pins.md` | #5346 pins: consolidation trio + compat surface and copied literals | WP06 + WP07 |
| `IC-07-fr007-architectural-and-call-site-counts.md` | FR-007 class: architectural and live-source call-site counts | WP08 |
| `IC-08-fr007-corpus-and-registry-counts.md` | FR-007 class: corpus, data-artefact and agent-registry counts | WP09 |
| `IC-09-dead-symbol-atdd-contract-pins.md` | Dead-symbol ATDD pins + parity snapshot | WP10 |
| `IC-10-dead-symbol-allowlist-rekey.md` | Re-key and externalise the dead-symbol allowlist + #470 fold | WP11 + WP12 |
| `IC-11-retire-hash-toll-surfaces.md` | Retire the hash-toll surfaces + docs | WP12 (refresh-helper retirement) + WP13 |
| `IC-12-size-ratchet-and-adr.md` | Size ratchet + top-level-keys floor + ADR | WP14 + WP15 |
| `dead-symbol-parity/` | FR-009 parity snapshot (before/after JSON + scripts) | WP10, WP12 |

Split-concern merges follow tasks.md's closeout mapping exactly: IC-06 ← WP06 + WP07;
IC-10 ← WP11 + WP12; IC-11 ← WP12's refresh-helper retirement + WP13; IC-12 ← WP14 + WP15.
Every other IC maps 1:1 to its WP, per plan.md's "Implementation Concern Map" and
tasks.md's Subtask Index.

## What came from where

- **Per-WP evidence** (the body of each IC file): WP01-WP05, WP08-WP15 copied from the
  scratchpad evidence files each implementer reported (`wp01-evidence.md` through
  `wp15-evidence.md`, and `WP09_evidence_records.md`, `WP10-evidence.md`, `WP11-evidence.md`,
  `wp12/WP12-evidence.md`, `wp13_evidence_note.txt`), per the task brief's "Sources" list.
  WP06 and WP07 copied from `WP06-evidence-5346-consolidation-trio.md`,
  `WP06-cycle2-evidence.md` (the cycle-2 fold), and `wp07/evidence.yaml`. For WP05, WP06 and
  WP08 — the WPs with more than one review cycle — the **latest** cycle's evidence is used
  (WP05: `wp05_evidence.md`'s own "Cycle 2" section; WP06: the cycle-1 trio file plus the
  cycle-2 fold file; WP08: `wp08-evidence.md`, already the post-fix form, cross-checked
  against the cycle-1 BLOCKING finding in the review-cycle file).
- **Reviewer re-runs**: the `reason` field of every `to_lane: approved` event in
  `status.events.jsonl` (`review_ref: auto-approval:WP<NN>:<date>`), one per WP (15 events
  total, `reviewer_agent: claude`, acting independently as reviewer-renata per the quoted
  text). Every one of these 15 events carries itemized, specific planted-break/covering-guard
  reproductions with red/green results — not just WP05/06/08, which additionally had a
  rejected cycle 1 with its own write-up in `tasks/WP*/review-cycle-1.md`. The
  `review-cycle-*.md` files are a short rendering and are NOT a reliable proxy for "did the
  reviewer itemize a re-run" — for most WPs they show only a one-line "Approved by claude:
  approval:WP<NN>" even though the underlying approval event's `reason` field is 1,000+
  characters of itemized reproduction. `reviewer_rerun: true` is set only on records whose
  planted break or covering guard a reviewer's approval-note text explicitly describes
  reproducing, with its red/green result; where an approval note is silent on a given
  record's specific break, that record's `reviewer_rerun` stays `false`.
- **Parity JSONs** (`dead-symbol-parity/`): copied byte-for-byte from the scratchpad's
  `before.json` (WP10), `before_wp12.json` (WP12, committed here as `before-wp12.json`), and
  `after.json` (WP12), plus `parity_before.py`, `parity_after.py` and `wp11_parity.py`. See
  that directory's own `README.md` for the digest cross-check.

## SC-005 tally

Per tasks.md closeout step 1 / analysis C6: "each per-WP reviewer re-runs its WP's
Review-Guidance picks during review and reports which ones. At closeout the orchestrator
tallies them (≥ 6 FIX and ≥ 2 RETIRE across the mission), and sets `reviewer_rerun: true` on
those records." The tally below counts only records whose planted break or covering guard a
reviewer's approval-note text (`status.events.jsonl`, `to_lane: approved`) explicitly
describes reproducing, with its red/green result quoted in the record's own `notes`.

**FIX re-runs: 38** (minimum 6 met)

| WP | Evidence ids |
|---|---|
| WP01 | `EV-IC01-01` (breaks C, D), `EV-IC01-02` (break A), `EV-IC01-03` (break A) |
| WP02 | `EV-IC02-03` (`mission_state.py` `if False:` plant) |
| WP03 | `EV-IC03-01` (`accept.py` diagnose-exit plant) |
| WP04 | `EV-IC04-03` (version-detection `None` plant), `EV-IC04-05` (home-isolation, both loops), `EV-IC04-06` / `EV-IC04-07` (`sys.modules` `None` plant, covers both files) |
| WP05 | `EV-IC05-04` (Plant 4, longest-prefix mutant), `EV-IC05-05` / `EV-IC05-06` (the "swap both error messages" mutant, covers both new unit tests) |
| WP06 | `EV-IC06-04` (`#5346-4`), `EV-IC06-06` (`#5346-6` cycle-1 identity asserts), `EV-IC06-06b` (`#5346-6` cycle-2 `mission_branch` fold) |
| WP07 | `EV-IC06-05a` (`:481`), `EV-IC06-05c` (`:494`), `EV-IC06-07` (`#5346-7` teardown seam) |
| WP08 | `EV-IC07-F11` (per-site partition), `EV-IC07-F3` (`materialize_calls` floor) |
| WP09 | `EV-IC08-F5` (glossary-seed neutral + blank-surface probe), `EV-IC08-F10` (both AGENT_DIRS/AGENT_COMMAND_CONFIG violations) |
| WP10 | `EV-IC09-01` (ATDD xfail/`--runxfail` progression), `EV-IC09-02` (SC-003 `envelope` plant) |
| WP11 | `EV-IC10a-04` (L8), `EV-IC10a-05` (L3), `EV-IC10a-11` (L7, reviewer-authored, no corresponding WP11-numbered record) |
| WP12 | `EV-IC10b-02` (SC-003, re-keyed gate), `EV-IC10b-04` (REVIVED), `EV-IC10b-05` (ATDD chain-level GREEN), `EV-IC10b-06` (M11c widened authority), `EV-IC10b-08` (GONE "probably moved to" hint), `EV-IC10b-09` (M13 corpus floor) |
| WP14 | `EV-IC12-F2` (`:618` floor violation), `EV-IC12-K14a` (allowlist-entries cap), `EV-IC12-K14b` (widened cap), `EV-IC12-T068` (leaf-drift re-plant, "rows removed, leaves kept") |
| WP15 | `EV-IC12-ADR` (C-011 docs-gate red→green, reproduced via a separate scratch export) |

**RETIRE re-runs: 10** (minimum 2 met)

| WP | Evidence ids |
|---|---|
| WP02 | `EV-IC02-02` (MG-06, `pyproject.toml` events-floor plant), `EV-IC02-04` (MG-07, `[tool.uv.sources]` plant) |
| WP06 | `EV-IC06-03` (`#5346-3`, `TestWorktreeTeardownSeamRouting`) |
| WP07 | `EV-IC06-02` (`#5346-2`, `== 196` copy-pin retirement), `EV-IC06-05b` (`:490`) |
| WP08 | `EV-IC07-F12a` (`EXPECTED_ENCLOSING_COUNT`), `EV-IC07-F8` (`test_member_count`) |
| WP09 | `EV-IC08-F7` (census covering guard) |
| WP12 | `EV-IC10b-03` / `EV-IC11-00` (same reviewer reproduction, duplicated across `IC-10` and `IC-11` per the closeout split-concern mapping — counted **once**) |
| WP13 | `EV-IC11-01` (`source_module` L5 plant, plus the reviewer's own widened-section variant) |

**RE-POINT re-runs (not part of the SC-005 FIX/RETIRE minimums, recorded for completeness):**
`EV-IC02-01` (WP02, `#3113`→`#5493`).

Every count above cites the exact approval-note sentence in the evidence id's own file. A
handful of approval notes also describe the reviewer running an *additional* plant not in
the WP's own reported inventory (e.g. WP01's break B on `_collect_fragment_yaml_edges`, WP03's
second `accept.py:948` plant, WP07's `mission_type` teardown variant, WP09's "blank a real
term surface" probe, WP12's 11-plant adversarial sweep): these are folded into the closest
matching record's `notes` rather than invented as new FIX/RETIRE-tallied items, except where
the plant maps to a schema rule the WP already claimed to cover but never itemized
(`EV-IC10a-11`, WP11's L7) or forms a genuinely separate verification sweep with no 1:1 match
(`EV-IC10b-11`, WP12's remaining battery plants, recorded as `kind: NO-OP`, not counted).

No evidence record's `reviewer_rerun` was set to `true` without a quoted approval-note
sentence describing that specific break or guard being reproduced. Records with no matching
quote (e.g. `EV-IC04-01`/`EV-IC04-02`/`EV-IC04-04`, `EV-IC08-F4`, `EV-IC10b-07`, every `KEEP`
record except `EV-IC09-03`/`EV-IC10a-01`/`EV-IC10a-02` — see each IC file for the full
per-record list) keep `reviewer_rerun: false`.

## Kind vocabulary

Data-model.md §4 enumerates `kind: FIX | RETIRE | RE-POINT | KEEP | RESOLVED | NO-OP`. Two
WP-reported kinds fall outside this enum and are mapped here (per tasks.md's "if a record's
kind falls outside the enum, map it to the closest enum value" instruction; `data-model.md`
itself is unedited):

- **`RUN`** (WP01, masked-greens rows 1+3 — `EV-IC01-01`): used by WP01 for a pure
  masking-removal proof with no product defect (the probe is deleted and replaced by a loud
  precondition assert; red/green evidence is reported exactly as a `FIX` record would be,
  just with no product-code planted break at its center). Mapped to the closest enum value,
  **`FIX`**, since the record carries the full red (break)/green (revert) proof shape FIX
  requires, with planted breaks, a command, and before/after results. `EV-IC01-01`'s `kind`
  field is left as `RUN` in the file itself (with this mapping note inline) so the original
  WP-reported value is not silently overwritten; the README is the single place recording the
  reconciliation.
- **`RUN+FIX`** (WP01/WP02, masked-greens row 2 and MG-06 — `EV-IC01-02`, `EV-IC02-02`/`03`):
  a masking-removal (`RUN`) combined with either a product fix or a new coverage test
  (`FIX`). Recorded simply as **`FIX`**, since each of these records' own planted-break/
  revert proof matches the FIX validation rule (`new_form_under_break == fail`,
  `clean_tree == pass`, `planted_break.reverted == true`) and the masking-removal is the
  mechanism, not a separate validated claim.

No other WP used a kind outside the data-model §4 enum.

## Gaps (sources not recorded)

- Several `counts` sub-fields (`executed_before`/`executed_after`) are `null` where a WP's
  evidence reported only a qualitative pass/fail result for an individual plant and gave the
  executed-count pair only for the *combined* named-file run, not that one item in isolation
  (e.g. several WP06/WP07/WP08/WP09 rows). The combined counts are recorded in each IC file's
  "Final named-file run" section instead.
- WP13's `wp13_evidence_note.txt` is prose, not pre-formed `yaml` blocks like most other WPs;
  it was transcribed into data-model §4 record shape for `IC-11-retire-hash-toll-surfaces.md`
  without inventing any field value not present in the source prose.
- A small number of reviewer-described plants in the approval notes exercise a real invariant
  this mission's WPs cover but do not correspond to any single WP-reported evidence item —
  see `EV-IC10a-11` (WP11's L7 schema rule) and `EV-IC10b-11` (WP12's remaining adversarial
  battery: the plain-GONE case, the AnnAssign form, a rename-with-false-red-control, the
  byte-identical-twin/bite_i case, the star-import MOOT case, the dropped-from-`__all__`
  case, and the ghost/INVALID+bite_k case). These are recorded as new or consolidated
  records rather than silently dropped, each noting explicitly that it has no corresponding
  WP-reported id.
- (Superseded) an earlier pass of this index asserted "no review-cycle file for WP01-04 or
  WP09-15 names a specific reviewer-reproduced planted break." That was true of the
  `review-cycle-*.md` files alone but false of the underlying `status.events.jsonl` approval
  events, which the coordinator flagged and which this revision now sources directly; see the
  "Correction" note at the top of this file and the SC-005 tally above.
