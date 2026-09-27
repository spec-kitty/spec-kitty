# Tracer: design decisions — analyze-prompt-context-load-01M3F4BV

## Plan phase (2026-09-26)

- **Deletion over copy for FR-001** (already decided by Operator Decision 4, not
  re-litigated here) — confirmed at the code level during plan authoring: the resolver's
  fall-through to canonical (`MissionTemplateRepository._command_template_path`, legacy shape
  first, then the canonical `mission-steps/<mission>/<name>/prompt.md` shape) requires no
  code change; deleting the override file is the entire mechanism. This is a stronger
  guarantee than a byte-for-byte copy would have been (no second file left to re-diverge).

- **Home for the new red-first resolver test: `tests/doctrine/test_resolver.py`, not
  `tests/doctrine/missions/test_mission_step_resolver.py`.** Both files were read in full.
  `test_resolver.py` directly imports and exercises `charter.offering.resolver.resolve_command`
  — the exact function SC-001/NFR-001 name — and already uses the `pytestmark = [pytest.mark.fast,
  pytest.mark.doctrine]` marker pair this new test should keep.
  `test_mission_step_resolver.py` tests a different repository class
  (`MissionStepRepository`/`StepKey`) for mission-step compound-key shadowing, a related but
  distinct concern. Neither file currently has a live-checkout (non-`tmp_path`) probe; this
  is a genuine gap this mission's plan closes by adding one, following the `_REPO_ROOT =
  Path(__file__).resolve().parents[N]` idiom already established elsewhere in this test tree.

- **Doctrine addition targets `packs/built-in/`, not `packs/internal/`** (C-001) — the
  failure mode (an orchestrating agent bypassing a canonical surface on an unverified size
  assumption) is a general agent-behavior rule any consumer's agent could exhibit, not
  Spec-Kitty-core-team-only tracker/PR-landing guidance. Same tier as DIRECTIVE_044's
  existing Rules 1 and 3.

- **No schema change for FR-002.** Both `tactic.schema.yaml` and `directive.schema.yaml`
  already accept unconstrained string arrays for `failure_modes` / `procedures`; a new entry
  is a content-only, same-shape addition. Confirmed by reading both schema files and by a
  dry-run `spec-kitty doctrine validate` pass against the current (unedited) files.

- **PR #5133 modify/delete risk resolved as "deletion wins," not "coordinate merge order."**
  Rather than proposing any sequencing gate (e.g., "land before/after #5133"), the plan
  records a fixed resolution instruction for whichever PR merges second, since #5133's own
  new parity test degrades gracefully (no failure) when `analyze.md` is simply absent — there
  is no need to block on merge order, only to resolve the conflict correctly when it occurs.

- **`spec-kitty agent tracer-append` not used for this pass** — see the appended entry in
  `tracer-tooling-friction.md` for the full reasoning (path-shape and COORD-partition
  mismatch against this mission's `single_branch` topology).

## Plan-revision pass (2026-09-26, Operator Decision 7)

- **FR-001's plan content is stripped, not adapted or left as inert prose.** Once #5133
  delivered the same byte-content outcome FR-001's deletion would have, and Decision 7
  formally dropped FR-001 as a build item, the plan's FR-001 sections (Seam, red-first test,
  landing-sequencing, campsite-clean framing) no longer described anything this mission
  builds. Decision: remove them outright rather than mark them "superseded" in place and
  leave the mechanism description standing — a future reader of plan.md should not have to
  wade through a deleted mechanism's design to find the one FR that still ships. Historical
  provenance for FR-001's original mechanism stays in spec.md (which already carries the
  full supersession trail verbatim) and in the prior round's git history; plan.md does not
  need to duplicate it.

- **FR-002's red-first test home changed from `tests/doctrine/test_resolver.py` (a real but
  now-irrelevant file, since it tests the resolver FR-001 no longer touches) to
  `tests/doctrine/test_directive_consistency.py`.** This is a genuinely new decision this
  pass made, driven by a concrete finding: the prior round's own suggested alternative for
  FR-002 (`test_schema_compatibility.py`, with `test_tactic_compliance.py` floated as a
  sibling option) both resolve a stale, pre-pack-relocation directory
  (`src/charter/offering/{directives,tactics}/built-in`) that does not exist on this
  checkout, so their content-parametrized tests collect zero cases (`[NOTSET]`) and can never
  fail against real content. This was discovered by actually running `pytest --collect-only`
  against both files this pass, not by inspecting the constant names and assuming they were
  live. `test_directive_consistency.py` was chosen because it is the one file in the test
  tree whose path constants (`_PACKS_BUILT_IN = REPO_ROOT / "packs" / "built-in"`) correctly
  target the post-relocation layout, it already runs real, passing tests against the actual
  shipped directive/tactic files, and no other file in the repository already asserts against
  these two specific files' `failure_modes`/`procedures` content by name (confirmed by
  grepping the whole `tests/` tree for `DIRECTIVE_044`/`canonical-source-unification` and
  reading every hit — all are DRG-reachability or comment references, none are content-string
  assertions).

- **Baseline-worktree commit: `34b53d78e` (the current `origin/main` tip merged into this
  branch), not the prior round's `da6d0af97eb1291cb08d4d0a6772cdfc43df4496`.** The old
  merge-base predates #5133 and no longer reflects what "clean, unmodified upstream" means
  for this branch. Re-baselining at the actual current merge point is the only way the
  baseline answers "what's pre-existing red on the code this branch actually merged," per
  the mission brief's explicit instruction.

- **Baseline-worktree file set narrowed from four files to three**, dropping
  `tests/doctrine/test_resolver.py` and `tests/doctrine/missions/test_mission_step_resolver.py`
  (both were baselined because of FR-001's resolver-tier claim, which no longer exists) and
  adding `tests/doctrine/test_directive_consistency.py` (the new FR-002 test's home) in their
  place, alongside the two required companion tests (unchanged).

## Tasks phase (2026-09-26)

- **Single WP, `cross_cutting: true`, no `plan_concern_refs`.** plan.md declares no `IC-##`
  implementation-concern IDs anywhere (grep-confirmed, zero hits) — the plan is small enough
  that it never introduces that numbering. WP01 is therefore marked `cross_cutting: true`
  per `tasks-outline/prompt.md`'s own rule for a WP with no specific concern ref, rather than
  inventing an `IC-01` that plan.md never declared.
