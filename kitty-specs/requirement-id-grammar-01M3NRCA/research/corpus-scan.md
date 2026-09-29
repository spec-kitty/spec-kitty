# NFR-001 compatibility-evidence corpus scan (WP08 / T036)

This is the committed evidence report for `research/corpus_scan.py` (T035).
It runs the mission's merge-base with `upstream/main` ("base") and the
mission's branch head ("head") over the SAME file list -- every
`kitty-specs/*/spec.md` and `kitty-specs/*/tasks/WP*.md` -- and classifies
every difference as an **intended fix** or a **regression**. Full machine
data is in the committed `research/corpus-scan.json`.

## Method

- **Merge-base SHA**: `ddf114f06c54e5454bad5c3172e7049a95f7f862`
  (`fix(doc-analysis): pin reporting/ in DEVELOPMENT_CONCERN_SUBDIRS`,
  2026-09-29), computed with `git merge-base HEAD upstream/main` at scan
  time. **Deviation from the planning-time base recorded in the spec
  (`aedb30cddd`)**: the branch was rebased onto a newer `upstream/main` tip
  after planning; the scan uses the real, re-verified merge-base rather than
  the stale planning-time SHA, per the orchestrator's instruction.
- **Head SHA**: `fdf383f34a746104d15afe44cf97d9d9d7310749` (the repo-root
  checkout HEAD at review cycle 2, after the cycle-1 evidence commit
  `09ea84976f`; `git rev-parse HEAD` in the repo root). No file under `src/`
  changed between cycle 1 and cycle 2 -- re-running the scan at this SHA
  reproduces `corpus-scan.json` byte-identically apart from this field
  (reviewer-renata independently confirmed the same for `09ea84976f`).
- **Head-source preflight** (all three checks passed before any measurement):
  1. `src/specify_cli/requirement_mapping/grammar.py` exists and exposes
     `classify` and `canonical`.
  2. `src/specify_cli/requirement_mapping/lint.py` exposes
     `lint_spec_requirement_ids`.
  3. Every lane tip recorded for WP01-WP07 (`lane-a` through `lane-g`) is an
     ancestor of the head SHA, confirmed with
     `git merge-base --is-ancestor <tip> <head>` for all seven branches.
- **Commands** (from the repo root; `<tmp>/rig-base` denotes the throwaway
  merge-base worktree, created once with `git worktree add --detach
  <tmp>/rig-base ddf114f06c54e5454bad5c3172e7049a95f7f862` before both
  scans and shared by every re-run in this cycle):
  ```bash
  .venv/bin/python kitty-specs/requirement-id-grammar-01M3NRCA/research/corpus_scan.py \
    --corpus-root "$(pwd)" \
    --base-src <tmp>/rig-base/src \
    --head-src "$(pwd)/src" \
    --out-dir <scratch>/research
  ```
  The driver process itself never imports `specify_cli` (only the worker
  subprocesses do, each with its own `PYTHONPATH`), so no `PYTHONPATH`
  prefix is needed on this command; an earlier revision of this report
  carried one out of habit, which was unnecessary and has been dropped.
  Run twice at the same SHAs; `diff` of the two `corpus-scan.json` outputs
  was empty (byte-identical) -- the determinism check.
- **File counts**: 3,542 files (520 `spec.md`, 3,022 `tasks/WP*.md`), hash
  `1ebfbd651a0f6712270d41699282c187c0c7bbbe34eb121866b6d053ff40b813`
  (`sha256` of the sorted, repo-relative POSIX path list). Both workers read
  file CONTENT from the head tree only; the file-list hash proves both sides
  received the identical list.
