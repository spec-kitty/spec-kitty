# Implementation Plan: Agents route around `/spec-kitty.analyze` because the command prompt is too large to load

**Branch**: `fix/analyze-prompt-context-load-5005` | **Date**: 2026-09-26 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/analyze-prompt-context-load-01M3F4BV/spec.md`

**Note**: canonical execution workflow for `analyze` lives at
`packs/built-in/missions/mission-steps/software-dev/analyze/prompt.md`. FR-004 forbids
editing that file's content or size in this mission; this plan does not touch it.

## Summary

**Revision note (2026-09-27, for Operator Decision 8 — supersedes this section's
"Revised for Operator Decision 7" framing below where the two conflict; the Decision-7
framing is otherwise still accurate and is kept, not deleted).** Decision 8 (spec.md,
"Clarifications / Decisions" item 8) retroactively authorizes the WP01 rework's
`implementer-ivan.agent.yaml` DIRECTIVE_044-citation edit and widens FR-002/SC-002 to all
four profiles that cite DIRECTIVE_044 — `architect-alphonso`, `implementer-ivan`,
`doctrine-daphne`, `python-pedro` — plus their shared regenerated
`packs/built-in/pack-manifest.yaml`. The reason: landing the failure-mode text only in the
tactic's `failure_modes` array does not, by itself, reach an agent — both the tactic's and
DIRECTIVE_044's rendered inline bodies exceed the per-artifact inline-body budget
(`_PROFILE_INLINE_BODY_LIMIT_CHARS`, `token_budget.py`) and fall back to a fetch-stanza
pointer in every automatic render path. The one surface that reaches an agent unconditionally
is the profile-citation header line rendered by `_render_directive_entry`
(`src/charter/activation/context_renderers/profile_sections.py`), which appends a citing
profile's own `directive-references[].rationale` **before** that budget check runs — see the
rewritten "Seam" and "Red-first tests" sections below for the full mechanism and the three
tests (not one) that now ship. FR-002's underlying doctrine-source edit narrowed in practice,
too: the shipped diff touches only the tactic file's `failure_modes` array; the directive
file's `procedures` array was not touched (spec.md's "and/or" wording permits this — see
"Seam" below). This plan's Decision-7 framing immediately below (scope narrowed to FR-002 as
the only build item, FR-001 a superseded no-op, FR-004 a hard constraint) is unaffected by
Decision 8 and stands unmodified.

**Revised for Operator Decision 7 (2026-09-26).** Per spec.md's "Remaining scope after
Operator Decision 7" section, this mission's actual build scope is narrower than any prior
plan round described. `analyze` was never oversized (11,891 B pre-#5133 / 16,458 B on this
merged checkout, research.md § 4 and § 10) — the reported "too large to load" premise does
not survive measurement. The originally-diagnosed defect — THIS checkout resolving
`analyze.md` through a stale, April-2026 project-local override instead of canonical — no
longer needs this mission's own fix: upstream PR #5133 (merged 2026-09-26T19:56:16Z into
`main`, now in this branch via the `origin/main` @ `34b53d78e` merge) already resynced that
override to canonical's exact bytes (both 11,555 B, `cmp -s`-confirmed on this checkout,
re-verified during this plan-revision pass — see "Contracts touched" below) and added a
byte-parity gate (`tests/cross_cutting/test_kittify_override_parity.py`, nightly-only, no
per-PR lane) that would fail if this mission edited the override to diverge again. This
plan now covers exactly one build item plus one hard constraint:

- **FR-001 (superseded, no-op — not built by this plan)**: Operator Decision 7 drops the
  override-deletion mechanism entirely. #5133 already delivered the practical outcome
  FR-001 would have (canonical content reachable through `analyze` resolution); deleting
  the file now would only remove content `test_kittify_override_parity.py`'s own
  enumeration logic depends on, for zero behavior change. No commit in this mission's diff
  touches `.kittify/overrides/missions/software-dev/command-templates/analyze.md`.
- **FR-002 (the only real build item — widened by Operator Decision 8, see the revision
  note above)**: add advisory doctrine (a new failure-mode entry
  and/or procedure line) naming the evidenced failure mode — bypassing a canonical surface
  on an unverified size assumption — to
  `packs/built-in/tactics/canonical-source-unification.tactic.yaml` and/or
  `packs/built-in/directives/044-canonical-sources-and-unification.directive.yaml`; **and**,
  per Decision 8, the identical failure-mode clause in the DIRECTIVE_044
  `directive-references[].rationale` of all four citing agent profiles
  (`architect-alphonso`, `implementer-ivan`, `doctrine-daphne`, `python-pedro`) — the actual
  delivery path a rendered agent receives; plus the required
  `spec-kitty doctrine regenerate-graph` write-mode companion step (regenerating
  `packs/built-in/pack-manifest.yaml`'s content hashes) and its named architectural tests.
- **FR-003**: already delivered (research.md's measurement method, including the § 10
  merged-branch re-measurement addendum) — referenced, not re-planned.
- **FR-004**: a constraint, not a build item — `analyze/prompt.md` (canonical or override
  content/size) is never edited by this mission, now doubly reinforced by #5133's parity
  gate.

FR-005/006/007 (the governance-context budget-gap fix) stay OUT OF SCOPE per Operator
Decision 6, unaffected by Decision 7; the "Known residual" section of spec.md is the
binding record of that deferral. Posting the ADR-amendment proposal on issue #5005 is an
orchestrator action outside this mission's implementation and is not a work item in this
plan.

## Technical Context

**Language/Version**: Python 3.11+ (repo-wide requirement; no new language surface)
**Primary Dependencies**: none new. Touches only the existing doctrine-pack YAML/DRG
toolchain (`spec-kitty doctrine regenerate-graph`, `spec-kitty doctrine validate`). FR-001
no longer executes (Decision 7), so this plan no longer touches the
`charter.offering.resolver` / `charter.offering.missions.repository` resolution chain at
all.
**Storage**: N/A — no database, no new persisted state.
**Testing**: pytest, via the pre-existing entry point `tests/doctrine/test_directive_consistency.py`
(re-verified during this revision pass — see "Red-first tests" below for why this file, not
`test_schema_compatibility.py` or `test_tactic_compliance.py`, is the correct home) plus
`tests/architectural/`, and the doctrine schema-validation CLI (`spec-kitty doctrine
validate`) — no new test-running mechanism.
**Target Platform**: this repository checkout only (a dogfooding/maintainer-local doctrine
addition); no consumer-facing runtime behavior change at all — FR-002 adds prose to an
already-shipped `packs/built-in/` doctrine pair, and FR-001 makes no change (see spec.md's
"Remaining scope after Operator Decision 7").
**Project Type**: single project (this repo). No web/mobile/multi-project structure applies.
**Performance Goals**: N/A — no code path changes; no CLI command's runtime is affected by a
content-only doctrine addition.
**Constraints**: FR-004 — `analyze/prompt.md` content/size, canonical or override, is not
edited (doubly reinforced now by #5133's `test_kittify_override_parity.py` gate). NFR-002 —
no new CLI surface. C-001 — FR-002's doctrine lands in `packs/built-in/` (ships to
consumers), not `packs/internal/` (see Seam section below for the pack-tier justification).
**Scale/Scope (widened 2026-09-27, Operator Decision 8 — supersedes the "one-to-two files"
figure below).** As shipped: one doctrine-source YAML
(`packs/built-in/tactics/canonical-source-unification.tactic.yaml` — the directive file was
not touched; see "Seam" below), four agent-profile YAMLs
(`packs/built-in/agent_profiles/{architect-alphonso,implementer-ivan,doctrine-daphne,
python-pedro}.agent.yaml`), the regenerated `packs/built-in/pack-manifest.yaml` (content
hashes only — the DRG `.graph.yaml` fragments did not diff; see "Generated artifacts"
below), and one extended test file (`tests/doctrine/test_directive_consistency.py`, three
test functions). FR-001 touches zero files (superseded, no-op). Six touched files is still a
genuinely small mission — the plan stays proportionally small (Governing Principle
"reconciling change-scope tensions": smallest-viable-diff picks the file set first) — but is
larger than the "one-to-two files... plus two regenerated fragments" figure this section
originally stated for the pre-Decision-8 design.

## Charter Check

*GATE: must pass before Phase 0 research (already complete — research.md) and re-checked
after Phase 1 design (this plan).*

- **Single canonical authority (Governing Principle 1 / DIRECTIVE_044)**: satisfied without
  this mission needing to act — #5133 already resynced the override to canonical's exact
  bytes (re-verified this pass, `cmp -s`, both 11,555 B), and FR-001's deletion mechanism is
  now a no-op (Decision 7). FR-002 documents the failure mode this mission's own root cause
  exemplifies (an agent that assumed size without measuring), using the SAME tactic/directive
  pair as the authority, not a new one.
- **Architectural alignment (Governing Principle 2)**: FR-002 stays inside the existing
  doctrine-pack DRG-source tier (no new seam). FR-001 introduces no seam at all, since it
  makes no change.
- **ATDD-first (Governing Principle 4)**: FR-002 is advisory-only doctrine prose (spec.md's
  own Status/notes on FR-002) — there is no runtime behavior to red/green-pin, but the
  doctrine content's own existence is pinned by a genuine red-first content test (see
  "Red-first tests" below), re-verified RED on this checkout during this revision pass.
  FR-001 has no behavior change to pin (no-op per Decision 7).
- **Campsite cleaning (Standing Order 2)**: **dropped per Operator Decision 7 — no
  substitute found.** Decision 3 originally framed the override-deletion commit as this
  mission's domain-matched campsite-clean commit; Decision 7 removes that framing entirely
  because there is no override-deletion commit left to serve that role. This plan re-checked
  FR-002's own target files (`packs/built-in/tactics/canonical-source-unification.tactic.yaml`,
  `packs/built-in/directives/044-canonical-sources-and-unification.directive.yaml`) for any
  other domain-matched staleness or drift that could fill the campsite-clean-first-commit
  role and found none — stated explicitly here rather than inventing debt that isn't there,
  matching spec.md's own "Campsite-clean framing" note under Dependencies & Sequencing.
- **Canonical sources (Standing Order 6)**: this plan is a direct revision of the plan
  originally scaffolded via the canonical `spec-kitty plan --mission <slug> --json` CLI (see
  "Tracer files" below for the prior round's friction note about which template it resolved);
  this revision pass edits `plan.md` directly per its own explicit brief (a plan revision,
  not fresh scaffolding).
- **Mission tracer files (Standing Order 3)**: appended in this same commit, not overwritten
  (see "Tracer files" below).
- **Pack tier placement (C-001)**: FR-002's doctrine lands in `packs/built-in/`, justified by
  CLAUDE.md's own test ("does this govern consumers, or only how the core team works?") —
  the failure mode is a general orchestrating-agent decision-making rule (attempt-to-load
  before bypassing a canonical surface), not Spec-Kitty-core-team-only PR-landing/triage
  guidance, so it belongs in the same tier as DIRECTIVE_044's existing Rules 1 and 3, not in
  `packs/internal/`. Re-verified this pass: both target files still exist unchanged in
  content by #5133 on this merged checkout (spec.md C-002's "FR-002 target-file re-check").

No Charter Check violations requiring justification — see "Complexity Tracking" below
(empty by design).

## Seam

**FR-001 — no seam (superseded, no-op per Operator Decision 7).** The prior plan round
described the 6-tier command-template resolver (`charter.offering.resolver.resolve_command()`)
as FR-001's seam, since its mechanism was deleting the stale override file so resolution
fell through to canonical. That mechanism no longer executes: #5133 already resynced the
override's content to canonical's exact bytes (re-verified this pass, `cmp -s`, both 11,555
B) before this mission's own deletion could land, and Decision 7 drops the deletion as a
build item entirely — there is nothing left for it to safely do (deleting the file now would
only remove content `tests/cross_cutting/test_kittify_override_parity.py`'s own enumeration
logic depends on, for zero behavior change). This plan makes no resolver-code claim and
touches no resolver seam.

**FR-002 (advisory doctrine) — the doctrine-pack DRG source tier.** The two candidate files
are hand-authored YAML in `packs/built-in/tactics/canonical-source-unification.tactic.yaml`
and `packs/built-in/directives/044-canonical-sources-and-unification.directive.yaml`. Both
already exist and already carry `failure_modes` (tactic) / `procedures` (directive) arrays
of the same free-form-string shape — spec.md's FR-002 text says "and/or," so a same-shape
addition to either or both satisfies it. **As shipped, only the tactic file was edited**
(one new `failure_modes` entry); the directive file's `procedures` array was left unchanged
— a valid choice under the "and/or" wording, not a partial implementation. The generated
companions (`packs/built-in/tactic.graph.yaml`, `packs/built-in/directive.graph.yaml` — both
already reference `tactic:canonical-source-unification` / `DIRECTIVE_044` today, confirmed by
grep) are DRG-derived from these sources; regenerating them produces no diff for this edit,
because `failure_modes`/`procedures` prose is not part of either fragment's shape — see
"Generated artifacts" below for what the regeneration step actually changes here
(`pack-manifest.yaml`'s content hashes).

**FR-002 (advisory doctrine) — second seam, added 2026-09-27 per Operator Decision 8: the
agent-profile citation-render tier.** The tactic/directive edit above is necessary but not
sufficient for the text to reach a working agent. Both `canonical-source-unification`'s
rendered inline body (~4.3K chars) and DIRECTIVE_044's rendered inline body (~3.5K chars)
already exceed the per-artifact inline-body budget
(`_PROFILE_INLINE_BODY_LIMIT_CHARS`, `src/charter/activation/context_renderers/
token_budget.py`), so every automatic render path (profile citation, global selection,
Action Doctrine block) falls back to a generic fetch-stanza pointer regardless of which
doctrine-source file carries the new text — reachable only via an agent's own explicit
`--include` fetch, not by default. The one surface that DOES render unconditionally,
independent of that budget check, is the profile-citation header line built by
`_render_directive_entry` (`src/charter/activation/context_renderers/profile_sections.py`,
function starts at line 527 on this checkout): it appends a citing profile's own
`directive-references[].rationale` for the matching `code` to the citation's header line
(`header_line = f"{header_line} — {rationale}"`) **before** the
`body_lines`/`_PROFILE_INLINE_BODY_LIMIT_CHARS` check that governs the inline-vs-fetch-stanza
branch immediately below it. Because that rationale is emitted unconditionally, adding the
failure-mode clause there is the actual, verified delivery path — proved by real-rendered-
output tests exercising `_render_profile_sections`, not raw-YAML content checks (see
"Red-first tests" below). This mission therefore also edits the DIRECTIVE_044
`directive-references[].rationale` field of the four shipped profiles that cite it —
`packs/built-in/agent_profiles/{architect-alphonso,implementer-ivan,doctrine-daphne,
python-pedro}.agent.yaml` (confirmed exhaustive via
`grep -rl 'code: "044"' packs/built-in/agent_profiles/`) — appending the same clause used in
the tactic's `failure_modes` entry. No schema change: `directive-references[].rationale` is
already a free-form string field in the agent-profile schema. This reach does **not** extend
to the mission-level orchestrating agent for `analyze`/`specify`/`plan`/`tasks`/`review`/
`accept`, whose step contract carries `agent_profile: null` — recorded as an explicit,
unclosed residual in spec.md's "Known residual (out of scope): mission-level orchestrating
agent never receives this warning" section (WP01-C2-003), not claimed as fixed here.

## Contracts touched

**Re-verified this revision pass (2026-09-26, on the merged checkout, after #5133/`34b53d78e`)**:
both target files still exist unchanged in content by #5133 —
`packs/built-in/tactics/canonical-source-unification.tactic.yaml` (6,732 B) and
`packs/built-in/directives/044-canonical-sources-and-unification.directive.yaml` (4,023 B) —
and both still pass `spec-kitty doctrine validate <path>` dry-run against their current,
unedited content ("1 artifact(s) passed validation" for each, re-run this pass). The
analysis below, authored in the prior plan round, still holds unchanged and is kept as-is
rather than needlessly rewritten.

The schema files governing both edited YAML shapes are
`src/charter/offering/schemas/tactic.schema.yaml` and
`src/charter/offering/schemas/directive.schema.yaml` (re-read in full this pass, confirmed
unchanged). Both schemas are **preserved unchanged** by this mission — verified as follows:

- `tactic.schema.yaml` declares `failure_modes` as `type: array, items: {type: string}` with
  no `maxItems`, no enum, no pattern constraint on entries. The tactic file's existing
  `failure_modes` block already contains six free-form prose strings (e.g. "Parity instead of
  unification: ...", "Wrong canonical surface: ..."). A seventh string describing the
  size-assumption-bypass failure mode is a same-shape addition — the schema does not need to
  change to accept it.
- `directive.schema.yaml` declares `procedures` the same way (`type: array, items: {type:
  string}`, no constraint on entry shape). The directive file's existing `procedures` array
  already holds three free-form "Rule N — ..." strings; a fourth ("Rule 4 — ...") is a
  same-shape addition.
- Both edits were dry-run validated during plan authoring against the CURRENT (unedited)
  files with `spec-kitty doctrine validate <path>` and both already pass ("1 artifact(s)
  passed validation" for each) — confirming the schema accepts today's shape and that
  appending one more array entry of the same type cannot introduce a schema violation
  (arrays of scalars have no positional or count constraint in either schema).
- No `$id`, `required`, `additionalProperties`, or `enum` change is needed or planned in
  either schema file. This FR is a content-only addition using the existing schema shape,
  never a schema change.

**Added 2026-09-27 (Operator Decision 8): the four edited agent-profile files.** Each
profile's `directive-references` array is a list of `{code, name, rationale}` entries;
`rationale` is a free-form string field with no shape/length constraint in the agent-profile
schema. Appending the failure-mode clause to the existing `code: "044"` entry's `rationale`
in each of `architect-alphonso.agent.yaml`, `implementer-ivan.agent.yaml`,
`doctrine-daphne.agent.yaml`, and `python-pedro.agent.yaml` is a same-shape string edit, not a
schema change — the same reasoning as the tactic/directive array edits above.

## Generated artifacts and their regenerating command

`packs/built-in/tactic.graph.yaml` and `packs/built-in/directive.graph.yaml` are two of the
14 sharded, machine-generated DRG fragments under `packs/built-in/` (per
`spec-kitty doctrine regenerate-graph --help`: "Composes the DRG extractor + calibrator into
per-populated-node-kind `packs/built-in/*.graph.yaml` fragments... retiring the legacy
`graph.yaml` monolith"). Editing either source YAML (the tactic or the directive file) without
regenerating these leaves the DRG stale relative to the pack-manifest.

**Binding sequencing for the implementation phase** (do not skip regardless of default
blast-radius calibration, per spec.md FR-002's own "Required companion step" note):

1. Edit the target doctrine-source YAML file(s) (the tactic and/or directive file).
2. Run `spec-kitty doctrine regenerate-graph` in **write mode** (no `--check`) — this is the
   ONLY sanctioned way to update `tactic.graph.yaml`/`directive.graph.yaml`; they must never
   be hand-patched.
3. Commit the resulting `packs/built-in/{tactic,directive}.graph.yaml` diff in the **same
   commit** as the source YAML edit (never a separate commit — a source-only commit would
   leave the DRG stale for one commit, tripping the freshness gate on any intermediate
   checkout).
4. Confirm `spec-kitty doctrine regenerate-graph --check` exits 0 (re-verified this revision
   pass, this checkout, 2026-09-26: `DRG graph is fresh: <repo>/packs/built-in`, exit 0;
   `tests/architectural/test_doctrine_regenerate_graph_roundtrip.py` already invokes this
   exact check as its baseline mechanism — see "Baseline method" below for its current
   passing state at the `34b53d78e` baseline).
5. Confirm `tests/architectural/test_doctrine_regenerate_graph_roundtrip.py` AND
   `tests/architectural/test_pack_manifest_no_author_edit.py` both pass (both read in full
   during plan authoring; both exist today and both are green at the `34b53d78e` baseline —
   see "Baseline method").

**Confirmed against the shipped diff (2026-09-27): only `pack-manifest.yaml` actually
changed.** `packs/built-in/tactic.graph.yaml` and `packs/built-in/directive.graph.yaml`
carry structural DRG nodes/edges (ids, node kinds, `requires`/`suggests` edges) — they do not
carry `failure_modes`/`procedures` prose or agent-profile `directive-references[].rationale`
text at all (confirmed by grep: neither fragment contains the phrase "unverified size
assumption"). Running `spec-kitty doctrine regenerate-graph` in write mode after this
mission's source edits therefore produced a byte-identical `tactic.graph.yaml` and
`directive.graph.yaml` (no diff to commit for either) and a changed
`packs/built-in/pack-manifest.yaml` — the per-constituent `content_hash` for each of the five
edited source files (the tactic file plus the four agent-profile files) and the file-level
`manifest_hash`, all regenerated by the same command. Step 2 above ("run
`regenerate-graph` in write mode") still applies and was still run — its observable effect for
this specific content shape is a `pack-manifest.yaml`-only diff, not a `.graph.yaml` diff. This
is not a step that was skipped; it is the correct, verified output of running it against
prose-only source content.

## Red-first tests per changed behaviour

**FR-001 — no red-first test (superseded, no-op per Operator Decision 7).** The prior plan
round pinned FR-001's resolver-tier transition with a live-checkout probe in
`tests/doctrine/test_resolver.py`. That test sketch guarded a deletion that no longer
happens; it is **removed from this plan entirely, not retained or repurposed**, per the same
reasoning spec.md's "Former Acceptance Scenario 2" section gives for removing the analogous
spec-level scenario: parity for this exact override is already covered by a test this
mission does not own (`tests/cross_cutting/test_kittify_override_parity.py`, added by
#5133), and this mission's diff makes no resolver-tier change for a new test to pin.

**Revision note (2026-09-27, Operator Decision 8 — supersedes the single-test design
immediately below, kept as history, not deleted, per the same convention used elsewhere in
this plan for superseded content).** The design below (one test,
`test_size_assumption_bypass_failure_mode_documented`, asserting the needle string exists
anywhere in the raw YAML) was the correct design for the pre-Decision-8 scope, where "the text
exists in the source file" was the only checkable property. Once the WP01 rework and Decision
8 established that raw source-file presence does not prove the text reaches a rendered agent
(see "Seam" above), the shipped implementation carries **three** test functions in
`tests/doctrine/test_directive_consistency.py`, not one:

1. **`test_size_assumption_bypass_failure_mode_documented`** — the same content-assertion
   intent as the design below, but revised in review cycle 3 (finding `pr-tests-001`) to
   anchor on the entry's own *title* (the segment before the first `:`), case-insensitively,
   via a small `_entry_title()` helper — not a substring match against the whole entry
   string. The original design's substring-anywhere-in-the-entry approach was found to pass
   only because of an incidental lowercase restatement of the needle phrase in the entry's
   closing sentence, not because the assertion was anchored to the entry's stable identity; a
   behaviour-preserving copy-edit of that restatement could have flipped the verdict without
   the doctrine content actually regressing. This is a real improvement over the design
   below, not a like-for-like re-implementation.
2. **`test_size_assumption_bypass_failure_mode_in_each_profiles_own_source_file`**
   (new, parametrized over all four DIRECTIVE_044-citing profiles) — reads each profile's
   own YAML file directly (never through `resolve_profile`) and asserts its own
   `directive-references[].rationale` for `code: "044"` contains the needle. This is the test
   that catches a revert of `python-pedro.agent.yaml`'s own hunk specifically: `python-pedro`
   `specializes_from` `implementer-ivan` in the DRG, and
   `AgentProfileRepository.resolve_profile`'s lineage union-merge
   (`src/charter/offering/agent_profiles/repository.py:190-204`) resolves a same-`code`
   `directive-references` collision to whichever entry the accumulated ancestor merge already
   carries when the child folds in — `implementer-ivan`'s "044" entry, never `python-pedro`'s
   own. So test 3 below (the production render-path test) stays green for `python-pedro` via
   inheritance even if `python-pedro`'s own file is reverted; this own-file test is the one
   that would go red in that case.
3. **`test_size_assumption_bypass_failure_mode_reaches_rendered_profile_context`**
   (parametrized over all four profiles) — the real proof, exercising the production
   `_render_profile_sections` render path (the same renderer `build_charter_context`/
   `spec-kitty charter context` calls) against the actual shipped doctrine catalog, not a
   synthetic fixture or raw YAML. For `architect-alphonso` and `doctrine-daphne` this was
   genuinely red before their own rationale edit and green after. `implementer-ivan` was
   already green from the round-1 rework. `python-pedro`'s parametrized case proves the text
   reaches it via DRG lineage inheritance from `implementer-ivan`, not via its own file — which
   is exactly why test 2 above exists as a companion, not a duplicate.

**Superseded design below (kept as the historical record of the pre-Decision-8, single-test
approach — the reasoning for why `tests/doctrine/test_directive_consistency.py` is the
correct file, and why the two alternative homes considered were rejected, still holds and is
not re-litigated).**

**FR-002 — a concrete, currently-RED content-assertion test (new).** Per spec.md's own
Independent Test framing, this FR is advisory-only prose; the only checkable property is
that the new failure-mode/procedure text exists verbatim in the loaded doctrine content.

**Choosing the entry point — the prior plan round's suggestion was checked and found wrong.**
The prior round suggested extending `tests/doctrine/directives/test_schema_compatibility.py`.
Read in full this pass: its `BUILT_IN_DIRECTIVES_DIR` constant points at
`src/charter/offering/directives/built-in` — a path that **does not exist** on this checkout
(`Path.exists()` is `False`; confirmed with a direct filesystem check this pass). Doctrine
content moved to the flattened `packs/built-in/<kind>/` pack root in mission
`relocate-builtin-doctrine-packs-01KYT87F` (per the comment block at the top of
`tests/doctrine/test_directive_consistency.py`), and this file's constant was never updated;
its one content-scoped test, `test_existing_built_in_directives_still_validate`, is
parametrized over an empty glob and collects as a single vacuous `[NOTSET]` case that can
never fail on real content (confirmed by running `pytest tests/doctrine/directives/test_schema_compatibility.py
--collect-only` this pass and by direct glob inspection). It never loads
`044-canonical-sources-and-unification.directive.yaml`'s content at all. This file is a
schema/model-enrichment compatibility suite (parses synthetic minimal/enriched directive
dicts), not a home for a real content assertion — extending it would have produced a test
that looks real but is provably inert. `tests/doctrine/test_tactic_compliance.py` was
checked for the same reason and has the identical defect: its `_TACTICS_DIRS` points at
`src/charter/offering/tactics/built-in` / `_proposed`, neither of which exists, so all four
of its tests also collect as vacuous `[NOTSET]` parametrizations (confirmed by
`--collect-only` this pass).

**Chosen home: `tests/doctrine/test_directive_consistency.py`.** Read in full this pass. It
is the one doctrine-content test file that resolves paths correctly for the post-relocation
layout — `_PACKS_BUILT_IN = REPO_ROOT / "packs" / "built-in"`, with `_DIRECTIVES_DIRS` and
`_BUILT_IN_TACTICS_DIR` both derived from it — and it already runs 8 real, passing tests
against the actual shipped directive/tactic files (`pytestmark = [pytest.mark.fast,
pytest.mark.doctrine, pytest.mark.corpus]`, confirmed green this pass: `8 passed`). No
existing test file in this repository already asserts against
`canonical-source-unification.tactic.yaml` / `044-canonical-sources-and-unification.directive.yaml`'s
specific `failure_modes`/`procedures` content by name — this is a genuine, confirmed gap,
not something duplicated elsewhere. A new test function,
`test_size_assumption_bypass_failure_mode_documented`, was staged into this file this pass to
verify it for real, then reverted (this plan-revision pass's own scope is `plan.md` + the
three tracer files; landing the test itself is FR-002's implementation-phase work, not this
pass's). It reuses the file's own `_BUILT_IN_TACTICS_DIR`, `_SHIPPED_DIRECTIVES_DIR`, and
`_load_yaml` helpers (no new imports needed) and should be added to
`tests/doctrine/test_directive_consistency.py` verbatim (or equivalent) when FR-002 is
implemented:

```python
def test_size_assumption_bypass_failure_mode_documented() -> None:
    """FR-002 (mission analyze-prompt-context-load-01M3F4BV, issue #5005): DIRECTIVE_044 /
    the canonical-source-unification tactic must name the evidenced failure mode explicitly —
    an agent bypassing a canonical prompt/skill/CLI surface on an *unverified size assumption*
    instead of attempting to load/measure it first. Neither doctrine-source file names this
    failure mode today.

    RED today (2026-09-26, verified during the plan-revision pass): the substring below is
    absent from both candidate files. GREEN once FR-002 lands the new failure-mode entry
    and/or procedure line in either or both files (spec.md says "and/or" — this test accepts
    either as satisfying the requirement).
    """
    tactic_path = _BUILT_IN_TACTICS_DIR / "canonical-source-unification.tactic.yaml"
    directive_path = _SHIPPED_DIRECTIVES_DIR / "044-canonical-sources-and-unification.directive.yaml"
    assert tactic_path.is_file(), f"expected FR-002 target file to exist: {tactic_path}"
    assert directive_path.is_file(), f"expected FR-002 target file to exist: {directive_path}"

    tactic_data = _load_yaml(tactic_path)
    directive_data = _load_yaml(directive_path)

    failure_modes = tactic_data.get("failure_modes", []) or []
    procedures = directive_data.get("procedures", []) or []

    needle = "unverified size assumption"
    found_in_tactic = any(needle in str(entry) for entry in failure_modes)
    found_in_directive = any(needle in str(entry) for entry in procedures)

    assert found_in_tactic or found_in_directive, (
        f"Expected the failure-mode text {needle!r} in "
        f"canonical-source-unification.tactic.yaml's failure_modes and/or "
        f"044-canonical-sources-and-unification.directive.yaml's procedures "
        f"(FR-002, analyze-prompt-context-load-01M3F4BV / issue #5005) — found in neither."
    )
```

**Confirmed genuinely RED this pass** (real invocation while staged, not merely asserted):
`grep -c "unverified size assumption" packs/built-in/tactics/canonical-source-unification.tactic.yaml
packs/built-in/directives/044-canonical-sources-and-unification.directive.yaml` returns `0`
for both files, and running the test itself while it was staged
(`.venv/bin/python -m pytest tests/doctrine/test_directive_consistency.py -k size_assumption`)
failed with `AssertionError: ... found in neither` — a real, non-vacuous red-first pin, not a
vacuous one. The file's other 8 pre-existing tests remained green with this addition staged
(`8 passed, 1 failed` for the full file). The test was then reverted from the working tree
per this pass's own scope (see above) — it is documented here, verified red, and ready to be
(re-)added verbatim during FR-002's implementation phase, where it will flip to GREEN once
the failure-mode text lands in either candidate file; no changes to the test itself are
needed at that point.

**Required companion tests (both re-confirmed to exist and pass this revision pass —
spec.md's own binding requirement, not optional; see "Baseline method" below for their
counts):**

- `tests/architectural/test_doctrine_regenerate_graph_roundtrip.py` —
  `test_regenerate_graph_check_is_byte_identical` shells out to
  `spec-kitty doctrine regenerate-graph --check` and asserts exit 0, hard-failing (never
  skip/xfail) if the CLI is uninvokable. This is the direct mechanical proof that FR-002's
  source-YAML edit was correctly followed by a real `regenerate-graph` write (step 2 above)
  — an un-regenerated edit would leave this test RED.
- `tests/architectural/test_pack_manifest_no_author_edit.py` — asserts the authored pair
  (`packs/built-in/pack.yaml`, `pack.md`) stays byte-unchanged when the manifest generator
  runs, and that neither of its two owned source modules writes to those authored filenames.
  FR-002 does not touch `pack.yaml`/`pack.md` at all, so this test's role here is a
  regression fence: it proves the doctrine-content edit did not accidentally also touch the
  authored manifest pair.

**Added 2026-09-27 (Operator Decision 8): the profile-pinning tests already covering the
four edited agent-profile files.** These are pre-existing tests, not new companions this FR
adds — they are re-exercised by the diff without any code change to them, and are named here
for completeness given the file set widened to `packs/built-in/agent_profiles/`:

- `tests/doctrine/test_shipped_profiles.py` — loads every shipped profile via
  `AgentProfileRepository`, schema-validates it, and checks for hierarchy errors and duplicate
  ids. A malformed `rationale` string (e.g. broken YAML block-scalar syntax from the `>-`
  folding used in this mission's edits) would fail here.
- `tests/doctrine/agent_profiles/test_supply_chain_profile_bindings.py` — resolves
  `implementer-ivan`, `python-pedro`, and `architect-alphonso` (three of this mission's four
  edited profiles, among others) through `resolve_profile` and asserts on their DIRECTIVE_051
  citation; unrelated to DIRECTIVE_044 in content, but a regression fence proving this
  mission's DIRECTIVE_044 edit did not corrupt those same profiles' other directive citations.
- `tests/doctrine/test_package_smoke.py` — smoke-imports `AgentProfileRepository` and
  resolves `implementer-ivan` via a subprocess; catches an import-time or resolution-time
  break in any edited profile file.

All three already fall under `tests/doctrine/`, the same directory
`test_directive_consistency.py` lives in — so they do not add a new module to the gate set
below (`select_modules()` already returns `frozenset({'charter'})` on the strength of
`tests/doctrine/test_directive_consistency.py` alone, per the "ci-modules.yml" bullet below).

## The gate set for this mission

**Re-derived from scratch this revision pass (2026-09-26), on the merged checkout.** Method:
cross-checked against the actual `.github/workflows/*.yml` files in this checkout
(`ci-router.yml`, `packs.yml`, `ci-modules.yml`, `ci-aggregate.yml` re-read this pass) and
against `~/.hermes/skills/sk/SKILL.md`'s §Gates table (re-verified 2026-09-23 against
`.github/workflows/`) rather than re-deriving the whole CI story from first principles.
**Drift found against SKILL.md's table**: this checkout's `.github/workflows/` directory now
also contains `ci-fleet-verdict.yml` (a `workflow_run`-triggered post-hoc verdict aggregator,
reacting to other workflows after they finish — see the memory note that `workflow_run` jobs
run the default-branch copy and are untestable from a PR) and `ci-stale-running-sweep.yml`
(`schedule`/`workflow_dispatch` only). Neither carries a `pull_request` or `push` trigger, so
neither adds a new per-PR-blocking gate this mission's diff would newly hit — the drift is a
new file, not a new binding gate, and does not change the gate set below.

**ALWAYS-ON enforced gates** (`ci-router.yml`'s `always_on_jobs`, confirmed by direct
`Router.always_on_jobs` inspection — see "ci-parity" below): `archive-freeze`,
`commit-msg`, `import-linter`, `layer-rules`, `markdownlint`, `prose-scan`, `regen-check`
(`spec-kitty regen --check`), `router-gate`, `ruff`, `terminology`, `uv-lock`. These run on
every PR regardless of path.

**Path/diff-scoped gates that WILL fire for this mission's diff:**

- **`tests-corpus`** (`ci-router.yml`) — gated on the `corpus` filter group, whose globs
  (read directly from the dorny filter block) include `packs/**`, `kitty-specs/**/spec.md`,
  and `kitty-specs/**/plan.md`. Both FR-002's `packs/built-in/**` edits and this very
  plan-authoring commit's `kitty-specs/.../spec.md` + `.../plan.md` edits match this group.
- **`packs.yml` built-in lane** (`built-in-regen-check` and its sibling jobs) — gated on its
  own `changes` job's `built_in` filter, whose globs (read directly) include
  `packs/built-in/**` and `tests/architectural/test_pack_manifest_no_author_edit.py`. FR-002's
  edit to `packs/built-in/tactics/*.yaml` / `packs/built-in/directives/*.yaml` and the
  regenerated `.graph.yaml` fragments both fall under `packs/built-in/**`, so this lane
  fires: `regen --check`, the DRG `regenerate-graph --check`, the pack-manifest
  freshness/authored-only guard, the `-m corpus` suite, and the Claude Code plugin
  build+`claude plugin validate --strict`.
- **`ci-modules.yml` / per-module test shards**: **`{'charter'}` selected — a positive
  finding, unchanged in shape from the prior round despite the narrower file set.**
  `ci-modules.yml` calls `select_modules()` (`scripts/ci/gate_selection.py`), not
  `select_gates()`. `select_modules()` additionally maps tests-only diffs back to their
  owning module via `.github/ci-module-registry.yml`'s `test_dirs` (closing
  spec-kitty#4454's false-green bug, where a tests-only diff selected no per-PR shard).
  Re-verified directly this pass: `select_modules()` invoked in-process against this
  mission's actual, narrower planned file set (FR-002 only — no
  `.kittify/overrides/...analyze.md` in the set at all, since FR-001 no longer touches it)
  returns `frozenset({'charter'})` — driven specifically by
  `tests/doctrine/test_directive_consistency.py` (the FR-002 red-first test's home, per "Red-first
  tests" above — replacing the prior round's `tests/doctrine/test_resolver.py`), which falls
  under the `charter` module's registered `test_dirs` (`tests/charter`, `tests/doctrine`; the
  `charter` module row in `.github/ci-module-registry.yml`). This means the `charter`
  module's shard run (`pytest tests/charter tests/doctrine -m "not performance and not
  stress"`, per that row) DOES execute the FR-002 red-first content test as part of this PR's
  own CI — independent of the manual local verification recorded in "Baseline method" below.
  (See "Correction to this Method" below for why `select_gates()`'s `selected_code_shards: []`
  does not contradict this.) **Unaffected by the Operator Decision 8 widening (2026-09-27):**
  the four added `packs/built-in/agent_profiles/*.agent.yaml` files fall under the `packs/**`
  glob (same `corpus` filter group as the tactic file), and the three added test functions
  still land in `tests/doctrine/test_directive_consistency.py` — the same file, not a new
  one — so `select_modules()`'s `frozenset({'charter'})` result is unchanged by the widening.

**Not applicable / no signal from this diff:** `ci-nightly.yml` (nightly-only, not PR-gated),
`sonar.yml` (nightly informational scan) and `ci-aggregate.yml`'s `sonar-pr` job (per-PR but
`continue-on-error`, reported not required) both run only against `src/**` shard coverage,
which this diff produces none of, so they will report vacuously green/skip rather than
meaningfully cover this change; the `ci-aggregate.yml` diff-cover ≥90% gate applies to
changed LINES in covered files, and this diff changes no `src/**` lines, so it has nothing
to measure here. `ci-windows.yml`, `docs-pages.yml`, and
`check-spec-kitty-events-alignment.yml` are unrelated surfaces this diff does not touch.

**Explicitly NOT enforced gates**, per SKILL.md's re-verified 2026-09-23 table, cross-checked
against this checkout's own `.github/workflows/` this pass with no drift found (so a future
reader does not chase them for this mission): commit-message lint (`commit-msg` job only
prints subjects, never fails), markdownlint (runs `... || true`, can never fail), mypy (in no
CI workflow at all — `make typecheck` only, and only on two unrelated files), Bandit/pip-audit
(no workflow), the "kernel 90%" / "mission-loader ≥90%" coverage floors (no such named floors
exist), and SonarCloud's quality-gate status (whole-repo scan is schedule-only; the per-PR
`sonar-pr` job is `continue-on-error`, never merge-blocking). diff-cover ≥90% on changed
lines **is** enforced but — per the bullet above — has no `src/**` lines to measure in this
mission's diff.

**`make ci-parity` — actually run this pass, both for real and simulated:**

1. **Real invocation, current committed diff** (`make ci-parity`, run this pass against
   `origin/main` via the tool's own default base-ref — this branch's actual diff now
   includes the whole mission's history: spec/research/plan/tracer/reviews commits plus the
   `origin/main`-merge commit, though `local_gate_parity.py`'s merge-base-diff idiom against
   the CURRENT `origin/main` tip collapses that to this mission's own net-new changes, 67
   paths, not the raw 262-file `git diff <old-merge-base>..HEAD`): **`Selected jobs (12)`** —
   `archive-freeze`, `commit-msg`, `import-linter`, `layer-rules`, `markdownlint`,
   `prose-scan`, `regen-check`, `router-gate`, `ruff`, `terminology`, `tests-corpus`,
   `uv-lock` — and **`Selected code shards (0): (none)`**. Identical job set to the prior
   plan round's real invocation, matching the `corpus`-group match from
   `kitty-specs/.../{spec,plan}.md` already on this branch.
2. **Simulated, the actual FR-002-only implementation diff** (no implementation exists yet in
   this plan phase; `make ci-parity` itself is HEAD-relative so it cannot answer a
   not-yet-committed diff without committing it, which this plan-revision phase must not do).
   The SAME authority `make ci-parity` calls — `scripts.ci.gate_selection.select_gates()`
   AND its sibling `select_modules()` — was invoked directly, in-process this pass, against
   the exact planned, narrower file set (no `.kittify/overrides/...analyze.md` — FR-001 no
   longer touches it):
   `packs/built-in/tactics/canonical-source-unification.tactic.yaml`,
   `packs/built-in/directives/044-canonical-sources-and-unification.directive.yaml`,
   `packs/built-in/tactic.graph.yaml`, `packs/built-in/directive.graph.yaml`,
   `tests/doctrine/test_directive_consistency.py`,
   `tests/architectural/test_doctrine_regenerate_graph_roundtrip.py`,
   `tests/architectural/test_pack_manifest_no_author_edit.py`. Real, non-guessed output:
   `GateSelection(matched_groups=frozenset({'corpus'}), unmatched_src=False,
   selected_jobs=frozenset({'tests-corpus', 'ruff', 'router-gate', 'terminology', 'uv-lock',
   'layer-rules', 'regen-check', 'archive-freeze', 'markdownlint', 'prose-scan', 'commit-msg',
   'import-linter'}), selected_code_shards=frozenset())` — identical job set to the real
   invocation in (1) and to the prior round's simulated FR-001+FR-002 set, confirming the
   narrower FR-002-only diff selects the same router/job-level gate surface (still
   `packs/**`-shaped, no `src/**`). `select_modules()` against the same file set returns
   `frozenset({'charter'})`, unchanged from the prior round (see the corrected "ci-modules.yml
   / per-module test shards" bullet above).

**Correction to this Method** (unchanged from the prior round, re-confirmed this pass):
`make ci-parity` (via `select_gates()`) only answers the router/job-level question — which
top-level CI jobs fire — and is **not** a complete proxy for "what CI actually runs" when the
diff touches `tests/**`. `select_modules()` is the complementary authority for module-shard
selection (see the corrected "ci-modules.yml / per-module test shards" bullet above): for
this exact, narrower planned file set it returns `frozenset({'charter'})`, not the empty set
`select_gates()`'s `selected_code_shards` alone would suggest. Both tools are correct for the
question each answers; `make ci-parity` alone under-claims module-shard coverage for a
`tests/**`-touching diff.

## Baseline method

Per the charter's Pre-existing Failure Reporting Rule, the orchestrator (not this plan-phase
agent) files an issue for genuine pre-existing reds; this plan only records what was found.

**Re-baselined this revision pass (2026-09-26) on the CURRENT merged `main`, not the old
merge-base.** The prior plan round's baseline was taken at `da6d0af97eb1291cb08d4d0a6772cdfc43df4496`
(before PR #5133 merged) and is now stale. **Method**: a separate git worktree at
`origin/main`'s current tip as merged into this branch, commit `34b53d78e`, was created —
`git worktree add <workspace-root>/5005-baseline 34b53d78e` — under the sibling
`SK-missions/` mission-workspace directory (never a path this repository's own checkout
cites), never under `/tmp` (tmpfs/RAM, inappropriate for a git worktree per the operator's
own standing note) and never checked out in this checkout. The already-synced `.venv` from
this checkout was reused via `PYTHONPATH=<workspace-root>/5005-baseline/src` rather than
syncing a second environment — verified this actually works before relying on it: `pyproject.toml`
and `uv.lock` are byte-identical between this checkout and the `34b53d78e` worktree (`diff`
confirmed empty for both), so the pinned dependency set is unchanged and the reuse is sound;
no second `uv sync` was needed in the baseline worktree.

The test files run there are the ones this mission's changed behaviour actually touches per
this revision's FR-002 test plan (narrower than the prior round's four-file set, which
included the now-irrelevant `tests/doctrine/test_resolver.py` and
`tests/doctrine/missions/test_mission_step_resolver.py` — both were about FR-001's resolver
change, which no longer exists): `tests/doctrine/test_directive_consistency.py` (the FR-002
red-first test's home — without this pass's new test, since it does not exist on the
`34b53d78e` commit), `tests/architectural/test_doctrine_regenerate_graph_roundtrip.py`, and
`tests/architectural/test_pack_manifest_no_author_edit.py`.

**Result**: `14 passed in 91.28s` (8 + 2 + 4 = 14, per-file breakdown below). **Baseline:
none — no pre-existing failures** among these three files at `34b53d78e`. No pre-existing
red test ids to record (per the mission brief, none found, so none filed).

Per-file counts (`PWHEADLESS=1`, `-q`, `-p no:cacheprovider`):

| Test file | Result |
|---|---|
| `tests/doctrine/test_directive_consistency.py` | 8 passed |
| `tests/architectural/test_doctrine_regenerate_graph_roundtrip.py` | 2 passed |
| `tests/architectural/test_pack_manifest_no_author_edit.py` | 4 passed |

No environmental gotcha this run — this checkout's `.venv` was already re-synced
(`uv sync --frozen --all-extras`) earlier in this same revision pass (see
`tracer-tooling-friction.md`'s newly-appended entry), and stripping `~/.local/bin` from
`PATH` before invoking pytest (the same stale-global-install workaround the prior round
recorded) avoided the previously-hit `shutil.which("spec-kitty")` false red. The worktree
was removed after this baseline run completed:
`git worktree remove <workspace-root>/5005-baseline` — confirmed gone via
`git worktree list` (only this checkout listed) and `git status --porcelain` (no residue
from the worktree operation itself).

## Reflexivity

**Revised for Operator Decision 7**: the prior plan round's reflexivity discussion analyzed
what happens to a mission mid-flight through `/spec-kitty.analyze` when FR-001's `git rm`
deletion lands — an atomic-filesystem-operation argument about resolver-tier fall-through.
That discussion is moot: FR-001 no longer executes, no file is deleted, and no resolver-tier
transition happens for any concurrently-running mission to observe. It is not retained or
adapted, since retaining it would misleadingly imply a live concurrency hazard where none
now exists.

**What, if anything, is a live reflexivity concern for FR-002 alone**: FR-002 is a
content-only addition to two already-shipped, already-loaded doctrine-source YAML files,
landed through the existing `spec-kitty doctrine regenerate-graph` write-mode path. Stated
honestly rather than padded: there is minimal-to-no reflexivity concern here. A mission
mid-flight through any step that loads `canonical-source-unification.tactic.yaml` or
`044-canonical-sources-and-unification.directive.yaml` (e.g. an agent consulting
DIRECTIVE_044 while reasoning about a split-brain surface) either reads the doctrine before
this mission's commit lands (old failure_modes/procedures list, one entry short) or after
(new entry present) — the same ordinary "doctrine content changed between reads" situation
any doctrine-pack edit creates, with no atomicity or intermediate-state hazard specific to
this change: a YAML file's content is either the pre-edit or post-edit version at read time,
and the DRG regeneration step (`spec-kitty doctrine regenerate-graph`) is run and committed
in the same commit as the source edit (per "Generated artifacts" above), so no reader ever
sees a stale-relative-to-source `.graph.yaml` fragment. There is no equivalent of the prior
round's "half-deleted file" concern to analyze, because nothing is deleted.

## Tracer files

Existing convention confirmed by directory listing (unchanged from the prior round): flat
`tracer-<category>.md` files at the mission root, NOT a `tracers/` subdirectory. All three
tracer files (`tracer-approach.md`, `tracer-design-decisions.md`, `tracer-tooling-friction.md`)
already existed with Plan-phase entries from the prior round before this revision pass began.
This revision pass **appends** a new, dated (2026-09-26, Operator Decision 7 revision pass)
section to each, preserving every existing entry rather than deleting or rewriting it: what
changed in this revision pass and why (`tracer-approach.md`), the new design decisions this
pass made — the choice of `tests/doctrine/test_directive_consistency.py` as the FR-002
red-first test's home over the prior round's now-irrelevant `tests/doctrine/test_resolver.py`,
and the choice of the `34b53d78e` baseline-worktree commit (`tracer-design-decisions.md`) —
and any tooling friction hit during this pass (`tracer-tooling-friction.md` — the stale
`.venv` needing `uv sync --frozen --all-extras` again, and the same stale-global-`spec-kitty`
`PATH` workaround the prior round already documented, both classified per AGENTS.md's
existing friction categories). The prior round's finding about `spec-kitty agent
tracer-append`'s COORD-partition/`traces/`-subdirectory mismatch against this mission's
`single_branch` topology still holds and is not re-litigated here; this revision pass again
edited the three files directly for the same reason.

## PR-overlap section (Dependencies & Sequencing addendum)

**Superseded 2026-09-27 by Operator Decision 8's widened file set — see spec.md's C-002 for
the current, binding re-check (kept here as the historical record of the pre-Decision-8
write set and PR list, not deleted).** spec.md's C-002 ("Sequencing vs. open PRs" — rewritten
per Decision 6, Decision 7, and again 2026-09-27 for Decision 8) is the up-to-date source for
this check; its "Live open-PR overlap re-check (2026-09-27, round-2 rework, widened
Decision-8 file set)" ran `gh pr list`/`gh pr view --json files` against the full widened set
— the two doctrine-source files, their graph fragments, all four
`packs/built-in/agent_profiles/*.agent.yaml` files, `packs/built-in/pack-manifest.yaml`, and
`tests/doctrine/test_directive_consistency.py` — against that day's open-PR list (#5161,
#5137, #5028, #5009, #4995) and found **zero overlap with any of the five**, including
against the newly-added `packs/built-in/agent_profiles/` and `tests/doctrine/` paths. No
rebase/merge-order file conflict is created by this mission's diff against any PR open on
that date. This plan does not re-run that check independently; it defers to C-002 as the
single binding source rather than maintaining two drift-prone copies of the same live
`gh pr list` result.

**Historical text below (pre-Decision-8, 2026-09-26 revision pass — kept for the audit trail,
not the current binding scope):**

**Rewritten this revision pass — the #5133 modify/delete git-mechanics risk the prior round
documented at length no longer exists.** #5133 is now MERGED (not open), and this mission no
longer touches `.kittify/overrides/missions/software-dev/command-templates/analyze.md` at
all (Decision 7 drops FR-001), so there is no override file in this mission's diff for any
open PR to conflict with, and no deletion-vs-modify race to resolve.

This mission's actual, current write set (FR-002 only, as scoped 2026-09-26 — since widened
by Decision 8, see above):
`packs/built-in/tactics/canonical-source-unification.tactic.yaml`,
`packs/built-in/directives/044-canonical-sources-and-unification.directive.yaml`,
`packs/built-in/tactic.graph.yaml`, `packs/built-in/directive.graph.yaml`,
`tests/doctrine/test_directive_consistency.py` (the red-first test's home), and the two
required companion test files (`tests/architectural/test_doctrine_regenerate_graph_roundtrip.py`,
`tests/architectural/test_pack_manifest_no_author_edit.py` — both already exist, neither is
newly created).

**Checked fresh this pass, not trusted from the prior round** (read-only
`gh pr list --repo spec-kitty/spec-kitty --state open --json number,title,mergeable,mergeStateStatus`,
plus `gh pr view <n> --json files` per PR — no writes/comments made). The open-PR list itself
has changed since the prior round: #5133 has merged and #5136 no longer appears in the open
list at all (merged or closed since the prior round; not investigated further, since it is
absent from the current open set either way). The current open list is:

- **#5141** ("[#5135] meta.json read authority: account the bake site, route the 0.13.x
  migration reads, fail census scanners closed") — `mergeStateStatus=CLEAN`,
  `mergeable=MERGEABLE`. Touches `docs/changelog/CHANGELOG.md`, `pyproject.toml`,
  `src/specify_cli/upgrade/migrations/m_0_13_*.py`, and test files under
  `tests/architectural/`, `tests/research/`, `tests/specify_cli/`, `tests/upgrade/`. **Zero
  overlap** with this mission's write set — confirmed by direct file-list comparison.
- **#5137** ("fix(coord): probe the remote before flattening a coordination mission
  (#4979)") — `mergeStateStatus`/`mergeable=UNKNOWN` (GitHub has not computed a fresh
  mergeability verdict at check time). Touches `src/specify_cli/coordination/*`,
  `src/specify_cli/git/remote_probes.py`,
  `src/specify_cli/cli/commands/{_coordination_doctor,implement,mission_type}.py`, its own
  `kitty-specs/coord-branch-remote-probe-01M3F6M7/**` planning tree, and coordination test
  files. **Zero overlap** — confirmed.
- **#5028** ("docs: add MySpec to ecosystem & specification discovery tools") —
  `mergeStateStatus`/`mergeable=UNKNOWN`. Touches only `README.md`. **Zero overlap** —
  confirmed.
- **#5009** ("fix: retain validated owned checkout authority across mission lifecycle") —
  `mergeStateStatus`/`mergeable=UNKNOWN`. Touches `src/runtime/next/prompt_builder.py`,
  `src/mission_runtime/resolution.py`, `src/runtime/next/{decision,runtime_bridge,runtime_bridge_engine}.py`,
  `src/specify_cli/coordination/{status_service,status_transition}.py`,
  `src/specify_cli/core/mission_creation.py`, `src/specify_cli/workspace/context.py`,
  `pyproject.toml`, `docs/development/owned-checkout-charter-resolution.md`, and its own test
  files. **Zero overlap** — confirmed. (This mission no longer has any relationship to
  `prompt_builder.py` at all now that FR-005/006/007 are out of scope per Decision 6 and
  FR-001's resolver-tier claim is moot per Decision 7 — this PR is noted for completeness
  only.)
- **#4995** ("fix(charter): make concurrent mission-template resolution thread-safe") —
  `mergeStateStatus`/`mergeable=UNKNOWN`. Touches
  `src/charter/offering/missions/mission_step_repository.py` /
  `mission_type_repository.py`, `.github/ci-shard-timings.json`, `docs/changelog/CHANGELOG.md`,
  its own `kitty-specs/concurrent-template-config-race-4589-01M35M6B/**` planning tree, and
  two test files under `tests/core/` and `tests/doctrine/missions/`. **Zero overlap** —
  confirmed.

**Net finding**: across the entire current open-PR list, **zero file-level overlaps** with
this mission's actual, narrower write set. No rebase/merge-order conflict, git-mechanics or
logical, is created by this mission's diff against any currently-open PR. No PR/issue writes
were made this pass; all `gh` calls were read-only `list`/`view`.

## Project Structure

### Documentation (this mission)

```
kitty-specs/analyze-prompt-context-load-01M3F4BV/
├── spec.md              # Final, squad-passed — revised for Operator Decision 7 (this pass's predecessor commit)
├── plan.md              # This file — revised this pass for Operator Decision 7
├── research.md          # Already delivered (FR-003), including § 10 merged-branch addendum — referenced, not re-authored
├── tracer-approach.md              # Appended this pass (pre-existing file, prior-round content preserved)
├── tracer-design-decisions.md      # Appended this pass (pre-existing file, prior-round content preserved)
├── tracer-tooling-friction.md      # Appended this pass (pre-existing file, prior-round content preserved)
└── tasks.md             # Phase 2 output (/spec-kitty.tasks — NOT produced by this plan)
```

No `data-model.md`, `quickstart.md`, or `contracts/` are produced — this mission has no data
model (Key Entities in spec.md are existing filesystem/config concepts, not new persisted
entities) and no new external contract.

### Source code (repository root)

No new directories. `.kittify/overrides/missions/software-dev/command-templates/analyze.md`
is **dropped from this list entirely** — FR-001 no longer touches it at all (Decision 7). The
touched surfaces, **updated 2026-09-27 for Operator Decision 8 to match what actually
shipped** (supersedes the narrower pre-Decision-8 list this table originally held):

```
packs/built-in/tactics/canonical-source-unification.tactic.yaml          # EDITED (FR-002, +1 failure_modes entry; directive.yaml's procedures array NOT touched — "and/or")
packs/built-in/agent_profiles/architect-alphonso.agent.yaml              # EDITED (FR-002/Decision 8, DIRECTIVE_044 rationale +clause)
packs/built-in/agent_profiles/implementer-ivan.agent.yaml                # EDITED (FR-002/Decision 8, DIRECTIVE_044 rationale +clause)
packs/built-in/agent_profiles/doctrine-daphne.agent.yaml                 # EDITED (FR-002/Decision 8, DIRECTIVE_044 rationale +clause)
packs/built-in/agent_profiles/python-pedro.agent.yaml                    # EDITED (FR-002/Decision 8, DIRECTIVE_044 rationale +clause)
packs/built-in/pack-manifest.yaml                                        # REGENERATED (FR-002 companion step — content hashes only; tactic.graph.yaml/directive.graph.yaml did NOT diff, see "Generated artifacts")
tests/doctrine/test_directive_consistency.py                             # EXTENDED (3 test functions: content-title-anchored, own-source-file, rendered-reachability — see "Red-first tests")
tests/architectural/test_doctrine_regenerate_graph_roundtrip.py          # Required companion, unmodified, must pass
tests/architectural/test_pack_manifest_no_author_edit.py                 # Required companion, unmodified, must pass
tests/doctrine/test_shipped_profiles.py                                  # Pre-existing profile-pinning test, unmodified, must pass
tests/doctrine/agent_profiles/test_supply_chain_profile_bindings.py      # Pre-existing profile-pinning test, unmodified, must pass
tests/doctrine/test_package_smoke.py                                     # Pre-existing profile-pinning test, unmodified, must pass
```

**Structure Decision**: single project (this repository), no new directories. Every touched
path already exists in the repository today; this mission adds/removes content within the
existing structure, per the smallest-viable-diff-first reconciliation order in the charter's
"Reconciling change-scope tensions" section.

## Complexity Tracking

*Empty by design — no Charter Check violations to justify. No new project, no new
architectural layer, no repository-pattern-style indirection introduced.*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| (none) | — | — |
