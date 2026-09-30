---
title: Manifesto tier — verdict, corrections, and handover
description: "Verdict of two adversarial squads on the proposed manifesto tier: the diagnosis survives, the mechanism is rejected by an experiment the proposal itself nominated."
doc_status: deprecated
updated: '2026-07-26'
related:
- docs/archive/plans/doctrine/manifesto-tier-primary-drivers.md
- docs/plans/doctrine/index.md
---
# Manifesto tier — verdict, corrections, and handover

> **Retired (deprecated).** Superseded by the canonical creed AUTHORITY doc [foundational-values-and-creed.md](../../../plans/doctrine/foundational-values-and-creed.md). Preserved as a historical record.

> ⚠️ **RECORD.** This verdict killed the *derived-tension* mechanism; a **successor design exists
> and is the build target**: [`foundational-values-and-creed.md`](../../../plans/doctrine/foundational-values-and-creed.md)
> (authored `impacts` edges, creed on the charter — none of the mechanisms rejected here).
> Its "~47,900 candidate pairs" is C(310,2) over DRG *nodes*; the authoring denominator is 260
> behavioural *artefacts* — different measures (authority §11).

**Date:** 2026-07-26
**Method:** two sequential adversarial squads, 8 profile-loaded agents, all read-only.
Round 1 (grounding): researcher-robbie, architect-alphonso, doctrine-daphne, paula-patterns.
Round 2 (dialectic): reviewer-renata (prosecution), designer-dagmar (defence),
debugger-debbie (experiment), planner-priti (sequencing).
**Supersedes** the mechanism proposed in [`manifesto-tier-primary-drivers.md`](manifesto-tier-primary-drivers.md).

---

## THE CALL

**Do not build the tier. Convert it into a measurement, and run the decision gate that
already exists (`#2538`).**

The diagnosis was right. The mechanism is dead. And the diagnosis was right about the
wrong layer.

### What killed the mechanism

The proposal named its own falsification condition: *"if the manifesto cannot reproduce
[`RECONCILE_CHANGE_SCOPE_TENSIONS`]'s stated ordering, the manifesto is wrong."* Nobody had
run it. Round 2 ran it.

**Result: 0 reproductions out of 6 derivations** (2 independent scoring passes × 3 weightings),
producing **4 distinct orderings** — worse than chance, which would yield ~1 hit in 6. The
authored ordering appeared zero times, including under the weighting derived from this
repository's own charter.

**The failure is categorical, not calibration.** `RECONCILE_CHANGE_SCOPE_TENSIONS` is not a
precedence over values. It is a **pipeline of three operator types**:

| Artifact | Role | Function |
| --- | --- | --- |
| `tactic:change-apply-smallest-viable-diff` | **generator** | *picks* the file set |
| `DIRECTIVE_025` Boy Scout Rule | **transformer** | operates *within* that set |
| `DIRECTIVE_024` Locality of Change | **guard** | *vetoes* growth of the set |

A scalar weighting has exactly one output type and cannot express *"A determines the domain
over which B ranges."* Note the ordering's direction is ambiguous before you even start:
"last" means *most authoritative* here (the brake vetoes), where in a precedence ranking last
means *weakest*.

Feasibility analysis confirms it structurally: with `d1 = v_SVD − v_025` and
`d2 = v_025 − v_024`, we find `d1 ≈ −d2`, so the reproducing set is a measure-near-zero cone
requiring **~zero weight on Minimal and Reachable — the two values the triple is about.** The
mechanism can reproduce the ordering only via a manifesto that declines to have an opinion on
the trade the ordering exists to resolve.

**The defence reached the same conclusion independently and conceded it** before the
experiment's results were shared. Two lenses, one categorical answer.

### Three more independent failures

- **False positives: 5 of 5 (100%).** Five deliberately unrelated pairs (a git-signing
  directive vs a docs-accessibility styleguide, etc.) all flagged. Opposition counts
  **overlap**: genuine tensions 4–6, unrelated 2–4, overlapping at 4. No count or magnitude
  threshold separates them.
