export const meta = {
  name: 'test-suite-speedup',
  description: 'Deep audit of the pytest suite for speed with no coverage loss: inventory cost drivers, apply 3 expert lenses, adversarially verify each change is coverage-safe, synthesize a ranked plan',
  phases: [
    { title: 'Inventory', detail: 'Fan out across test clusters + CI timing to profile cost drivers, dead/duplicate tests, fixture topology' },
    { title: 'Lenses', detail: 'Randy Reducer (reduction), Architect Alphonso (architecture+local parallelism), Paula Patterns (recurring anti-patterns)' },
    { title: 'Verify', detail: 'Adversarially confirm each high-value change loses NO coverage quality' },
    { title: 'Synthesize', detail: 'One ranked remediation plan: safe-now vs follow-up, with owners and required tests' },
  ],
}

// ---------------------------------------------------------------------------
// Shared context handed to every agent so they share one mental model.
// ---------------------------------------------------------------------------
const REPO = '/Users/robert/spec-kitty-dev/spec-kitty-20260614-181143-WQFQqN/spec-kitty'
const SHARED = `
You are auditing the pytest test suite of Spec Kitty (a Python CLI) at ${REPO}.
GOAL: make the suite run MUCH faster — both in GitHub CI and on a developer laptop —
with ZERO loss of coverage quality. "Coverage quality" = the set of real behaviors,
regressions, and assertion paths the suite actually guards. Speed must never be bought
by deleting a genuine assertion path or weakening a real regression guard.

GROUND TRUTH ALREADY ESTABLISHED (do not re-derive, build on it):
- ~1457 test files under tests/. 33 conftest.py files, ~4730 lines of fixtures total.
- CI = .github/workflows/ci-quality.yml (~113KB), split into ~20 jobs:
  * Per-directory "fast" shards: kernel, doctrine, sync, merge, missions, post_merge,
    release, status, review, next, lanes, dashboard, upgrade, cli — these run pytest
    with "-m 'fast and not windows_ci'" SINGLE-PROCESS (NO -n auto).
  * "integration-tests-core-misc" matrix shards (architectural, integration,
    specify-cli-heavy, specify-cli-rest, auth-audit-git) DO use "-n auto --dist loadfile --durations=50".
  * Plus slow/timing/distribution/clean-install jobs.
- The local dev command is plain "pytest tests/" or "PWHEADLESS=1 pytest tests/" with
  NO -n auto (see CLAUDE.md) — so locally the whole suite runs single-process.
- Cost drivers measured across the suite: 315 files use subprocess (subprocess.run/Popen/etc),
  233 files do real "git init"/Repo.init, 236 files use CliRunner, 1056 use tmp_path, 32 time.sleep calls.
- Markers: fast(37), integration(40), git_repo(38), slow(27), windows_ci(36), asyncio(163),
  parametrize(483). pytest-xdist IS already a dependency. test_venv is a session-scoped autouse fixture.
- Tooling: pytest>=9, pytest-xdist, pytest-asyncio, pytest-cov, pytest-timeout, respx, pytestarch.

HOW TO WORK (the venv is ALREADY WARM at ${REPO}/.venv — do NOT re-sync):
- Prefer STATIC analysis (read files, grep) and CHEAP targeted commands.
- You MAY run fast, scoped commands: "${REPO}/.venv/bin/pytest <dir> --collect-only -q",
  "... --durations=25 -p no:cacheprovider" on a SMALL directory, or grep/ast scans.
- NEVER run the whole suite. NEVER run anything that takes >60s. Time-box hard.
- Cite concrete evidence: file path + line/symbol. No vague "some tests are slow".
- Be honest about uncertainty and coverage risk. A fast test that guards a real bug stays.
`

