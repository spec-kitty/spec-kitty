# Research: Op Records Stop Naming A Model, And Carry The Operator's Attribution

**Mission**: `op-record-model-and-coauthor-01M6EJV5` · **Issue**: #7013

## Grounding (read-only, on `origin/main` at `9aed3a8012`)

| Fact | Evidence |
| --- | --- |
| The defect reproduces on current `main` | `ProfileInvocationExecutor.invoke()` builds `OpStartedEvent(..., model_id=catalog_candidate.model_id)` (`src/specify_cli/invocation/executor.py:543,562`); `OpStartedEvent.model_id` is declared at `src/specify_cli/invocation/record.py:61`. |
| It is not a rare path | 1,014 of the tracked records under `kitty-ops/` carry `model_id` — 625 `claude-opus-4-6`, 383 `claude-sonnet-5`, 6 `claude-haiku-4-5`. |
| The auto-commit builds its message once and only once | `_commit_op_record()` composes `op(<profile>): <action> [<id8>]` and calls `safe_commit(message=...)`; nothing appends a trailer (`executor.py:1065-1100`). |
| Op commits in this repository carry no trailer | `git log --grep='^op('` shows messages with a subject line and no body or trailer. |
| Not superseded | No changelog entry mentions `model_id` (`git log -S model_id -- docs/changelog/CHANGELOG.md` is empty), no merged PR removes it, and #7013 is open with no assignees before this mission. |
| The field has exactly two consumers | `_resolve_dispatch_binding` (`cli/commands/agent/workflow.py:1519`) and `dispatch --json`'s advisory recommendation, which does not read the record at all (`RoutingCandidate.model_id`, a live value, not the persisted field). |
| History cannot be scrubbed | `kitty-ops/` is an immutable archive root under `tests/architectural/test_archive_root_byte_identical.py`: a pre-existing `kitty-ops/<ULID>.jsonl` may never be modified, so a scrub migration is structurally impossible, not merely unwanted. |
| The claim already has an explicit-absent vocabulary | `RESOLVED_MODEL_ABSENT` (`status/resolved_binding.py`) is the documented SC-011 sentinel for "a pick-up ran but resolved no model". |
| Pydantic ignores undeclared keys | `OpStartedEvent` sets no `extra=forbid`, so a legacy line carrying `model_id` still validates; a same-fixture test must prove both that it parses and that the key is not re-serialised. |

## Decisions

### D1 — Drop `model_id`; do not replace it with a derived token

Decision record: `plan.record.model-field-disposition`.

*Chosen*: remove the field. `actor` already records the harness key, which is
the non-identifying substitute the issue offers.

*Rejected*: an opaque digest of the model id, so `--model` could still be
verified against the record. Rejected because a digest of a small, public
catalog is the same identifier wearing a hat: it satisfies the letter of "no
model identifier appears" while keeping the prohibited fact recoverable, and it
would add a novel concept to a record schema that should stay boring. The rule
is about the fact being committed, not about the characters used to spell it.

*Consequence*: the resolved-model actual can no longer be proven from the Op.
Handled in D2.

### D2 — A claim refuses `--model` instead of inventing one

With no durable model evidence, `_resolve_dispatch_binding` cannot honour a
`--model` assertion. It raises an actionable error telling the caller to omit
`--model`, and the claim records `RESOLVED_MODEL_ABSENT` — the sentinel that
already exists for exactly this state. Alternative — silently dropping the
assertion and recording the caller's string as if it were resolved — was
rejected: it would turn an unprovable claim into a fabricated resolved actual,
which is the failure mode the SC-011 contract exists to prevent. This is a
deliberate narrowing of FR-013/FR-014 behaviour and is named in the PR body.

### D3 — The trailer comes from `commit.co_author`, with a per-close override

Decision record: `plan.attribution.trailer-source`.

*Chosen*: `.kittify/config.yaml` → `commit.co_author: "<Name> <email>"` as the
standing operator configuration, plus an explicit value on the close path
(`complete_invocation(..., co_author=...)`, surfaced as
`profile-invocation complete --co-author`) that overrides it.

*Rejected*: env-var only (`SPEC_KITTY_CO_AUTHOR`). It cannot be reviewed,
versioned with the project, or discovered by the next operator, and the
repository's config authority for behaviour switches is already
`.kittify/config.yaml` (`review.test_command`, `review.timeout_seconds`,
`merge.strategy`). *Rejected*: CLI-flag only, because the issue's primary ask is
that the standing auto-commit needs no hand work.

### D4 — A malformed configured trailer refuses the commit, visibly

The auto-commit is best-effort: a configuration defect must not lose the trail
(the completed event is already durable) and must not commit unattributed
either. So a malformed `commit.co_author` becomes an `OpCommitOutcome.refusal`
whose reason names the key; the existing close output and the doctor sweep
report already surface refusals.

*Rejected*: warn-and-commit-without-trailer (silently reproduces the reported
bug, now with a log line nobody reads), and raise-and-fail-the-close (turns an
optional attribution setting into a dispatch outage).

### D5 — Historical records are immutable; no migration

The archive-preservation gate forbids modifying a pre-existing
`kitty-ops/<ULID>.jsonl`, and the value is already public in `main`'s history.
The ruling is therefore: leave them, document it, and make the new-record
behaviour the ratchet. A scrub migration would have to rewrite frozen history,
which the repository's own gate refuses — that is a maintainer-relevant ruling,
so it is stated in the changelog, the docs and the PR body rather than assumed.

## Risk notes

- **Half-fix detection**: IC-03 must go red on its own when reverted. The trailer
  tests drive `complete_invocation` on a real git fixture (the existing
  `tests/specify_cli/invocation/_op_git.py` helpers) and read `git log -1 --format=%B`.
- **Vacuous absence probes**: the "no `model_id`" assertion is paired on the same
  fixture with a legacy line that carries it, and with a re-serialisation check,
  so a probe that simply cannot see the key fails.
- **Docs freshness**: `docs/api/cli-commands.md` is generated; the generator was
  run on a clean tree first and produced no diff, so a diff after the change is
  caused by `--co-author` alone.
