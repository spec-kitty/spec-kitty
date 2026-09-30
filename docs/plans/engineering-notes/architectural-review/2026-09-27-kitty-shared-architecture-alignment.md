---
title: Engine-side alignment review against the Kitty Shared Architecture — 2026-09-27
description: 'Engine-side, point-in-time review of what spec-kitty offers and lacks for a proposed hosted target architecture: 29 findings, term collisions, next steps.'
doc_status: point_in_time
type: explanation
updated: '2026-09-27'
audience:
- docs/context/audience/internal/system-architect.md
- docs/context/audience/internal/maintainer.md
related:
- docs/plans/engineering-notes/architectural-review/README.md
- docs/plans/engineering-notes/architectural-review/2026-05-25-deep-dive-architectural-review.md
- docs/context/team-kitty.md
- docs/context/glossary-conventions.md
- docs/architecture/diagrams/01_context/README.md
- docs/architecture/diagrams/02_containers/README.md
- docs/architecture/launch-readiness-future.md
- docs/adr/3.x/2026-04-09-1-mission-identity-uses-ulid-not-sequential-prefix.md
- docs/adr/3.x/2026-04-19-1-cli-auth-uses-encrypted-file-only-session-storage.md
- docs/adr/3.x/2026-04-26-1-contract-pinning-resolved-version.md
- docs/adr/3.x/2026-09-06-1-convergence-retirement-and-client-repo-inversion.md
---
# Engine-side alignment review against the Kitty Shared Architecture — 2026-09-27

On 2026-09-27 a read-only review squad compared the spec-kitty engine with the **Kitty Shared Architecture**: a proposed, not-yet-ratified target architecture for the hosted Kitty products, kept as a private planning document. The full analysis, including the findings and rulings on the target-architecture side, is held in the private planning repository for spec-kitty organization members.

This page is the **engine-side** version. It keeps only what concerns spec-kitty: what the engine does today, what its contracts, ADRs and charter say, and what any hosted target architecture would need from the engine. Target-architecture assumptions are stated generically.

- **Squad**: four agent profiles, one lens each — `architect-alphonso` (core architecture, and consolidator), `planner-priti` (roadmap and plans), `paula-patterns` (docs, language and authority) and `reviewer-renata` (adversarial claim check).
- **Pinned to**: spec-kitty `main` at `e2dcf69c` (CLI `4.0.0rc5`); line numbers are at that commit. `spec-kitty-events` 10.4.0, inside the pin `>=10.4.0,<11` ([`pyproject.toml`](../../../../pyproject.toml), line 80).
- **Audience**: system architects and maintainers of spec-kitty who know the engine. This is a point-in-time record; it will not be updated.
- **Terms**: a **Decision Moment** is the engine's decision ledger entry (`agent decision open/resolve/…`); a **moment** is a live Zeitgeist frame the CLI publishes; the **HiC** (Human-in-Charge) governs charter changes.

**Severity scale (engine-side)**

| Severity | Meaning |
|---|---|
| BLOCKER | A hosted design cannot rely on this until the engine gains it or the design routes around it. |
| HIGH | Plan or fix before a hosted design depends on this part of the engine. |
| MEDIUM | Fix during follow-through. |
| LOW | Wording. |

A ↓ marks a finding the consolidator downgraded; the reason is in the row.

---

## Executive summary

**Engine-side verdict: a sound core to build on, with real gaps that are not yet tracked.**

The engine is the only writer of mission state, persists locally first, versions its public contracts, and publishes live moments without blocking local work.

What the engine lacks today:

- an engine↔hosted decision round trip (EC-1);
- room to add schema fields without a breaking change (EC-2);
- record canonicalisation, signature verification and repo-level decisions (EC-3);
- any spec-kitty plan for this work (RM-1).

The charter also fixes contract ownership and release rules that any target design must respect or amend through the HiC (EC-5, EC-6). And spec-kitty's own living C4 context view still describes the retired CLI→SaaS sync transport, so its docs cannot yet serve as the engine half of any alignment (SK-1).

**Counts:** 1 BLOCKER · 10 HIGH · 15 MEDIUM · 3 LOW (29 findings).

---

## 1. What the engine already provides

