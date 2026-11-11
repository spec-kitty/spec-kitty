# Research: Docsite canary deploy

## R-1: where DocFX is restored

- **Decision**: keep the existing `build` (DocFX) job unchanged and running in parallel; publish the canary only once that build succeeded; make the existing `deploy` job wait on the probe and run on `!cancelled() || inputs.canary`.
- **Rationale**: no copy of the DocFX build steps; the restore artifact exists before production changes, so a failed DocFX build never strands the doc-kitty site live. The default path keeps the same jobs and guards, and its `deploy` condition is equivalent (with `canary-probe` skipped, `!cancelled()` plus `needs.build.result == 'success'` equals the old implicit `success()`).
- **Alternatives considered**: a separate restore job duplicating the DocFX steps (rejected: two definitions); making `build` wait on the probe (rejected: changes the default path's job graph and delays the restore artifact until after the canary).

## R-2: job-level status functions are transitive

- **Decision**: give `deploy` an explicit status function.
- **Rationale**: without one, a job gets an implicit `success()`, which is false when any upstream job in its `needs` chain failed, so a failed probe would skip the DocFX restore.

## R-3: two Pages artifacts in one run

- **Decision**: the shared build takes `pages-artifact-name` (default `github-pages`); the canary uses `github-pages-canary` and `deploy-pages`' `artifact_name`.
- **Rationale**: both `upload-pages-artifact` and `deploy-pages` default to `github-pages`; the DocFX artifact keeps that name, so its jobs are unchanged.

## R-4: action pins

- **Decision**: `actions/deploy-pages@368f82528645a54fb793d4d04e342629a3f51346 # v5.0.1` for the canary; `actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8 # v5.0.0` as elsewhere. The existing DocFX jobs keep their tag references (unchanged path).
- **Rationale**: the repository pins no `deploy-pages` by SHA yet; `refs/tags/v5` resolves to the v5.0.1 commit, which is what the DocFX job's `@v5` runs today, so the canary publishes with the same action code.

## R-5: the probe's sample

- **Decision**: derive one URL per class, deterministically (first in sorted order), from the baseline, the collapsed moves ledger and the committed legacy map:
  - own-page key: a map key that is not moved, not an index key, whose target is its own directory route;
  - chain key: a map key whose move's target moved again;
  - live `dir/index.html`: a baseline `*/index.html` route (not the root) with no map key (rule 3);
  - `dir/README.html`: a map key ending in `/README.html`;
  - directory URL: the rule-3 route's directory;
  - fixed: `/`, `/llms.txt`, and `/kitty-specs/glossary.html` (ADR D-5 names it as dropped), which must not be in the baseline.
- **Rationale**: no hand list (#2361 acceptance); a missing class refuses.
- **Redirects**: the probe does not follow HTTP redirects. GitHub Pages serves a flat stub file and a trailing-slash directory directly; a 3xx would be the hop D-5 worried about, so it fails.

## R-6: a PR-time exercise of the probe

- **Decision**: the shared build serves `site/dist` with `python3 -m http.server` and runs the probe with one attempt.
- **Rationale**: every pull request proves the sample still derives from the ledgers and the built site answers it, so a canary does not discover a ledger drift. `http.server` answers a directory with its `index.html`, a file directly, and 404 for a missing path, like Pages for these classes.
