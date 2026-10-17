# Charter-offering promises

<!-- Frozen-contract index for the charter-offering BDD suite. Each @promise id tags exactly one
scenario and names the offering guarantee it asserts. Authored per the
charter-offering-scenario-extraction procedure; evidence is read, never transcribed. Updated:
2026-10-17. -->

Each row maps a `@promise:` id to the offering guarantee it asserts and the FR/ADR that states it.
The suite is the consumer contract on top of the Python `tests/e2e` / `tests/charter*` mechanism
net, which stays in place. See `RESEARCH.md` for the extraction trail.

## The governance in force is what I chose — `governance-in-force/`

| Promise | Consumer guarantee | Offering authority | Binding |
|---------|--------------------|--------------------|---------|
| `PR-CHARTER-GOVERNANCE-001` | Sharing a pack does not silently add its commands to every tool; a skill is in force only when the charter requires/selects it, not merely because a pack offers it. | `ArtifactKind.effective_when_absent == "required"` for `skill` — `src/charter/offering/artifact_kinds.py`; ADR `2026-09-27-1`. | bound |
| `PR-CHARTER-GOVERNANCE-002` | A team's org-wide requirement is honoured on top of the project's own choices (selection overlay). | `ArtifactKind.selection_overlayable` + org `required_<plural>` → `selected_<plural>` union — `src/charter/offering/artifact_kinds.py` / `src/charter/activation/org_charter.py`. | bound |

## The system refuses unsound governance with a clear reason — `refuses-unsound-governance/`

| Promise | Consumer guarantee | Offering authority | Binding |
|---------|--------------------|--------------------|---------|
| `PR-CHARTER-REFUSAL-001` | Governance that would silently drop part of a profile is refused, not quietly accepted. | `enhances` field-merge preserves step sequence + I/O; a silent drop is rejected — agent-profile validation (AGENTS.md "Profile Load Diagnostics"). | bound |
| `PR-CHARTER-REFUSAL-002` | A mistyped reference between pieces of governance is named, not dropped. | `unresolved_edge_endpoint` / `UnknownRelationError` — `src/charter/offering/drg/merge.py` (FR-010 / FR-003), closing ADR `2026-07-26-3`'s silent-drop path. | bound |
| `PR-CHARTER-REFUSAL-003` | A broken charter fails closed instead of running half-applied. | `ActiveCharterConfigError` fail-closed; `plan_activation()` never mutates on validation failure — ADR `2026-05-16-1` (NFR-003). | bound |

## I can share governance across a team or project safely — `share-governance-safely/`

| Promise | Consumer guarantee | Offering authority | Binding |
|---------|--------------------|--------------------|---------|
| `PR-CHARTER-SHARING-001` | A team pack carrying an unsound profile is not reported healthy, even when its graph counts look right. | `AgentProfileRepository.skipped_profiles` → `doctor charter-packs` (FR-010) — `src/charter/offering/agent_profiles/repository.py`. | bound |
| `PR-CHARTER-SHARING-002` | A project's own governance choice wins over the team pack it adopts. | Layered repository + override machinery — ADR `2026-05-16-1`. | `@wip` (needs #6137 override + layer-provenance fixture) |
| `PR-CHARTER-SHARING-003` | A shared skill under a reserved namespace is not accepted as sound. | Reserved prefixes `spk-` / `spec-kitty-` / `spec-kitty.` + namespace grammar — `src/charter/activation/org_charter.py`, `skill_preparation`; ADR `2026-09-27-1`. | bound |
| `PR-CHARTER-SHARING-004` | A shared asset that reaches outside its own pack folder is not accepted as sound. | `AssetPathEscapeError` fail-closed (NFR-006) — `src/charter/offering/assets/repository.py`. | bound |

## Binding status

Every scenario drives, in its Act, the command that actually performs the governed check, so a red
is honest: `doctor charter-packs` exits non-zero (not healthy) on an unsound shared pack, and
`charter synthesize` fails closed on a broken charter — never `charter synthesize` on a fresh
project, which takes the seed path and evaluates nothing. Eight scenarios are bound to a real
outcome-verb step; one (`SHARING-002`) is `@wip` because witnessing that the project's choice WINS
over an org pack needs the black-box override + layer-provenance fixture tracked by #6137.

A bound scenario may still be red in the nightly Cucumber-JVM run for a real, documented reason
(a defect's witness surfaces on a surface the Act does not yet drive, or a fixture gap), never
because of a stub. The per-PR scenario contract (`tests/architectural/test_scenario_contract.py`)
checks the tag and step-binding shape without a JDK; the nightly acceptance-bdd job runs the bound
scenarios cross-OS. Expected green vs red-for-a-real-reason is called out in the PR body.