- **The corpus is ~one-dimensional.** It holds two archetypes — *impose rigour*
  (`Ma+ E+ Mi− R−`) and *remove friction* (`Mi+ R+ Ma−`) — so every cross-archetype pair is
  automatically "in tension" whether or not it can ever co-apply. This falsifies §4(a)'s
  "vector in 7 fixed dimensions" **by measurement**, corroborating the prior-art finding that
  AMMERSE's non-zero matrix off-diagonals mean the dimensions co-vary and are therefore not a
  basis.
- **Author-dependence in the deciding cell.** `DIRECTIVE_024`'s Solvable sign flipped between
  the same agent's two passes one hour apart — and that is precisely the cell determining
  whether a threshold is needed at all.

At 310 DRG nodes the mechanism emits **~47,900 candidate pairs**, on which the one real
tension does not stand out. The load-bearing control is the **co-application filter**, and
that filter is exactly the human judgement the mechanism was supposed to automate away.

### The finding that decides the cost question

The experiment surfaced two genuinely unrecorded tensions: `DIRECTIVE_043` × smallest-viable-diff,
and `DIRECTIVE_044` × `DIRECTIVE_024`. Both carry zero tension edges. **Both are already
resolvable by machinery that ships today** — `required` beats `lenient-adherence`.

> The cheap path **resolves** them. The expensive path only **flags** them.

### The re-frame that matters most

This investigation began from *"current-generation LLMs optimise output over outcomes."* The
repo's own history says: **yes — and the same bias already operated on the governance
machinery itself.**

Three arbitration registers shipped as Reachable-maximal slots — schema now, producers later:

| Register | Born | Fate |
| --- | --- | --- |
| `Directive.severity` | `8b25f444f` 2026-02-15 | 13/13 uniform `warn`, **162 days**, zero producers, zero readers |
| `GovernanceConfig.enforcement` | `8b25f444f` (same commit) | `{}` — only consumers are a test asserting it is empty and a round-trip probe |
| `routing_policy` / `task_fit` | `45a451a16` 2026-07-04 | **inert for ~20 of 21 verbs**, remediated the *same day* by copying one artifact's scores four times |

All three shipped with **green, passing tests** the entire time — the tests proved Pydantic
round-trips, not that anything populated or read the field. `git log -S'severity: error'`
returns nothing: never populated once, ever.

**Three for three: in this repo, a scoring register without a producer *and* a coverage gate in
the same commit does not degrade gracefully — it goes silently inert and passes review.**

§8.1's mitigation ("partial population must be a first-class state, never an error") is the
Reachable-maximal move, and it is **falsified by measurement, not argument**. The manifesto
proposal was itself an instance of the bias it diagnosed. That is the real finding.

---

## What survives

1. **The core diagnosis, inverted and sharpened.** Doctrine does not *lack* ordering — it
   **discards the orderings it already has.** `resolve_context` walks `requires` unbounded and
   `suggests` bounded, then destroys the distinction: `all_artifacts = scoped | required |
   suggested` (`src/doctrine/drg/query.py:119`), returning a `frozenset`. Measured:

   | Action | union | scope | requires | **suggests** | **soft share** | depth-2-only |
   | --- | --- | --- | --- | --- | --- | --- |
   | specify | 4 | 3 | 1 | 0 | 0.0% | 0 |
   | plan | 26 | 7 | 12 | 7 | 26.9% | 3 |
   | tasks | 25 | 7 | 8 | **10** | **40.0%** | 3 |
   | **implement** | **89** | 37 | 27 | **25** | **28.1%** | **8** |
   | review | 79 | 30 | 39 | 10 | 12.7% | 2 |

   `suggests` is the **majority relation** (332 edges vs 259 `requires`). At `implement`, 8
   artifacts arrive as a *suggestion-of-a-suggestion* and are presented identically to a hard
   transitive prerequisite.

