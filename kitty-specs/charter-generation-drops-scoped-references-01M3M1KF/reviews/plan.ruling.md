# Operator rulings — plan phase, round 4

Dated 2026-09-28. Both rulings below are quoted verbatim, attributed to **the operator**.

## Round-3 ruling (standing — already reflected in plan.md; restated here for the record, not
re-litigated in this round)

On finding `PLAN-FRESH2-001` (widening the whole-kind fail-closed check to `graph.unresolved`, and
what to do about total graph-load failure), the operator ruled:

> "Widen, bounded: route `graph.unresolved` ids through the same classify-and-placeholder helper
> so they count toward the whole-kind fail-closed check and get a reason; graph-load failure emits
> a loud, structured diagnostic (also in `--json`) instead of vanishing, without attempting to
> reconstruct the transitive closure. Stays in compiler.py, same defect class, keeps the plan's
> 'one shared helper' campsite claim true."

With an explicit constraint: **graph-load failure does NOT make `generate` fail closed** (the
operator explicitly declined the stricter fail-closed-on-graph-load-failure option) — it must be
loud and structured, not fail-closed.

This ruling is implemented in plan.md's "WP-CORE reconciliation" → "Round-3 amendment to point 3"
subsection (Design parts (a)/(b)/(c)) and in `tracer-design-decisions.md`'s "Decision: operator
ruling on PLAN-FRESH2-001" entry.

## Round-4 ruling — per finding, this round

### 1. PLAN-FRESH2-001 / PLAN-FRESH3-001 (sev4, ONE defect filed twice across rounds)

The plan must specify parsing each `graph.unresolved` entry's URN (`"<kind>:<id>"`, both tuple
elements are the same URN per query.py) exactly as `resolve_transitive_refs`'s successful-lookup
branch does — `urn.split(":", 1)` (see `src/charter/offering/drg/query.py:397-398`, the pattern
`bare_id = urn.split(":", 1)[1] if ":" in urn else urn`), then mapping the singular DRG/NodeKind
kind to the plural repository name `_raw_kind_repository` expects
(`src/charter/activation/compiler.py:1073`) — USING AN EXISTING MAPPING IN THE CODEBASE IF ONE
EXISTS. Search for one and cite it in the plan text (file:line), don't invent a new one if an
existing one fits. A strong candidate to verify: `src/charter/offering/artifact_kinds.py` —
`ArtifactKind` is a `StrEnum` whose singular values match `NodeKind`'s singular values for the 9
gated kinds, and its `.plural` property (backed by the `_PLURALS` dict, `artifact_kinds.py:52-64`)
returns exactly the plural strings `_raw_kind_repository` and the 9-kind gated set
`_RAW_REPOSITORY_KINDS` (`src/charter/activation/resolver.py:98-108`) expect (`"directives"`,
`"tactics"`, `"styleguides"`, `"toolguides"`, `"paradigms"`, `"procedures"`, `"agent_profiles"`,
`"mission_step_contracts"`, `"glossary_packs"`). Verify this yourself against live code before
citing it — check whether `ArtifactKind(kind_str)` construction from a bare NodeKind singular
string round-trips correctly, and what it raises (`ValueError`) for a `NodeKind` value that is NOT
an `ArtifactKind` member (`NodeKind` has `action`, `glossary_scope`, `glossary`, `mission_type`
with no `ArtifactKind` counterpart — see `src/charter/offering/drg/models.py:43-77`), and
separately what happens when `ArtifactKind.plural` resolves to a plural string (e.g.
`"templates"`, `"assets"`, `"anti_patterns"`) that is valid but still outside
`_RAW_REPOSITORY_KINDS`'s 9-member set (so `_raw_kind_repository`/`raw_repository` degrades to
`None` for it, per resolver.py's documented degrade-silently-to-`None` behavior). The plan must
state what happens for a URN whose kind maps to no repository (either case above) OR which has no
":" in it: it must be preserved/reported as an unresolved reference with a reason string, NEVER
crash (no unguarded `.get()`/`in ...` on a `None` repository) and NEVER be silently dropped from
the count/placeholder output.

### 2. PLAN-FRESH3-002 (sev3) — DIAGNOSTICS SINK

