---
title: Read-side placement-seam classification ledger
description: "Per-site verdicts (migrate-fail-loud / stay-lenient / sanction-infra) for every production call site that bypasses PlacementSeam.read_dir(kind)."
doc_status: active
updated: '2026-10-04'
audience: docs/context/audience/internal/system-architect.md
type: reference
related:
- docs/architecture/execution-lanes.md
---

# Read-side placement-seam classification ledger

> **When you need this page.** If your change reads a mission directory
> through one of the older kind-blind path helpers instead of
> `PlacementSeam.read_dir(kind)`, `tests/architectural/test_no_read_side_bypass.py`
> checks the call site against this ledger. Find (or add) the row for your
> site and follow its verdict. The rest of the page is the per-site record.

`PlacementSeam.read_dir(kind)` (`src/mission_runtime/resolution.py:1404`, which
delegates to `resolve_artifact_surface` at `:1705`) is the one kind-aware,
fail-loud read authority: it raises `CoordinationBranchDeleted` when a
COORD-partition kind is required but the mission's declared coordination
branch has been deleted from git, and it resolves identically to the
historical primitives for every other cell. PR #2920 hardened that seam but
did not migrate its pre-existing bypassers.

This ledger is the classification spine for the read-side placement-seam
migration programme. It was authored by the **read-side-placement-seam-migration-01KYHP67**
mission (WP02 there) for the original two bypass primitives, and that
migration has since **completed** — nearly all of its `migrate-fail-loud`
sites are now routed through the seam; only sanctioned-infra and
deliberately-`stay-lenient` residuals still call the two primitives directly.

**read-side-seam-primary-primitive-closure-01KYKMMT (WP02, this revision,
FR-008/FR-009/FR-010/FR-012/FR-016/FR-017)** extends this SAME ledger — never
a second authority (C-002) — to police the two primitives no prior gate
covered:

- `resolve_feature_dir_for_mission(repo_root, mission_slug, *, cwd=None, env=None)`
  — kind-blind, routes through `mission_runtime.resolve_action_context` (a
  richer, structured-error-raising resolver than the other three primitives).
- `primary_feature_dir_for_mission(repo_root, mission_slug)` — kind-blind
  **and** deliberately topology-blind (never routes to a coordination
  worktree); it inherits the guarantee transferred from WP01's retired
  use-count floors (in `test_resolution_authority_gates.py`, deleted in #3285;
  the guarantee is now enforced by `tests/architectural/test_no_read_side_bypass.py`).

The censused-callee set is now **five** primitives. The first four are
defined in `src/specify_cli/missions/_read_path_resolver.py`; the fifth is the
module-private leaf WP03/WP08 extracted from (and WP08 re-pointed the deleted
public wrapper's foundation callers onto):

| Primitive | Kind-aware? | Topology-aware? | Status this revision |
|---|---|---|---|
| `candidate_feature_dir_for_mission` | no | yes | migrated (historical record below) |
| `resolve_planning_read_dir` | yes | yes (per-kind) | migrated (historical record below) |
| `resolve_feature_dir_for_mission` | no | yes (via `resolve_action_context`) | **censused + classified this revision** |
| `primary_feature_dir_for_mission` | no | no (deliberately blind) | **censused this revision; classification is a later WP's job** |
| `_compose_primary_feature_dir` | no | no (pure `KITTY_SPECS_DIR` join) | **post-merge closeout: promoted from alias-only bookkeeping to a first-class censused callee (see § "Post-merge closeout" below)** |

**Post-merge closeout (fix/read-side-seam-primary-primitive-closure follow-up,
aggregate-squad cross-lane-integration finding).** WP08 deleted the public
wrapper `primary_feature_dir_for_mission` and re-pointed its five named
FR-005/NFR-009 foundation callers at the module-private leaf
`_compose_primary_feature_dir` directly (`core/paths.py` ×2, `core/git_ops.py`,
`coordination/surface_resolver.py`, `retrospective/writer.py`) — but left the
leaf itself OUT of `_TARGET_CALLEE_NAMES`, relying solely on
`_LEAF_PRIMITIVE_ALIASES` to fold its bookkeeping back onto the old primitive
name for the ledger's own reconciliation. That left the gate enforcing a
**dead name with zero live call sites** while the **live leaf itself** —
importable and callable from any module — carried no census entry at all: a
future module outside the five named foundation sites could import
`_compose_primary_feature_dir` and call it with a canonical handle, reopening
the exact canonical-handle + caller-chosen-partition bypass shape this mission
exists to end, invisibly to every one of the four gates. This closeout adds
the leaf to `_TARGET_CALLEE_NAMES` as its own censused primitive (proven by
`test_ratchet_bites_on_a_planted_leaf_primitive_call_outside_sanctioned_modules`
in the gate) and sanctions its two previously-unclaimed real call sites
(`retrospective/writer.py::resolve_retrospective_home`,
`status/aggregate.py::MissionStatus._find_meta_path` — both deferred by WP06/
WP08, see the "WP06 correction" note below) via two new
`_FOUNDATION_SANCTION_SEED` entries, bringing the FR-005/NFR-009 foundation
population to its full **five** sites / **four** files. `_LEAF_PRIMITIVE_ALIASES`
keeps mapping the leaf's literal name back onto the `primary_feature_dir_for_mission`
bucket for `_entry_primitive`'s bookkeeping/reconciliation purposes (so the §
"Live census summary" and § "Foundation-site sanctions" rows below keep
counting these five sites under the OLD primitive name, preserving the
historical continuity WP08 established) — the alias mechanism is consulted
FIRST, before the literal-name match, so adding the leaf to
`_TARGET_CALLEE_NAMES` does not silently reclassify these five bookkept
entries. The leaf's OWN § "Live census summary" row is therefore a deliberate,
permanent `0 declared / 5 live` mismatch — the exact mirror image of
`primary_feature_dir_for_mission`'s existing permanent `3→5 declared / 0 live`
mismatch below — recorded as a second entry in
`test_ledger_summary_counts_reconcile_with_the_allow_list_and_themselves`'s
`expected_end_state_reds`. Both mismatches describe the SAME underlying
foundation-sanctioned population, counted once, under the old name, for
continuity; nothing here reopens the gap the closeout exists to close (the
main ratchet's offender check keys on `(rel_path, qualname, token_line)`, never
on the primitive-bucket label, so this bookkeeping choice has zero effect on
what the gate actually flags).

`tests/architectural/test_no_read_side_bypass.py` (WP02, this revision) parses
this ledger as the authority for the machine-checked stay-lenient index and
foundation-sanction index, and for the live-census Summary counts it
reconciles against. Every count below is re-derived fresh against the tree at
authoring time (T014 / SC-008) — none is copied from a prior mission's figure
or from issue #3014 (whose own count is stale, see the corrected Known-gap
section below).

## ⚠ This revision deliberately leaves part of the census red

Growing the censused callees to their terminal set of four means the gate
begins flagging every real `primary_feature_dir_for_mission` call site that is
neither sanctioned nor allow-listed — **31 sites across 17 files** — plus the
one `resolve_feature_dir_for_mission` site classified `migrate-fail-loud`
(`decisions/emit.py:71`, not yet routed). That is **32 expected-red findings**,
recorded in
`kitty-specs/read-side-seam-primary-primitive-closure-01KYKMMT/research/expected-reds.md`
§ WP02. **This is the acceptance signal (US8 / FR-023), not a defect** — later
WPs (WP04–WP08) turn these green by routing each site per its eventual
classification. Do not allow-list them preemptively (the allow-list is
shrink-only; pre-populating 31 entries you intend to delete would invert the
ratchet), and do not soften the gate to avoid the red.

**A second, related expected red (T010.3, NFR-008)**: because the
§ "Live census summary" table below declares the **post-migration end
state** rather than today's in-flight tree, its `Total real call sites` rows
for `resolve_feature_dir_for_mission` and `primary_feature_dir_for_mission`
mismatch the live census
(`test_ledger_summary_counts_reconcile_with_the_allow_list_and_themselves`)
from this commit onward — also recorded in `research/expected-reds.md`
§ WP02, with **WP08** named as its greening owner. See § "Live census
summary" below for the full reasoning.

## Method (how the original 2-primitive census was built — historical)

1. `grep -rl -E "candidate_feature_dir_for_mission|resolve_planning_read_dir" src --include="*.py"`
   found **62 files**. Removing the two DEFINITION modules
   (`src/specify_cli/missions/_read_path_resolver.py`, which defines both
   primitives, and `src/mission_runtime/resolution.py`, which is the seam
   itself and calls `resolve_planning_read_dir` once internally to
   canonicalize a handle) leaves **60 consumer files** — this is the
   file-level census the historical ledger below reconciled against.
2. A textual line grep (`symbol\(`) over those 60 files found 93 apparent call
   sites. **3 were false positives** — prose/docstring mentions that happen to
   contain a literal `symbol(...)` substring (one plain `#` comment, two inside
   triple-quoted docstrings) — caught by cross-checking against an `ast.walk`
   census (below), not by the textual grep alone.
