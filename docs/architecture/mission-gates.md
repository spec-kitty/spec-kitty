---
title: Mission transition gates — declarative, asset-backed, trust-gated
description: 'The declarative model for transition gates: a gate artefact whose check ships as an asset, trust-checked before it runs, with severity-typed outcomes.'
doc_status: active
updated: '2026-09-27'
type: explanation
related:
- docs/architecture/mission-type-resolution.md
- docs/architecture/artifact-placement-seam.md
- docs/architecture/doctrine-kinds.md
- docs/adr/3.x/2026-08-13-2-gates-are-declarative-asset-backed-doctrine-artefacts.md
- docs/adr/3.x/2026-08-13-3-gate-execution-targets-through-kernel-surface-selector.md
- docs/adr/3.x/2026-08-13-4-executable-doctrine-runs-only-from-trusted-publishers.md
- docs/adr/3.x/2026-08-13-5-local-daemon-amortizes-doctrine-parse-and-caches-gate-verdicts.md
- docs/adr/3.x/2026-08-13-6-gate-outcomes-carry-severity-operator-strategy-decides-effect.md
---
# Mission transition gates — declarative, asset-backed, trust-gated

> **Status: the gate mechanism is an accepted design, not yet shipped behaviour.** The
> definition, trust and severity ADRs ([2026-08-13-2](../adr/3.x/2026-08-13-2-gates-are-declarative-asset-backed-doctrine-artefacts.md),
> [-4](../adr/3.x/2026-08-13-4-executable-doctrine-runs-only-from-trusted-publishers.md),
> [-6](../adr/3.x/2026-08-13-6-gate-outcomes-carry-severity-operator-strategy-decides-effect.md))
> were amended and **Accepted** together on 2026-09-27; [-3](../adr/3.x/2026-08-13-3-gate-execution-targets-through-kernel-surface-selector.md)
> and [-5](../adr/3.x/2026-08-13-5-local-daemon-amortizes-doctrine-parse-and-caches-gate-verdicts.md)
> keep their own status. This page is the design of record, not a description of shipped
> behaviour: today the only gate is the `spec-kitty-pre-review` code gate, and every gate fault
> fails open. The structural decision underneath it — the built-in mission
> subtree stays nested and the legacy `MissionStepContract` surface is retired
> ([ADR 2026-08-13-1](../adr/3.x/2026-08-13-1-built-in-mission-subtree-stays-nested-retire-legacy-step-contracts.md))
> — is **Accepted**.

A **transition gate** is a deterministic check that runs when a work package crosses a lane
edge (e.g. `in_progress → for_review`) and returns a pass/fail verdict that can block the
transition. This page explains the declarative model that replaces the legacy
named-Python-handler registry.

## The moving parts

| Concern | Answer | ADR |
|---|---|---|
| **What a gate is** | A first-class doctrine `gate` artefact kind (declarative YAML), reusable by id, tiered like every other kind. | [-2](../adr/3.x/2026-08-13-2-gates-are-declarative-asset-backed-doctrine-artefacts.md) |
| **What the check is** | Code shipped as an `asset` (inert blob, resolved by id), run as an allowlisted `interpreter` plus an `args` list (no shell string). | [-2](../adr/3.x/2026-08-13-2-gates-are-declarative-asset-backed-doctrine-artefacts.md) |
| **Where it runs** | An `executionTarget` surface selector (doctrine-owned token set) resolved through the existing stamped `GateExecutionContext` via the topology placement seam's `execute_dir` verb. | [-3](../adr/3.x/2026-08-13-3-gate-execution-targets-through-kernel-surface-selector.md) |
| **Whether it may run** | Trust: built-in trusted by install position; org/project packs are trust-on-first-use, keyed on the operator coordinate plus a locally computed hash of the executable surface. Consent lives in the user home; the repo may only pin hashes. Release signing is deferred. | [-4](../adr/3.x/2026-08-13-4-executable-doctrine-runs-only-from-trusted-publishers.md) |
| **What its outcome does** | The outcome carries a typed severity (`BLOCKING`/`RECOVERABLE`/`WARN`/`INFO`); the operator's error-handling strategy (`block_above(threshold)` in `.kittify`) decides the CLI effect. The default blocks at `BLOCKING` only; trust/tamper outcomes are always `BLOCKING`. | [-6](../adr/3.x/2026-08-13-6-gate-outcomes-carry-severity-operator-strategy-decides-effect.md) |
| **How fast (later)** | *Open.* Parse-amortization is sound (content-addressed parse cache, no daemon); a deterministic *verdict* cache is contested and held open. | [-5](../adr/3.x/2026-08-13-5-local-daemon-amortizes-doctrine-parse-and-caches-gate-verdicts.md) |

