# Contract: `doctor workspaces --remote`

```
spec-kitty doctor workspaces [--fix] [--prune] [--remote <name>] [--json]
```

| Flag | Effect |
|------|--------|
| `--remote <name>` | The remote whose tracking refs prove a landing. Default `origin`. Applies to the landed-worktree report and to `--prune`; `--fix` keeps its husk-only remediation and never prunes, but the report it also prints is proven against `<name>`. |
| (unchanged) | `--fix`, `--prune`, `--json` keep the semantics of `contracts/doctor-workspaces-cli.md` in Mission `landed-worktree-cleanup-01M6KZNP`. |

## What the remote selects

| Decision | With `--remote <name>` |
|----------|------------------------|
| Primary branch name | `refs/remotes/<name>/HEAD` when it is a symbolic ref; otherwise the same resolver as before (`resolve_primary_branch(bias=False)`). A name that only that fallback produced stays `PRIMARY_UNRESOLVED` unless it is one of the common primary names. |
| Absorption proof | `refs/remotes/<name>/<primary>` — and only that ref. A tip present on another remote-tracking ref but absent from this one is `not_landed` (`CONTENT_NOT_ON_PRIMARY`). |
| `--prune` re-assessment | The same `<name>`; a mismatch between the reported remote and the pruned one fails closed (the worktree is kept). |
| Network | Nothing is fetched or contacted, with any `<name>`: the ref is read locally. |

The verdicts (`landed`, `not_landed`, `mission_owned`, `unproven`, `excluded`),
the `Reason` codes and their documented first-match order are unchanged, and
still come from `landed-worktree-cleanup-01M6KZNP`'s `data-model.md`. This
contract adds no reason code.

## Messages

| Situation | Output |
|-----------|--------|
| `<name>` is not a configured remote, and the repository has remotes | One error line `no such remote '<name>'; configured remotes: <a>, <b>`, no verdicts, exit 1. JSON carries it as `worktrees_error`. A repository with no remote at all keeps the older answer: every worktree `unproven` / `PRIMARY_REF_MISSING`. |
| `<name>` configured, `refs/remotes/<name>/<primary>` absent | Each worktree `unproven` / `PRIMARY_REF_MISSING`, detail `refs/remotes/<name>/<primary> does not exist locally: run \`git fetch <name>\``. |
| Primary only guessed | `unproven` / `PRIMARY_UNRESOLVED`, detail `the primary branch '<branch>' is only a guess: set it with \`git remote set-head <name> <branch>\``. |
| A landed worktree, without `--prune` | The remedy line names the remote: `remove with: spec-kitty doctor workspaces --prune --remote <name>` (`--remote <name>` is omitted when it is `origin`). |

## JSON

`--json` adds `remote` beside `worktrees` and `uninspected_processes`, so a
payload says which remote proved the verdicts it carries. Existing keys keep
their meaning and exit codes are unchanged: 0 when there are no husks and no
guard refusal, 1 otherwise.

`WorktreeAssessment.to_json()` — the assessment's own machine shape, pinned by
`landed-worktree-cleanup-01M6KZNP`'s `data-model.md` — is deliberately unchanged;
the remote travels on the attribute and in the CLI payload, so a sibling
Mission's contract is not extended from here.
