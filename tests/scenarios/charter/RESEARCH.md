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
  _Authored as GOVERNANCE-001 in its skill-specific, witnessable form below. The
  fully general "chosen subset vs every available artifact" case is DEFERRED: on a
  default project in-force == available for every kind except `skill`, so a strict
  subset cannot be witnessed without a non-default selection — the #6137 selection
  fixture._
- **PR-CHARTER-GOVERNANCE-001** (authored) — Sharing a pack does not silently add
  its commands to every tool; a skill is in force only when the charter requires
  or selects it, not merely because a pack offers it.
  Evidence: `effective_when_absent == "required"` for `skill` (ADR `2026-09-27-1`);
  the in-force skill set is the required set, not every available skill. Witnessed
  honestly: a team pack OFFERS a skill without requiring it → the skill is in
  `charter list --all` (available) but not in `charter list` (in force).
- **PR-CHARTER-GOVERNANCE-002** (authored; research add) — A team's org-wide
  requirement is honoured on top of the project's own choices (selection overlay).
  Evidence: `ArtifactKind.selection_overlayable` and the org `required_<plural>` →
  `selected_<plural>` union (`artifact_kinds.py`,
  `src/charter/activation/org_charter.py`). The evidence fact is offering-owned; the
  union is applied during generation/synthesis, so the scenario synthesizes WITH the
  org pack present, then reads `charter list`.

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
- **PR-CHARTER-SHARING-002** (`@wip`) — When a project and an org pack both speak to
  the same governance, the project's choice is the one in force.
  Evidence: layered repository resolution (`has_layered_repository`, 11 kinds);
  project overrides org/built-in (`drg/merge.py` override machinery, ADR
  `2026-05-16-1`). `@wip` because witnessing that the project's choice WINS (not just
  that its rule is present) needs the black-box override + layer-provenance fixture
  tracked by #6137.
- **PR-CHARTER-SHARING-003** — A shared skill under a reserved namespace is not
  accepted as sound.
  Evidence: reserved prefixes `spk-` / `spec-kitty-` / `spec-kitty.` and the
  namespace grammar (`src/charter/activation/org_charter.py`,
  `skill_preparation.require_valid_skill_namespace`; ADR `2026-09-27-1`). Witnessed
  via the offering surface `doctor charter-packs` (pack-health), not via an
  activation command, so no excluded activation behaviour is authored; if the
  namespace check does not surface in pack-health it is red for a real reason.
- **PR-CHARTER-SHARING-004** (research add) — A shared asset that reaches outside its
  own pack folder is not accepted as sound.
  Evidence: `AssetPathEscapeError` fail-closed (NFR-006) —
  `src/charter/offering/assets/repository.py`. A genuine, offering-owned trust
  guarantee; witnessed via `doctor charter-packs`.

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
- Partial-override field-merge + a "your override shadows a shipped one" warning
  (ADR `2026-05-16-1`) — the field-preservation half drifts toward "composition
  resolves the way I expect"; the warning half is an affordance echo. Mechanism tier.
- Model→task-type routing (`charter.offering.api` → `model_task_routing.evaluate`) —
  reduces to a catalog lookup; a separate governed "routing" sense, not
  governance-in-force. Mechanism tier.
- The artifact-placement layout gate (ADR `2026-07-26-2`) and the DRG-edges-as-sole-
  authority mechanism (ADR `2026-07-26-1`) — authoring-time / file-layout, explicitly
  excluded. Skipped.
- The public-surface "a consumer pinned to the seam survives the split" guarantee
  (ADR `2026-10-12-2` / `2026-10-16-1`) — this is the **Python public-surface import-
  conformance** tier that #6286's own DoD owns; wrong tier for a BDD scenario. Skipped.

## Step-library plan (and the real cost)

The binding cost is the Java step library + its black-box governance fixture. The
existing arrange steps (interview / generate / synthesize) are reused; the new
`CharterSteps` adds a small, coarse, **outcome-verb** vocabulary (`the author checks
the shared governance is sound`, `the governance in force is only what the charter
puts in force`, `the system refuses with a clear reason`) plus a thin team-pack
fixture that authors a user-authored pack and registers it — all **by running the
CLI / authoring user content** (constraint C-002), never by writing CLI-managed
state.

**Honest wiring (the review-driven correction):** each Act drives the command that
actually performs the governed check. `charter synthesize` on a fresh project takes
the seed path and evaluates nothing, so it is NOT the witness for pack soundness;
`doctor charter-packs` is — it exits non-zero (not healthy) on an invalid profile,
an org-DRG error (a dangling edge), an unhealthy skill/asset surface. Broken-charter
fail-closed is witnessed by `charter synthesize` on a corrupt `charter.yaml`;
in-force membership by `charter list` vs `charter list --all`.

The operator ruled **bind all** (green not required; red acceptable only for a real
reason). Eight scenarios are bound to a real step; one — `SHARING-002` (project's
choice WINS over an org pack) — is `@wip` because a correct witness needs the
override + layer-provenance fixture tracked by **#6137** (owned by the operator),
and binding it to a weaker check would pass even when the org pack won (dishonest).
No scenario is stubbed; a bound scenario that is red in the nightly is red for a
documented real reason, not a fake one.

## Traceability + honesty

`PROMISES.md` maps every `@promise:` id to its FR/ADR. Bound scenarios run nightly
cross-OS via Cucumber-JVM; unbound ones carry `@wip` + `@wip-owner` + `@wip-since`
and do not gate the nightly. No promise was invented without evidence; no scenario
tagged `@defect` or phrased as a reproduction.