- **Single writer, local first.** The live fan-out never raises into local persistence ([`status/zeitgeist_bridge.py`](../../../../src/specify_cli/status/zeitgeist_bridge.py), lines 52-56).
- **Decision lifecycle** follows `spec-kitty-events`; the `resolved`, `deferred` and `canceled` verbs exist. The ledger is `status.events.jsonl` + `decisions/index.json` + `DM-<id>.md`.
- **Versioned client contract.** `orchestrator-api` is at contract 1.6.0 ([`orchestrator_api/envelope.py`](../../../../src/specify_cli/orchestrator_api/envelope.py), line 42), and the charter's "range plus lock" rule governs contract packages ([`charter.md`](../../../../.kittify/charter/charter.md), lines 312-318).
- **Live layer.** Team Kitty mints per-actor capabilities whose response carries `relay_url`, a seam for re-pointing clients. Presence TTL is at most 90 s ([`team-kitty.md`](../../../context/team-kitty.md), line 65). "Zeitgeist carries NOW, Git carries DONE" ([`live_work/__init__.py`](../../../../src/specify_cli/live_work/__init__.py), lines 6-7).

---

## 2. Findings

Prefixes: **EC** engine contract, **CL** target-architecture assumptions vs code, **RM** roadmap, **DA** docs, language and authority, **SK** spec-kitty staleness.

### EC — engine contract