Pass the existing diagnostics list into the private `_resolve_transitive_reference_graph`
(`src/charter/activation/compiler.py`, currently ~lines 1296-1307, its `except Exception: return
fallback` branch) and append the structured graph-load-failure record INSIDE that except branch,
at the point the exception is caught — not by widening the function's return type. The return type
stays a `ResolveTransitiveRefsResult` (unchanged) and the shared `ResolveTransitiveRefsResult`
model (`charter.offering.drg.query`) stays UNCHANGED — do not propose a tuple/`NamedTuple`
return-type widening or a marker exception; that option is explicitly declined by the operator.
Add `_resolve_transitive_reference_graph` to IC-01's "Affected surfaces" list in plan.md.

### 3. PLAN-FRESH3-003 (sev2)

Add the dedicated red-first whole-kind-test commit (and the `graph.unresolved` / graph-load-failure
red-first tests within it) as an explicit, numbered step in the "Phasing & Sequencing" list in
plan.md, so that list agrees with what ATDD-First Discipline and PR Shape already say (both already
updated in round 3). Do not just cross-reference the other sections in prose — the numbered list
itself must show the step.

### 4. PLAN-FRESH3-004 (sev2)

State explicitly (in plan.md's round-3 amendment "Design, part (c)" area and/or the contract doc)
that the new structured graph-load-failure record's `cause` field is a plain `str` (e.g.
`"graph_load_failed"`), NOT the `CatalogMissCause` enum type. State explicitly that
`CatalogMissCause` / `src/charter/activation/_catalog_miss.py` stay REUSED, NOT MODIFIED (no new
enum member) — and that Project Structure's existing "`_catalog_miss.py` ... REUSED, not modified"
line is correct and why (the new sentinel value never flows through `CatalogMissDiagnosis`, which
stays strictly typed to the 4-member enum).

---

## Disposition — how round 4 applied each ruling

- **Item 1** (PLAN-FRESH2-001/PLAN-FRESH3-001): implemented in plan.md's Round-3 amendment,
  "Design, part (a)" (rewritten with an explicit 3-step URN-split/kind-mapping/classify sequence,
  citing `query.py:391`/`:394`, `artifact_kinds.py:51-64`/`:125-148`, `resolver.py:100-112`/`:393-
  424`, `drg/models.py:43-76`, `compiler.py:37,289-292,1073-1093`) and "Design, part (b)" (bounds
  the per-kind aggregate count to ids the mapping could actually attribute to one of the six
  tracked kinds). Also corrected in `tracer-design-decisions.md`'s ruling entry, point 1/2, and in
  the Project Structure source tree comment for `compiler.py`. Verified line numbers differ
  slightly from the finding's own citations (drift across rounds) — `query.py:391`/`:394` (not
  `:397-398`), `artifact_kinds.py:51-64`/`:125-148` (not `:52-64`), `resolver.py:100-112`/`:393-
  424` (not `:98-108`) — re-verified against live `HEAD` source in this round, not taken on faith
  from the prior finding's citations.
- **Item 2** (PLAN-FRESH3-002): implemented in plan.md's Round-3 amendment, "Design, part (c)"
  (rewritten to specify two mutable-list sink parameters — `diagnostics: list[str]` and a new
  structured-records list — passed into `_resolve_transitive_reference_graph`, appended to inside
  its `except Exception:` branch at `compiler.py:1306`, immediately before `return fallback` at
  `compiler.py:1307`; return type unchanged). `_resolve_transitive_reference_graph` added to IC-01's
  "Affected surfaces" list.
- **Item 3** (PLAN-FRESH3-003): implemented — "Phasing & Sequencing" now has an explicit numbered
  step 2, "WP-CORE-TESTS", for the dedicated red-first whole-kind-unresolved test commit, between
  WP-ATDD (step 1) and WP-CORE (renumbered step 3); WP-JSON/WP-AUTOREFRESH/WP-CLEANUP-VERIFY
  renumbered 4/5/6 accordingly.
- **Item 4** (PLAN-FRESH3-004): implemented — plan.md's Design part (c) and Project Structure's
  `_catalog_miss.py` tree comment, plus `contracts/charter-generate-json-diagnostics.md`'s Round-3
  addition section, all now state explicitly that the structured record's `cause` field is typed
  `str`, not `CatalogMissCause`, and that `_catalog_miss.py` stays unmodified because of that typing
  choice.

## Round-5 ruling