## Diagrams

> Rendered locally by the no-egress PlantUML pipeline (`scripts/docs/plantuml_render.py`,
> `--network=none`, SANDBOX profile). The distribution view uses PlantUML's **native ArchiMate**
> (bundled in the pinned jar — no `!include`, no egress).

### Distribution & consumer value (ArchiMate)

```plantuml
@startuml
title Gate distribution & consumer value (ArchiMate)
archimate #Business "Operator" as op <<business-role>>
archimate #Technology "built-in pack\n(trusted by position)" as builtin <<technology-artifact>>
archimate #Technology "org / project pack\n(TOFU)" as orgpack <<technology-artifact>>
archimate #Technology "gate defs + assets" as gates <<technology-artifact>>
archimate #Technology "Operator machine\n(CLI - optional daemon)" as machine <<node>>
archimate #Application "Declarative gate engine" as engine <<application-component>>
archimate #Business "Mission transition" as mission <<business-process>>
archimate #Motivation "Deterministic governed checks" as value <<motivation-value>>
builtin --> gates : ships
orgpack --> gates : ships
gates --> machine : resolved on
machine *-- engine
op --> machine : configures strategy (.kittify)
engine --> mission : guards
mission --> value : realizes
@enduml
```

### Bounded contexts by layer (component)

```plantuml
@startuml
title Gate subsystem - bounded contexts by layer
skinparam componentStyle rectangle
package "kernel" {
  [ERROR_SEVERITY ladder] as sev
}
package "doctrine" {
  [gate ArtifactKind - BC1] as gatekind
  [MissionStep.gates - BC2] as binding
  [executionTarget token set] as token
  [asset - inert blob] as asset
}
package "charter" {
  [activation and trust prompt] as charteract
}
package "mission_runtime" {
  [placement seam + execute_dir - BC4] as seam
}
package "specify_cli" {
  [declarative-gate dispatcher - BC3] as dispatch
  [stamped GateExecutionContext] as stamp
  [trust TOFU - BC5] as trust
  [error-handling policy] as policy
}
gatekind --> asset : references
binding --> gatekind : binds by id
dispatch --> binding : reads
dispatch --> stamp : runs in
stamp --> seam : resolves via
seam ..> token : parity ACL
dispatch --> trust : checks
dispatch --> policy : outcome to effect
policy --> sev : uses
trust ..> charteract : prompt at activation
@enduml
```

### Runtime flow + internal resolution (sequence)

```plantuml
@startuml
title Gate flows - runtime-charter-gate and internal resolution
actor Runtime
participant Charter
participant "Dispatcher" as D
participant "Doctrine" as Doc
participant "Placement seam" as Seam
participant "Trust" as Trust
participant "Asset runner" as Run
participant "Policy" as Pol
== 1. Runtime calls gates through the charter ==
Runtime -> Charter : transition WP on_transition
Charter -> D : dispatch bound gates
D -> Doc : gate id to definition and asset
D -> Trust : trusted? re-hash executable surface
alt untrusted or tampered
  Trust --> D : could-not-run BLOCKING
else trusted
  D -> Seam : executionTarget to execute_dir
  Seam --> D : stamped GateExecutionContext
  D -> Run : allowlisted interpreter + args, confined
  Run --> D : JSON verdict or could-not-run RECOVERABLE
end
D -> Pol : outcome and severity
Pol --> Charter : effect via block_above strategy
Charter --> Runtime : allowed or blocked or degraded
== 2. Internal resolution and files ==
note over Doc: packs/built-in/gates/ID.gate.yaml then asset blob then executionTarget token
note over Seam: token + MissionTopology then surface then workdir (stamped)
note over Trust: user-home consent store: operator coord + executable-surface hash; repo may pin hashes only
note over Pol: .kittify strategy then ERROR_SEVERITY ladder (kernel)
@enduml
```

