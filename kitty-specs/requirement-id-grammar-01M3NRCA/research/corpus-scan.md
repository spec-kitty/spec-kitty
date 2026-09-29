# NFR-001 compatibility-evidence corpus scan (WP08 / T036)

This is the committed evidence report for `research/corpus_scan.py` (T035).
It runs the mission's merge-base with `upstream/main` ("base") and the
mission's branch head ("head") over the SAME file list -- every
`kitty-specs/*/spec.md` and `kitty-specs/*/tasks/WP*.md` -- and classifies
every difference as an **intended fix** or a **regression**. Full machine
data is in the committed `research/corpus-scan.json`.

**Pre-PR squad correction (review cycle 3, MEDIUM finding).** Section (d)
below only tracks the transition of individual raw WP-frontmatter *ref
tokens*. It never asked whether a functional requirement that only became
*declared* through (c)'s newly-recognised letter-suffixed shape actually
has any WP mapped to it -- so the previous revision of this report claimed
"only mission `058` newly fails re-finalize", which undercounted the real
set. A new **section (e)** closes that gap by running each side's own
`compute_coverage` (the exact function `finalize-tasks`'
`unmapped_functional_requirements` key is built from) over the corpus; see
(e) and the corrected "Missions whose NEXT re-finalize newly fails" list
below.

## Method