const INVENTORY_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['cluster', 'file_count_estimate', 'cost_drivers', 'dead_or_duplicate', 'fixture_observations', 'speedup_candidates', 'notes'],
  properties: {
    cluster: { type: 'string' },
    file_count_estimate: { type: 'integer' },
    cost_drivers: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['kind', 'evidence', 'impact', 'est_seconds_or_scale'],
        properties: {
          kind: { type: 'string', description: 'subprocess_cli | real_git | sleep_wait | no_xdist | heavy_session_setup | wheel_build | network | redundant_io | other' },
          evidence: { type: 'string', description: 'file path + line/symbol' },
          impact: { type: 'string', enum: ['high', 'medium', 'low'] },
          est_seconds_or_scale: { type: 'string' },
        },
      },
    },
    dead_or_duplicate: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['file', 'what', 'reason', 'confidence'],
        properties: {
          file: { type: 'string' },
          what: { type: 'string', description: 'test name or group' },
          reason: { type: 'string', description: 'why dead/duplicate/over-parametrized' },
          confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
        },
      },
    },
    fixture_observations: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['fixture', 'observation', 'opportunity'],
        properties: {
          fixture: { type: 'string' },
          observation: { type: 'string' },
          opportunity: { type: 'string', description: 'e.g. raise scope to session/module, share across conftests, replace real-git with cached template' },
        },
      },
    },
    speedup_candidates: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['title', 'kind', 'target', 'est_speedup', 'risk', 'coverage_safe'],
        properties: {
          title: { type: 'string' },
          kind: { type: 'string', description: 'parallelize | fixture_scope | subprocess_to_inprocess | git_fixture_cache | dedupe | delete_dead | shard_rebalance | marker_fix | other' },
          target: { type: 'string', description: 'files/dirs affected' },
          est_speedup: { type: 'string' },
          risk: { type: 'string', enum: ['low', 'medium', 'high'] },
          coverage_safe: { type: 'string', description: 'why this does not lose coverage quality, or what must be checked' },
        },
      },
    },
    notes: { type: 'string' },
  },
}

const LENS_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['persona', 'headline', 'recommendations', 'open_risks'],
  properties: {
    persona: { type: 'string' },
    headline: { type: 'string', description: 'one-sentence thesis' },
    recommendations: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['id', 'title', 'rationale', 'affected_scope', 'est_speedup', 'effort', 'risk', 'coverage_safety', 'release_safe_now'],
        properties: {
          id: { type: 'string' },
          title: { type: 'string' },
          rationale: { type: 'string' },
          affected_scope: { type: 'string', description: 'concrete files/dirs/CI jobs' },
          est_speedup: { type: 'string', description: 'quantified where possible (e.g. ~Nx on shard X, ~Ns saved)' },
          effort: { type: 'string', enum: ['S', 'M', 'L', 'XL'] },
          risk: { type: 'string', enum: ['low', 'medium', 'high'] },
          coverage_safety: { type: 'string', description: 'argument that coverage quality is preserved + what must be verified' },
          release_safe_now: { type: 'boolean', description: 'true = mechanical/low-risk, ship now; false = needs a scoped follow-up' },
        },
      },
    },
    open_risks: { type: 'array', items: { type: 'string' } },
  },
}

const VERDICT_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['rec_id', 'coverage_preserving', 'speedup_credible', 'verdict', 'reasoning', 'required_safeguards'],
  properties: {
    rec_id: { type: 'string' },
    coverage_preserving: { type: 'boolean' },
    speedup_credible: { type: 'boolean' },
    verdict: { type: 'string', enum: ['accept', 'accept_with_safeguards', 'reject'] },
    reasoning: { type: 'string' },
    required_safeguards: { type: 'array', items: { type: 'string' }, description: 'tests/checks that must accompany the change' },
  },
}

// ---------------------------------------------------------------------------
// PHASE 1 — Inventory. Fan out across balanced clusters + one CI-timing scout.
// ---------------------------------------------------------------------------
phase('Inventory')

