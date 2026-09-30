# Tracer: Design Decisions

Mission: `charter-generation-drops-scoped-references-01M3M1KF` (#5257)

## Decision: fold in the preflight auto-refresh fail-closed swallow (bounded)

**Context.** Spec.md's Edge Cases "Mid-flight missions" bullet identifies a confirmed fact (verified
against the actual current code during this planning phase, not taken on faith from the dispatch
prompt): `src/specify_cli/charter_runtime/preflight/references_refresh.py::refresh_references_if_needed`
spawns the targeted `generate` subprocess via `subprocess.run(cmd, cwd=repo_root,
capture_output=True, text=True, timeout=..., check=False)` (line 175), discards the returned
`CompletedProcess` without binding it to a name, catches only `(OSError, subprocess.TimeoutExpired)`
at debug-log level (lines 183–188), never inspects `.returncode`, and **unconditionally
`return`s `True`** (line 189) regardless of the subprocess's actual outcome. Its one caller,
`_attempt_auto_refresh` in `runner.py` (~line 733), treats that `True` as "an attempt was made" with
no success/failure information, and unconditionally re-runs `spec-kitty charter synthesize` (lines
749–759, flagless, `SynthesizeMode.preserve`) to re-stamp the synthesis manifest's
`bundle_content_hash` against `charter.yaml`'s CURRENT content — then recomputes freshness (lines
763–765) and reports `passed=post_passed`.

