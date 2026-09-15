# Spec Kitty Charter

> Created: 2026-01-27
> Version: 1.4.0
> Updated: 2026-08-08 — activated the writing-comms & diagramming doctrine set (see "Writing, Communication & Diagramming Doctrine"; rehome-writing-comms-doctrine / PR #2918)
> Updated: 2026-07-01 — interactive charter intake (doctrine-catfooding-2196-01KWE16N)
>
> **v1.3.0 note:** retains the full v1.1.5 substance; adds the activated catfooding
> doctrine set and an interactive-intake pass that foregrounds actionable governance. `config.yaml` `activated_*` keys were
> produced by the canonical `spec-kitty charter activate --cascade all` CLI
> (DIRECTIVE_044 compliant). The interactive charter intake (2026-07-01) wired
> `directive→artifact` `suggests` edges from DIRECTIVE_043/044/045 so **all 14
> catfooding artifacts are directive-reachable and resolve in `references.yaml`**,
> and states the eight standing orders as actionable policy in the section below
> (superseding the earlier deferral-and-status framing).

## Purpose

This charter captures the technical standards, architectural principles, and development practices for Spec Kitty. All features and pull requests should align with these principles.

---

## Governing Principles

These bind every action; detail lives in the referenced doctrine and the sections below.

- **Single canonical authority.** Every rule, surface, and identity has ONE owning
  source. Reconcile (extend/reference) existing doctrine rather than add a second
  authority; prefer require-canonical + migration over no-canonical-field fallback
  branches; chase unification, not parity with a dead quirk. (Principle — reviewers
  weigh it; not an automated rejection.) → `DIRECTIVE_044`, `canonical-source-unification`.
- **Architectural alignment.** Respect the declared architecture — shared-package
  boundaries (external contract packages vs the internal runtime) and the integrity of
  module seams. New surfaces align to the existing structure, not around it.
  → `DIRECTIVE_001` (architectural-integrity), the Architecture sections below.
- **Domain-driven splits + tiered rigour.** Model bounded contexts; keep aggregates
  well-formed; apply MORE rigour to core domain logic than to glue/IO.
  → `domain-driven-design` paradigm, `tiered-standards` + `aggregate-design-rules` styleguides.
- **ATDD-first.** Drive features outside-in from acceptance criteria; the acceptance
  test is the contract. → `acceptance-test-first`, the ATDD-First Discipline section below.
- **Glossary & terminology adherence.** Use the canonical terms; keep domain language
  precise across specs, code, and docs; the terminology canon (Mission, not Feature) is
  enforced. → the Terminology Canon section below, `contextive` toolguide.

## Quality & Tech-Debt Standing Orders

Nine standing practices that keep spec-driven missions honest, now activated
doctrine (15 artifacts) and compiled into this charter. Each rule below is
binding actionable guidance; the full how-to lives in the referenced doctrine
artifact. **Throughline:** never trust a green check, a clean diff, or a confident
summary — verify against live code, witness the bug in a real run, and let
independent adversarial perspectives try to break the work *before* it lands, at
the cheapest point in the lifecycle.

1. **Adversarial squad cadence.** Run a bounded, profile-loaded adversarial squad
   at every planning point-cut (pre-spec / post-spec / post-plan / post-tasks)
   before proceeding — one lens per agent, strongest model for the hard lenses.
   Optional and advisory, never a hard gate. → `adversarial-squad-cadence` styleguide.
2. **Campsite cleaning & incremental debt paydown.** *Open* a mission/WP by
   campsite-cleaning the surfaces it will touch **first** — resolve their Sonar
   findings, extract/decompose over-long functions/files, refactor the methods
   about to change — *before* the functional change, as a tidy-first enabler
   (behavior-preserving, focused tests, a distinct preceding step; dispatch a
   campsite scout on god-surfaces). Then fold only *domain-matched* debt at each
   point-cut; freeze current offenders as a baseline when a litter class cannot be
   cleared in-mission (debt stops growing while you chip at it). → `DIRECTIVE_025`.
3. **Mission tracer files.** Seed three tracer files (tooling-friction, approach,
   design-decisions) at planning, append during implementation, assess at close —
   friction and rationale feed the next mission. → `mission-tracer-files` procedure.
4. **Test remediation & bug-fix discipline.** Judge the test, not git-blame
   (stale → re-pin, stub → delete, valid → fix the product); reproduce RED-FIRST
   through the pre-existing entry point; require live evidence over "looks fixed";
   use realistic data; never retry-to-green. → `DIRECTIVE_041`, `DIRECTIVE_034`.
5. **Architectural gate discipline.** Close defect classes by construction with a
   NON-VACUOUS call-site gate (concrete floor + self-mutation test + shrink-only
   allowlist); a gate-unmask cannot self-validate. After merge, run the full
   arch-gate sweep with a cross-base pre-existing check. → `DIRECTIVE_043`,
   `architectural-gate-non-vacuity`, `frozen-baseline-shrink-only-ratchet`,
   `post-merge-arch-gate-adjudication`.
6. **Canonical sources & unification.** Use canonical templates/skills/CLI, never
   improvise or copy an older mission; chase unification, not parity; a missing
   command is a gap to file upstream; guard the terminology canon. → `DIRECTIVE_044`,
   `canonical-source-unification`, `terminology-guard`.
7. **Git & workflow discipline.** PRs only, the programme merge agent merges;
   read intent before any high-risk op; isolate PR-touching agents in a worktree;
   no version numbers in scope. → `DIRECTIVE_045`, `pr-agent-worktree-isolation`.
8. **Mission hygiene.** Reviewer and implementer are distinct roles; every addressed
   issue gets an issue-matrix row + claim + tracker comment naming the mission;
   give implementers ownership-map leeway (no-overlap is the real guard); apply
   tiered rigour. → `planning-and-tracking` styleguide,
   `reviewer-implementer-role-separation`, `ownership-map-leeway`.
9. **Red-main & release discipline.** A red mainline is an honest signal of a
   known release-blocking (P0) defect — never green-wash it (no reverting an
   honest red, no declining a bug's reproduction test). Mainline CI status is the
   authoritative release gate: **red CI == no release**. When a P0 is filed or
   accepted, land a failing reproduction test; do not spend expensive QA or manual
   testing on a red base; work red main down as top priority. Transparency over
   convenience — it's broken, we hate it, but it's the truth, so we do not hide it.
   → `red-main-release-discipline` procedure, ADR `2026-07-17-1`.

All 15 catfooding artifacts are activated (`.kittify/config.yaml`) and
directive-reachable, so each resolves in the compiled reference set
(`references.yaml`). This section states the rules; the referenced artifacts carry
the detailed procedures, examples, and anti-patterns.

### Reconciling change-scope tensions (small diff ↔ boy-scout ↔ locality)

Three activated rules each bound the size of a change from a *different* angle, and
by design they are **not fully compatible** — the tension is real and intentionally
left unresolved at the rule level, then reconciled per-change:

- **`change-apply-smallest-viable-diff`** (tactic) minimizes the *diff itself* — the
  smallest file set and smallest edit within each file that achieves the stated goal;
  stop once the goal is met.
- **`DIRECTIVE_025` Boy Scout Rule** licenses *opportunistic in-place improvement* of
  areas you already touched — fix the failing test/lint/type error surfaced there by
  default, and at planning point-cuts fold *domain-matched* debt. This pulls the change
  *larger*.
- **`DIRECTIVE_024` Locality of Change** minimizes *blast radius* — keep edits close to
  the problem, separate opportunistic cleanup from functional work, resist scope creep.

These genuinely pull in different directions, so the default pack does **not** pick a
silent winner. `RECONCILE_CHANGE_SCOPE_TENSIONS` (directive, advisory — active) is the
single place to weigh all three on a specific change, with this resolution order:

1. **Smallest-viable-diff picks the file set and edit size first** — the minimal files
   and minimal edit for the stated goal.
2. **Boy Scout Rule then governs cleanup strictly *inside* that file set** — fix
   touched-area breakage and apply proportional tidy-up, **without adding files** to the
   set chosen in step 1.
3. **Locality of Change is the brake** — it stops either rule from *growing the file
   set*. Any extension beyond the touched area must be directly connected to the goal,
   proportional, and carry a one-line rationale (a tracker reference for anything
   genuinely broad).

Record what was folded in and what was deferred, and why, in task/review context rather
than silently picking a side. The reconciler resolves the tension for a given change; it
does **not** retire, weaken, or supersede any of the three rules — all remain
independently valid and co-activatable. Note the interaction with Standing Order #2's
*tidy-first* sequencing: an opening campsite-clean is a **distinct, behavior-preserving
step that precedes** the functional change (and may legitimately open its own surfaces
for that purpose); the reconciliation order above governs the *functional* change that
follows. → `RECONCILE_CHANGE_SCOPE_TENSIONS`, `DIRECTIVE_024`, `DIRECTIVE_025`,
`change-apply-smallest-viable-diff`.

## Agent Operating Discipline

How agents and orchestrators should work so quality and context survive long missions.

- **Model discipline.** Match model strength to the task: the strongest model for hard
  judgment — sizing, fakeability, code-truth, review, architecture — and a cheaper model
  for grounded or mechanical passes. Never run high-stakes review or design on a light
  model. → `model-task-routing`.
- **Delegate to preserve context.** Use subagents for work that can run in an isolated
  context — a work package in its own worktree, a review against a fixed diff, a focused
  investigation — so the orchestrator's context stays clean. Each delegation LOADS the
  relevant doctrine profile (not merely a persona name). Compact after task pivots; do not
  combine architecture, debugging, and implementation in one long context.
  → `autonomous-operation-protocol`.

## Collaboration Strategy

How missions are executed between the operator (human-in-command) and the agent fleet
(**SkyKitty** — see [The SkyKitty agent fleet](../../docs/development/agent-fleet.md) for the
roles and the `ready-for-squad` handshake).

- **Dispatch a governed profile to run the mission.** The operator delegates mission
  execution to a governed orchestrator; planning and tracker work runs under
  `planner-priti` (profile LOADED, not a persona name). The orchestrator **claims** the
  mission's tickets (assign the operator + a comment naming the mission), **plans**
  (spec → plan → tasks, with an adversarial squad at each planning point-cut), and
  **runs** the implement→review loop to completion.
- **Issue branch first.** Completed mission work is opened from an
  `issue-<n>-<slug>` branch as a pull request targeting `main`, with compact history.
- **Ready for squad only when complete.** The implementer runs the required tests and
  self-review, then labels the PR `ready-for-squad`; fleet agents own CI and review.
- **The merge agent merges.** Implementers never merge. → git/workflow discipline
  (`DIRECTIVE_045`), Agent Operating Discipline above.

## Governance by Workflow Action

Quick map from workflow action to the rules that bind it (load the action's doctrine
context for the detail).

- **Specify / Plan** — reconcile-don't-duplicate (check for an existing authority before
  adding one); run an adversarial squad at each planning point-cut (advisory, never a
  gate); fold only domain-matched debt; model bounded contexts with tiered rigour; assign
  no version numbers in scope.
- **Implement** — ATDD / red-first through the pre-existing entry point; close defect
  classes with non-vacuous gates; use canonical sources (no improvise); keep the
  terminology canon; append the mission tracer files.
- **Review** — reviewer ≠ implementer; run the FULL compliance suite (not a subset);
  verify no duplicate authority, no dead code, and live evidence; apply tiered rigour;
  grant ownership-map leeway (no-overlap is the real guard).
- **Merge** — PRs only, the programme merge agent merges; isolated PR-review
  agents; post-merge full arch-gate sweep with a cross-base pre-existing check;
  issue-matrix + tracker hygiene.

## Writing, Communication & Diagramming Doctrine

Activated 2026-08-08 from the built-in writing-comms doctrine set ("The Magnificent
7", rehomed via PR #2918). These rules bind agent-authored prose, documentation, and
diagrams; the full how-to lives in each referenced artifact. Enforcement levels are
noted where they bind harder than advisory.

- **Audience-oriented writing.** Any artifact meant for a human reader must name its
  target persona *before* drafting and calibrate vocabulary, detail, and structure to
  that reader — not to the author's own familiarity. Prefer persona-specific variants
  over one artifact that serves everyone and therefore no one. Pick a reader from the
  shipped persona catalog rather than inventing one ad hoc. → `DIRECTIVE_047`
  (advisory), `writing-audience-catalog` tactic (+ audience personas:
  software-engineer, line-manager, nontech-educator, automation-agent,
  agentic-framework-core-team), `plain-language` + `professional-communications`
  styleguides.
- **Documentation structure.** Builds on the already-active common-docs doctrine
  (`DIRECTIVE_042`, `common-docs` styleguide, `common-docs-*` tactics). One document is
  exactly one Divio quadrant (Tutorial / How-To / Reference / Explanation), declared in
  frontmatter; every non-decorative image/diagram carries descriptive alt text; every
  page carries an `updated: YYYY-MM-DD` freshness date (pages without one are treated
  as stale); code is the source of truth and docs mirror *shipped* behaviour (a
  doc/code disagreement is a doc defect). → `divio-type-discipline`,
  `docs-accessibility`, `docs-freshness-sla`, `publication-authority` styleguides.
- **Diagramming.** Model and reason about architecture with the C4 model's progressive
  zoom — System Context → Container → Component → Code — so each diagram serves one
  audience at one level instead of one all-in-one picture. Draw only the levels that
  earn their keep. This composes with the already-active Mermaid and PlantUML rendering
  toolguides and the `architecture-diagram-review-checklist` tactic. → `USE_C4_MODEL_TECHNIQUES`
  (lenient-adherence), `mermaid-diagramming` + `plantuml-diagramming` toolguides.
- **Communication governance.** Cite the current canonical version of any versioned
  artifact (glossary, spec, doctrine, released document), never a cached/stale copy —
  stale analysis is confidently wrong, not merely lower-quality. A specialist agent
  opens with a short role/scope declaration so a mismatch can be caught early.
  Authentication credentials (tokens, keys, passwords, session cookies) must never be
  logged, echoed, or written into output, errors, or artifacts. → `DIRECTIVE_048`
  version-governance (**required**), `DIRECTIVE_049` agent self-introduction (advisory),
  `DIRECTIVE_050` credential-handling (**required**).
- **Supporting workflows.** Run continuous term capture/triage against the living
  glossary so terminology drift is caught early rather than in a big periodic cleanup;
  every factual claim in a research output is traceable to a named source (an unsourced
  claim is a hypothesis and must be labelled one). → `glossary-maintenance-workflow`
  procedure, `research-citation-discipline` styleguide.
- **Charter-blessed profiles.** The writing-comms specialist profiles are activated for
  governed delegation: `comms-cleo` (professional communications), `diagram-daisy`
  (diagramming), `analyst-annie` (analysis), `lexical-larry` (glossary/terminology),
  `minutes-maker-mahad` (meeting minutes), `scribe-sally` (documentation), and
  `synthesizer-sam` (synthesis). The meeting-minutes format styleguide and pipeline
  procedure were intentionally left un-activated.

## Technical Standards

### Languages and Frameworks

**Python 3.11+** is required for all CLI and library code.

**Key dependencies:**
- **typer** - CLI framework
- **rich** - Console output
- **ruamel.yaml** - YAML parsing (frontmatter)
- **pytest** - Testing framework
- **mypy** - Type checking (strict mode)

### Testing Requirements

- **pytest** with **90%+ test coverage** for new code
- **mypy --strict** must pass (no type errors)
- **Integration tests** for CLI commands
- **Unit tests** for core logic
- **Run only the affected test packages, not the full suite, whenever the change is scoped to a known surface.** The repository's test suite has ~17,000 tests and a full run is expensive in wall-clock time and orchestrator context budget. Per-WP and per-PR validation should target the directories that bound the change (e.g., `tests/specify_cli/audit/` for an audit-detector change, `tests/specify_cli/cli/commands/test_sync*.py` for a sync surface change). The full `pytest tests/` gate is reserved for: (a) post-merge mission-level validation against the merged mission branch, (b) explicit cross-cutting changes that touch shared infrastructure, and (c) release-candidate verification. Each WP must declare its targeted test surface in the WP prompt's validation section so reviewers can confirm scope.

### Performance and Scale

- CLI operations must complete in **< 2 seconds** for typical projects
- Dashboard must support **100+ work packages** without lag
- Git operations should be efficient (no unnecessary clones/checkouts)

### Deployment and Constraints

- **Cross-platform:** Linux, macOS, Windows 10+
- **Python 3.11+** (no legacy Python 2 support)
- **Git required** (all worktree features depend on Git)
- **PyPI distribution** via automated release workflow

---

## Architecture: Shared Package Boundaries

### External Contract Packages

`spec-kitty-events` and `spec-kitty-tracker` are true external package dependencies for the Spec Kitty CLI. Treat them like normal third-party Python libraries with Spec Kitty-owned governance:

- Consume released PyPI packages through the normal dependency graph.
- Do not vendor their source into the CLI package.
- Do not commit path dependencies, editable installs, or moving branch refs for production or release builds.
- Use SemVer-compatible dependency ranges in library/package metadata where compatibility allows; keep exact artifact resolution in lockfiles and release records.
- Validate cross-repo behavior with consumer tests and compatibility fixtures rather than forcing every sibling package to release in lockstep.

`spec-kitty-events` owns event envelopes, payload schemas, committed fixtures, replay helpers, and event compatibility rules.

`spec-kitty-tracker` owns tracker provider abstractions, hosted discovery/sync primitives, normalized tracker models, and tracker authority policy behavior.

### Internal Runtime Boundary

Mission runtime behavior is CLI-owned implementation code, not an external shared dependency for the CLI release path.

- Runtime code used by `spec-kitty next` and mission execution should live inside this repository.
- CLI runtime code may consume `spec-kitty-events` and `spec-kitty-tracker` as external package contracts where needed.
- The CLI must not require the standalone `spec-kitty-runtime` PyPI package at runtime.
- Do not add release gates that require publishing `spec-kitty-runtime` before the CLI can ship.
- If SaaS needs analogous mission execution behavior, establish an explicit SaaS-owned boundary or a new shared contract through a reviewed issue before reintroducing a shared runtime package.

### Development Workflow Requirements

For external package contract changes:

1. Change the owning package repository first.
2. Publish or prepare a versioned package artifact with compatibility notes.
3. Update CLI dependency constraints or lockfiles to consume that artifact.
4. Run CLI consumer tests that cover the changed contract.
5. Do not merge temporary path, git, branch, or editable-install overrides.

---

## Architecture: Branch and Release Strategy

### Current Branch Strategy (3.x)

**Active development** happens on `main`. The current version is **3.x** (3.1.0a3+).

**Branch layout:**
- **`main`** — Active development. All new features, bug fixes, and releases target `main`.
- **`remotes/origin/1.x-maintenance`** — Historical. The 1.x local-only CLI is in maintenance mode. Only security and critical bug fixes are accepted.

The former `2.x` branch was merged into `main` when the SaaS transformation reached maturity. There is no separate `2.x` branch.

### Release Versioning

- **3.x** — Current active version. Event sourcing, sync protocol, mission identity model, spec-kitty-events integration.
- **1.x** — Historical maintenance branch. YAML activity logs, local-only operation, no spec-kitty-events dependency.

### Development Principles

- All new features target `main`
- Breaking changes are allowed during pre-release alpha/beta cycles
- The `spec-kitty agent mission branch-context --json` command resolves the deterministic branch contract for any feature
- Do not hardcode branch names in templates or scaffolding; use the resolved branch context

### Programme PR Workflow

**All changes must land on `main` through a pull request. Direct pushes to `main` are never allowed — not for mission merges, hotfixes, doc updates, or any other reason.**

Nothing on GitHub enforces this workflow: there is no branch protection or required
review. The leftover workflow files still run and post check results, but nothing
requires them to pass — a failing run has no power to block a PR. The binding process is
[`EXPERIMENTAL-spec-kitty-planning/PROGRAM.md`](https://github.com/spec-kitty/EXPERIMENTAL-spec-kitty-planning/blob/main/PROGRAM.md)
§5–§9.

### Agent Push Authorization (binding)

Agents are **not allowed** to push directly to `origin/main` under any circumstances. This includes `spec-kitty merge`.

**Required workflow for mission merges:**
1. Run `spec-kitty merge` locally — this merges lane branches into local `main`.
2. Create the ticket branch: `git checkout -b issue-<n>-<slug>`
3. Push it: `git push origin issue-<n>-<slug>`
4. Open a PR targeting `main`: `gh pr create --title "..." --body "..."`
5. Do **not** merge it; the programme merge agent owns that step.

**Required workflow for all other changes (hotfixes, docs, config):**
1. Start work on a named branch, never on `main` directly.
2. Push the branch and open a PR.
3. Never push `main` directly.

**When `safe_commit` refuses on a locally guarded branch, agents must:**
1. Use the mission lane branch/worktree as intended by the workflow.
2. If planning artifacts need to land on `main`, create an `issue-<n>-<slug>` branch instead of bypassing the guard.
3. Never silently work around the guard with raw git commands or `SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS=1`.

### Historical Context

The 1.x/2.x branch split was originally documented in [ADR-12: Two-Branch Strategy for SaaS Transformation](../../docs/adr/2.x/2026-01-27-12-two-branch-strategy-for-saas-transformation.md). That strategy served its purpose during the SaaS transformation and is now superseded by single-branch development on `main`.

---

## Code Quality

### Pull Request Requirements

- Use the exact PR body sections from programme `PROGRAM.md` §5.
- Run the implementer tests from §6 and label complete work `ready-for-squad`.
- Implementers never merge; the fleet owns CI, squad review, and merge.

**Readable and consistent PRs are binding** (directive `046-readable-consistent-prs`, active). Every mission branch / PR an agent hands the operator must be:

- **Linear** — rebased onto the current upstream base and compacted into a small set of logically-sliced commits (rebase over merge; a non-reordering, behaviour-preserving snapshot chain per the `clean-linear-commit-history` tactic, never an interactive reorder).
- **Consistent / complete** — the intended scope is finished; only genuinely high-effort / mission-sized work is deferred, and only as a tracked follow-up with a rationale.
- **Independently reviewed** — the aggregate diff has had an independent review before, or in parallel to, opening the draft PR, with real findings folded in while it is still a draft; an adversarial review squad is the recommended mechanism (not a mandated gate).

The standing close-out sequence that produces such a PR — accept → resolve issue verdicts → aggregate review squad → local merge → compact history → rebase onto upstream → draft PR + pre-merge squad → hand off — is captured as the `mission-wrap-up-sequence` procedure (active). The operator, not the agent, performs the mainline merge (`045-prs-only-and-read-intent`).

### Code Review Checklist

- Tests added for new functionality
- Type annotations present (mypy --strict passes)
- Docstrings for public APIs
- No security issues (credentials, secrets handling)
- Breaking changes documented in CHANGELOG.md

### Quality Gates

- Required pytest surface passes (targeted packages for scoped changes; full suite only for the cases named in Testing Requirements)
- Type checking passes (mypy --strict)
- No regressions in existing functionality
- Documentation updated (README, CLI help text)

### Documentation Standards

- **CLI commands:** Help text must be clear and include examples
- **Public APIs:** Docstrings with parameter types and return values
- **Breaking changes:** Update migration guide in docs/
- **Architecture decisions:** Capture in ADRs (architecture/decisions/)

### Branch-Intent Terminology Governance

- Use **`repository root checkout`** for the non-worktree checkout where planning commands run.
- Use **`current branch`**, **`target branch`**, **`planning_base_branch`**, and **`merge_target_branch`** for branch semantics.
- Do **not** use **`main repository`**, **`main repo`**, or **`main repository root`** in user-facing docs or prompts.
- Do **not** use **`main`** as a generic default branch name. Only use `main` when the actual branch is `main`.
- When a document needs to talk about location and branch in the same sentence, name both explicitly instead of implying one from the other.

### Identifier Safety Rules

1. Database names, lane identifiers, and other storage-facing slugs generated from user, branch, lane, mission, or tracker input must remain ASCII-only and deterministic. Sanitizers must use an explicit ASCII allowlist such as `[A-Za-z0-9_]` or opt Python regular expressions into ASCII semantics with `re.ASCII`; do not rely on default Unicode `\w` or `\W` behavior for database-safe identifiers.
2. Any change to identifier normalization or slug sanitization must include regression coverage for non-ASCII input, including at least one accented Latin example and one case that proves the produced storage identifier is `.isascii()`.

---

## User Customization Preservation

### Ownership Boundaries for Mutating Flows

- This section governs **Spec Kitty development itself**. It is a maintainer rule for the Spec Kitty codebase and release process; it is not a substitute for end-user project charters, which users generate for their own repositories.
- Package-owned mutation flows (`init`, `upgrade`, install/remove/sync commands, shipped-asset refresh, and migrations) must treat user-authored custom commands, custom skills, and project overrides as **user-owned assets** by default.
- No mutating flow may overwrite, delete, rename, or chmod a user-owned customization unless the exact path is explicitly package-managed or manifest-tracked.
- Name-based heuristics alone are not sufficient proof of package ownership. Historical broad matching of `spec-kitty.*` command names has created a real risk of clobbering user-authored slash commands that were never shipped by Spec Kitty.
- When package-managed files share a directory with user-authored files, cleanup and migration logic must scope destructive changes only to known package-owned paths and leave unknown or third-party files untouched.
- If ownership cannot be proven from manifest data or an explicit managed-path contract, the safe behavior is to preserve the file and emit a warning instead of deleting or rewriting it.

### Proof Trail

- `src/specify_cli/runtime/merge.py` already encodes the intended ownership model for runtime assets: package-managed paths may be refreshed, while user-owned data must be preserved.
- `src/specify_cli/skills/command_installer.py` already codifies the same boundary for shared skills roots: third-party paths under `.agents/skills/` are never touched unless they are manifest-owned.
- `src/specify_cli/upgrade/migrations/m_3_1_2_globalize_commands.py` is the motivating hazard: broad `spec-kitty.*` filename matching can incorrectly classify user-authored custom slash commands as shipped assets and remove them.
- Any future migration, installer, or cleanup path that mutates user-visible command or skill directories must document its ownership proof and show why it cannot hit custom user files.

---

## Local Docker Development Governance (`spec-kitty-saas`)

When work in this program touches the SaaS repository, all contributors and agents must use a two-mode Docker workflow:

1. **`dev-live` mode** for active implementation loops
- Live code volumes
- Django autoreload
- Vite dev server
- Primary commands: `make docker-app-up-live`, `make docker-app-down-live`

2. **`prod-like` mode** for pre-merge and pre-deploy validation
- Image-based parity stack
- Primary commands: `make docker-app-up`, `make docker-auth-check`, `make docker-app-down`

Mandatory gate:
- A `prod-like` authenticated preflight must pass before considering SaaS integration work complete.

Operational reference:
- `spec-kitty-saas/docs/docker-development-modes.md` (sibling SaaS repo checkout)

---

## Central CLI-SaaS API Contract

- The published current-state CLI↔SaaS contract lives at `../spec-kitty-saas/contracts/cli-saas-current-api.yaml`.
- Any CLI change that alters hosted routes, request/response bodies, auth headers, websocket behavior, sync payloads, or tracker control-plane semantics must update that contract in the same change.
- ADRs, PRDs, and roadmap notes may describe future APIs, but the authoritative reference for what the CLI actually speaks to SaaS today is that contract file.

---

## Tracker Ticket Assignment Rule

1. When an agent starts implementing work from a tracker-backed issue for this repository, the agent must assign that ticket to the Human-in-Charge (HiC) before or as part of beginning the implementation. For Spec Kitty today, GitHub issues are the active tracker case and must follow this rule.

## Pre-existing Failure Reporting Rule

1. When an agent encounters pre-existing test failures while working in this repository, the agent MUST open a GitHub issue reporting them before treating those failures as accepted baseline context or continuing past them. The issue must include the command run, the relevant failure summary, and why the agent believes the failures are pre-existing rather than introduced by its current change.

---

## Governance

### Amendment Process

Any maintainer can propose amendments via pull request. Changes are discussed and merged following standard PR review process.

**For major architectural changes:**
1. Write ADR (Architecture Decision Record)
2. Open PR with ADR + implementation
3. Discuss trade-offs and alternatives
4. Merge after review

### Compliance Validation

Code reviewers validate compliance during PR review. Charter violations should be flagged and addressed before merge.

### Exception Handling

Exceptions discussed case-by-case. Strong justification required.

**If exceptions become common:** Update charter instead of creating more exceptions.

---

## Attribution

**Spec Kitty** is inspired by GitHub's [Spec Kit](https://github.com/github/spec-kit). We retain the original attribution per the Spec Kit license while evolving the toolkit under the Spec Kitty banner.

**License:** MIT (All Rights Reserved for Priivacy AI code)

---

## Terminology Canon (Mission vs Feature)

- Canonical product term is **Mission** (plural: **Missions**).
- `Feature` / `Features` are prohibited in canonical, operator, and user-facing language for active systems.
- Hard-break policy: do not introduce or preserve `feature*` aliases (API/query params, routes, fields, flags, env vars, command names, or docs) when the domain object is a Mission.
- Use `Mission` / `Missions` as the only canonical term in active codepaths and interfaces.
- Historical archived artifacts may retain legacy wording only as immutable snapshots and must be explicitly marked legacy.

### Regression Vigilance (2026-04-06)

The `--feature` → `--mission` rename has been a persistent source of regressions. Mission 065 swept ~45 user-facing references, but the pattern keeps recurring because:
1. New code copies from old code that still uses `feature` as variable names (the internal Python parameter name is `feature` even when the CLI flag is `--mission`)
2. Error messages and guidance strings are written ad-hoc without checking the canon
3. Subagent-implemented code may not see this charter

**Hyper-vigilance rules:**
- Every PR that adds a new `typer.Option` or `argparse.add_argument` for a mission slug MUST use `--mission` as the primary name. `--feature` is only acceptable as a hidden secondary alias.
- Every PR that adds an error message mentioning a CLI flag MUST reference `--mission`, not `--feature`.
- Every PR that adds a command example in templates or docstrings MUST use `--mission`.
- Code reviewers MUST grep for `--feature` in new/changed lines and reject any non-alias usage.
- The upstream contract at `src/specify_cli/core/upstream_contract.json` lists `--feature` as a **forbidden CLI flag** for new code. This is authoritative.

---

## Charter Resolution Hints

These declarations are read by `spec-kitty charter sync` (per FR-007 / FR-008 of mission
`wp-prompt-governance-payload-01KRR8HS`). They drive the action-scoped governance
resolver so that `spec-kitty charter context --action <name>` does not need to fall
back to runtime defaults. Keep this block up to date as the project adopts new
template sets, tools, or authority directories.

```yaml
template_set: software-dev-default
available_tools: [git, spec-kitty, pytest, mypy, ruff]
authority_paths:
  # Common Docs fold complete: legacy homes dropped, canonical new homes only
  # (matches charter.yaml/governance.yaml; keeps `charter sync` idempotent).
  - docs/context/             # canonical terminology (FR-009)
  - docs/adr/3.x/             # canonical architectural decisions
```

---

## Burn-down Policy (binding per HiC §5a.2 / C-004)

(a) Every mutable architectural allowlist is governed by a baseline in
`tests/architectural/_baselines.yaml`. Growth above baseline **FAILS CI**;
shrinkage WARNS (informational, non-fatal).

(b) `test_no_dead_modules._CATEGORY_7_GRANDFATHERED` (Cat-7) shrinks by ≥2
entries per major release; **target 0 by 4.0**.

(c) Pure-shim files (`test_compat_shims._ADAPTER_FILES`) **target 0 by 4.0**.

---

## `__all__` Declaration Convention (binding per C-007)

Every module under `src/charter/` and `src/kernel/` MUST declare `__all__`.
The symbol-level dead-code gate (`tests/architectural/test_no_dead_symbols.py`)
walks `__all__` and asserts every name has at least one caller in `src/`.

Future expansion to other subpackages is a per-mission scope decision.

---

## ATDD-First Discipline (binding per C-011)

Every implementation work package follows the red-green-refactor cycle.
The WP cannot start coding until at least one failing-first ATDD test
exists that pins the user-observable behaviour the WP delivers. The ATDD
test is committed as a separate commit (often the first commit of the lane)
**BEFORE** any implementation commits.

The reviewer verifies red→green: the test was RED on the WP's
`planning_base_branch` AND GREEN on the WP's final commit.

This mirrors Mission B's executable-contract pattern (the 7-file ATDD spec
at `bd95f1f5` was the canonical contract).