const CLUSTERS = [
  { label: 'specify_cli-cli', dirs: 'tests/specify_cli/cli tests/specify_cli/invocation tests/specify_cli/decisions tests/specify_cli/ownership tests/specify_cli/widen tests/specify_cli/agent_utils' },
  { label: 'specify_cli-upgrade', dirs: 'tests/specify_cli/upgrade tests/specify_cli/migration tests/specify_cli/compat tests/specify_cli/skills tests/specify_cli/tool_surface tests/specify_cli/bulk_edit' },
  { label: 'specify_cli-core', dirs: 'tests/specify_cli/core tests/specify_cli/coordination tests/specify_cli/status tests/specify_cli/missions tests/specify_cli/next tests/specify_cli/doctrine tests/specify_cli/lanes tests/specify_cli/runtime tests/specify_cli/session_presence tests/specify_cli/integration tests/specify_cli/dossier tests/specify_cli/saas_client tests/specify_cli/charter_preflight tests/specify_cli/context tests/specify_cli/tasks' },
  { label: 'charter', dirs: 'tests/charter' },
  { label: 'integration', dirs: 'tests/integration' },
  { label: 'doctrine', dirs: 'tests/charter_offering tests/doctrine_synthesizer' },
  { label: 'sync', dirs: 'tests/sync' },
  { label: 'agent', dirs: 'tests/agent' },
  { label: 'architectural+auth', dirs: 'tests/architectural tests/auth' },
  { label: 'upgrade+status', dirs: 'tests/upgrade tests/status' },
  { label: 'cli+runtime+missions', dirs: 'tests/cli tests/runtime tests/missions tests/mission_runtime tests/mission_metadata tests/mission' },
  { label: 'midtier-flows', dirs: 'tests/contract tests/next tests/lanes tests/retrospective tests/merge tests/git_ops tests/git tests/cross_branch' },
  { label: 'support+grabbag', dirs: 'tests/test_dashboard tests/dashboard tests/tasks tests/release tests/core tests/kernel tests/dossier tests/glossary tests/docs tests/audit tests/review tests/reviews tests/init tests/readiness tests/policy tests/cli_gate tests/cross_cutting tests/unit tests/regressions tests/regression tests/e2e tests/research tests/migration tests/migrate tests/adversarial tests/saas tests/post_merge tests/paths tests/doctor tests/calibration tests/perf tests/packaging tests/concurrency tests/stress tests/tracker tests/prompts tests/lint tests/context tests/architecture' },
]

const inventoryThunks = CLUSTERS.map((c) => () =>
  agent(
    `${SHARED}

YOUR CLUSTER: "${c.label}" — these directories: ${c.dirs}

Rigorously profile EVERY test file in your cluster. For each directory:
1. Run "${REPO}/.venv/bin/pytest ${c.dirs.split(' ')[0]} --collect-only -q 2>/dev/null | tail -5" style cheap probes to size it (scope to one dir at a time; skip dirs that don't exist).
2. grep for cost drivers in YOUR dirs only: subprocess, "git init"/Repo.init, time.sleep,
   CliRunner, wheel/build, network/httpx (un-mocked), large @pytest.mark.parametrize sets,
   per-test fixture work that could be session/module scoped.
3. Identify DEAD tests (skipped-forever, xfail-always, testing removed code, tautological
   asserts), DUPLICATE tests (same behavior asserted in multiple files), and OVER-PARAMETRIZED
   tests (dozens of cases where a handful prove the contract) — but only flag deletion/merge
   when you can argue NO real coverage is lost.
4. Note fixtures used and whether they rebuild expensive state (git repos, venvs, projects)
   that could be cached, shared, or scope-raised. These tests are NOT marked with -n xdist
   in their CI fast-shard, so note whether they are parallel-SAFE (no shared cwd/global state/db).

Return findings as the structured object. Be concrete (file:line). Quantify impact where you can.`,
    { label: `inv:${c.label}`, phase: 'Inventory', schema: INVENTORY_SCHEMA }
  )
)

