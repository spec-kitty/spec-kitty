# Evidence: scheduled recapture publish failure

**Date**: 2026-10-04. **Requirements covered**: FR-022 (classification), NFR-007 (time limit). Origin: #5536.

## What failed

| Item | Value |
|---|---|
| Runs examined | 37182764995 and 37097776055 (scheduled recapture) |
| Failing command | `git push --force origin HEAD:refs/heads/ci/recapture-charter-shard-timings` |
| Error | `remote: Permission to spec-kitty/spec-kitty.git denied to stijn-dejongh` |
| HTTP status | 403 |
| Scheduled runs failing in a row | the last six |

## Classification

The token stored in the secret `CHARTER_SHARD_RECAPTURE_TOKEN` cannot write to the repository. This is inferred from the 403: the token's scopes were not inspected. It is not a code defect.

## Time limit observation

Three runs lasted 30 minutes 19 to 21 seconds against a job limit of 30 minutes.

## What the mission changed

| Change | Value |
|---|---|
| A rejected push | exits non-zero with a message naming the missing permission and the secret |
| Token check | a `detect` phase uses the token before the long capture, so a bad token fails early |
| Time budget | 4,200 s |
| Per-capture timeout | 2,100 s |
| Count-pass timeout | 300 s per module, inside the budget |
| Job limit | 120 minutes |

None of this was run against GitHub; every external call is faked in the tests.

## Operator action still required

Operator action is still required; see #5624. Given the classification above, the token in `CHARTER_SHARD_RECAPTURE_TOKEN` needs repository write access (inferred from the 403; not inspected).

## Conclusion

The six failed scheduled runs come from a credential without repository write access, not from the recapture code. The mission makes that failure explicit and early. Whether the scheduled recapture now publishes is `pending`: it needs the operator action in #5624, then one scheduled or manually dispatched run on GitHub.
