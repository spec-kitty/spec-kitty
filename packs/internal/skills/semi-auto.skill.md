Goal: take the named issue-set through a governed delivery run that works on its own but pauses to escalate the operator's decisions, landing a draft PR the operator merges. The same standing orders run two ways — here in this session (local), or handed to a fresh cloud runner (cloud). The operator is the maintainer who invoked this skill; the canonical remote is the git remote that points at `spec-kitty/spec-kitty` (find it with `git remote -v`).

Input: the issue numbers or issue-set (parameter `issues`), the mode (parameter `mode`), optional guidance and a closeout profile. If no issue is named, ask which to run. If the mode is not given: ask whether to run here or dispatch when this session can create cloud sessions, otherwise run local.

The standing orders are identical in both modes and live in the `semi-auto-delivery` procedure — it carries the rules; this skill carries only the order and the mode fork. Load it with `spec-kitty charter context --include procedure:semi-auto-delivery`, and `--action implement` / `--action review` for the phase doctrine.

## Both modes: the standing orders

Follow the `semi-auto-delivery` procedure end to end:

1. Orientation gate — sync the environment, read CLAUDE.md, AGENTS.md and the charter in full, load the phase context. The charter overrides any brief.
2. Research, grounding and discovery squads first — commit the read-only grounding note (sizes, responsibility map, invariants with citations, the gates and ledgers touched, test seams, open-P0 and sibling-run interactions, 90-day churn) plus the two discovery-squad verdicts — sibling surfaces and related/superseding issues, each with its disposition — before any spec exists. The discovery verdict lands in the PR's Discovery sub-section at closeout; it beats the pointfix tendency.
3. Decide Mission vs Ops by blast radius; split an issue-set that spans unrelated surfaces. State the choice.
4. Work autonomously, but STOP and surface the decision to the operator on the escalation classes: a regression-vs-stale-test verdict; a shared-seam, public-contract or architectural-boundary change; a test-expectation edit; scope widening; a charter Decision Moment; contract versioning. A path that decides also signals — never resolve one silently.
5. Brownfield discipline — smallest viable diff, locality of change, single canonical source, red-first, and never skip/disable/xfail/quarantine a test or retry-to-green.
6. Test policy — `make test-fast` plus the test files of every module the diff touches and the owning subsystem's own test directory, plus the specific architectural gate files a cross-cutting change implicates (named individually); never a heavy-suite sweep or `make test-full` (CI owns those at the draft PR); `make format-check`; zero ruff and mypy. Record commands and counts in "Tests run".
7. Rebase cadence — onto the canonical remote's `main` after spec, plan and tasks (before implement), then only on a staleness notice. Never push `main`.
8. Closeout — clean branch, rebase, update `docs/changelog`, pre-PR review squad, fold the findings, open a DRAFT PR targeting `main` with the five-section body contract (validate with `validate-pr-body.py`), watch CI to green, then flip to ready-for-review with a reviewer handover comment. The operator merges.

## Local mode

You are the runner. Run the whole delivery in this session, following the standing orders above directly, and land the draft PR from here. Every escalation-class decision pauses THIS conversation and asks the operator before you proceed.

## Cloud mode

You are the dispatcher, not the runner. Follow the `cloud-session-dispatch` procedure to build a complete dispatch prompt (no placeholders) and spawn a fresh cloud runner against `spec-kitty/spec-kitty` at `main`, inheriting the model and environment. The prompt BINDS the semi-auto standing orders by reference — it tells the runner to load `spec-kitty charter context --include procedure:semi-auto-delivery` and follow it — instead of re-typing them, and fills in the issue-set, the per-kind doctrine for the work, the numbered slices, and the closeout profile. Report the session id, the branch and the instruction summary; never predict results; read real state back from the session before claiming any progress. Relay later operator guidance as a labelled addendum. The runner performs the escalation pauses in its own session — the prompt instructs it to surface escalation-class decisions there.

## Stop and ask the operator when

- the mode is ambiguous and this session can create cloud sessions;
- the issue-set spans unrelated surfaces (split it into separate runs or dispatches and confirm the scope);
- any escalation-class decision arises (local: pause here; cloud: the runner pauses in its session);
- an issue is already resolved or superseded, or already claimed by someone active on it.

## Hand-off

Local: the flip from draft to ready-for-review is the hand-off to the maintainers. Report the PR link, the issues it closes, what each review round changed, and every still-red check with the reason it is not this PR's. Never flip a PR that is red or still being changed; never merge or arm auto-merge on your own initiative.

Cloud: the hand-off is the spawned session plus its dispatch summary; the runner delivers its own draft PR and performs its own hand-off. Do not archive or interrupt a session unless the operator asks.

In either mode, the operator's commit attribution trailer rides every commit, no AI model identifier appears in any commit or PR, and GitHub posts follow the operator's and the harness's attribution conventions.