// CI timing scout: pull the real --durations tables from the most recent green CI run.
const timingThunk = () =>
  agent(
    `${SHARED}

YOU ARE THE CI TIMING SCOUT. Ground the whole audit in REAL measured timing, not guesses.
1. Find the most recent SUCCESSFUL ci-quality.yml run:
   "gh run list --workflow=ci-quality.yml --status=success --limit=5 --json databaseId,createdAt,displayTitle"
2. For that run, list jobs and their elapsed durations:
   "gh run view <id> --json jobs -q '.jobs[] | {name, startedAt, completedAt, conclusion}'"
   Compute each job's wall-clock minutes; identify the LONGEST jobs (the critical path).
3. The integration shards emit "--durations=50". Pull a couple of the slowest jobs' logs and
   extract ONLY the "slowest durations" tables:
   "gh run view --job=<jobId> --log 2>/dev/null | grep -iE 's call|slowest|====.*slowest|[0-9]+\\.[0-9]+s (call|setup)' | head -80"
   Capture the slowest individual TESTS by name + seconds.
4. If gh is unavailable or rate-limited, say so explicitly and fall back to static reasoning.

Report as the inventory schema with cluster="ci-timing": put the longest JOBS and slowest
TESTS into cost_drivers (kind=other, evidence=job/test name, est_seconds_or_scale=measured),
and put "critical path" observations + which jobs dominate wall-clock into notes.
This is the single most important grounding input — be precise with numbers.`,
    { label: 'inv:ci-timing', phase: 'Inventory', schema: INVENTORY_SCHEMA }
  )

const inventory = (await parallel([timingThunk, ...inventoryThunks])).filter(Boolean)

// Compact the inventory into a digest string the lens agents can consume.
const digest = inventory.map((r) => {
  const drivers = (r.cost_drivers || []).map((d) => `   - [${d.impact}] ${d.kind}: ${d.evidence} (${d.est_seconds_or_scale})`).join('\n')
  const dead = (r.dead_or_duplicate || []).map((d) => `   - ${d.confidence}: ${d.file} :: ${d.what} — ${d.reason}`).join('\n')
  const fix = (r.fixture_observations || []).map((f) => `   - ${f.fixture}: ${f.observation} -> ${f.opportunity}`).join('\n')
  const cand = (r.speedup_candidates || []).map((s) => `   - [${s.risk}] ${s.title} (${s.kind}) ~${s.est_speedup} | safe: ${s.coverage_safe}`).join('\n')
  return `### CLUSTER ${r.cluster} (~${r.file_count_estimate} files)
 COST DRIVERS:\n${drivers || '   (none)'}
 DEAD/DUPLICATE:\n${dead || '   (none)'}
 FIXTURES:\n${fix || '   (none)'}
 SPEEDUP CANDIDATES:\n${cand || '   (none)'}
 NOTES: ${r.notes || ''}`
}).join('\n\n')

log(`Inventory complete: ${inventory.length} cluster reports gathered.`)

// ---------------------------------------------------------------------------
// PHASE 2 — Three expert lenses, in parallel, over the full digest.
// ---------------------------------------------------------------------------
phase('Lenses')

