---
work_package_id: WP01
title: 'Advisory doctrine: unverified-size-assumption failure mode'
dependencies: []
requirement_refs:
- FR-002
- FR-001
- FR-003
- FR-004
- FR-005
planning_base_branch: fix/analyze-prompt-context-load-5005
merge_target_branch: fix/analyze-prompt-context-load-5005
branch_strategy: Planning artifacts for this mission were generated on fix/analyze-prompt-context-load-5005. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/analyze-prompt-context-load-5005 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-analyze-prompt-context-load-01M3F4BV
base_commit: 6fd106041b9d2328c6b67ef4a888ea96f7d4325d
created_at: '2026-09-26T22:39:55.465658+00:00'
subtasks:
- T001
- T002
- T003
- T004
history: []
agent_profile: implementer-ivan
authoritative_surface: packs/built-in/
create_intent: []
execution_mode: code_change
model: claude-sonnet-4-6
owned_files:
- packs/built-in/tactics/canonical-source-unification.tactic.yaml
- packs/built-in/directives/044-canonical-sources-and-unification.directive.yaml
- packs/built-in/tactic.graph.yaml
- packs/built-in/directive.graph.yaml
- tests/doctrine/test_directive_consistency.py
role: implementer
tags: []
tracker_refs: []
---

# WP01 — Advisory doctrine: unverified-size-assumption failure mode

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Revision Note (2026-09-27 — syncing this WP prompt to Operator Decision 8 and the shipped implementation)

This WP prompt's body predated Operator Decision 8 (spec.md, "Clarifications / Decisions" item
8, 2026-09-27) and, per this mission's own `/spec-kitty.analyze` finding F1 (`analysis-report.md`,
commit `a83b96fcf`), was never revised for it. This note, plus the edits to Objective, Context,
T001–T004, Definition of Done, and Reviewer Guidance below, bring the body into sync with
spec.md/plan.md (both already synced for Decision 8 at commit `6c2024d3c`) and with what the lane
branch actually shipped. Superseded text below is marked in place, not deleted, matching this
mission's own convention elsewhere (e.g. spec.md's inline "(Superseded by ...)" markers).

**What changed, in one paragraph:** the pre-Decision-8 design described below covers editing one
or both of two doctrine-source YAML files (the `canonical-source-unification` tactic and/or the
`044-canonical-sources-and-unification` directive) and landing one content-assertion test. What
actually shipped — across the round-1 WP01 rework and its round-2 follow-on, driven by the
pre-merge squad's `pr-contract-001`/`pr-tests-001` findings and review cycles 2–3
(`reviews/wp-WP01-cycle2.yaml`, findings WP01-C2-001/002/003, verdict `rejected`;
`reviews/wp-WP01-cycle3.yaml`, finding WP01-C3-001, verdict `rejected`; both resolved at cycle 4,
verdict `approved`) — is wider:

- Only the **tactic** file's `failure_modes` array was edited; the **directive** file's
  `procedures` array was left untouched (spec.md's "and/or" wording permits this — it is a valid
  choice, not a partial implementation).
- The doctrine-source edit alone does not reach a rendered agent: both the tactic's and
  DIRECTIVE_044's inline bodies exceed the per-artifact inline-body budget
  (`_PROFILE_INLINE_BODY_LIMIT_CHARS`, `token_budget.py`) and fall back to a fetch-stanza pointer
  in every automatic render path. The surface that *does* render unconditionally is the
  profile-citation header line built by `_render_directive_entry`
  (`src/charter/activation/context_renderers/profile_sections.py`), which appends a citing
  profile's own `directive-references[].rationale` **before** that budget check runs. This
  mission therefore also edits the DIRECTIVE_044 `rationale` on all four profiles that cite it —
  `architect-alphonso`, `implementer-ivan`, `doctrine-daphne`, `python-pedro`. Operator Decision 8
  retroactively authorizes the `implementer-ivan` edit (made on the round-1 rework's own
  authority, citing `pr-contract-001`, not a numbered Operator Decision at the time) and extends
  the same clause to the other three.
