---
title: Mission Seed M4 - Deliver Loaded Doctrine to the Agent
description: 'Specify-intake seed for the mission closing #3489/#3176/#3389: fix silent delivery-table and render no-ops so loaded doctrine reaches the dispatched agent.'
doc_status: active
updated: '2026-08-19T00:00:00Z'
kind: Planning
---

# Mission Seed — M4: Deliver Loaded Doctrine to the Dispatched Agent

> **Status:** seed. Feed to `/spec-kitty.specify` in a fresh session.
> **Part of:** charter-resolution program (see `../program-brief.md`).
> **Closes:** #3489, #3176, #3389, and the render half of #3488.
> **Effort:** M. **Depends on:** the render/builder parts are independent; the **org-authored** reach for glossary/op-proc acceptance is **gated on M2** (the DRG bridge). Land M4's built-in/project reach first if M2 is not yet in.

## Problem

Two delivery pipelines carry doctrine to a dispatched agent — the **action-doctrine bundle** and the **profile channel** — and each has silent no-ops. Everything validates clean and warns nothing, yet content never arrives:

- **#3489** — `GLOSSARY_PACK` has `slot=None` in the delivery table (one of two `None` rows lacking the module's required "stated reason"), and no profile-channel renderer. Glossary packs are diagnostically present but structurally unreachable in every config.
- **#3488 (render half)** — styleguide/toolguide reference channels pass `body_fn=None`, so they always emit a fetch pointer, never a budgeted inline body; and procedure step `description` is dead code (`title` is required, so `title or description` never reaches `description` — measured 63% of step content undeliverable).
- **#3176** — `build_activation_aware_doctrine_service` derives its project root from three fixed candidates, none of which is `.kittify/agent_profiles`, so a project-overlay profile is silently dropped (three named projection tests are red-carved-out C-002 today).
- **#3389** — `charter context --json` omits a `procedures[]` array the text render ships; `procedure` is folded only into the flat `references[]`.

## Fix approach (three groupings)

- **WP-A — delivery-table/render family:** give `GLOSSARY_PACK` a real slot + term-list render row (or ratify document-only) and **restore the "stated reason" for every remaining `None` row** (close the class, incl. `ANTI_PATTERN`'s twin); render step `description`; decide styleguide/toolguide inline-body-vs-pointer.
- **WP-B — builder overlay seam (#3176):** thread an optional `agent_profile_overlay_dir` param through `_build_activation_aware_doctrine_service` → `_build_doctrine_service`, default `None` (byte-identical when unset); migrate `default_profile_repository` onto it; delete the composite-key carve-out. **Preserve the single-wrapper-body invariant.**
- **WP-C — `procedures[]` in context JSON (#3389):** promote `procedure` from `extra_delivered` to a fifth typed array; **versioned-contract bump** (increment `context_schema_version` + ledger deliberately).

## Open operator decisions (resolve at this mission's discovery)

1. **Glossary delivery:** real delivery slot vs document-only exclusion? If delivered — action-bundle slot, profile channel, or both? inline terms vs surface-list + fetch pointer (token budget)?
2. **styleguide/toolguide:** grant a budgeted inline body, or ratify pointer-only and make it discoverable in schema/docs? (Was pointer-only *by design* for the NFR-001 token budget.)
3. **#3389 asset asymmetry:** after promoting `procedures[]`, is `asset` deliberately reference-only forever, or a follow-up sixth typed array? State it in the contract.
4. **Org acceptance gating:** require M2 landed for glossary/op-proc *org* acceptance, or scope M4's first pass to built-in/project reach with an org follow-up?

## Scope

- **In:** the delivery-table/render no-ops, the builder overlay seam, the context-JSON `procedures[]` parity.
- **Out:** the operating-procedures *edge wiring* (that is M3); cascade traversal completeness (M5).

## Key seams

- `charter/context_renderers/delivery_table.py` (`_ACTION_BUNDLE_DELIVERY_BY_KIND`, `_classify_artifact_urns`)
- `charter/context_renderers/profile_sections.py` (`format_inline_named_body`, `render_profile_styleguides/toolguides`)
- `charter/context_renderers/bootstrap_text.py` (`_ACTION_RENDER_ROWS`); `charter/action_doctrine_bundle.py` (`_ActionDoctrineBundle`)
- `charter/doctrine_service_builder.py` (`_build_doctrine_service`, `_build_activation_aware_doctrine_service`); `charter/_doctrine_paths.py`; `specify_cli/tool_surface/profiles/projection.py`
- `charter/progressive_disclosure.py` (`_ARRAY_BY_KIND`); `charter/context.py` (~L487-494)

## Risk

Widening styleguide/toolguide/glossary bodies can blow the NFR-001 token budget (the reason they were pointer-only). `procedures[]` is a versioned-contract change — bump deliberately. Totality tests redden until slot + render row land together (that is the guard working).