3. An AST-based census (`ast.parse` + `ast.walk` over every `ast.Call` node,
   matching `Name.id` or `Attribute.attr` against the two symbol names) gives
   the authoritative, zero-false-positive site list: **90 real call sites**
   across **54 files** (the other 6 of the 60 have a grep hit but zero real
   `ast.Call` sites — a comment or docstring mention only). This is exactly
   the discrimination the structural gate (`test_no_read_side_bypass.py`)
   must make via its own AST walk — the bite test ("a prose/docstring
   mention stays green") this ledger's method already had to get right.
4. Of the 90 real sites: **31 kind-blind** (`candidate_feature_dir_for_mission`)
   and **59 kind-aware** (`resolve_planning_read_dir`).

**This entire section describes the pre-migration state.** Since then, every
`migrate-fail-loud` site from that census has been routed through the seam;
the only real call sites remaining today are the sanctioned-infra and
stay-lenient residuals reconciled in the live-census Summary below.

## Method (WP02 this revision — the live 4-primitive re-derivation)

Re-derive, never trust a written count (quickstart.md § 1's alias-resolving
recipe, extended to all four primitives and scoped to the read gate's actual
`_read_side_scan_scope()` — the shared whole-tree `scan_scope()` minus the
four sanctioned-infra modules, never a second scanner, NFR-006):

```
candidate_feature_dir_for_mission : 12 sites / 9 files   (unchanged; historical migration complete)
resolve_planning_read_dir         :  4 sites / 2 files   (unchanged; historical migration complete)
resolve_feature_dir_for_mission   :  8 sites / 7 files   (NEW this revision — fully classified below)
primary_feature_dir_for_mission   : 34 sites / 19 files  (NEW this revision — 3 sanctioned + 31 expected-red)
```

The four sanctioned-infra modules excluded from this scan (`_READ_SANCTIONED_MODULES`
in the gate): `missions/_read_path_resolver.py` (the primitive authority
itself), `mission_runtime/resolution.py` (the seam itself — self-reference),
`mission_runtime/write_target_degrade.py` (bootstrap-window degrade helper),
and `coordination/surface_resolver.py` (the canonical surface resolver both
`candidate_feature_dir_for_mission` and, now, `primary_feature_dir_for_mission`
are partly built to serve).

## Coverage reconciliation (historical 2-primitive record)

```
grep -rl -E "candidate_feature_dir_for_mission|resolve_planning_read_dir" src --include="*.py" | wc -l
  → 62
minus the 2 definition modules (_read_path_resolver.py, mission_runtime/resolution.py)
  → 60  == this ledger's file-row count (§ Full ledger, every one of the 60 files
          appears exactly once, either in a verdict table or the "no real call
          site" table)
AST-verified real call sites across those 60 files: 90  == the sum of every
  per-file "sites" column in the historical § Full ledger below (72 migrate + 16 stay-lenient + 2 sanction-infra)
```

100% of the 60 consumer files and 100% of the 90 real call sites from the
original census were classified. No row carried an `unknown` verdict. **This
record is historical (NFR-008): it is preserved as an audit trail of the
pre-migration state and is not reconciled against by any gate.** The gate's
live reconciliation runs against the § "Live census summary" table below.

File counts in the historical ledger are **site-containing** (a mixed file
such as `tasks_status_cmd.py` appears in both migrate and stay-lenient).
`54 = 42 migrate-containing + 11 stay-containing − 1 mixed + 2 sanction`.

- **Ambiguous — reviewer confirm** (defaulted to the safer disposition, per
  mission instructions): 9 stay-lenient sites — `tasks_move_task.py:2368`,
  `tasks_status_cmd.py:160`, `archive.py:65`, `reconcile.py:126`,
  `retrospect.py:110`, `dossier/api.py:227,397,435`, `manifest.py:272` —
  plus `next_cmd.py:377` (defaulted **migrate-fail-loud**, flagged for a
  dead-except-clause check). See the per-row rationale for each.
- **Multi-kind readers flagged for split**: `archive.py:65` and
  `reconcile.py:126` — one resolved dir feeds more than one downstream
  artifact kind read (see rows). Both stay lenient until the owning
  migration WP can split them by kind (blind single-kind swap would be a
  false precision).
- **Research hard-case note**: `_cutover_doctor.py` is named in research.md
  as a diagnostic/audit reader, but it has **zero** calls to either bypass
  primitive (it delegates to `migration.runtime_state_cutover.cutover_repo`);
  correctly absent from this census.
- **Sanctioned set** (mirrors `resolution.py`'s own self-exclusion style, and
  the write-gate's `BOUNDARY_SANCTIONED_MODULES` per-file rationale
  convention in `tests/architectural/_placement_whole_tree_scan.py`):
  - `src/specify_cli/missions/_read_path_resolver.py` — the primitive
    authority itself (excluded from the consumer census entirely, per FR-003 —
    it does not call itself).
  - `src/specify_cli/coordination/surface_resolver.py` — canonical surface
    resolver infra (FR-003 explicit). WP02 this revision: also calls
    `primary_feature_dir_for_mission` (:739) as one of the four named FR-005
    foundation sites — the same sanction covers both primitives.
  - `src/mission_runtime/write_target_degrade.py` — already covered by the
    `src/mission_runtime/` `BOUNDARY_SANCTIONED_PREFIXES` blanket on the
    write-side gate; carries its own per-file rationale here too so the
    read-side gate's sanctioned-module test can assert it directly, matching
    the "carries a rationale" discipline `test_sanctioned_modules_carry_a_rationale`
    already enforces on the write side.
  - `src/mission_runtime/resolution.py` — the seam itself. WP02 this revision
    adds this as an explicit per-file entry (previously covered only via the
    prefix blanket): it calls `primary_feature_dir_for_mission` internally
    (four sites: the mid8/coordination-branch/topology/mission-id resolution
    helpers) to compose its own PRIMARY-partition leg — self-reference, not a
    bypass.
- **Doctrine-named stay-lenient modules** (research.md hard cases, honoured
  verbatim): `_coordination_doctor.py`, `dashboard/scanner.py`,
  `status/aggregate.py`, `retrospective/summary.py`, and the `retrospect.py`
  corpus-walk classifier — every real call site in these modules stays
  lenient regardless of whether the specific declared kind is PRIMARY-partition
  (behaviorally risk-free) or COORD-partition (real fail-loud risk), because
  the module's *purpose* — never crash a corpus scan or audit report — is the
  invariant, not the incidental safety of today's kind assignment.
- **`workflow.py` correction**: research.md's pre-planning grounding squad
  counted **17** raw grep hits for `cli/commands/agent/workflow.py`. The
  AST-verified count is **7 real call sites** (2 of the original textual hits,
  at lines 843 and 1447, are docstring prose describing the very migration
  this ledger performs, not real calls). Recorded here so WP03 does not
  over-scope its `workflow.py` slice against the inflated textual figure.

## Live census summary (machine-checked, end-state)

**This is the table the gate parses (`_ledger_summary_counts`).** T010.3
resolves the "live" ambiguity explicitly: these counts are the
**POST-MIGRATION END STATE** — what the census will read once every
`migrate-fail-loud`/expected-red site above has been routed through the seam
— never the as-of-today in-flight tree, and never the historical
pre-migration totals in § below (NFR-008 covers both directions: neither a
historical nor an in-flight figure may be rewritten to make a check pass).
Editing any row here, or the § "Stay-lenient allow-list index" /
§ "Foundation-site sanctions" tables below, REDS the gate.

| Verdict | Sites | Files | Primitive |
|---|---|---|---|
| migrate-fail-loud | 0 | 0 | `candidate_feature_dir_for_mission` |
| stay-lenient | 13 | 10 | `candidate_feature_dir_for_mission` |
| sanction-infra | 0 | 0 | `candidate_feature_dir_for_mission` |
| expected-red (unrouted) | 0 | 0 | `candidate_feature_dir_for_mission` |
| Total real call sites | 13 | 10 | `candidate_feature_dir_for_mission` |
| migrate-fail-loud | 0 | 0 | `resolve_planning_read_dir` |
| stay-lenient | 4 | 2 | `resolve_planning_read_dir` |
| sanction-infra | 0 | 0 | `resolve_planning_read_dir` |
| expected-red (unrouted) | 0 | 0 | `resolve_planning_read_dir` |
| Total real call sites | 4 | 2 | `resolve_planning_read_dir` |
| migrate-fail-loud | 0 | 0 | `resolve_feature_dir_for_mission` |
| stay-lenient | 7 | 6 | `resolve_feature_dir_for_mission` |
| sanction-infra | 0 | 0 | `resolve_feature_dir_for_mission` |
| expected-red (unrouted) | 0 | 0 | `resolve_feature_dir_for_mission` |
| Total real call sites | 7 | 6 | `resolve_feature_dir_for_mission` |
| migrate-fail-loud | 0 | 0 | `primary_feature_dir_for_mission` |
| stay-lenient | 0 | 0 | `primary_feature_dir_for_mission` |
| sanction-infra | 5 | 4 | `primary_feature_dir_for_mission` |
| expected-red (unrouted) | 0 | 0 | `primary_feature_dir_for_mission` |
| Total real call sites | 5 | 4 | `primary_feature_dir_for_mission` |
| migrate-fail-loud | 0 | 0 | `_compose_primary_feature_dir` |
| stay-lenient | 0 | 0 | `_compose_primary_feature_dir` |
| sanction-infra | 0 | 0 | `_compose_primary_feature_dir` |
| expected-red (unrouted) | 0 | 0 | `_compose_primary_feature_dir` |
| Total real call sites | 0 | 0 | `_compose_primary_feature_dir` |

**WP08 (T039) closeout.** `resolve_feature_dir_for_mission` is now FULLY
reconciled: its one `migrate-fail-loud` site (`decisions/emit.py:71`) was
allow-listed rather than routed (reconciliation item #5 — see § below and
`research/expected-reds.md` § WP08), moving it `migrate-fail-loud 1 → 0` /
`stay-lenient 7 → 8`, so the declared row equalled a fresh live census
exactly (8 sites / 7 files) — no exemption remained for this primitive.

**write-side-seam-matrix-tracer (WP02, FR-010 "Move A") supersession.** The
allow-list above was transitional. WP02 of the write-side mission then ROUTED
`decisions/emit.py:71`: `_mission_dir` now resolves through
`placement_seam(...).read_dir(STATUS_STATE)` instead of the kind-blind
`resolve_feature_dir_for_mission ( repo_root , mission_slug )` call. That call
no longer exists in `emit.py`, so it is a **completed migration**, not an
allow-listed offender. A fresh live census now finds `stay-lenient 8 → 7`
(**7 sites / 6 files**) — the declared row above was updated to match, its
`_ALLOW_LIST_SEED` descriptor removed, and the stay-lenient index / per-site
rows below dropped the `emit.py` entry. #3055's gate-owner follow-up is
subsumed: the coord-authority gate keeps its own permanent `_mission_dir`
sanction (`test_resolution_authority_gates.py`, since deleted), which WP02 re-pinned 4 → 3.

`primary_feature_dir_for_mission` carries a **permanent**, not transitional,
reconciliation red. The public wrapper is DELETED (T035, SC-001): nothing in
`src/` can call it by that name any more, so a fresh live census now finds
**0** real call sites for it, not the 5 this row now declares (post-merge
closeout: was 3, see below). This is NOT "not yet converged" (T010.3's
original framing, written before the wrapper's deletion was designed as an
outright delete rather than a rename) — it is structurally *unconvergeable* by
construction: the row's `sanction-infra: 5 / 4` count is not a live-call tally
any more, it is a frozen historical pointer to the five FR-005/NFR-009
foundation sites (`core/paths.py` x2, `core/git_ops.py`,
`retrospective/writer.py`, `status/aggregate.py` — the latter two added by the
post-merge aggregate-squad closeout, see § "Post-merge closeout" above) that
were sanctioned for this primitive and are now permanently re-pointed at the
module-private `_compose_primary_feature_dir` leaf (`_FOUNDATION_SANCTION_SEED`'s
`_LEAF_PRIMITIVE_ALIASES` maps the leaf's literal name back onto this
primitive column purely for that bookkeeping continuity — see the §
"Foundation-site sanctions" table above). Retiring this row to `0` and
dropping `_FOUNDATION_SANCTION_SEED`'s five entries instead would sever that
historical trace for no live-behaviour gain, so this closeout keeps the row's
bookkeeping identity (only its count grows 3→5) and keeps the reconciliation
exemption (`test_ledger_summary_counts_reconcile_with_the_allow_list_and_themselves`'s
`expected_end_state_reds`) for this ONE primitive, permanently, with this
paragraph as the record of why.

**`_compose_primary_feature_dir` carries the mirror-image permanent
reconciliation red.** Its own § "Live census summary" row above declares `0`
in every bucket (nothing is bookkept under the leaf's own literal name — see
the preceding paragraph), yet a fresh live census finds **5** real call sites
for it (the same five foundation sites, counted once, under the OLD
primitive's name). This is the structural mirror of
`primary_feature_dir_for_mission`'s `5 declared / 0 live` red: here it is
`0 declared / 5 live`, permanently, for the identical bookkeeping-continuity
reason. Both mismatches are recorded together in
`expected_end_state_reds` (post-merge closeout, this commit).

**This is a deliberate, recorded reconciliation red, not an oversight.**
`test_ledger_summary_counts_reconcile_with_the_allow_list_and_themselves`
mismatches on `primary_feature_dir_for_mission`'s `Total real call sites` row
— "ledger declares 5 total real call sites but a fresh census finds 0" — and
symmetrically on `_compose_primary_feature_dir`'s — "ledger declares 0 total
real call sites but a fresh census finds 5" — both by permanent design (see
the preceding two paragraphs). `resolve_feature_dir_for_mission`'s sibling
mismatch, by contrast, was transitional and was CLOSED at WP08 — its declared
numbers were updated to match a fresh live census exactly, and it was removed
from `expected_end_state_reds` (only WP08 is permitted to edit either, per
`tasks.md` § 6; this post-merge closeout is the mission's own follow-up
remediation, not a new WP, and edits both per the aggregate-squad finding it
resolves).

The **`expected-red (unrouted)`** bucket's role changes with this framing: at
end state every primitive's row is `0 | 0` by definition (there is nothing
left unrouted once WP08 closes out), so this bucket no longer carries an
as-of-now residual count. Its job going forward is to stay the *visible zero*
the end-state declaration commits to — a nonzero value here after WP08 would
mean a brand-new, still-uncensused bypass appeared, which the main ratchet
(`test_no_read_side_bypass_outside_sanctioned_and_allow_listed`) would
already independently catch.