- `packs/built-in/pack-manifest.yaml` was regenerated (content hashes only — the
  `tactic.graph.yaml`/`directive.graph.yaml` DRG fragments did not diff, because
  `failure_modes`/`procedures` prose and profile `rationale` text are not part of either
  fragment's shape).
- Three test functions ship in `tests/doctrine/test_directive_consistency.py`, not the one
  described in T001 below: `test_size_assumption_bypass_failure_mode_documented` (revised in
  cycle 3 to anchor on the entry's own title, case-insensitively, rather than a whole-string
  substring match), `test_size_assumption_bypass_failure_mode_in_each_profiles_own_source_file`
  (parametrized over all four profiles; reads each profile's own YAML directly, never through
  `resolve_profile`), and `test_size_assumption_bypass_failure_mode_reaches_rendered_profile_context`
  (parametrized over all four profiles; exercises the real `_render_profile_sections` render
  path). The own-source test exists specifically because `python-pedro` `specializes_from`
  `implementer-ivan` in the DRG, and `AgentProfileRepository.resolve_profile`'s lineage
  union-merge resolves a same-`code` `directive-references` collision to the parent's entry — so
  the rendered-reachability test's `python-pedro` case stays green via inheritance even if
  `python-pedro`'s own file is reverted, and only the own-source test catches that revert
  (cycle-3 finding WP01-C3-001, confirmed by an isolated-worktree revert).

The `owned_files` frontmatter above was **not** hand-edited to add the four profile files or
`pack-manifest.yaml` — spec.md's "Authorized scope beyond WP01's `owned_files`/`lanes.json`
`write_scope`" note (below C-002) records this as a known, operator-authorized divergence, not
staleness, and this sync pass leaves that frontmatter untouched for the same reason.

---

## Objective

**Historical, pre-Decision-8 objective (kept below, not deleted — still correct as far as it
goes, but undercounts what shipped; see the Revision Note above for the widened scope: the
render-path seam through the four DIRECTIVE_044-citing agent profiles, and the three shipped
tests rather than one).**

First add a red-first content test pinning the failure-mode text's absence and confirm it is
genuinely RED; then add one new failure-mode entry (and/or one procedure line) to the
existing built-in canonical-source-unification doctrine pair, naming the failure mode this
mission's own root-cause trace evidenced — an agent bypassing a canonical prompt/skill/CLI
surface on an *unverified size assumption* instead of attempting to load/measure it first;
then regenerate the doctrine pack's DRG graph fragments in write mode; then confirm the
required companion tests still pass — in that order, per the charter's ATDD-first discipline
(C-011: the failing-first test is committed before any implementation commit).

## Context

Issue #5005 was originally filed on the claim that `/spec-kitty.analyze`'s prompt is "too
large to load." Live measurement (`research.md`, this mission) disproved that premise:
`analyze`'s rendered prompt is the third-smallest of the eight measured actions. The real,
evidenced defect is that the reporting agent never attempted to load or measure the prompt
before deciding to route around it — a gap the charter's existing canonical-sources doctrine
(`DIRECTIVE_044`, `canonical-source-unification` tactic) does not yet name explicitly. This
WP closes that doctrine gap.

By Operator Decision 7 (2026-09-26, spec.md), this is the **only build item left in this
mission**. FR-001 (deleting the stale `analyze` override) is superseded and executes no
change — upstream PR #5133 already resynced the override to canonical's exact bytes and
added its own parity gate (`tests/cross_cutting/test_kittify_override_parity.py`). Do
**not** touch `.kittify/overrides/missions/software-dev/command-templates/analyze.md` or
canonical `packs/built-in/missions/mission-steps/software-dev/analyze/prompt.md` in any way
— neither their content nor their size — in either form. This is FR-004, a hard constraint
on this WP, not merely on the mission as a whole.

The two target files already exist and already carry arrays of the right shape:
- `packs/built-in/tactics/canonical-source-unification.tactic.yaml` has a `failure_modes`
  array of free-form prose strings (six today).
- `packs/built-in/directives/044-canonical-sources-and-unification.directive.yaml` has a
  `procedures` array of free-form "Rule N — ..." strings (three today).

Both schemas (`src/charter/offering/schemas/tactic.schema.yaml`,
`src/charter/offering/schemas/directive.schema.yaml`) declare these arrays as
`type: array, items: {type: string}` with no positional/count constraint — a same-shape
addition needs no schema change (plan.md, "Contracts touched").

`packs/built-in/tactic.graph.yaml` and `packs/built-in/directive.graph.yaml` are
machine-generated DRG fragments derived from the source YAML above. They must be
regenerated via `spec-kitty doctrine regenerate-graph` in **write mode**, never
hand-edited, in the **same commit** as the source edit (plan.md, "Generated artifacts").
As shipped, this regeneration produced no diff to either `.graph.yaml` fragment for this
specific content shape (`failure_modes`/`procedures` prose and profile `rationale` text are not
part of either fragment's shape) — only `packs/built-in/pack-manifest.yaml`'s per-constituent
content hashes changed. This is the correct, verified output of running the step, not a step
that was skipped (plan.md, "Generated artifacts and their regenerating command").

**Render-path seam (added 2026-09-27, Operator Decision 8 — see the Revision Note above for the
full mechanism).** The doctrine-source edit above is necessary but not sufficient for the
failure-mode text to reach a working agent. Both `canonical-source-unification`'s rendered
inline body (~4.3K chars) and DIRECTIVE_044's rendered inline body (~3.5K chars) already exceed
the per-artifact inline-body budget (`_PROFILE_INLINE_BODY_LIMIT_CHARS`,
`src/charter/activation/context_renderers/token_budget.py`), so every automatic render path
falls back to a fetch-stanza pointer regardless of which doctrine-source file carries the new
text — reachable only via an agent's own explicit `--include` fetch, not by default. The one
surface that DOES render unconditionally is the profile-citation header line built by
`_render_directive_entry` (`src/charter/activation/context_renderers/profile_sections.py`,
function starts at line 527 on this checkout): it appends a citing profile's own
`directive-references[].rationale` for the matching `code` to the citation's header line
**before** the inline-body/fetch-stanza budget check runs. Because that rationale is emitted
unconditionally, this WP also appends the same failure-mode clause used in the tactic's
`failure_modes` entry to the `code: "044"` `directive-references` entry's `rationale` field in
all four profiles that cite DIRECTIVE_044 — `packs/built-in/agent_profiles/
{architect-alphonso,implementer-ivan,doctrine-daphne,python-pedro}.agent.yaml` (confirmed
exhaustive via `grep -rl 'code: "044"' packs/built-in/agent_profiles/`). No schema change:
`rationale` is already a free-form string field. This reach does **not** extend to the
mission-level orchestrating agent for `analyze`/`specify`/`plan`/`tasks`/`review`/`accept`,
whose step contract carries `agent_profile: null` — recorded as an explicit, unclosed residual
in spec.md's "Known residual (out of scope): mission-level orchestrating agent never receives
this warning" section (WP01-C2-003), not claimed as fixed here.

**Note on `FR-001`, `FR-003`, `FR-004`, and `FR-005` in this WP's `requirement_refs`:** Only
FR-002 is actually built by this WP. The other four ride along in `requirement_refs` for the
same underlying reason (below), each with its own disposition:

- **FR-001** (deleting the stale `analyze` override) is superseded per Operator Decision 7
  (spec.md) and executes no change at all — upstream PR #5133 already resynced the override
  to canonical's exact bytes.
- **FR-003** (the prompt-size measurements that originally motivated this mission) was
  already delivered pre-WP by `research.md` during an earlier mission phase. This WP does not
  re-measure anything or add new evidence for FR-003 — it only inherits that prior reference.
- **FR-004** (do not edit `analyze/prompt.md`'s content or size, canonical or override) is a
  negative constraint enforced by this WP's Definition of Done, not a positive deliverable.
- **FR-005** (the governance-context budget fix) is explicitly OUT OF SCOPE for this mission
  (Operator Decision 6, spec.md) and is NOT implemented by this WP — do not attempt it.

All four are listed in `requirement_refs` only because `finalize-tasks --validate-only`'s
requirement-mapping check treats spec.md's own "- **FR-NNN" bulleted lines (in the "Remaining
scope after Operator Decision 7" section) as *declared* requirements needing WP coverage — a
parser limitation (`src/specify_cli/requirement_mapping.py::_declared_ids`'s bold-bullet-lead
heuristic fires on any line starting `- **FR-NNN`, regardless of whether the prose says "in
scope" or "out of scope", superseded, or already-delivered, and regardless of whether the FR
has an actual row in the Functional Requirements table). FR-005 has no table row in spec.md's
Functional Requirements section at all. This is documented tooling friction
(`tracer-tooling-friction.md`), not a claim that this WP builds FR-001, FR-003, FR-004, or
FR-005. The underlying parser limitation is tracked upstream as issue #5065 ("Requirement
lifecycle status"), which would let a future `requirement_refs` schema record each FR's
disposition (builds / references / constrains / superseded) instead of bundling all four into
one undifferentiated list. See the "Requirement disposition" table in the Definition of Done
below for the per-FR no-op/control annotation this repo's own review checklist
(`review/prompt.md` item 4/4b) requires.

FR-002 is advisory-only doctrine prose: no automated test in this repository can verify a
future agent's prompt-following behavior against it. The only checkable property is that
the failure-mode text exists verbatim and is syntactically valid doctrine. plan.md's
"Red-first tests" section already worked out the correct test home
(`tests/doctrine/test_directive_consistency.py` — the only doctrine-content test file whose
path constants resolve correctly post-relocation) and supplies the exact test function body
to use.

## Subtask T001: Add the red-first content test, and confirm it is genuinely RED

**Purpose**: Per the charter's ATDD-first discipline (C-011), land the failing-first test
*before* any implementation commit. This pins the failure-mode text's presence with a
genuine, currently-RED test — the only mechanically checkable property FR-002 has (this is
advisory-only prose; no test can verify a future agent's behavior against it).

**Revision note (2026-09-27, Operator Decision 8 / cycle-3 finding WP01-C3-001 — superseded
design below, kept as the historical pre-Decision-8 record, not deleted).** The steps and test
body immediately below describe the single-test design that was correct before the render-path
seam (see Context above) was established. As shipped, `tests/doctrine/test_directive_consistency.py`
carries **three** test functions, not one:

1. **`test_size_assumption_bypass_failure_mode_documented`** — the same content-assertion intent
   as the design below, but revised in cycle 3 (pre-merge squad finding `pr-tests-001`) to anchor
   on the failure-mode entry's own *title* (the segment before the first `:`), case-insensitively,
   via a small `_entry_title()` helper — not a substring match against the whole entry string. The
   original substring-anywhere approach below was found to pass only because of an incidental
   lowercase restatement of the needle phrase in the entry's closing sentence, not because the
   assertion was anchored to the entry's stable identity.
2. **`test_size_assumption_bypass_failure_mode_in_each_profiles_own_source_file`** (new,
   parametrized over all four DIRECTIVE_044-citing profiles) — reads each profile's own YAML file
   directly (never through `resolve_profile`) and asserts its own `directive-references[].rationale`
   for `code: "044"` contains the needle. This is the test that catches a revert of
   `python-pedro.agent.yaml`'s own hunk specifically (see next item).
3. **`test_size_assumption_bypass_failure_mode_reaches_rendered_profile_context`** (parametrized
   over all four profiles) — the real proof, exercising the production `_render_profile_sections`
   render path against the actual shipped doctrine catalog. `python-pedro` `specializes_from`
   `implementer-ivan` in the DRG, and `AgentProfileRepository.resolve_profile`'s lineage
   union-merge resolves a same-`code` `directive-references` collision to the parent's entry — so
   this test's `python-pedro` case proves the text reaches it via DRG lineage inheritance from
   `implementer-ivan`, not via its own file, which is exactly why test 2 above exists as a
   companion, not a duplicate: reverting only `python-pedro`'s own hunk leaves this test 3 green
   for `python-pedro` but flips test 2 RED.

Steps 1-5 below (the single-test T001 as originally authored) still describe the correct home
(`tests/doctrine/test_directive_consistency.py`), the correct ATDD-first commit sequencing, and
the correct reasoning for rejecting the two alternative test-file candidates — none of that is
superseded. Only the number of test functions and test 1's exact assertion logic (title-anchored,
not whole-string) changed; apply steps 1-5 below to all three test functions when reproducing this
work, not only to the one shown in the code fence.

**Steps**:
1. Open `tests/doctrine/test_directive_consistency.py`. This is the correct home — it is
   the one doctrine-content test file whose path constants (`_BUILT_IN_TACTICS_DIR`,
   `_SHIPPED_DIRECTIVES_DIR`) resolve correctly for the post-relocation
   `packs/built-in/<kind>/` layout (plan.md verified this; do NOT extend
   `tests/doctrine/directives/test_schema_compatibility.py` or
   `tests/doctrine/test_tactic_compliance.py` — both have stale path constants pointing at
   a `src/charter/offering/{directives,tactics}/built-in` location that does not exist on
   this checkout, and their content-scoped tests collect as vacuous `[NOTSET]`
   parametrizations that can never fail).
2. Add the following test function verbatim (already verified genuinely RED against the
   pre-T002 files, and reusing the file's own existing `_BUILT_IN_TACTICS_DIR`,
   `_SHIPPED_DIRECTIVES_DIR`, and `_load_yaml` helpers — no new imports needed). The fence
   below sits at 0-space margin, matching plan.md's "Red-first tests per changed behaviour"
   section byte-for-byte — do not nest it inside this list item's indentation when copying it
   in:

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

3. Before landing T002's content edit, confirm this test is genuinely RED (run it against
   the pre-edit files — it must fail with the `AssertionError` above, not error out for an
   unrelated reason such as a missing helper or a bad import).
4. **Commit this test now, as its own standalone commit, before starting T002's content
   edit** — per the charter's ATDD-First Discipline (C-011: "The ATDD test is committed as a
   separate commit … BEFORE any implementation commits"). Run
   `.venv/bin/spec-kitty safe-commit` (never a bare `git commit`) with a conventional-commit
   `test:` type (this repo's commitlint `type-enum` has no `tasks`/`doctrine` type; `test` is
   the correct type for a test-only addition), passing the test file as the required
   `FILES...` positional argument alongside the message flag, e.g.
   `.venv/bin/spec-kitty safe-commit tests/doctrine/test_directive_consistency.py -m
   "test(doctrine): add red-first test for size-assumption-bypass failure mode (#5005)"`. This
   commit must contain only the T001 test-file change — do not fold T002's or T003's edits
   into it, and do not conflate this commit boundary with the separate one T003 step 4
   describes (that one governs T002+T003 landing *together*, in a second commit, after this
   one).
5. After T002 lands, re-run and confirm GREEN, and confirm the file's other 8 pre-existing
   tests remain green (no regression from this addition).

**Files**: `tests/doctrine/test_directive_consistency.py` (extended, +1 test function, ~35
lines). Do not modify any of the file's other 8 existing tests or its helpers.

**Validation**: `.venv/bin/python -m pytest tests/doctrine/test_directive_consistency.py -v` reports the new test genuinely RED before T002's edit lands, then PASSING alongside the pre-existing 8 (9 passed total) after it lands. Confirmed RED-before/GREEN-after, not merely asserted.

## Subtask T002: Add the failure-mode entry to the tactic and/or directive file, and to the four DIRECTIVE_044-citing profiles' rationale

**Purpose**: Land the advisory doctrine text naming the evidenced failure mode, making T001's
red test go green.

**Revision note (2026-09-27, Operator Decision 8).** As shipped, this subtask has two parts, not
one: the doctrine-source edit (steps 1-4 below, unchanged from the original design — and, as
shipped, only the tactic file was actually edited; the directive file's `procedures` array was
left untouched, a valid "and/or" choice) **and** the profile-citation edit (new step 5 below),
which is the part that makes the text reach a rendered agent at all (see Context's "Render-path
seam" note above).

**Steps**:
1. Open `packs/built-in/tactics/canonical-source-unification.tactic.yaml`. Append one new
   entry to its `failure_modes` array (matching the existing prose style of the other six
   entries, e.g. `"Wrong canonical surface: ..."`), describing: bypassing a canonical
   prompt/skill/CLI surface on an *unverified size assumption* instead of attempting to
   load/measure it first, and — if genuinely oversized — filing an upstream gap (the
   tactic's existing Rule 3 pattern) rather than improvising a substitute.
2. AND/OR open `packs/built-in/directives/044-canonical-sources-and-unification.directive.yaml`
   and append one new entry to its `procedures` array (matching the existing "Rule N — ..."
   style of the three entries already there, i.e. author it as "Rule 4 — ...") stating the
   same rule in procedure form.
3. **The literal substring `unverified size assumption` MUST appear** in whichever file(s)
   you edit — this is the exact needle T001's red-first test above asserts on.
   Quote/adapt plan.md's own wording for this failure mode rather than re-deriving it from
   scratch — plan.md and spec.md both already use this precise phrase.
4. Do not touch any other field, array entry, or file. This is a content-only addition
   using the existing schema shape.
5. **(Added 2026-09-27, Operator Decision 8.)** Open each of the four agent-profile files that
   cite DIRECTIVE_044 —
   `packs/built-in/agent_profiles/architect-alphonso.agent.yaml`,
   `packs/built-in/agent_profiles/implementer-ivan.agent.yaml`,
   `packs/built-in/agent_profiles/doctrine-daphne.agent.yaml`,
   `packs/built-in/agent_profiles/python-pedro.agent.yaml`
   (confirmed exhaustive via `grep -rl 'code: "044"' packs/built-in/agent_profiles/`) — and, in
   each one's `directive-references` array, append the same failure-mode clause used in T002's
   tactic-file entry to the `code: "044"` entry's `rationale` field (a free-form string field;
   use YAML's `>-` block-scalar folding to keep the existing single-line style consistent, and
   confirm the folded result still parses as one continuous rationale sentence — a broken `>-`
   fold is exactly the defect `tests/doctrine/test_shipped_profiles.py` exists to catch, see T004).
   This is the actual, verified delivery path — see Context's "Render-path seam" note above.

**Files**: `packs/built-in/tactics/canonical-source-unification.tactic.yaml` (edit, +1
`failure_modes` entry; as shipped, the directive file below was NOT touched — a valid "and/or"
choice) and/or
`packs/built-in/directives/044-canonical-sources-and-unification.directive.yaml` (edit, +1
`procedures` entry). At least one of the two files must carry the needle text; spec.md/
plan.md explicitly allow either or both ("and/or"). **Plus (Operator Decision 8):**
`packs/built-in/agent_profiles/{architect-alphonso,implementer-ivan,doctrine-daphne,
python-pedro}.agent.yaml` (each edited, +clause on the existing `code: "044"` `rationale`).

**Validation**: `grep -c "unverified size assumption" packs/built-in/tactics/canonical-source-unification.tactic.yaml packs/built-in/directives/044-canonical-sources-and-unification.directive.yaml` returns a non-zero count for at least one file. `spec-kitty doctrine validate <path>` still reports "1 artifact(s) passed validation" for each edited file (no schema regression). T001's content-assertion test now reports GREEN. **Plus (Operator Decision 8):** `tests/doctrine/test_directive_consistency.py::test_size_assumption_bypass_failure_mode_in_each_profiles_own_source_file` and `::test_size_assumption_bypass_failure_mode_reaches_rendered_profile_context` both report GREEN, parametrized across all four profiles.

## Subtask T003: Regenerate the DRG graph fragments (write mode)

**Purpose**: Keep the machine-generated DRG fragments in sync with the hand-authored source
edit from T002 — this is a **required companion step, not optional**, regardless of default
blast-radius calibration (spec.md FR-002's "Required companion step" note).

**Steps**:
1. After T002's edit(s) are in place, run:
   ```bash
   .venv/bin/spec-kitty doctrine regenerate-graph
   ```
   in **write mode** — do NOT pass `--check`. This is the only sanctioned way to update
   `packs/built-in/tactic.graph.yaml` and `packs/built-in/directive.graph.yaml`; never
   hand-patch either file.
2. Confirm the resulting diff to `packs/built-in/tactic.graph.yaml` and
   `packs/built-in/directive.graph.yaml` reflects only the T002 content addition (no
   unrelated regressions — #5133 already added unrelated nodes/edges for its own
   `acceptance-criteria-non-vacuity` tactic elsewhere in `tactic.graph.yaml`; leave that
   content untouched, your diff should be additive only around the
   `canonical-source-unification` / `DIRECTIVE_044` entries). **As shipped (confirmed against the
   actual diff): running this command produced NO diff to either `.graph.yaml` fragment** —
   `failure_modes`/`procedures` prose and profile `rationale` text are not part of either
   fragment's DRG shape — and instead changed `packs/built-in/pack-manifest.yaml`'s
   per-constituent `content_hash` for each of the five edited source files (the tactic file plus
   the four agent-profile files, added Operator Decision 8) and the file-level `manifest_hash`.
   This is the correct, verified output for this content shape, not a sign the step was skipped
   (plan.md, "Generated artifacts and their regenerating command").
3. Run `.venv/bin/spec-kitty doctrine regenerate-graph --check` and confirm it exits 0
   ("DRG graph is fresh: <repo>/packs/built-in").
4. Commit the regenerated `.graph.yaml` diff in the **same commit** as the T002 source edit
   — never a separate commit (a source-only commit leaves the DRG stale for one commit,
   tripping the freshness gate on any intermediate checkout).

**Files**: `packs/built-in/tactic.graph.yaml` (regenerated — as shipped, byte-identical, no diff),
`packs/built-in/directive.graph.yaml` (regenerated — as shipped, byte-identical, no diff). Never
hand-edit either. **Plus (Operator Decision 8):** `packs/built-in/pack-manifest.yaml`
(regenerated — content-hash diff for all five edited source files).

**Validation**: `spec-kitty doctrine regenerate-graph --check` exits 0. `tests/architectural/test_doctrine_regenerate_graph_roundtrip.py` and `tests/architectural/test_pack_manifest_no_author_edit.py` both pass (see T004 — these are required companion checks, not owned by this WP, run but never edited).

## Subtask T004: Confirm the two required companion tests still pass

**Purpose**: Prove the doctrine edit and DRG regeneration did not regress the two
pre-existing architectural gates this FR is bound to honor (spec.md's own binding
requirement — required regardless of default blast-radius calibration). This WP does not
own or edit either file; it only runs them as a required companion check.

**Steps**:
1. Run `.venv/bin/python -m pytest tests/architectural/test_doctrine_regenerate_graph_roundtrip.py -v` and confirm all tests pass (this file's `test_regenerate_graph_check_is_byte_identical` is the direct mechanical proof that T003's `regenerate-graph` write step was correctly run and committed — an un-regenerated edit would leave this RED).
2. Run `.venv/bin/python -m pytest tests/architectural/test_pack_manifest_no_author_edit.py -v` and confirm all tests pass (proves the doctrine-content edit did not accidentally also touch the authored `packs/built-in/pack.yaml`/`pack.md` manifest pair).
3. **(Added 2026-09-27, Operator Decision 8 — required now that this WP also edits four shipped
   agent-profile files.)** Run `.venv/bin/python -m pytest tests/doctrine/test_shipped_profiles.py -v`,
   `.venv/bin/python -m pytest tests/doctrine/agent_profiles/test_supply_chain_profile_bindings.py -v`,
   and `.venv/bin/python -m pytest tests/doctrine/test_package_smoke.py -v`, and confirm all pass.
   These are pre-existing profile-pinning tests, not new companions this WP adds — `test_shipped_profiles.py`
   schema-validates every shipped profile (catches a broken YAML `>-` block-scalar fold from T002
   step 5); `test_supply_chain_profile_bindings.py` resolves three of the four edited profiles and
   asserts on their unrelated DIRECTIVE_051 citation (a regression fence proving the DIRECTIVE_044
   edit did not corrupt other citations); `test_package_smoke.py` smoke-imports
   `AgentProfileRepository` and resolves `implementer-ivan` (catches an import-time break). Do NOT
   edit any of these three files — read-only companions.
4. Record the exact commands and pass counts in the PR's Tests-run section (per this repo's own CLAUDE.md test-policy convention), plus the targeted `tests/doctrine` and `tests/architectural` runs from T001/T004 together.
5. Do NOT edit any of these five files — they are read-only companions for this WP, not owned files.

**Files**: none (read-only verification of pre-existing files).

**Validation**: `test_doctrine_regenerate_graph_roundtrip.py` and `test_pack_manifest_no_author_edit.py`
report 100% pass, matching plan.md's recorded baseline (2 passed; 4 passed) with zero
regressions. **Plus (Operator Decision 8):** `test_shipped_profiles.py`, `test_supply_chain_profile_bindings.py`,
and `test_package_smoke.py` all report 100% pass, confirming the four profile-file edits did not
regress schema validation, lineage bindings, or importability.

## Definition of Done

**Revision note (2026-09-27, Operator Decision 8).** The checklist below is updated to name what
actually shipped; items unchanged from the pre-Decision-8 design are kept as-is, new/widened
items are marked `(Decision 8)`.

### Requirement disposition (per `review/prompt.md` checklist item 4/4b)

This WP's `requirement_refs` (`wps.yaml`) carries five FRs, but only FR-002 is built here. The
other four are riding along per the `finalize-tasks --validate-only` bold-bullet-lead parser
heuristic described in the Context section above (tracked upstream as issue #5065,
"Requirement lifecycle status"). Per-FR disposition, so a reviewer applying this repo's own
checklist has a recorded control instead of a silent waive:

| FR | No-op passable? | Control |
|----|------------------|---------|
| FR-001 | yes | Superseded per Operator Decision 7 (spec.md) — no diff at all, since upstream PR #5133 already resynced the override to canonical's exact bytes. |
| FR-003 | yes | Delivered pre-WP by `research.md` (earlier mission phase) — this WP builds nothing new for it. |
| FR-004 | yes | Enforced by this DoD's git-diff zero-bytes-changed check on `analyze/prompt.md`, below. |
| FR-005 | yes | Not implemented by design (Operator Decision 6, spec.md) — explicitly out of scope. |

- `tests/doctrine/test_directive_consistency.py` carries three test functions (not one):
  `test_size_assumption_bypass_failure_mode_documented` (title-anchored, case-insensitive),
  `test_size_assumption_bypass_failure_mode_in_each_profiles_own_source_file` (parametrized over
  all four DIRECTIVE_044-citing profiles), and
  `test_size_assumption_bypass_failure_mode_reaches_rendered_profile_context` (parametrized over
  all four profiles) — all confirmed RED-before/GREEN-after where applicable (see T001's revision
  note for which cases were genuinely red), with the file's other 8 pre-existing tests unaffected
  (T001).
- The literal substring `unverified size assumption` appears in
  `packs/built-in/tactics/canonical-source-unification.tactic.yaml`'s `failure_modes` array (as
  shipped, the directive file's `procedures` array was not touched — a valid "and/or" choice)
  (T002).
- **`(Decision 8)`** The identical failure-mode clause appears in the `code: "044"`
  `directive-references[].rationale` field of all four shipped profiles that cite DIRECTIVE_044 —
  `architect-alphonso`, `implementer-ivan`, `doctrine-daphne`, `python-pedro` — verified by the
  rendered-reachability test above exercising the real `_render_profile_sections` production
  render path, and independently by the own-source-file test above (which catches a revert of
  `python-pedro`'s own hunk that the rendered-reachability test cannot, due to DRG lineage
  inheritance from `implementer-ivan` — see the Revision Note / Context "Render-path seam" above)
  (T002 step 5).
- `packs/built-in/tactic.graph.yaml` and `packs/built-in/directive.graph.yaml` were regenerated
  via `spec-kitty doctrine regenerate-graph` in write mode (never hand-edited); as shipped this
  produced no diff to either fragment (this content shape is outside the DRG's shape), and instead
  regenerated `packs/built-in/pack-manifest.yaml`'s content hashes for all five edited source
  files; `spec-kitty doctrine regenerate-graph --check` exits 0 (T003).
- `tests/architectural/test_doctrine_regenerate_graph_roundtrip.py` and
  `tests/architectural/test_pack_manifest_no_author_edit.py` both pass, unmodified (T004).
- **`(Decision 8)`** `tests/doctrine/test_shipped_profiles.py`,
  `tests/doctrine/agent_profiles/test_supply_chain_profile_bindings.py`, and
  `tests/doctrine/test_package_smoke.py` all pass, unmodified — confirming the four profile-file
  edits regressed neither schema validation, lineage bindings, nor importability (T004).
- Zero bytes changed in `analyze/prompt.md`, canonical or override, in either content or
  size (FR-004 — verify with `git status`/`git diff` before committing: neither
  `packs/built-in/missions/mission-steps/software-dev/analyze/prompt.md` nor
  `.kittify/overrides/missions/software-dev/command-templates/analyze.md` appears in the
  diff at all).
- No new CLI surface introduced (NFR-002) — this WP is a content-only doctrine addition
  reusing the existing `regenerate-graph`/`doctrine validate` CLI surfaces.
- Per-subtask completion is recorded via
  `spec-kitty agent tasks mark-status <Txxx> --status done` (event-sourced), not a ticked
  checkbox.

Implement with: `spec-kitty agent action implement WP01 --agent claude`

## Risks

- **Schema drift risk (low)**: both target schemas accept unconstrained string arrays
  today; a future schema tightening (e.g. an enum or length cap on `failure_modes`) is out
  of this WP's scope and not anticipated — no action needed unless a schema change lands
  concurrently (verified zero open-PR overlap in plan.md's PR-overlap section).
- **DRG regeneration touching unrelated content (medium, mitigated)**: upstream PR #5133
  already added unrelated nodes/edges to `tactic.graph.yaml` for its own
  `acceptance-criteria-non-vacuity` tactic. Running `regenerate-graph` in write mode after
  T002 must produce an additive diff around the `canonical-source-unification`/
  `DIRECTIVE_044` entries only — inspect the diff before committing to confirm no
  unintended regeneration drift elsewhere in the file (T003, step 2).
- **Test-home mis-selection (mitigated)**: plan.md already ruled out the two other
  candidate test files (`test_schema_compatibility.py`, `test_tactic_compliance.py`) as
  structurally vacuous for this checkout's layout — do not second-guess this and add the
  test there instead; `tests/doctrine/test_directive_consistency.py` is confirmed correct.
- **FR-004 regression risk (low, high consequence)**: any accidental edit to
  `analyze/prompt.md` (canonical or override) would violate a hard mission constraint and
  trip #5133's `test_kittify_override_parity.py` gate. This WP's `owned_files` list does
  not include either path — stay inside it.

## Reviewer Guidance

**Revision note (2026-09-27, Operator Decision 8).** The bullets below are updated to reflect
the widened, actually-shipped scope; new bullets are marked `(Decision 8)`.

- Confirm the literal substring `unverified size assumption` is present verbatim in at
  least one of the two target files (as shipped, the tactic file only), and that the added prose
  reads coherently against the existing entries' style (not a bare keyword stuffed in).
- Confirm `packs/built-in/tactic.graph.yaml`/`directive.graph.yaml` were regenerated (not
  hand-edited) — as shipped, the correct output is NO diff to either fragment for this content
  shape (confirm via `spec-kitty doctrine regenerate-graph --check` exiting 0), with the change
  instead landing in `packs/built-in/pack-manifest.yaml`'s content hashes. Do not treat an
  unchanged `.graph.yaml` as evidence the regeneration step was skipped — check the manifest diff
  instead.
- Confirm the tests in `tests/doctrine/test_directive_consistency.py` are real,
  non-vacuous assertions (not a `[NOTSET]`-style vacuous parametrization). Then confirm C-011
  directly, not merely by documented claim: run
  `git log --oneline <planning_base_branch>..HEAD` (or equivalent) and verify there is a
  distinct, standalone commit that adds only the T001 test file(s), landing *before* the
  commit(s) that touch the doctrine source/profile/DRG files (T002/T003) — a PR description or
  commit message that merely *asserts* RED-before/GREEN-after evidence, with no such standalone
  commit actually on the branch, does not satisfy C-011.
- **`(Decision 8)`** Confirm all three test functions ship, not one:
  `test_size_assumption_bypass_failure_mode_documented`,
  `test_size_assumption_bypass_failure_mode_in_each_profiles_own_source_file` (parametrized over
  the four profiles), and `test_size_assumption_bypass_failure_mode_reaches_rendered_profile_context`
  (parametrized over the four profiles). Confirm the second one is not a duplicate of the third:
  it must read each profile's own source YAML directly (never through `resolve_profile`) —
  because `python-pedro` `specializes_from` `implementer-ivan` in the DRG and
  `AgentProfileRepository.resolve_profile`'s lineage union-merge resolves a same-`code`
  `directive-references` collision to the parent's entry, the rendered-reachability test's
  `python-pedro` case would stay green via inheritance even if `python-pedro`'s own file were
  reverted — only the own-source test catches that revert. If in doubt, reproduce the check
  cycle-3's review did: in an isolated scratch worktree, revert only `python-pedro.agent.yaml`'s
  own DIRECTIVE_044 hunk and confirm the own-source test goes RED while the
  rendered-reachability test's `python-pedro` case stays GREEN.
- **`(Decision 8)`** Confirm the identical failure-mode clause is present in the `code: "044"`
  `directive-references[].rationale` of all four profiles —
  `packs/built-in/agent_profiles/{architect-alphonso,implementer-ivan,doctrine-daphne,
  python-pedro}.agent.yaml` — not `implementer-ivan` alone, and that each is valid YAML (a broken
  `>-` block-scalar fold would still parse as a shorter, truncated rationale string rather than
  erroring, so check the rendered/parsed value, not just that the file loads).
- Confirm `git diff` touches zero bytes of `packs/built-in/missions/mission-steps/software-dev/analyze/prompt.md` and zero bytes of `.kittify/overrides/missions/software-dev/command-templates/analyze.md` (FR-004).
- Confirm both required companion tests (`test_doctrine_regenerate_graph_roundtrip.py`,
  `test_pack_manifest_no_author_edit.py`) are reported passing in the PR, and that neither
  file itself was edited by this WP.
- **`(Decision 8)`** Confirm the three profile-pinning companion tests
  (`test_shipped_profiles.py`, `test_supply_chain_profile_bindings.py`, `test_package_smoke.py`)
  are reported passing, and that none of the three was edited by this WP — they are pre-existing
  regression fences, re-exercised by the profile-file edits, not new companions this WP adds.
- Confirm the PR is scoped as this repo's default one-PR-per-mission shape (not split across
  multiple WPs/PRs) — this mission has exactly one WP by design.
- Confirm the Definition of Done's "Requirement disposition" table gives a per-FR
  no-op-passable/control annotation for FR-001, FR-003, FR-004, and FR-005 (this repo's
  `review/prompt.md` checklist item 4/4b) rather than leaving those four `requirement_refs`
  entries silently unaddressed.
- **`(Decision 8)`** Confirm the PR body or spec.md cites Operator Decision 8 as authorization
  for touching the four shared, cross-mission `packs/built-in/agent_profiles/*.agent.yaml` files
  and `packs/built-in/pack-manifest.yaml` — these are not in WP01's `owned_files` frontmatter, and
  spec.md's "Authorized scope beyond WP01's `owned_files`/`lanes.json` `write_scope`" note (below
  C-002) is the binding record of why that divergence is intentional, not stale.
