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

`workflow-runs-by-head.json` also carries the run identity fields the candidate
binding reads (`head_branch`, `head_repository.full_name`, `pull_requests[].number`).
`head_branch` and `head_repository` are recorded from the live run. The recorded run's
`pull_requests` is `[]` today (a live projection that GitHub empties once the PR is merged),
so its content is synthesized over the shape recorded from a live CI Router run that still
listed its PR (run 36895215854: `{base, head, id, number, url}`), with the number, branch and
head SHA set to this fixture's PR. Negative contract rows (forged-from-other-PR, different head
branch, different head repository, missing or empty `pull_requests`) derive from this object
by replacing one field.

`pulls-by-head.json` is the head-uniqueness listing. It was recorded with
`gh api 'repos/spec-kitty/spec-kitty/pulls?head=spec-kitty:fix/nightly-reds-5505-5506-5507&state=all&per_page=100'`
(2026-10-01) and trimmed with `jq` to `number`, `state`, `base.ref`, `base.sha`, `head.ref`,
`head.sha` and `head.repo.full_name`. The recorded `head.sha` is the PR's final head, so it is
set to this fixture's `HEAD`. The "second PR on the same head" object that the negative rows
add (`other_pull()` in `test_green_match.py`) is synthesized over this recorded PR object: a
different `number`, `state: closed` and a different `base.ref`. The shape is recorded; those
values are synthesized.