- **Agent profile: `implementer-ivan`, not `paula-patterns` or `debugger-debbie`.** The
  mission brief suggested the latter two as candidates, but their `action_domains`
  (`architecture-scout` / `boundary` / `investigate` / `bisect` / `root-cause`) don't match
  this WP's actual shape — a content edit plus test authoring, not an architecture-boundary
  decision or a bug investigation. `implementer-ivan`'s `action_domains` include `implement`,
  `test`, `unit test`, and `fix`, and its role is `implementer` — the closest canonical match
  for "edit a doctrine file, regenerate its graph, add a passing test."
- **Requirement mapping: `FR-005` added to WP01's `requirement_refs`, honestly annotated as
  out-of-scope.** `finalize-tasks --validate-only` failed once with
  `unmapped_functional_requirements: ["FR-005"]`. Root cause (read from
  `src/specify_cli/requirement_mapping.py::_declared_ids`): the parser treats any line
  matching `^\s*[-*]\s*\*\*((?:FR|NFR|C)-\d+)` as a *declared* requirement needing WP
  coverage — spec.md's own "Remaining scope after Operator Decision 7" section has exactly
  such a bullet (`- **FR-005/006/007 (governance-context budget fix) stay out of scope...`),
  even though FR-005 has no row in spec.md's actual Functional Requirements table and is
  explicitly dropped from this mission's scope (Operator Decision 6). Per the mission brief's
  explicit instruction not to fabricate a mapping to route around a real validator error, the
  fix chosen mirrors the brief's own sanctioned pattern for FR-001/003/004 (list as
  "addressed by reference," not as a build claim): `FR-005` was added to WP01's
  `requirement_refs` with an explicit note in the WP prompt's Context section stating this WP
  does NOT implement FR-005 and explaining exactly why it's listed (parser limitation, not a
  scope claim). `FR-006`/`FR-007` never independently triggered the same check (they never
  appear as the first id on a `- **FR-NNN` line anywhere in spec.md), so they were not added.

## WP01: tactic file only, not the directive file (2026-09-27)