> "Invariants + closing round. Round 5 applies the four PLAN-FRESH4 remedies AND restates decision 3
> as testable invariants rather than line-level mechanism: (I1) every activated reference id, from
> any source bucket (graph.<kind> or graph.unresolved), ends up either in catalog.references
> (resolved or placeholder) or in a structured diagnostic — never silently absent; (I2) the
> whole-kind fail-closed check is evaluated once per kind, after ALL sources (all per-kind render
> calls and the kind-mapped graph.unresolved pass) have contributed, and a kind counts as activated
> if any source attributed an id to it; (I3) every structured diagnostic record carries a defined
> kind, id and cause, including for unresolved URNs whose kind is outside the six tracked kinds, has
> no repository mapping, or has no ':' (contract doc defines the sentinel/shape for each, cause is a
> plain str distinct from CatalogMissCause values and 'graph_load_failed'); (I4) graph-load failure
> yields a loud structured diagnostic and does not fail closed (round-3 ruling); (I5) generation is
> deterministic across repeat invocations on the fail-closed and diagnostic paths. Each invariant
> maps to a named red-first test fixture in the ATDD-First section. Remaining mechanism detail
> belongs to the tasks squad and WP reviews, where the red-first tests catch it."

### Disposition — how round 5 applied the ruling

- **PLAN-FRESH4-001** (activation-detection input conflated with output-emptiness condition):
  closed by I2's explicit OR condition ("a kind counts as activated if any source attributed an id
  to it") — plan.md's "WP-CORE reconciliation" point 3, "Round-5 restatement" subsection, and IC-01's
  Risk (3).
- **PLAN-FRESH4-002** (three contradictory timing statements for when the check runs): closed by I2
  stating the single evaluation point once, unambiguously — the prior three inconsistent statements
  (decision 3's original "immediately after each per-kind call", the round-3 amendment's "automatically
  sees them", and IC-01's Risk (3) "strictly AFTER all per-id classification") were all replaced by
  I2's one statement, reconciled at both landing sites (the invariant restatement and IC-01's Risk (3)).
- **PLAN-FRESH4-003** (no defined `kind`/`id` shape for three unattributable `graph.unresolved`
  classes): closed by I3 plus `contracts/charter-generate-json-diagnostics.md`'s new "Round-5
  addition" section, which defines the `kind`/`id`/`cause` shape for all three classes (malformed
  URN, unrecognized kind prefix, valid-but-untracked/no-repository kind), using `cause` values
  `"malformed_urn"` and `"unattributed_kind"`, both plain `str`, distinct from `CatalogMissCause` and
  from `"graph_load_failed"`.