const lensThunks = [
  () => agent(
    `${SHARED}

ADOPT THE PERSONA: Randy Reducer — semantic compression. "Fewer tests/lines, same proven behavior."
You map what MUST NOT change (the protected behavioral envelope), then remove only redundancy
that EVIDENCE shows is redundant. You prize small diffs and verification over intuition. You do
NOT expand scope or do cosmetic cleanup, and you NEVER delete unverified.

Using the cluster inventory digest below, produce the REDUCTION lens:
- Dead tests safe to delete (with the evidence that nothing real is lost).
- Duplicate/overlapping tests safe to merge (same assertion path covered elsewhere).
- Over-parametrized tests where a representative subset proves the same contract.
- Redundant setup/IO inside tests that can be removed without weakening assertions.
For EACH recommendation: quantify the speedup, state effort/risk, and give an explicit
coverage_safety argument. Mark release_safe_now=true only for mechanical, obviously-safe removals.

CLUSTER INVENTORY DIGEST:
${digest}`,
    { label: 'lens:randy-reducer', phase: 'Lenses', schema: LENS_SCHEMA, model: 'opus' }
  ),
  () => agent(
    `${SHARED}

ADOPT THE PERSONA: Architect Alphonso — system architecture & design. You design the test
suite's execution architecture; you do NOT write the implementation patches.

Using the cluster inventory digest below, produce the ARCHITECTURE lens, centered on
PARALLELISM and STRUCTURAL speed. Explicitly answer the operator's two questions:
  (A) Can the per-directory CI "fast" shards (currently single-process, NO -n auto) be
      parallelized with pytest-xdist "-n auto --dist loadfile"? Which are parallel-SAFE vs
      which share cwd/global singletons/SQLite queue/git state and would need isolation first?
  (B) When run LOCALLY ("pytest tests/" with no -n), CAN the suite be parallelized across
      multiple processes? What exactly blocks it today (autouse session fixtures, shared
      tmp/db/cwd, ordering deps), what is the recommended local invocation (e.g. "-n auto
      --dist loadfile -p no:cacheprovider"), and what guardrails make it deterministic?
Also cover: fixture scope architecture (session/module promotion, especially git-repo and
project-scaffold and venv fixtures), CI shard rebalancing for critical-path reduction,
subprocess-CLI -> in-process CliRunner conversions as a structural pattern, and a cached/
templated git-repo fixture to replace 233 real "git init" calls.
For EACH recommendation quantify est_speedup, effort, risk, and coverage_safety.

CLUSTER INVENTORY DIGEST:
${digest}`,
    { label: 'lens:architect-alphonso', phase: 'Lenses', schema: LENS_SCHEMA, model: 'opus' }
  ),
  () => agent(
    `${SHARED}

ADOPT THE PERSONA: Paula Patterns — architecture scout. You detect RECURRING, systemic
patterns (boundary leaks, whack-a-field repetition) rather than one-off defects, and you
SEPARATE what must ship now from what belongs in a scoped follow-up architecture issue.

Using the cluster inventory digest below, produce the RECURRING-ANTI-PATTERN lens:
- The cross-cutting patterns that appear again and again and dominate cost: e.g. subprocess
  CLI where in-process would do (315 files), real "git init" where a cached template repo
  would do (233 files), time.sleep polling where event/condition waits would do, duplicated
  near-identical fixtures across 33 conftests, autouse fixtures taxing every test.
- For each pattern: estimate suite-wide impact, give the smallest SAFE release action now,
  and define the scoped long-term follow-up (with explicit non-goals) so it isn't whack-a-mole.
For EACH recommendation quantify est_speedup, effort, risk, coverage_safety, and set
release_safe_now to separate now-vs-later.

CLUSTER INVENTORY DIGEST:
${digest}`,
    { label: 'lens:paula-patterns', phase: 'Lenses', schema: LENS_SCHEMA, model: 'opus' }
  ),
]

const lenses = (await parallel(lensThunks)).filter(Boolean)
const allRecs = lenses.flatMap((l) => (l.recommendations || []).map((r) => ({ ...r, persona: l.persona })))
log(`Lenses complete: ${allRecs.length} recommendations across ${lenses.length} personas.`)

// ---------------------------------------------------------------------------
// PHASE 3 — Adversarial coverage-safety verification of every recommendation.
// Default to skepticism: a change that MIGHT lose a real assertion path is rejected.
// ---------------------------------------------------------------------------
phase('Verify')

