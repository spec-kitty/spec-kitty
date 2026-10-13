# Mission spec — charter module entry-point seams (#6188)

> Governed mission, SEMI-AUTO. Grounded by `grounding-note.md`,
> `scope-c-public-contract-delta.md`, `findings-and-recommendation.md` (committed first).
> Operator steer (2026-10-13): "hide the charter internals behind a module entry-point seam
> so we can extract/rewrite the module internals (e.g. to a Java-based system) without the
> rest of the code being impacted. Keep the activation and offering surfaces split."

## Purpose / intent

Make the charter layer's two sub-surfaces — **offering** and **activation** — each reachable
by the rest of the codebase only through a **single module entry-point seam**, so the
internals behind each seam can be rewritten, re-homed, or extracted to a separate (even
non-Python) service without impacting any consumer. This is the GA-gating in-tree precondition
for the charter extraction (epic #6099); it is the import-decoupling only, not the extraction.

## Acceptance (this mission)

- **Two seams, kept split** (ADR `2026-10-06-2` §1): offering → `charter.offering.api` + the
  `charter.*` offering facades; activation → new `charter.activation.api`. Neither seam fronts
  the other layer's symbols.
- **Offering seam enforced for every external consumer.** The boundary gate
  `test_runtime_charter_doctrine_boundary.py` scans `specify_cli`, `runtime`, **`glossary`**,
  **`mission_runtime`** (was only the first two — `glossary` reached `charter.offering.drg.models`
  directly, unguarded). `glossary` is repointed onto the `charter.drg` facade. Gate green.
- **Activation seam established + enforced (shrink-only).** `charter.activation.api` exists as
  the curated identity-re-export entry point (first tranche: the mission-type-key access
  cluster). A new boundary gate `test_runtime_charter_activation_boundary.py` forbids external
  consumers from importing `charter.activation` internals except via the seam, with the 236
  pre-existing reaches frozen as a shrink-only baseline (new reaches FAIL; stale rows FAIL, so the ratchet is shrink-only)
  governed through `_baselines.yaml` (owner: epic #6099).
- **First drain tranche landed:** the 11 `charter.activation.mission_type_key` consumers are
  repointed onto `charter.activation.api`.
- `make test-fast` + owning test dirs + the named gate files green; ruff/format/mypy clean;
  complexity ≤ 15.

## Non-goals (this mission)

- The repository extraction itself (#6099) and any charter-behaviour / offering-internal change.
- Draining the remaining 236 activation reaches (gate-driven follow-on, owner #6099) and the
  ticketed offering residuals (#3179/#2173/#3593).
- Widening `charter.offering.api` (the charter-blessed design prefers facade doors over api
  widening; see `scope-c-public-contract-delta.md`). The offering seam already exists; this
  mission only hardens its enforcement reach and splits out the activation seam.

## Why this shape (reconciliation with #6188's literal text)

The issue's literal "route specify_cli onto `charter.offering.api`" is incompatible with the
gate-enforced facade architecture (`charter.offering.api` is a facade/wheel door, not a
`specify_cli` door — C-001) and cannot host the activation surface. The operator steer resolves
it: give **each** layer its own entry-point seam, kept split. The dominant coupling is
`→ charter.activation` internals (236 `(file, module)` pairs across 81 files), so the activation seam is the load-bearing new
work; the offering seam already exists and only needed its enforcement widened to all consumers.
Full reconciliation in the three committed grounding docs.
