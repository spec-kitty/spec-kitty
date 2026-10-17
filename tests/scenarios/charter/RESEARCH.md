# Charter-offering scenario suite — grounding note

<!-- Not part of the behaviour description. Grounding record for the
charter-offering BDD suite, authored per the `charter-offering-scenario-extraction`
procedure (promise-first; the nightly e2e and the fast charter tests are read as
EVIDENCE, never transcribed). Updated: 2026-10-17. -->

This note records the promise extraction, the evidence behind each promise, and
the litmus decisions that shaped the three offering outcome features under
`tests/scenarios/charter/`. It is the maintainer's trail for anyone extending the
suite; the frozen promise→contract map is `PROMISES.md`.

## Why this suite exists (and what it is not)

Ahead of the `spec-kitty-charter` extraction (epic #6099), the offering layer
needs a **consumer contract net** that survives the repo split. Issue #6286's own
Definition of Done is a *Python public-surface import-conformance* suite (a
simulated external consumer importing only `charter.offering.api`, a surface
snapshot, DTO-shape `xfail`s, a negative "up the chain" import). This BDD suite is
the **complementary consumer-outcome layer** on top of that mechanism net: it
states "what should the system do for me" in the consumer's language, independent
of which command delivers it. It does **not** replace the Python import-conformance
suite #6286 enumerates, and it does not replace the `tests/e2e` / `tests/charter*`
mechanism tier. Hence this increment is `Refs #6286`, not `Closes #6286`.

## Scope (exactly three outcome features; nothing more)

| Area | Feature (consumer outcome) | Folder |
|------|----------------------------|--------|
| GOVERNANCE | The governance in force is what I chose | `governance-in-force/` |
| REFUSAL | The system refuses unsound governance with a clear reason | `refuses-unsound-governance/` |
| SHARING | I can share governance across a team or project safely | `share-governance-safely/` |

**Excluded, deliberately not authored** (procedure §1 + anti-patterns):
activation behaviour (activate / deactivate / cascade — the activation layer
extracts later); command-affordance / CRUD echoes (what `list` / `path` /
`context` print byte-for-byte — the existing `charter/charter.feature` already
owns that affordance tier); the dropped over-broad "composition resolves the way I
expect"; and anything that fails the litmus (goal + consequence, independent of
command).

## Promise extraction, with evidence

Each promise is a plain consumer sentence, tied to an offering FR/ADR and to the
existing test that proves the mechanism already holds. Evidence is read, never
transcribed.

### GOVERNANCE — the governance in force is what I chose

- **PR-CHARTER-GOVERNANCE-001** — An author gets the artifacts their charter puts
  in force, not every artifact that merely exists.
  Evidence: `ArtifactKind.effective_when_absent` and the three-state resolution
  (`src/charter/offering/artifact_kinds.py` FR-005); the default-in-force rule
  (an absent activation key is the unrestricted "all" state for every kind
  except `skill`).
- **PR-CHARTER-GOVERNANCE-002** — Registering a shared pack does not silently add
  its commands to every tool; a skill is in force only when the charter requires
  or selects it.
  Evidence: `effective_when_absent == "required"` for `skill` (ADR
  `2026-09-27-1`); "default in force" = org `required_skills` + built-in defaults,
  not every available skill.
- **PR-CHARTER-GOVERNANCE-003** — An org pack's required selections are honoured
  on top of what the project chose (selection overlay).
  Evidence: `ArtifactKind.selection_overlayable` and the org `required_<plural>` →
  `selected_<plural>` union (`artifact_kinds.py`,
  `src/charter/activation/org_charter.py`).

### REFUSAL — the system refuses unsound governance with a clear reason

- **PR-CHARTER-REFUSAL-001** — Governance that would silently drop a profile's
  steps, or strip a step's inputs/outputs, is refused rather than quietly
  accepted.
  Evidence: `enhances` = field-merge preserving the action sequence + step I/O;
  `overrides` = full replacement; a silent step-drop / I/O-strip is rejected
  (AGENTS.md "Profile Load Diagnostics"; `agent_profiles` validation).
