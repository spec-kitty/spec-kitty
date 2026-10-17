# Charter-activation scenarios — DRAFT (promise tie-in pending QA ratification)

These feature files describe the consumer-facing behaviour of the charter **activation**
offering: the lifecycle verbs — adopting (activate), retiring (deactivate), and bringing along
what a choice depends on (cascade) — that the charter **offering** suite under
[`../charter/`](../charter/) deliberately left out ("the activation layer extracts later", see
that suite's `RESEARCH.md`).

They exist to close an asymmetry: the charter is slated to extract as an external package with
**two** sibling entry-point seams — `charter.offering.api` and `charter.activation.api` (ADR
`2026-10-12-2`, epic #6099). The offering seam already has a consumer-outcome contract net
(`../charter/`, `Refs #6286`); the activation seam did not. This subtree is that net for
activation.

## What is deliberately NOT here

This is a **description of features and scenarios only**. It intentionally omits:

- the `@promise:PR-...` identity tags, and
- a `PROMISES.md` promise→contract ledger mapping each scenario to its offering FR/ADR.

Creating and ratifying those is the **QA team's** to own, tracked in **spec-kitty-qa#801**.
Until QA binds the step vocabulary and decides each scenario's gating status, every scenario
carries `@wip` (with `@wip-owner` / `@wip-since`), so the per-PR scenario-contract gate treats
its not-yet-bound steps as information, not failure
(`tests/architectural/test_scenario_contract.py`).

Each scenario's **Act** already drives the governed outcome rather than a command's output, so a
later step binding stays honest and the scenario survives whichever command delivers it.

## Features

| Folder | Consumer outcome |
|--------|------------------|
| `turning-governance-on-and-off/` | Adopting or retiring a rule changes what is actually in force; adopting one more never drops the rest; naming something that does not exist changes nothing. |
| `turning-off-keeps-the-rest-sound/` | Retiring a choice keeps anything still relied on (and names why), and refuses — with the way forward — on a kind never put under explicit control. |
| `brings-what-it-depends-on/` | Adopting a choice can bring what it depends on in one step, can be scoped, warns about what a bare adoption left out, and never offers to turn on something that cannot stand alone. |
| `provisioning-governance-packs/` | The backend is supplied with packs that resolve through public seams (a filesystem location or a published reference); an unresolvable pack is refused, never treated as empty; and a configured pack's parts are brought into force deliberately, changing what the runtime offers (a new mission type to run, a new profile that applies). |
| `the-default-governance-profile/` | Before a project turns anything on, it is governed by all the governance available to it — except shareable commands, which apply only when the charter requires or selects them, so provisioning a pack never silently adds commands to every tool; maintainer-only governance is in force only on explicit opt-in. |

## For QA, when ratifying

- The grounding evidence each feature's maintainer notes cite (FR/ADR, `src/charter/activation/*`)
  is the raw material for the promise→contract ledger — read it, do not transcribe it into the
  scenario text.
- Candidate activation promises **deliberately deferred** from this first draft (for QA to weigh):
  a workflow step loads exactly the governance in force for it (`charter context --action`, the
  effective-set resolver). It risks reading as a command-affordance echo, so it is held back
  rather than authored speculatively.
- **Overlap caveat:** some activation authorities are already asserted *through* the offering
  suite — selection overlay (`org_charter.py`), fail-closed activation (`plan_activation`),
  skill-namespace grammar (`org_charter.py`). The activation ledger should cover the lifecycle
  **verbs** the offering suite excluded, not re-assert those.
