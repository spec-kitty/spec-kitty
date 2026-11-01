# Research: action-critical charter sections resolve in the active charter

Mission: `action-critical-sections-resolve-01M6BTST`
Issue: #6968
Grounded on: `origin/main` @ `287a226cfe` (2026-11-01), `spec-kitty` 4.0.0rc8.

## Decisions

### D-001 — The three names are core code, not `packs/built-in` doctrine

Evidence:

- `src/charter/activation/context_renderers/section_bodies.py` defines
  `TERMINOLOGY_CANON`, `CODE_REVIEW_CHECKLIST`, `REGRESSION_VIGILANCE` and
  `ACTION_CRITICAL_SECTIONS = {"implement": [...], "review": [...]}` as literals.
- `grep -rn "code-review-checklist" src/` finds no other producer.
- `packs/built-in` is **not vendored**: `git ls-files packs/built-in` is empty and
  `.gitignore:251` ignores it; `packs/built-in.source.yaml` pins
  `spec-kitty-open-packs` commit `af1c370f3460`, fetched by `make sync-packs`.
  The built-in `implement`/`review` mission-step `prompt.md` files only *name* the
  three headings in prose; they do not drive the `--include section:` output.

Consequence: the defect is fixable in this repository. The pack prose that also
names the headings as project-charter sections is an upstream follow-up in
`spec-kitty-open-packs` (issue to be filed; not editable here).

### D-002 — Fix by filtering the advertised set, not by serving substitute doctrine

The issue's "Expected" asks three things: name only sections that resolve, do not
present a missing section as action-critical, and (only if built-in doctrine
needs the content) serve it from a doctrine artifact.

No built-in artifact carries these three rules; they are project governance that
Spec Kitty's own dogfooding charter authored. So the honest fix is to stop
advertising headings the active charter does not have. Inventing a substitute
pack artifact would add a second source of authority (charter vs doctrine) and a
new content set to maintain — out of scope for a P1 defect fix.

### D-003 — Present-section behaviour is unchanged

For a heading the charter does carry, the renderer keeps emitting the verbatim
body **and** the fetch + when-doing stanza (the recovery path, pinned by the
WP-prompt governance ATDD anchors in
`tests/specify_cli/next/test_wp_prompt_governance_contract.py`). Only the
missing-heading arm changes.

### D-004 — Empty and masked headings count as not resolving

`_extract_section_body` returns `None` when the heading is absent or masked by an
unbalanced fence and `""` when the heading has no body. A heading with no rule
text is not action-critical guidance, so both are treated as "does not resolve"
for advertising. The direct `--include section:<slug>` fetch keeps its existing
honest-degrade placeholder (`_honest_placeholder`) so an explicit fetch never
crashes — that surface is not advertising.

### D-005 — The block header disappears when nothing resolves

`render_critical_section_bodies` already returns `""` for an action with no
configured set. Extending that to "no heading resolves" removes the empty
`Action-Critical Charter Sections (<action>):` header that would otherwise
advertise a block with no content. Callers already skip empty blocks
(`_append_block`), so no caller change is needed.

## Reproduction (witnessed, pre-fix)

Minimal consumer project — `.kittify/charter/charter.md` with only `Purpose` and
`Testing Policy`:

```
$ spec-kitty charter context --action implement
...
Action-Critical Charter Sections (implement):

### Terminology Canon
  Run: spec-kitty charter context --include section:terminology-canon
  When you rename or introduce a term in the diff, run this command and apply
  the returned rule.

### Code Review Checklist
  Run: spec-kitty charter context --include section:code-review-checklist
...
```

and each selector resolves to
`_This charter has not yet authored a **Code Review Checklist** section. Add one to .kittify/charter/charter.md._`

## Evidence — surfaces that pin the current behaviour

| Surface | Path | Action |
| --- | --- | --- |
| Renderer | `src/charter/activation/context_renderers/section_bodies.py` | change |
| Bootstrap caller | `src/charter/activation/context_renderers/bootstrap_text.py` (`_append_block`) | no change needed |
| Compact caller | `src/charter/activation/context_renderers/compact_governance.py` | no change needed |
| Budget split-out | `src/charter/activation/context_renderers/token_budget.py` (`_split_critical_sections`) | no change needed: it only sees rendered headings |
| Unit tests | `tests/charter/test_context_section_bodies.py` | update the one test that pins missing-heading advertising |
| Display tests | `tests/charter/test_context_display_charter_md.py` | check for empty-charter expectations |
| ATDD contract | `tests/specify_cli/next/test_wp_prompt_governance_contract.py` | must keep passing unchanged |
| Contract doc | `kitty-specs/wp-prompt-governance-payload-01KRR8HS/contracts/charter-context-resolver.md` | update the `Action-Critical Charter Sections` row |

## Open questions

- None blocking. Whether a *masked* heading deserves a distinct message from a
  genuinely absent one remains an open follow-up already noted in the existing
  unit test; this mission does not change the placeholder text.

## Follow-up (not this mission)

- `spec-kitty-open-packs` `packs/built-in/missions/mission-steps/software-dev/{implement,review}/prompt.md`
  name `Terminology Canon`, `Code Review Checklist`, `Regression Vigilance` as
  sections "from `.kittify/charter/charter.md`". They reach consumer prompts and
  should describe them as project-charter sections that may be absent. File an
  issue; fix upstream and bump the pin.