2. **§4(b) — mandatory negative components.** The proposal's one contribution with no prior
   art, and it survived all four Round 2 lenses. It is *why detection worked at all*: the shape
   forced honest negatives where a positives-only rubric would have vector-washed all eight
   pairs to "aligned." It needs no kind, no vectors, no weighting, no complete scoring. It
   survives as an **authoring constraint and review heuristic**.

3. **Detection on an already-co-applying set.** Both passes flagged both authored tensions and
   missed neither. Real, useful, and requires none of the dead machinery.

4. **A twelfth arbitration register, inert *because of* the union.**
   `src/specify_cli/calibration/walker.py:507` sets
   `known_irrelevant = resolved_scope - required_scope`, making the over-broad half of the
   R-005 inequality **vacuously true by construction**. The in-code comment is the confession:
   the harness needed a blanket absorber *because the union makes a hard prerequisite
   indistinguishable from a depth-2 suggestion.* Fixing `query.py:119` un-blinds an existing,
   CI-collected instrument.

5. **A new always-on surface nobody had identified.**
   `src/specify_cli/tool_surface/profiles/_render_helpers.py:47-65` renders to
   `.claude/agents/<id>.md` **and twelve harness siblings**, unconditionally, **outside the
   32k token budget**, reaching every dispatched subagent on every harness with a cold context.
   Confirmed first-person: it is the only doctrine in a subagent's system prompt. Nothing else
   in the repository has that property.

## What is dead

| § | Claim | Why |
| --- | --- | --- |
| §4(c) | Derived ordering reproduces the authored one | **0/6, worse than chance**; categorically impossible (sequencing ≠ precedence). Killed independently by two lenses |
| §7.4 | Derive `in_tension_with`, keep authored edges as overrides | **Option C of ADR `2026-07-21-1`, Accepted 2026-07-21 — explicitly rejected 5 days before the proposal was written.** Plus 5/5 false positives on a one-axis corpus |
| §7.3 | `value_impact` vector per artifact | Reintroduces field-authored relationships that `test_built_in_relationships_authored_in_drg` asserts are gone; collides with `#2216`'s `component-type` all-artefact sweep; its incremental-population plan is the exact recipe that produced `070edbd4f` |
| §7.2 | `manifesto` node kind, three scopes | 41–59 files / 2.2–3.8 kLOC measured from three real precedents (`d54470c83`, `ce9d20e6c`, `1e3dc8d2c`). Unjustifiable pre-gate. Also undeliverable as scoped: the kind universe is a triple-mirrored fail-closed literal, so an "org manifesto" means editing a library that declares itself project-independent |
| §6 | Computable squad coverage / collinearity | Zero prior art; depends on the dead vectors. Was billed as "the first concrete thing the tier buys" |
| §5.2 | The licensed non-delivery move needs the basis | **Premise false.** `tactics/built-in/stopping-conditions.tactic.yaml` already exists, is activated, and carries six inbound DRG edges including `scope` on `implement` and `review`. Grammar: *"When X happens, I will Y"*; worked example escalates to the human-in-charge. The capability was never missing — and its presence has not fixed the bias, which is the measurement the proposal needed and never took |
| §5's promise generally | Naming the defect makes it correctable | Prior art measured a declared value ordering moving revealed model priorities by **0.145** normalized, with rankings *inverting* between elicitation formats. §5.1 (*deviation becomes statable*) is supported. §5.2 (*agent obeys*) is not |

**Honest scope: diagnosis and review support. Not agent correction.**

---

## Corrections to the original document

Errors found by independent verification. Several corrections make the case *stronger*.

1. **The vocabulary census is wrong on two rows.** Claimed `trade-off` = 0 and `long-term` = 0.
   **Actual: 35 and 15.** Cause was my own regex bug — `grep -E "trade-off\|tradeoff"` searches
   for the *literal string* `trade-off|tradeoff`. The rhetorical close *"a corpus that cannot
   say trade-off cannot arbitrate one"* is **falsified**. The single-term rows stand: `output`
   168, `outcome` 49 (all BDD "observable outcome"), `horizon` 1 (= "horizontal"),
   `stewardship` 4.