T002 allowed "and/or" across the tactic's `failure_modes` array and the directive's
`procedures` array. Chose the tactic file only: it already names five closely-related
failure modes (parity-instead-of-unification, fallback-preservation, gate-omission, wrong
canonical surface, assumed-superset canonical, seam-bypass-via-stale-comment) in the exact
same prose register the new entry needed, whereas the directive's `procedures` array holds
only three high-level numbered rules. Adding a sixth/seventh failure mode to the tactic
matches the smallest-viable-diff resolution order (Charter § "Reconciling change-scope
tensions"): one file, one new array entry, no new "Rule 4" needed on the directive side to
satisfy FR-002's falsifiable needle-text requirement. T001's red-first test accepts either
location (`found_in_tactic or found_in_directive`), so this is a legitimate, test-verified
choice, not an unstated narrowing of the requirement.

## WP01 rework (2026-09-27): making the failure-mode text reachable

The pre-merge adversarial squad confirmed `pr-contract-001` (severity 4): the tactic's
`failure_modes` array (and DIRECTIVE_044's `procedures`, had the text landed there instead)
is never read by ANY automatic doctrine renderer. Traced every renderer that turns a doctrine
artifact into agent-visible prompt text before choosing a remedy:

- `_format_inline_tactic_body` (`src/charter/activation/context_renderers/artifact_bodies.py:213-227`)
  renders only Name/Purpose/Steps for a tactic — no branch reads `failure_modes` at all.
  `format_inline_named_body` (`profile_sections.py:155-190`, the profile-citation body
  formatter shared by tactics/procedures) has the identical Name/Purpose/Steps shape.
  Extending a step's `description` (the one tactic field the inline renderer DOES show) was
  considered and rejected: `canonical-source-unification`'s rendered body already measures
  ~4,350 chars against the 2,400-char `_PROFILE_INLINE_BODY_LIMIT_CHARS` ceiling
  (`token_budget.py:79`) — any addition keeps it over budget, so it still falls back to the
  fetch-stanza pointer in every automatic render path regardless of which field carries it.
  DIRECTIVE_044's rendered body independently measures ~3,460 chars against the same
  2,400-char ceiling — also already over, so landing the text in `procedures` (the field
  `_format_inline_directive_body` DOES render) does not help either, for the same budget
  reason. Both measurements were taken directly against the real renderer functions on the
  worktree's post-T002 files, not estimated.
- The fetch-stanza's own `when_doing_clause` text (`fetch_stanza.py`) is a Python literal
  per selector kind (e.g. `_ACTION_DOCTRINE_LINK_WHEN = "are about to apply a code change"`
  in `selection_block.py:94`) — not a doctrine YAML field and not a generated DRG edge, so it
  cannot carry new content without a renderer code change (out of scope per the dispatch's
  hard limits).
- **The surface that actually works, found by continuing the trace into the profile-citation
  renderers:** `_render_directive_entry` (`profile_sections.py:527-546`) builds the citation's
  header line — `f"  - {code}: {title}"`, then `f"{header_line} — {rationale}"` when the
  profile's own `directive-references[].rationale` field is non-empty — and appends it to
  `lines` BEFORE the body/fetch-stanza budget check at lines 560-569 ever runs. The sibling
  tactic-citation path (`_render_selector_entry`, used by `_render_profile_tactics` via
  `render_profile_selector_refs`) has the identical unconditional-header-line shape
  (`selection_block... profile_sections.py:253-256`). This header line is NOT subject to the
  2,400-char per-artifact body budget at all — it renders regardless of whether the
  artifact's own body is small enough to inline or falls back to the fetch stanza. Confirmed
  empirically, not just by reading the code: rendering `implementer-ivan`'s profile through
  the REAL `_render_profile_sections(profile, service)` (real shipped catalog, not a
  synthetic fixture) showed the DIRECTIVE_044 citation line rendering with its rationale
  intact, immediately followed by the fetch-stanza (confirming the body itself still falls
  back, exactly as the squad's measurement predicted) — i.e. the header+rationale line
  survives independently of the body-budget fallback.
- **Why `implementer-ivan` and not another profile:** four shipped profiles cite DIRECTIVE_044
  via `directive-references` (`architect-alphonso`, `implementer-ivan`, `doctrine-daphne`,
  `python-pedro`, confirmed via `grep -rl 'code: "044"' packs/built-in/agent_profiles/`); no
  shipped profile cites the tactic via `tactic-references` at all (confirmed:
  `grep -rl canonical-source-unification packs/built-in/agent_profiles/` returns nothing), so
  the tactic-citation path was not an available option for this failure mode without adding a
  brand-new citation somewhere (out of scope for a smallest-viable-diff fix). Of the four
  directive-citing profiles, `implementer-ivan` is the one this dispatch runs under and the
  one whose `avoidance-boundary`/`success-definition` most directly covers "is this canonical
  surface safe to bypass" judgment calls during implementation — editing its own existing
  citation's `rationale` (an in-place content edit, no new reference added) is the smallest
  change that makes the text reachable through a real, already-active profile channel.
  Whether the other three profiles' citations should carry the same addition is a fold-in
  candidate for a future pass, not decided here (see "No follow-up issues — fold in" —
  deliberately narrow-scoped to the one profile this fix's own test proves reachable, rather
  than silently widening to all four without an equivalent red/green proof for each).
- **Rejected alternative: editing the renderer** (e.g. adding a `failure_modes` branch to
  `_format_inline_tactic_body`, or lowering `_PROFILE_INLINE_BODY_LIMIT_CHARS`) — excluded by
  the dispatch's explicit hard limit ("no renderer code change unless it is genuinely required
  AND small AND you stop to report it first"); a genuine reachable surface existed without
  touching renderer code, so no renderer change was needed or attempted.
- Confirms via `git -C <primary> status --porcelain -- packs/` after every doctrine command
  that this fix never wrote to the primary checkout's `packs/` — only the lane worktree's own
  copy (and, correctly, `packs/built-in/pack-manifest.yaml`'s regenerated `content_hash` for
  the edited profile file; the DRG graph fragments themselves are byte-unchanged, since a
  profile's citation `rationale` prose is not DRG node/edge content).

## WP01 round-2 rework (2026-09-27): Operator Decision 8 — widen to all four DIRECTIVE_044-citing profiles

**Operator Decision 8 (verbatim, recorded in spec.md's Clarifications/Decisions as item 8):**
"(8) All 4 citing profiles: Decision 8 authorizes editing all four profiles that cite
DIRECTIVE_044 (architect-alphonso, implementer-ivan, doctrine-daphne, python-pedro). Wider
reach, still no orchestrator reach; bigger shared-file blast radius." This retroactively
authorizes the round-1 `implementer-ivan.agent.yaml` edit (previously self-authorized by that
same rework's own spec.md text, per WP01-C2-002) and authorizes extending the identical clause
to the other three profiles.

- **Parametrize the existing test over all four profiles, not four separate tests.** The
  cycle-1/round-1 test already exercises the real `_render_profile_sections` render path
  generically over a `profile_id` argument (only the fixed string `"implementer-ivan"` needed
  generalizing); `pytest.mark.parametrize` over a module-level tuple keeps one assertion body
  and one failure-message template instead of four near-duplicate test functions, and produces
  four independently-reportable pass/fail results (`test_...[architect-alphonso]`, etc.) —
  exactly the per-profile red/green evidence the rework needed to prove.
- **Commit the parametrized test standalone before touching any of the three new profile
  files**, per this WP's own red-first discipline (T001's original pattern) and the dispatch's
  explicit instruction. This surfaced a real, non-obvious finding (see
  tracer-tooling-friction.md's "`python-pedro` inherits DIRECTIVE_044 via `specializes_from`"
  entry): the genuine red-first run showed only 2 of 3 unedited profiles failing, not 3, because
  `python-pedro` inherits implementer-ivan's already-fixed DIRECTIVE_044 citation via a
  `specializes_from` DRG edge. This is reported honestly rather than silently reconciled to the
  "3 profiles fail" shape the dispatch's own framing anticipated.
- **Edit `python-pedro.agent.yaml`'s own rationale anyway**, despite its rendered-reachability
  test case already being green via inheritance before the edit. Rationale: (1) Decision 8 and
  the corrected SC-002 both name `python-pedro` as one of "the four" whose own file should carry
  the clause, not merely whichever profile happens to resolve it at render time; (2) the
  `specializes_from` union-merge is an implementation detail of today's resolver, not a spec
  guarantee — a future change to lineage-merge precedence (e.g., child-overrides-parent) could
  silently regress `python-pedro`'s reach if its own file were left stale; (3) a doctrine reader
  opening `python-pedro.agent.yaml` directly (not through the resolved/merged view) should see
  the same governance text a reader of `implementer-ivan.agent.yaml` sees, per DIRECTIVE_044's
  own single-canonical-authority spirit — leaving the raw source silently reliant on inheritance
  would itself be a small split-brain surface.
- **Spec sync ordering: fix spec.md's internal contradiction (WP01-C2-001/pr-FRESH-001) before
  re-running `/spec-kitty.analyze`**, not after. `implement WP01`'s reopen was gated on a fresh
  analyze report; analyzing the still-self-contradictory spec first would have produced a
  `blocked` verdict this same rework would have had to re-run anyway once the sync landed, so
  the sync was done first and `/spec-kitty.analyze` was run once, against the corrected spec
  (verdict `ready`, zero findings).
- **`lanes.json`/WP01's `owned_files` frontmatter left unedited, by design.** The dispatch
  forbids hand-editing spec-kitty state, and no CLI surface exists to re-derive `write_scope`/
  `owned_files` for an already-materialized WP outside the `finalize-tasks` authoring flow.
  `safe-commit` on the four-profile-plus-manifest commit correctly emitted (non-blocking)
  `ACTIVE_WP_SCOPE_VIOLATION` warnings for all four touched files; spec.md's C-002 section now
  carries an explicit "Authorized scope beyond WP01's owned_files/lanes.json write_scope" note
  naming Decision 8 and this spec revision as the authorization of record, so the warning's
  cause is documented rather than silently overridden.