- **PLAN-FRESH4-004** (PR Shape's "six" vs. its own five-item enumeration): closed by correcting the
  count to "five" in plan.md's "PR Shape" section; the enumeration itself was already correct and is
  unchanged.
- **Line-level mechanism prose** (decision 3's original "Design" paragraph and the "Round-3 amendment
  to point 3" subsection, plan.md's former lines ~274–571) was replaced, not appended to, by the
  five invariants (I1–I5), a short non-binding implementation sketch, and a retained list of the
  load-bearing operator rulings (URN split/kind mapping, the diagnostics sink mechanism, `cause`'s
  plain-`str` typing, I4's not-fail-closed rule) stated as binding. plan.md net-shrank (633 → 428
  lines) despite the additions this round required.
- **`reviews/plan-verify-4.yaml`'s residual** (`_raw_kind_repository`'s `getattr` fallback raising
  `AttributeError` instead of degrading to `None` for `"template"`/`"anti_pattern"`): ruled OUT OF
  SCOPE for this mission — noted in IC-01's Risks as unreachable via `generate`'s default production
  path and unexercised by this mission's own fixtures, flagged for a follow-up rather than silently
  dropped.

## Round-6 ruling

Dated 2026-09-28, issued after review round 6 (fix round R4) against `reviews/plan-fresh-5.yaml`'s
three surviving findings (PLAN-FRESH5-001, -002, -003). Quoted verbatim, attributed to **the
operator**:

> "(1) PLAN-FRESH5-002 — Explicit carve-out + pin it: under total graph-load failure, ids reachable
> only via transitive closure are covered by the single loud `_graph/_load_failure` sentinel
> diagnostic — no per-id records and no fail-closed (consequence of the round-3 ruling not to
> reconstruct the closure). State this explicitly as a carve-out in I1 and I2; narrow spec.md
> FR-001's 'at any cardinality' wording and the Key Entities 'Activated reference id' definition to
> match (minimal edits, keep spec style); add a red-first fixture to the ATDD invariant table pinning
> it: transitive-only kind + graph-load failure → sentinel present, exit 0, deterministic across
> repeat runs. (2) PLAN-FRESH5-001 — repoint all three dangling 'WP-CORE reconciliation point 3's
> test requirement' citations to the ATDD-First Discipline invariant → red-first fixture table,
> matching IC-01 Risk (3)'s phrasing. (3) PLAN-FRESH5-003 — split contract item 3 into two entries
> with accurate detail templates: genuinely-None-repository kinds ('no repository for kind:
> <kind_prefix>') vs valid-but-untracked kinds with a real repository outside the six tracked kinds
> (a detail saying it is not one of the six DRG-backed kinds tracked for reference resolution);
> `cause` may stay 'unattributed_kind' for both. (4) FOLD IN the verify-4 residual (reversing round
> 5's out-of-scope ruling): `_raw_kind_repository`'s raw-service fallback becomes
> `getattr(doctrine_service, kind, None)` so it degrades to a reported miss rather than
> AttributeError, covered by a small red-first test; remove the 'flagged for a follow-up' wording —
> no follow-up issue. (5) Close-out: verify-only — no further fresh sweep this phase; residual
> mechanism risk is carried by the tasks squad, analyze, and the red-first tests."

### Disposition — how round 6 applied the ruling

- **Item (1)** (PLAN-FRESH5-002): implemented in plan.md's "WP-CORE reconciliation" → "Round-5
  restatement" subsection — I1 and I2 each gained an explicit "Carve-out (total graph-load failure)"
  paragraph stating that transitively-only-reachable ids are covered collectively, never
  individually, by the `_graph`/`_load_failure` sentinel, as a direct consequence of the round-3
  ruling. `spec.md`'s FR-001 requirements-table row (Functional Requirements) and the Key Entities
  "Activated reference id" bullet were each given a minimal, style-preserving carve-out clause
  cross-referencing Edge Cases/FR-001. The ATDD-First Discipline section's invariant → red-first
  fixture mapping table gained a new row, "I1/I2 carve-out (transitive-only-reachable id + total
  graph-load failure)", pinning the sentinel-present / exit-0 / deterministic-across-repeat-runs
  fixture.
- **Item (2)** (PLAN-FRESH5-001): implemented — the two Phasing & Sequencing step 3 (WP-CORE)
  citations and IC-01's Purpose-bullet citation were each repointed from "WP-CORE reconciliation
  point 3's test requirement" to "the ATDD-First Discipline section's invariant → red-first fixture
  mapping table" (with "WP-CORE reconciliation" point 3 kept alongside, for the design rationale),
  matching IC-01's Risk (3) bullet's existing correct phrasing.
- **Item (3)** (PLAN-FRESH5-003): implemented in `contracts/charter-generate-json-diagnostics.md`'s
  "Round-5 addition" section — the merged item 3 was split into item 3 (genuinely-`None`-repository
  kinds: `template`/`asset`/`anti_pattern`, detail "no repository for kind: <kind_prefix>") and a new
  item 4 (valid-but-untracked kinds with a real, non-`None` repository outside the six tracked kinds:
  `paradigm`/`mission_step_contract`/`glossary_pack`, detail "kind '<kind_prefix>' is not one of the
  six DRG-backed kinds tracked for reference resolution"); both keep `cause: "unattributed_kind"`.
  plan.md's I3 row in the ATDD fixture table and the "Binding mechanism decisions retained" I3 bullet
  were updated from "three unattributable classes"/"valid-but-untracked or no-repository kind" (one
  merged case) to four classes, matching the contract doc's new item count.
- **Item (4)** (verify-4 residual fold-in, reverses round 5's out-of-scope ruling): implemented —
  plan.md's IC-01 "Affected surfaces" bullet now names `_raw_kind_repository`'s fallback-branch
  change (`compiler.py:1093`, `getattr(doctrine_service, kind)` → `getattr(doctrine_service, kind,
  None)`); the former "Residual ... ruled OUT OF SCOPE" bullet was rewritten to "FOLDED IN this
  round", states the fix is landing in this mission (not deferred), and the "flagged for a follow-up"
  wording was removed (no other occurrence of that phrase existed in plan.md, spec.md, or the
  contract doc). The ATDD-First Discipline fixture table gained a dedicated row,
  "`_raw_kind_repository` raw-service degrade", pinning the pre-fix `AttributeError` / post-fix
  `None`-degrade red-first test.
- **Item (5)** (close-out, verify-only): this round made no further fresh-sweep findings of its own —
  it is a direct, targeted remediation of `reviews/plan-fresh-5.yaml`'s three surviving findings plus
  the operator-directed reversal of the verify-4 residual's disposition. No new adversarial round was
  run against the resulting text this round, per the operator's own instruction that residual
  mechanism risk is carried forward to the tasks squad, analyze, and the red-first tests themselves.

## Round-7 ruling

Dated 2026-09-28, issued for the round-7 consistency pass (fresh-sweep verifier finding
PLAN-FRESH5-006 against `reviews/plan-verify-6.yaml`). Quoted verbatim, attributed to **the
operator**:

> "Consistency pass, verify, close. A fresh fixer applies the round-6 graph-load carve-out (under
> total graph-load failure, ids reachable only via transitive closure are covered by the single
> loud `_graph/_load_failure` sentinel — no per-id record, no fail-closed) to EVERY
> absolute-coverage claim in spec.md and plan.md — SC-001, the Key Entities 'CharterReference'
> bullet, the 'all activated references of a kind … unresolvable (misconfigured pack root)' Edge
> Case, and any other 'every activated id' / 'never silently' / 'at any cardinality' / 'must never
> vanish' sentence found by a systematic grep, not only the two named. No new mechanism, no new
> requirements. A fresh verifier confirms no absolute-coverage claim remains without the carve-out.
> On pass, commit the whole trail; on fail, report without starting another round."

### Disposition

A systematic grep (case-insensitive) of `spec.md`, `plan.md`, and `contracts/charter-generate-json-diagnostics.md`
for `every activated`, `never silent`, `silently`, `any cardinality`, `never vanish`, `must never`,
`all activated`, `exhaustive`, and the near-variants `no trace`, `vacuous`, `omission`, `dropped`,
`accounted for`, `coherent` turned up 20 distinct hits. Full hit-by-hit list with dispositions
(carve-out applied / not-a-claim-and-why) is recorded in `tracer-design-decisions.md`'s new dated
entry, "Decision: round 7 — apply the round-6 graph-load carve-out to every remaining
absolute-coverage claim (closes PLAN-FRESH5-006)".

Three genuine absolute-coverage claims were found still lacking the round-6 carve-out and were fixed,
all three named explicitly in the operator's ruling:

- **SC-001** (spec.md, Measurable Outcomes) — gained: "except for ids reachable only via DRG-transitive
  closure when the whole DRG graph fails to load, which are covered collectively — never individually —
  by the single loud `_graph`/`_load_failure` sentinel diagnostic (see Edge Cases; FR-001)."
- **Key Entities "CharterReference" bullet** (spec.md) — gained: "except for an id reachable only via
  DRG-transitive closure when the whole DRG graph fails to load, which is covered collectively with
  other such ids — never individually as a `CharterReference` — by the single loud `_graph`/
  `_load_failure` sentinel diagnostic (see Edge Cases; FR-001)."
- **Edge Case "All activated references of a kind... are unresolvable"** (spec.md, the
  misconfigured-pack-root case) — gained: "except for a kind whose activated ids are reachable only via
  DRG-transitive closure when the whole DRG graph fails to load, which is covered collectively — never
  individually or via fail-closed exit — by the single loud `_graph`/`_load_failure` sentinel diagnostic
  (see FR-001)."

All three edits reuse FR-001's own already-committed carve-out clause verbatim (or a minimally
grammar-adapted form of it), rather than inventing a fourth distinct wording, so the doctrine now
reads as one consistent carve-out across all five spec.md sites that state it (FR-001, the "Activated
reference id" bullet, and these three) plus plan.md's I1/I2.

Every other grep hit — in both spec.md and plan.md, and the one contracts-doc hit — was determined,
per-hit, to be either (a) already carved in round 6 (FR-001's table cell, the "Activated reference id"
bullet, I1, I2 — re-verified intact, not re-edited) or (b) not an absolute-coverage claim the
graph-load carve-out implicates at all: several are scoped explicitly to the `SCOPE_FILTERED` cause
only (which has no graph-load-failure exception of its own — spec.md AS4/SC-005, the WP-ATDD/FR-005
fixture assertions, plan.md's Charter-Check seam description and IC-01 Purpose), several describe a
different, non-overlapping mechanism (the contract doc's Round-5 addition, which presupposes the DRG
graph loaded successfully), and the remainder are historical/narrative/purpose prose (mission history,
gate-applicability notes, a classification-correctness risk, a test's own not-vacuous assertion) that
make no per-id/per-kind completeness guarantee in the first place. No new mechanism, no new
requirement, and no FR/NFR/SC was added — every edit narrows/qualifies existing absolute wording to
match the already-ruled invariant. Re-read spec.md, plan.md, and the contracts doc in full after
editing: no absolute-coverage claim survives that contradicts the round-6 carve-out, and no edit
contradicts any standing round 3–6 ruling above.