## Summary (historical — pre-migration 2-primitive audit record, NFR-008)

**Preserved verbatim as an audit trail; not reconciled by any gate.** This is
the census as it stood before the read-side-placement-seam-migration-01KYHP67
mission routed its `migrate-fail-loud` sites through the seam.

| Verdict | Sites | Files (site-containing) |
|---|---|---|
| migrate-fail-loud | 72 | 42 |
| stay-lenient | 16 | 11 |
| sanction-infra | 2 | 2 |
| **Total real call sites** | **90** | **54** |
| No real call site (docstring/comment mention only) | 0 | 6 |
| **Grand total (file-level census)** | | **60** |

## Stay-lenient allow-list index (machine-checked)

This table is the **authoritative membership list** for the read-side gate's
allow-list. `tests/architectural/test_no_read_side_bypass.py` parses it
(`_ledger_stay_lenient_index`) and asserts set equality against its
`_ALLOW_LIST_SEED`, and parses the § "Live census summary" table
(`_ledger_summary_counts`) for each primitive's stay-lenient site/file counts.
Editing a row here — or the `stay-lenient` numbers in § "Live census summary"
— REDS that gate. The gate's seed carries only the per-site content
descriptors (token substring + condensed rationale) that markdown cannot
express; it never declares its own membership or cardinality.

Rows are the AST-verified `(rel_path, enclosing qualname)` of each
stay-lenient site in § Full ledger (historical rows) or § below (this
revision's `resolve_feature_dir_for_mission` rows), one row per **site** (a
file with two lenient sites gets two rows), plus a trailing **`primitive`**
column (WP02 T009, G2) — **and now a second trailing `site token` column**
(cycle-1 review fix, G2/DIRECTIVE_041): `(rel_path, qualname, primitive)`
alone still cannot address more than ONE site when several censused sites of
the *same* primitive share one qualname, which is exactly the acceptance
fixture below. The `site token` column carries the site's own normalised
token line (the SAME `token_substring` the gate's `_ALLOW_LIST_SEED` /
`_FOUNDATION_SANCTION_SEED` descriptor already declares for that site — never
a hand-restated duplicate, and never a line number: DIRECTIVE_041 forbids
anchoring on `file.py:NNN`, which drifts on every unrelated edit above it).
With a genuine per-call assignment-target or argument shape, the token line
differs site-by-site even within one qualname.

The discriminator's acceptance fixture is
`status/aggregate.py::MissionStatus._find_meta_path`, which carries one
existing `candidate_feature_dir_for_mission` site (row below) plus three
newly-censused `primary_feature_dir_for_mission` sites (`:499`, `:522`,
`:543` — **not yet classified/allow-listed**; they are part of this
revision's 31 `primary_feature_dir_for_mission` expected-red sites, see
`research/expected-reds.md` § WP02; a later WP will decide their disposition
and, if `stay-lenient`, add their rows here — the four-column shape below
already lets those three land as three DISTINCT rows sharing one qualname).
Shrink-only: when a residual is finally routed through the seam, delete its
row here and its descriptor in the gate.

| rel_path | qualname | primitive | site token |
|---|---|---|---|
| `src/specify_cli/cli/commands/agent/tasks_move_task.py` | `_coord_status_events_path` | `candidate_feature_dir_for_mission` | `candidate_feature_dir_for_mission ( coord_root , mission_dir )` |
| `src/specify_cli/cli/commands/agent/tasks_status_cmd.py` | `_st_resolve_dirs` | `candidate_feature_dir_for_mission` | `candidate_feature_dir_for_mission ( status_read_root , st . mission_slug )` |
| `src/specify_cli/cli/commands/archive.py` | `create` | `candidate_feature_dir_for_mission` | `candidate_feature_dir_for_mission ( root , mission )` |
| `src/specify_cli/cli/commands/_coordination_doctor.py` | `_finding_for_reconcile_marker` | `resolve_planning_read_dir` | `feature_dir = resolve_planning_read_dir (` |
| `src/specify_cli/cli/commands/_coordination_doctor.py` | `_heal_one_strand` | `resolve_planning_read_dir` | `feature_dir = resolve_planning_read_dir (` |
| `src/specify_cli/cli/commands/reconcile.py` | `reconcile_mission_dossier` | `candidate_feature_dir_for_mission` | `candidate_feature_dir_for_mission ( root , mission_slug )` |
| `src/specify_cli/cli/commands/retrospect.py` | `_canonical_events_path` | `candidate_feature_dir_for_mission` | `candidate_feature_dir_for_mission ( repo_root , mission_slug )` |
| `src/specify_cli/cli/commands/retrospect.py` | `summary_cmd` | `candidate_feature_dir_for_mission` | `candidate_feature_dir_for_mission ( resolved_project , mission_slug )` |
| `src/specify_cli/retrospective/summary.py` | `_read_proposal_events` | `candidate_feature_dir_for_mission` | `candidate_feature_dir_for_mission ( project_path , mission_slug )` |
| `src/specify_cli/retrospective/tracer_writer.py` | `_local_staging_path` | `candidate_feature_dir_for_mission` | `candidate_feature_dir_for_mission ( repo_root , mission_slug )` |
| `src/specify_cli/status/aggregate.py` | `MissionStatus._find_meta_path` | `candidate_feature_dir_for_mission` | `candidate_feature_dir_for_mission ( repo_root , mission_slug )` |
| `src/specify_cli/manifest.py` | `WorktreeStatus.get_feature_status` | `candidate_feature_dir_for_mission` | `candidate_feature_dir_for_mission ( worktree_path , feature )` |
| `src/specify_cli/agent_tasks_ports.py` | `RealCoordCommitRouter.feature_write_dir` | `resolve_feature_dir_for_mission` | `resolve_feature_dir_for_mission (` |
| `src/specify_cli/cli/commands/decision.py` | `_resolve_repo_root_and_slug` | `resolve_feature_dir_for_mission` | `resolve_feature_dir_for_mission ( repo_root , mission_handle )` |
| `src/specify_cli/cli/commands/mission_type.py` | `current_cmd` | `resolve_feature_dir_for_mission` | `resolve_feature_dir_for_mission ( project_root , mission_slug )` |
| `src/specify_cli/cli/commands/mission_type.py` | `close_cmd` | `resolve_feature_dir_for_mission` | `resolve_feature_dir_for_mission ( repo_root , mission_slug )` |
| `src/specify_cli/context/resolver.py` | `resolve_context` | `resolve_feature_dir_for_mission` | `resolve_feature_dir_for_mission ( repo_root , mission_slug )` |
| `src/specify_cli/lanes/recovery.py` | `reconcile_status` | `resolve_feature_dir_for_mission` | `resolve_feature_dir_for_mission ( repo_root , mission_slug )` |
| `src/specify_cli/widen/state.py` | `WidenPendingStore.__init__` | `resolve_feature_dir_for_mission` | `resolve_feature_dir_for_mission ( repo_root , mission_slug )` |

