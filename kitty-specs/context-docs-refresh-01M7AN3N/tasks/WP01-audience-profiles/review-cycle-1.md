---
affected_files: []
cycle_number: 1
mission_slug: context-docs-refresh-01M7AN3N
reproduction_command:
reviewed_at: '2026-11-13T15:09:10Z'
reviewer_agent: claude-reviewer::reviewer-renata
wp_id: WP01
---

**Issue 1 (medium, FR-004): the audience hub's description overstates a fact.**
`docs/context/audience/README.md:3` says the profiles are the ones "every Spec Kitty doc page names in its audience frontmatter". That is not true today. DIRECTIVE_042 and the `common-docs` styleguide (`packs/built-in/styleguides/common-docs.styleguide.yaml:13`) require `audience:` only on touched pages, and deliberately keep it out of `frontmatter_required_fields`. `audience_resolver --strict` examines 307 values on this branch, while the site validates 680 pages, many with no `audience:`; the #7522 audit table lists most `context/` pages as "Reader: none". Fix: describe it as the catalog a page picks its reader from (for example "the ten reader profiles a page names in its `audience:` frontmatter, and how to choose one").

**Issue 2 (medium, FR-004): wrong source for the "choose from the catalog" rule.**
`docs/context/audience/README.md:39-41` says to choose from this catalog "as the `writing-audience-catalog` tactic and directive 047 ask". The tactic (`packs/built-in/tactics/communication/writing-audience-catalog.tactic.yaml`) points at a different library: the pack's `assets/audiences/` personas (software engineer, automation agent, and so on). It never mentions `docs/context/audience/`. DIRECTIVE_047 (through DIRECTIVE_042 and the `common-docs` styleguide) is what points docs pages at `docs/context/audience/`. Fix: cite DIRECTIVE_047 and DIRECTIVE_042 (or `common-docs`) for this catalog; drop the tactic, or say what it actually covers.

**Issue 3 (low): the internal hub contradicts itself.**
`docs/context/audience/internal/README.md:22-25` says "The three `system` and `llm` personas are readers too", then says two of them (the CLI runtime and the codebase) are actors a page must match, not readers. The same table and your own P2 flag ("they model system actors ..., not readers") say the same thing. Fix: say the agent persona is a reader, and the two `system` personas are actors that a page is rarely written for.

**Issue 4 (low, overloaded term): "lanes" in the tech-lead profile.**
`docs/context/audience/external/tech-lead-evaluator.md:47` says "how a work package moves through its lanes to review and approval". For an external evaluator, "lanes" also means execution lanes, the lane branches and worktrees that the same sentence refers to. Name the sense: "through its status lanes (planned, ..., approved, done)" or "through its lifecycle states".

**Issue 5 (low, overstatement): "changed only by appended amendments".**
`external/architect-evaluator.md:48` and `internal/system-architect.md:50` say ADRs are changed only by appended amendments. A superseded ADR also gets its `status`/Status banner edited (for example `docs/adr/4.x/2026-10-12-2-...md:4,11,14`), and `docs/adr/README.md` allows renaming or deleting an ADR file. Fix: "amended by appended, dated amendments rather than rewritten; supersession is recorded on the record", or simply drop the parenthetical.

Advisory, not required for approval:
- `README.md:38` "Name one primary reader; add a second entry only when the page serves two readers": no doctrine states this rule. It is reasonable guidance, and the 13 pages here are consistent with it because each serves two readers. Keep it if you want; the commit message calls it "the one-primary-reader rule", so make sure no one later reads it as a sourced rule.
- `operator-flags.md` O2: DIRECTIVE_042 and the `common-docs` styleguide carry the same retired path form as DIRECTIVE_047. Name all three in the upstream flag.

Verified and fine: all 8 corrections-log rows hold against the source (version 4.0.0rc9; `spec-kitty next --help`; `spec-kitty tracker providers` beads/fp plus 5 removed; `charter list|activate|deactivate|context --action`; the `identity.md#human-in-charge-hic` anchor; the Intent Summary in the specify step prompt; the spec template sections; the `index.md` to `README.md` rename `6a5a6d7abb` (#6939); 0 of 307 `audience:` values name runtime or codebase). No anchor was renamed or removed. Scope stays inside the owned files plus the mission logs. The commits are signed. All gates are green.
