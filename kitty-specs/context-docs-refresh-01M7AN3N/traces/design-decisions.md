# Design decisions

- **[2026-11-13][discover] Reader is named in `audience:` frontmatter.** The staleness audit and `scripts/docs/audience_resolver.py` read the reader from `audience: [{profile, guidance_text}]`, so that is how each page names its reader; no new convention is introduced.
- **[2026-11-13][discover] No profile added or removed.** Profile changes need an operator ruling (#7522); proposals go to the operator.
- **[2026-11-13][design] Persona pages keep the canonical template.** Goals, vocabulary and questions are checked inside the existing sections rather than adding new ones to ten copies; a template change is proposed to the operator instead (plan.md Decision 3).
- **[2026-11-13][design] Profile pages are read by maintainers and writing agents.** The 13 audience pages name `internal/maintainer` and `internal/ai-collaboration-agent` (plan.md Decision 2).
- **[2026-11-13][implement] Landing set left unchanged.** The coordinator asked WP02 to drain 'the landing set as the gate's hint requires'; the gate's hint and the operator brief only touch the burn-down and the baseline, and the landing set is a frozen record (C-004), so it was not edited.
- **[2026-11-13][design] Mission 081 names stay documented with their code names beside them.** `identity-fields.md` keeps every 081 heading (identity.md links two of its anchors) and adds a "Code today" row per entry, because the code still stores `project.uuid` / `project.slug` (W1, W2).
- **[2026-11-13][design] Diagrams carry metadata and a prose equivalent.** Both new Mermaid diagrams carry `%% title:` / `%% description:` (operator instruction) plus Mermaid `accTitle` / `accDescr`, and a sentence that says the same in words (P5).
