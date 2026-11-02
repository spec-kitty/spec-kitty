# Discovery — issue-matrix source-issue gating (#7011)

The detailed grounding lives in [`research/code-grounding.md`](research/code-grounding.md)
(reproduction harness, exact line numbers, consumer map, existing test surfaces). This file
records the discovery *decisions* that the spec and plan build on.

## Decisions

- **D1 — The defect has two independent causes, and both need fixing.** The reported row
  came from a positional citation label (`epic #…`) matched anywhere on its line, which
  demoted every number on that line; but even with that fixed, the Mission's own source
  issue can still be demoted by prose that genuinely reads like a citation. The issue's
  "never" therefore needs a second, explicit guarantee, not just a better heuristic.
- **D2 — Fix the match site, not the pattern.** `Occurrence` kept only the stripped line;
  the citation's column is what was lost. Retaining it lets the existing label arms keep
  their (deliberate, #3469-hardened) behaviour while binding each label to one number.
  Deleting the `epic` arm was rejected: it would re-open the fail-open hole #3469 closed.
- **D3 — The guarantee belongs in the shared gating seam.** Four consumers already derive
  "referenced-but-missing" from one predicate (`is_gating` / `gating_issue_numbers`), so a
  promotion applied there reaches all of them; a fifth predicate would be the exact
  single-authority violation the classifier docs warn about. The `finalize-tasks` scaffold
  is the one caller that detects on `spec.md` alone, so it calls the same helper.
- **D4 — Derivation is narrow and fail-open.** Only a leading issue form in
  `meta.json` `source_description`, the spec's `**Input**:` line, and explicit closing
  keyword lines name a source issue. Free-form prose that mentions a number in passing is
  not promoted, and unreadable metadata contributes nothing rather than raising inside the
  approval blocker.
- **D5 — Promotion is additive, never subtractive.** It rewrites the classification of a
  reference that already exists; it never invents a row (the zero-reference rule is
  unchanged) and never demotes anything.

## Evidence

- Reproduction on the base, and the per-line classification of six citation shapes:
  `research/code-grounding.md` §1-§3, §5.
- Consumer map (scaffold, approval blocker, `status doctor`, merge gate) and the
  single-predicate seam they share: §4.
- Pre-existing suites that pin the current classification outcomes, including the
  fail-open hole guard for ordinary English words: §6.
- Changelog convention (per-PR fragment, `check_changelog_style`): §7.

## Open questions

None blocking. One accepted consequence to document rather than fix: a `see #A, #B` list now
demotes only `#A`, and `Parent epic #X. See #A, #B` no longer demotes `#A`/`#B` — both are
the documented default-gating contract (fail-safe in the direction of requiring a verdict),
and the reference doc states it in WP03.