2. **`^DIRECTIVE_\d{3}$` is not the directive ID contract.** It is `^[A-Z][A-Z0-9_-]*$`
   (`schemas/directive.schema.yaml:40`); `RECONCILE_CHANGE_SCOPE_TENSIONS` conforms. That
   pattern lives only at `paradigm.schema.yaml:62`. **The real defect is sharper:** because its
   ID is not `DIRECTIVE_NNN`, no paradigm can list it in `directive_refs` and no profile can
   cite it — **verified zero inbound references corpus-wide.** It is unreachable, not malformed.
   It is also itself `enforcement: advisory` — the arbiter is the most ignorable item in the bag.
3. **"Completely inert" is wrong.** The AMMERSE tactic is charter-**activated**
   (`.kittify/config.yaml:53`), ships in the default pack, and is a **`requires`** target of
   `procedure:situational-assessment`. True statement: *activated and procedure-mandated, yet
   zero scores exist anywhere.*
4. **"Nothing catches a contradictory reconciliation" is wrong.** `scan_unreconciled_tensions()`
   (`src/charter/consistency_check.py:977`) is live, canonical, flags half-reconciled pairs, and
   has a non-vacuous suite naming this exact triple. Missing piece is narrower: **presence is
   validated; ordering semantics are not.**
5. **Counts:** 13 paradigm DRG nodes, not 14 (`test-first.paradigm.yaml` sits outside
   `built-in/` so is not a DRG node — a separate drift defect). **310** DRG nodes, not ~200.
   **6** artifacts carry "Adapted from patterns.sddevelopment.be", not a dozen — and the AMMERSE
   tactic carries **no** sddevelopment provenance, so "AMMERSE came across with them" is
   inference. `in_tension_with` = 2 ✓. 18 profiles ✓.
6. **"All paradigms are methodologies" is overstated.** `brownfield-onboarding.paradigm.yaml`
   is a genuine epistemic stance. Defensible claim instead: **the paradigm schema has no field
   able to hold a value, weighting, or ordering**, so worldview content degrades into prose.
7. **§9 "must be authored, not ported" is partly refuted.** The three-tier meta model is already
   in-repo as **unregistered** diagram templates —
   `templates/diagrams/{plantuml,mermaid}/examples/structure-meta-model-*.md` carry
   `Primary Drivers`, `{{Derived Concept}} (e.g., Creeds, Principles)`, `{{Observable Behavior}}`,
   `{{Effects}}`. Better framing: *the meta model shipped as a drawing aid instead of as doctrine
   structure.*
8. **The AMMERSE definitions are already duplicated and already drifted.** Second copy at
   `templates/architecture/ammerse-analysis-template.md`; the template's Environmental
   definition has **lost "impact on nature"**. Step 1 is a DIRECTIVE_044 unification of two
   drifted copies — a debt payment, not a speculative refactor.
9. **The first-order interaction matrix is not in the repository.** Both copies defer to an
   external URL. §8.3's "port first-order only" mitigation names the one component that is
   **unavailable and is the trademarked party's uncalibrated judgement.**
10. **`enforcement` is not wholly unrendered** (correcting Round 1). It *is* emitted — but only
    by `_format_full_artifact_payload_body` as a `json.dumps(sort_keys=True)` blob reached via
    `--include`/fetch recovery. Sharper claim: **enforcement reaches the agent only after the
    agent already went looking, alphabetized inside a JSON dump — never on the line where the
    directive is first presented.**
11. **`tactic.schema.yaml` has no `references.type` enum** (correcting Round 1). It is a free
    string, and `TacticReference.type` *is* `ArtifactKind` including `glossary_pack`. So such a
    reference **validates at both schema and model level and is then silently dropped by
    `extractor._KIND_MAP`** (11 entries; missing `glossary_pack`, `asset`, `anti_pattern`).
    Strictly worse than a rejected enum value.