**The concrete hazard.** Per the module's own "post-#2759 retirement" docstring note,
`synthesized_drg` staleness is fundamentally "does the manifest's stored hash match a hash of
charter.yaml's CURRENT content" — so re-stamping over a `charter.yaml` that `generate` FAILED to
actually reconcile (for ANY reason: a crash, a lock conflict, a schema error, disk pressure — not
only this mission's specific scoped-reference defect class) makes the post-refresh recompute report
`synthesized_drg="fresh"` even though the underlying references-parity condition was never resolved.
This is the class this repo's charter names as its dominant failure mode: silent success. It is a
**pre-existing defect this mission's own investigation surfaced**, independent of whether this
mission's own FR-001 fix (placeholder-always, see tracer-approach.md) ever itself triggers a
fail-closed `generate` exit — which, per that design choice, it mostly should not need to for THIS
defect class, but the swallow remains reachable for any other `generate` failure mode at that call
site.

**Operator doctrine applied (not re-litigated):** prefer folding in a bounded, same-defect-class fix
over deferring to a follow-up issue, because a silently-swallowed fail-closed exit is itself a
silent-success violation of this mission's own acceptance bar (FR-001, NFR-002). Fold it in IF
bounded: one call site, testable red-first, no contract change to `CharterPreflightResult`/
`contracts/charter-preflight-json.md` beyond what already exists.

**Decision: FOLD IN**, with the following bounded design — verified sound against the actual code
(not restated from the dispatch prompt without checking):

1. Widen `references_refresh.refresh_references_if_needed`'s return contract from `bool` to a small
   frozen outcome type (`RefreshOutcome(attempted: bool, succeeded: bool, detail: str | None)`),
   where `succeeded` reflects the now-bound `completed.returncode == 0` and `detail` is a short
   excerpt of stderr/stdout on failure. Confined to this one module and its one in-repo caller
   (`runner.py`'s wrapper at ~line 553 and `_attempt_auto_refresh` at ~line 733) — not a change to
   any public/documented contract.
2. In `_attempt_auto_refresh`: when `attempted and not succeeded`, return
   `CharterPreflightResult(passed=False, checks=initial_checks, auto_refresh_applied=True,
   auto_refresh_actions=actions, blocked_reason=f"references-parity refresh failed: {detail}")`
   immediately, **skipping the manifest-restamp step entirely** — restamping over un-regenerated
   content is precisely the masking mechanism being removed. `blocked_reason` is an existing field
   (`result.py` line 98) already populated with `auto_refresh_applied=True` at multiple other branches
   in the same function (lines 686–692, 704–709) — this fold-in makes the references-parity step
   consistent with every OTHER step in the same sequence, which already surfaces its own failures
   this way, rather than adding a new mechanism.
3. Red-first test: monkeypatch/mock the `generate` subprocess to return non-zero inside the
   auto-refresh path. Assert (a) BEFORE the fix, the failure never reaches an actionable
   `blocked_reason` (RED, proving the bug is real on `af847be71`); (b) AFTER the fix, `passed=False`
   and `blocked_reason` names the failure (GREEN).

**Why this is "bounded", not a HALT-for-operator case:** one call site, one function's return-type
widening confined to a module and its single caller, testable red-first in isolation, no contract
change beyond reusing an already-existing field in an already-established pattern within the same
function, no reach outside the two named preflight files. See plan.md's own "Auto-refresh
fail-closed swallow — decision: FOLD IN (bounded)" section for the full verification trail.

## Decision: WP-CORE's placeholder path is scoped to `SCOPE_FILTERED` only — Contract C4 stands, not superseded

**Context (post-plan-review finding PLAN-GOV-001).** The plan-phase adversarial squad found that
WP-CORE's original design — "ALWAYS preserves the id as a placeholder `CharterReference` ...
uniformly regardless of cardinality/cause, never a second fail-closed exit branch" — silently
reverses **Contract C4** ("Recompiled catalog is complete and stable",
`kitty-specs/charter-catalog-coherence-01M2XQQF/contracts/behavior-contracts.md`, issue #4785, a
prior COMPLETED mission). Contract C4 requires: "Given a directive id with genuinely no bundled
definition, Then it surfaces through the `graph.unresolved` diagnostics channel, not as a silent
placeholder `catalog.references` row." This is pinned today by a real, currently-green test —
`tests/charter/test_render_kind_references_routes_genuine_miss_to_diagnostics_not_placeholder`
(`tests/charter/test_catalog_completeness_4785.py:191-216`) — which asserts `references == []`
(never a placeholder row) and the exact diagnostics string for a genuine, never-existed miss
against `_render_kind_references` (`src/charter/activation/compiler.py:1096`), the EXACT function
WP-CORE rewrites. Verified live: `.venv/bin/python -m pytest -q
tests/charter/test_catalog_completeness_4785.py` is 5 passed on this branch today. Under the
original always-placeholder design, both of that test's assertions go red the moment WP-CORE lands.

**Decision: option (b) — narrow WP-CORE's placeholder path to the `SCOPE_FILTERED` cause only.**
Contract C4 is NOT superseded; it stands as written and its pinning test is NOT modified. The
narrower design is:

- When `_render_kind_references`'s raw-repository lookup misses for `raw_id`, first check
  `raw_id in repository.scope_filtered_ids` (`BaseDoctrineRepository.scope_filtered_ids`,
  `src/charter/offering/base.py`). If **true** (the artifact exists on disk, present but excluded
  by language/scope — this mission's actual #5257/#5253 defect class), classify via
  `classify_scope_filtered_miss` (`CatalogMissCause.SCOPE_FILTERED`) and preserve the id as a
  reason-bearing placeholder `CharterReference` — uniformly regardless of *cardinality* within this
  cause (one scope-filtered id or every scope-filtered id of a kind, per Acceptance Scenario 4 /
  SC-005, is handled by the same code path).
- If **false** (the artifact genuinely has no bundled definition anywhere — `MISSING_ARTIFACT` or
  `TYPO_SUSPECTED` via `classify_catalog_miss`), stay on the EXISTING Contract-C4-compatible
  diagnostics-only path: no placeholder row, `references` stays `[]` for that id, and a
  reason-bearing diagnostic string is appended (FR-002/NFR-002 apply to this path too — the
  diagnostic text gains the `(cause): detail` suffix exactly like the scope-filtered path's
  diagnostic does; only the placeholder-row *mechanism* is withheld, not the reason-classification
  improvement).

**Why (b), not (a) [explicit supersession of Contract C4]:**

1. **Correctly scoped to the actual defect.** #5257/#5253's defect is specifically that a
   *present-on-disk, scope-filtered* id was being silently dropped as if it never existed. Genuinely
   nonexistent ids were never the defect — Contract C4's diagnostics-only behavior for that case is
   already correct, already tested, and already a "loud report" (FR-001's title is "Preserve **or**
   loudly report" — a reason-bearing diagnostics-list entry, which is what Contract C4 already
   produces and what FR-002 makes reason-bearing, satisfies the disjunctive "loudly report" branch;
   it does not need to also become a placeholder row to satisfy FR-001).
2. **DIRECTIVE_044 (single canonical authority) favors reconciliation over silent supersession.**
   Contract C4 is a real, prior-mission, currently-tested authority on this exact function. Option
   (a) would require editing both `test_catalog_completeness_4785.py`'s assertions AND
   `behavior-contracts.md`'s Contract C4 text in the same commit with a rationale note — a real,
   defensible path, but a heavier one that touches a settled prior mission's contract to fix a
   narrower, unrelated defect. Option (b) reconciles by *scoping* the new mechanism precisely to
   where it is needed, leaving the existing authority untouched and still correct.
3. **Smallest-viable-diff (charter's change-scope reconciliation order).** Narrowing to
   `SCOPE_FILTERED` is the minimal edit that closes the actual defect; it does not require touching
   a second mission's contract doc or a currently-green regression test outside this mission's
   stated blast radius.
4. **No conflict with SC-005 / Acceptance Scenario 4.** That scenario's fixture ("every activated
   `toolguide` id excluded by language scope") is, by construction, a `SCOPE_FILTERED` case — it is
   fully satisfied by the narrowed placeholder path with no special aggregate-cardinality handling
   needed (same reasoning tracer-approach.md's "Rejected alternative" section already gives for why
   always-placeholder-within-a-cause needs no cardinality branch).

**Consequence for the plan:** `tests/charter/test_catalog_completeness_4785.py` is added to
WP-CORE's stated blast-radius test command (it is NOT modified, but it now sits directly in the
diff's path and must be run to prove Contract C4 still holds after WP-CORE lands). Verified today,
with the file included: `.venv/bin/python -m pytest -q tests/doctrine/test_activation_parity_guard.py
tests/charter/test_active_languages_idempotency.py tests/charter/test_context_catalog_miss.py
tests/charter/test_catalog_completeness_4785.py` → **56 passed, 0 failed, 1 warning (75.20s)**
(the prior 51-test baseline plus this file's 5 tests). WP-CORE's own green-bar re-check must use
this 56-test command, not the original 51-test one, so a future regression against Contract C4 is
actually caught rather than silently missed by an incomplete shard list.

## Decision: SCOPE_FILTERED placeholder summary text — extend the existing baseline string, don't replace it

**Context (post-plan-review finding PLAN-ARCH-001).** NFR-002 requires every placeholder entry to
name a reason category. The CURRENT committed convention for an unresolvable id's placeholder
summary — set by `_doctrine_yaml_reference`'s fallback (`src/charter/activation/compiler.py:1505`:
`{"summary": "Definition unavailable in bundled doctrine."}`) — is the literal string
`"Definition unavailable in bundled doctrine."` with no reason category, verified against this
repo's own committed `.kittify/charter/charter.yaml` (nine rows carry this exact string today,
e.g. lines 962, 1250, 1346, 1460, 1496, 1514, 1670, 1694, 1712). Spec.md's Edge Case says a repo
already carrying this baseline "must not further diverge from" the existing placeholder convention
on regeneration. Making the new `SCOPE_FILTERED` placeholder (see the decision above — WP-CORE's
placeholder path only builds a placeholder row for the `SCOPE_FILTERED` cause) satisfy NFR-002
therefore has to change this text somehow, which is in tension with "must not diverge" unless the
change is framed as an extension.

**Decision: option (a) — extend, don't replace.** The new `SCOPE_FILTERED` placeholder's `summary`
keeps `"Definition unavailable in bundled doctrine."` as a stable, byte-identical PREFIX and appends
a reason-bearing suffix built from `classify_scope_filtered_miss`'s own suggestion text:

```
Definition unavailable in bundled doctrine. Reason: scope_filtered — <classify_scope_filtered_miss suggestion text>
```

This satisfies NFR-002 (the reason category `scope_filtered` and the specific detail are named) and
the Edge Case (the existing literal string is preserved verbatim as a prefix — a repo regenerating
today's baseline sees its existing text extended, never discarded or reworded). This is an
extension, not a replacement, of the existing convention — the same "template, not direct reuse"
relationship tracer-approach.md's "Overall approach" section already describes between
`_doctrine_yaml_reference` (paradigm placeholders, YAML-dict sourced) and the new DRG-backed-kind
placeholder path (typed-repository sourced): the new path borrows the *prefix convention*, not the
function itself. WP-CORE adds one concrete test (fixture: a still-unresolvable `SCOPE_FILTERED` id
regenerated from a repo seeded with today's exact baseline row shape) asserting the post-fix
`summary` matches this prefix+suffix format exactly — see plan.md's IC-01/WP-CORE text for the test
placement.

## Decision: add an aggregate, cause-agnostic whole-kind-unresolved fail-closed check (round-2 fix, closes PLAN-FRESH-001)

**Context (post-plan-fresh-review finding PLAN-FRESH-001, second adversarial round after the
decision above landed).** A fresh-eyes review of the fix that produced the "SCOPE_FILTERED-only"
narrowing (the decision immediately above) found that it reopened a different gap: FR-001's own
text and its matching Edge Case bullet give "a misconfigured pack root" — a MISSING_ARTIFACT-class
cause, NOT SCOPE_FILTERED — as an illustrative *whole-kind-unresolvable* scenario, and state that
only two mechanisms satisfy FR-001 "at any cardinality": placeholder-preservation of every affected
id, OR a fail-closed non-zero exit naming the kind. The SCOPE_FILTERED-only narrowing gives a
whole-kind MISSING_ARTIFACT/TYPO_SUSPECTED miss NEITHER: no placeholder row (by design, per the
decision above) and no fail-closed exit (`charter generate` still exits 0 and writes a structurally
valid but silently-empty-for-that-kind catalog section). Verified against spec.md directly during
this fix round (not taken on faith from the finding): FR-001's Functional Requirements table row and
the Edge Cases "All activated references of a kind... are unresolvable" bullet both state this
two-mechanism, any-cardinality bar in the spec's own words, and neither SC-005 nor Acceptance
Scenario 4 (User Story 1) exercises the MISSING_ARTIFACT/whole-kind combination — both are
SCOPE_FILTERED-only fixtures ("every activated toolguide id excluded by language scope"). So an
implementation built exactly to the pre-round-2 plan text would silently fail FR-001 for the
genuinely-missing whole-kind case, and nothing in the described test suite would catch it.

**Decision: add a second, independent mechanism — a per-kind aggregate check — rather than widening
the per-id placeholder scoping back out.** After `_render_kind_references` classifies every id of a
kind (the decision above's per-id SCOPE_FILTERED vs. MISSING_ARTIFACT/TYPO_SUSPECTED routing,
unchanged), `_build_references_from_service` checks, per kind: did this kind have at least one
activated id, AND did none of them produce a reference (no resolution, no SCOPE_FILTERED
placeholder)? If both hold, every one of that kind's activated ids fell through to the
diagnostics-only branch — the exact "misconfigured pack root" / whole-kind-genuinely-missing case
FR-001 names. When this holds for one or more kinds, `_build_references_from_service` raises a
fail-closed error (a private `RuntimeError` subclass) naming the affected kind(s) and their
unresolved ids, propagating up through `_build_references` → `compile_charter` so `generate.py`'s
existing broad `RuntimeError` handler (`generate.py:584`) exits non-zero **before**
`write_compiled_charter` (`generate.py:497`, called strictly after `compile_charter` at line 489)
ever runs — so no catalog is written for this case, matching FR-001's "exits non-zero before writing
any catalog" language. Full design (call-site details, the exact emptiness check, and the new test
requirement): plan.md's "WP-CORE reconciliation" section, point 3.

**Why this does not reopen the SCOPE_FILTERED decision above, and does not reintroduce C-002.**
This is a genuinely different axis from the decision above, not a widening of it:

1. **Different trigger, different mechanism.** The decision above governs whether a SCOPE_FILTERED
   miss gets a placeholder row (a per-id question, answered per the cause). This decision governs
   whether an entire KIND's activated-id set is left with zero catalog presence after all per-id
   classification completes (a per-kind aggregate question, answered by counting). A kind with even
   one SCOPE_FILTERED id mixed in never trips this new check — that id already produced a
   placeholder row under the decision above, so the kind's reference list is non-empty. The two
   decisions compose without conflict: the SCOPE_FILTERED-only narrowing still stands exactly as
   written; this decision only adds behavior for the case it never covered (a kind where literally
   every activated id is genuinely missing).
2. **A count comparison, not an id comparison — this is the C-002 distinction that matters.** C-002
   forbids special-casing the six literal id strings from #5257
   (`styleguide/java-conventions`, `toolguide/maven-review-checks`, `toolguide/typescript-mutation-tools`,
   `agent-profile/frontend-freddy`, `agent-profile/java-jenny`, `agent-profile/node-norris`) anywhere
   in the fix. This check never reads or compares against any literal id string at all — it compares
   two counts per kind (activated-id count vs. diagnostics-only-miss count for that kind), computed
   identically for every kind, on every repo, regardless of which ids are involved. "Check whether
   every id of a kind is unresolved" is a cardinality gate over an arbitrary kind's arbitrary id set;
   it is not the same shape of special-casing C-002 forbids, and tracer-approach.md's "Rejected
   alternative" section (which argues against a *per-id, cardinality-conditioned* fail-closed branch
   for SCOPE_FILTERED specifically) is not in tension with this decision — that section's objection
   was to branching WHEN a single mechanism applies based on how many ids are affected; this decision
   instead adds FR-001's own second, already-named mechanism (fail-closed exit) for a case the first
   mechanism (placeholder) was deliberately scoped never to cover.
3. **No new test-suite conflict.** `tests/charter/test_catalog_completeness_4785.py` (Contract C4)
   pins a SINGLE genuinely-missing id producing `references == []` with no placeholder row and no
   fail-closed exit for that single-id case — this check only fires when an entire KIND's ids are
   ALL genuinely missing, a materially different (and, per that test's own fixture, untested)
   cardinality; Contract C4's fixture is not a whole-kind case, so it is unaffected. WP-CORE's new
   test (plan.md, "WP-CORE reconciliation" point 3) covers the whole-kind case directly, closing the
   gap PLAN-FRESH-001 identified: SC-005/Acceptance Scenario 4 and this new test together now cover
   both whole-kind-unresolvable causes (SCOPE_FILTERED via the existing placeholder path, and
   MISSING_ARTIFACT/TYPO_SUSPECTED via this new fail-closed path).

## Decision: operator ruling on PLAN-FRESH2-001 — widen the whole-kind check to `graph.unresolved`, and make graph-load failure loud+structured (not fail-closed)

**Context (round 3 of the plan-phase adversarial squad, `reviews/plan-fresh-2.yaml`, finding
`PLAN-FRESH2-001`, severity 4).** A further fresh-eyes review of the decision immediately above
(the per-kind aggregate whole-kind check) found it inspects only the per-kind list
`_render_kind_references` returns. Two verified-in-code gaps fall entirely outside its field of
view: (1) `_build_references_from_service`'s OWN separate `graph.unresolved` loop
(`compiler.py:1250-1251`) — populated by `resolve_transitive_refs`
(`charter/offering/drg/query.py`) when a visited URN's DRG node is absent from an
otherwise-successfully-loaded graph — never reaches `_render_kind_references` and so never
contributes to the aggregate check; (2) `_resolve_transitive_reference_graph`'s
`except Exception: return fallback` branch (`compiler.py:1298-1307`), hit when the WHOLE DRG graph
fails to load, drops anything reachable only via directive-transitive closure with zero trace —
not even a diagnostic. This also left the "Campsite-clean scope" section's claim ("both call sites
end up calling one new shared classify-and-placeholder helper") false as written, since the
`graph.unresolved` site was never mentioned in the WP-CORE reconciliation design.

**The operator ruled on this finding directly (binding — replaces the finding's own remediation
options (a)/(b)):**

> "Widen, bounded: route `graph.unresolved` ids through the same classify-and-placeholder helper
> so they count toward the whole-kind fail-closed check and get a reason; graph-load failure emits
> a loud, structured diagnostic (also in `--json`) instead of vanishing, without attempting to
> reconstruct the transitive closure. Stays in compiler.py, same defect class, keeps the plan's
> 'one shared helper' campsite claim true."

**Explicit constraint from the operator:** graph-load failure does **NOT** make `generate` fail
closed (the operator explicitly declined the stricter option) — it must be loud and structured,
not fail-closed. This is a deliberate, bounded widening, not a reopening of decision 1 above (the
`SCOPE_FILTERED`-only placeholder scoping) or a general "make everything fail closed" reversal.

**Decision: implement exactly this ruling, nothing broader.**

1. Route `_build_references_from_service`'s `graph.unresolved` loop through the SAME
   classify-and-placeholder helper decision 3's per-kind loop already uses, so both unresolved-
   tracking sites genuinely share one helper (making the Campsite-clean section's claim true).
   **Correction (round 4, closes PLAN-FRESH3-001 — the same root cause PLAN-FRESH2-001 above
   named, filed again against a fresh-eyes pass of the resulting text):** each `graph.unresolved`
   entry is a `(urn, urn)` tuple — both elements the SAME full `"kind:id"` URN string
   (`src/charter/offering/drg/query.py:391`), never a bare `(kind, id)` pair. Routing it through
   the shared helper first requires splitting the URN (`urn.split(":", 1)`, matching
   `resolve_transitive_refs`'s own successful-lookup branch, `query.py:394`) and mapping the
   singular kind to the plural repository key via the existing `ArtifactKind(kind_str).plural`
   mapping (`src/charter/offering/artifact_kinds.py:125-148`/`51-64`) — guarding against a
   URN with no `":"`, a kind string with no `ArtifactKind` member, and a valid `ArtifactKind`
   whose repository resolves to `None` (all three preserved/reported, never crashed). The
   implementable design (all three guarded cases) is in plan.md's "Round-3 amendment", Design
   part (a).
2. Because `graph.unresolved` ids now flow into the same per-kind `references` list
   `_render_kind_references` populates, the existing aggregate whole-kind check (decision 3, above)
   automatically counts them — no separate counting logic needed. (Bounded to the ids point 1's
   correction can actually attribute to one of the six tracked kinds — see plan.md's Design
   part (b) for the same "no attribution, no aggregate count" exemption point 3 below already
   applies to graph-load failure.)
3. A total graph-load failure (`_resolve_transitive_reference_graph`'s `except Exception` branch)
   gets ONE unconditional, structured diagnostic — present in both the plain `diagnostics: list[str]`
   and the `--json` `unresolved_references` field — instead of vanishing. It does NOT attempt to
   reconstruct the transitive closure (the existing fallback's direct-root-only behavior is
   unchanged) and does NOT trip the whole-kind aggregate fail-closed check: that check counts
   per-kind ids that were actually classified (`SCOPE_FILTERED` vs. `MISSING_ARTIFACT`/
   `TYPO_SUSPECTED`, each attributable to one kind); a total graph-load failure has no per-kind
   breakdown to classify, so it gets its own unconditional loud diagnostic instead of being folded
   into a count it cannot honestly populate. **Correction (round 4, closes PLAN-FRESH3-002):** this
   diagnostic is appended INSIDE `_resolve_transitive_reference_graph`'s own `except` branch, via
   `diagnostics`/structured-records sink parameters passed into it by its caller — not by widening
   its return type and not via a marker exception (both explicitly declined by the operator); see
   plan.md's Design part (c). Its `cause` value (`"graph_load_failed"`) is a plain `str`, never the
   `CatalogMissCause` enum type, so `_catalog_miss.py` stays unmodified (closes PLAN-FRESH3-004).

Full design (the exact helper call sites, the diagnostic message shape, the `--json` entry shape,
and the extended test requirement) lives in plan.md's "WP-CORE reconciliation" point 3, "Round-3
amendment" subsection, and in `contracts/charter-generate-json-diagnostics.md`'s "Round-3 addition"
section — this tracer entry records the ruling and the reasoning; those files record the
implementable design. This also closes PLAN-FRESH2-004 (idempotency): the whole-kind aggregate
check's fail-closed branch (now widened to include `graph.unresolved`) writes no catalog on either
invocation, so NFR-001's literal byte-identical-catalog guarantee does not apply to it — the
relevant property is that the same unresolved-kind repo fails the same way (same exit code, same
kind named) on a second invocation, with any pre-existing catalog left untouched. The graph-load-
failure diagnostic path (not fail-closed, still writes a catalog) remains subject to ordinary
NFR-001 unchanged.

**Note (round 4):** the "Round-3 amendment" subsection this decision cites was, in round 5, replaced
(not appended to) by an invariant restatement — see the decision entry below. This entry's ruling
and reasoning still stand; only the location of the implementable design text changed.

## Decision: operator ruling round 6 — I1/I2 graph-load-failure carve-out, citation repoints, contract-item split, and fold-in of the verify-4 residual

**Context.** `reviews/plan-fresh-5.yaml` (the fifth fresh-eyes adversarial round) found three surviving
findings against the round-5 invariant restatement: PLAN-FRESH5-002 (severity 4) — I1/I2 do not
account for ids reachable only via DRG-transitive closure when the whole graph fails to load, an
internal inconsistency with I4's own retained graph-load-failure mechanism; PLAN-FRESH5-001
(severity 3) — three citations to "WP-CORE reconciliation point 3's test requirement" point at a
subsection round 5 deleted; PLAN-FRESH5-003 (severity 3) — the contract doc's round-5 item 3 gives a
factually inaccurate "no repository for kind" detail for kinds (`paradigm`, `mission_step_contract`,
`glossary_pack`) that DO have a repository. Separately, the operator directed a reversal of round 5's
disposition on the `reviews/plan-verify-4.yaml` residual (`_raw_kind_repository`'s `getattr` fallback
raising `AttributeError` instead of degrading to `None`), which round 5 had ruled out of scope with a
"flagged for a follow-up" note.

**Operator ruling (round 6, quoted in full in `reviews/plan.ruling.md`'s "Round-6 ruling" section):**
apply all three PLAN-FRESH5 remedies, AND fold in the verify-4 residual as an in-mission fix rather
than a deferred follow-up.

**Decision: implement exactly this ruling.**

1. **PLAN-FRESH5-002 (I1/I2 carve-out).** plan.md's "WP-CORE reconciliation" → "Round-5 restatement"
   subsection: I1 gained an explicit "Carve-out (total graph-load failure)" paragraph stating that
   ids reachable ONLY via DRG-transitive closure are covered collectively — never individually — by
   the single `_graph`/`_load_failure` sentinel diagnostic when the whole graph fails to load, framed
   as a direct, explicit consequence of the round-3 ruling declining to reconstruct the transitive
   closure (this file's "operator ruling on PLAN-FRESH2-001" entry, above). I2 gained the matching
   restatement for its OR condition: under total graph-load failure, `graph.unresolved` is never
   populated and `graph.<kind>` reflects only direct config roots, so a kind whose ids are ALL
   transitively-reachable never satisfies I2's OR condition in that failure mode — by design, not by
   omission. `spec.md`'s FR-001 requirements-table cell and the Key Entities "Activated reference id"
   bullet each gained a minimal, style-preserving carve-out clause. The ATDD-First Discipline
   invariant → red-first fixture table gained one new row pinning the transitive-only-reachable-id +
   total-graph-load-failure fixture: sentinel present, `generate` exits 0, deterministic across repeat
   invocations.
2. **PLAN-FRESH5-001 (dangling citations).** The two Phasing & Sequencing step 3 (WP-CORE) citations
   and IC-01's Purpose-bullet citation, all three previously reading "see 'WP-CORE reconciliation'
   point 3... for the test requirement" (a subsection round 5's invariant restatement had already
   replaced), were repointed to "the ATDD-First Discipline section's invariant → red-first fixture
   mapping table" (keeping "WP-CORE reconciliation" point 3 alongside, for the design rationale) —
   matching the phrasing IC-01's own Risk (3) bullet already used correctly.
3. **PLAN-FRESH5-003 (contract item split).** `contracts/charter-generate-json-diagnostics.md`'s
   "Round-5 addition" section: the merged item 3 (which claimed "no repository for kind: <kind_prefix>"
   for both genuinely-`None`-repository kinds AND valid-but-untracked kinds with a real repository)
   was split into item 3 (genuinely-`None`-repository kinds only: `template`/`asset`/`anti_pattern`)
   and a new item 4 (valid-but-untracked kinds with a real, non-`None` repository outside the six
   tracked kinds: `paradigm`/`mission_step_contract`/`glossary_pack`), with item 4's detail text
   corrected to "kind '<kind_prefix>' is not one of the six DRG-backed kinds tracked for reference
   resolution" instead of the factually wrong "no repository" claim. Both items keep the shared
   `cause: "unattributed_kind"` value, per the operator's explicit allowance. plan.md's I3 fixture-table
   row and the "Binding mechanism decisions retained" I3 bullet were updated from three to four
   unattributable classes to match.
4. **Fold in the verify-4 residual (reverses round 5's out-of-scope ruling).** plan.md's IC-01
   "Affected surfaces" bullet now names `_raw_kind_repository`'s fallback-branch change
   (`compiler.py:1093`: `return getattr(doctrine_service, kind)` → `getattr(doctrine_service, kind,
   None)`) as part of this mission's implementation scope, not a deferred item. The former "Residual
   ... ruled OUT OF SCOPE ... flagged for a follow-up" bullet was rewritten to "FOLDED IN this round"
   — it states the fix lands in this mission, and the "flagged for a follow-up" wording was removed
   (verified: no other occurrence of that phrase existed anywhere in plan.md, spec.md, or the contract
   doc before this round). The ATDD-First Discipline fixture table gained a dedicated row for this
   fix's own small red-first test (pre-fix `AttributeError`, post-fix `None`-degrade).

**Why this does not reopen any standing round-3/round-4/round-5 ruling.** The I1/I2 carve-out states
an explicit consequence of the round-3 "graph-load failure does not fail closed, does not reconstruct
the closure" ruling — it does not change that ruling, only makes a gap in its own restatement (I1/I2)
visible and pinned. The citation repoints and contract-item split are wording/documentation-accuracy
fixes with no behavioral change. The verify-4 fold-in is the one substantive reversal, and it is
explicit, operator-directed, and scoped exactly as the fold-in bar the auto-refresh decision (above)
already established: one call site, one one-line fallback-default change, testable red-first in
isolation, no contract change.

## Decision: operator ruling on round-5 invariant restatement (closes PLAN-FRESH4-001..004)

**Context.** Four rounds of adversarial review (`reviews/plan-fresh-2.yaml` through
`reviews/plan-fresh-4.yaml`) kept finding real defects in decision 3's line-level mechanism prose
(this file's "operator ruling on PLAN-FRESH2-001" entry above, and its implementable design in
plan.md's former "Round-3 amendment to point 3" subsection) — not in the underlying idea, but in how
the mechanism was *described*: PLAN-FRESH4-001 found the activation-detection input (does
`graph.<kind>` alone gate whether a kind counts as "activated"?) conflated with the check's separate
output-emptiness condition; PLAN-FRESH4-002 found three mutually contradictory statements of WHEN
the check runs; PLAN-FRESH4-003 found three `graph.unresolved` classes (malformed URN, unrecognized
kind prefix, valid-but-untracked kind) with no defined `kind`/`id` shape in the contract doc;
PLAN-FRESH4-004 found an arithmetic error in "PR Shape"'s own commit count ("six" vs. its own
five-item enumeration).

**Operator ruling (round 5, quoted in full in `reviews/plan.ruling.md`'s "Round-5 ruling" section):**
apply the four PLAN-FRESH4 remedies, AND restate decision 3 as five testable invariants (I1–I5)
rather than continuing to re-litigate mechanism-level prose. Each invariant maps to a named
red-first test fixture; remaining mechanism detail (exact call ordering, helper signatures, line
numbers) is explicitly deferred to the tasks squad and WP review, where red-first tests catch any
drift — this plan does not need to pin implementation mechanics the tests already pin.

**Decision: implement exactly this ruling.** plan.md's "WP-CORE reconciliation" point 3's original
"Design" paragraph and its "Round-3 amendment to point 3" subsection (the URN-parsing steps, the
exact call-order claims, the three overlapping "Test requirement" paragraphs) were REPLACED (not
appended to) by: (a) a short, one-paragraph restatement of why decision 1's `SCOPE_FILTERED`-only
placeholder scoping reopens the whole-kind gap (kept, still needed context); (b) the five invariants
I1–I5, stated exactly as the operator ruling, each self-contained and testable; (c) a short,
explicitly-labeled non-binding implementation sketch pointing at `_build_references_from_service`,
`_render_kind_references`, `_resolve_transitive_reference_graph`, and `compiler.py`, with no exact
line numbers or step-by-step URN-parsing recipe; (d) every CONCRETE operator ruling from prior
rounds kept intact and stated as binding, not demoted to sketch — the URN split/kind-mapping rule,
the diagnostics-sink-not-return-widening mechanism, `cause`'s plain-`str` typing, and I4's
not-fail-closed rule. The auto-refresh fold-in section was left untouched except for its
cross-references into this section. `contracts/charter-generate-json-diagnostics.md` gained a
"Round-5 addition" section defining the `kind`/`id`/`cause` shape for I3's three unattributable
`graph.unresolved` classes. The ATDD-First Discipline section gained an I1–I5 → red-first-fixture
table, consolidating the test-requirement paragraphs the deleted prose used to scatter across three
places; "Phasing & Sequencing" step 2 (WP-CORE-TESTS) and IC-01's Risks were updated to match. "PR
Shape"'s commit count was corrected from "six" to "five". Net effect: plan.md shrank from 633 to 428
lines despite these additions, because far more line-level mechanism prose was deleted than was
added back as invariants/sketch/table. See `reviews/plan.ruling.md`'s "Round-5 ruling" →
"Disposition" for the finding-by-finding closure record.

## Decision: round 7 — apply the round-6 graph-load carve-out to every remaining absolute-coverage claim (closes PLAN-FRESH5-006)

**Context.** `reviews/plan-verify-6.yaml` (the round-7 fresh-sweep verifier) found that round 6 applied
the graph-load carve-out (total graph-load failure → ids reachable only via transitive closure are
covered collectively, never individually, by the single loud `_graph`/`_load_failure` sentinel — no
per-id record, no fail-closed) to only two of spec.md's absolute-coverage sentences (FR-001's table
cell and the Key Entities "Activated reference id" bullet), leaving other "every activated" / "never
silently" / "must never" sentences uncarved, specifically SC-001 and the Key Entities "CharterReference"
bullet.

**Operator ruling (round 7, quoted in full in `reviews/plan.ruling.md`'s "Round-7 ruling" section):**
apply the carve-out to every absolute-coverage claim in spec.md and plan.md — SC-001, the "CharterReference"
bullet, the misconfigured-pack-root Edge Case, and any other hit a systematic grep turns up — no new
mechanism, no new requirements; a fresh verifier confirms none remain.

**Systematic grep** (case-insensitive) across `spec.md`, `plan.md`, `contracts/charter-generate-json-diagnostics.md`
for: `every activated`, `never silent`, `silently`, `any cardinality`, `never vanish`, `must never`,
`all activated`, `exhaustive`, plus near-variants `no trace`, `vacuous`, `omission`, `dropped`,
`accounted for`, `coherent`. Every hit and its disposition:

1. **spec.md:58, Edge Case "All activated references of a kind... are unresolvable"** (misconfigured
   pack root) — **carve-out applied.** Named explicitly in the ruling; this is the sibling absolute
   claim FR-001 itself cross-references via "(see Edge Cases)". Added: "except for a kind whose
   activated ids are reachable only via DRG-transitive closure when the whole DRG graph fails to load,
   which is covered collectively — never individually or via fail-closed exit — by the single loud
   `_graph`/`_load_failure` sentinel diagnostic (see FR-001)" — reusing FR-001's own already-committed
   clause verbatim for consistency.
2. **spec.md:94, Key Entities "CharterReference" bullet** ("must never silently vanish for an activated
   id") — **carve-out applied.** Named explicitly in the ruling. Added the matching exception clause,
   naming the `_graph`/`_load_failure` sentinel as the collective substitute for a per-id row.
3. **spec.md:104, SC-001** ("every activated reference id is either present... or corresponds to...
   diagnostic — never a silent omission with no trace") — **carve-out applied.** Named explicitly in
   the ruling. Added the matching exception clause.
4. **spec.md:69, FR-001 table cell** — **already carved (round 6).** No further edit; re-verified this
   round that its existing clause ("except for ids reachable only via DRG-transitive closure when the
   whole DRG graph fails to load, which are covered collectively by one loud, structured diagnostic
   rather than individually or via fail-closed exit") is intact and is the template this round's three
   new edits echo.
5. **spec.md:97, Key Entities "Activated reference id" bullet** — **already carved (round 6).** No
   further edit; its existing "Exception: an id reachable only via DRG-transitive closure... is
   accounted for collectively, not individually, when the whole DRG graph fails to load" clause is
   intact.
6. **plan.md:310-320 (I1) and :321-334 (I2)** — **already carved (round 6).** Both invariants carry
   their own "Carve-out (total graph-load failure)" paragraphs. No further edit.
7. **spec.md:23, User Story 1 Acceptance Scenario 4** (every activated `toolguide` id excluded by
   language scope... never a silently empty `toolguide` section) — **not a coverage claim needing the
   carve-out — why:** this scenario's fixture is entirely `SCOPE_FILTERED` (directly config-activated
   `toolguide` ids excluded by language, not DRG-transitive-closure-only ids), and per plan.md's IC-01
   "Relevant requirements" note, SC-005/AS4 back only the unconditional `SCOPE_FILTERED` placeholder
   mechanism, which has no graph-load-failure exception — `graph.unresolved`/transitive closure is not
   involved in this fixture at all.
8. **spec.md:108, SC-005** (same "every activated `toolguide` id... never silently empty" wording) —
   **not a coverage claim needing the carve-out — why:** identical reasoning to (7); SC-005 is scoped
   to the same AS4 `SCOPE_FILTERED`-only fixture per plan.md's own IC-01 citation, explicitly stated
   there to NOT exercise the whole-kind `MISSING_ARTIFACT` (let alone graph-load-failure) mechanism.
9. **spec.md:16, User Story 1 Independent Test** ("never a silent omission with only a diagnostics-list
   entry nobody reads") — **not a coverage claim needing the carve-out — why:** scoped to a single
   directly-config-activated `SCOPE_FILTERED` id (`activated_styleguides`/`_toolguides`/`_agent_profiles`),
   not a DRG-transitive-closure/graph-load-failure scenario.
10. **spec.md:22, User Story 1 Acceptance Scenario 3** ("`styleguide/java-conventions` present in
    `catalog.references`... rather than missing") — **not a coverage claim needing the carve-out — why:**
    names one concrete, directly-activated `SCOPE_FILTERED` id from Scenario 1's fixture, not a
    graph-load-failure/transitive-only case.
11. **spec.md:37, User Story 2 Acceptance Scenario 1** ("none of the fixture's activated ids are missing
    from `catalog.references`") — **not a coverage claim needing the carve-out — why:** the FR-005
    fixture (the six #5257 ids plus one more) is built entirely from directly-activated,
    language/scope-filtered ids per spec.md:29/plan.md's WP-ATDD description ("no Java/TypeScript
    signal activating those six ids plus one more") — no graph-load failure or transitive-only id is
    part of this fixture.
12. **plan.md:232, WP-ATDD step** ("Assert: (a) every fixture id is present in `catalog.references`") —
    **not a coverage claim needing the carve-out — why:** same WP-ATDD/FR-005 fixture as (11); no
    graph-load-failure scenario present.
13. **plan.md:30, Charter Check seam description** ("a `SCOPE_FILTERED` miss is preserved... never
    silently dropped") — **not a coverage claim needing the carve-out — why:** describes the
    unconditional `SCOPE_FILTERED`-cause classification branch specifically, which has no
    graph-load-failure exception in its own right (a `SCOPE_FILTERED` classification requires the id to
    have actually been looked up against a live repository — it is not the transitive-closure-only-under-
    total-graph-failure case I1/I2's carve-out addresses).
14. **plan.md:406, IC-01 Purpose** ("making every activated-but-unresolvable id whose cause is
    `SCOPE_FILTERED` a placeholder... uniformly regardless of cardinality") — **not a coverage claim
    needing the carve-out — why:** identical reasoning to (13); explicitly cause-scoped to
    `SCOPE_FILTERED`, not a blanket "every activated id" claim.
15. **plan.md:290/292-293, WP-CORE reconciliation decision 3 prose** ("mechanisms that satisfy FR-001
    'at any cardinality'"; "exactly the vacuous success FR-001 forbids") — **not a coverage claim
    needing the carve-out — why:** historical design-rationale prose explaining the `MISSING_ARTIFACT`/
    `TYPO_SUSPECTED` whole-kind gap decision 3 closed (round 2), not itself a forward-looking absolute
    guarantee; it paraphrases FR-001's pre-carve-out wording in a discussion of a graph-load-failure-
    unrelated cause. FR-001 itself (the source being paraphrased) already carries the carve-out at its
    point of record.
16. **plan.md:10, Summary** ("This mission makes that loss impossible"; "never a silent omission, never
    a second fail-closed code path") — **not a coverage claim needing the carve-out — why:** "that loss"
    refers explicitly, in the same sentence, to "the actual #5257/#5253 defect" — a directly-activated,
    scope-filtered id — not the transitive-closure-only/graph-load-failure case; editing high-level
    Summary prose beyond what the ruling named risks scope creep the ruling's "no new mechanism, no new
    requirements" / minimal-edit framing does not call for.
17. **plan.md:410, IC-01 Risks (2)** ("a `MISSING_ARTIFACT`/`TYPO_SUSPECTED` id must never fall through
    to the placeholder branch") — **not a coverage claim needing the carve-out — why:** a classification-
    correctness guard (don't misclassify), not a per-id completeness/coverage guarantee; unrelated to
    the graph-load carve-out.
18. **plan.md:431, IC-04 Purpose** ("pin this defect class... so it cannot silently regress") —
    **not a coverage claim — why:** describes a test's purpose, not a system behavior guarantee.
19. **plan.md:50/91/98/334**, **spec.md:10/12/14/29/31/38/60/61/73/74/87/105** — **not coverage claims —
    why:** matched only on generic "silently"/"coherent"/"vacuous"/"dropped" usage describing gate
    applicability, test-baseline rationale, campsite-clean-decision documentation, mission narrative/
    history (#5253, #5257), backward-compatibility (FR-006), the parity-guard constraint (C-001), the
    already-carved I2 carve-out's own closing clause (plan.md:334), or a test's own not-vacuous
    assertion — none assert unconditional per-id/per-kind completeness in a context the graph-load
    carve-out could contradict.
20. **contracts/charter-generate-json-diagnostics.md:130** ("each of these still gets a real entry —
    never silently dropped") — **not a coverage claim needing the carve-out — why:** this is the
    Round-5 addition section describing four `graph.unresolved`-URN-unattributable classes (malformed
    URN, unrecognized kind, no-repository kind, valid-but-untracked kind) that presuppose the DRG graph
    itself loaded successfully (only individual URNs within it are unattributable to a tracked kind) —
    a different mechanism from I1/I2's total-graph-load-failure carve-out, and not in tension with it:
    under total graph-load failure, `graph.unresolved` is never populated at all (per I2), so this
    section's guarantee and the carve-out apply to disjoint, non-overlapping scenarios.

**Edits applied (minimal, style-preserving, no new mechanism/requirement):** spec.md's Edge Case "All
activated references of a kind... are unresolvable" (line 58), the Key Entities "CharterReference"
bullet (line 94), and SC-001 (line 104) each gained a carve-out clause matching FR-001's own
already-committed phrasing pattern (reusing "covered collectively... by the single loud
`_graph`/`_load_failure` sentinel diagnostic... rather than individually or via fail-closed exit", or
the same clause naming, adapted grammatically per site) — the same doctrine FR-001 and the "Activated
reference id" bullet already state, now applied uniformly across every genuine absolute-coverage claim
found by the systematic grep. plan.md required no edits: every plan.md hit was either already carved
(I1/I2, round 6) or is scoped to a mechanism (`SCOPE_FILTERED`-cause-specific, or historical/purpose
prose) the carve-out does not implicate.

## Decision: reuse the canonical `_diagnose_catalog_miss` gate instead of a parallel classify helper + `active_languages` threading (round-8 fix, closes analyze D1/C1/U1)

**Context.** `/spec-kitty.analyze` against this mission's plan.md/tasks.md/WP02 prompt raised three
findings (`analysis-report.md`, verdict `blocked`): **D1** (high, duplication) — WP02's IC-02 design
built a brand-new classify-and-placeholder helper plus 4-level `active_languages` threading
(`compile_charter` → `_build_references` → `_build_references_from_service` →
`_render_kind_references`) that duplicates an already-built, already-used gate,
`_diagnose_catalog_miss(missing_id, repository)`
(`src/charter/activation/context_renderers/catalog_diagnosis.py`), which `selection_block.py` and
`profile_sections.py` already call for the identical FR-013 never-existed-vs-filtered-by-scope
classification, and which already reads `active_languages` straight off the repository's own
`_active_languages` attribute with zero threading; **C1** (high, coverage) — the plan's own
`raw_id in repository.scope_filtered_ids` design would raise `AttributeError` against the mandatory
Contract-C4 baseline test's `_EmptyRepository` double, which exposes only `.get()`; the existing
defensive `getattr(repository, "scope_filtered_ids", frozenset())` precedent (`catalog_diagnosis.py:51`)
was never cited; **U1** (medium, underspecification) — the plan's `classify_catalog_miss(raw_id,
available_ids)` fallback never stated where its `Iterable[str]` fuzzy-match corpus would come from;
the existing `_available_catalog_ids(repository)` helper (used internally by the gate) solves this
defensively but was never named.

**Verification performed before ruling (not taken on faith from the finding text).** Read
`catalog_diagnosis.py` in full: `_diagnose_catalog_miss` (`__all__`-exported — the ONLY export)
checks `getattr(repository, "scope_filtered_ids", frozenset())` first, routes a scope-filtered id to
`classify_scope_filtered_miss(missing_id, getattr(repository, "_active_languages", None))`, and
otherwise falls through to `classify_catalog_miss(missing_id, _available_catalog_ids(repository))` —
exactly the sequence D1/C1/U1 all point at. Read every import in `catalog_diagnosis.py`,
`_catalog_miss.py`, and `context_renderers/__init__.py` (plus its sibling modules
`authority_paths.py`, `fetch_stanza.py`, `section_bodies.py`, `token_budget.py`): none of them import
`compiler` anywhere. `_catalog_miss.py` is confirmed a leaf (imports only `difflib`/`logging`/
`warnings`/stdlib `collections.abc`/`dataclasses`/`enum`). So the new import direction
`charter.activation.compiler` → `charter.activation.context_renderers.catalog_diagnosis` →
`charter.activation._catalog_miss` is one-directional with **no import cycle**.

**Decision: reuse, do not reinvent.** WP02's per-id classification now calls
`_diagnose_catalog_miss(raw_id, repository)` directly from the new classify-and-placeholder helper in
`compiler.py`, instead of building a parallel classify function and threading `active_languages`
through four call levels. This applies the spec's own already-stated mandate (spec.md Key Entities
"Existing catalog-miss classifier (reuse target)", DIRECTIVE_044 single-canonical-authority) more
precisely than the original WP02 design did — it does not change any operator ruling from rounds 3–7:
the whole-kind fail-closed check, the `graph.unresolved` URN-split/kind-mapping via
`ArtifactKind(kind_prefix).plural`, the graph-load diagnostics/structured-records sink on
`_resolve_transitive_reference_graph`, the plain-`str` typing of `cause` (never `CatalogMissCause`),
and the `_raw_kind_repository` `getattr` fallback fix are all UNCHANGED — those mechanisms are
orthogonal to per-id classification and are not touched by this decision. `_diagnose_catalog_miss`
is in `catalog_diagnosis.py`'s `__all__`, so importing it across the `context_renderers` package
boundary is a legitimate, sanctioned use of the module's public surface — it is not renamed.

**Consequence for T007/T008.** T007's helper shrinks to a thin wrapper: call the gate, branch on the
returned `CatalogMissDiagnosis.cause`, build a placeholder only for `SCOPE_FILTERED`, otherwise stay
diagnostics-only (Contract C4 unchanged), and append the reason-bearing diagnostic string plus the
structured record in both branches. T008 — originally "thread `active_languages` across four call
levels" — is repurposed to a verification-only subtask (confirm no threading was added; confirm the
gate receives the real repository object so its language-set-naming suggestion text surfaces
end-to-end) rather than a plumbing change, since the plumbing no longer exists to write.
