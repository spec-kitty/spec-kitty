# Mission Specification: Agents route around `/spec-kitty.analyze` because the command prompt is too large to load

**Mission Branch**: `fix/analyze-prompt-context-load-5005`
**Created**: 2026-09-26
**Status**: Draft
**Input**: GitHub issue #5005 (verbatim in the mission dispatch); user description: "Agents route around /spec-kitty.analyze because the command prompt is too large to load"

## Clarifications / Decisions

The following six operator decisions are binding inputs to this mission. Items 1-3 are
reproduced verbatim from the original mission dispatch. Items 4, 5, and 6 are later, binding
operator decisions delivered on 2026-09-26 — after the original dispatch and after the
spec-phase squad's review rounds (4 and 5 followed the first two review rounds; 6 followed
round 2's HALT on the ADR 2026-07-28-1 conflict Decision 5 exposed, see below) — each
reproduced verbatim from that later communication (not paraphrased or elaborated by the
orchestrator, except where explicitly marked as the orchestrator's own gloss); each is dated
inline and states explicitly which part of the earlier items it supersedes, so the
provenance sources (original dispatch vs. each 2026-09-26 follow-on) are distinguishable at
every citation below.

1. **DIAGNOSE FIRST** — the mission opens by measuring what an agent actually receives for
   `analyze` (template + injected charter/governance context) and identifies the real cause
   before choosing a remedy. It may conclude `analyze/prompt.md` needs no edit at all.
2. **Remedy scope**: a prompt/context-side fix on EXISTING canonical sources ships in THIS
   mission. NO new CLI surface in-mission — instead the orchestrator will draft a SEPARATE
   proposal for a lean `analyze` CLI entrypoint pending maintainer sign-off. If the diagnosis
   concludes the real cause can only be fixed by a new CLI entrypoint, say so EXPLICITLY in
   spec.md and do not silently widen scope to build it anyway.
3. **FOLD IN** the stale override reconciliation
   (`.kittify/overrides/missions/software-dev/command-templates/analyze.md`) as a
   domain-matched campsite-clean commit — i.e. this mission's scope includes bringing that
   stale project-local override (dated ~April 2026, still cites the retired
   `/memory/constitution.md`) back into alignment with canonical, as a separate,
   behaviour-preserving first commit (the actual commit happens in later phases — this spec
   scopes it in as an explicit FR/scope item so the squad and later phases know it's in
   scope).

   > **Clarification (added in review round 3; narrows the reading of "behaviour-preserving"
   > above, does not alter the verbatim operator text quoted in item 3):** "behaviour-preserving"
   > is read narrowly here — it preserves the campsite-clean, domain-matched framing of this
   > fold-in and this mission's overall scope/heuristics (the analyze step's detection and
   > severity-classification logic; the same narrowing NFR-001 already applies under the label
   > "heuristic preservation"). It is **not** a claim that the override's own literal read/write
   > contract stays unchanged. That contract changes intentionally and in-scope — from
   > `STRICTLY READ-ONLY` to a `NON-REMEDIATING` contract with a real write-and-persist path
   > (adopting canonical's `record-analysis` step) — because closing that gap (the recurring
   > `record-analysis` persistence/verdict-honesty defect class) is the actual fix FR-001
   > requires, per full contract PARITY by construction. FR-001's citation of "Operator Decision
   > 3" below inherits this same narrowed reading.

