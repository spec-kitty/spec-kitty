# Charter

The **charter** package is the governance bridge between the Human in Charge
(HiC) and the charter offering, the catalog of Charter Pack artifacts. It captures project-level governance
intent, compiles it into actionable bundles, and injects action-scoped context
at every execution boundary.

## What it does

1. **Interview** — guides the HiC through structured questions to record
   operating constraints, quality rules, and artifact selections.
2. **Compile** — resolves those selections transitively through the DRG and produces the `.kittify/charter/` output bundle.
3. **Context injection** — at each action boundary (specify / plan / implement /
   review), resolves which governance applies using
   Action Index intersection with project selections.

## Relationship to the charter offering

The activation side *consumes* the offering (`charter.offering`) but the
offering does not depend on it. The offering is a self-contained
catalog of reusable patterns (paradigms, directives, tactics, etc.) that can
ship independently. Charter is the application-layer code that reads from that
catalog and turns selections into project-specific governance.

**Dependency direction:** `charter` (facades, `charter.activation`) -> `charter.offering`. Never the reverse.

Runtime prompt generation under `src/specify_cli/next/` must resolve offering
artifacts through charter facades (`context.py`, `resolver.py`, `catalog.py`,
`scope_router.py`) so project and org governance remains scoped by the charter
trust boundary. There is no exempt subpackage: the charter pack fetch and
scaffold adapters in `src/specify_cli/charter_packs/` reach the pack model and
tooling (`charter.offering.packs`) only through the `charter.packs` and
`charter.drg` facades, and org charter composition lives in
`charter.activation.org_charter`.

## Key entry points

| Entry point | Purpose |
|---|---|
| `interview.py` | `CharterInterview` — the guided Q&A flow |
| `compiler.py` | `compile_charter()` — transitive resolution producing `charter.md` + `references.yaml` |
| `context.py` | `build_charter_context()` — action-scoped governance injection |
| `resolver.py` | `resolve_project_governance()` / `resolve_governance_for_profile()` — profile-aware governance resolution |
| `catalog.py` | `OfferingCatalog` / `resolve_offering_root()` — discovers available offering artifacts |
| `defaults.yaml` | Default interview answers for `--non-interactive` and "accept defaults" paths |

## Architecture references

- Container view: `docs/architecture/diagrams/02_containers/README.md` — "Charter and Governance Engine"
- Component view: `docs/architecture/diagrams/03_components/README.md` — Governance section
- Init flow: `docs/plans/user_journey/init-doctrine-flow.md`
- Governance ADR: `docs/adr/2.x/2026-02-23-1-doctrine-artifact-governance-model.md`
- Glossary: `docs/context/governance.md`
