# Tracer: Tooling Friction

Mission: `ci-nightly-interpreter-matrix-45min-timeout-01M3G17F`

## Mission scaffold (`spec-kitty agent mission create`)

During this mission's scaffold, `spec-kitty agent mission create` failed once
with a transient `StartupAssetError` ("Global asset input changed... re-run
the command"). An immediate retry succeeded, and the tree was clean between
the two attempts (no partial state left behind by the failed attempt). This
is recorded here per the mission brief's explicit instruction, not
independently re-triggered or investigated further by this plan phase.

## Scaffold auto-commit subject line (known ledger SK-64)

The scaffold's auto-commit subject line, "Add scaffold for feature ...",
uses the prohibited term **"feature"** (Terminology Canon: `Mission`, not
`Feature`) and is not conventional-commit shaped. This is known ledger entry
SK-64. Per the mission brief's explicit instruction, this commit is left
**un-amended** — it is not this mission's job to fix the scaffold tooling's
own commit message, and amending it would rewrite history outside this
mission's stated scope.

## `spec-kitty plan --mission ... --json` (this phase)

Ran cleanly on the first attempt:

```
.venv/bin/spec-kitty plan --mission ci-nightly-interpreter-matrix-45min-timeout-01M3G17F --json
```

Result: `{"result": "success", "phase_complete": false, ..., "plan_substantive": false, "scaffold_only": true, ...}` — scaffolded `plan.md` from the standard template, current/target/base branch all correctly resolved to `issue-4951-ci-nightly-interpreter-matrix-timeout`. No drift from the expected `--help` shape (`--mission TEXT`, `--json`, `--help`) was observed; `--help` was checked first and matched.

## `safe-commit`

Recorded after the commit is made — see the plan-phase report / commit hash for the exact invocation and outcome.

## `safe-commit` on the final reviews/ trail commit — second live `StartupAssetError`

Committing the full `reviews/` trail at the end of the plan phase's R1-R6 loop
(`.venv/bin/spec-kitty safe-commit kitty-specs/.../reviews/ --to-branch ... -m ...`)
hit the SAME transient `StartupAssetError` class as the scaffold step above:

```
{"error": "global_assets: Asset changed during preparation:
~/.agents/skills/spec-kitty-setup-doctor; another spec-kitty
process (possibly a different version) is writing the same Spec Kitty home --
let it finish or stop it, then re-run the command", "kind": "StartupAssetError",
"path": null}
```

An immediate retry of the identical command succeeded (`"result": "success"`,
11 files committed). This is a second first-hand-verified occurrence of the
same defect class noted at scaffold time: concurrent `spec-kitty` CLI
invocations (very plausible here — up to seven review subagents plus this
phase agent's own commit all invoke the CLI against the same shared
`~/.agents`/`~/.spec-kitty` home over a short window) race on writing the
global asset store, and the loser fails closed with a retryable error rather
than corrupting state. No hand-edit was used; the retry is the documented
recovery path.

## Tasks phase (this session) — CLI drift confirmed as SK-237, plus three more `StartupAssetError` occurrences

**CLI-drift confirmation (SK-237)**: this session's own experience directly
confirms ledger entry SK-237 rather than merely citing it. The mission brief
warned in advance that the design-pipeline doctrine's "write `wps.yaml` →
`tasks-packages` → finalize-tasks" flow is NOT this checkout's wired flow, and
that this exact checkout's `software-dev` mission type wires only the single
`tasks` step (`packs/built-in/missions/mission-steps/software-dev/tasks/step.yaml`,
`sequence_index: 2`, `in_action_sequence: true`); `tasks-outline`/`tasks-packages`
exist as files but are `in_action_sequence: false`. This session read
`packs/built-in/missions/mission-steps/software-dev/tasks/prompt.md` directly
(the canonical SOURCE, per AGENTS.md's "Use Canonical Sources" rule) and
followed its actual documented flow: hand-author `tasks.md` + one WP prompt
file directly in `feature_dir` (no `wps.yaml`, no `tasks-packages` verb
invoked), `spec-kitty agent tasks map-requirements --batch`, then
`spec-kitty agent mission finalize-tasks --validate-only`, then the mutating
form. Both finalize-tasks invocations succeeded cleanly with zero ownership or
requirement-mapping errors on the first content-level attempt. This is
independent, first-hand confirmation of SK-237's account (the ledgered
instance was on a different mission, `reconcile-flake-family-01M34HR7`) — the
`tasks-outline`/`tasks-packages` naming trap did not need to be triggered here
because this session went straight to the canonical `tasks/prompt.md`, exactly
as the mission brief instructed and as SK-237's own "how it manifested" note
recommends for future agents.

**Three further first-hand `StartupAssetError` occurrences, same defect class**:

1. `spec-kitty agent context resolve --action tasks --mission ... --json` —
   succeeded on the FIRST attempt, no retry needed (contrary to the mission
   brief's expectation that this exact command commonly needs one retry in
   this checkout).
2. `spec-kitty agent mission check-prerequisites --json --paths-only
   --include-tasks --mission ...` — failed once with
   `{"error": "slash_commands: Global asset input changed:
   ~/.kittify/cache/agent-commands-freshness.lock; ...",
   "kind": "StartupAssetError"}`; an immediate retry succeeded and returned the
   full `feature_dir`/branch-context JSON cleanly.
3. `spec-kitty agent mission finalize-tasks --validate-only --mission ...
   --json` — failed once with
   `{"error": "slash_commands: Global asset input changed:
   ~/.agent/workflows/spec-kitty.analyze.md; ...",
   "kind": "StartupAssetError"}`; an immediate retry succeeded
   (`"result": "validation_passed"`).
4. `spec-kitty agent profile list --json` — failed on the FIRST **and**
   SECOND attempt, each against a *different* underlying asset path (first the
   same `.kittify/cache/agent-commands-freshness.lock`-class lock file, then
   `~/.agent/workflows/spec-kitty.analyze.md`). Per this
   session's own read of `tasks/prompt.md` step 8a ("a read-only harness that
   cannot invoke the CLI may inspect profiles under
   `packs/built-in/agent_profiles/` ... directly"), this session fell back to
   directly reading `packs/built-in/agent_profiles/*.agent.yaml` rather than
   retrying a third time or improvising a CLI substitute — the documented,
   sanctioned degraded path, not an ad-hoc workaround. `implementer-ivan` was
   selected over `python-pedro` because the latter's profile explicitly names
   "infrastructure-as-code" as an avoidance boundary, and this WP is majority
   GitHub Actions YAML.

All four occurrences are the same underlying defect class already documented
above (concurrent `spec-kitty` CLI processes racing on the shared
`~/.kittify`/`~/.spec-kitty`/`~/.agent` asset cache), just against different
victim files each time — consistent with genuinely concurrent activity in this
shared environment (other agents/sessions plausibly running spec-kitty
commands against the same home directory during this window), not a new or
different defect. No hand-edit of CLI state was used in any case; retry (or,
for the profile-list command, the documented degraded-fallback read) is the
recovery path used throughout.

**A fifth occurrence, requiring two retries**: committing this very tracer-file
update via `spec-kitty safe-commit ... --to-branch
issue-4951-ci-nightly-interpreter-matrix-timeout --json` hit the same class
twice in a row (first against `.kittify/cache/agent-commands-freshness.lock`,
then against `.agent/workflows/spec-kitty.analyze.md` — the same two victim
paths seen above, in the same order), before a third attempt succeeded
(`"result": "success", "committed": true`). This is the first time in this
session the sanctioned single retry was insufficient; a second retry cleared
it. No hand-edit was used — three total attempts, same command, unmodified.

## Tasks fix-round: git-history leak addressed via escalation language, not a changed check (TASKS-SEQ-004 / TASKS-VERIFY-001 / TASKS-VERIFY-002)

The tasks-phase adversarial review confirmed that this mission's own git history
(commit `afcf3bcd6`'s stored diff, only content-redacted by the later additive
commit `13dc5d966` — never rewritten) permanently trips the binding
`git log -p main..HEAD | grep -cE '/home/|/tmp/'` pre-push check at a nonzero
count. One proposed remediation (switching the check to a diff-scoped scan) was
explicitly rejected by this fix round because the exact check command was
mandated verbatim by this mission's own orchestration brief, and changing what
"the binding check" means is an operator-level decision this fix-round session
has no authority to make unilaterally. Instead, this fix round added a "Known
Issue" section to `tasks.md` plus a fallback/escalation clause to WP01's
T008/T011/T013 so the implementer can recognize the already-known leak, confirm
no new leak exists, and proceed without attempting any forbidden git-history
operation. No command text in the binding check itself was changed.

## History rewrite note (2026-09-27)

The unpushed branch history for this mission was rewritten on 2026-09-27 to
remove an OS username that had leaked into mission artifacts under this
mission's spec directory. Commit hashes cited elsewhere in this file and in
`reviews/tasks.*` (e.g. `afcf3bcd6`, `13dc5d966`, `bb5db8865`, and all commits
after them) refer to PRE-rewrite commit identities; the rewrite gave every
commit in the branch a new hash. Content is otherwise unchanged aside from the
targeted redaction.

## `record-analysis` verdict/findings mismatch (live tracked defect #3133, ledger SK-06)

During the analysis phase (this session, 2026-09-27), ran:

```
.venv/bin/spec-kitty agent mission record-analysis --mission ci-nightly-interpreter-matrix-45min-timeout-01M3G17F --input-file <temp-report.md> --json
```

The input file's body was a Markdown document containing a fenced
` ```yaml ` block conforming to the `analysis-findings/v1` schema, with
`verdict: ready` and 4 populated findings (severities: high, moderate, minor,
none). The command itself succeeded (`"success": true, "result": "success"`)
after one retry for a transient `StartupAssetError` (same defect class already
documented above in this file — a different victim asset path,
`~/.github/prompts`, this time).

However, the JSON result AND the persisted file
(`kitty-specs/ci-nightly-interpreter-matrix-45min-timeout-01M3G17F/analysis-report.md`)
both show the command's own frontmatter carrier recorded `verdict: unknown`,
`findings: []`, and `issue_counts` with every field `null` — none of which
match the `analysis-findings/v1` YAML block actually supplied in the input
file's body (`verdict: ready`, 4 findings). The command appears to generate its
own frontmatter carrier independently of parsing the input file's embedded
YAML findings block, rather than deriving `verdict`/`findings`/`issue_counts`
from it. This is a first-hand-verified occurrence of the live tracked defect
this mission's own orchestration brief named in advance (#3133, ledger SK-06):
a findings-free-and-`ready` analysis body can be recorded with a top-level
`verdict: unknown` (not `ready`), which is exactly the mismatch shape that
defect describes.

Per the orchestration brief's explicit instruction, this was NOT hand-fixed
by editing `analysis-report.md` directly — only this tracer note was added,
and only via `spec-kitty safe-commit`, never a raw file edit followed by a
plain `git commit`.

### CORRECTION (2026-09-27, follow-up investigation) — the SK-06/#3133 conclusion above is not supported by this round's evidence

A follow-up investigation traced `record-analysis`'s actual carrier contract
from primary sources — its `--help` text, `src/specify_cli/analysis_report.py`
(`_split_carrier`, `parse_structured_findings`,
`FINDINGS_SCHEMA_V1 = "analysis-findings/v1"`), and the canonical analyze
mission-step prompt (`packs/built-in/missions/mission-steps/software-dev/analyze/prompt.md`,
step 6/7) — rather than trusting the assumption this section made about the
required input shape. Two independent findings retract the conclusion above:

1. **The round-1 input carrier was NOT correctly shaped.** `record-analysis`
   parses the carrier as literal **YAML frontmatter** at the very start of the
   input file — `_split_carrier` returns `None` immediately unless
   `body.startswith("---")`, i.e. the file's first three characters must be a
   `---` delimiter, with a matching closing `---` before the Markdown body
   begins. The prompt template is explicit and repeated on this point ("The
   report MUST begin with a structured `analysis-findings/v1` YAML frontmatter
   carrier..."; "Writing `analysis-report.md` directly... leaves the file in
   carrier format, which the implement gate rejects"). The round-1 input file,
   per this section's own description above, instead began with a Markdown
   document containing a **fenced ` ```yaml ` code block** — confirmed by the
   persisted `analysis-report.md`'s surviving body, which shows the untouched
   input starting with a literal ` ```yaml ` fence line (no leading `---` at
   all) followed by `schema: analysis-findings/v1`. Because the body does not
   start with `---`, `_split_carrier` returns `(None, body)` unconditionally —
   `parse_structured_findings` never even inspects the fenced block's
   contents. `record-analysis` therefore correctly fell back to its documented
   legacy-report behavior (`verdict: unknown`, `findings: []`,
   `issue_counts` all `null` — see `C-FIND-3` in `analysis_report.py`). This is
   the tool behaving exactly as designed for a malformed/unrecognized input,
   not the tool silently discarding a well-formed one.
2. **Even a byte-correct carrier here would never have produced `verdict:
   ready`.** `record-analysis` does not read a bare `verdict:` key from the
   carrier at all — it *computes* the verdict solely from
   `findings[].severity` (`compute_verdict_from_findings`: any `high`/
   `critical` finding -> `blocked`, otherwise `ready`). A literal `verdict:`
   field (as opposed to the optional `verdict_hint`, which the tool validates
   for agreement and fails loudly on mismatch) is not consulted at all. The
   round-1 body's own fenced block carried a `high`-severity finding (AF-001)
   alongside a hand-written `verdict: ready` — a shape that violates the
   pipeline's own binding rule (`design-pipeline.md` §4/§4a: "any high/critical
   finding -> verdict: blocked") independent of anything `record-analysis`
   does. Had this input been correctly frontmatter-shaped, the tool would have
   computed `verdict: blocked` from the `high` finding, not `unknown`.

**Conclusion:** this round does **not** confirm live tracked defect
#3133/ledger SK-06 as reproduced. The round-1 input was doubly
non-compliant with `record-analysis`'s actual, documented contract — wrong
carrier delivery mechanism (fenced code block instead of leading YAML
frontmatter) and a hand-written `verdict: ready` value that the tool never
reads and that also contradicted the pipeline's own ready+high exclusion rule.
`verdict: unknown` here is a garbage-in/garbage-out artifact of that malformed
input, not a demonstrated tool defect. Whether `record-analysis` mis-parses a
*correctly-shaped* (leading `---`/`---` frontmatter, `schema:
analysis-findings/v1`, no `verdict:` literal) carrier whose findings include a
`high`/`critical` entry remains **untested by this mission** — this
correction does not claim SK-06/#3133 is false, only that this occurrence does
not verify it. A future analyzer that reproduces the failure with a
byte-correct carrier should log it as a fresh, independently-verified
occurrence rather than citing this entry as confirmation.

## WP01 implement phase: `spec-kitty agent action implement` transient/usage friction

Two distinct issues hit back-to-back on the FIRST invocation of
`spec-kitty agent action implement WP01 --agent claude` (no `--mission` yet):

1. `Error: slash_commands: Global asset input changed:
   /home/<redacted>/.agent/workflows/spec-kitty.analyze.md; re-run the
   command`. This machine runs several concurrent spec-kitty agent sessions
   across different missions/checkouts (confirmed via `ps aux` showing a
   sibling mission's lane worktree pytest process running at the same time),
   so this reads as a per-user GLOBAL asset (`~/.agent/workflows/`, Google
   Antigravity's directory — not a tool this project's `.kittify/config.yaml`
   configures) being touched by a concurrent peer's own asset-preparation
   pass while this invocation's own drift-recheck was mid-flight
   (`asset_preparation.py`'s `Global asset input changed` observation-vs-
   recheck mismatch, not this project's fault). `spec-kitty doctor
   command-files` (the suggested diagnostic) reported "all files healthy"
   immediately after, and a bare re-run of the exact same command succeeded
   past this point on attempt 2 (surfacing the NEXT, unrelated issue below) —
   consistent with a transient concurrent-peer race, not a persistent defect
   in this checkout. Not independently investigated further, per this
   session's scope.
2. `Error: --mission <slug> is required` — `spec-kitty agent action implement
   WP01 --agent claude` alone is refused; the command's own `--help` text
   does not make `--mission` sound required for a single-mission checkout
   (there is exactly one active mission's `kitty-specs/` entry with an
   unresolved WP01), yet `spec-kitty next --mission <slug>` and other WP
   commands seen elsewhere in this checkout DO pass `--mission` explicitly.
   Adding `--mission
   ci-nightly-interpreter-matrix-45min-timeout-01M3G17F` resolved it on the
   third invocation and produced the expected lane-worktree allocation. Not
   filed as a gap by this WP (out of scope for an implementer session), but
   worth a future doctrine note: `--mission` being conditionally required
   with no single-mission auto-detection fallback is easy to miss on a first
   read of `--help`.

## Lane worktree has no `.venv`

`spec-kitty implement WP01`'s resolved lane worktree
(`.worktrees/ci-nightly-interpreter-matrix-45min-timeout-01M3G17F-lane-a`)
does not carry its own `.venv/` — `uv sync`/a fresh venv build was not run
there. Since this mission's diff touches no `src/` code (CI YAML + one new
test-support module + one new test module, all under `tests/architectural/`),
this WP ran `pytest`/`ruff` via the PRIMARY checkout's `.venv/bin/python` /
`.venv/bin/ruff` binaries while `cd`'d into the lane worktree (absolute
interpreter path, relative test paths resolved against the worktree's own
files) rather than `uv sync`-ing a second venv purely to satisfy a path
convention — confirmed safe by checking that
`import specify_cli; specify_cli.__file__` resolves to the PRIMARY checkout's
`src/` (an editable install), which this WP never touches or exercises. A WP
whose diff DOES touch `src/` would need to `uv sync` a lane-local venv first
to avoid running against stale/mismatched primary-checkout code.

## 2026-09-28 — takeover as #5263 (supersedes #5244)

- **Wrong implementer profile for the #5128 fold.** The orchestrator hand-picked
  `implementer-ivan` for the override-tier removal instead of routing it. The change is
  pure Python test code plus a repo-tree deletion, so `python-pedro` (the Python
  specialist, which inherits Ivan's discipline per `implementer-ivan.agent.yaml`) was
  the right profile. Root cause: no `spec-kitty dispatch` routing step before delegating
  to a subagent; the profile was chosen from memory. Remedy for next time: route
  subagent work through `spec-kitty dispatch "<task>"` (no `--profile`) or pick the
  language specialist explicitly. Mitigation here: a `python-pedro` review lens over the
  fold before it is pushed.
- **`uv run` silently drops the interpreter.** Without `--python`, `uv run` honours
  `.python-version` (3.11.15) and rebuilds a `UV_PROJECT_ENVIRONMENT` venv synced for
  3.13. That is how every "3.13" shard in #5244's validation run tested 3.11. The same
  trap bit a local 3.13 scratch venv built without `--python`.
- **`_gate_coverage` tokenizer let `--frozen` swallow `--python`**, so the pinned run
  line resolved to zero gates. That is why the pin had been dropped to begin with.
- **The shard roster lists loose `tests/specify_cli/*.py` files one by one.** Each new
  file there reds the zero-gap gate (#5252's `test_analysis_report_symlink_loops.py`
  did) until someone assigns it a shard.
- **The CI artifact store is unreachable from the cloud container** (egress proxy 403 on
  `*.blob.core.windows.net`). The JUnit reports could not be fetched, so red shards had
  to be re-run locally on 3.11 and 3.13 to classify them.
- **Dispatched nightlies on a topic branch still run P0 escalation.** They open or update
  `priority:P0` issues (#5265 was opened by this branch's validation run).
- Adjacent, found during the parallel doctrine Op (#5266):
  - `spec-kitty dispatch --profile X` refuses a built-in profile the repo charter has not
    activated.
  - `charter activate` refuses to run from a linked worktree, and recompiles all of
    `charter.yaml` (about 1,100 lines of churn that drops still-activated artifacts).
  - `profile-invocation complete --artifact <url>` mangles `https://` to `https:/`.