- **Merge-base SHA**: `f8ef65cfb3cfe30cba5d1680ede076d1251707c2`
  (`test(landing): use a non-/tmp file:// URL in the verbatim fixture
  (#5270)`), computed with `git merge-base HEAD upstream/main` at scan time
  (this mission's own doctrine reminder,
  `docs/context/orchestration.md#target-ref--commit-target`, applies: this
  is the mission's Target Ref, not a `main`-branch instruction).
  **Deviation from the SHA recorded in the previous revision of this report
  (`ddf114f06c54e5454bad5c3172e7049a95f7f862`)**: `upstream/main` advanced
  again between review cycles; the scan uses the real, re-verified
  merge-base rather than the stale prior SHA, per the same instruction that
  produced that earlier correction.
- **Head SHA**: `e7b8cd9b49b2801f49140b2fbc5e5ce1a15906dc` (`docs(mission):
  align the payload contract and ownership records with the pre-PR folds`
  -- the repo-root checkout HEAD at scan time, `git rev-parse HEAD` in the
  repo root). No file under `src/` changed between the two runs in this
  cycle (see the determinism check below), so the phase-(a)-(d) results
  are directly comparable to the prior revision modulo corpus growth
  (explained per-section below); only (e) is new.
- **Head-source preflight** (checked before any measurement):
  1. `src/specify_cli/requirement_mapping/grammar.py` exists and exposes
     `classify` and `canonical`.
  2. `src/specify_cli/requirement_mapping/lint.py` exposes
     `lint_spec_requirement_ids`.
  3. `src/specify_cli/requirement_mapping/__init__.py` exposes
     `compute_coverage` (the (e) API), `parse_requirement_ids_from_spec_md`
     and `read_all_wp_raw_requirement_refs`; the base module
     `src/specify_cli/requirement_mapping.py` exposes the same three names
     (with base's own `compute_coverage` implementation, `ref.upper()`
     matching rather than `grammar.canonical()`) -- confirmed by the
     worker's own `isolation` block below, not asserted separately.
- **Commands** (from the repo root; `<tmp>/rig-base` denotes the throwaway
  merge-base worktree, created once with `git worktree add --detach
  <tmp>/rig-base f8ef65cfb3cfe30cba5d1680ede076d1251707c2` under `/tmp`
  before both scans and shared by every re-run in this cycle):
  ```bash
  .venv/bin/python kitty-specs/requirement-id-grammar-01M3NRCA/research/corpus_scan.py \
    --corpus-root "$(pwd)" \
    --base-src <tmp>/rig-base/src \
    --head-src "$(pwd)/src" \
    --out-dir <scratch>/research
  ```
  The driver process itself never imports `specify_cli` (only the worker
  subprocesses do, each with its own `PYTHONPATH`), so no `PYTHONPATH`
  prefix is needed on this command.
  Run twice at the same SHAs (`HEAD` was re-checked with `git rev-parse
  HEAD` before each run and was identical both times); `diff` of the two
  `corpus-scan.json` outputs was empty (byte-identical) -- the determinism
  check.
- **File counts**: 3,558 files (522 `spec.md`, 3,036 `tasks/WP*.md`), hash
  `db4a1fcfb03852b74bbaf9c12c155f96b511c361a80711ce6463afbe0de45931`
  (`sha256` of the sorted, repo-relative POSIX path list). Both workers read
  file CONTENT from the head tree only; the file-list hash proves both sides
  received the identical list. The corpus grew by 2 specs / 14 WP files
  since the prior revision's snapshot (520/3,022) -- new missions landing on
  `upstream/main` between review cycles, not a scan artefact; every
  per-section count below is explained against that growth.
- **Python**: 3.11.15 (the repo `.venv`; each worker subprocess ran under
  the same interpreter with `PYTHONPATH` pointed at its own side's `src`).
- **Import isolation**: both workers asserted `specify_cli.__file__` (and
  `runtime`/`charter`/`kernel`, when importable) resolved under the
  expected side's `src`, and the driver additionally asserts `--base-src !=
  --head-src`. `corpus-scan.json`'s `isolation` block records the per-side
  resolution as a boolean (never the raw `/tmp` path, so the JSON output
  stays byte-identical across runs at the same SHAs) -- both sides: `ok:
  true`.
- **Worktree removal proof**: `git worktree remove --force <tmp>/rig-base`
  followed by `git worktree prune`; the subsequent `git worktree list`
  no longer lists it.

## (a) Bare prose / SC-005

| | base | head |
|---|---|---|
| flagged specs | 1 | 1 |

**Unchanged from the prior revision.** Both sides flag exactly
`kitty-specs/egress-refusal-consolidation-3110-01KYW895/spec.md` with ids
`C-1`, `C-3`. **Verdict: PASS** (`head_count (1) <= base_count (1)`).

**SC-005 positive control**: the egress spec is still flagged at the head
with the same `C-1`/`C-3` ids -- it was **not** silently dropped. C-009
(unqualified, unsuffixed FR/NFR/C candidates only) keeps this spec's
citations of its own orchestrator-notes ids (`C-1`..`C-4`, distinct from
its own `C-001`..`C-011` constraints) as bare-prose candidates exactly as
before the mission.

## (b) Newly refused specs (planning hand-off lint, FR-013)

**Count: 4 specs, matching the expected 4 -- unchanged from the prior
revision** (same 4 missions, same 84 refused tokens total: 4 + 71 + 1 + 8;
the corpus's 2 new specs contribute nothing new here). Every refused token
is a kind-prefixed token in a declared position (table row, heading,
bullet, or bold lead) that the grammar cannot parse -- **all four are
classified INTENDED FIX**, none are false refusals of a legitimate id, an
HTML-comment token, a non-first table cell, or a prose compound outside a
declared position:

1. **`coord-read-residuals-merge-lanes-and-identity-routing-01KW2M8V`** (4
   tokens: `C-009-mirror`, `C-EXCL-2167`, `C-EXCL-FALLBACK`, `C-SEQ`) --
   none of these are `<kind>-<digits>[<lowercase letter>]`; they are
   non-numeric qualifier-style constraint labels the old free-text scan
   never validated. **Intended.**
2. **`doctrine-enrichment-frontend-brownfield-normalization-01KQ48XA`** (71
   tokens: `FR-001.1` .. `FR-012.5`, a dotted sub-requirement numbering
   scheme) -- `.N` is not the grammar's `[<lowercase letter>]` suffix.
   **Intended** (a pre-existing dotted-numbering convention this spec used
   that the grammar correctly refuses as malformed).
3. **`doctrine-public-api-surface-01KZPDSR`** (1 token: `C-007-mission`) --
   this spec's own locally-declared id fails the grammar's exact-digits
   capture (a known, pre-existing declared-shape gap, not new to this
   mission). **Intended** -- the lint correctly reports it as needing a
   grammar-conforming shape; this was never a validly-parsed id before
   either (the old code silently ignored it rather than reporting it).
4. **`mission-type-drg-edges-01KXKY2N`** (8 tokens: `C-S1`..`C-S5`,
   `SC-S1`..`SC-S3`) -- a non-numeric suffix (`S1`, not digits). **Intended**
   -- exactly the malformed-kind-prefixed-token shape FR-013 exists to
   catch.

## (c) Declared-set growth

**421 of 522 specs grew; 0 specs shrank** (prior revision: 419 of 520; the
delta tracks the corpus's +2 specs, not a behaviour change).

All 2,648 added ids across those 421 specs match `(FR|NFR|C|SC)-\d+[a-z]?`
-- i.e. every addition is either a bare `SC-###` id (2,614 of 2,648) or a
lowercase-letter-suffixed `FR-###a`/`NFR-###a`/`C-###a` id (28 of 2,648),
plus 6 letter-suffixed `SC-###a` ids. **All 2,648 are classified INTENDED**
(FR-003: SC is a new recognised kind; the lowercase suffix is a new
recognised declared shape). Zero placeholders (`FR-00N`), zero qualified
citations, and zero description-cell leaks were found in the added set.
**`corpus_scan.py` itself makes no claim about this shape** -- per C-008 the
script contains no requirement-ID regex of its own, and
`_compare_declared_growth` only computes set differences; the
`(FR|NFR|C|SC)-\d+[a-z]?` breakdown below is a post-hoc, reviewer-facing
check run separately against the committed `corpus-scan.json`, not an
assertion inside the script:
```bash
python3 -c "
import json, re
d = json.load(open('corpus-scan.json'))
growth = d['declared_growth']['growth']
pattern = re.compile(r'^(FR|NFR|C|SC)-\d+[a-z]?$')
counts = {'matched': 0, 'other': 0}
for ids in growth.values():
    for i in ids:
        counts['matched' if pattern.match(i) else 'other'] += 1
print(counts)
"
```
This printed `{'matched': 2648, 'other': 0}` against the committed
`corpus-scan.json` (2,614 bare `SC-###`, 6 letter-suffixed `SC-###a`, 28
letter-suffixed `FR`/`NFR`/`C` -- among the latter 28, the four new
`FR-028a`..`FR-028d` tokens in `028-cli-event-emission-sync`, which is also
the one mission (e) below finds with no prior-revision precedent). Full
per-spec list: `corpus-scan.json` `declared_growth.growth`.

**Shrink**: 0 specs, same as the prior revision. The one expected shrink
class -- an id declared only inside an HTML comment, now correctly blanked
by `blank_html_comments` before scanning (WP01) -- still does not fire
against the live corpus.

## (d) WP ref transitions

**10,897 raw WP-frontmatter tokens compared** (prior revision: 10,854; the
+43 tracks the corpus's +14 WP files). Matrix (excluding the unchanged
`kept/known -> accepted` baseline, 10,851 tokens -- prior revision: 10,808
-- where a ref valid under the old known-ref gate is still valid, just
relabelled under the new `accepted` vocabulary):

| Transition | Count | Classification |
|---|---|---|
| `dropped -> accepted` | 12 | **Intended** (#2991: the ref is now kept and counted) |
| `dropped -> rejected:malformed` | 5 | **Intended**, but **fail -> fail** for 3 of 5 (see below) |
| `kept/unknown -> rejected:unknown_spec_id` | 29 | **Intended**, and **fail -> fail for all 29** (see below) |
| `kept/known -> rejected:*` | 0 | (none found -- this would be a probable regression) |

**Unchanged from the prior revision in every respect except the baseline
`kept/known -> accepted` count** (which only grows with corpus size): same
46 non-baseline transitions, same missions, same tokens -- re-verified
directly against `corpus-scan.json`'s `wp_ref_transitions.changed` for this
revision's SHAs.

**`dropped -> accepted` (12, all intended)** -- letter-suffixed and SC refs
the old regex never recognised at all, now correctly kept and mapped:
`065-wp-metadata-state-type-hardening` WP05 (`FR-012a`..`FR-012d`),
`cascade-asset-silent-drop-01M0RME0` WP03 (`FR-005a`),
`charter-epic-golden-path-nfr-budget-01M35H35` WP02/WP03/WP06/WP08
(`SC-001`..`SC-005`), `common-docs-consolidation-01KW3Q6M` WP04 (`SC-006`).

**The base `finalize-tasks` gate already blocked on both failure shapes
below.** `_validate_requirement_mapping` calls `raise typer.Exit(1)`
whenever `unknown_requirement_refs` is non-empty (built by
`_classify_wp_requirement_refs`, which buckets a WP with NO refs after
normalization into `missing_requirement_refs_wps` -- also gate-failing),
and `_read_spec_requirement_ids` calls `raise typer.Exit(1)` when
`spec.md` does not exist. Both are gate-wide, mission-level failures at
base -- not merely recorded-but-non-blocking.

**`dropped -> rejected:malformed` (5, all intended)** -- all five tokens are
non-ID garbage that leaked into `requirement_refs` frontmatter in mission
`058-mission-template-repository-refactor`, split across two WPs with
different base outcomes:
- **WP08** (`Constitution`, `terminology`, `canon` -- 3 tokens): at base,
  `normalize_requirement_refs_value` matches none of these, so WP08's
  normalized ref list is empty and it lands in `missing_requirement_refs_wps`
  -- **already failing at base**. Fail -> fail; not a new failure.
- **WP10** (`ADR`, `2026-03-27-1` -- 2 tokens, alongside a separate,
  unaffected `FR-018`): at base these two tokens are silently dropped by
  the same regex (WP10 keeps `FR-018` and is not itself in
  `missing_requirement_refs_wps` or `unknown_requirement_refs` on their
  account) -- **WP10 passes at base**. At head, `grammar.classify` rejects
  both as `malformed`, which DOES fail `_validate_requirement_mapping`.
  **WP10 is the one genuinely new WP-ref-transition failure in this WP
  frontmatter class specifically** (see the corrected mission-level list
  below, which also folds in (e)'s coverage-gate failures).

The new grammar correctly and loudly rejects `ADR`/`2026-03-27-1` as
malformed where the old regex silently dropped them; that tightening is
intended (FR-019), and it is also a real, newly-introduced failure for
WP10 specifically -- both things are true at once.

**`kept/unknown -> rejected:unknown_spec_id` (29, all intended, all
fail -> fail)** -- 27 of the 29 are in mission
`charter-doctrine-mission-type-configuration-01KSWJVX` (WP01-WP15,
`FR-001`..`FR-019`); this mission's own `spec.md` does not exist on disk, so
`_read_spec_requirement_ids` already raises `typer.Exit(1)` at base -- the
whole mission was **already failing before any of these 27 refs were even
classified**. The remaining 2 are
`excise-doctrine-curation-and-inline-references-01KP54J6` WP03 (`NFR-002`)
and `spdd-reasons-activation-split-brain-01M1K6VN` WP01 (`C-004`) --
genuinely undeclared refs in specs that DO exist; at base these land in
`unknown_requirement_refs`, which already fails `_validate_requirement_
mapping` for that mission too. **All 29 are fail -> fail.**
Full item list: `corpus-scan.json` `wp_ref_transitions.changed`.

No `kept/known -> rejected:*` transitions occurred anywhere in the corpus --
the class the review guidance calls a probable regression is empty.

## (e) Coverage verdict, base vs. head (`compute_coverage`)

**New section, added for the pre-PR squad's MEDIUM finding.** (c) only
diffs the *declared* functional-ID set per spec; it never checks whether a
newly-declared functional ID actually has a WP mapped to it. This section
runs each side's OWN `compute_coverage` (imported from that side's
`specify_cli.requirement_mapping` -- base's naive `ref.upper()` match, head's
`grammar.canonical()` match; no regex of this script's own, C-008) over
that side's own raw `requirement_refs` mapping (`read_all_wp_raw_
requirement_refs`) and that side's own declared-functional-ID set
(`parse_requirement_ids_from_spec_md(...)['functional']`) -- the exact same
inputs `finalize-tasks`' `unmapped_functional_requirements` key is built
from.

**Per mission: 500 unchanged, 9 newly unmapped, 0 newly mapped, 0 mixed.**

| Mission | Newly-unmapped FR IDs |
|---|---|
| `028-cli-event-emission-sync` | `FR-028a`, `FR-028b`, `FR-028c`, `FR-028d` |
| `060-canonical-status-model-cleanup` | `FR-009a` |
| `065-tasks-and-lane-stabilization` | `FR-002a`, `FR-010a`, `FR-010b` |
| `078-planning-artifact-and-query-consistency` | `FR-002a`, `FR-008a`, `FR-014a` |
| `content-address-ratchet-allowlists-01KX8M4D` | `FR-007b` |
| `doctrine-built-in-seam-consolidation-01KYW3TX` | `FR-001b` |
| `mission-type-doctrine-authority-01KXH6GE` | `FR-003a` |
| `operator-config-ergonomics-01M04YK8` | `FR-004a` |
| `up-org-doctrine-consumers-01M05YAB` | `FR-006a` |

**All 9 are classified INTENDED FIX**, in the exact sense the mission's own
`spec.md` Assumptions section names: "Existing missions that re-finalize
will, for the first time, see their declared letter-suffixed functional
requirements counted and their malformed or undeclared refs fail. Newly
failing coverage there is the intended fix, not a regression." In every
one of these 9 cases the functional ID was **already sitting, unreferenced,
in the spec** before this mission -- at base, the old declared-ID parser
simply never recognised the letter-suffixed shape (`FR-###a`/`FR-###b`) as
a declared functional requirement at all, so `compute_coverage`'s
`functional_ids` input never included it and it could never appear in
`unmapped_functional`. At head, FR-003's newly-recognised declared shape
makes it visible for the first time, and because no WP in any of these 9
missions references it (under either the old regex or the new grammar),
`compute_coverage` correctly reports it as unmapped: a real, pre-existing
coverage gap the mission's own tightening now surfaces rather than one the
mission introduced. `028-cli-event-emission-sync` is the one mission in
this set with no prior-revision precedent -- it entered the corpus (or, more
precisely, its `FR-028a`..`FR-028d` declarations entered the *declared-ID
growth set*, (c) above) after the prior revision of this report was
written; it is the same class as the other 8, just newly in view because
the corpus grew (see the Method section's file-count delta).

**8 of these 9 exactly reproduce the pre-PR squad's independently-verified
list; the 9th (`028-cli-event-emission-sync`) is additional, not
contradictory** -- it was not yet part of the corpus (or not yet declared)
when the squad ran its manual check. The squad's own CLI-confirmed positive
control -- `finalize-tasks --validate-only` on `operator-config-ergonomics-
01M04YK8` exits 1 with `unmapped_functional_requirements: ["FR-004a"]` --
is reproduced exactly here and is now an executable floor
(`_assert_floors`) in `corpus_scan.py`, so a future revision of this script
cannot silently regress this check back to a false-clean result.

No `newly_mapped` or `mixed` missions were found: the tightening only ever
adds visibility to a pre-existing gap, never removes coverage anywhere in
the corpus.

## Interpretation and escalations

Every measured difference between the merge-base and the head is an
**intended fix**. (b) newly refuses 4 pre-existing malformed-shape specs at
the planning hand-off (a new, non-finalize-gated lint -- these are not
finalize failures). (d)'s `kept/unknown -> rejected:unknown_spec_id`
transitions touch WP-frontmatter tokens in three already-imperfect
missions (missing spec.md, or genuinely undeclared refs):
`charter-doctrine-mission-type-configuration-01KSWJVX`,
`excise-doctrine-curation-and-inline-references-01KP54J6`, and
`spdd-reasons-activation-split-brain-01M1K6VN` -- all three were **already
failing** `finalize-tasks` at the merge-base and remain failing at head --
not new failures.

**Missions whose NEXT re-finalize newly fails (corrected, per the pre-PR
squad's MEDIUM finding): `058-mission-template-repository-refactor` (via
its WP10's malformed refs, (d) above) plus the 9 missions listed in (e)
above (via their newly-visible `unmapped_functional_requirements`) -- 10
missions in total.** `058`'s own WP08 was likewise already failing at base
(non-ID garbage tokens left it with zero accepted refs even under the old
regex); only its WP10 is a new failure reason for that mission. Every one
of the 10 is an **intended fix**: a declared requirement that was
previously invisible (058: garbage tokens the old regex silently dropped
instead of rejecting; the (e) 9: letter-suffixed FRs the old declared-ID
parser never recognised) now correctly fails a gate it should always have
failed, per the spec's own Assumptions section. No mission that passed
`finalize-tasks` at base for a *content* reason (as opposed to a
pre-existing `spec.md`-missing or garbage-token defect) newly fails at
head.

The bare-prose detector's floor and SC-005 positive control both hold. The
declared-ID growth is 100% attributable to newly-recognised declared shapes
(SC kind, lowercase suffix), with zero suspect additions (verified by the
post-hoc check in the (c) section above, not by a script assertion). No
`kept/known -> rejected:*` transitions -- the probable-regression bucket --
occurred. (e)'s `compute_coverage` floor (the CLI-confirmed
`operator-config-ergonomics-01M04YK8` / `FR-004a` positive control) holds,
and no `newly_mapped`/`mixed` mission was found.

**No regressions found. Nothing to escalate.**