| ID | Sev | Finding | Evidence | Recommendation |
|---|---|---|---|---|
| EC-1 | **BLOCKER** | An engine↔hosted decision round trip does not exist today. The target architecture assumes the engine opens decisions on the hosted side and receives answers back. | `decision open` appends locally and queues a best-effort moment ([`decisions/emit.py`](../../../../src/specify_cli/decisions/emit.py), 239-243) that is "lost — by design" ([`zeitgeist_bridge.py`](../../../../src/specify_cli/status/zeitgeist_bridge.py), 54). The SaaS client has no "get decision" ([`decisions/ownership.py`](../../../../src/specify_cli/decisions/ownership.py), 32-33). | Spike an inbound path. Until then a hosted design learns of decisions only from pushed `status.events.jsonl`, and answers return only through `agent decision resolve` or `orchestrator-api resolve-decision`. |
| EC-2 | HIGH | Schema additions are breaking. The target architecture assumes new decision fields are optional and additive. | DecisionPoint payloads are `extra="forbid"` (`spec_kitty_events/decisionpoint.py`, 9 sites; `decision_moment.py:84…144`), as are `IndexEntry` ([`decisions/models.py`](../../../../src/specify_cli/decisions/models.py), 84) and `WPMetadata` ([`status/wp_metadata.py`](../../../../src/specify_cli/status/wp_metadata.py), 215-217). | Older readers, including teammates' CLIs reading `status.events.jsonl` from git, reject new fields. Ship versioned types or tolerant readers first, then a declared breaking events release. |
| EC-3 | HIGH | Primitives a signed decision register would need are missing, and some cut across accepted ADRs. | No record canonicalisation (for example RFC 8785), signature verification or decision-policy code in `src/`. Events has an `overridden` state (`decisionpoint.py:86`) but the CLI has no override verb. The ledger is per mission ([`ownership.py`](../../../../src/specify_cli/decisions/ownership.py), 27-33), so repo-level decisions have no home. A new branch writer for records cuts across ADRs [2026-06-22-1](../../../adr/3.x/2026-06-22-1-mission-topology-ssot.md) and [2026-06-24-2](../../../adr/3.x/2026-06-24-2-write-branch-resolution-primary-anchor.md). | Size the engine delta (verbs, event types, branch writers, config, crypto) against those ADRs, split into events work and engine work. |
| EC-4 | HIGH | Any replacement for the per-team relays must keep, or explicitly retire, the live surfaces the CLI ships today. | Lane, lifecycle and decision moments fan out live ([`zeitgeist_bridge.py`](../../../../src/specify_cli/status/zeitgeist_bridge.py), 1-30); also `event.publish` moments, retained history ([`zeitgeist_client/history.py`](../../../../src/specify_cli/zeitgeist_client/history.py)), authored-message tools and `live_work`. The client resolves capabilities and admission ([`resolution.py`](../../../../src/specify_cli/zeitgeist_client/resolution.py), 186-237), then opens the relay channel ([`transport.py`](../../../../src/specify_cli/zeitgeist_client/transport.py), 157). | Mark each surface kept or retired; say whether lane moments are NOW signals; switch only once a released CLI speaks the new transport. |
| EC-5 | HIGH | The charter recognizes two contract packages and one contract pointer. Adding packages or splitting the CLI↔SaaS contract needs a HiC amendment. | Events and tracker packages only ([`charter.md`](../../../../.kittify/charter/charter.md), 312, 320); one contract file (529-530). Moment vocabulary: `spec_kitty_events/zeitgeist_attrs.py:396`. ADR [2026-09-06-1](../../../adr/3.x/2026-09-06-1-convergence-retirement-and-client-repo-inversion.md) (31) names `spec-kitty/zeitgeist` as authority. | One owner per schema. A change of owner needs a charter amendment, a re-pointed contract and a superseding ADR. |
| EC-6 | HIGH | Shared packages release on SemVer ranges, not in lockstep with the CLI. A target design must respect this or amend it through the HiC. | "rather than forcing every sibling package to release in lockstep" ([`charter.md`](../../../../.kittify/charter/charter.md), 318); ADR [2026-04-26-1](../../../adr/3.x/2026-04-26-1-contract-pinning-resolved-version.md) (Accepted). Installed CLIs cannot be forced to upgrade. | Declare a compatibility window (for example N/N-1) with consumer-contract tests. |
| EC-7 | MEDIUM | The engine does not emit one envelope, so a single-envelope mapping is lossy and fixture replay can pass while the engine emits something else. | Package `Event` (`spec_kitty_events/models.py:59-146`) vs the local, exempt decision envelope ([`decisions/emit.py`](../../../../src/specify_cli/decisions/emit.py), 233-238; #1198). | Publish a field map; replay real `status.events.jsonl` from the pinned CLI in CI. |
| EC-8 | MEDIUM ↓ | `orchestrator-api` lacks verbs any IDE or cockpit client would need. | No `next`, charter or pack verbs; a client-side pack manager would bypass `charter pack apply`. #645 has "no contract … yet" ([`api-dashboard-domain-plan.md`](../../../plans/domains/api-dashboard-domain-plan.md), 180-181). | List the needed verbs; route pack install through the engine. Downgraded: no hosted flow depends on such a client. |
| EC-9 | MEDIUM | Runtime `decision_required` inputs are a second decision channel that no external register classifies. | `DecisionInputRequested/Answered` ([`events/runtime_moments.py`](../../../../src/specify_cli/events/runtime_moments.py), 194-197), `answer-decision`, `decisions.events.jsonl`. | State whether they count as decisions. |

### CL — target-architecture assumptions vs code

| ID | Sev | Finding | Evidence | Recommendation |
|---|---|---|---|---|
| CL-1 | LOW | CLI session storage is an encrypted file per ADR 2026-04-19-1; documents describing OS keychain storage are out of date. | ADR [2026-04-19-1](../../../adr/3.x/2026-04-19-1-cli-auth-uses-encrypted-file-only-session-storage.md) (Accepted). | Correct such documents. |
| CL-2 | MEDIUM | `decision verify` must stay distinct from any signature verification. | It is a sentinel-marker lint with no cryptography ([`decisions/verify.py`](../../../../src/specify_cli/decisions/verify.py), 1-13); one verb would carry two trust models. | Propose a separate record-verification verb, labelled `PROPOSED`. |
| CL-3 | MEDIUM | Widen-to-Slack ships today, including a local resolve. | `DecisionPointWidened` with `SLACK` (`decisionpoint.py:260-280`); "resolve locally right now" ([`charter/_widen.py`](../../../../src/specify_cli/cli/commands/charter/_widen.py), 128); GA blockers #3178, #2941 ([`4-0-0-milestone-roadmap.md`](../../../plans/4-0-0-milestone-roadmap.md), 154-157). | Hosted decision routing must start from this behaviour; settle the local resolve before GA. |
| CL-4 | LOW | Descriptions of today's Zeitgeist understate what ships. | Per-actor capability JWTs are already minted ([`zeitgeist_client/credentials.py`](../../../../src/specify_cli/zeitgeist_client/credentials.py), 43-50). | Describe the mint as shipped. |

### RM — roadmap

| ID | Sev | Finding | Evidence | Recommendation |
|---|---|---|---|---|
| RM-1 | HIGH | No spec-kitty plan or tracker item covers the engine work in EC-1 to EC-3. | `docs/plans/`, [`launch-readiness-future.md`](../../../architecture/launch-readiness-future.md) and [`changelog/4.0.0.md`](../../../changelog/4.0.0.md) say nothing of origin surfaces, record signing, decision owners or cross-mission `blocks`. | Open the epic (section 5, tracker item 1). |

### DA — docs, language and authority

| ID | Sev | Finding | Evidence | Recommendation |
|---|---|---|---|---|
| DA-1 | HIGH | Mission identity is the ULID; the target architecture assumes repository plus slug. | ADR [2026-04-09-1](../../../adr/3.x/2026-04-09-1-mission-identity-uses-ulid-not-sequential-prefix.md) (Accepted); engine payloads already carry `mission_id` ([`decisions/emit.py`](../../../../src/specify_cli/decisions/emit.py), 216-221). | Any external record format must carry the ULID before its first version is frozen; the slug is display only. |
| DA-2 | HIGH | `Accepted` spec-kitty ADRs are binding; the target architecture assumes repository ADRs admitted after its baseline become candidates. | "canonical architectural decisions" ([`charter.md`](../../../../.kittify/charter/charter.md), 616); "`Accepted` means … current policy" ([`adr/3.x/index.md`](../../../adr/3.x/index.md), 63). | Repo ADRs keep repo authority; signature or import status describes provenance only. |
| DA-3 | HIGH | External decisions that change the engine have no ratification path in spec-kitty. | A new policy file under `.kittify/charter/` is unknown to [`governance-files.md`](../../../context/governance-files.md) (32) and conflicts with ADR [2026-07-18-1](../../../adr/3.x/2026-07-18-1-charter-yaml-authoring-authority-and-extractor-retirement.md) (`charter.yaml` is the single structured charter). No 3.x ADR decides the Decision Moment ledger's design. | Treat such decisions as proposals; ratify each as a spec-kitty 3.x ADR or an events change. |
| DA-4 | MEDIUM ↓ | "Decision" has several senses, and "Decision Moment" has no glossary entry. | The next-loop decision ([`orchestration.md`](../../../context/orchestration.md), 282); the "Decision Moment ledger" ([`agent-subcommands.md`](../../../api/agent-subcommands.md), 430). | Add Decision Moment; call the next-loop sense "Runtime Decision". Downgraded: the senses separate once named. |
| DA-5 | MEDIUM | Today's presence vocabulary is not documented as a whole. | Moment, Relay and Capability ([`team-kitty.md`](../../../context/team-kitty.md), 62-66); "Presence" also names ADR [2026-06-07-2](../../../adr/3.x/2026-06-07-2-session-presence-multi-harness-architecture.md) (harness orientation). | Document today's vocabulary in `team-kitty.md`, with room for a today → target map. |
| DA-6 | MEDIUM | The "sync is a dead word" rule is too broad. | [`team-kitty.md`](../../../context/team-kitty.md) (53) and [`CLAUDE.md`](../../../../CLAUDE.md) (65), while "sync" legitimately names git mirror fetch and tracker refresh. | Scope it to "the retired CLI→SaaS sync transport". |
| DA-7 | MEDIUM | The ADR index under-documents status values. | It lists Accepted, Superseded and Deprecated; ADR files also use `Proposed`. | Document `Proposed`; map external statuses onto the spec-kitty set. |
| DA-8 | MEDIUM | The glossary precedence rule would let external planning decisions override engine terms. | [`glossary-conventions.md`](../../../context/glossary-conventions.md) (21) ranks planning ADRs above the glossary. | Planning docs win only for the contexts they own. |
| DA-9 | MEDIUM | Repo admission cardinality conflicts inside spec-kitty. | "One team per repo per provider" ([`team-kitty.md`](../../../context/team-kitty.md), 67) vs "can appear in multiple teams" (ADR [2026-04-21-1](../../../adr/3.x/2026-04-21-1-private-teamspace-and-repository-sharing-boundary.md), 86). | Check the hosted service's constraint (not read here), then fix the wrong doc. |

### SK — spec-kitty staleness (fix in this repo)

| ID | Sev | Finding | Evidence | Recommendation |
|---|---|---|---|---|
| SK-1 | HIGH | The living C4 L1 still describes hosted sync; no living C4 view shows Team Kitty or Zeitgeist; 2.x pages describing the deleted sync subsystem are still `active`. | L1 [`diagrams/01_context/README.md`](../../../architecture/diagrams/01_context/README.md) (47, 56-57); L2 [`diagrams/02_containers/README.md`](../../../architecture/diagrams/02_containers/README.md) shows only "External Tracker / SaaS" (71). Active 2.x pages: [`02_containers/README.md`](https://github.com/spec-kitty/spec-kitty/blob/main/docs/architecture/diagrams/02_containers/README.md) (78), [`runtime-execution-domain.md`](https://github.com/spec-kitty/spec-kitty/blob/main/docs/architecture/diagrams/02_containers/runtime-execution-domain.md) (28, 86), [`03_components/README.md`](https://github.com/spec-kitty/spec-kitty/blob/main/docs/architecture/diagrams/03_components/README.md) (143). | Redraw living L1–L3 with the engine, `orchestrator-api`, the Zeitgeist and SaaS clients, the moment fan-out, the relay, Team Kitty and the git host. Mark the 2.x pages superseded. |
| SK-2 | MEDIUM | [`launch-readiness-future.md`](../../../architecture/launch-readiness-future.md) is stale. | "Coming Soon" (2-3); "Sync runs by default" (44); recommends `spec-kitty sync doctor` (77), which no longer exists. | Re-banner as launched; drop the sync remediation. |
| SK-3 | MEDIUM | Charter versioning text is stale. | "3.x … sync protocol" ([`charter.md`](../../../../.kittify/charter/charter.md), 375, 385); "sync payloads" (530). | HiC amendment. |
| SK-4 | MEDIUM | Planning-doc drift. | [`changelog/4.0.0.md`](../../../changelog/4.0.0.md) (43, 59); the milestone roadmap still says rc3; #645 is "3.3.x" in [`api-dashboard-domain-plan.md`](../../../plans/domains/api-dashboard-domain-plan.md) (198); [`changelog/3.3.x.md`](../../../changelog/3.3.x.md) is still active. | Addendum, re-milestone, supersede. |
| SK-5 | MEDIUM | Engine defects and drift. | Hard-coded `_ACTOR_TYPE` ([`decisions/emit.py`](../../../../src/specify_cli/decisions/emit.py), 67); dead events 5.x/6.x gates ([`status/emit.py`](../../../../src/specify_cli/status/emit.py), 95-120); [`events/adapter.py`](../../../../src/specify_cli/events/adapter.py) (50-80) maps fields absent from events 10.x; a stale `relay_url` comment ([`transport.py`](../../../../src/specify_cli/zeitgeist_client/transport.py), 195). | Tracker items. |
| SK-6 | LOW | Small doc fixes. | [`team-kitty.md`](../../../context/team-kitty.md) (27) understates the SaaS surface; [`CLAUDE.md`](../../../../CLAUDE.md) heading (65) and banner (678); deprecated [`team-kitty-saas.md`](../../../architecture/team-kitty-saas.md); [`governance.md`](../../../context/governance.md) (34-35) omits 3.x; [`dossier.md`](../../../context/dossier.md) (29, 172) uses the legacy term; "Actor" is undefined. | Section 5, doc fixes. |

---

## 3. Term collisions that matter

| Term | spec-kitty sense | External documents should |
|---|---|---|
| Mission identity | ULID `mission_id`; slug for display | use the ULID (DA-1) |
| Decision | next-loop choice; Decision Moment in the ledger | say "Runtime Decision" or "Decision Moment" (DA-4) |
| Moment · Relay · Capability | `event.publish` moment; per-team relay; per-actor capability | map new terms onto these (DA-5) |
| Presence | liveness samples; also the Session Presence harness ADR | qualify which |
| Sync | the retired CLI→SaaS transport | say "mirror fetch" or "tracker refresh" (DA-6) |
| Primary / default branch | **primary surface** = repo-root checkout; **Primary Branch** = protected branch; commits land on the mission **Target Ref** (ADR 2026-06-24-2) | name the one a new branch writer targets (EC-3) |
| Routing | profile routing in `spec-kitty dispatch` | qualify decision routing separately |
| ADR | dated 3.x ADRs, authoritative | use a citation form that cannot collide |
| Charter | `charter.yaml` is authoritative | not place policy in a parallel file (DA-3) |

---

## 4. Authority split, engine side

| Topic | Canonical home |
|---|---|
| Engine terms (Mission, WP, lane, Decision Moment, charter files) | spec-kitty `docs/context/` |
| Engine-side decisions (verbs, `.kittify/`, gates, branch writers) | spec-kitty `docs/adr/3.x/`; external decisions are proposals until ratified here |
| Event, envelope and moment schemas | `spec-kitty-events` |
| CLI↔SaaS route contract | the single charter-named contract, until the charter is amended |
| Team Kitty client-side behaviour | `docs/context/team-kitty.md` |
| Cross-repo term precedence | `docs/context/glossary-conventions.md`, amended per DA-8 |

Rulings on the target-architecture side are tracked privately.

---

## 5. Recommended next steps

### spec-kitty tracker items

1. **Epic "Decision records in the engine"** (RM-1): ADR-surface `decision open`; classification and decision-owner fields; `blocks` and cross-mission dependencies; record canonicalisation and commit, with a topology ADR; a record-verification verb (CL-2); an override verb; a decision-policy reader whose home a spec-kitty ADR decides (DA-3); repo-level decisions.
2. Spike an inbound decision path (EC-1).
3. `spec-kitty-events`: versioned or tolerant DecisionPoint types, and the envelope field map (EC-2, EC-7).
4. HiC charter amendment: contract packages and pointer (EC-5); versioning text (SK-3).
5. #645: name IDE and cockpit clients as consumers and list their verbs (EC-8).
6. Engine defects (SK-5).
7. Settle widen-to-Slack's local resolve before GA (CL-3); classify runtime `decision_required` inputs (EC-9).

### spec-kitty doc fixes (safe now)

1. Redraw C4 L1–L3 (SK-1) and re-banner `launch-readiness-future.md` (SK-2).
2. Glossary (DA-4 to DA-6, SK-6): add Decision Moment and Actor; qualify Runtime Decision; document today's presence vocabulary; scope the dead word "sync"; add 3.x scopes; say "mission directory" in `dossier.md`.
3. Narrow the precedence rule; document `Proposed`; state that `Accepted` means repo policy (DA-8, DA-7, DA-2).
4. Planning-doc drift (SK-4).
5. `team-kitty.md` SaaS-surface line and admission cardinality; delete `team-kitty-saas.md`; fix the `CLAUDE.md` heading and banner; correct keychain wording (SK-6, DA-9, CL-1).

---

## 6. Method

Each lens reviewed read-only under one governed Op. A synthesis step grouped findings raised by two or more lenses; `architect-alphonso` consolidated and adjudicated them. The consolidation applied the charter directives on architectural integrity (001), decision documentation (003), specification fidelity (010), conceptual alignment (031/032), canonical sources (044) and version governance (048), plus C4 techniques and the Terminology Canon.

**Verification.** The squad read `baef0af5`; every code citation was re-read at `e2dcf69c` (between the two, `src/` changed only in `status/aggregate.py` and `charter/activation/context_contract.py`). CLI behaviour was checked by running the CLI, and event-schema claims against the installed `spec_kitty_events` 10.4.0. The live C4 L1 is `docs/architecture/diagrams/01_context/`; `docs/architecture/01_context/` is a frozen 2.x snapshot.

**Hypothesis.** The hosted service's admission constraint (DA-9) was not read.

**Out of scope.** The soundness of the target architecture itself (security design, capacity, cost); the internals of the hosted service and the Zeitgeist relay; implementing any fix — each change goes through its own mission, ADR or tracker item.