const verified = await parallel(allRecs.map((rec) => () =>
  agent(
    `${SHARED}

You are an ADVERSARIAL coverage-safety verifier. Your job is to TRY TO REFUTE the claim that
this proposed change preserves coverage quality and delivers the speedup. Default to skepticism:
if you cannot convince yourself a REAL assertion path / regression guard survives, the verdict
is "reject" or at best "accept_with_safeguards". Inspect the actual files when needed
(read/grep under ${REPO}; the venv is warm for quick --collect-only checks).

PROPOSED CHANGE (id=${rec.id}, from ${rec.persona}):
  title: ${rec.title}
  scope: ${rec.affected_scope}
  rationale: ${rec.rationale}
  claimed speedup: ${rec.est_speedup}
  author's coverage_safety claim: ${rec.coverage_safety}
  author says release_safe_now: ${rec.release_safe_now}

Decide: does it actually preserve coverage quality? Is the speedup credible? What safeguards
(specific regression tests, equivalence checks, parallel-safety guards) MUST accompany it?
Return the verdict object.`,
    { label: `verify:${rec.id}`, phase: 'Verify', schema: VERDICT_SCHEMA }
  ).then((v) => (v ? { rec, verdict: v } : null))
)).then((arr) => arr.filter(Boolean))

const accepted = verified.filter((v) => v.verdict.verdict !== 'reject')
const rejected = verified.filter((v) => v.verdict.verdict === 'reject')
log(`Verification complete: ${accepted.length} accepted/conditional, ${rejected.length} rejected.`)

// ---------------------------------------------------------------------------
// PHASE 4 — Synthesis into one ranked, owner-tagged remediation plan.
// ---------------------------------------------------------------------------
phase('Synthesize')

const verifiedDigest = accepted.map((v) =>
  `- [${v.verdict.verdict}] (${v.rec.persona}) ${v.rec.id}: ${v.rec.title}
    scope: ${v.rec.affected_scope}
    speedup: ${v.rec.est_speedup} | effort: ${v.rec.effort} | risk: ${v.rec.risk} | safe_now: ${v.rec.release_safe_now}
    safeguards: ${(v.verdict.required_safeguards || []).join('; ') || 'none'}
    verifier: ${v.verdict.reasoning}`
).join('\n')

const rejectedDigest = rejected.map((v) => `- ${v.rec.id} (${v.rec.persona}): ${v.rec.title} — REJECTED: ${v.verdict.reasoning}`).join('\n')

const finalPlan = await agent(
  `${SHARED}

You are the synthesis lead. Three expert lenses (Randy Reducer / reduction, Architect Alphonso /
architecture+parallelism, Paula Patterns / recurring anti-patterns) proposed changes; an
adversarial verifier filtered them for coverage safety. Produce the FINAL remediation plan as
a markdown report. Requirements:

1. EXECUTIVE SUMMARY: the 3-5 highest-leverage moves and the realistic wall-clock win
   (CI critical path AND local single-dev run). Lead with the answer to the operator's two
   direct questions: (a) can CI fast-shards be parallelized, (b) can the suite be parallelized
   locally across processes — and the exact recommended local command.
2. RANKED ACTION TABLE: every accepted recommendation, ranked by (speedup / effort), columns:
   rank | action | owner-persona | est speedup | effort | risk | required safeguards | safe-now?
3. "SAFE NOW" vs "FOLLOW-UP ISSUE": split per Paula's separation. For follow-ups, give a crisp
   scoped issue title + non-goals.
4. COVERAGE-SAFETY STATEMENT: affirm how the plan preserves coverage quality, and list the
   regression/equivalence safeguards that gate the risky items.
5. REJECTED IDEAS: brief table of what was thrown out and why (so nobody re-litigates).
6. SEQUENCING: a short ordered rollout (quick wins first, structural changes behind safeguards).

Be specific and quantitative. This report is the deliverable.

ACCEPTED & VERIFIED RECOMMENDATIONS:
${verifiedDigest}

REJECTED:
${rejectedDigest || '(none)'}`,
  { label: 'synthesis', phase: 'Synthesize', model: 'opus' }
)

return {
  report: finalPlan,
  stats: {
    clusters_profiled: inventory.length,
    recommendations: allRecs.length,
    accepted: accepted.length,
    rejected: rejected.length,
  },
}