12. **There is no `feature` terminology guard.** `test_no_legacy_terminology` forbids exactly
    two retired legacy nouns (see `_FORBIDDEN_TERMS`; not reproduced here — the guard scans
    `docs/`, so quoting them in prose reds it), and `_SCAN_ROOTS` excludes `.kittify/`. Do not
    sell the Purpose rewrite as gate-verified — nothing checks it.
13. **`#2917` is CLOSED** (corrects standing project memory). The release blocker is `#2934`
    plus 14 open P0s. **`#2537` is CLOSED** → ADR `2026-07-21-1` accepted.

---

## THE SEQUENCE — what to actually do

### File unconditionally, regardless of the manifesto's fate

**Close the three silent kind-drop sites.** ~3 source files, ≈150–300 LOC:

| # | Site | Failure |
| --- | --- | --- |
| 1 | `src/doctrine/drg/query.py:231-241` | `resolve_transitive_refs` buckets all 16 `NodeKind`s, reads out 10 → new kind computed, silently dropped |
| 2 | `src/charter/context.py:670-682` | `_classify_artifact_urns`, four `elif`, **no `else`** → silent drop at the injection boundary |
| 3 | `src/doctrine/drg/migration/extractor.py:133-145` | `_KIND_MAP` has 11 entries; `.get()` → `None` → **edge vanishes at extraction time** |

It is a shared enabler for **four already-open issues** (`#2468`, `#2847`, `#2862`, `#2829`),
belongs under `#2466`, and **retires the proposal's "step 1 is a pure refactor, available
immediately" claim outright.**

### The first mission — make the thesis falsifiable, build no new tier