4. **Override handling (2026-09-26, binding, supersedes part of item 3/FR-001 above):**
   **(Superseded by Operator Decision 7, 2026-09-26 — kept verbatim below as history, not
   deleted from the record; see Decision 7's gloss below for why FR-001 no longer executes.)**
   DELETE the analyze override
   (`.kittify/overrides/missions/software-dev/command-templates/analyze.md`) so canonical
   `packs/built-in/missions/mission-steps/software-dev/analyze/prompt.md` resolves — no future
   drift. Stays scoped to #5005. This SUPERSEDES FR-001's byte-for-byte-copy approach. The
   other 9 stale software-dev command-template overrides (accept, implement, plan, review,
   specify, tasks, tasks-outline, tasks-packages, tasks-finalize — all differ from canonical;
   verified by orchestrator with `cmp`) are OUT of scope; the orchestrator has recorded them as
   ledger entry **SK-276** in the workspace-level `SPEC-KITTY-LEDGER.md` (that ledger lives
   outside this repository checkout, one level up in the mission workspace — not a path this
   spec cites). This is mentioned here as a known residual, nothing more.

   > **What this supersedes, precisely:** Decision 4 replaces FR-001's *mechanism*
   > (byte-for-byte copy the override's content from canonical) with deletion. It does **not**
   > reopen Decisions 1–3, which stand unmodified. The round-3 clarification above (narrowing
   > "behaviour-preserving" and describing the override's contract moving from
   > `STRICTLY READ-ONLY` to a `NON-REMEDIATING` contract with `record-analysis` persistence)
   > describes an *outcome* — an agent resolving `analyze` in this checkout gets canonical's
   > `record-analysis` persistence step — that Decision 4 still delivers, just by deleting the
   > shadow rather than overwriting it with a copy. FR-001, NFR-001, SC-001, and the relevant
   > Edge Cases bullet are rewritten below to describe deletion, not a copy-then-diff contract.

5. **Governance-context bloat (2026-09-26, binding, supersedes FR-005 as originally
   scoped):** FOLD INTO THIS MISSION. Fix the 81–95 KB governance-context injection in
   specify/plan/tasks/implement/review (root cause per research.md: `_governance_context()` in
   `src/runtime/next/prompt_builder.py` and the charter action-scoped context resolution it
   calls) now, accepting collision risk with open PR #5009. This SUPERSEDES FR-005 (no
   follow-up issue gets filed) and whatever scope text deferred this work.

   > **Root-cause attribution refined by investigation (research.md § 9, does not alter the
   > verbatim operator decision above):** the operator's framing names
   > `_governance_context()` in `src/runtime/next/prompt_builder.py` as (part of) the root
   > cause. Live measurement (research.md § 9) confirms `_governance_context()` is a thin
   > pass-through — it never inlines a byte of doctrine itself — and locates the actual defect
   > one layer further in: `src/charter/activation/context_renderers/token_budget.py`'s
   > existing NFR-001 budget-enforcement function (`_enforce_token_budget`, 40,000-character
   > `BUDGET_DEFAULT`) never sees the "Action Doctrine" block
   > (`_render_action_doctrine_lines` in `src/charter/activation/context_renderers/bootstrap_text.py`),
   > which is the block that actually carries 71–75% of the oversized bytes. This is "the
   > charter action-scoped context resolution [`_governance_context`] calls" the operator's
   > decision already names as in-scope — a more precise seam within that same scope, not a
   > different one. FR-005/006/007 below implement the fix at this confirmed seam. See the
   > "Confirmed diagnosis" section's superseded call-out immediately below for the full
   > reconciliation.

6. **Governance-context fix deferred to maintainer (2026-09-26, binding, supersedes Decision
   5's in-mission implementation):** Keep ADR 2026-07-28-1 intact. DROP FR-005/006/007 (the
   governance-context budget fix) from this mission's implementation scope. Ship the
   analyze-override deletion (FR-001, Decision 4) + the advisory doctrine (FR-002) + the
   measurements (FR-003, research.md). The orchestrator will post the budget-gap measurements
   and an ADR amendment proposal on #5005 for the upstream maintainer; the budget fix waits on
   the maintainer's ruling and is NOT implemented here.

   > **What this supersedes, precisely (orchestrator's gloss on the operator's verbatim text
   > above, not itself operator text):** Decision 6 supersedes Decision 5's directive to
   > implement the governance-context budget fix in-mission — the round-2 HALT on the ADR
   > 2026-07-28-1 conflict (see the "SUPERSEDED (Operator Decision 6...)" call-out below) is
   > resolved by dropping FR-005/006/007 from scope, not by ruling on the ADR trade-off itself.
   > ADR 2026-07-28-1 stays Accepted and unmodified — nothing here ratifies eroding its
   > requires-eager inline guarantee. Decisions 1-5 otherwise stand unmodified as history, the
   > same pattern already used above where Decision 4 superseded part of Decision 3/FR-001's
   > mechanism while leaving the rest of Decision 3 intact. The confirmed diagnosis this
   > investigation produced (research.md § 9) is preserved as a historical/evidence-trail
   > record, not discarded — it is exactly what the orchestrator hands the maintainer.

7. **Slim PR (2026-09-26, binding, supersedes Decision 4/FR-001 and Decision 3's
   campsite-clean framing of the override deletion):**

   > (7) Slim PR: merge main into the branch, drop FR-001 (superseded by #5133), re-spec/re-plan
   > lightly, ship FR-002 advisory doctrine + the research.md measurements in one small PR that
   > closes #5005. Post the ADR-proposal comment when the PR opens.

   > **What this supersedes, precisely (orchestrator's gloss on the operator's verbatim text
   > above, not itself operator text):** between Decision 4 (2026-09-26) and this Decision 7
   > (2026-09-26, later the same day), upstream PR #5133 ("feat(doctrine): criterion delivery
   > labels + acceptance-criteria-non-vacuity review tactic," merged 2026-09-26T19:56:16Z into
   > `main`) resynced ALL 10 stale `.kittify/overrides/missions/software-dev/command-templates/`
   > files — including `analyze.md` — to byte-parity with their canonical counterparts, and added
   > a new gate, `tests/cross_cutting/test_kittify_override_parity.py`, asserting byte-identity
   > for every file under that override tree against its canonical counterpart (three named
   > orphan exceptions: README.md, constitution.md, dashboard.md, which have no counterpart).
   > This branch has since merged `origin/main` @ `34b53d78e` (which includes #5133), and the
   > orchestrator independently re-verified, on this checkout, right now (2026-09-26): all 10
   > overrides are byte-identical (`cmp -s`) to their canonical counterparts, and
   > `.kittify/overrides/missions/software-dev/command-templates/analyze.md` is 11,555 bytes,
   > identical byte-for-byte to canonical `packs/built-in/missions/mission-steps/software-dev/analyze/prompt.md`
   > (also 11,555 bytes). Deleting the override file now would not change what any agent
   > resolving `analyze` reads (the bytes already match canonical) — it would only remove a file
   > `test_kittify_override_parity.py`'s own mapping/enumeration logic currently accounts for,
   > which is a regression risk to a gate this mission did not add, not a behavior change worth
   > taking that risk for. **Decision 7 therefore drops FR-001 as a build item entirely**
   > (superseded, not merely re-mechanized the way Decision 4 superseded Decision 3's
   > byte-for-byte-copy approach with deletion) — there is nothing left for FR-001 to safely do.
   > It also **drops Decision 3's "domain-matched campsite-clean commit" framing** for the
   > override, since there is no override-deletion commit left to be that campsite-clean first
   > commit (see the "Campsite-clean framing" note in Dependencies & Sequencing below for whether
   > any other domain-matched debt fills that role — it does not). Decisions 1, 2, 3 (except its
   > FR-001/campsite-clean framing, now superseded by this decision), 5, and 6 stand unmodified
   > as history. Decision 4 is itself now superseded by this decision (kept as history, not
   > deleted from the record, marked in place by the inline "(Superseded by Operator Decision
   > 7...)" note now added directly on item 4 above — the same inline-marker convention
   > FR-001's table row above already uses, not the literal "### SUPERSEDED" heading
   > convention used below for Decision 5/6's superseded diagnosis content, since Decision 4 is
   > a numbered list item rather than a `###`-headed section and a literal banner heading
   > doesn't fit that slot). Decision 6's ruling on FR-005/006/007 (governance-context
   > budget fix dropped to maintainer) is untouched by this decision — Decision 7 only concerns
   > FR-001/Decision 4's override-deletion mechanism, not the governance-context budget question
   > Decision 6 already settled. This mission's remaining scope is FR-002 (advisory doctrine) +
   > FR-003 (measurements, already delivered) + the FR-004 constraint, re-detailed in "Remaining
   > scope after Operator Decision 7" below.

8. **All 4 citing profiles (2026-09-27, binding, retroactively authorizes the WP01 rework's
   `implementer-ivan.agent.yaml` edit and supersedes that edit's own self-authorization):**

   > (8) All 4 citing profiles: Decision 8 authorizes editing all four profiles that cite
   > DIRECTIVE_044 (architect-alphonso, implementer-ivan, doctrine-daphne, python-pedro). Wider
   > reach, still no orchestrator reach; bigger shared-file blast radius.

   > **What this supersedes, precisely (orchestrator's gloss on the operator's verbatim text
   > above, not itself operator text):** the WP01 rework (2026-09-27, pre-dating this decision)
   > edited `packs/built-in/agent_profiles/implementer-ivan.agent.yaml`'s DIRECTIVE_044 citation
   > `rationale` on its own authority, citing only the pre-merge squad's `pr-contract-001`
   > finding — not a numbered Operator Decision, unlike every other material scope change in
   > this mission's history (WP01-C2-002, cycle-2 rejection). Decision 8 retroactively supplies
   > that missing authorization for the `implementer-ivan` edit already shipped, and separately
   > authorizes extending the identical rationale-clause addition to the other three shipped
   > profiles that also cite DIRECTIVE_044 via `directive-references` —
   > `architect-alphonso.agent.yaml`, `doctrine-daphne.agent.yaml`, and `python-pedro.agent.yaml`
   > (the full set, confirmed via `grep -rl 'code: "044"' packs/built-in/agent_profiles/`) — plus
   > their shared regenerated `packs/built-in/pack-manifest.yaml` content hashes. It does **not**
   > authorize reach into the mission-level orchestrating agent (the null-`agent_profile` mission
   > steps — `analyze`/`specify`/`plan`/`tasks`/`review`/`accept`); that residual gap
   > (WP01-C2-003) remains open and out of this mission's authorized scope, per Decision 7's
   > binding prohibition on renderer/CLI/`prompt.md` changes. This decision widens FR-002/SC-002's
   > file set but does not reopen Decisions 1-7, which stand unmodified.

## Confirmed diagnosis (full detail in `research.md`)

The issue's own framing does not survive live measurement on this checkout (`main` @
`da6d0af97`, `.venv/bin/python` render of `runtime.next.prompt_builder.build_prompt`):

- **`analyze/prompt.md` is not oversized.** Canonical: 11,555 B / 245 lines — smaller than 7 of
  the other 11 sibling command templates (`specify` 46.8 KB is 4x larger). The resolved
  template for THIS checkout is the stale project-local override (6-tier resolver, OVERRIDE
  tier wins), which is smaller still (6,988 B).
- **The full rendered payload an agent actually receives** for `analyze` — mission-context
  header + injected governance/charter context + resolved template body, measured through the
  real `build_prompt()` entry point — is **11,891 bytes / 305 lines / ~2,973 estimated
  tokens** (measured 2026-09-26 with the stale override still in place, before FR-001's
  deletion — see the honest post-deletion figure below). This is not large by any LLM-context
  standard. **Correction (factual, does not change the diagnosis or any decision — full
  corrected table in research.md § 4):** analyze is not "the smallest of 8 actions
  measured except for `accept` and `research`," as an earlier draft of this spec claimed.
  `accept` renders 8,112 B and `research` renders 8,952 B, both smaller than analyze's 11,891 B
  — analyze is the **third-smallest** of the 8 actions measured, still roughly 8.2x–9.4x
  below the 97,175–112,248 B group of five (97,175 / 11,891 ≈ 8.2x; 112,248 / 11,891 ≈ 9.4x).
  **Wording fix (documentation-accuracy only, does not change the diagnosis or any
  decision):** an earlier draft of this sentence said "an order of magnitude," which
  overstates the actual ratio; the ratio above is computed the same way the surrounding
  text already computes its own ratios (see the post-deletion sentence immediately below,
  unchanged). **Honest post-deletion figure:** the 11,891 B
  figure above was measured while the stale override (6,988 B template) resolved. Once FR-001
  deletes that override, canonical resolves instead (11,555 B template — larger than the
  override), so the post-deletion rendered total is larger, not the same:
  **16,458 bytes / 367 lines / ~4,115 estimated tokens** (orchestrator-measured 2026-09-26;
  method and provenance in research.md § 4). This remains roughly 6x–7x smaller than
  the 97,175–112,248 B group (97,175 / 16,458 ≈ 5.9x; 112,248 / 16,458 ≈ 6.8x) and well within
  normal LLM-context standards — the correction does not change the diagnosis or any decision.

  > **Correction (factual, merged-branch re-measurement per Operator Decision 7, 2026-09-26 —
  > does not change the diagnosis or any decision): the "post-deletion" figure above never gets
  > realized by a deletion, because Decision 7 drops FR-001 — but it is also no longer merely a
  > projection.** Between the "honest post-deletion figure" paragraph above being written and
  > this correction, upstream PR #5133 (merged 2026-09-26T19:56:16Z into `main`, now in this
  > branch after `origin/main` @ `34b53d78e` was merged in) resynced the analyze override to
  > canonical's exact bytes. The orchestrator re-ran research.md § 4's own `build_prompt()`
  > script, unmodified, on this merged checkout, right now (2026-09-26; script staged outside
  > this repository, `git status --porcelain` confirmed clean before and after). **Result for
  > `analyze`: 16,458 bytes / 367 lines / ~4,114.5 estimated tokens (rounds to the same ~4,115
  > figure already on record)** — this is not a new number arrived at by a different method; it
  > is the exact same figure the "honest post-deletion figure" paragraph above already
  > projected, now independently reproduced as a live measurement rather than a projection.
  > **Why the numbers land on the same figure despite no deletion occurring**: the override file
  > still exists (Decision 7 does not delete it) and `resolve_command("analyze.md", repo_root,
  > mission="software-dev")` still reports `tier=override` — but its content is now
  > byte-identical to canonical (both 11,555 B, confirmed via `cmp -s` and `wc -c`), so
  > resolving through the override tier today renders the identical bytes resolving through
  > `package_default` would have rendered post-deletion. The 11,891 B figure above (measured
  > pre-#5133-merge-into-this-branch, stale 6,988 B override) is now superseded by this measured
  > 16,458 B figure as the accurate figure for what an agent resolving `analyze` in this checkout
  > receives today — not because FR-001 executed, but because #5133 already delivered the same
  > byte-content outcome FR-001 would have. This correction does not change the diagnosis (the
  > analyze render remains small — the third-smallest of the eight actions, same ~6x–7x-below-
  > the-large-group ratio already computed above) or any decision; it only updates which of the
  > two historical figures (11,891 B vs. 16,458 B) is now the live, current one.
- **The governance/charter-context overhead is real and wildly non-uniform by action — but
  `analyze` is in the small group, not the large one.** `analyze`, `accept`, and `research`
  each carry ~4,903 bytes of injected governance context. `specify`, `plan`, `tasks`,
  `implement`, and `review` each carry **81,000–95,000 bytes** of injected governance context
  — 17–19x more than `analyze`. If a prompt-size pressure is driving canonical-surface bypass
  anywhere in this codebase, the measured evidence points at those five actions, not at
  `analyze`.
- **Root cause of the reported behavior, as best determined**: the reporting agent's "very
  large skill prompt" claim is not reproducible against `analyze`'s measured render path. It
  either refers to a different, out-of-repo surface (e.g. the `~/.hermes/skills/sk-design/`
  doctrine document a Claude-harness orchestrator loads to drive the analyze phase — outside
  this repository's canonical sources and out of this mission's remit) or — the defect this
  mission can and does fix — the agent **never attempted to load or measure** the prompt
  before deciding to route around it. The charter's existing canonical-sources doctrine
  (`DIRECTIVE_044`, `canonical-source-unification` tactic) has no rule addressing a bypass
  driven by an *unverified size assumption*; it only covers split-brain surfaces and missing
  commands. This is the gap FR-002 below closes.

### SUPERSEDED (Operator Decision 5, 2026-09-26): what this section originally argued

The two subsections immediately below this banner are kept verbatim as a historical record —
this is what the spec-phase squad reviewed and passed in round 1–3 — but their conclusion no
longer holds. They argued (a) proportionality (issue #5005 was evidenced against `analyze`
only) and (b) file-level collision risk with open PR #5009, and on that basis deferred the
`specify`/`plan`/`tasks`/`implement`/`review` governance-context fix to a follow-up issue
(FR-005 as originally written). **Operator Decision 5 (2026-09-26) explicitly overrides that
call and folds the fix into this mission, accepting the collision risk.** Investigation
(research.md § 9) additionally found that reason (b) does not actually apply to the fix as
scoped: the confirmed seam (`src/charter/activation/context_renderers/token_budget.py` +
`bootstrap_text.py`) shares zero files with PR #5009's diff (verified via `gh pr diff 5009` —
#5009 touches `src/runtime/next/prompt_builder.py`'s `_governance_context` **call sites**,
threading an `effective_root` parameter through, but never touches
`src/charter/activation/context_renderers/*.py` or `src/charter/activation/context.py`). See
FR-005/006/007 and the reconciled NFR-003/C-002 below for the current, binding scope **as of
round 2** — since further superseded by Operator Decision 6 immediately below, which drops
FR-005/006/007 from this mission's scope entirely; see "Known residual (out of scope):
governance-context budget gap" after the newly-collapsed historical section for the actual
current, binding scope.

<details>
<summary>Historical text (superseded, kept for audit trail — do not re-implement from this)</summary>

#### Explicit call-out: what remedy scope (2) genuinely cannot absorb in this mission

The `specify`/`plan`/`tasks`/`implement`/`review` governance-context disparity (81–95 KB vs
`analyze`'s 4.9 KB) is a real, larger, previously-undocumented systemic finding. It does **not**
require a new CLI entrypoint (so it does not trigger the Operator Decision (2) escape hatch as
literally worded), but this mission does **not** fold a fix for it in, for two reasons that
belong in their own labeled call-out per the mission brief:

1. **Proportionality.** Issue #5005 was filed and evidenced against `analyze` specifically.
   The measured disparity is real but sits in five *other* actions; fixing it is a materially
   larger change than anything `analyze` was ever shown to need.
2. **File-level collision risk.** Fixing it means editing
   `src/runtime/next/prompt_builder.py::_governance_context` and/or the charter action-scoped
   resolution it calls (`charter.activation.scope_router.build_with_scope`,
   `charter.activation.context.build_charter_context`). `prompt_builder.py` is **actively
   touched by open PR #5009** ("fix: retain validated owned checkout authority across mission
   lifecycle," confirmed OPEN); the charter template-resolution family it depends on is
   touched by open PR **#4995** ("fix(charter): make concurrent mission-template resolution
   thread-safe," confirmed OPEN). Editing this file now would collide with #5009's in-flight
   changes and require re-verifying the NFR-001 byte-stability contract the module's own
   docstring calls out, across five actions — out of proportion for this mission.

**This is not left as an unenforced recommendation.** DIRECTIVE_052 (Prefer Durable Fixes,
activated in this repo's charter) requires a deferred structural cause to be recorded as a
tracked follow-up behind an umbrella/epic issue naming the root cause, not dropped as prose —
see **FR-005** below, which binds the orchestrator to file that issue (naming the root cause,
affected actions, measured magnitude, and the `#5009` sequencing dependency) before mission
wrap-up and to record the resulting issue number in "Dependencies & Sequencing."

</details>

### SUPERSEDED (Operator Decision 6, 2026-09-26): the fix plan below is not implemented in this mission

Decision 6 (2026-09-26, binding) keeps ADR 2026-07-28-1 intact and drops FR-005/006/007
from this mission's implementation scope, deferring the governance-context budget fix to
the upstream maintainer. The investigation, byte arithmetic, and ADR-conflict analysis
below are kept verbatim as the historical/evidence trail this mission hands to the
maintainer — not as a build plan for this mission. See "Known residual (out of scope):
governance-context budget gap" immediately below for the current, binding scope.

<details>
<summary>Historical text (superseded, kept for audit trail — do not re-implement from this)</summary>

### Confirmed root cause and fix plan for the governance-context disparity (Operator Decision 5)

Full measurement in `research.md` § 9. Summary of what is now confirmed (not modelled):

- **The 81–95 KB rendered payload is not a stable property of these five actions — it is a
  one-time-per-checkout "first load" spike.** `_governance_context()` routes
  `specify`/`plan`/`implement`/`review` (and, via a declared DRG action node rather than the
  hardcoded set, `tasks`) through a "bootstrap" render exactly once per action **per
  repository checkout** — tracked in `.kittify/charter/context-state.json`, a file this repo's
  own `.gitignore` (line 90) marks local/untracked. Once an action is marked loaded there, every
  subsequent render of that same action in that same checkout falls back to a small (8.0–12.6 KB
  — live-measured, this checkout, 2026-09-26: specify=8,002 B, plan=8,308 B, tasks=8,354 B,
  implement=12,614 B, review=12,492 B; **not** the ~4.5–4.9 KB figure, which applies only to
  `analyze`/`accept`/`research`'s unrelated `build_non_bootstrap_context_result` path, never to
  these five bootstrap actions' post-first-load compact render — see research.md §9.7.3) "compact"
  render forever. `analyze`/`accept`/`research` never take this path at all (no
  declared DRG action node for them under `software-dev`), which is why they were never large.
  Practical consequence: every fresh clone, every new mission worktree, and CI all pay the full
  81–95 KB cost again on first touch — this is not a one-time historical cost that has already
  been paid off.
- **A budget-enforcement mechanism already exists and already runs, but has a coverage gap.**
  `src/charter/activation/context_renderers/token_budget.py` defines `BUDGET_DEFAULT = 40_000`
  (characters) and `_enforce_token_budget`, which substitutes the longest sections for
  fetch-and-pull stanzas until the render fits — and it **is** firing (the measured renders
  each carry a `# Governance payload: N sections substituted with fetch commands (budget=40000).`
  trailer). Live measurement with a cleared first-load state (research.md § 9) shows exactly
  why it still leaves 81,476–95,139 bytes on the table: `_enforce_token_budget`'s candidate
  collectors (`_collect_section_block_candidates`, `_collect_profile_block_candidates`,
  `_collect_selection_block_candidates`) only ever look at three pre-rendered strings
  (`section_block`, `profile_block`, `selection_block`). The "Action Doctrine" block — the
  resolved directive/tactic/styleguide/toolguide/procedure bodies rendered by
  `_render_action_doctrine_lines` in `bootstrap_text.py` — is assembled directly into the final
  text and is **never** offered to the budget enforcer as a candidate, even though it is the
  dominant contributor: 69,261 of 93,799 bytes (~74%) for `review`; 70,598 of 95,139 (~75%) for
  `implement`; 57,772–59,727 of 81,476–83,431 bytes (~71–72%) for `specify`/`plan`/`tasks`. The
  ~23.7–24.5 KB portion that IS budget-covered is already fully substituted (every eligible
  candidate swapped) before Action Doctrine is even added — so the enforcer is not failing to
  try; it is structurally blind to three-quarters of the render.
- **The "budget enforced" trailer is misleading as currently worded.** It reports a
  substitution *count*, not whether the budget was actually met. An operator reading
  `# Governance payload: 11 sections substituted with fetch commands (budget=40000).` on a
  93,799-byte render (2.3x over budget) has no signal from that line alone that the budget was
  missed by 53,799 bytes. FR-006 below closes this.
- **Chosen fix seam and why:** `src/charter/activation/context_renderers/token_budget.py` (extend
  the candidate collectors to also draw from the Action Doctrine body list) and
  `src/charter/activation/context_renderers/bootstrap_text.py` (thread those bodies through as
  `RenderedSection` candidates before calling `_enforce_token_budget`). **Not**
  `src/runtime/next/prompt_builder.py`. This is the right seam on the merits — it is where the
  confirmed defect lives, not merely a PR-#5009-avoidance move — and it happens to also carry
  zero file-level overlap with PR #5009's diff (`gh pr diff 5009`, checked; see the reconciled
  NFR-003/C-002 below). No new CLI command, subcommand, or schema change is required: this is an
  internal rendering-algorithm change to an existing function using its existing
  `RenderedSection`/fetch-stanza substitution contract. **Operator Decision (2) is therefore
  satisfied without invoking its escape hatch.**
- **Honest residual, confirmed by measurement, not merely hedged:** this fix closes the
  *coverage gap* in budget enforcement — and, doing so, it necessarily makes the
  requires-closure entries themselves budget-substitutable. Today, `_extend_named_artifact_lines`
  (`bootstrap_text.py`) already renders a DRG-`suggests`-only artifact (outside the
  requires-closure) as a one-line id/title stub plus a fetch stanza (D2c/WP15's progressive
  disclosure), while a requires-closure member renders its id/title/summary line unconditionally,
  with no `RenderedSection` wrapper and no `substitutable` flag at all — it is not "pinned
  `substitutable=False`" so much as simply never offered as a candidate. FR-005 closes exactly
  that gap: it threads each Action Doctrine artifact's rendered line through
  `_enforce_token_budget` as a candidate, at the same per-artifact granularity the D2c
  suggests-path already uses, so under budget pressure a requires-closure member degrades to the
  identical stub-plus-fetch-stanza shape a suggests-only member already gets. **This directly
  contradicts the prior round's framing** ("the requires-closure alone... substitutable=False...
  never swapped") — that framing described the *problem* FR-005 fixes, not a property that
  survives the fix. Nothing in the Action Doctrine block is exempt from substitution after this
  fix except the `Action Doctrine (<action>):` heading itself and the bare `- id: title` stub a
  substituted entry keeps (FR-007 requires the selector to stay visible).

  **Byte arithmetic against research.md §9.2's measured figures (does SC-005's original
  ≤40,000-byte target hold once every Action Doctrine candidate is exhausted?):** research.md
  §9.2's "before Action Doctrine" portion (23,703-24,540 bytes) is already fully substituted at
  baseline — it is not a source of further savings. Re-measured for this fix (2026-09-26, this
  checkout, `.kittify/charter/context-state.json` cleared and restored byte-for-byte — see
  research.md §9.2/§9.7) with every Action Doctrine entry forced through the same
  stub-plus-fetch-stanza path FR-005 adds as a candidate (the maximal exhaustion case — every
  eligible candidate swapped, exactly the FR-006 "still over budget after every substitution"
  case), the floor each action's render can reach is:

  | Action | Pre-fix baseline (bootstrap) | Post-fix floor (every AD candidate swapped) | Reduction | ≤ 40,000? |
  |---|---:|---:|---:|---|
  | specify | 81,476 B | 61,208 B | -20,268 B / -24.9% | No |
  | plan | 82,707 B | 61,808 B | -20,899 B / -25.3% | No |
  | tasks | 83,431 B | 63,000 B | -20,431 B / -24.5% | No |
  | implement | 95,139 B | 70,434 B | -24,705 B / -26.0% | No |
  | review | 93,799 B | 70,380 B | -23,419 B / -25.0% | No |

  **SC-005's original ≤40,000-byte target is therefore NOT achievable as scoped, for any of the
  five actions, purely by extending the budget enforcer's candidate coverage** — confirmed by
  measurement, not merely a hedged "for some action" possibility. Even in the maximal-exhaustion
  case (every Action Doctrine entry reduced to a bare id/title stub + fetch stanza, nothing left
  to swap), every action lands 1.5x-1.76x over `BUDGET_DEFAULT`. The residual is a genuine
  DRG-curation question — the `software-dev` action nodes' `requires`-closures name more
  artifacts than can ever fit under 40,000 characters even fully stubbed, independent of how
  honestly the renderer reports it — and DRG-curation (re-classifying some `requires` edges to
  `suggests`) is explicitly out of this mission's remit (it is a content-authoring decision,
  not a rendering-algorithm change). **SC-005 and FR-005's Falsifiable target are revised below**
  to the achievable claim (a ~24.5%–26.0% reduction, landing at ≤72,000 bytes, not ≤40,000)
  rather than leaving an unreachable target in this spec; FR-006's honestly-worded trailer is
  precisely how the remaining over-budget condition is surfaced rather than hidden.

- **ADR 2026-07-28-1 conflict — confirmed, NOT resolved by this round, operator ruling required
  (flagged by SPEC-R2-FRESH-001, investigated here rather than dismissed):** the "Honest
  residual" bullet above establishes that FR-005 closes the coverage gap by making every
  requires-closure entry in the Action Doctrine block budget-substitutable — degrading it, under
  pressure, to the identical stub-plus-fetch-stanza shape `_extend_named_artifact_lines` already
  gives a `suggests`-only entry. That mechanism is investigated here against
  `docs/adr/3.x/2026-07-28-1-progressive-disclosure-of-doctrine-context.md` (status: Accepted,
  Operator-ruled 2026-07-28) — the ADR this repo's own code cites as the authority for exactly
  this requires/suggests split (`src/charter/activation/progressive_disclosure.py`'s module
  docstring: "Progressive disclosure of doctrine context (WP15, ADR 2026-07-28-1)"; this
  mission's own `_render_action_doctrine_lines` docstring in `bootstrap_text.py`: "D2c:
  directive/tactic/styleguide/toolguide entries follow the same requires-eager / suggests-linked
  cadence WP15 already applies to the `--json` payload").

  **What the ADR actually says (read in full, not just the Decision bullet, to settle whether it
  governs literal representation or only inclusion):** Decision item 2 states, verbatim: "`requires`
  edges are followed eagerly and their targets delivered inline. A required artefact is
  unconditional; there is no 'when' to evaluate, and 87% of `requires` edges carry no guidance
  text because none is needed" — and separately: "**This is the default cadence, not an opt-in
  mode.** An earlier draft of this ADR deferred the default change on blast-radius grounds.
  Operator ruling, 2026-07-28: that is backwards, and the deferral is withdrawn." The Rationale
  section confirms this is about literal representation, not merely whether an artefact is
  reachable at all: "Bodies are fetched, not omitted. The distinction matters: truncation removes
  an artefact from an agent's awareness; a link keeps it addressable" — `requires` is contrasted
  against `suggests` throughout as "delivered inline" (full body) versus "emitted as links"
  (fetch-and-pull pointer), never as two ways of expressing the same inclusion decision. The
  codebase's own pre-existing implementation independently confirms the same reading:
  `progressive_disclosure.requires_closure`'s docstring says "`requires` is unconditional — a
  required artefact is delivered inline with no 'when' to evaluate (ADR: cadence follows the
  relation, C-011)," and — before this mission's fix — `_render_action_doctrine_lines` in
  `bootstrap_text.py` renders a requires-closure member's "id/title/summary line
  unconditionally, with no `RenderedSection` wrapper and no `substitutable` flag at all," while
  only a `suggests`-only artifact ever gets the fetch-stanza treatment. So the answer to "does the
  ADR forbid representing required content as a fetch-stanza, or only care whether it's
  included": it is squarely the former — the ADR's "eager" guarantee is about the literal
  rendered shape (full body vs. pointer), not merely about resolution-time inclusion.

  **FR-005 as currently scoped removes that guarantee.** It moves every requires-closure Action
  Doctrine entry from "always full inline body" to "fetch-stanza-swappable under budget
  pressure" — exactly the treatment the ADR reserves, by name, for `suggests` edges only.
  **Operator Decision 5 does not authorize this.** Its verbatim text above reads: "FOLD INTO THIS
  MISSION. Fix the 81–95 KB governance-context injection ... **accepting collision risk with open
  PR #5009**." That decision scopes the accepted risk to the #5009 file-collision question; it
  says nothing about waiving ADR 2026-07-28-1's requires-eager inline guarantee, and no separate,
  ADR-scoped operator ruling exists anywhere in this mission's record.

  **This is left as an open decision point requiring operator input — not silently resolved
  either way.** Two paths forward, either of which needs the operator's explicit word before
  FR-005 can be implemented as currently written:
  1. Obtain an explicit operator ruling that accepts eroding ADR 2026-07-28-1's requires-eager
     inline guarantee under budget pressure specifically, recorded as a supersession note on that
     ADR (or a new ADR) — not merely as prose in this spec.
  2. Redesign FR-005 so it does not touch requires-closure eagerness at all — extend substitution
     only to whatever `suggests`-reachable Action Doctrine content remains uncovered. Per this
     section's own byte arithmetic, the non-Action-Doctrine budget-substitutable portion
     (~23.7–24.5 KB) is already fully exhausted at baseline before Action Doctrine is even
     considered, so this path very likely reclaims **zero further bytes**, meaning SC-005's
     ≤72,000-byte target — and any reduction beyond the pre-fix 81,476–95,139-byte baseline —
     becomes unreachable by a rendering-algorithm-only fix, reverting to the ORIGINAL, narrower
     "Honest residual, narrowly scoped" framing this round-4 diff replaced (a DRG-curation-only
     residual, explicitly out of this mission's remit).

  **This mission does not pick between (1) and (2).** FR-005/FR-006/FR-007/SC-005 below still
  describe the round-4 design — path (1)'s consequence if and only if the operator ratifies it —
  so the byte arithmetic and fetch-reachability requirements are on record either way, but
  implementation of FR-005 as scoped must not proceed until this specific ADR trade-off, distinct
  from and not covered by Operator Decision 5's #5009-collision-risk acceptance, is resolved by
  the operator.

</details>

### Known residual (out of scope): governance-context budget gap

Per Decision 6, this mission does not implement the governance-context budget fix; ADR
2026-07-28-1 stays intact and unmodified. The confirmed diagnosis — the NFR-001 budget
enforcer (`_enforce_token_budget`) never sees the "Action Doctrine" block, which carries
71–75% of the 81,476–95,139 B oversized bootstrap render for
`specify`/`plan`/`tasks`/`implement`/`review`; the achievable ceiling by a
rendering-algorithm-only fix is a confirmed ~24.5%–26.0% reduction, landing around
70,000–72,000 bytes for the two largest actions (`implement`/`review`; the other three
land lower, around 61,000–63,000 bytes) — still well over the 40,000-character
`BUDGET_DEFAULT` — remains recorded as measured findings in research.md § 9. This is
a known, out-of-scope residual, not a defect this mission closes. FR-005/006/007, as scoped
in round 2, are dropped from this mission's scope per Decision 6 (their text survives
inside the collapsed historical section above, and in research.md § 9). The
orchestrator will post these measurements and an ADR-amendment proposal to spec-kitty#5005
for the upstream maintainer; the fix waits on that ruling.

**DIRECTIVE_052 compliance for this deferral:** DIRECTIVE_052 (Prefer Durable Fixes) requires a
deferred structural remediation to be recorded as a tracked follow-up behind an umbrella/epic
issue naming the root cause — its own procedures (step 1) distinguish that umbrella/epic from
the specific defect ticket under repair: "Identify an existing umbrella/epic that the class
belongs to, or propose one." #5005 is the specific, narrow ticket this mission's own
FR-002/FR-003 close out (FR-001 no longer executes per Operator Decision 7; filed and evidenced
against `analyze`'s prompt size specifically) — it is not a distinct umbrella/epic for the
five-action governance-context budget-gap class, so
keeping it open does not itself satisfy DIRECTIVE_052's umbrella/epic requirement, and #5005
closes normally on this mission's merge, per the ordinary issue-closing convention. Decision 6
(above) already commits the orchestrator to post the budget-gap measurements and an
ADR-amendment proposal "on #5005" for the upstream maintainer; this deferral satisfies
DIRECTIVE_052 because that same #5005 comment will itself **propose opening a new, distinct
tracked issue** naming the governance-context budget-gap root cause (the Action Doctrine
block's exclusion from the NFR-001 budget enforcer's candidate coverage) as the umbrella/epic
DIRECTIVE_052 actually requires — rather than relying on #5005, which closes on merge, to serve
double duty as its own umbrella. This does not change Decision 6's scope: Decision 6 commits
only to posting on #5005, and proposing a new umbrella issue inside that post is consistent with,
not an addition to, that commitment.

### Known residual (out of scope): mission-level orchestrating agent never receives this warning

Added 2026-09-27 (round-2 rework, WP01-C2-003, severity 2, advisory). FR-002's fix — the
DIRECTIVE_044 citation `rationale` clause, now on all four DIRECTIVE_044-citing profiles per
Operator Decision 8 — renders only when a work package's frontmatter names one of those four
profiles as `agent_profile` (confirmed via `src/runtime/next/prompt_builder.py::_governance_context`,
which forwards the WP frontmatter's `agent_profile` field as the `profile=` kwarg to
`build_charter_context`) — i.e. only for downstream WP-implementation work done under one of
those profiles. The mission-step contract for the action that was actually bypassed in the
evidenced trace, `packs/built-in/missions/mission-steps/software-dev/analyze/step.yaml`, carries
`agent_profile: null`, so no profile-citation channel — this fix or any other doctrine reachable
only via a profile's `directive-references`/`tactic-references` — reaches the top-level
orchestrating agent that decides whether to invoke `/spec-kitty.analyze` at all. That decision is
exactly the one the evidenced trace documents
(`kitty-specs/mission-state-audit-trail-durability-01M37PWG/traces/tooling-friction.md`: "the
orchestrating agent's own words were: 'Let me check for a direct analyze entrypoint to avoid
loading the very large skill prompt'"). This spec does not overclaim beyond "any agent operating
under one of the four DIRECTIVE_044-citing profiles" — it never claims analyze-step or
orchestrator-level reach — and Decision 7's binding remedy forbids the renderer/CLI/`prompt.md`
changes that would be needed to actually close the orchestrator-level gap, so it is currently
structurally unfixable within this mission's authorized scope. **The orchestrator will note this
residual gap explicitly on spec-kitty#5005** when this mission's PR opens, alongside the
governance-context budget-gap note above, so the maintainer sees it rather than it being silently
dropped. No action is required of this mission's WP01 beyond recording it here; a future
doctrine/renderer mission would need to either give the `analyze` (and other null-`agent_profile`)
mission steps a profile whose citations can carry this warning, or otherwise accept the gap.

### Remaining scope after Operator Decision 7 (2026-09-26)

Per Decision 7, this mission's actual remaining build scope is narrower than any prior round
described. Stated explicitly so no reader has to reconstruct it from the supersession trail
above:

- **FR-002 (advisory doctrine entry + `spec-kitty doctrine regenerate-graph` write-mode
  companion + its named architectural tests) is the only real build item left.** It is
  unaffected by Decision 7 — Decision 7 concerns only FR-001's override-deletion mechanism, not
  the advisory-doctrine fix. See "FR-002 target-file re-check" note at C-002 below for
  confirmation that its target files (`packs/built-in/tactics/canonical-source-unification.tactic.yaml`,
  `packs/built-in/directives/044-canonical-sources-and-unification.directive.yaml`) still exist
  and are unaffected in content by #5133 on this merged checkout.
- **FR-003 (measurements) is already done** — referenced, not re-built. The "Confirmed
  diagnosis" section's correction above updates the live figures; research.md's dated addendum
  (§ 10) records the same re-measurement.
- **FR-004 (do not edit `analyze/prompt.md`'s content/size) is restated, not weakened**: no edit
  to `analyze/prompt.md`'s content or size in **either** canonical or override form — and the
  override-edit prohibition is now load-bearing in a new way. #5133's new gate,
  `tests/cross_cutting/test_kittify_override_parity.py`, fails if this repo's override is ever
  edited to diverge from canonical, so "don't touch the override" is now doubly reinforced: once
  by FR-004's original rationale (nothing here is oversized, so there is nothing to fix by
  editing it), and again by a gate this mission did not author but must not trip.
- **FR-005/006/007 (governance-context budget fix) stay out of scope per Decision 6, unchanged
  by Decision 7.** Decision 7 does not touch Decision 6's ruling at all — the two decisions
  concern different parts of this mission (Decision 6: the governance-context budget fix that
  never shipped in-mission; Decision 7: the override-deletion mechanism that no longer executes)
  and should not be conflated. The maintainer-facing ADR-amendment proposal Decision 6 commits
  the orchestrator to post on #5005 is unaffected by Decision 7 and still happens.
- **FR-001 no longer executes** (superseded per Decision 7 — see its row in the Functional
  Requirements table below and the Decision 7 supersession text above). No override-deletion
  commit lands in this mission's diff.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A future agent gains advisory doctrine against bypassing a canonical surface on an unverified size assumption (Priority: P1)

> **Restructured per Operator Decision 7 (2026-09-26):** this story previously had two halves —
> FR-001 (deleting the stale `analyze` override) and FR-002 (advisory doctrine). Decision 7 drops
> FR-001 as a build item (see the Decision 7 supersession text above and FR-001's row in the
> Functional Requirements table): upstream PR #5133 already resynced this repo's `analyze`
> override to canonical's exact bytes (both 11,555 B, `cmp -s`-confirmed) before this mission's
> own deletion could land, and added `tests/cross_cutting/test_kittify_override_parity.py`, a
> real, fast (`pytest.mark.fast`), currently-passing test that would flag the override diverging
> from canonical whenever it runs — but, per this repo's own `.github/ci-module-registry.yml`
> disposition, `tests/cross_cutting` has no per-PR CI lane; its only current automated execution
> home is the nightly `ci-nightly.yml` interpreter-matrix job (Python 3.13-only,
> `pytest -m "fast or unit"` over the whole tree) or a manual `make test-full` that no workflow
> invokes, so this is not a per-PR merge-blocking gate (see the Former Acceptance Scenario 2
> rationale under this story for the full citation). This repo's
> `analyze` surface therefore already resolves to canonical's content today — through the
> OVERRIDE tier, not `package_default`, but with byte-identical content — with no action this
> mission needs to take. **This story is now about FR-002 alone.**

This repo's `analyze` command-template surface already carries the same consistency checklist,
gate semantics, reporting shape, and `record-analysis` persistence step canonical ships, because
#5133's resync already delivered content parity (see the "Confirmed diagnosis" correction above
for the re-measured byte figures). What this mission still adds is advisory doctrine text
(FR-002) naming the evidenced failure mode this issue actually reports — an agent bypassing a
canonical prompt/skill/CLI surface on an unverified size assumption — for a future agent to
read. FR-002 is advisory-only prose with no automated enforcement (Acceptance Scenario 1); this
mission does not claim, and cannot test, that any future agent actually changes its
decision-making after loading it.

**Why this priority**: the evidenced failure mode (an agent that never measured `analyze`'s
prompt before deciding it was "too large" to load) needs explicit doctrine coverage even though
that coverage's effect on a future agent's behavior is not something this mission can verify
(FR-002, advisory-only). It remains P1 because it is the only build item this mission still
carries.

**Independent Test**: FR-002 is **advisory-only doctrine prose** — no automated test in this
repository can verify a future agent's prompt-*following* behavior against it (there is no
runtime hook, CLI check, or gate that consumes this doctrine text to alter an agent's
subsequent reasoning; that effect is not mechanically observable). **Corrected (2026-09-27,
WP01 rework + Decision 8 — supersedes the "no automated test can verify … reaches rendered
agent context" claim this paragraph previously made, which is now false):** a narrower but
real thing — whether the text actually *reaches* rendered agent-visible context, as opposed to
being followed once read — is mechanically testable and is now tested. This Independent Test
therefore verifies three things: (a) the new failure-mode entry exists verbatim in
`packs/built-in/tactics/canonical-source-unification.tactic.yaml` and/or
`packs/built-in/directives/044-canonical-sources-and-unification.directive.yaml`, and is
syntactically valid doctrine (passes the same YAML/DRG loading the pack already requires); (b)
the same failure-mode clause reaches real rendered profile-citation output for each of the four
shipped profiles that cite DIRECTIVE_044 — `architect-alphonso`, `implementer-ivan`,
`doctrine-daphne`, `python-pedro` (Decision 8) — verified by
`tests/doctrine/test_directive_consistency.py::test_size_assumption_bypass_failure_mode_reaches_rendered_profile_context`,
parametrized over all four, exercising the real `_render_profile_sections` render path (the
same one `build_charter_context`/`spec-kitty charter context` calls). **Corrected (2026-09-27,
WP01 cycle-3 fix, WP01-C3-001 / pr-FRESH2-001):** this was NOT uniformly "red before each
profile's rationale edit and green after" — `architect-alphonso` and `doctrine-daphne` were
genuinely red-before/green-after; `implementer-ivan` was already green from the round-1 rework;
and `python-pedro` was already green before this round's fix too, via `specializes_from`
lineage inheritance from `implementer-ivan` (`AgentProfileRepository.resolve_profile`'s
`_union_merge`, `src/charter/offering/agent_profiles/repository.py:190-204`, resolves a
same-`code` directive-references collision to the parent's entry, never the child's own) —
not because `python-pedro`'s own file's rationale said so at the time. (b′) A second test,
`test_size_assumption_bypass_failure_mode_in_each_profiles_own_source_file`, also parametrized
over all four profiles, closes the resulting gap by asserting directly on each profile's own
source YAML (bypassing `resolve_profile`), so a revert of any one profile's own hunk —
including `python-pedro`'s, which (b) alone cannot catch — is caught; and (c) no existing test
or gate regresses, including the DRG-freshness companion step FR-002 itself requires (see
FR-002's Status/notes). It does **not** and cannot test that an agent actually *changes its
behavior* after loading this text,
and it does **not** reach the mission-level orchestrating agent for
analyze/specify/plan/tasks/review/accept, whose step contract carries `agent_profile: null` —
that residual gap is recorded, not closed (WP01-C2-003; see "Known residual" below).

**Acceptance Scenarios**:

1. **Given** the new failure-mode entry has been added to
   `packs/built-in/tactics/canonical-source-unification.tactic.yaml` and/or
   `packs/built-in/directives/044-canonical-sources-and-unification.directive.yaml`, **When**
   the pack is loaded (`spec-kitty doctrine regenerate-graph --check` and the pack's own
   validation), **Then** the entry parses as valid doctrine and is present verbatim.
   **Corrected/extended (2026-09-27, WP01 rework + Decision 8):** this Scenario also covers a
   second, separately-verified condition — **Given** the same failure-mode clause has been
   appended to the DIRECTIVE_044 citation `rationale` of all four shipped profiles that cite it
   (`architect-alphonso`, `implementer-ivan`, `doctrine-daphne`, `python-pedro`), **When** each
   profile is rendered through the real `_render_profile_sections` charter-context render path,
   **Then** the clause is present in the rendered output for all four (proved red-before/
   green-after by
   `tests/doctrine/test_directive_consistency.py::test_size_assumption_bypass_failure_mode_reaches_rendered_profile_context`,
   parametrized over the four profiles). Together, these two conditions verify that the
   failure-mode text (i) exists as syntactically valid doctrine and (ii) actually reaches
   rendered agent-visible context for any agent operating under one of the four profiles — but
   **not** that any future agent's decision-making changes as a result, and **not** that the
   mission-level orchestrating agent (whose step contract carries `agent_profile: null`) ever
   sees it. This FR remains advisory-only with no behavioral-enforcement mechanism in this
   mission's scope (no new CLI, no `prompt_builder.py`/renderer edit); no automated test in this
   repository can verify — nor does this Scenario claim to verify — an agent's future
   prompt-*following* behavior against it, only that the text reaches rendered context.

> **Former Acceptance Scenario 2, removed per Operator Decision 7 — reasoning stated, not
> silently dropped:** it verified the FR-001 file-absence + `resolve_command` tier check
> (override deleted, resolution reaches `tier=package_default`). FR-001 no longer executes
> (Decision 7), so there is no deletion for this Scenario to verify. It is **removed entirely**,
> not rewritten to assert parity instead, because parity for this exact override is already
> covered by a test this mission did not author and does not own:
> `tests/cross_cutting/test_kittify_override_parity.py` (added by #5133, already merged into
> `main` and into this branch) enumerates every file under
> `.kittify/overrides/missions/software-dev/` — including `analyze.md` — and asserts byte
> parity against its canonical counterpart whenever that test file runs. Its content logic does
> not depend on this or any other mission's own scope. **This is real coverage, but it is not a
> per-PR merge-blocking gate.** The test itself is real, fast (`pytest.mark.fast`), and currently
> passing — but per this repo's own `.github/ci-module-registry.yml` disposition, the directory
> it lands in (`tests/cross_cutting`) has no per-PR CI lane; no per-PR module row in that
> registry claims it, `.github/workflows/module-tests.yml`'s per-PR shard selection never
> reaches it, and `.github/workflows/ci-router.yml`'s `tests-e2e` job — though its path-filter
> group globs `tests/cross_cutting/**` as a trigger — only ever runs `pytest tests/e2e -q` in its
> job body, never touching this file. Its only current automated execution home is the nightly
> `.github/workflows/ci-nightly.yml` `interpreter-matrix` job (schedule/`workflow_dispatch`
> triggers only — no `pull_request`/`push` trigger, so a PR event never starts it — Python
> 3.13-only, `pytest -m "fast or unit"` over the whole tree), or a manual `make test-full` that no
> workflow ever invokes. Duplicating this test's assertion as this mission's own Acceptance
> Scenario would test a check this mission touches zero bytes of, not behavior this mission
> delivers — the genuine coverage gap FR-001 used to fill (verifying the override matches
> canonical) is addressed by that test today whenever it runs, not closed or pinned in the
> per-PR-blocking sense: a future PR that reintroduced a divergence in the override would still
> merge, because this specific check never runs in that PR's own checks, and the divergence would
> surface only via the next nightly run (if that lane happens to catch it). **Non-scope
> follow-up, not built by this mission:** the maintainer could wire this test into a per-PR
> module's `test_dirs` in `.github/ci-module-registry.yml` to close that gap; this mission does
> not do so (Decision 6/7 do not expand this mission's scope to cover it).

---

### User Story 2 - A maintainer or future triage agent can trust prompt-size claims are measured, not asserted (Priority: P2)

A maintainer investigating a future "prompt too large" report can point to a documented,
reproducible measurement method (the `build_prompt()` render script in `research.md`) instead
of re-deriving byte counts from scratch or trusting an agent's self-report.

**Why this priority**: prevents this exact ambiguity (issue filed on an unverified claim) from
recurring for the next large-prompt report.

**Independent Test**: `research.md`'s measurement script is copy-pasteable and reproduces the
same relative ordering (analyze/accept/research small; specify/plan/tasks/implement/review
large) on a clean checkout at the same commit.

**Acceptance Scenarios**:

1. **Given** a future prompt-size complaint against any command, **When** a maintainer runs
   the documented `build_prompt()` measurement, **Then** they get an exact byte/line/token
   count instead of relying on an agent's self-reported impression.

---

### Edge Cases

> **Note on the four bullets below marked "(retired per Operator Decision 7)": FR-001 no longer
> executes** (see Decision 7 above and FR-001's Superseded row in the Functional Requirements
> table). Each was originally written to guard a deletion that is no longer part of this
> mission's scope. They are kept, marked retired in place, rather than silently removed, so a
> reader of this spec's history can see what was once guarded against and why it no longer
> applies — the same convention this spec already uses for retired bullets under Operator
> Decision 6.

- **(Retired per Operator Decision 7 — FR-001 no longer executes.)** What happens if the stale
  override reconciliation accidentally invents new finding-detection or severity-classification
  logic instead of adopting canonical's? This guarded against a *copy-then-diverge* risk from
  FR-001's original byte-for-byte-copy mechanism (superseded by Decision 4's deletion approach,
  itself now superseded by Decision 7's no-op). Since FR-001 makes no change at all now, there is
  no authoring surface, copy, or deletion for this bullet to guard — moot, not merely satisfied.
- **(Retired per Operator Decision 7 — FR-001 no longer executes.)** What happens if a downstream
  consumer project has no `.kittify/overrides/...analyze.md` at all? This bullet's substance (the
  override is a `spec-kitty`-repo-local dogfooding artifact, not something shipped to consumers)
  remains true as background fact, but it was framed around FR-001's effect on consumer
  projects; FR-001 has no effect on anything now, so the bullet's original question no longer
  has a live FR to answer it.
- What happens if the doctrine text added in FR-002 is itself perceived as "large"? It is a
  bounded addition (a failure-mode entry + one procedure line) to an existing, already-loaded
  artifact, not a new document — negligible marginal size against the ~4.9 KB `analyze`
  governance overhead already measured. **(Unaffected by Decision 7 — FR-002 is this mission's
  only remaining build item.)**
- **(Retired per Operator Decision 7 — FR-001 no longer executes.)** What happens to other
  missions in this checkout that are concurrently mid-`/spec-kitty.analyze` when FR-001
  **deletes** the override file? This entire bullet described a mid-flight-deletion hazard (an
  atomic-landing requirement, a "no intermediate half-deleted state" argument, and an
  operator-courtesy check for in-progress `analyze` steps before merging). None of it applies
  once there is no deletion: no file disappears out from under any concurrently-running mission,
  because this mission's diff never touches
  `.kittify/overrides/missions/software-dev/command-templates/analyze.md` at all.
- **(Retired per Operator Decision 7 — FR-001 no longer executes.)** **Read-only check (per
  mission brief): is anything else in the live codebase affected by the FR-001 deletion?** This
  bullet's grep-based blast-radius check (`grep -rl "overrides/missions/software-dev/command-templates" src/ packs/ docs/ tests/ scripts/`,
  4 hits found, none naming `command-templates/analyze.md`) was scoped to a deletion that no
  longer happens. There is no blast radius to check for a file this mission's diff does not
  touch.
- **(Operator Decision 6, 2026-09-26 — this bullet is retired.)** Per Decision 6, the governance-context budget fix (FR-005/006/007) is not implemented in this mission, so no mid-flight-mission edge case applies to it; see "Known residual (out of scope): governance-context budget gap" above.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | **(Rewritten per Operator Decision 4 — supersedes the byte-for-byte-copy approach of the prior round.) Superseded by Operator Decision 7, 2026-09-26 — #5133 already resynced this override to canonical byte-parity and added a parity gate; deleting it now would remove content a new gate depends on. See "Known residual" / "Remaining scope after Operator Decision 7" above.** Historical text (preserved verbatim, do not re-implement — this FR no longer executes): DELETE the stale `.kittify/overrides/missions/software-dev/command-templates/analyze.md` project override file outright so that resolving `analyze` in this checkout falls through the 6-tier resolver to canonical `packs/built-in/missions/mission-steps/software-dev/analyze/prompt.md` directly — full contract parity by construction, with no copy left in the repository to drift again. This is a stronger structural guarantee than the previous round's "byte-for-byte copy" approach (which still left a second file in existence that some future edit could silently re-diverge): deleting the shadow removes the drift surface entirely rather than merely re-synchronizing it once. Landed as a separate, first commit (campsite-clean framing per Operator Decision 3), atomically (see Edge Cases) — `git rm .kittify/overrides/missions/software-dev/command-templates/analyze.md`. | As a spec-kitty maintainer, I want this repo's own `analyze` resolution to not silently shadow canonical improvements — including the persistence contract the override is currently missing entirely — so that this repo's agents see exactly the same contract consumers get from canonical, permanently, instead of perpetuating the recurring `record-analysis` persistence/verdict-honesty defect class documented in the ledger (SK-06, SK-43, SK-47, SK-63, SK-141 @ L2780) or requiring a future review round to catch the override drifting again. | High | **Superseded** (Operator Decision 7 — #5133 already delivered byte-parity; this FR does not execute) |
| FR-002 | Add a new failure-mode entry (and/or procedure line) to the existing `packs/built-in/tactics/canonical-source-unification.tactic.yaml` and/or `packs/built-in/directives/044-canonical-sources-and-unification.directive.yaml` naming the evidenced failure mode explicitly: an agent must not bypass a canonical prompt/skill/CLI surface on an *unverified size assumption* — it must attempt to load/measure the surface first, and if genuinely oversized, file an upstream gap (Rule 3's existing pattern) rather than improvising a substitute. **Status/notes (corrected 2026-09-27 during WP01 rework, per the pre-merge squad's `pr-contract-001` finding — supersedes the original "adds text an LLM reads at prompt-render time" claim below, which overstated the delivery mechanism):** landing the text only in the tactic's `failure_modes` and/or the directive's `procedures` does **not**, by itself, reach an agent automatically. A tactic's automatic inline render is Name/Purpose/Steps only (`_format_inline_tactic_body`); both `canonical-source-unification`'s rendered body (~4.3K chars) and DIRECTIVE_044's rendered body (~3.5K chars) already exceed the 2,400-char per-artifact inline ceiling (`_PROFILE_INLINE_BODY_LIMIT_CHARS`, `token_budget.py`), so both fall back to a generic fetch-stanza pointer in every automatic render path (profile citation, global selection, Action Doctrine block) regardless of which file carries the new text — reachable only via an agent's own explicit `--include tactic:canonical-source-unification` / `--include directive:DIRECTIVE_044` fetch, not by default. The surface that DOES reach an agent automatically, independent of that per-artifact body budget, is the profile-citation header line: `_render_directive_entry` (`charter.activation.context_renderers.profile_sections`) appends a profile's own `directive-references[].rationale` for DIRECTIVE_044 to the citation's header line **before** the body/fetch-stanza budget check runs, so that rationale text always renders for any profile citing the directive. This mission's WP01 rework therefore *also* edits `packs/built-in/agent_profiles/implementer-ivan.agent.yaml`'s DIRECTIVE_044 citation `rationale` to name the failure mode explicitly — this is the actual, verified delivery path, proved by a real-rendered-output test (`tests/doctrine/test_directive_consistency.py::test_size_assumption_bypass_failure_mode_reaches_rendered_profile_context`) that exercises the shipped doctrine catalog through `_render_profile_sections` (the same profile-channel renderer `build_charter_context`/`spec-kitty charter context` calls for every action an agent under `implementer-ivan` performs), red before that profile edit and green after. **Extended (2026-09-27, round-2 rework, per Operator Decision 8 and cycle-2 findings WP01-C2-001/002):** the `implementer-ivan`-only edit was authorized only by this same rework's own spec.md text (citing `pr-contract-001`), not by a numbered Operator Decision — unlike every other material scope change in this mission's history — and it left the identical DIRECTIVE_044 citation on the other three shipped profiles that also carry it (`architect-alphonso`, `doctrine-daphne`, `python-pedro`; confirmed via `grep -rl 'code: "044"' packs/built-in/agent_profiles/`) unedited, so the failure-mode text reached agents under `implementer-ivan` only, not any agent under those other three profiles. Operator Decision 8 retroactively authorizes the `implementer-ivan` edit already shipped and additionally authorizes appending the identical clause (consistent with `implementer-ivan`'s wording) to all three remaining profiles' DIRECTIVE_044 citation `rationale`, so the failure mode now reaches rendered context for any agent operating under any of the four DIRECTIVE_044-citing profiles. This widens FR-002/SC-002's touched-file set to include `packs/built-in/agent_profiles/{architect-alphonso,doctrine-daphne,python-pedro}.agent.yaml` (plus the already-touched `implementer-ivan.agent.yaml`) and their shared regenerated `packs/built-in/pack-manifest.yaml` content hashes; see C-002 for the re-run sequencing/overlap check against this widened set, and the "Authorized scope beyond WP01's owned_files" note below C-002 for why `lanes.json`/WP01's `owned_files` frontmatter were not hand-edited to match. The tactic's `failure_modes` entry and any directive `procedures` line remain valid documentation but are not automatically delivered by any render path this mission traced. No automated test in this repository can verify a future agent's prompt-*following* behavior against this text once delivered; what is now tested and enforced is narrower but real: that the text actually reaches rendered agent-visible context in the first place, through the pre-existing `charter context` render path, rather than being silently confined to a fetch-stanza pointer or raw YAML no renderer reads — for all four DIRECTIVE_044-citing profiles, not implementer-ivan alone. This reach still does **not** extend to the mission-level orchestrating agent for analyze/specify/plan/tasks/review/accept, whose step contract carries `agent_profile: null` (WP01-C2-003, recorded as an open residual, not claimed as closed). Its Acceptance Scenario (User Story 1) verifies both that the failure-mode text exists (syntactically valid doctrine) and that it reaches this rendered surface for all four profiles.** **Required companion step (binding, do not skip regardless of default blast-radius calibration):** because this FR edits a DRG-source input (`packs/built-in/tactics/*.tactic.yaml` and/or `packs/built-in/directives/*.directive.yaml`, and — per the WP01 rework above — `packs/built-in/agent_profiles/implementer-ivan.agent.yaml`), after editing the target file(s) run `spec-kitty doctrine regenerate-graph` in WRITE mode (not `--check`) and commit the resulting `packs/built-in/pack-manifest.yaml`/`{directive,tactic}.graph.yaml` diff in the same commit; then confirm `spec-kitty doctrine regenerate-graph --check` exits 0, and that `tests/architectural/test_doctrine_regenerate_graph_roundtrip.py` and `tests/architectural/test_pack_manifest_no_author_edit.py` both pass. These are required tests for this FR's work package regardless of whether the change would otherwise be classified as doctrine-content-only and out of the default `tests/architectural/` blast radius. | As an orchestrating agent, I want explicit canonical doctrine covering "I assumed it's too big" bypasses, so that I do not silently under-apply a canonical command's contract the way the evidenced trace did. | High | Open |
| FR-003 | Document in `research.md` (this mission, already delivered) the reproducible `build_prompt()` render measurement across `analyze` and its 7 sibling actions, so a future prompt-size claim can be checked against real numbers instead of an agent's self-report. **Status/notes (falsification condition, mirroring FR-002's pattern): this FR's claim is falsified if User Story 2's Independent Test fails — i.e. if `research.md`'s measurement script is not copy-pasteable, or does not reproduce the same relative ordering (analyze/accept/research small; specify/plan/tasks/implement/review large) on a clean checkout at the same commit.** | As a maintainer, I want a documented measurement method, so future "too large" claims are verifiable. | Medium | Done (delivered as part of this spec/research phase) |
| FR-004 | Do NOT edit `analyze/prompt.md`'s content/size (canonical or override) as a "shrink/segment" fix — diagnosis shows this is not warranted and would not address any measured problem. **(Reinforced per Operator Decision 7: this prohibition is now doubly load-bearing — once by its original rationale, and again because #5133's `tests/cross_cutting/test_kittify_override_parity.py` gate would fail this mission's own diff if the override were edited to diverge from canonical.)** | As a maintainer, I want the fix to target the confirmed cause, not the issue's unverified premise, so effort isn't spent shrinking an already-small template. | High | Open (constraint, not a build item) |
| FR-005 | Out of scope per Operator Decision 6 (2026-09-26): dropped from this mission's implementation scope before any build work started. Was the governance-context budget-enforcer coverage fix (extending `_enforce_token_budget`'s candidate collectors to the Action Doctrine block). Full rationale, byte arithmetic, and the ADR 2026-07-28-1 conflict that prompted the drop are in "Known residual (out of scope): governance-context budget gap" above; not re-narrated here. | As a maintainer, I want the governance-context budget fix, so `specify`/`plan`/`tasks`/`implement`/`review` renders stay under budget. (N/A in this mission — dropped before implementation; see Known residual.) | — | **Dropped** (Operator Decision 6 — out of scope, never executed) |
| FR-006 | Out of scope per Operator Decision 6 (2026-09-26): dropped from this mission's implementation scope before any build work started. Was the honest-budget-trailer wording fix (report actual shortfall, not just a substitution count). See "Known residual (out of scope): governance-context budget gap" above for the full rationale. | As an operator, I want the budget trailer to report the real shortfall, so I'm not misled into thinking budget was met. (N/A in this mission — dropped before implementation; see Known residual.) | — | **Dropped** (Operator Decision 6 — out of scope, never executed) |
| FR-007 | Out of scope per Operator Decision 6 (2026-09-26): dropped from this mission's implementation scope before any build work started. Was the requirement that a substituted Action Doctrine entry keep its `- id: title` stub visible to the selector. See "Known residual (out of scope): governance-context budget gap" above for the full rationale. | As an agent, I want a substituted requires-closure entry to stay identifiable by id/title, so I can still fetch it on demand. (N/A in this mission — dropped before implementation; see Known residual.) | — | **Dropped** (Operator Decision 6 — out of scope, never executed) |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | **(Rewritten per Operator Decision 4 — the byte-diff verification is meaningless once the override no longer exists. Superseded by Operator Decision 7, 2026-09-26 — FR-001 does not execute, so there is no deletion for this NFR to verify.)** Historical text (preserved, do not re-implement): Deletion correctness on override removal | FR-001 removes the override file; there is nothing left to compare it against, so "heuristic preservation" is no longer verified by diffing two files — it is verified by confirming resolution now reaches canonical unchanged. **Verification (single, fully-checkable condition):** (a) `.kittify/overrides/missions/software-dev/command-templates/analyze.md` does not exist (`test -e` / `Path.exists()` is `False`); AND (b) `resolve_command("analyze.md", repo_root, mission="software-dev")` (the same probe research.md § 3 already used) returns `result.tier == "package_default"` (or whichever tier constant names canonical resolution) pointing at `packs/built-in/missions/mission-steps/software-dev/analyze/prompt.md`, **not** `tier == "override"`. Both conditions together mean an agent resolving `analyze` reads canonical's Detection Passes / Severity Assignment / `record-analysis` persistence step unchanged, because there is no longer a second file that could carry a divergent version of them. **Current, binding status: moot.** This mission's diff never touches the override file; on this checkout, `resolve_command("analyze.md", ...)` returns `tier=override` (not `package_default`) pointing at a file whose bytes are already identical to canonical (verified `cmp -s`, both 11,555 B) — a different, gate-backed guarantee (#5133's `test_kittify_override_parity.py`) delivers the same practical outcome this NFR was written to verify, without this mission changing anything. | Reliability | High | **Superseded** (Operator Decision 7 — moot, no deletion occurs) |
| NFR-002 | No new CLI surface | This mission introduces no new `spec-kitty` CLI command, subcommand, or argument (Operator Decision 2). **Re-verified per Operator Decision 7:** FR-001 no longer executes at all (not merely "a deletion, not a new command" — it does nothing), so it trivially introduces no new CLI surface; FR-002 still holds (a doctrine-content addition, reusing the existing doctrine-loading/pack-regeneration surfaces). Per Decision 6, the governance-context fix (FR-005/006/007) is dropped from this mission's scope entirely — moot with respect to this constraint (see "Known residual"). | Constraint compliance | High | Open |
| NFR-003 | Sequencing: FR-002 diff has no file-level overlap with currently-open PRs | **Re-verified per Operator Decision 7 against the narrower actual write set** (FR-001 no longer touches anything; this mission's diff is now FR-002's doctrine files only). Per Decision 6, the governance-context fix this NFR originally analyzed is out of this mission's scope (see "Known residual (out of scope): governance-context budget gap"). Re-ran `gh pr list --repo spec-kitty/spec-kitty --state open --json number,title,mergeable,mergeStateStatus` live, 2026-09-26, on this checkout: open PRs are #5141, #5137, #5136, #5028, #5009, #4995. Re-ran `gh pr view <n> --json files` for each against this mission's actual touched-file set (`packs/built-in/tactics/canonical-source-unification.tactic.yaml`, `packs/built-in/directives/044-canonical-sources-and-unification.directive.yaml`, their regenerated `packs/built-in/{tactic,directive}.graph.yaml`, and the two named architectural test files) — **zero overlap with any of the six.** #5009 and #4995 touch `src/runtime/next/prompt_builder.py` and `src/charter/offering/missions/mission_step_repository.py`/`mission_type_repository.py` respectively (neither touched here); #5141/#5137/#5136/#5028 touch unrelated migration, coordination, skills-doc, and README files. C-002 below states the full file-list detail. | Sequencing / risk | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Doctrine pack tier | FR-002's doctrine addition lands in `packs/built-in/` (ships to all consumers), justified by walking CLAUDE.md's own pack-tier test ("does this govern consumers, or only how the core team works?") rather than asserting the conclusion: the failure mode FR-002 documents is an **orchestrating agent's decision-making behavior toward a canonical surface** (attempt-to-load-before-bypassing, file-a-gap-if-genuinely-oversized) — the same class of rule DIRECTIVE_044's existing Rules 1 ("use canonical sources") and 3 ("missing command is a gap") already ship as `built-in`, because any consumer's agent, not just this project's core team, can reason "this might be too big" and bypass a canonical prompt/skill/CLI. This is categorically distinct from `packs/internal/README.md`'s worked examples of core-team-only doctrine — PR-landing specifics, tracker triage calibration, the internal maintainer glossary — which govern *how the Spec Kitty team itself operates the tracker/PR process*, not how any orchestrating agent (consumer or maintainer) should behave toward a canonical surface. The one caveat worth naming: this conclusion's sole evidence base is a single in-house dogfooding trace (`kitty-specs/mission-state-audit-trail-durability-01M37PWG/traces/tooling-friction.md`) — the exact "thin evidence for a broad claim" situation the CLAUDE.md test exists to catch — but the failure-mode text itself (bypass-on-unverified-size-assumption) is written generically, not scoped to this repo's tooling, so it still passes the "governs consumers" branch of the test on the merits. | Technical | High | Open |
| C-002 | **(Rewritten per Operator Decision 6 — the governance-context fix is dropped from this mission's scope entirely, not merely sequenced around open PRs. Re-rewritten per Operator Decision 7 — the write set is narrower still: FR-001 no longer touches the override file at all. Re-rewritten again 2026-09-27, round-2 rework, per Operator Decision 8 and cycle-2 findings WP01-C2-001/002 — the write set widens to all four DIRECTIVE_044-citing profiles.)** Sequencing vs. open PRs | This mission's diff now touches: `packs/built-in/tactics/canonical-source-unification.tactic.yaml` and/or `packs/built-in/directives/044-canonical-sources-and-unification.directive.yaml` plus their regenerated `packs/built-in/{tactic,directive}.graph.yaml` (FR-002) — plus test siblings `tests/architectural/test_doctrine_regenerate_graph_roundtrip.py` and `tests/architectural/test_pack_manifest_no_author_edit.py` — **plus, per Operator Decision 8: `packs/built-in/agent_profiles/{architect-alphonso,implementer-ivan,doctrine-daphne,python-pedro}.agent.yaml`, `tests/doctrine/test_directive_consistency.py` (the profile-citation rationale edits and their red-first/green rendered-reachability test), and their shared regenerated `packs/built-in/pack-manifest.yaml` content-hash diff.** `.kittify/overrides/missions/software-dev/command-templates/analyze.md` is **not** in this mission's diff at all (Decision 7 drops FR-001; the file is untouched, left exactly as #5133 resynced it). Per Decision 6, the governance-context budget fix (and its `token_budget.py`/`bootstrap_text.py`/`compact_governance.py` touch-set) is dropped from scope entirely — so the earlier #5009/#4995 overlap analysis for that portion is moot. **FR-002 target-file re-check on the merged checkout (2026-09-26, this branch, after `origin/main` @ `34b53d78e`):** both `packs/built-in/tactics/canonical-source-unification.tactic.yaml` and `packs/built-in/directives/044-canonical-sources-and-unification.directive.yaml` still exist and are still the correct target for FR-002's new failure-mode entry. Upstream PR #5133 (already merged into this branch) DOES touch `packs/built-in/tactic.graph.yaml` — it adds an unrelated new node/edges for its own `acceptance-criteria-non-vacuity` tactic elsewhere in that file (confirmed via `gh pr view 5133 --json files` and reading the merged file); the pre-existing `tactic:canonical-source-unification` node and its `suggests → directive:DIRECTIVE_044` edge are unchanged in content by that merge (only line positions elsewhere in the file shifted). Since #5133 is already merged (not an open PR to sequence against), this is not a live collision risk for this mission — FR-002's own future `spec-kitty doctrine regenerate-graph` write-mode run will simply add its new entry on top of a graph file that already includes #5133's content, the same way any doctrine edit follows a prior merged doctrine edit. **Live open-PR overlap re-check (2026-09-26, this checkout, narrower pre-Decision-8 file set):** `gh pr list --repo spec-kitty/spec-kitty --state open --json number,title,mergeable,mergeStateStatus` returned #5141, #5137, #5136, #5028, #5009, #4995. `gh pr view <n> --json files` for each, checked against this mission's then-actual touched-file set above: zero overlap. **Live open-PR overlap re-check (2026-09-27, round-2 rework, widened Decision-8 file set):** re-ran `gh pr list --repo spec-kitty/spec-kitty --state open --json number,title,mergeable,mergeStateStatus`; today's open set is #5161, #5137, #5028, #5009, #4995 (#5141/#5136 have since closed/merged; #5161 is new). Ran `gh pr view <n> --json files` for each against the full widened file set (the two doctrine-source files, their graph fragments, all four `packs/built-in/agent_profiles/*.agent.yaml` files, `packs/built-in/pack-manifest.yaml`, and `tests/doctrine/test_directive_consistency.py`): #5161 touches only `.kittify/evidence/**`, `kitty-ops/**`, and `tests/specify_cli/cli/commands/test_review_git_baseline.py`; #5137 touches coordination/doctor source+test files and its own `kitty-specs/coord-branch-remote-probe-01M3F6M7/**`; #5028 touches only `README.md`; #5009 touches `src/runtime/next/prompt_builder.py` and other runtime/coordination files (not touched here); #4995 touches `src/charter/offering/missions/mission_{step,type}_repository.py` and its own `kitty-specs/concurrent-template-config-race-4589-01M35M6B/**`. **Zero overlap with any of the five**, including against the newly-added `packs/built-in/agent_profiles/` and `tests/doctrine/` paths. No rebase/merge-order file conflict is created by this mission's own diff against any currently-open PR. | Technical | High | Open |

> **Authorized scope beyond WP01's `owned_files`/`lanes.json` `write_scope` (2026-09-27, round-2 rework, WP01-C2-002 remediation):** the four `packs/built-in/agent_profiles/*.agent.yaml` files and `packs/built-in/pack-manifest.yaml` are authorized targets for this mission by Operator Decision 8 and this plan/spec revision, but `kitty-specs/analyze-prompt-context-load-01M3F4BV/lanes.json`'s lane-a `write_scope` and `tasks/WP01-unverified-size-assumption-doctrine.md`'s `owned_files` frontmatter were **not** hand-edited to add them — the mission brief for this rework explicitly forbids hand-editing spec-kitty state (lanes.json, WP frontmatter, tasks.md) and no CLI surface exists to re-derive/append `write_scope`/`owned_files` for an already-materialized WP outside the `finalize-tasks` authoring flow. This is recorded here, explicitly, as a known, operator-authorized divergence between the spec's authorized file set and the tooling's own scope-tracking artifacts — not a silent staleness — so a future reader does not mistake the unedited `write_scope`/`owned_files` as the authoritative boundary of what this mission touches.
| C-003 | Remedy-2 (new CLI entrypoint) deferred | Per Operator Decision (2), a lean `spec-kitty analyze` CLI entrypoint is explicitly NOT built in this mission; the orchestrator drafts a separate proposal for maintainer sign-off outside this mission. FR-005/006/007 are dropped from this mission's scope per Decision 6 (see "Known residual"), so they are moot with respect to this constraint too. | Business | High | Open |

### Key Entities *(include if feature involves data)*

- **Canonical command template** (`packs/built-in/missions/mission-steps/software-dev/<action>/prompt.md`): the single source of truth for a command's contract, resolved through the charter/doctrine chain.
- **Project-local override** (`.kittify/overrides/missions/<mission>/command-templates/<action>.md`): a per-project shadow of the canonical template; OVERRIDE tier wins resolution (highest of 6 tiers) when present, so staleness here silently shadows canonical improvements. **(Corrected per Operator Decision 7 — FR-001 no longer deletes this entity for `analyze`.)** Current state, verified 2026-09-26 on this checkout: the `analyze` override still exists at this path (11,555 bytes) and is byte-identical to canonical `packs/built-in/missions/mission-steps/software-dev/analyze/prompt.md` (also 11,555 bytes, `cmp -s`-confirmed), because upstream PR #5133 already resynced it. `resolve_command("analyze.md", repo_root, mission="software-dev")` still returns `tier=override`, not `tier=package_default` — the entity is present, not deleted — but its content no longer diverges from canonical. It is additionally checked against future drift by #5133's new test, `tests/cross_cutting/test_kittify_override_parity.py`, which asserts byte-parity for every file under `.kittify/overrides/missions/software-dev/` (including `analyze.md`) against its canonical counterpart whenever it runs — but that test has no per-PR CI lane under this repo's own `.github/ci-module-registry.yml` disposition, so this is a nightly-only check (`ci-nightly.yml`'s `interpreter-matrix` job), not a per-PR merge gate; see the Former Acceptance Scenario 2 rationale under User Story 1 for the full citation.
- **Governance/charter context** (`_governance_context()` in `src/runtime/next/prompt_builder.py`, calling `charter.activation.scope_router.build_with_scope` / `charter.activation.context.build_charter_context`): action-scoped doctrine content injected ahead of the resolved template at render time; size varies drastically by action (measured 4.5–4.9 KB for analyze/accept/research vs 81,476–95,139 bytes for specify/plan/tasks/implement/review, research.md § 9).
- **Per-checkout first-load state** (`.kittify/charter/context-state.json`, gitignored per this repo's `.gitignore` line 90): records, per `(repo checkout, action)` pair, whether that action's governance context has ever rendered in "bootstrap" mode before; gates whether a given render takes the large bootstrap path or the small compact path. Local to a checkout/worktree, never shared or synced — a fresh clone or worktree always starts with this file absent, so the bootstrap cost recurs there regardless of how many other checkouts have already paid it.
- **NFR-001 governance token budget** (`BUDGET_DEFAULT = 40_000` characters, `_enforce_token_budget` in `src/charter/activation/context_renderers/token_budget.py`): the existing, pre-this-mission budget-enforcement mechanism that substitutes oversized sections for fetch-and-pull stanzas; background context for the governance-context budget-gap findings recorded in research.md § 9 — per Decision 6, FR-005/006/007 (which would have extended its candidate coverage) are dropped from this mission's scope (see "Known residual").
- **Action Doctrine block** (`_render_action_doctrine_lines` in `src/charter/activation/context_renderers/bootstrap_text.py`, backed by `_ActionDoctrineBundle` in `src/charter/activation/action_doctrine_bundle.py`): the resolved directive/tactic/styleguide/toolguide/procedure/asset/glossary bodies for an action's DRG requires-closure; confirmed (research.md § 9) as the block responsible for 71–75% of the oversized bytes — background context for those recorded research findings, not a block this mission's dropped FR-005 modifies (Decision 6; see "Known residual").

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: **(Rewritten per Operator Decision 4 — replaces the byte-diff criterion, which is inapplicable once the override no longer exists. Superseded by Operator Decision 7, 2026-09-26 — moot, see below.)** Historical text (preserved, do not re-implement): The stale override no longer exists at `.kittify/overrides/missions/software-dev/command-templates/analyze.md`, AND resolving `analyze` for this checkout (`resolve_command("analyze.md", repo_root, mission="software-dev")`) returns the canonical tier (`package_default`, or whichever tier constant names canonical resolution — see NFR-001), not `override`. This presumes the four intervening tiers (LEGACY, ORG, GLOBAL_MISSION, GLOBAL) do not shadow `analyze.md` ahead of `package_default`; **verified for this checkout/machine as of 2026-09-26** (research.md § 3.1): no `.kittify/command-templates/analyze.md` (LEGACY); the configured org pack (`packs/internal`, `.kittify/config.yaml` → `charter_packs.org.packs`) has no `missions/` directory at all, so it resolves nothing for any mission's `analyze.md` (ORG); and no `~/.kittify/missions/software-dev/command-templates/analyze.md` or `~/.kittify/command-templates/analyze.md` exist on this machine (GLOBAL_MISSION / GLOBAL). The GLOBAL_MISSION/GLOBAL tiers are genuinely operator-machine-dependent (a different operator's `~/.kittify/` could carry a shadowing file); the checkout-relative LEGACY/ORG tiers are not. Pass condition: `test ! -e .kittify/overrides/missions/software-dev/command-templates/analyze.md` succeeds, AND the `resolve_command` probe from research.md § 3, re-run post-deletion, reports the canonical tier and path. Together these subsume every narrower thing prior rounds checked individually (no retired `/memory/constitution.md` reference, current `--mission`/`feature_dir` convention, `record-analysis` persistence, matching frontmatter) — because there is no override content left to diverge from canonical in any of those respects. **Current, binding status: superseded/removed.** FR-001 no longer executes, so there is nothing to delete and no tier transition for this criterion to check. The practical outcome this SC was written to guarantee (an agent resolving `analyze` gets canonical's exact content) already holds today by a different mechanism: #5133 resynced the override to canonical's bytes, and `tests/cross_cutting/test_kittify_override_parity.py` — a real, fast, currently-passing test outside this mission's scope — asserts that byte-parity whenever it runs. This is not a per-PR merge-blocking guarantee: per this repo's own `.github/ci-module-registry.yml` disposition, `tests/cross_cutting` has no per-PR CI lane, so its only current automated execution home is the nightly `ci-nightly.yml` `interpreter-matrix` job or a manual `make test-full` (see the Former Acceptance Scenario 2 rationale under User Story 1 for the full citation) — it describes today's checkout state accurately, but a future divergence would not be caught in that PR's own checks.
- **SC-002**: `packs/built-in/tactics/canonical-source-unification.tactic.yaml` and/or `packs/built-in/directives/044-canonical-sources-and-unification.directive.yaml` contains an explicit failure-mode entry naming "bypassing a canonical surface on an unverified size assumption," reviewable by any future doctrine reader without re-deriving this mission's reasoning. **Verification method (required, per FR-002's companion-step note):** after the edit, `spec-kitty doctrine regenerate-graph` has been run in write mode and its `packs/built-in/{directive,tactic}.graph.yaml` diff is committed in the same commit; `spec-kitty doctrine regenerate-graph --check` exits 0; and `tests/architectural/test_doctrine_regenerate_graph_roundtrip.py` and `tests/architectural/test_pack_manifest_no_author_edit.py` both pass. SC-002 is not met if the doctrine text is added but the DRG graph fragments are left stale. **(Unaffected by Decision 7 — FR-002 is this mission's only remaining build item; re-confirmed on this merged checkout that both target files still exist and are unaffected in content by #5133, see C-002.)** **(Extended 2026-09-27, WP01 rework, per FR-002's corrected Status/notes above):** SC-002 additionally requires that `packs/built-in/agent_profiles/implementer-ivan.agent.yaml`'s DIRECTIVE_044 citation `rationale` names the same failure mode, verified by `tests/doctrine/test_directive_consistency.py::test_size_assumption_bypass_failure_mode_reaches_rendered_profile_context` asserting on real output from `_render_profile_sections` (red before the profile edit, green after) — the raw-YAML-only check above is necessary but not sufficient to show the text reaches an agent. **(Further extended 2026-09-27, round-2 rework, per Operator Decision 8):** SC-002 now requires the identical clause on **all four** shipped profiles that cite DIRECTIVE_044 — `architect-alphonso`, `implementer-ivan`, `doctrine-daphne`, `python-pedro` — verified by the same test parametrized over all four. **Correction (2026-09-27, WP01 cycle-3 fix, WP01-C3-001 / pr-FRESH2-001 — the prior sentence here overclaimed a uniform "red before each of the three newly-edited profiles' rationale edit, green after" story):** only `architect-alphonso` and `doctrine-daphne` were genuinely red before their own edit and green after; `implementer-ivan` was already green from the round-1 rework and stays green. `python-pedro` is a distinct, third case: it was **already green before this round's fix too**, not because its own file's rationale mentioned the failure mode at that time, but because `python-pedro` `specializes_from` `implementer-ivan` in the DRG and `AgentProfileRepository.resolve_profile`'s lineage union-merge (`_union_merge`, `src/charter/offering/agent_profiles/repository.py:190-204`) resolves a same-`code` collision on `directive-references` to whichever entry the accumulated ancestor merge already carries when the child is folded in — `implementer-ivan`'s "044" entry, never `python-pedro`'s own. So the parametrized `[python-pedro]` case of `test_size_assumption_bypass_failure_mode_reaches_rendered_profile_context` has only ever proven the text reaches `python-pedro` via inheritance through the real render path, not that `python-pedro`'s own file content is load-bearing there — a revert of only `python-pedro`'s own DIRECTIVE_044 rationale hunk leaves that parametrized case green regardless. `python-pedro`'s own-file edit is kept (source-of-truth consistency, in case the lineage edge or `implementer-ivan`'s own citation is ever changed) but was, and remains, a fallback addition rather than something the current lineage merge actually renders for `python-pedro` today. SC-002's coverage of this fact is now split across two tests: the rendered-reachability test above (production-path proof for all four, with `python-pedro`'s case proving lineage delivery, not its own file) and a second test, `test_size_assumption_bypass_failure_mode_in_each_profiles_own_source_file`, parametrized over all four profiles, which reads each profile's own source YAML directly (not through `resolve_profile`) and would catch a revert of any one profile's own hunk, including `python-pedro`'s. `packs/built-in/pack-manifest.yaml`'s regenerated content hashes for all four edited profile files are included in SC-002's verification, same as any other doctrine-source edit.
- **SC-003**: **(Reworded per Operator Decision 7 — there is no FR-001 deletion left to except from this criterion, so the criterion is now unconditional and, per #5133's new gate, stronger than before.)** No edit lands against `analyze/prompt.md`'s content/size in either canonical or override form — no exception, because FR-001 does not execute and makes no edit at all. Confirmed by the PR diff touching zero bytes of canonical `analyze/prompt.md` and zero bytes of the override `.kittify/overrides/missions/software-dev/command-templates/analyze.md`. This is a strictly stronger guarantee than the prior wording ("beyond the FR-001 deletion"), since that prior wording still permitted one specific edit (the deletion); this wording permits none. It is additionally reinforced by a mechanism outside this mission's own scope: `tests/cross_cutting/test_kittify_override_parity.py` (added by #5133) would independently fail if this mission's diff edited the override to diverge from canonical.
- **SC-004**: `src/runtime/next/prompt_builder.py` has zero lines changed in this mission's diff. **(Rewritten per Operator Decision 6 — NFR-003 was rewritten again this round and no longer analyzes this file at all; it is now a live PR-overlap sequencing check against #5009/#4995, unrelated to why this criterion holds. This holds because FR-005/006/007 — the fix that would have touched `prompt_builder.py`'s governance-context call sites — are dropped from this mission's scope entirely per Decision 6, not because the mission avoids the file to dodge #5009's collision risk and not because NFR-003 says so; see "Known residual (out of scope): governance-context budget gap" above.)**

## Dependencies & Sequencing

- **#5009** ("fix: retain validated owned checkout authority across mission lifecycle") — **re-verified 2026-09-26, still OPEN**, `mergeable=CONFLICTING`, `mergeStateStatus=DIRTY` (`gh pr list`/`gh pr view 5009 --json files`, this checkout), touches `src/runtime/next/prompt_builder.py`, `decision.py`, `runtime_bridge.py`, `runtime_bridge_engine.py`, `src/mission_runtime/resolution.py`, `src/specify_cli/core/mission_creation.py`, `src/specify_cli/workspace/context.py`, `coordination/status_*.py`, `pyproject.toml`, plus three test files. This mission's actual, narrower scope after Decision 7 (FR-002 only — the doctrine pack files, their regenerated `.graph.yaml`, and two named architectural test files) touches neither `prompt_builder.py` nor any other file #5009 touches — zero overlap. Per Decision 6, the governance-context fix is dropped from scope entirely, so the earlier collision-risk-acceptance analysis for it (research.md § 9, `gh pr diff 5009`) is moot.
- **#4995** ("fix(charter): make concurrent mission-template resolution thread-safe") — **re-verified 2026-09-26, still OPEN**, `mergeable=CONFLICTING`, `mergeStateStatus=DIRTY`, touches `src/charter/offering/missions/mission_step_repository.py` / `mission_type_repository.py` (the same resolver family `resolve_command` belongs to) plus `kitty-specs/concurrent-template-config-race-4589-01M35M6B/**` and test files. This mission's FR-002 does not touch those files either; no direct dependency, noted for completeness per the mission brief.
- **Other currently-open PRs, re-checked 2026-09-26 for completeness (none overlap this mission's FR-002-only diff):** #5141 (meta.json read authority — migration/census files), #5137 (coord remote-probe fix — coordination/doctor files), #5136 (mission-review skill Gate 3 doc — CONFLICTING/DIRTY, touches `src/charter/offering/skills/spec-kitty-mission-review/SKILL.md` and evidence/ops files), #5028 (README.md ecosystem-tools addition). None touch `packs/built-in/tactics/canonical-source-unification.tactic.yaml`, `packs/built-in/directives/044-canonical-sources-and-unification.directive.yaml`, `packs/built-in/tactic.graph.yaml`, `packs/built-in/directive.graph.yaml`, or the two named architectural test files.
- **FR-001 landing sequencing — retired per Operator Decision 7.** This bullet previously described an atomic-landing requirement and an operator courtesy-check for missions mid-flight through `/spec-kitty.analyze` when FR-001's deletion commit landed. FR-001 no longer executes (Decision 7), so no file is removed and no concurrency hazard exists for this mission's own diff to create.
- **Ledger residual (Operator Decision 4) — corrected per Operator Decision 7: no longer "out of scope, deferred"; already resolved upstream.** Re-verified directly against the workspace-level `SPEC-KITTY-LEDGER.md` (outside this repository checkout), 2026-09-26: the SK-276 entry itself now reads "**Status**: fixed on `main` by #5133 (merged 2026-09-26). That PR resynced all ten overrides and added a byte-parity gate, `tests/cross_cutting/test_kittify_override_parity.py`. Verified first-hand at `origin/main` @ `34b53d78e`: every software-dev command-template override now matches canonical." The earlier framing in this spec ("the 9 other stale software-dev command-template overrides ... are out of scope for this mission ... recorded as ledger entry SK-276") is stale: it is not merely deferred, it is **resolved** — #5133 already resynced all 10 overrides (not just the other 9; `analyze` too), independently re-confirmed by the orchestrator on this checkout via `cmp -s` against each of the 10 canonical counterparts (accept, analyze, implement, plan, review, specify, tasks, tasks-outline, tasks-packages, tasks-finalize — all 10 IDENTICAL). SK-276 remains cited here for provenance/history, not as an open residual this mission still owes anything toward.
- **Campsite-clean framing (Operator Decision 3) — dropped per Operator Decision 7; no substitute found.** Decision 3 originally scoped the override reconciliation in as "a domain-matched campsite-clean commit," and FR-001's row above still calls the (now-superseded) deletion "the domain-matched campsite-clean commit." Decision 7 drops this framing entirely: there is no override-deletion commit left to serve as a campsite-clean first commit, because FR-001 does not execute. The orchestrator looked for any other domain-matched debt within this mission's remaining scope (FR-002 alone: the two doctrine-source files, their regenerated graph fragments, and two named architectural tests) that could fill the campsite-clean-first-commit role, and **found none** — FR-002's target files (`packs/built-in/tactics/canonical-source-unification.tactic.yaml`, `packs/built-in/directives/044-canonical-sources-and-unification.directive.yaml`) carry no known pre-existing staleness or drift the orchestrator is aware of from this investigation; nothing in this mission's narrowed scope has an obvious "clean up first, then build" candidate. This is stated explicitly, per the same instruction given to the plan-phase agent, rather than left implied or invented.
