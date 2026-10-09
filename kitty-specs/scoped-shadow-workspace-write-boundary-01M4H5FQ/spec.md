# Spec — Scoped shadow workspaces: write-boundary design spike (#3129 / #2334)

> Mission type: **research** (design + analysis spike). Deliverable is **decision
> material**, not a code rewrite. The structural call is the operator's; this mission
> escalates it. See `research.md` for the decision record.

## Intent

Put a shape on the shared root behind #3129's class of worktree/write-path bugs — *a
command's write target derived from ambient location rather than from the Mission's
declaration* — and answer the one question #3129 asks the operator: is a
scoped-shadow-workspace-handle boundary **(A)** a replacement for, **(B)** a layer onto,
or **(C)** incompatible with the current coordination/primary partition — and, if
incompatible, what is reason X. Produce a parallel scoping verdict for #2334 (the one
still-open concrete instance): fix-now-and-bounded vs gated on the #3129 decision.

## Scope

In scope: as-built write-boundary topology mapping (placement seam, ambient entry points,
lane allocator, #3128 guard); pattern extraction from the 13 merged point-fixes; a
≥3-option analysis with a recommendation marked as the operator's call; a #2334 scoping
verdict with a concrete bounded fix proposal (template eviction + regression tests) *if*
decoupled; risks and a sequencing recommendation.

Out of scope (hard): refactoring or rewriting any write-path seam; adopting ThickTicket's
ticket model or QA gate; any structural change before the operator chooses the #3129
direction; any PR.

## Acceptance

- [x] As-built topology mapped with real `file:line` citations.
- [x] 13 merged fixes pattern-extracted into recurring shapes with supply-not-exhausting evidence.
- [x] ≥3 #3129 options, each weighed vs the partition / migration cost / blast radius, with a recommendation.
- [x] #2334 verdict: fix-now (bounded, with concrete fix + tests) vs gated, with rationale.
- [x] Risks + sequencing recommendation.
- [ ] **Escalation gate:** operator chooses #3129 direction and rules on the #2334 go/no-go. (Open — awaiting operator.)
