# green_match fixtures

Recorded read-only from `spec-kitty/spec-kitty` on 2026-10-01 (WP16, mission
ci-runtime-stabilisation-01M3TZH6) and trimmed with `jq` to the fields
`scripts/ci/green_match.py` reads. Tests never call the live API.

| File | Recording command |
|---|---|
| `run-ci-modules-zero-selection.json` | `gh api repos/spec-kitty/spec-kitty/actions/runs/36823737462` (a CI Modules `pull_request` run with zero module selection; it still carries one immutable `referenced_workflows` merge reference) |
| `commit-merge-5509.json` | `gh api repos/spec-kitty/spec-kitty/git/commits/a8f4ac8c897fee4067d20ddfb5552a03a1650d27` (`parents: [base, head]`) |
| `artifacts-by-name.json` | `gh api "repos/spec-kitty/spec-kitty/actions/runs/36823737462/artifacts?name=selected-modules"` |
| `workflow-runs-by-head.json` | `gh api "repos/spec-kitty/spec-kitty/actions/workflows/ci-router.yml/runs?event=pull_request&head_sha=a5cd2d26a5f9384d639a9eea0d6cae8afdaf1506&per_page=5"` |

The tested-key (`ci-tested-key-pr<N>-base-<sha>`) and green-match
(`ci-green-match-run-<id>-attempt-<n>`) markers do not exist on any real run
yet. Tests synthesize those artifact records from the **shape** recorded in
`artifacts-by-name.json`, changing only `name`, `expired` and `created_at`.
The names are synthesized; the shapes are recorded.

`pull_requests` is emptied in the run fixture on purpose: the helper never
reads that field (it is a live projection of the PR, and empty for fork PRs).
