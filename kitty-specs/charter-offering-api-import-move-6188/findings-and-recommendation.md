# #6188 — mission findings & recommendation (grounding capstone)

> SEMI-AUTO run, paused at an escalation point for an operator routing decision (a valid
> semi-auto exit state). Consolidates `grounding-note.md` + `scope-c-public-contract-delta.md`
> with the decisive findings from the C-facades-only deep dive. No `api.py` / gate / source
> repoint has been made. Date 2026-10-13. Branch `issue-6188-charter-offering-api-import-move`.

## TL;DR

The literal #6188 target ("`specify_cli` imports a charter internal only via
`charter.offering.api`") is **incompatible with the repo's gate-enforced facade architecture**,
and the genuine `specify_cli → charter.offering` decoupling it names is **already substantially
done**. The remaining offering reaches are small, in-body, and **owned by other tickets**. The
larger C-facades-only legs the operator selected are **#6099 extraction work** — the facade→api
leg overturns a deliberate curation, and the **activation→api leg is architecturally unsound as
stated** and blocked on the still-unsettled #3101 boundary. Recommendation: resolve #3101 first;
route the api-widening into #6099 (with its required ADR); treat #6188's specify_cli decoupling
as complete-modulo-#3179/#2173/#3593.

## The four decisive facts

1. **`charter.offering.api` is a facade/wheel door, not a `specify_cli` door (C-001).** The
   sanctioned seam is `specify_cli/runtime → charter.* facade → charter.offering.*`, enforced
   green today by `test_runtime_charter_doctrine_boundary.py` (module-level offering baseline
   EMPTY; 11 ticketed lazy pairs left). So "route specify_cli onto `charter.offering.api`"
   contradicts the architecture and the C-001 invariant.

2. **The residual `specify_cli`/`runtime` offering reaches are all owned elsewhere.** The 11
   lazy baseline pairs map to: `charter.offering.service` (sole-door, #3179), `drg.override_policy`
   + `drg.migration.hand_authored_overlay` ("TICKETED-BASELINE", #3179), `agent_profiles.
   operating_procedures` (op-procedures door, #3593), `missions.step_contracts` /
   `missions.step_projection` in `src/runtime` (#2173), and `codex.py`'s `charter.offering.__file__`
   metadata read (FR-006 exempt). **Five are trivially facade-ready** (ArtifactKind, built_in_dir,
   load_built_in_graph, OrgDRGFragment, the runtime step symbols already have facade doors), but
   repointing runtime (non-TYPE_CHECKING) imports onto facades risks the **#4188 mypy-strict `Any`
   leak** (the facade re-export types as `Any` under `follow_imports=skip`; `mission_step_contracts/
   executor.py` documents keeping a concrete TYPE_CHECKING import precisely to avoid this). The
   other reaches are the genuinely-hard doorless/sole-door cases those tickets own.

3. **The facade→api leg of C-facades-only overturns a deliberate curation and is pure churn
   pre-split.** The DISPOSITION manifest classifies 21 charter.offering modules **FACADE-ONLY**
   with the explicit rationale *"prefer a clean door over widening the api"*; the negative guard
   `test_charter_offering_public_surface.py` asserts their absence from `api`. Promoting ~110
   symbols to PUBLIC + rewriting DISPOSITION is a governance change that belongs to epic #6099
   (which *requires* a dedicated extraction ADR), and buys nothing until the physical split.

4. **The activation→api leg is architecturally unsound as stated.** `charter.activation.*`
   reaches `charter.offering` internals in **191 import lines**, including **private symbols**
   (`_NON_AUGMENTATION_ELIGIBLE_KINDS`, `BaseArtifactRepository._load`, `_apply_overlay_layer`,
   `CHARTER_ACTIVATABLE_KINDS`, …) and **modules absent from DISPOSITION** (`directives.models`,
   `directives.repository`, `discovery_recursion`, `drg.migration.id_normalizer`,
   `drg.migration.calibrator`, `drg.migration.extractor`, `glossary_packs.models`). You cannot
   route private intra-package symbols through a curated PUBLIC api without exporting privates
   (absurd) or a large redesign. This is **intra-`src/charter/` coupling**, which is only a
   cross-package boundary IF the extraction unit is `charter.offering` *alone* — the exact
   question #3101 leaves **unsettled**. If the extracted wheel is the whole `src/charter/`
   (activation + facades included), activation↔offering is internal and needs **no** api routing.

## Additional finding: the external-consumer boundary is wider than specify_cli

`src/glossary` imports `charter.offering.drg.models.DRGGraph` directly — and
`test_runtime_charter_doctrine_boundary.py` scans only `src/specify_cli` + `src/runtime`, so
**the glossary→offering reach is unguarded**. Any true "external consumers route through the
public surface" extraction precondition must add `glossary` (and confirm `mission_runtime`,
currently clean) to the boundary, not just specify_cli.

## Recommendation (for operator routing)

1. **Settle #3101 first** (extraction unit = whole `src/charter/` vs `charter.offering` subtree).
   This single decision determines whether activation/facades are *inside* the unit (no api
   routing needed — recommended, given fact #4) or *external* consumers (api routing needed).
   Everything downstream depends on it.
2. **#6188 (specify_cli decoupling): treat as complete-modulo-tickets.** The clean part is done;
   the residual 11 lazy pairs are owned by #3179 / #2173 / #3593. Recommend #6188 `Refs` those and
   is reframed/closed as "specify_cli already reaches charter only through the facade seam; residual
   offering reaches tracked by #3179/#2173/#3593", rather than re-doing their work here. (Optionally,
   land the ~5 trivially-facade-ready drains as a small, low-risk slice — guarding against the #4188
   `Any` leak — to shrink the lazy baseline 11→~6; offered, not forced.)
3. **Route the api-widening into #6099** with its required extraction ADR; it is not a
   specify_cli import move and overturns the FACADE-ONLY curation.
4. **Do not attempt activation→api** until (1) resolves; as stated it needs private-symbol
   exports and is unsound.

Nothing outward (push / PR / api edit) has been taken, pending this routing decision.
