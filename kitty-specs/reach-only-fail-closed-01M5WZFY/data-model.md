# Data Model: Reach-only membership fails closed (#6454)

No persisted shape changes. The files below are read, never written, by this fix.

| Entity | File | Role | Unreadable means |
|--------|------|------|------------------|
| Synthesis manifest | `.kittify/charter/synthesis-manifest.yaml` | primary membership source (`artifacts[].kind/slug`) | present, but YAML, schema or I/O error |
| Created-artifacts record | `.kittify/charter/synthesized-artifacts.yaml` | fallback membership (`created_<plural>` lists) | present but malformed, or no record file for the kind |
| Legacy tactic record | `.kittify/charter/synthesized-tactics.yaml` | fallback for tactics only (`created_tactics`) | as above |
| Project overlay | `.kittify/charter-packs/**.graph.yaml` | nodes + synthesis-shaped edges | unchanged: degrades to empty (existing behaviour) |

## Invariant

A node of a reach-only kind that is the target of a synthesis-shaped edge is never a root when
its membership cannot be disproven; only an org-required id overrides this.

## Membership states

| Manifest | Record | Membership | Warning |
|----------|--------|------------|---------|
| absent | any | empty | no |
| readable | any | manifest slugs | no |
| unreadable | readable | record ids | yes |
| unreadable | unreadable/absent | every synthesis-edge target | yes |
