---
title: Layered Doctrine Resolution — Design Blueprint
description: 'Design blueprint (approved 2026-05-15) for layered doctrine resolution across issues #832/#883/#1013: how doctrine layers compose and resolve.'
doc_status: durable
updated: '2026-09-30'
audience: docs/context/audience/internal/system-architect.md
---
# Layered Doctrine Resolution — Design Blueprint

Status: approved for mission planning, 2026-05-15  
Related issues: #832, #883, #1013  
Depends on: Phase 7 schema versioning (#469), landed in 3.2.x

---

## Problem

*Written 2026-05-15. The org layer this blueprint proposes has since shipped (the three-layer
built-in → org → project model; see the retired [#391 doctrine usage test](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/doctrine/391-doctrine-usage-test.md)),
so read this section as the problem as it stood then.*

The spec-kitty doctrine resolution stack had two layers at the time: **shipped** (bundled with the
CLI) and **project** (`.kittify/doctrine/`). This is sufficient for individual project governance,
but it leaves a structural gap for organisations that adopt spec-kitty across multiple teams.

Today those organisations face one of three unacceptable options:

- **Fork the CLI** to hard-code org governance into the shipped layer. Forks diverge from upstream
  and become a maintenance liability.
- **Repeat configuration** in every project's `.kittify/doctrine/`. Each new project re-derives
  org standards from scratch; drift accumulates.
- **Leave org governance out** of spec-kitty entirely and maintain a parallel initialisation
  system. Two systems means two onboarding paths and no shared governance model.

Two secondary gaps compound the problem:

- **Mission-type bleed-through.** All missions — software-dev, documentation, research — receive
  the same governance context, which leans on `software-dev-default` assumptions. A documentation
  mission should not inherit test-first coding doctrine.
- **External doc opacity.** A project may have an authoritative governance document (a public
  constitution, a security policy, an architecture decision record) that agents should read. There
  is no first-class way to declare these references in the charter so that `charter context`
  includes them.

---

## User Journeys

The following journeys describe the intended end-to-end experience once both missions land.
They are ordered from authoring (upstream) to consumption (downstream).

### Journey 1 — Security Policy Lead: authoring an org doctrine pack

> "Our security team has an exhaustive discovery process and a set of required security directives
> that every engineering team must follow. I need to encode these once and have them automatically
> available in every project that uses spec-kitty — without asking project teams to copy anything."

**Actors:** Security Policy Lead (doctrine author), spec-kitty CLI  
**Preconditions:** a spec-kitty release with org-layer support installed (org packs shipped during 3.2.x; the 3.3.x line named here originally was retired and never shipped); org has adopted spec-kitty for project workflow

1. The lead initialises a new git repository: `security-policies-doctrine`.
2. She authors directives, tactics, and toolguides in spec-kitty YAML schema under the pack
   directory layout:
   ```
   directives/
     sec-001-threat-modelling.directive.yaml
     sec-002-dependency-scanning.directive.yaml
   tactics/
     security-discovery-tactic.tactic.yaml
   toolguides/
     sast-pipeline.toolguide.yaml
   graph-extensions.yaml   ← additive DRG edges linking new nodes to shipped nodes
   ```
3. She runs `spec-kitty doctrine pack validate .` to confirm schema compliance and DRG edge
   consistency against the shipped graph.
4. She tags a release (`v1.0.0`) and publishes the repository (private git or internal registry).
5. She documents the pack's versioning policy in `CHANGELOG.md`.

**Outcome:** A versioned, self-contained doctrine pack that passes CLI validation and is ready
to distribute.

---

### Journey 2 — Enterprise Doctrine Maintainer: assembling the org distributable

> "We have several domain-specific doctrine packs — security, compliance, architecture standards.
> I need to aggregate them into a single org distributable that ships to every developer alongside
> the spec-kitty CLI."

**Actors:** Doctrine Maintainer, IT/Platform team  
**Preconditions:** Domain packs (`security-policies-doctrine`, `compliance-doctrine`, etc.) are
published and validated

1. The maintainer creates an `org-doctrine-distributable` repository.
2. She declares all domain packs as versioned dependencies in an `org-doctrine.yaml` manifest:
   ```yaml
   schema_version: "1"
   org_name: "acme-corp"
   packs:
     - source: git
       url: "git@internal.example.com:security/security-policies-doctrine.git"
       ref: "v1.0.0"
     - source: git
       url: "git@internal.example.com:architecture/arch-doctrine.git"
       ref: "v2.1.0"
   ```
3. She authors a **baseline charter fragment** — shared charter policy elements (review
   expectations, human-in-command policy, publication authority) that all projects inherit. These
   reference org-layer doctrine artifacts by URN so `charter context` can traverse them.
4. She runs `spec-kitty doctrine pack assemble .` to merge domain packs into a single validated
   local snapshot and confirm no DRG edge conflicts.
5. She tags and publishes the distributable. The distributable is the single installation artifact
   that IT will push to all developer machines.

**Outcome:** One versioned artifact that aggregates all org governance. Domain pack owners update
their packs independently; the maintainer cuts new distributable releases on their schedule.

---

### Journey 3 — IT/Platform: enforcing org doctrine installation

> "We distribute spec-kitty to all engineers via our internal toolchain. We want the org doctrine
> pack to be installed alongside the CLI with no manual step required from each developer."

**Actors:** IT/Platform team, company installation policy  
**Preconditions:** org-doctrine-distributable published; spec-kitty org-layer support landed

1. IT adds the distributable installation to the company toolchain alongside the spec-kitty CLI
   install:
   ```bash
   # company install script (conceptual)
   pipx install spec-kitty-cli  # any release with org-layer support
   spec-kitty doctrine fetch \
     --source git \
     --url git@internal.example.com:platform/org-doctrine-distributable.git \
     --ref stable \
     --target ~/.kittify/org/acme-corp/
   ```
2. The org source is registered in the global user config (`~/.kittify/config.yaml`):
   ```yaml
   doctrine:
     org:
       local_path: "~/.kittify/org/acme-corp/"
   ```
3. IT publishes the install script and policy in the company developer portal. New starters run
   one command; existing developers receive the update through the standard toolchain refresh.
4. `spec-kitty doctor` lists the registered org-layer artifacts and their versions at any time,
   giving IT an audit surface.

**Outcome:** Every developer machine has the org doctrine pack installed at a known path. No
project-level bootstrap is needed. The org layer is invisible until invoked — it just works.

---

### Journey 4 — Developer: starting a new project with zero org-layer configuration

> "I just installed spec-kitty and the org toolkit. When I start a new project, I expect our
> security and architecture standards to be automatically available — I should not need to set
> anything up."

**Actors:** Developer  
**Preconditions:** Journeys 1–3 complete; developer machine has org doctrine installed

1. The developer creates a new project repository and runs `spec-kitty init`.
2. She runs `spec-kitty charter interview` to produce the project charter. The interview surfaces
   org-layer directives, tactics, and agent profiles alongside shipped defaults. She selects the
   ones relevant to her project; org-layer selections are tagged with `source: org` in the
   compiled charter.
3. She runs a mission (`spec-kitty implement WP01`). The agent context includes org-layer security
   directives without any project-level configuration. She does not know or care that they came
   from the org layer — they are just part of governance.
4. She adds a project-local override for one directive (`sec-002-dependency-scanning`) to use a
   different scanner: she drops an override YAML in `.kittify/doctrine/directive/` and the
   project layer takes precedence as usual.
5. `spec-kitty charter status` shows the resolved governance stack: shipped → org → project,
   with source attribution for each artifact.

**Outcome:** Zero org-layer configuration at the project level. Project-local overrides still
work. The resolution order is transparent on demand.

---

### Journey 5 — Developer: mission-type governance in practice

> "I'm running a documentation mission. I don't want software-dev coding doctrine cluttering my
> agent context. And I want the org's documentation standards — audience, plain language,
> accessibility — to apply automatically."

**Actors:** Developer, agent running the mission  
**Preconditions:** Journey 4 complete; org pack includes documentation governance profile

1. The developer starts a documentation mission (`/spec-kitty.specify`). The mission type recorded
   in `meta.json` is `documentation`.
2. `charter context --action write` resolves governance in mission-type-aware order:
   ```
   project charter
   + shipped documentation governance profile
   + org documentation governance overrides (if present in org pack)
   + mission-instance addendum (if declared in mission meta)
   ```
3. The agent context does **not** include test-first coding doctrine, CLI interface requirements,
   or code-review assumptions. It does include audience targeting, Divio type requirements,
   plain-language directives, and accessibility guidelines.
4. If the project charter also declares `governance_references`, those external docs (e.g.
   `docs/style-guide.md`, `spec/writing-standards.md`) are included as bounded excerpts in the
   context.
5. Running the same mission on another project in the same org automatically picks up the org
   documentation governance profile — no per-project setup.

**Outcome:** Mission-type governance is zero-config and compositional. The correct governance
scope is derived from the mission type, not inferred from template selection.

---

### Journey 6 — Developer: declaring governance references in the charter

> "We have a public project constitution at `spec/constitution.md` and a company architecture
> decision record at `docs/adr/`. I want agents to read these when doing governed actions — but
> I don't want to copy them into `.kittify/`."

**Actors:** Developer  
**Preconditions:** `charter.md` exists; referenced documents exist in the repository

1. The developer adds a `governance_references` block to the project charter:
   ```markdown
   ## Governance References
   - path: spec/constitution.md
     description: "Public project governance constitution"
   - path: docs/adr/
     description: "Architecture decision records"
   ```
2. `charter context --action implement` includes bounded excerpts from the referenced paths in
   the rendered context block.
3. `charter status` confirms the references resolve correctly. If `spec/constitution.md` is later
   deleted or moved, `charter status` emits an actionable warning (not a silent omission).
4. `charter generate --force` does not overwrite `charter.md` if it is a symlink pointing outside
   the expected charter bundle path — an error is emitted with a remediation hint.

**Outcome:** External authoritative documents are first-class references in the charter, surfaced
in agent context without duplication or enforcement of content equality.

---

## Architecture Blueprint

### Current resolution stack

```
shipped  (.../site-packages/doctrine/)
    ↕ field-level merge
project  (.kittify/doctrine/)
```

### Target resolution stack

```
shipped  (.../site-packages/doctrine/)
    ↕ full-replace on ID collision (org overrides shipped)
org      (~/.kittify/org/<pack-name>/)      ← new
    ↕ full-replace on ID collision (project overrides org)
project  (.kittify/doctrine/)
```

Precedence: `shipped < org < project`. Project teams retain full override authority.
Org-layer overrides of shipped artifacts surface as advisory warnings in `doctor` and
`charter lint`, never hard errors.

### DRG layer model

The DRG (`graph.yaml`) gains the same three-layer treatment. Additionally, the shipped and org
graphs support **multi-file loading**: a `doctrine/drg/` directory of `*.graph.yaml` fragments
is merged before the layer merge, replacing the current single-file constraint.

```
shipped graph fragments  →  merge  →  shipped DRGGraph
org graph-extensions.yaml           →  additive layer
project graph-extensions.yaml       →  additive layer
                                    =  resolved DRGGraph
```

### Mission-type governance resolution

```
project charter policy
  + shipped mission-type profile  (src/doctrine/mission_type_profiles/<type>.profile.yaml)
  + org mission-type override     (org layer, if present)
  + mission-instance addendum     (kitty-specs/<mission>/governance-addendum.yaml, if present)
```

Selection key: `mission_type` from `kitty-specs/<mission>/meta.json`.
No fallback to `software-dev-default` for non-software missions.

### Governance references

Charter metadata gains an optional `governance_references` list. Each entry is a repo-root-scoped
path (file or directory). `charter context` includes referenced content as bounded excerpts.
Missing paths produce a warning in `charter status`; they do not block resolution.

---

## Key design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Org-layer slot type | `org_root: Path \| None` in config; `org_roots: list[Path]` internally | Exposes single-org UX; internally generalisable to multi-org without API break |
| ID collision semantics | Full-replace (org replaces shipped; project replaces org) | Simpler authoring contract than field-level merge; authors need to substitute, not patch |
| Remote fetch model | Pull-once → validate → write local snapshot; no runtime remote calls | Deterministic in CI/CD; offline-safe |
| Multi-file DRG | Directory of `*.graph.yaml` fragments merged before layer merge | Scoped diffs; enables token-efficient partial loading |
| Mission-type key | `mission_type` from `meta.json`, not inferred from `template_set` | Explicit; removes software-dev bleed-through |
| Governance references | Path-list in charter; bounded excerpts in context | No copy requirement; no equality enforcement |
| Symlinked charter.md | Guard on `charter generate --force`; error + remediation hint | Explicit over silent |

---

## Mission structure

This capability is delivered in two chained missions.

### Mission A — Layered Doctrine Resolution (infrastructure)

Closes #832. Prerequisite for Mission B.

| WP | Scope |
|---|---|
| WP01 | Multi-file DRG loading: `load_graph(path_or_dir)` + update 8 `graph.yaml` call sites in `charter/` |
| WP02 | `BaseDoctrineRepository` three-layer loading: `_apply_org_overrides()` between shipped and project |
| WP03 | `DoctrineService` gains `org_roots: list[Path]`; all repository properties updated |
| WP04 | Config model: `doctrine.org` block in `.kittify/config.yaml`; `spec-kitty doctrine fetch` command |
| WP05 | Observability: `"source": "org"` in `charter context --json`; `doctor` lists org artifacts; `charter lint` advisory warning on org-overrides-shipped |

### Mission B — Governance-Aware Context (application layer)

Closes #883 and #1013. Depends on Mission A.

| WP | Scope |
|---|---|
| WP01 | Shipped mission-type governance profiles (`software-dev`, `documentation`, `research`, `plan`) as `*.profile.yaml` |
| WP02 | Mission-type resolution in `charter context`: key off `meta.json mission_type`; no software-dev fallback for non-software missions |
| WP03 | Charter `governance_references`: schema field, context injection, missing-path warning in `charter status` |
| WP04 | Charter write guards: symlinked `charter.md` detection in `charter generate --force`; legacy-path cleanup (`constitution`-era paths removed from current runtime checks) |

---

## Non-goals

- CLI plugin system for runtime behaviour (doctrine scopes agent evaluation, not CLI execution).
- Multi-org layers (company + business-unit config UX) — structurally supported by the
  `org_roots: list` internal model but deferred.
- External-authoritative charter path (configured alternate path for `charter.md`) — deferred
  per ADR `2026-05-08-1-charter-governance-center-and-external-governance-docs`.
- Content-equality enforcement between governance references and `charter.md`.
- Automatic org-layer upgrade (version pinning and upgrade are explicit operator actions).
