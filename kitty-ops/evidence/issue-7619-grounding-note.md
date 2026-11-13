# Grounding note: #7619, nightly `acceptance-bdd` red (73 scenarios, 3 OSes)

> Read-only grounding for a governed Op (one surface, one file). Date: 2026-11-13.
> Branch: `issue-7619-acceptance-fixture-init-commit`. Kind: test quality (fixture drift).
> Operator ruling Q1: keep the #7555 default (`spec-kitty init` commits its own writes). Do not revert it.

## 1. Root cause (confirmed locally, not inferred)

The triager blamed `acceptance-jvm/src/test/java/kitty/acceptance/environment/MissionFixture.java`:
`ensureProject()` ran `git add -A && git commit -m "set up spec-kitty"` right after `spec-kitty init`.
`git(...)` throws on a non-zero exit (old line 106). The triager *inferred* that the commit failed
with "nothing to commit". Reproduced on `origin/main` (`1fb3b55f`, editable install, 4.0.0rc9):

```
git init -b main && git commit --allow-empty -m seed
spec-kitty init --non-interactive --ai claude   # exit 0
git log --oneline                               # 9c5fa62 chore: initialize spec-kitty project / a13124b seed
git status --porcelain                          # (empty)
git add -A && git commit -m "set up"            # "nothing to commit, working tree clean", exit 1
```

So the inference holds: since #7555 / PR #7562, `init` makes its own commit on a repository that
already has one, which leaves a clean tree. The fixture's unconditional commit then fails. Every
scenario that builds its project through `ensureProject()` (directly through "a project set up with
Spec Kitty whose files are committed", or through `MissionFixture.createMission` and
`MissionLifecycle.plan*`) fails during arrange. That accounts for all 73 failures, each with the same
message, `git [commit, -m, set up spec-kitty] failed`.

## 2. Fix

`ensureProject()` runs `git add -A && git commit` only when `git status --porcelain` is not empty, and
never makes an empty commit. That keeps the history a user would have. The commit also still covers
anything `init` leaves uncommitted: an opt-out, or the unborn-branch case of #7612 (which the fixture
never reaches, because it always seeds a commit first). The output is merged stdout and stderr
(`ProcessRunner`). A stray git warning would therefore read as a dirty tree, and the commit would then
fail loudly. That fails in the safe direction and hides nothing.

## 3. Similar-surfaces sweep

| Surface | Assumes a dirty tree or counts commits after `init`? | Disposition |
|---|---|---|
| `MissionFixture.ensureProject` | Yes: unconditional commit | **Fixed here** |
| `ArrangeSteps` "a project already set up with Spec Kitty for the agents" | No: runs `init` only | Unaffected |
| `GitStates.commitEverything` ("every change in the project is committed") | Uses `--allow-empty` | Unaffected. Used after `init` in `migration-ledger.feature`, and still holds |
| `ArrangeSteps.commitWorkingTree` (some uses right after `init`) | Uses `--allow-empty` | Unaffected |
| `ArrangeSteps` "the file ... is committed with the text ..." | Commits a file it has just written | Unaffected |
| `MissionLifecycle.commit(...)` | Runs after `mission create`, plan and amend, which leave writes | Unaffected by #7555. If a scenario goes red here, it shows up in the gating run (see the PR's *Tests run*) |
| `init.feature` "...inside an existing repository leaves its git history alone" (`no new commits`) | Records commits *before* `init <dir>` in a subfolder | Not among the 73. `init` does not commit into the parent repository for a new subfolder project |
| `migration-ledger.feature` `no new commits` after `upgrade` | Counts after the explicit commit step | Unaffected |
| Python test tree (`tests/`) | Out of scope for #7619 (a JVM acceptance-only red) | Not swept |

## 4. Related issues

| Issue | State | Disposition |
|---|---|---|
| #7555 (`init` leaves its writes uncommitted) | Closed by PR #7562 | The behaviour change that caused this drift. Kept (ruling Q1) |
| #7545 (Sub-epic B: the CLI commits its own writes) | Open | Parent context. Not changed here |
| #7612 (`init` on an unborn branch does not commit) | Open, P3 | A separate slice. The fixture always seeds a commit, so this fix neither depends on #7612 nor masks it |
| #5106 (Epic: red-on-main and stale tests) | Open | Parent of #7619 |

No open PR references #7619 (searched 2026-11-13).
