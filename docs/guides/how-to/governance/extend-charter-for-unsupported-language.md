---
title: Extend your charter for an unsupported language
description: What "Languages unknown" means, how to add tech-specific guidelines to your local charter, and what review reports for non-Python missions.
doc_status: active
updated: '2026-10-08'
audience: docs/context/audience/external/tech-lead-evaluator.md
type: how-to
related:
- docs/guides/how-to/governance/setup-governance.md
- docs/guides/how-to/governance/create-an-org-doctrine-pack.md
- docs/guides/how-to/governance/troubleshoot-charter.md
- docs/architecture/doctrine-kinds.md
---
# Extend your charter for an unsupported language

Use this guide when `spec-kitty charter context` reports `Languages: unknown` for your project
(for example a Zig or Go project), or when `spec-kitty review` says the dead-code scan is not
applicable to your Mission. It shows how to add your own tech-specific guidelines to the local
charter.

## What `Languages: unknown` means

Spec Kitty doctrine is technology-agnostic. It does not ship specialist guidance for every language.
`Languages: unknown` means your project declares a language that neither the built-in detector nor any installed doctrine recognizes.

- Language-neutral doctrine keeps applying. Built-in tactics are language-neutral.
- Guides, tool guides and profiles that are scoped to a specific language (for example the Python
  ones) stop applying to your project.
- Language-specific guidance lives in explicitly language-specific styleguides, toolguides and
  profiles, or in your local charter. Spec Kitty does not add languages one at a time.

The context output includes a single `Advisory:` line that points you to this page whenever no
installed doctrine is scoped to your project's languages. That includes `unknown`, and also a
recognized language that has no shipped specialist guidance (for example Rust, Swift or Ruby). In
that case the compact view shows the recorded value, such as `Languages: rust`, followed by the
advisory. A project whose language has installed guidance (for example Python) sees no advisory.

## How Spec Kitty decides

The languages/frameworks answer (key `languages_frameworks` in
`.kittify/charter/interview/answers.yaml`) decides when you give one.

1. **A real declaration decides alone.** When that answer is non-empty, not a placeholder and not
   the shipped default, Spec Kitty resolves your languages from that answer only. Two sources
   contribute, and their results are combined:
   - the **built-in detector**, a fixed list of common languages (Python, TypeScript, JavaScript,
     Rust, Java, Swift, Ruby, PHP) and their well-known tools (for example `pytest`, `mypy` or
     `ruff` for Python, `npm` or `jest` for JavaScript, `cargo` for Rust, `rspec` for Ruby);
   - the **doctrine-derived vocabulary**: a whole word that some installed doctrine artifact
     (built-in, org or project pack) is scoped to (for example `Twig`, or a language your own pack
     declares).

   So `Python and Twig` is recorded as `python, twig`, `Rust with cargo` as `rust`, and `Zig` or a
   framework-only answer such as `Django` as `unknown`. Words in your other answers (for example
   `pytest` in the testing answer) are ignored, so they can no longer turn a Zig project into a
   Python one.
2. **Otherwise the other answers are scanned.** Only when the languages/frameworks answer is
   absent, the shipped default or a placeholder (empty, `N/A`, `none`, `TBD`,
   `language-agnostic`, or several of these joined by commas, semicolons or slashes) does the
   built-in detector scan the remaining answers. A hit there is recorded, and a miss records
   nothing: no signal, no `unknown` and no advisory.
3. **`unknown`** is written only for a real languages/frameworks declaration that neither the
   detector nor the vocabulary recognized.

A language token attached to a preceding `word-` does not count: `librespot-java` does not declare
Java, and `React-TypeScript` does not declare TypeScript (write `TypeScript with React` instead).
A trailing compound such as `Java-based` still counts. Spec Kitty does not interpret sentiment or
negation: a mention counts even if the answer says the tool is only used for helper scripts.
Recognized languages are written to `catalog.languages` in `.kittify/charter/charter.yaml`.

## Add tech-specific guidelines to your local charter

1. Scaffold a project-level styleguide or toolguide for your language. The stub lands under
   `.kittify/charter-packs/`:

   ```bash
   spec-kitty charter new styleguide zig-conventions
   ```

2. Fill in the placeholders, then validate it:

   ```bash
   spec-kitty charter validate .kittify/charter-packs
   ```

3. Activate it:

   ```bash
   spec-kitty charter activate styleguide zig-conventions
   ```

   Do not set `applies_to_languages` to `unknown`; the value is reserved and validation rejects it.
   Leave the field unset and the artifact applies to your project.

4. Put narrative rules that do not fit an artifact (build commands, test commands, review
   expectations) in `.kittify/charter/charter.md`. See
   [How to Set Up Project Governance](setup-governance.md).

To share the same guidelines across several repositories, package them as an org Charter Pack. See
[How to Create an Org Charter Pack](create-an-org-doctrine-pack.md).

## Regenerate after correcting the interview

`spec-kitty charter generate` reads the interview by default (`--from-interview`). It re-derives the
languages from the current answers and replaces any hand edit of `catalog.languages`.

```bash
spec-kitty charter generate --force
```

To keep the recorded languages unchanged, pass `--no-from-interview`. `charter activate`
without `--resynthesize` and the pack commands recompile without re-deriving, so they also keep the
recorded languages. `charter activate --resynthesize` re-derives the languages the way
`charter generate` does and replaces a hand edit.

If `available_tools` lists a tool Spec Kitty does not register (for example `zig`), generation prints
that it is not a registered tool id and ignores it. Tool ids are validated separately from project
languages, and the entry never becomes a language.

## What `spec-kitty review` reports for non-Python Missions

The dead-code scan analyzes Python sources only. When the changed files hold nothing it supports
(for example only Zig, Go or documentation files), the review reports:

```text
MISSION_REVIEW_DEAD_CODE_NOT_APPLICABLE
```

The gate is recorded as `skip`, the verdict is `pass_with_notes` and the exit code is 0. This is not a
clean scan: no dead-code analysis ran for those files. Add your own analyzer or test command, and
tech-specific review guidance, to your local charter as described above.
