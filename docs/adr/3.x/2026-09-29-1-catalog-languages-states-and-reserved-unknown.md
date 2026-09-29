---
title: 'ADR: Catalog languages — four states and the reserved unknown value'
description: 'Accepted: catalog.languages keeps absent, empty and recognised states and gains a reserved unknown value, with a regenerate-only precedence bypass and tech-agnostic doctrine.'
status: Accepted
date: '2026-09-29'
---

**Status:** Accepted

**Date:** 2026-09-29

**Deciders:** Stijn Dejongh (operator). Design reviewed by the mission's pre-planning, post-spec and
post-tasks adversarial squad lenses.

**Technical Story:** [#5284](https://github.com/spec-kitty/spec-kitty/issues/5284) (planning and
context for non-Python projects), [#5283](https://github.com/spec-kitty/spec-kitty/issues/5283) (mission
review), [#4614](https://github.com/spec-kitty/spec-kitty/issues/4614) (stale languages survive
regeneration), under umbrella [#2330](https://github.com/spec-kitty/spec-kitty/issues/2330).

---

## Context and Problem Statement

A Zig consumer got Python guidance in planning context, a failing review gate, and a stale
`catalog.languages: [python]` that survived every regeneration.

- `catalog.languages` carries a load-bearing contract from
  [#3292](https://github.com/spec-kitty/spec-kitty/issues/3292): absent means "admit every artifact",
  an empty list means "admit none".
- [#2395](https://github.com/spec-kitty/spec-kitty/issues/2395) decided that runtime reads treat the
  compiled value as authoritative over the interview transcript.
- No state expressed "the project declared a language Spec Kitty does not recognise".
- Operator policy (#2330): doctrine is tech-agnostic; unknown languages are advised to extend their
  local charter; languages are never added one by one.
- Governing principle (operator, 2026-09-29): charter and doctrine components are language- and
  stack-agnostic wherever possible; a language- or framework-specific component declares that
  specificity in its metadata (today `applies_to_languages`). When a project is configured for a
  language or stack, matching and suggested activation consider both the generic and the matching
  specific doctrine and charter packs.

## Decision

`catalog.languages` has four states:

| State | Stored form | Language-scoped artifacts admitted |
|---|---|---|
| No signal | absent or null | all (unchanged) |
| Admit none | `[]` (hand-edited only) | none (unchanged) |
| Recognised | `[python, ...]` | overlapping ones only |
| Unknown | `[unknown]` | none; unscoped artifacts still load, and one advisory is rendered |

1. **Reserved `unknown` value.** Spec Kitty writes `[unknown]` when the languages/frameworks answer
   is a real declaration that names no recognised language. Placeholders and the shipped default
   answer mean no signal, never `unknown`. A recognised language in that answer always wins over
   `unknown`.
2. **Declared answer wins (operator decision D1, 2026-09-29).** When the languages/frameworks answer
   is a real declaration (non-empty, not the shipped default, not a placeholder), languages resolve
   from THAT ANSWER ALONE: the built-in detector hits in it UNION the doctrine-vocabulary whole-word
   hits in it, else `unknown`. So `Python and Twig` resolves to `python, twig`, while `Zig` stays
   `unknown` even when the testing answer mentions `pytest`. The other answers are scanned, with the
   built-in detector only, when the languages/frameworks answer is absent, default or a placeholder.
   The built-in detector list is frozen (no per-language additions, C-001); the vocabulary is read
   from installed doctrine (built-in, org and project packs). A token attached to a preceding
   `word-` (for example `librespot-java`, or the `TypeScript` in `React-TypeScript`) does not count.
3. **Regenerate-only precedence bypass.** Only the regenerate path (`charter generate` with `--from-interview`, the default, and
   `charter activate --resynthesize`, which calls it) re-derives languages from the interview and
   replaces the compiled value, including a hand edit. Runtime reads and non-interview recompiles keep compiled-first precedence, so #2395 and
   #3292 stay intact.
4. **`unknown` is reserved in artifact scopes.** `spec-kitty charter validate` rejects it at authoring time,
   and it is stripped from both sides of the scope match at runtime. `any` and `all` remain rejected
   at authoring and are treated as unscoped at runtime.
5. **Advice, not language tables.** The context renders one advisory pointing to the how-to
   "Extend your charter for an unsupported language" whenever no installed doctrine is scoped to the
   resolved languages (operator decision D2, 2026-09-29). That covers `unknown` and also recognised
   languages without shipped specialist guidance, for example Rust, Swift or Ruby, while the stored
   `Languages:` value is still shown as recorded. `lacks_specialist_guidance` in
   `charter.activation.language_scope` is the single authority for this decision. The dead-code gate reports
   `MISSION_REVIEW_DEAD_CODE_NOT_APPLICABLE` (skip, `pass_with_notes`) for change sets it does not
   support.

## Consequences

- No shipped doctrine is Go-scoped after the tactic de-scoping below, so a Go project has no specialist
  guidance either; C# and C++ are not whole words and resolve to `unknown`. Installed doctrine (an
  org or project pack) that declares a language brings that language into the vocabulary.
- A recognised language without installed specialist guidance (Rust, for example) records
  `Languages: rust` and still sees the advisory.
- Follow-up, not delivered here: stack and framework metadata on doctrine components and
  language-aware activation suggestions, tracked in #5364.
- A framework-only answer (for example `Django`) is labelled `unknown`; the advisory tells the user
  to extend their charter.
- A plain `charter generate` replaces a hand-edited `catalog.languages`; `--no-from-interview` keeps it.
- Tactic de-scoping (operator directive 2026-09-29): three built-in tactics that are
  language-independent (`dependency-hygiene`, `chain-of-responsibility-rule-pipeline`,
  `secure-regex-catastrophic-backtracking`) are now unscoped and language-neutral. Built-in tactics
  are language-neutral; language-specific guidance lives in explicitly language-specific styleguides,
  toolguides and profiles, or in the local charter.
- The `unknown` value is reserved, so no artifact may target it.

## Alternatives Considered

- **A separate status field.** Two fields to keep consistent; rejected.
- **Reuse `[]` for unknown.** Loses the advisory signal and collides with the hand-edited admit-none
  meaning; rejected.
- **Modification-time precedence between interview and compiled value.** Fragile under git; rejected.
- **An explicit reset flag.** Undiscoverable; rejected.
- **Growing a per-language table.** Contradicts the tech-agnostic policy; rejected.