- **PR-CHARTER-REFUSAL-002** — A mistyped reference between governance artifacts
  is named, not dropped without trace.
  Evidence: `unresolved_edge_endpoint` (FR-010) and `UnknownRelationError`
  (FR-003) — `src/charter/offering/drg/merge.py` closes ADR `2026-07-26-3`'s
  silent-drop path; an `operating-procedures` entry resolving to nothing / the
  wrong kind is `no_node` / `wrong_kind`, not silently accepted
  (`agent_profiles/operating_procedures.py`).
- **PR-CHARTER-REFUSAL-003** — A broken charter fails closed instead of running
  with partial, unsound governance.
  Evidence: `ActiveCharterConfigError` fail-closed; `plan_activation()` never
  mutates config on validation failure (ADR `2026-05-16-1`, NFR-003).

### SHARING — I can share governance across a team or project safely

- **PR-CHARTER-SHARING-001** — A pack that carries an invalid profile is not
  reported healthy, even when its graph counts look right.
  Evidence: `AgentProfileRepository.skipped_profiles` feeds
  `doctor charter-packs --json`; FR-010 — a pack with invalid profiles is NOT
  reported healthy even if DRG counts are valid
  (`src/charter/offering/agent_profiles/repository.py`,
  `src/specify_cli/cli/commands/_charter_pack_health.py`).
- **PR-CHARTER-SHARING-002** — When a project and an org pack both speak to the
  same governance, the project's choice is the one in force.
  Evidence: layered repository resolution (`has_layered_repository`, 11 kinds);
  project overrides org/built-in (`drg/merge.py` override machinery, ADR
  `2026-05-16-1`).
- **PR-CHARTER-SHARING-003** — A shared skill must declare a safe namespace; a
  reserved or malformed one is refused with a reason.
  Evidence: reserved prefixes `spk-` / `spec-kitty-` / `spec-kitty.` and the
  namespace grammar (`src/charter/activation/org_charter.py`,
  `skill_preparation.require_valid_skill_namespace`; ADR `2026-09-27-1`). NOTE:
  this validation sits in `charter.activation`, which extracts later, so this
  promise is captured but its step stays `@wip` until the activation-layer
  fixture exists.

## Litmus — demoted to the Python/e2e mechanism tier (not authored)

- "`charter list --kind agent_profile` prints `researcher-ryan`" — pure affordance
  echo; owned by the unit/e2e tier and the existing `charter.feature`.
- "`charter synthesize` writes `.kittify/charter-packs/` and a
  `synthesis-manifest.yaml` with 7 artifacts" — mechanism / file-layout; owned by
  `tests/e2e/test_charter_epic_golden_path.py` and `charter.feature`.
- "the DRG fragment has an edge `a -> b` / the manifest lists N nodes" — internal
  state; mechanism tier.
- "composition resolves the way I expect" — too broad for a step to witness;
  dropped per the procedure.

## Step-library plan (and the real cost)

The binding cost is the Java step library + its black-box governance fixture.
Existing steps (`ArrangeSteps`/`AssumeSteps`/`ActSteps`/`AssertSteps`) are
command-centric (`When I run "<cmd>"`, `Then the output mentions "<text>"`); the
styleguide wants **outcome-verb** steps (`Then the governance in force
includes <...>`, `Then the system refuses with a reason naming <...>`). Those need
new step definitions plus a governance-fixture builder that arranges a charter in
a known state **only by running the CLI** (constraint C-002, as `MissionFixture`
already does for missions).

This directly depends on the black-box fixture-builder work tracked in **#6137**
(Mission/governance fixtures, still in triage, owned by the operator). Per the
procedure, standing up broad new step infrastructure vs authoring `@wip` and
deferring is an **operator decision** — surfaced before any step infra is built.
Recommended first bound-and-green area: **REFUSAL** (most behavioural, already
covered by the fast charter tests, lowest fixture cost — a refusal is observed
from the command's failure + reason, needing no rich success-state fixture).

## Traceability + honesty

`PROMISES.md` maps every `@promise:` id to its FR/ADR. Bound scenarios run nightly
cross-OS via Cucumber-JVM; unbound ones carry `@wip` + `@wip-owner` + `@wip-since`
and do not gate the nightly. No promise was invented without evidence; no scenario
tagged `@defect` or phrased as a reproduction.