read-side-seam-primary-primitive-closure-01KYKMMT WP08 (T039, reconciliation
item #5): `decisions/emit.py:71` was WP02's one `migrate-fail-loud` finding
for this primitive (STATUS_STATE), deliberately left unrouted pending
adjudication. WP04's reviewer confirmed routing is directory-identical to
`test_resolution_authority_gates.py`'s (since deleted) coord-authority gate's own PERMANENT
sanction of the same call (`_COORD_WRITE_BY_DESIGN`); full routing needs
gate-owner work (teach that gate the seam idiom, re-token its allow-list,
transfer `COORD_AUTHORITY_WRITE_FLOOR`) outside this WP's charter, so it is
allow-listed here instead of routed or left an unexplained offender — tracked
at <https://github.com/spec-kitty/spec-kitty/issues/3055>. This moves the
primitive's `migrate-fail-loud` count `1 → 0` and `stay-lenient` `7 → 8`
(files `6 → 7`), which is why § "Live census summary" below now declares
`Total = 8`, not the previously-declared `7`.

write-side-seam-matrix-tracer-01KYP3MH (commit `2d96492ca`, "route … tracer
staging through canonical mission-spec-path seams"): the new
`retrospective/tracer_writer.py::_local_staging_path` replaced a hand-built raw
`repo_root / KITTY_SPECS_DIR / mission_slug / …` join with
`candidate_feature_dir_for_mission(repo_root, mission_slug)`, adding one
`candidate_feature_dir_for_mission` site in a previously-uncensused file. It is
**stay-lenient**, mirroring the sibling `retrospective/summary.py::_read_proposal_events`
(`:220`) staging-path pattern: it computes where a LOCAL `traces/<category>.md`
staging file should LAND before the mission's `traces/` subdir exists (the
caller `mkdir`s + `write_text`s it), then commits it through the WP03
`write_seam.write_artifact`, whose FR-011 probe is the canonical routability
authority. A read-resolver route (`read_dir(kind)`) is wrong here — this
resolves a write-then-stage destination, not where to READ from — and the raw
join it replaced was the ghost sink previously carried by the surface-resolution
and untrusted-path audits (both rows deleted with this change). This moves the
primitive's `stay-lenient` count `12 → 13` (files `9 → 10`), which is why
§ "Live census summary" above now declares `Total = 13`, not `12`.

## Foundation-site sanctions (machine-checked)

WP02 (T011/E3, FR-005) — the fourth named foundation site,
`coordination/surface_resolver.py`, is already a whole-module sanctioned
entry above; the remaining named foundation sites are per-SITE sanctions
instead, because `core/paths.py`, `core/git_ops.py`, `retrospective/writer.py`,
and `status/aggregate.py` are general-purpose modules carrying substantial
unrelated logic — whole-module sanctioning any of them would be exactly the
path-scoped blanket C-003 forbids. Each calls the module-private leaf
`_compose_primary_feature_dir` from beneath the seam's own composition root
(or, for `retrospective/writer.py`, beneath `PlacementSeam.read_dir`'s
`RETROSPECTIVE` short-circuit); routing any risks a resolution cycle
(NFR-009). `tests/architectural/test_no_read_side_bypass.py` parses this
table (`_ledger_foundation_index`) and asserts set equality against its
`_FOUNDATION_SANCTION_SEED`, and reconciles the `sanction-infra` row of §
"Live census summary" against it. These sites are **recorded by name and
remain unrouted** — never migrated, never absorbed into the stay-lenient index
(a separate table, so foundation-infra counts never blend into the
stay-lenient business-logic counts). Same trailing **`site token`** column
(cycle-1 review fix, G2) as the stay-lenient index above — `core/paths.py`
carries two of these five sites, so the site token disambiguates the two rows
sharing that one file (their qualnames already differ, so no collision exists
here today, but the shape must match the stay-lenient index's, per G1's "one
grammar" discipline).

read-side-seam-primary-primitive-closure-01KYKMMT WP08 (T035): the `site
token` column was re-pointed from `primary_feature_dir_for_mission (` to
`_compose_primary_feature_dir (` in the same commit as the public wrapper's
deletion — WP08 re-pointed the three `core/*.py` call sites at the leaf (the
M1 build-break fix WP07 deferred), and `_entry_primitive`'s
`_LEAF_PRIMITIVE_ALIASES` maps the leaf name back onto the
`primary_feature_dir_for_mission` primitive column so these rows keep
counting toward that primitive's `sanction-infra` bucket, not a new one.

**Post-merge closeout (aggregate-squad finding, this commit)** adds the
remaining two named FR-005/NFR-009 foundation sites that WP06/WP08 explicitly
deferred (see the "WP06 correction" note further below):
`retrospective/writer.py::resolve_retrospective_home` and
`status/aggregate.py::MissionStatus._find_meta_path`. Both already called the
leaf directly (WP03/WP08 re-pointed them in prior commits); their
machine-checked sanction is the `ContentDescriptor` entries in
`tests/architectural/test_no_read_side_bypass.py`'s `_FOUNDATION_SANCTION_SEED`
descriptor table, which this closeout added. This closeout also adds
`_compose_primary_feature_dir` itself to `_TARGET_CALLEE_NAMES` (§
"Post-merge closeout" above) so the gate's main ratchet can flag a *new*,
un-sanctioned call to the leaf — these five rows are precisely the sites the
ratchet would otherwise flag once the leaf became censused, sanctioned here
exactly as `core/paths.py`/`core/git_ops.py` already were.

| rel_path | qualname | primitive | site token |
|---|---|---|---|
| `src/specify_cli/core/paths.py` | `get_feature_target_branch` | `primary_feature_dir_for_mission` | `_compose_primary_feature_dir (` |
| `src/specify_cli/core/paths.py` | `resolve_merge_target_branch` | `primary_feature_dir_for_mission` | `_compose_primary_feature_dir (` |
| `src/specify_cli/core/git_ops.py` | `resolve_target_branch` | `primary_feature_dir_for_mission` | `_compose_primary_feature_dir (` |
| `src/specify_cli/retrospective/writer.py` | `resolve_retrospective_home` | `primary_feature_dir_for_mission` | `_compose_primary_feature_dir (` |
| `src/specify_cli/status/aggregate.py` | `MissionStatus._find_meta_path` | `primary_feature_dir_for_mission` | `_compose_primary_feature_dir (` |

## `resolve_feature_dir_for_mission` — classification (WP02, FR-010/FR-012)

The 8 real call sites (7 files; `mission_type.py` carries two) below were the
read-side mission's end state — re-derived, not trusted from the WP prompt or
#3014 (both stale). The live census above now declares **7 sites (6 files)**:
the write-side-seam-matrix-tracer mission routed `decisions/emit.py:71` to
`read_dir(STATUS_STATE)` (see the supersession note above), so its row below is
retained for the historical record but marked ROUTED. Each site is classified
on **both** axes (disposition,
and raise-vs-degrade), with its anchoring root and rationale of record. Per
T012's vacuity guard: the census does **not** yield zero `migrate-fail-loud`
sites (there is exactly one), so the SC-005 zero-case discharge does not
apply here.

Per-disposition counts: **migrate-fail-loud = 1**, **stay-lenient = 7**,
**sanction-infra = 0**.

| rel_path | qualname | disposition | raise/degrade | anchoring root | target kind | rationale |
|---|---|---|---|---|---|---|
| `agent_tasks_ports.py:323` | `RealCoordCommitRouter.feature_write_dir` | stay-lenient | raise (propagates `ActionContextError`) | `mission.repo_root` (`MissionHandle`, same anchoring as the adjacent `RealFsReader.primary_anchor_dir`) | n/a | `tasks_move_task.py:348-353`'s production comment is the rationale of record: "resolves the FR-010 coord husk — NEVER a primary kind... It is NEVER repointed to a primary kind — that would move the event-log read off the coord husk and reintroduce the split-brain FR-010 closes." Ambiguous whether a COORD-kind `read_dir()` swap would preserve `resolve_action_context`'s richer resolution; defaulted lenient. |
| `cli/commands/decision.py:130` | `_resolve_repo_root_and_slug` | stay-lenient | raise (propagates `ActionContextError`) | `repo_root = locate_project_root() or Path.cwd()` (main-repo-anchored, CWD fallback) | n/a | Own production comment: "deliberately EXCLUDED from the `read_dir(kind)` migration" — relies on `resolve_action_context`'s structured error (e.g. `COORDINATION_BRANCH_DELETED`) for the #8 live-symptom fix pinned by `test_decision_single_authority.py`. |
| `cli/commands/mission_type.py:238` | `current_cmd` | stay-lenient | raise (propagates `ActionContextError`) | `project_root` (`get_project_root_or_exit()`) | n/a | Own comment: mirrors `close_cmd`/`decision.py`; shares the identical existence-probe shape needing the structured-error contract. |
| `cli/commands/mission_type.py:582` | `close_cmd` | stay-lenient | raise (propagates `ActionContextError`) | `repo_root = _resolve_primary_repo_root(project_root)` | n/a | Own comment: pinned tests require an unresolvable/ambiguous handle to raise the structured error, never a silent "not found" or wrong pick; both `read_dir(kind)` legs are lenient by design and would swallow it. |
| `context/resolver.py:191` | `resolve_context` | stay-lenient | degrade (catches `ActionContextError`, translates to `FeatureNotFoundError`) | `repo_root` (caller-supplied, main-repo-anchored) | n/a | Own comment: exists to canonicalize the caller's HANDLE to a directory NAME, not to read a PRIMARY-partition artifact off the returned dir; re-routing would over-claim a single funnel over the `*_feature_dir_for_mission` primitives beyond what the gate enforces. |
| `decisions/emit.py:71` | `_mission_dir` | ~~stay-lenient (WP08 allow-list)~~ **ROUTED** (write-side WP02 → `read_dir(STATUS_STATE)`; no longer a live `resolve_feature_dir_for_mission` site — see supersession note above) | raise (`STATUS_STATE` is fail-loud-appropriate) | `repo_root` (param, passed through) | `STATUS_STATE` | Feeds `_events_path` → the shared `status.events.jsonl` coord-authoritative surface (the same file decision-point events append into). Originally classified `migrate-fail-loud`; WP08 (T039, reconciliation item #5) found `test_resolution_authority_gates.py`'s (since deleted) coord-authority gate PERMANENTLY sanctions this exact call as a legitimate coord-owned write (`_COORD_WRITE_BY_DESIGN`) — routing is directory-identical (WP04 reviewer-verified) but needs gate-owner work (teach that gate the seam idiom, re-token its allow-list, transfer `COORD_AUTHORITY_WRITE_FLOOR`) outside this WP's charter. Allow-listed per the WP08 prompt's escape hatch rather than routed unilaterally or left an unexplained offender; tracked at <https://github.com/spec-kitty/spec-kitty/issues/3055>. |
| `lanes/recovery.py:781` | `reconcile_status` | stay-lenient | raise | `repo_root` (param) | n/a | Own comment: "KEEP coord-aware (C-001 / #2155 analog): this `feature_dir` feeds `emit_status_transition_transactional` below — a STATUS-WRITE leg. The status event log lives on the coordination worktree for coord-topology missions, so this MUST stay on the coord-aware resolver — never route it." |
| `widen/state.py:63` | `WidenPendingStore.__init__` | stay-lenient (ambiguous — reviewer confirm) | raise | `repo_root` (constructor param) | n/a | No protective comment; `widen-pending.jsonl`'s partition (PRIMARY vs COORD) is not established anywhere else in the module, and the store's own "a missing file is equivalent to an empty store — never raises" invariant would be broken by a `read_dir(kind)` swap that CAN raise on a deleted coord branch for a COORD-partition kind. Defaulted lenient pending a bespoke kind decision (not a reason to skip classifying, per T012's vacuity guard). |

## `primary_feature_dir_for_mission` — live census (WP02, FR-012)

34 real call sites across 19 files (live census above). **3** are the FR-005
foundation sites (§ above, sanctioned, unrouted by design). The remaining
**31** (17 files) are this revision's expected-red set — **not classified by
this WP** (T012's classification scope is `resolve_feature_dir_for_mission`
only; scope statement repeated in the WP body). They are recorded here as
`(rel_path, qualname)` composite keys and duplicated into
`research/expected-reds.md` § WP02 so later WPs can prove *zero additions*
against a concrete list rather than staring at an undifferentiated red:

```text
runtime/next/runtime_bridge.py :: _mission_routes_through_coordination
runtime/next/runtime_bridge.py :: _dn_bootstrap
runtime/next/runtime_bridge_identity.py :: _primary_runtime_feature_dir
specify_cli/acceptance/__init__.py :: _primary_anchor_feature_dir
specify_cli/agent_tasks_ports.py :: RealFsReader.primary_anchor_dir
specify_cli/cli/commands/accept.py :: _stamp_birth_cutover_for_accept
specify_cli/cli/commands/agent/mission_feature_resolution.py :: _safe_load_meta
specify_cli/cli/commands/agent/mission_finalize.py :: finalize_tasks
specify_cli/cli/commands/agent/tasks_move_task.py :: _mt_resolve_targets
specify_cli/cli/commands/agent/tasks_move_task.py :: _mt_issue_matrix_facts
specify_cli/cli/commands/agent/workflow.py :: _analysis_report_gate_dir
specify_cli/cli/commands/agent/workflow.py :: _mission_id_for_claim
specify_cli/cli/commands/agent/workflow_executor.py :: implement_sparse_checkout_preflight
specify_cli/cli/commands/agent/workflow_executor.py :: implement_resolve_mission_type
specify_cli/cli/commands/agent/workflow_executor.py :: review_finalize_and_print
specify_cli/cli/commands/implement.py :: find_wp_file
specify_cli/cli/commands/implement.py :: _load_primary_anchored_mission_meta
specify_cli/cli/commands/implement.py :: _planning_artifact_source_dir
specify_cli/cli/commands/implement.py :: _build_implement_json_payload
specify_cli/cli/commands/mission_type.py :: close_cmd
specify_cli/cli/commands/mission_type.py :: _resolve_mission_handle
specify_cli/cli/commands/next_cmd.py :: _pair_previous_lifecycle_record
specify_cli/cli/commands/next_cmd.py :: _write_issuance_lifecycle_record
specify_cli/cli/commands/next_cmd.py :: _handle_answer
specify_cli/coordination/commit_router.py :: _resolve_mid8
specify_cli/merge/executor.py :: _run_lane_based_merge_locked
specify_cli/status/aggregate.py :: MissionStatus._find_meta_path   (x3: :499, :522, :543)
specify_cli/status/aggregate.py :: MissionStatus.save
```

(16 distinct qualnames-in-files above; `status/aggregate.py::MissionStatus._find_meta_path`
carries 3 of the 30 sites, so the count is 16 files / 30 sites. This is one
qualname/site fewer than the file/site tallies stated above this list (17
files / 31 sites) — see the correction note immediately below; **WP08's
end-state reconciliation is what makes the surrounding prose counts agree**
(`tasks.md` § 6).)

**WP06 correction (scoped ledger exception, `tasks.md` § 6 — the single
authorized row):** this list previously also carried
`specify_cli/retrospective/writer.py :: resolve_retrospective_home`. That row
is now **stale**: WP03's cycle-1 fix (`research/expected-reds.md` § WP03,
Ledger cycle-1 B1/B2) re-pointed that call at the module-private leaf
`_compose_primary_feature_dir` — a FIFTH FR-005/NFR-009 foundation site,
sitting beneath `PlacementSeam.read_dir`'s `RETROSPECTIVE` short-circuit
(`mission_runtime/resolution.py:1454`), not a routable `migrate-fail-loud`
bypass. Its corrected verdict is **`sanction-infra` (verify-only)** —
`resolve_retrospective_home` calls the leaf directly and permanently, even
after WP08 deletes the public wrapper. WP06 verified (not routed) this site:
confirmed the call target, the standing regression guard
(`tests/retrospective/test_home_resolution_single_authority.py::test_writer_authority_gates_on_primary_partition_kind`,
which reds when mutated back to the wrapper — checked non-vacuous), and no
cycle in the `read_dir` call graph. Consequence: the enumerated finding set
this row belonged to drops **32 → 31** (mission-wide) / this ledger's
in-flight `primary_feature_dir_for_mission` count drops **31 → 30** routable
sites. At WP06/WP08 time this row was **not** added to the machine-checked §
"Foundation-site sanctions" table above — that table's set is asserted
against `test_no_read_side_bypass.py`'s `_FOUNDATION_SANCTION_SEED`, which
WP06 did not own and could not edit (`tasks.md` § 6); recording a 4th ledger
row there without a matching code-side seed entry would have been a new gate
mismatch. **This row (and `status/aggregate.py::MissionStatus._find_meta_path`,
the same deferral) was finally folded into that machine-checked set by the
post-merge aggregate-squad closeout** (§ "Foundation-site sanctions" above,
this commit) — the census-gap the squad found was exactly this: the leaf
itself was never censused at all, so these two verified-but-unclaimed sites
sat outside every gate's view rather than merely outside one table.

## Known gap — `primary_feature_dir_for_mission` (CORRECTED, FR-016)

**This section previously claimed the primary primitive was "policed by
nothing".  That claim was false and is what manufactured
[#3014](https://github.com/spec-kitty/spec-kitty/issues/3014).** It was policed
on the **anchoring axis** by
`tests/architectural/test_resolution_authority_gates.py` (the retired-floor
gate WP01 rewrote; see that mission's own ledger) until that file was deleted
in #3285. What was actually true is
narrower: no gate policed it on the **call-site-bypass axis** — i.e. nothing
stopped a *new* call to it outside a tracked set. That gap is what this
revision closes: `primary_feature_dir_for_mission` is now one of the four
`_TARGET_CALLEE_NAMES` in `test_no_read_side_bypass.py`, with its 3 foundation
sites sanctioned above and its 31 remaining sites tracked as expected-red
(§ above) pending routing by WP04–WP08.

`resolve_feature_dir_for_mission` is likewise no longer a gap: it is fully
censused and classified in this revision (§ above).

**Remaining honest bounds** (named with sizes, per T013):

- **Wrong-`kind` argument class**: a call site that passes an incorrect
  `MissionArtifactKind` to `resolve_planning_read_dir`/`read_dir` is
  census-invisible by construction — this gate polices *which primitive is
  called*, not *which kind argument is correct*. Zero known instances; not
  discoverable by this gate's grammar regardless.
- **Wrapper laundering**: `resolve_subtasks_gate_dir` (`_read_path_resolver.py`)
  wraps `resolve_planning_read_dir` with a pinned `TASKS_INDEX` kind — a
  callee-name census cannot see through the wrapper to the primitive it
  launders. One wrapper, zero additional censused call sites (it is itself
  one of `resolve_planning_read_dir`'s already-counted historical sites).
- **Zero-site latent sibling — `resolve_feature_dir_for_slug`**: defined in
  the same module, deliberately **not exported** in `__all__` and has **zero**
  cross-module `src/` callers today (confirmed by the live census: it does
  not appear in any scan above). Importing it anywhere would silently
  re-open the exact gap this ledger closes for its siblings — it is not
  censused because there is nothing to census yet, not because it is safe.
- **Sanctioned foundation + resolver-internal sites**: 4 foundation sites
  (§ above) + resolver-internal self-reference in `_read_path_resolver.py`
  and `mission_runtime/resolution.py` — recorded by name, deliberately
  unrouted (NFR-009).
- **Artifacts with no kind**: `gap-analysis.md` anchors on a resolved
  directory rather than being routed through any `MissionArtifactKind` — an
  honest bound recorded in the mission spec, out of this gate's scope
  entirely (it never calls a censused primitive to begin with).

## Known gap — raw `KITTY_SPECS_DIR` joins (out of census grammar)

The census grammar is "calls to the four primitives", so a site that
reconstructs a mission directory by **joining path constants** is invisible to
it. One such site was found during the landing pass and is not represented by
any row above:

| file | construction | verdict | kind | rationale |
|---|---|---|---|---|
| `cli/commands/accept.py` | `coord_worktree_root / KITTY_SPECS_DIR / mission_slug` | migrate-fail-loud | `STATUS_STATE` | The COORD leg passed to `stamp_accept_cutover` as `status_feature_dir` — per `cutover_mission`'s contract, the `STATUS_STATE` port target. Migrated on 2026-07-27 to `placement_seam(...).read_dir(STATUS_STATE)` via `_coord_status_feature_dir`, which also fixes a latent bug: the hand-built join was wrong for identity-suffixed `<slug>-<mid8>` mission dirs. |

This class is policed by a *different* gate —
`tests/architectural/test_no_raw_mission_spec_paths.py`, which is what caught
this site — not by `test_no_read_side_bypass.py`. The two gates are
complementary and neither subsumes the other; the counts above deliberately
exclude this row so the real-call-site arithmetic keeps meaning "call sites of
the four censused primitives".

## Full ledger (historical — the original 2-primitive migration, WP03–WP07 of
## read-side-placement-seam-migration-01KYHP67)

**Preserved verbatim as the audit record of the completed migration (NFR-008)
— not machine-parsed, not reconciled against the live census above.** Every
`migrate-fail-loud` row below describes a site that has SINCE been routed
through the seam; only the `stay-lenient` rows still call the primitive
directly (and are re-declared, live, in the § "Stay-lenient allow-list index"
table above).

Columns: `file` · `symbol(s)` · `sites` (file:line) · `family` · `verdict` ·
`kind` (target `MissionArtifactKind` for a kind-blind migrate site; `n/a` for
sanction/stay-lenient/already-kind-aware) · `cluster` (which migration WP
consumed this row) · `rationale`.

### Sanction-infra

| file | symbol(s) | sites | family | verdict | kind | cluster | rationale |
|---|---|---|---|---|---|---|---|
| `src/mission_runtime/write_target_degrade.py` | `candidate_feature_dir_for_mission` | 1 (:183) | kind-blind | sanction-infra | n/a | N/A — sanctioned | Bootstrap-window write-target degrade helper (`resolve_write_target_or_degrade`); already excluded from the write-side whole-tree scan via the `src/mission_runtime/` `BOUNDARY_SANCTIONED_PREFIXES` blanket. Self-referential resolution infra, not a migration target (mirrors FR-003). |
| `src/specify_cli/coordination/surface_resolver.py` | `candidate_feature_dir_for_mission` | 1 (:675) | kind-blind | sanction-infra | n/a | N/A — sanctioned | The canonical surface resolver (`resolve_status_surface_with_anchor` et al.) that `candidate_feature_dir_for_mission` itself is partly built to serve; FR-003 names this module explicitly as sanctioned infra, not a bypass site awaiting a route. |

### WP03 — agent-CLI (`src/specify_cli/cli/commands/agent/**`)

| file | symbol(s) | sites | family | verdict | kind | cluster | rationale |
|---|---|---|---|---|---|---|---|
| `cli/commands/agent/mission_feature_resolution.py` | — | 0 real (grep hit only) | n/a | no-site | n/a | WP03 | Grep hit is prose (`:78,93,131,258`) describing the seam/primitives; zero `ast.Call` sites. |
| `cli/commands/agent/status.py` | `candidate_feature_dir_for_mission` | 1 (:72) | kind-blind | migrate-fail-loud | `PRIMARY_METADATA` | WP03 | Slug-canonicalization idiom (`legacy_dir = candidate_feature_dir_for_mission(...); if legacy_dir.exists(): return legacy_dir.name`) — the SAME idiom the seam's own `resolve_artifact_surface` uses (`canonical_slug = primary_dir.name`) for handle→dir-name folding. `candidate_feature_dir_for_mission`'s own docstring states it never raises `StatusReadPathNotFound`, only `MissionSelectorAmbiguous` (unchanged either way) — migration is behavior-preserving. |
| `cli/commands/agent/tasks_dependency_graph.py` | `resolve_planning_read_dir` | 1 (:134) | kind-aware | migrate-fail-loud | `WORK_PACKAGE_TASK` | WP03 | Builds the WP dependency graph from `tasks/` (PRIMARY-partition); genuine functional read, already kind-annotated. |
| `cli/commands/agent/tasks_map_requirements.py` | `resolve_planning_read_dir` | 2 (:312, :694) | kind-aware | migrate-fail-loud | `WORK_PACKAGE_TASK` (both) | WP03 | `map-requirements` WP-frontmatter read. (Line 679 is a docstring restatement of the :694 call — not a third site.) |
| `cli/commands/agent/tasks_materialization.py` | `resolve_planning_read_dir` | 1 (:118) | kind-aware | migrate-fail-loud | `WORK_PACKAGE_TASK` | WP03 | `tasks/WP*.md` materialization read. |
| `cli/commands/agent/tasks_move_task.py` | `candidate_feature_dir_for_mission` | 1 (:2368) | kind-blind | **stay-lenient** (ambiguous — reviewer confirm) | n/a | WP03 | Structurally atypical call: `repo_root` is `CoordinationWorkspace.worktree_path(...)` (an **already-resolved coord worktree path**, not the primary checkout) and the slug arg is a composed `mission_dir_name(...)`, not a raw handle — a direct probe of an already-verified coord worktree's own `status.events.jsonl`, not the seam's `repo_root`+topology contract. Defaulted lenient (no behavior change) pending a bespoke (non-mechanical) fix, not a kind-route. |
| `cli/commands/agent/tasks_parsing_validation.py` | `resolve_planning_read_dir` | 1 (:949) | kind-aware | migrate-fail-loud | `RESEARCH` | WP03 | Research-artifact dirty-tree check; explicitly documented as needing the PRIMARY leg, not the coord husk. |
| `cli/commands/agent/tasks.py` | `resolve_planning_read_dir` | 4 (:842, :943, :1155, :1303) | kind-aware | migrate-fail-loud | `WORK_PACKAGE_TASK` (:842, :1303), `TASKS_INDEX` (:943, :1155) | WP03 | `tasks/` reads and the pre-3.0-layout boundary guard; all four already kind-annotated. |
| `cli/commands/agent/tasks_shared.py` | `candidate_feature_dir_for_mission`, `resolve_planning_read_dir` | 2 (:252, :455) | mixed | migrate-fail-loud (both) | `PRIMARY_METADATA` (:252, slug-canon idiom — same as `status.py:72`), `TASKS_INDEX` (:455) | WP03 | :252 is the same recurring slug-canonicalization idiom as `status.py:72`/`mission_type.py:413`/`next_cmd.py:377`/`merge/resolve.py:67`/`workflow.py:820` (6 near-duplicate sites — a consolidation candidate for a future helper, out of this mission's scope but worth flagging). |
| `cli/commands/agent/tasks_status_cmd.py` | `candidate_feature_dir_for_mission`, `resolve_planning_read_dir` | 2 (:160, :170) | mixed | :160 **stay-lenient** (ambiguous — reviewer confirm); :170 migrate-fail-loud | n/a (:160); `WORK_PACKAGE_TASK` (:170) | WP03 | :160 is explicitly documented as a "last-ditch fallback to the original worktree-aware path" using a **CWD-derived** `status_read_root` (not `repo_root`) "so tests / projects that stand up status files in unusual places still work." The seam is explicitly CWD-invariant by design (data-model.md) — routing this fallback through it would defeat its documented purpose. |
| `cli/commands/agent/workflow_executor.py` | `resolve_planning_read_dir`, `candidate_feature_dir_for_mission` | 2 (:1713, :1721) | mixed | migrate-fail-loud (both) | `WORK_PACKAGE_TASK` (:1713); `STATUS_STATE` (:1721) | WP03 | :1721 reads the event log to warn about dependent WPs during review — a genuine functional STATUS read (not diagnostic); fail-loud-appropriate. |
| `cli/commands/agent/workflow.py` | `candidate_feature_dir_for_mission` (3), `resolve_planning_read_dir` (4) | 7 real (:820, :855, :862, :1391, :1396, :1450, :1465) | mixed | migrate-fail-loud (all 7) | `PRIMARY_METADATA` (:820, slug-canon idiom); `WORK_PACKAGE_TASK` (:855, :1391, :1450); `STATUS_STATE` (:862, :1465 — dependency-gate/review-gate lane reads via the event log); `LANE_STATE` (:1396) | WP03 | **Hard case / own attention** (highest site-density file). See the research.md-correction note above: raw grep counted 9 hits here, 2 are docstring prose (`:843`, `:1447`) describing the exact calls at `:855`/`:1465` — only 7 are real. |

### WP04 — CLI-commands (`src/specify_cli/cli/commands/*.py` + `cli/commands/charter/_widen.py`)

| file | symbol(s) | sites | family | verdict | kind | cluster | rationale |
|---|---|---|---|---|---|---|---|
| `cli/commands/archive.py` | `candidate_feature_dir_for_mission` | 1 (:65) | kind-blind | **stay-lenient, flagged multi-kind** (ambiguous — reviewer confirm) | n/a | WP04 | `feature_dir` is an existence probe then passed into `archive_mission(feature_dir=...)` (`src/specify_cli/missions/_archive.py:300`), which threads it into BOTH `terminal_state_resolver` (a STATUS_STATE read) and `invariants_reader` (an ACCEPTANCE_MATRIX read) — a genuine multi-kind reader off one kind-blind anchor. A single-kind `PRIMARY_METADATA` swap would be false precision. Defaulted **stay-lenient** (mission ambiguous→safer rule); WP04 should split into two seam calls (`STATUS_STATE` + `ACCEPTANCE_MATRIX`) before migrating. |
| `cli/commands/charter/_widen.py` | `candidate_feature_dir_for_mission` | 1 (:54) | kind-blind | migrate-fail-loud | `PRIMARY_METADATA` | WP04 | Reads `meta.json` only (`load_meta_or_empty(feature_dir).get("mission_id")`). |
| `cli/commands/_coordination_doctor.py` | `resolve_planning_read_dir` | 2 (:933, :1057) | kind-aware | **stay-lenient** | n/a (`WORK_PACKAGE_TASK` already declared, but kept lenient by doctrine) | WP04 | Named explicitly in research.md's hard-cases list — a diagnostic tool auditing `pending_coord_reconcile` markers / live-strand findings across the corpus; both sites already catch `(ValueError, MissionSelectorAmbiguous)` and degrade to a warning finding rather than abort the doctor run. Kept lenient module-wide per doctrine, independent of this particular kind's incidental safety. |
| `cli/commands/decision.py` | — | 0 real (grep hit only) | n/a | no-site | n/a | WP04 | Grep hit at `:125` is a comment describing the STATUS-partition leg; zero `ast.Call` sites. |
| `cli/commands/merge.py` | `resolve_planning_read_dir` | 1 (:284) | kind-aware | migrate-fail-loud | `PRIMARY_METADATA` | WP04 | `--abort` teardown reading `meta.json` to discover the coord worktree's `mid8`; genuine functional read. |
| `cli/commands/mission_type.py` | `candidate_feature_dir_for_mission` | 1 (:413) | kind-blind | migrate-fail-loud | `PRIMARY_METADATA` | WP04 | Same slug-canonicalization idiom as `agent/status.py:72` (see the 6-site cluster note under `tasks_shared.py`). |
| `cli/commands/next_cmd.py` | `candidate_feature_dir_for_mission` | 1 (:377) | kind-blind | **migrate-fail-loud** (ambiguous — reviewer confirm) | `PRIMARY_METADATA` | WP04 | Same slug-canonicalization idiom, but this site's `except StatusReadPathNotFound` branch explicitly `raise`s (re-surfaces the typed error) rather than degrading — the author evidently believed this exception was reachable here. Per the primitive's own docstring it is not (only `MissionSelectorAmbiguous` propagates), so the branch is already dead; migrating to `PRIMARY_METADATA` preserves that (still dead, never reachable). Flagged so WP04 double-checks this specific site's except-clause before/after the swap. |
| `cli/commands/reconcile.py` | `candidate_feature_dir_for_mission` | 1 (:126) | kind-blind | **stay-lenient, flagged multi-kind** (ambiguous — reviewer confirm) | n/a | WP04 | `feature_dir` feeds `dossier.snapshot.load_snapshot` (reads a `.kittify/dossiers/<slug>/snapshot-latest.json` cache — no direct `MissionArtifactKind` mapping) and then a `present_projection` rebuild that hashes across several artifact kinds for drift comparison — a genuine multi-kind reader with no single clean target kind. Defaulted lenient; the fail-closed `ReconciliationResult.ERROR` return already absorbs any resolution failure gracefully, so no regression from staying put. |
| `cli/commands/research.py` | `resolve_planning_read_dir` | 2 (:95, :110) | kind-aware | migrate-fail-loud | `RESEARCH` (:95), `FINALIZED_EXECUTION_PLAN` (:110) | WP04 | Research-artifact scaffold + `plan.md` validation reads; both already kind-annotated. |
| `cli/commands/retrospect.py` | `candidate_feature_dir_for_mission` | 2 (:110, :1005) | kind-blind | **stay-lenient** (both; :110 ambiguous — reviewer confirm) | n/a | WP04 | :110 (`_canonical_events_path`) is an explicit fallback fired only when `resolve_status_surface` raises `FileNotFoundError`/`ValueError` — "meta.json absent for a legacy mission" per its own docstring; migrating the fallback leg to the fail-loud seam risks raising `CoordinationBranchDeleted` in exactly the degraded window this fallback exists to tolerate. :1005 is a corpus-walk classifier iterating **every** mission under `.kittify/missions/` to compute a 4-state retrospective-coverage report — a single problematic mission's coord-branch deletion must not abort the whole report (named diagnostic pattern, research.md). |
| `cli/commands/validate_tasks.py` | `resolve_planning_read_dir` | 1 (:120) | kind-aware | migrate-fail-loud | `WORK_PACKAGE_TASK` | WP04 | `scan_all_tasks_for_mismatches` WP-frontmatter read; already kind-annotated, explicit prior bugfix (coord husk silently returned `{}`). |
| `cli/commands/verify.py` | `candidate_feature_dir_for_mission` | 1 (:33) | kind-blind | migrate-fail-loud | `PRIMARY_METADATA` | WP04 | Existence-gated presentation adapter (`spec-kitty verify` environment check) — a pure existence probe. **Exception axis:** no-op — `PRIMARY_METADATA` never raises `CoordinationBranchDeleted`. **Anchoring axis:** the seam adds a `get_main_repo_root` hop that `candidate_feature_dir_for_mission` did not perform, so `_existing_feature_dir` becomes CWD-invariant — a worktree `project_root` now resolves `<main repo>/kitty-specs/<slug>` where it previously returned `None`. Both production callers (`verify_setup` via `find_repo_root`/`get_project_root_or_exit`; `_run_diagnostics_mode` via `locate_project_root`) already pass a main-repo-anchored root, so the hop is idempotent and the migration is observationally a no-op **for the production paths** — but not for a direct call on a raw worktree path. Accepted as the intended contract on 2026-07-27; pinned by `tests/specify_cli/test_active_mission_removal.py::test_existing_feature_dir_is_cwd_invariant`. |

### WP05 — merge+lanes (`src/specify_cli/consolidation/**` + `src/specify_cli/lanes/**`)

| file | symbol(s) | sites | family | verdict | kind | cluster | rationale |
|---|---|---|---|---|---|---|---|
| `lanes/lifecycle_sync.py` | `resolve_planning_read_dir` | 1 (:149) | kind-aware | migrate-fail-loud | `LANE_STATE` | WP05 | Auto-rebase `lanes.json` read; already kind-annotated, explicit prior silent-skip bugfix note. |
| `lanes/merge.py` | `resolve_planning_read_dir` | 2 (:143, :291) | kind-aware | migrate-fail-loud | `LANE_STATE` (both) | WP05 | Mission-merge `lanes.json` reads. |
| `lanes/recovery.py` | `resolve_planning_read_dir`, `candidate_feature_dir_for_mission` | 3 (:602, :606, :706) | mixed | migrate-fail-loud (all 3) | `LANE_STATE` (:602, :706); `STATUS_STATE` (:606, comment: "STATUS leg: the append-only event log stays coord-aware") | WP05 | Recovery-state computation genuinely needs to know whether the coord branch backing a WP's event log was deleted, rather than silently reading a stale/absent surface. |
| `lanes/worktree_allocator.py` | `resolve_planning_read_dir` | 1 (:442) | kind-aware | migrate-fail-loud | `PRIMARY_METADATA` | WP05 | Chicken-and-egg coord-topology discovery read (`meta.json.coordination_branch`); explicitly documented as needing the topology-blind PRIMARY leg (it produces the very topology answer a coord-aware read would need). |
| `merge/done_bookkeeping.py` | `resolve_planning_read_dir` | 2 (:262, :578) | kind-aware | migrate-fail-loud | `WORK_PACKAGE_TASK` (both) | WP05 | Merge-complete WP-file lookup + committed-events anchor; already kind-annotated with an explicit "historical comment predated the kind-aware split" correction note. |
| `merge/executor.py` | `resolve_planning_read_dir`, `candidate_feature_dir_for_mission` | 4 (:520, :1540, :1547, :1550) | mixed | migrate-fail-loud (all 4) | `WORK_PACKAGE_TASK` (:520); `STATUS_STATE` (:1540, comment: "MUST stay on topology-aware resolver"); `PRIMARY_METADATA` (:1547); `LANE_STATE` (:1550) | WP05 | :1540's STATUS leg is a genuine functional read feeding `run.feature_dir` for the coord-aware event log during a lane-based merge — fail-loud-appropriate (a merge must not silently treat a deleted coord branch as healthy). |
| `merge/forecast.py` | `resolve_planning_read_dir` | 1 (:160) | kind-aware | migrate-fail-loud | `LANE_STATE` | WP05 | Dry-run `lanes.json` read; explicit prior bugfix note (spurious "missing lanes" report off the coord husk). |
| `merge/ordering.py` | — | 0 real (grep hit only) | n/a | no-site | n/a | WP05 | Grep hit at `:372` is a comment describing `candidate_feature_dir_for_mission`; zero `ast.Call` sites. |
| `merge/resolve.py` | `candidate_feature_dir_for_mission`, `resolve_planning_read_dir` | 2 (:67, :109) | mixed | migrate-fail-loud (both) | `PRIMARY_METADATA` (:67, slug-canon idiom; :109, merge-state key identity read) | WP05 | :67 is the same 6-site slug-canonicalization idiom as `agent/status.py:72`. |

### WP06 — diagnostic-heavy

| file | symbol(s) | sites | family | verdict | kind | cluster | rationale |
|---|---|---|---|---|---|---|---|
| `coordination/status_transition.py` | `candidate_feature_dir_for_mission`, `resolve_planning_read_dir` | 3 (:606, :623, :1259) | mixed | migrate-fail-loud (all 3) | `PRIMARY_METADATA` (:606, :623 — `_canonical_primary_feature_dir`'s create-window/malformed-meta degrade branches, which want the topology-blind PRIMARY anchor, not a coord read); `LANE_STATE` (:1259) | WP06 | :606/:623 compute the transaction-identity **primary anchor** for the status write path (not a STATUS read) — `PRIMARY_METADATA` is the correct, behavior-preserving target (never raises, matching the existing degrade contract verbatim). Not one of the 3 FR-003-named sanctioned modules, so this is a regular migrate site despite its proximity to the status machinery. |
| `dashboard/scanner.py` (removed, #5530) | `resolve_planning_read_dir` | 2 (:423, :461) | kind-aware | **stay-lenient** | n/a (`PRIMARY_METADATA`, `TASKS_INDEX` already declared, but kept lenient by doctrine) | WP06 | Named explicitly in research.md's hard-cases list; both sites already catch `(ValueError, MissionSelectorAmbiguous)` with an explicit "the dashboard scan must never crash" comment. Kept lenient module-wide. |
| `decisions/service.py` | `resolve_planning_read_dir` | 1 (:173) | kind-aware | migrate-fail-loud | `STATUS_STATE` | WP06 | Decision-log companion `status.events.jsonl` read — explicitly documented as needing to "agree with where `emit.py` writes" (the permanent coord-authority write target); a genuine functional read, fail-loud-appropriate (a stale/deleted coord branch here is a real split-brain risk, not tolerable). |
| `dossier/api.py` (removed, #5530) | `candidate_feature_dir_for_mission` | 3 (:227, :397, :435) | kind-blind | **stay-lenient** (all 3; ambiguous — reviewer confirm) | n/a | WP06 | Every site feeds `dossier.snapshot.load_snapshot`, which reads a `.kittify/dossiers/<slug>/snapshot-latest.json` cache file — not a `MissionArtifactKind`-mapped artifact. The API already treats "not found" as an expected outcome (`error_response(..., 404)`), not an exception; these are external/SaaS-facing read endpoints (`SnapshotExportResponse` docstring: "SaaS import-compatible") that should not start raising `CoordinationBranchDeleted` for a mission whose coord branch was later consolidated away (a plausible steady state post-merge). |
| `retrospective/summary.py` | `candidate_feature_dir_for_mission` | 1 (:220) | kind-blind | **stay-lenient** | n/a (`STATUS_STATE`) | WP06 | Own docstring: "Returns (0, 0, 0) on any error, including missing slug, missing log, or corrupt lines" — an explicitly resilient summary-statistics reader, named in the WP06 diagnostic cluster. |
| `retrospective/writer.py` | — | 0 real (grep hit only) | n/a | no-site | n/a | WP06 | Grep hit at `:55` is a docstring cross-reference to `resolve_planning_read_dir`; zero `ast.Call` sites. |
| `review/cycle.py` | `resolve_planning_read_dir` | 1 (:49) | kind-aware | migrate-fail-loud | `WORK_PACKAGE_TASK` | WP06 | Docstring already documents this site as having "retir[ed] the kind-blind `candidate_feature_dir_for_mission` fold" historically (#2646/#2697/#2275) — this is the final swap from the lenient kind-aware resolver to the seam. |
| `status/aggregate.py` | `candidate_feature_dir_for_mission` | 1 (:527) | kind-blind | **stay-lenient** | n/a | WP06 | Named explicitly in research.md's hard-cases list; the surrounding code already translates `StatusReadPathNotFound` into a graceful fail-closed result for every handle form rather than letting it propagate raw — status aggregation is itself an audit/reporting surface. |

### WP07 — core/misc

| file | symbol(s) | sites | family | verdict | kind | cluster | rationale |
|---|---|---|---|---|---|---|---|
| `acceptance/__init__.py` | `resolve_planning_read_dir` | 1 (:824) | kind-aware | migrate-fail-loud | `WORK_PACKAGE_TASK` | WP07 | Accept-gate WP-task read; explicit invariant check (`is_primary_artifact_kind(WORK_PACKAGE_TASK)`) already guards for a future re-partition. |
| `agent_tasks_ports.py` | `resolve_planning_read_dir` | 2 (:244, :250) | kind-aware | migrate-fail-loud | passthrough (:244, caller-supplied `kind`); `WORK_PACKAGE_TASK` (:250) | WP07 | `FsReader` port adapter (`RealFsReader`) — a direct 1:1 swap: `resolve_planning_read_dir(root, slug, kind=kind)` → `PlacementSeam(root, slug).read_dir(kind)`. |
| `agent_utils/status.py` | `resolve_planning_read_dir` | 1 (:137) | kind-aware | migrate-fail-loud | `WORK_PACKAGE_TASK` | WP07 | Tasks-status report read of the PRIMARY leg. |
| `cli/commands/agent/mission_record_analysis.py` | `resolve_planning_read_dir` | 1 (:321) | kind-aware | migrate-fail-loud | `SPEC` (via `_kind_for_artifact("spec")`) | WP07 | Analysis-report gate-dir read feeding `write_analysis_report`; already kind-annotated (dynamically). Note: this file sits under `cli/commands/agent/` (WP03's directory glob) but is explicitly assigned to WP07 by the mission's cluster list — flagging the directory/cluster mismatch for the WP03/WP07 owners to coordinate `owned_files` on this one file. |
| `context/resolver.py` | `resolve_planning_read_dir` | 2 (:222, :252) | kind-aware | migrate-fail-loud | `WORK_PACKAGE_TASK` (:222 — single anchor also used for the immediately-following `meta.json` read; both `WORK_PACKAGE_TASK` and `PRIMARY_METADATA` are PRIMARY-partition and resolve to the identical dir, so this is a documented single-kind anchor, not a multi-kind split candidate); `LANE_STATE` (:252) | WP07 | `MissionContext` construction; both already kind-annotated. |
| `core/stale_detection.py` | `resolve_planning_read_dir` | 1 (:446) | kind-aware | migrate-fail-loud | `WORK_PACKAGE_TASK` | WP07 | Already wrapped in a broad `except Exception: return None` at the call site, independent of the seam's own fail-loud behavior. |
| `core/worktree_topology.py` | `resolve_planning_read_dir` | 1 (:145) | kind-aware | migrate-fail-loud | `LANE_STATE` | WP07 | Co-resolves identity + `lanes.json` + dependency graph from one PRIMARY anchor; documented single-kind anchor (all three are PRIMARY-partition). |
| `doctrine_synthesizer/apply.py` | `resolve_planning_read_dir` | 1 (:167) | kind-aware | migrate-fail-loud | `STATUS_STATE` | WP07 | Per-kind apply logic's STATUS surface read; a genuine functional (not diagnostic) read — fail-loud-appropriate. |
| `manifest.py` | `candidate_feature_dir_for_mission` | 1 (:272) | kind-blind | **stay-lenient** (ambiguous — reviewer confirm) | n/a | WP07 | The `worktree_path` (not `repo_root`) is passed as the resolver's first arg — a deliberate "what artifacts physically exist in THIS worktree" probe, compared against the sibling `artifacts_in_main` leg (already migrated to `placement_seam(self.repo_root, feature).read_dir(PRIMARY_METADATA)` per the adjacent comment). Structurally incompatible with the seam's `repo_root`+topology contract; migrating would collapse the main-vs-worktree drift comparison this diagnostic exists to make. |
| `mission_loader/command.py` | `candidate_feature_dir_for_mission` | 1 (:157) | kind-blind | migrate-fail-loud | `PRIMARY_METADATA` | WP07 | Feeds `_ensure_feature_metadata(feature_dir, ...)` — a `meta.json`-adjacent read. |
| `missions/plan/plan_interview.py` | `resolve_planning_read_dir` | 1 (:66) | kind-aware | migrate-fail-loud | `PRIMARY_METADATA` | WP07 | `mission_id` read for the plan interview; already kind-annotated. |
| `missions/plan/specify_interview.py` | `resolve_planning_read_dir` | 1 (:66) | kind-aware | migrate-fail-loud | `PRIMARY_METADATA` | WP07 | Same pattern as `plan_interview.py:66` (near-duplicate module pair). |
| `orchestrator_api/wp_lifecycle.py` | — | 0 real (grep hit only) | n/a | no-site | n/a | WP07 | Grep hit is the comment in `append_history` describing the seam route (it sat in `orchestrator_api/commands.py` at `:1544` before the #5628 split); zero `ast.Call` sites. |
| `runtime/next/runtime_bridge_identity.py` | — | 0 real (grep hit only) | n/a | no-site | n/a | WP07 | Grep hit at `:97` is a docstring mention of `candidate_feature_dir_for_mission`; zero `ast.Call` sites. Also the shared-package-boundary file the spec's edge cases flag for a routing confirmation — moot here since there is no real call to route. This mission's own census finds THREE real `primary_feature_dir_for_mission` calls in this same file (`runtime/next/runtime_bridge.py:260,1244` and `runtime_bridge_identity.py:118`) — see § "primary_feature_dir_for_mission — live census" above; a different primitive, not a re-derivation of this row. |
| `sync/events.py` | `candidate_feature_dir_for_mission` | 1 (:120) | kind-blind | migrate-fail-loud | `PRIMARY_METADATA` | WP07 | "Best-effort lookup of the canonical `mission_id`" for a dashboard sync trigger; reads `meta.json` only. |
| `task_utils/support.py` | `resolve_planning_read_dir` | 1 (:548) | kind-aware | migrate-fail-loud | `WORK_PACKAGE_TASK` | WP07 | `tasks/` root read for the CLI task-view reconstruction. |
| `workspace/context.py` | `resolve_planning_read_dir` | 6 (:481, :679, :730, :770, :811, :877) | kind-aware | migrate-fail-loud (all 6) | `WORK_PACKAGE_TASK` (:481, :679, :730); `LANE_STATE` (:770, :811, :877) | WP07 | Partially migrated already: line 477 (adjacent to :481) already uses `placement_seam(repo_root, context.mission_slug).read_dir(MissionArtifactKind.STATUS_STATE)` directly — the remaining 6 sites are the same file's not-yet-migrated PRIMARY-partition legs. |

## Notes for the migration WPs (WP03–WP08)

- **The 6-site slug-canonicalization idiom** (`legacy_dir = candidate_feature_dir_for_mission(...); if legacy_dir.exists(): return legacy_dir.name`) recurs verbatim in `cli/commands/agent/status.py:72`, `cli/commands/agent/tasks_shared.py:252`, `cli/commands/agent/workflow.py:820`, `cli/commands/mission_type.py:413`, `cli/commands/next_cmd.py:377`, and `merge/resolve.py:67` — all six migrate to `PlacementSeam.read_dir(MissionArtifactKind.PRIMARY_METADATA)`, mirroring the seam's own internal canonicalization pattern in `resolve_artifact_surface`. Six near-identical duplications of the same "resolve a handle to its canonical on-disk directory name" operation is itself a recurring-boundary-leak worth a follow-up consolidation ticket (a shared helper), but is out of this mission's scope (C-001 forbids introducing a second read authority; a shared *helper* built atop the one authority would not violate that, but is not requested by any FR here).
- **Two files fall outside the WP03–WP07 directory globs but are explicitly assigned by the mission's own cluster list**: `cli/commands/agent/mission_record_analysis.py` (physically under `cli/commands/agent/**`, WP03's glob) is assigned to **WP07**, and `cli/commands/charter/_widen.py` (not under a bare `cli/commands/*.py` glob) is assigned to **WP04** explicitly. Both are called out here so the corresponding `owned_files` lists match the mission's cluster assignment, not the naive directory glob.
- No bypass file fell outside all five clusters (WP03–WP07) or the sanctioned-infra set — every one of the 60 consumer files is accounted for above (all historical, all `candidate_feature_dir_for_mission`/`resolve_planning_read_dir`).
- **This revision's `resolve_feature_dir_for_mission` classification** (§ above) is the new authority for the 8 sites this primitive covers; WP04's cluster table applies it (never re-derives it).
- **This revision's `primary_feature_dir_for_mission` expected-red list** (§ above) is not yet classified — a later WP applies the shared migration procedure per site and reports any ledger gap back to WP02's owner rather than authoring a row itself (tasks.md § 6).