## Definition vs binding

Two separated concerns:

- **Definition** — the `gate` artefact says *what the check is*: which asset holds the code,
  the `interpreter` and `args`, the `executionTarget`, the timeout, and the severity of a
  detected violation.
- **Binding** — the `MissionStep` says *when it fires*: an `on_transition` edge plus the gate
  id. Definition is reusable across steps and mission types; binding is per-step and ships in
  the per-type mission bundle.

```yaml
# gate definition — packs/built-in/gates/docs-structural-lint.gate.yaml
id: docs-structural-lint
schema_version: "1.0"
description: "DIRECTIVE_042 structural lint for documentation missions"
asset: common-docs-structural-lint       # code blob (asset kind, inert, resolved by id)
interpreter: python                       # structured invocation — no shell string
args: ["{asset}", "--strict"]            # {asset} → resolved asset path, as one argv element
executionTarget: primary                  # doctrine-owned selector → placement seam execute_dir
timeout_seconds: 120
severity: RECOVERABLE                      # outcome severity; operator strategy decides the effect
```

```yaml
# binding — packs/built-in/missions/mission-steps/documentation/validate/step.yaml
id: validate
# … unified MissionStep fields …
gates:
  - on_transition: "in_progress->for_review"
    gate: docs-structural-lint
```

## Execution model

1. A lane transition fires; the generic `declarative-gate` dispatcher (alongside a few
   grandfathered code gates such as `spec-kitty-pre-review`) is invoked with a
   `TransitionGateContext`.
2. The dispatcher resolves the gate's `executionTarget` selector through the placement seam,
   given the mission's `MissionTopology`, to a **stamped `GateExecutionContext`** (not a bare
   path — the stamp is what refuses a surface that cannot hold the artifact).
3. It checks the pack's **trust** before resolving or running anything: built-in is trusted by
   install position; any other pack needs a consent entry in the user-home trust store matching
   the executable-surface hash, which is **re-computed now**, at dispatch. Untrusted, a hash
   mismatch, or tampering is a *could-not-run* outcome at `BLOCKING` — never a silent skip.
4. If trusted, it resolves the referenced asset to a path and runs the allowlisted `interpreter`
   with `args` in the resolved context under the refuse-unconfinable baseline (env allowlist,
   process-group kill + `setrlimit`, path confinement, capped verdict channel). A host that cannot
   apply the baseline, a crash, a timeout, or a missing interpreter is a *could-not-run* outcome
   at `RECOVERABLE`; a detected violation carries the gate's declared severity.
5. The operator's error-handling strategy (`block_above(threshold)`, default: block at `BLOCKING`
   only) maps that severity to the CLI effect (block vs proceed-degraded). Repository config
   cannot demote trust outcomes below `BLOCKING`, and every verdict records the effective
   strategy.

## Invariants

- Gates are **deterministic and side-effect-free** — pure checks, never mutate mission state.
  This is **enforced** by the refuse-unconfinable baseline (#2540), not merely asserted; OS-level
  network denial is follow-on work (#2541).
- The `asset` kind stays inert — resolved to a path, never self-executing. The gate is the
  only thing that turns a path into an invocation.
- Trust is only ever consulted for **executing code**; inert doctrine needs no trust decision,
  and an edit to inert doctrine never changes the trust hash.
- Nothing is resolved or executed before the trust check passes. Trust is not containment: a
  trusted gate still runs under the baseline.
- There is **one disposition model**: every outcome (pass / failed / could-not-run) carries a
  severity, and the operator's error-handling strategy decides the effect. Trust and tamper
  failures are fixed at `BLOCKING`, so a missing CI trust seed **blocks loudly** rather than
  silently no-ops; machinery faults are fixed at `RECOVERABLE`, so they proceed degraded and on
  the record (this keeps C-003, "never break `move-task`").

## Relationship to the mission subtree

Gates that are mission-type dependent (documentation linting, per-type consistency checks)
ship inside the per-type bundle under `packs/built-in/missions/<type>/`; shared gates live at
the built-in tier and are referenced by id. This follows the nested, self-contained mission
subtree fixed by [ADR 2026-08-13-1](../adr/3.x/2026-08-13-1-built-in-mission-subtree-stays-nested-retire-legacy-step-contracts.md).
