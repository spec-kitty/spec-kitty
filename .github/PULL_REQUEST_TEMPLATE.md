<!--
Spec Kitty PR-body contract (docs/development/how-to/pr-landing.md, "PR-body contract").
Use EXACTLY these five sections, in this order. An ad-hoc body
(Summary / Changes / Why / ...) draws a squad MAJOR and blocks merge.

- Title: `[#<n>] <what changes>`; branch `issue-<n>-<slug>` where possible.
- Open as a draft while CI runs; never request review with a WIP/[WIP] title.
- Lead `## Change` with impact for a user or operator (BLUF), before any
  architecture or test-strategy detail (docs/development/how-to/review-gates.md,
  "PR body style: consumer-focused BLUF").
- User-facing changes also carry an entry in docs/changelog/CHANGELOG.md
  under [Unreleased].
-->

## Issue

closes #<n>

## Change

<!-- First paragraph: what changes for a user or operator, in plain language.
     Then: what changed and why, grouped by area. Call out formatting-only or
     generated-file churn separately from behaviour changes. -->

## Tests run

<!-- Every command must be runnable verbatim: full tests/... and docs/... paths;
     invoke doc scripts as `uv run python -m scripts.docs.<x>`. Record counts. -->

```
<command>  # <N passed, M failed>
```

Self-review:
- <what you checked in your own diff, and the result>

## Blast radius

Discovery: `<git grep command used to find affected code>`
Files:
- <paths re-derived from a fresh run of the discovery command>

## Deferred

- None.