- **Python**: 3.11.15 (the repo `.venv`; each worker subprocess ran under
  the same interpreter with `PYTHONPATH` pointed at its own side's `src`).
- **Import isolation**: both workers asserted `specify_cli.__file__` (and
  `runtime`/`charter`/`kernel`, when importable) resolved under the
  expected side's `src`, and the driver additionally asserts `--base-src !=
  --head-src` (added in cycle 2) so isolation is checked, not merely
  assumed by construction. `corpus-scan.json`'s `isolation` block records
  the per-side resolution as a boolean (never the raw `/tmp` path, so the
  JSON output stays byte-identical across runs at the same SHAs) -- both
  sides: `ok: true`.
- **WP-token pairing** (cycle 2): `_wp_transition_entries` now asserts
  `base_token == head_token` at every paired index instead of silently
  discarding the head token -- reviewer-renata verified by hand that all
  10,854 pairs already agreed; the assertion makes that self-proving on
  every future run rather than trusted-by-inspection.
- **Worktree removal proof**: `git worktree remove --force <tmp>/rig-base`
  followed by `git worktree prune`; the subsequent `git worktree list`
  no longer lists it.

## (a) Bare prose / SC-005

| | base | head |
|---|---|---|
| flagged specs | 1 | 1 |

Both sides flag exactly `kitty-specs/egress-refusal-consolidation-3110-01KYW895/spec.md`
with ids `C-1`, `C-3`. **Verdict: PASS** (`head_count (1) <= base_count (1)`).

**SC-005 positive control**: the egress spec is still flagged at the head
with the same `C-1`/`C-3` ids -- it was **not** silently dropped. C-009
(unqualified, unsuffixed FR/NFR/C candidates only) keeps this spec's
citations of its own orchestrator-notes ids (`C-1`..`C-4`, distinct from
its own `C-001`..`C-011` constraints) as bare-prose candidates exactly as
before the mission.

## (b) Newly refused specs (planning hand-off lint, FR-013)

**Count: 4 specs, matching the expected 4.** Every refused token is a
kind-prefixed token in a declared position (table row, heading, bullet, or
bold lead) that the grammar cannot parse -- **all four are classified
INTENDED FIX**, none are false refusals of a legitimate id, an HTML-comment
token, a non-first table cell, or a prose compound outside a declared
position:

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

No count deviation to explain -- the live result matches the fixture's
expected 4 specs exactly (84 refused tokens total: 4 + 71 + 1 + 8).

## (c) Declared-set growth

**419 of 520 specs grew; 0 specs shrank.**

All 2,637 added ids across those 419 specs match `(FR|NFR|C|SC)-\d+[a-z]?`
-- i.e. every addition is either a bare `SC-###` id (2,603 of 2,637) or a
lowercase-letter-suffixed `FR-###a`/`NFR-###a`/`C-###a` id (28 of 2,637),
plus 6 letter-suffixed `SC-###a` ids. **All 2,637 are classified INTENDED**
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
This printed `{'matched': 2637, 'other': 0}` against the committed
`corpus-scan.json` (2,603 bare `SC-###`, 6 letter-suffixed `SC-###a`, 28
letter-suffixed `FR`/`NFR`/`C`). Full per-spec list: `corpus-scan.json`
`declared_growth.growth`.

**Shrink**: 0 specs. The one expected shrink class -- an id declared only
inside an HTML comment, now correctly blanked by `blank_html_comments`
before scanning (WP01) -- did not fire against the live corpus: no spec in
today's `kitty-specs/` happens to declare an id exclusively inside an HTML
comment. This is a clean, unsurprising negative result, not evidence of a
detector gap (the mechanism is exercised directly by WP01's own unit
tests); noted here because the spec's Test Strategy calls out this shrink
class specifically.

## (d) WP ref transitions

**10,854 raw WP-frontmatter tokens compared** (positionally paired per WP,
same tokenisation on both sides). Matrix (excluding the unchanged
`kept/known -> accepted` baseline, 10,808 tokens where a ref valid under the
old known-ref gate is still valid, just relabelled under the new
`accepted` vocabulary):

| Transition | Count | Classification |
|---|---|---|
| `dropped -> accepted` | 12 | **Intended** (#2991: the ref is now kept and counted) |
| `dropped -> rejected:malformed` | 5 | **Intended**, but **fail -> fail** for 3 of 5 (see below) |
| `kept/unknown -> rejected:unknown_spec_id` | 29 | **Intended**, and **fail -> fail for all 29** (see below) |
| `kept/known -> rejected:*` | 0 | (none found -- this would be a probable regression) |

**`dropped -> accepted` (12, all intended)** -- letter-suffixed and SC refs
the old regex never recognised at all, now correctly kept and mapped:
`065-wp-metadata-state-type-hardening` WP05 (`FR-012a`..`FR-012d`),
`cascade-asset-silent-drop-01M0RME0` WP03 (`FR-005a`),
`charter-epic-golden-path-nfr-budget-01M35H35` WP02/WP03/WP06/WP08
(`SC-001`..`SC-005`), `common-docs-consolidation-01KW3Q6M` WP04 (`SC-006`).

**Correction (review cycle 1): the base `finalize-tasks` gate already
blocked on both failure shapes below.** `_validate_requirement_mapping`
(`mission_finalize.py@ddf114f06c:1257-1295`) calls `raise typer.Exit(1)`
whenever `unknown_requirement_refs` is non-empty (built by
`_classify_wp_requirement_refs`, `:1161-1182`, which buckets a WP with NO
refs after normalization into `missing_requirement_refs_wps` -- also
gate-failing), and `_read_spec_requirement_ids` (`:863-885`) calls
`raise typer.Exit(1)` when `spec.md` does not exist. Both are gate-wide,
mission-level failures at base -- not merely recorded-but-non-blocking.
The corrected classification below replaces an earlier draft that
mis-stated this as "recorded as unknown but never blocked on it."

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
  **WP10 is the one genuinely new failure in this entire scan.**

The new grammar correctly and loudly rejects `ADR`/`2026-03-27-1` as
malformed where the old regex silently dropped them; that tightening is
intended (FR-019), and it is also a real, newly-introduced failure for
WP10 specifically -- both things are true at once.

**`kept/unknown -> rejected:unknown_spec_id` (29, all intended, all
fail -> fail)** -- 27 of the 29 are in mission
`charter-doctrine-mission-type-configuration-01KSWJVX` (WP01-WP15,
`FR-001`..`FR-019`); this mission's own `spec.md` does not exist on disk
(confirmed: `kitty-specs/charter-doctrine-mission-type-configuration-
01KSWJVX/` has a `tasks/` directory but no `spec.md`), so `_read_spec_
requirement_ids` already raises `typer.Exit(1)` at base -- the whole
mission was **already failing before any of these 27 refs were even
classified**. The remaining 2 are
`excise-doctrine-curation-and-inline-references-01KP54J6` WP03 (`NFR-002`)
and `spdd-reasons-activation-split-brain-01M1K6VN` WP01 (`C-004`) --
genuinely undeclared refs in specs that DO exist; at base these land in
`unknown_requirement_refs`, which already fails `_validate_requirement_
mapping` for that mission too. **All 29 are fail -> fail: the base gate was
already red for every one of these missions; the head gate is also red,
for the same (and now more precisely diagnosed) reason.** The
"not a regression" conclusion is unchanged -- only the reasoning was wrong.
Full item list: `corpus-scan.json` `wp_ref_transitions.changed`.

**Missions whose NEXT re-finalize newly fails (corrected list): only
`058-mission-template-repository-refactor`, via WP10.** The other three
missions named in this section
(`charter-doctrine-mission-type-configuration-01KSWJVX`,
`excise-doctrine-curation-and-inline-references-01KP54J6`,
`spdd-reasons-activation-split-brain-01M1K6VN`) were already failing
`finalize-tasks` at the merge-base and remain failing at head -- not new
failures, and `058`'s own WP08 was likewise already failing at base
(only its WP10 is new).

No `kept/known -> rejected:*` transitions occurred anywhere in the corpus --
the class the review guidance calls a probable regression is empty.

## Interpretation and escalations

Every measured difference between the merge-base and the head is an
**intended fix**. (b) newly refuses 4 pre-existing malformed-shape specs at
the planning hand-off (a new, non-finalize-gated lint -- these are not
finalize failures). (d) touches four already-existing missions whose
`requirement_refs` frontmatter or spec.md state was already imperfect
(missing spec.md, non-ID garbage tokens, or genuinely undeclared refs);
three of those four (`charter-doctrine-mission-type-configuration-01KSWJVX`,
`excise-doctrine-curation-and-inline-references-01KP54J6`,
`spdd-reasons-activation-split-brain-01M1K6VN`) were **already failing**
`finalize-tasks` at the merge-base and remain failing at head -- not new
failures. Only **one** mission, `058-mission-template-repository-refactor`,
newly fails at head, and only via its WP10 (WP08 was already failing at
base). The bare-prose detector's floor and SC-005 positive control both
hold. The declared-ID growth is 100% attributable to newly-recognised
declared shapes (SC kind, lowercase suffix), with zero suspect additions
(verified by the post-hoc check in the (c) section above, not by a script
assertion). No `kept/known -> rejected:*` transitions -- the
probable-regression bucket -- occurred.

**No regressions found. Nothing to escalate.**