| WP | Scope | Dep |
| --- | --- | --- |
| **WP01** | Partition `ResolvedContext` **additively** — add `scoped_urns`/`required_urns`/`suggested_urns`; keep `artifact_urns` as the union so all 3 consumers are untouched. Publish the strength breakdown through the **existing** `test_surface_report`. **Campsite:** delete `Directive.severity` + `GovernanceConfig.enforcement` (dead since 2026-02-15); fix the `src/doctrine/README.md` kind table (10 rows vs 12 kinds, 2 non-kinds, 4 omissions) | — |
| **WP02** | Un-vacuum `walker.py:507` → `known_irrelevant = ctx.suggested_urns - required_scope`. **Expect RED. The red is the deliverable.** Do not re-widen the absorber to get green | WP01 |
| **WP03** | Group Action-Doctrine under `Required:` / `Suggested:`. Render enforcement **for the non-`required` minority only** — the census is 22 required / 3 lenient / 1 advisory, and at `implement` 15/2/**0**, so rendering the field wholesale distinguishes 2 of 17 while adding a token to all. Critically: put it in `_format_inline_directive_body`, which feeds the **always-on profile block** and so escapes the 4-of-24 Action-Doctrine ceiling | WP02 |

⚠️ **Before rendering the token `advisory`, resolve the homonym.** It already means three
incompatible things (`{required, lenient-adherence, advisory}` in doctrine;
`{advisory, enforcing}` in contracts; `Literal["advisory","blocking"]` in runtime), with four
more `severity` ladders alongside. Rendering it into agent context as-is is a new
`primary`/`merge`-class footgun. **Collapsing eight vocabularies to two is the real
unification mission**, it is independently valuable, and it is the prerequisite for anything
the enforcement render could buy.

### THE DECISION GATE — `#2538`, and it already exists

**`#2538`** — *"experiment: does missing tension-modeling cause bad deferment at depth?"* ·
OPEN · P2 · milestone 3.3.x · under epic `#2466` · **"Rig is standing. Run and results
pending."**

It is a **pre-registered controlled rig** on the real `specify → plan → tasks` loop with six
seeded deferment/ambiguity forks. Its metric is exactly right — **"surfaced vs silent, because
silently resolving a tension is the failure even when the pick is right"** — and its threshold
is **locked**: reproduced if, across a majority of runs, ≥2 forks are decided wrong or resolved
silently. Its own triage says it should run *before* any tension build work and that **"a null
result is a legitimate outcome."**

**Do not build a second rig.** Run the standing one as an A/B: arm A = today's flat context,
arm B = WP03's strength-ordered context. Post the arm-B pre-registration as a comment
*before* the run.

> **If arm B does not increase *surfaced* on ≥2 forks across a majority of runs, §7 steps 2–5
> close as won't-do.**

Two caveats for whoever runs it: `specify` resolves only **4 artifacts** — there is nothing
there to reorder, so weight the `plan` (26) / `tasks` (25) forks or it reads null for a trivial
reason. And **verify the rig still runs before starting WP01** — "rig is standing" is the
author's claim, unverified, and the entire gate decays with it.

Prior art predicts arm B ≈ null (0.145 effect size). **Running the gate first therefore has a
positive expected value of roughly one avoided 41–59-file mission** — the trade the proposal
never priced.

### Two human decisions — not agent tasks

1. **The AMMERSE trademark question.** *"AMMERSE, AMMERSE Method, AMMERSE Theory, AMMERSE Value
   System are all trademarks of J.B Crossland."* Shipping a trademarked value system as a
   built-in doctrine kind in a distributed CLI needs an answer. Cheap to get; a "no" kills the
   branch regardless of `#2538`.
2. **The `charter.md:16-18` Purpose rewrite.** This is a declaration of the operator's own
   values and trade posture. An agent drafting it is precisely the self-scoring failure §8.5
   names, and nothing verifies it (correction 12). Operator authors; an agent may then propagate
   mechanically. Apply §4(b) as the constraint: **it must name something the project gives up.**
   The material already exists — the throughline at `charter.md:49-52`, the dated horizon
   ("target 0 by 4.0") at `:481-491`, the never-auto-decide posture at `:29-30`.

### Explicitly parked — with reasons

| Parked | Reason | Unpark on |
| --- | --- | --- |
| §7.3 `value_impact` | Field-authored relationships + `#2216` collision + 3-for-3 decay precedent | `#2538` positive **and** a coverage gate designed before the schema |
| §7.4 derived tension | Option C of an **Accepted** ADR | A *superseding* ADR, not a plan doc |
| §7.2 `manifesto` kind | 41–59 files, unjustifiable pre-gate | `#2538` positive **and** `#2467` KEYSTONE landed **and** silent-drop closure landed |
| §6 squad composition | Zero prior art; needs the dead vectors | Only if the kind exists for other reasons |
| §7 step 6 outcomes tier | Downstream of an ungated prerequisite | Value tier shipped |
| Re-tier AMMERSE onto `glossary_pack` | Landing kind is 4 days old and **not in `_KIND_MAP`** — the edge would silently vanish. Also the basis still has no consumer | Silent-drop closure landed **and** a consumer exists |
| Populating `severity` / `governance.enforcement` | **Permanently** — in favour of deletion. Populating either reproduces `070edbd4f` voluntarily | Never; a consumer must be designed first, at which point it is a new field |

### Debt tickets worth filing now (independent of everything above)

- `RECONCILE_CHANGE_SCOPE_TENSIONS` has **zero inbound references** and is itself `advisory` —
  delete-or-wire.
- AMMERSE definitions duplicated and drifted (tactic vs template; "impact on nature" lost) —
  DIRECTIVE_044 unification. Home: `#2080`.
- `src/doctrine/README.md` kind table drift. Home: `#2080`.
- `DIRECTIVE_043` × smallest-viable-diff and `DIRECTIVE_044` × `DIRECTIVE_024` carry zero
  tension edges while both directives are `required` and both mandate non-local work.
- Nothing detects a schema field with zero producers — three registers proved it. A lint for
  that is worth more than any of the above.

---

## Handover note to the parallel session (`fix/2934-demock-planning-closeout-test`)

**What this was:** a deliberately meta-level lens run alongside your grounded work, per the
operator's framing. It is now finished and has produced a verdict, not an open question.

**What you need from it — three things, in priority order:**

1. **`src/doctrine/drg/query.py:119` is a real defect on your side of the fence.** It unions
   `scoped | required | suggested` into a `frozenset`, destroying an authored strength ordering.
   Measured impact: **40% of the `tasks` doctrine surface and 28% of `implement` (25 of 89
   artifacts, 8 of them depth-2-only) are soft suggestions presented identically to hard
   prerequisites.** `suggests` is the majority relation in the graph (332 vs 259). If you are
   anywhere near context assembly or planning-closeout behaviour, this is upstream of you.
2. **`src/specify_cli/calibration/walker.py:507` has a vacuous gate.**
   `known_irrelevant = resolved_scope - required_scope` makes the over-broad half of the R-005
   inequality **true by construction** — the in-code comment admits it. It is a live instrument
   that currently measures nothing, and it went vacuous *because of* (1). If your work touches
   calibration, treat this as a known-red-when-fixed.
3. **The three silent kind-drop sites** (`query.py:231-241`, `_classify_artifact_urns` missing
   `else`, `extractor._KIND_MAP`) silently discard data with no error. Any work adding or
   plumbing a doctrine kind hits these.

**What you should NOT inherit:** no new doctrine kind, no `value_impact` field, no derived
tension, no manifesto schema. All rejected above with reasons. If a future prompt suggests any
of them, this document is the refusal.

**The one transferable discipline**, and it generalises well beyond this investigation:

> **A schema slot without a producer and a coverage gate in the same commit goes silently inert
> and passes review.** Three for three in this repo, one of them inert for 162 days behind
> green tests. If your work adds a field, add its producer and its coverage assertion in the
> same commit, or do not add the field.

**Where the artifacts are:** this note and
[`manifesto-tier-primary-drivers.md`](manifesto-tier-primary-drivers.md) (marked superseded, kept
as the investigation record) live on branch `docs/manifesto-tier-analysis`, worktree
`.worktrees/docs-manifesto-tier`, based on `main`. Nothing was landed on either active mission
branch and the parallel checkout was never touched.

---

## Method note and limits

Eight agents, all profile-loaded, all read-only, no HEAD-moving git. Round 2 was assigned
adversarial positions (prosecution / defence / experiment / sequencing) specifically because
Round 1 converged uniformly deflationary and four reviewers each optimising for their own
Reachable value is exactly the bias under investigation.

Honest limits on the verdict:

- **The experiment is one instrument sampled twice, not two raters.** The 4-distinct-orderings
  spread is a *lower* bound on real disagreement. The categorical argument (sequencing ≠
  precedence) does not depend on the numbers and is the load-bearing part.
- **Experiment 3's "unnoticed tensions" are confirmation, not discovery** — the agent picked the
  pairs by reading, then scored them. A real discovery test requires blind scoring and a ranking
  in which unknown tensions rise above ~47.9k pairs of noise.
- **The 5/5 false-positive rate has a wide interval** — 5 pairs of 47,900, chosen as expected-to-be-unrelated rather than adversarially hard.
- **A non-linear reconciliation could plausibly reproduce the ordering.** What was falsified is
  the *linear weighting* the proposal specifies. A typed generator/transformer/guard composition
  might work — but that is a small composition algebra, not a manifesto, and it is a different
  proposal.
- **The scoring agent was a current-generation LLM scoring a rubric designed to detect
  current-generation LLM value bias**, and said so: it gave the two scope-limiting artifacts the
  highest Reachable scores in its table. Whether that is correct reading or its own bias
  rendered as data cannot be determined from the inside.
- **Nothing was executed.** All "what breaks" claims are static reads. No test was run by any
  agent.
- **The recommended blind experiment before any schema work:** 3 independent scorers × 20
  artifacts (10 known-co-applying, 10 known-unrelated) × 7 values, blind to the authored edges.
  Outputs: Krippendorff's α per value, precision/recall against the 2 authored + 2 nominated
  edges, and a PCA rank of the 20×7 matrix to settle the one-axis question. ~1 day. It cannot
  test §6, which needs profile vectors that do not exist.
