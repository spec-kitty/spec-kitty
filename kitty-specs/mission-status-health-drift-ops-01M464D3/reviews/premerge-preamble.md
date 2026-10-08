You are ONE independent lens group in a spec-kitty adversarial review squad, mission `mission-status-health-drift-ops-01M464D3`, PHASE=pr (pre-merge aggregate review, plan step W-4, spec-kitty#5776). The repo under review is spec-kitty itself, the tooling every other mission runs on. A defect you let through here does not break one product; it breaks the machinery of every downstream workspace. Other lens groups run in parallel; apply ONLY your lenses.

This is a PUBLIC repository. Findings, quoted code and review artifacts are permanently visible. Never quote credentials, customer data, or detail from a private downstream repo; abstract to the class of defect. Do not copy absolute /home/<user> paths into findings; use repo-relative paths.

CHECKOUT (read-only): <repo> , branch issue-5776-mission-status-contract-health-drift-ops at 9a168182d. PRs target main.
DIFF UNDER REVIEW: cd <repo> && git diff abafc135e...9a168182d -- . ':!kitty-specs'   (abafc135e = merge base with main; the diff is 85 files, +11900/-103). Read changed files in the working tree (it is at 9a168182d); use git show abafc135e:<path> for the main-side version.
PROFILE: FIRST read the profile file named below (in the checkout, under packs/built-in/agent_profiles/) and adopt its directives. Never use ~/.claude or ~/.hermes profiles. In your final summary state which profile directives/tactics you applied.
CHARTER (binding): read .kittify/charter/charter.md first, then AGENTS.md.
THE BAR (reference, NOT under review): kitty-specs/mission-status-health-drift-ops-01M464D3/{spec.md, plan.md (every operator ruling: D-P6 kind 3 honest; offline drift 200 at WP07; WP08 closure-instant and credential-handle skips; no new version, 1.0.0-SNAPSHOT), data-model.md, contracts/*.md, tracer-design-decisions.md (every ruling)}; the contract's own contracts/mission-status/ README/CHANGELOG and its lint ruleset; NFR-007 (no src/ change). kitty-specs/ itself is the bar, not under review.
ALREADY KNOWN - DO NOT RE-FILE (cite as known if you touch them): every item in <scratch>/c12-wrapup-folds.md (all folded at W-3 already; the replay-twice perf nit is accepted), plus the operator's known tool issues.

Severity rubric:
| # | Name | Meaning |
| 1 | nit | Wording/style; no effect on implementation |
| 2 | minor | Small gap; implementation would still come out right |
| 3 | moderate | Ambiguity or gap likely to cause rework inside one work package |
| 4 | high | Would produce a wrong implementation: untestable/vacuous AC, FR without coverage, contradicts existing code, tenancy/permission gap |
| 5 | critical | Charter or scope violation, breaks a stability contract, a production-safety breach, or a security/credential hazard |

SUB-AGENT RULES (verbatim, binding):
- read-only;
- no commits, no push;
- no git checkout, restore, reset, clean or stash;
- a denied command means stop and report;
- no further sub-agents;
- no pattern kills;
- set TMPDIR under the scratchpad (export TMPDIR=<scratch>/c12-squad/tmp);
- nothing left running.
Tests: if you run tests use `uv run pytest` style as the repo documents (AGENTS.md); baseline first - main carries known pre-existing red tests, a lens that files "suite is red" has found nothing. Never write into the checkout (no .pyc-committing, no generated files in the tree; use TMPDIR and PYTHONDONTWRITEBYTECODE=1). If you plant a mutation to test a claim, do it on a COPY under TMPDIR, never in the checkout.

RULES: verify every claim against the code before reporting; every finding cites evidence (artifact section and/or file:line); no finding without a concrete single remediation; do not pad - an empty list is a valid result. Terminology: Mission (never Feature).

OUTPUT: write findings to the file named below in this format (YAML, schema review-findings/v1):
schema: review-findings/v1
complete: false
phase: pr
lens_group: <group>
mission: mission-status-health-drift-ops-01M464D3
findings:
  - id: PR-<GROUP>-001   # uppercase group, sequential
    lens: <lens name>
    severity: <1-5>
    title: one line
    evidence:
      - artifact: "..."
      - code: "path:line"
    claim: what is wrong, concretely, with the failure scenario
    remediation: the single concrete change (or state the fork)
Validate with python -c "import yaml,sys;yaml.safe_load(open(sys.argv[1]))" <file>, then flip complete: true, then print a one-paragraph summary. Writing this one findings file in the squad dir is the ONLY write you may make.
