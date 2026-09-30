# Charter

The **charter** package is the governance bridge between the Human in Charge
(HiC) and the doctrine knowledge catalog. It captures project-level governance
intent, compiles it into actionable bundles, and injects action-scoped context
at every execution boundary.

## What it does

1. **Interview** — guides the HiC through structured questions to record
   operating constraints, quality rules, and doctrine selections.
2. **Compile** — resolves those selections transitively through the doctrine
   graph and produces the `.kittify/charter/` output bundle.
3. **Context injection** — at each action boundary (specify / plan / implement /
   review), resolves which governance applies using
   Action Index intersection with project selections.

## Relationship to doctrine

Charter *consumes* doctrine but is not part of it. Doctrine is a standalone
catalog of reusable patterns (paradigms, directives, tactics, etc.) that can
ship independently. Charter is the application-layer code that reads from that
catalog and turns selections into project-specific governance.

**Dependency direction:** `charter` -> `doctrine`. Never the reverse.

Runtime prompt generation under `src/specify_cli/next/` must resolve doctrine
through charter facades (`context.py`, `resolver.py`, `catalog.py`,
`scope_router.py`) so project and org governance remains scoped by the charter
trust boundary. CLI org-pack tooling under `src/specify_cli/doctrine/` is the
documented exception: validators and assemblers may import charter.offering artifact
models directly because they validate and package doctrine artifacts as data,
not prompt-runtime governance context.

## Key entry points

| Entry point | Purpose |
|---|---|
| `interview.py` | `CharterInterview` — the guided Q&A flow |
| `compiler.py` | `compile_charter()` — transitive resolution producing `charter.md` + `references.yaml` |
| `context.py` | `build_charter_context()` — action-scoped governance injection |
| `resolver.py` | `resolve_project_governance()` / `resolve_governance_for_profile()` — profile-aware governance resolution |
| `catalog.py` | `DoctrineCatalog` / `resolve_doctrine_root()` — discovers available doctrine artifacts |
| `defaults.yaml` | Default interview answers for `--non-interactive` and "accept defaults" paths |

## Architecture references

- Container view: `docs/architecture/diagrams/02_containers/README.md` — "Charter and Governance Engine"
- Component view: `docs/architecture/diagrams/03_components/README.md` — Governance section
- Init flow: `docs/plans/user_journey/init-doctrine-flow.md`
- Governance ADR: `docs/adr/2.x/2026-02-23-1-doctrine-artifact-governance-model.md`
- Glossary: `docs/context/governance.md`
