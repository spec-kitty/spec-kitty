# Research: Agents route around `/spec-kitty.analyze` because the command prompt is "too large to load" (#5005)

**Mission**: `analyze-prompt-context-load-01M3F4BV`
**Measured against**: `main` @ `da6d0af97eb1291cb08d4d0a6772cdfc43df4496` (same commit the `_readiness/5005-analyze-prompt-oversized.md` report measured against)
**Environment**: this checkout's synced `.venv` (`.venv/bin/python`) — unlike the readiness report's fresh clone, which had no venv and could not run the live render.

## 1. What was actually reported (evidence trail)

The issue's only evidence is one self-reported agent quote, sourced from
`kitty-specs/mission-state-audit-trail-durability-01M37PWG/traces/tooling-friction.md`
(quoted verbatim below, re-read directly rather than trusting the issue's paraphrase):

> "Let me check for a direct analyze entrypoint to avoid loading the very large skill prompt:"

The trace records that the agent then bypassed `/spec-kitty.analyze` and hand-rolled the
cross-artifact analysis, persisting it via `spec-kitty agent mission record-analysis` directly.
**No byte/line/token count is cited anywhere in the issue or the trace file** — the "too large"
claim is the agent's own unverified assertion, not a measurement. This research measures the
real rendered payload to check whether that assertion holds.

## 2. Static template sizes (repo-relative, copy-pasteable)

```bash
wc -c packs/built-in/missions/mission-steps/software-dev/*/prompt.md
wc -c .kittify/overrides/missions/software-dev/command-templates/*.md
```

Confirms the readiness report's numbers (unchanged, same commit):

| Action | Canonical `packs/built-in/.../prompt.md` | Project override `.kittify/overrides/.../command-templates/*.md` |
|---|---|---|
| research | 4,049 B | (none — falls through to package_default) |
| accept | 4,300 B (approx, readiness report) | 3,209 B |
| tasks-finalize | 6.6 KB | (not overridden) |
| tasks-outline | 9.3 KB | (not overridden) |
| **analyze** | **11,555 B / 245 lines** | **6,988 B** |
| charter | 12.7 KB | (not overridden) |
| tasks-packages | 12.9 KB | (not overridden) |
| review | 14.1 KB | 6,666 B |
| implement | 15.7 KB | 8,831 B |
| plan | 21.6 KB | 14,136 B |
| tasks | 33.4 KB | 28,485 B |
| specify | 46.8 KB | 28,308 B |

`analyze/prompt.md` (canonical) is smaller than 7 of the other 11 sibling templates. As filed,
"analyze is too large" does not hold against the canonical template body alone — this matches
the readiness report's finding and is reconfirmed here on the same commit.

## 3. Which template actually resolves for `analyze` in THIS checkout (resolver tier)

```bash
.venv/bin/python - <<'PY'
import sys
sys.path.insert(0, "src")
from pathlib import Path
from specify_cli.runtime.resolver import resolve_command
result = resolve_command("analyze.md", Path.cwd(), mission="software-dev")
print(result.tier.value, result.path, result.path.stat().st_size)
PY
```

Result: **`tier=override`**, path
`.kittify/overrides/missions/software-dev/command-templates/analyze.md` (6,988 B) — the
6-tier resolver (`src/charter/offering/resolver.py`, OVERRIDE tier checked first) returns this
project-local override, **not** the canonical `packs/built-in/.../analyze/prompt.md`, for any
agent running `/spec-kitty.analyze` or `spec-kitty next` in this checkout. Confirmed identically
for every other overridden action (specify, plan, tasks, implement, review, accept all resolve
to their `.kittify/overrides/...` copies; only `research` — which has no override file — falls
through to `package_default`). This matches the readiness report's finding.

The override is smaller than canonical (6,988 B vs 11,555 B), so it **cannot itself be the
"too large" driver** — but it is stale (dated ~April 2026, commit `2db24b362`, still cites the
retired `/memory/constitution.md` and omits the current `--mission` flag convention). This is
the drift Operator Decision (3) requires reconciling.

### 3.1 Post-deletion resolution: the four intervening tiers, checked not assumed (round-4 fix, SPEC-R2-ARCH-002)

`resolve_command`'s 6-tier chain (`src/charter/offering/resolver.py:151-261`, `_resolve_asset`) is OVERRIDE (1) →
LEGACY (2) → ORG (3) → GLOBAL_MISSION (4) → GLOBAL (5) → PACKAGE_DEFAULT (6). SC-001/NFR-001
claim that deleting the OVERRIDE-tier file (FR-001) makes `analyze.md` resolve to
`PACKAGE_DEFAULT` (canonical). That is only true if none of the four intervening tiers shadow
`analyze.md` first. Each was checked directly against this repository checkout and this
operator's machine on 2026-09-26 (not asserted from the resolver's general behavior):

- **LEGACY** (`.kittify/command-templates/analyze.md`, checkout-relative): does not exist —
  `ls .kittify/command-templates/analyze.md` → "No such file or directory".
- **ORG** (each configured org pack's `missions/<mission>/command-templates/<name>`,
  checkout-relative config): this repo's `.kittify/config.yaml` configures exactly one org pack
  (`charter_packs.org.packs: [{name: internal, local_path: packs/internal}]`). `packs/internal`
  has no `missions/` directory at all (`find packs/internal -type d -name missions` returns
  nothing — its shape is `assets/`, `directives/`, `drg/`, `glossary_packs/`, `procedures/`,
  `styleguides/`, `toolguides/`, `org-charter.yaml`, per `packs/internal/README.md`'s documented
  org-tier shape). The ORG tier therefore resolves nothing for `analyze.md` (or for any
  mission's command templates) — structurally, not by absence of a specific file.
- **GLOBAL_MISSION** (`~/.kittify/missions/software-dev/command-templates/analyze.md`) and
  **GLOBAL** (`~/.kittify/command-templates/analyze.md`), both **operator-machine-dependent, not
  checkout-relative**: on this operator's machine, `~/.kittify/missions/` exists (populated by
  the global CLI install) and its `software-dev/` subtree has `actions/`, `templates/`, and
  top-level metadata files, but no `command-templates/` subdirectory at all under any mission —
  confirmed by a full recursive listing. `~/.kittify/command-templates/` does not exist either.

**Conclusion, honestly scoped**: for THIS checkout and THIS operator's machine, as of
2026-09-26, all four intervening tiers are confirmed empty for `analyze.md`, so
post-deletion resolution genuinely reaches `PACKAGE_DEFAULT`. The checkout-relative tiers
(LEGACY, ORG) are stable facts about this repository; the machine-relative tiers
(GLOBAL_MISSION, GLOBAL) are **not** — a different operator's `~/.kittify/` could carry a
shadowing file the resolver would prefer over `PACKAGE_DEFAULT`, which is exactly why NFR-001
already hedges ("or whichever tier constant names canonical resolution") and why SC-001 is
now worded to match that hedge rather than assert an unconditional, machine-independent
guarantee.

## 4. Live-rendered payload — the actual measurement requested (template + injected governance/charter context)

Per the mission brief, the full rendered prompt was measured through the real runtime entry
point `runtime.next.prompt_builder.build_prompt`, not modelled. Script (repo-relative,
run from the repo root with `.venv/bin/python`):

```python
# scratchpad/measure_prompts.py (kept out of the repo; reproduce by pasting this into
# .venv/bin/python from the repo root)
import sys
sys.path.insert(0, "src")
from pathlib import Path
from specify_cli.runtime.resolver import resolve_command
from runtime.next.prompt_builder import build_prompt

REPO_ROOT = Path.cwd()
FEATURE_DIR = REPO_ROOT / "kitty-specs" / "analyze-prompt-context-load-01M3F4BV"
MISSION_SLUG = "analyze-prompt-context-load-01M3F4BV"
ACTIONS = ["analyze", "specify", "plan", "tasks", "implement", "review", "accept", "research"]

for action in ACTIONS:
    prompt_text, prompt_file = build_prompt(
        action=action, feature_dir=FEATURE_DIR, mission_slug=MISSION_SLUG,
        wp_id=None, agent="claude", repo_root=REPO_ROOT, mission_type="software-dev",
    )
    b = len(prompt_text.encode("utf-8"))
    print(action, b, prompt_text.count("\n") + 1, b / 4)
```

Invocation: `.venv/bin/python <script>` from the repository root checkout.
`wp_id=None` for every action — for `implement`/`review` this exercises the same
`_build_template_prompt` path `analyze` uses (the WP-specific `_build_wp_prompt` branch only
fires when a real `wp_id` is supplied, which is not the case for `/spec-kitty.analyze`).

**Measured rendered totals (header + governance/charter context + resolved template body):**

| Action | Resolved template tier | Template bytes | **Rendered bytes** | Rendered lines | ~Tokens (bytes/4) |
|---|---|---:|---:|---:|---:|
| **analyze** | override | 6,988 | **11,891** | 305 | ~2,973 |
| accept | override | 3,209 | 8,112 | 197 | ~2,028 |
| research | package_default | 4,049 | 8,952 | 213 | ~2,238 |
| plan | override | 14,136 | 97,175 | 1,001 | ~24,294 |
| review | override | 6,666 | 100,797 | 917 | ~25,199 |
| implement | override | 8,831 | 104,302 | 998 | ~26,076 |
| specify | override | 28,308 | 110,116 | 1,280 | ~27,529 |
| tasks | override | 28,485 | 112,248 | 1,383 | ~28,062 |

**Post-deletion re-measurement (orchestrator-attributed, 2026-09-26; does not change the
diagnosis or any decision):** the `analyze` row above (11,891 B / 305 lines / ~2,973 tokens) was
measured with the stale override in place (6,988 B template). Once FR-001 deletes that override,
canonical resolves instead (11,555 B template — larger than the override), so the post-deletion
rendered total is larger, not the same. Method (one sentence): the override file was temporarily
moved aside to a scratch path outside the repository, the exact `build_prompt()` measurement
script above was re-run for the `analyze` action, the override file was then restored and its
restoration confirmed byte-for-byte via checksum, with `git status --porcelain` empty before and
after. **Result: 16,458 bytes / 367 lines / ~4,115 estimated tokens.** This remains roughly
6x–7x smaller than the 97,175–112,248 B group of five (97,175 / 16,458 ≈ 5.9x; 112,248 / 16,458
≈ 6.8x) and well within normal LLM-context standards.

**Governance/charter overhead per action** (rendered bytes minus resolved-template bytes —
i.e. what `_governance_context()` + the mission-context header actually inject):

| Action | Overhead (bytes) |
|---|---:|
| analyze | 4,903 |
| accept | 4,903 |
| research | 4,903 |
| plan | 83,039 |
| review | 94,131 |
| implement | 95,471 |
| specify | 81,808 |
| tasks | 83,763 |

## 5. Diagnosis

Two premises in the issue's framing do **not** survive live measurement:

1. **"`analyze`'s prompt is too large."** False on both axes measured. Canonical template:
   11,555 B, smaller than 7 of 11 siblings. The resolved template for this checkout (the stale
   override): 6,988 B, smaller still. The **actual rendered payload** an agent receives —
   template + injected governance/charter context, measured through the real
   `build_prompt()` entry point — is **11,891 bytes / 305 lines / ~2,973 tokens** (this checkout,
   2026-09-26, with the stale override still in place — see the post-deletion re-measurement note
   under § 4's table for the honest figure once FR-001 deletes the override). That is not large by
   any LLM-context standard. **Correction (does not change the diagnosis or any decision):**
   analyze is not "the smallest of the eight actions measured except for `accept` and `research`,"
   as an earlier draft of this document claimed — § 4's table above shows `accept` renders
   8,112 B and `research` renders 8,952 B, both smaller than analyze's 11,891 B. Analyze is the
   **third-smallest** of the eight actions measured (larger than `accept` and `research`, but still
   an order of magnitude below the 97,175–112,248 B group of five).
2. **"The governance-context preamble dominates uniformly across all actions, so `analyze`
   is not the problem — the shared preamble is."** Also false, and false in the *opposite*
   direction from what the mission brief hypothesized. The governance/charter overhead is
   **wildly non-uniform by action**, but `analyze` sits in the **small** group (4,903 B,
   alongside `accept` and `research`), not the large one. `specify`, `plan`, `tasks`,
   `implement`, and `review` each carry **81,000–95,000 bytes** of injected governance/charter
   context — 17–19x more than `analyze` gets. This is a real, large, previously-unmeasured
   size disparity, but it is the **opposite** of `analyze` being the outlier: `analyze` is
   the outlier on the *small* side.

**Root cause, confirmed**: neither `analyze/prompt.md` (canonical or the resolved stale
override) nor the governance-context injection specific to the `analyze` action is oversized.
The one-off agent quote in the evidence trace ("very large skill prompt") is not reproducible
against this measured render path for `analyze`. Two non-exclusive explanations for what the
reporting agent actually experienced, neither of which is `analyze/prompt.md`:

- The agent may have been reasoning about a different large surface entirely — e.g. the
  `~/.hermes/skills/sk-design/` doctrine document that Claude-harness `sk-design` loads to
  drive the analyze phase subagent (outside this repository, not a spec-kitty canonical
  source, and out of this mission's remit — remedy scope is bounded to spec-kitty's own
  canonical sources).
- The agent **never measured** before deciding to route around the canonical surface — it
  reasoned from an assumption ("the very large skill prompt") rather than from an attempt to
  load it or a real count. This is a distinct, addressable defect: the charter's canonical-
  sources doctrine (`DIRECTIVE_044` / `canonical-source-unification` tactic, both in
  `packs/built-in/`, read in full — see below) already tells agents never to hand-roll a
  substitute for a *missing* command (Rule 3) and never to improvise instead of using a
  canonical template/skill/CLI (Rule 1), but it has **no rule addressing a bypass driven by
  an unverified size assumption** — the agent in the trace never attempted to load
  `/spec-kitty.analyze`; it pre-emptively decided not to. That is a gap in the existing
  doctrine text, not a gap in `analyze/prompt.md`'s content or size.

**What this means for remedy scope.** Per Operator Decision (2), a prompt/context-side fix on
existing canonical sources ships in this mission, no new CLI surface. Given the diagnosis:

- Shrinking/segmenting `analyze/prompt.md` (issue's remedy option 1) is **not warranted** —
  there is nothing oversized to shrink, and doing so would not address a real problem (it
  would only make the smallest-already sibling template smaller still).
- The stale-override reconciliation (Operator Decision 3) **is** warranted and ships in this
  mission — it's a real, distinct drift defect (retired `/memory/constitution.md` reference,
  missing `--mission` convention), independent of the size question, and was already directed
  in-scope by the operator.
- A new failure-mode entry added to the existing `canonical-source-unification` tactic (and/or
  `DIRECTIVE_044`) — "never bypass a canonical prompt/skill on an unverified size assumption;
  attempt to load it, and if it is genuinely oversized, file an upstream gap rather than
  improvising" — is a legitimate prompt/context-side fix on an *existing* canonical source
  that directly targets the evidenced failure mode (an agent that reasoned about size without
  measuring), within remedy scope (2), no new CLI surface. See spec.md FR list.

### Explicit call-out: the real, larger disparity is out of THIS mission's proportionate scope

The `specify`/`plan`/`tasks`/`implement`/`review` governance-context overhead (81–95 KB per
render, vs `analyze`'s 4.9 KB) is a genuine, more severe, previously-undocumented size
concern — but it is **not** what #5005 was filed or evidenced against, and fixing it means
editing `src/runtime/next/prompt_builder.py::_governance_context` and/or the charter
action-scoped context resolution it calls into (`charter.activation.scope_router.build_with_scope`,
`charter.activation.context.build_charter_context`). That file is **actively touched by open
PR #5009** ("fix: retain validated owned checkout authority across mission lifecycle" — confirmed
`OPEN` via `gh pr view 5009`), and the charter template-resolution family it depends on is
touched by open PR #4995 ("fix(charter): make concurrent mission-template resolution
thread-safe" — confirmed `OPEN` via `gh pr view 4995`). Editing `_governance_context` in this
mission would: (a) collide at the file level with #5009's in-flight changes, (b) require
verifying the NFR-001 byte-stability contract the module's own docstring calls out for every
one of the five affected actions, and (c) be a materially larger, riskier change than what
`analyze` was ever evidenced to need. This mission does **not** fold that fix in.

Per DIRECTIVE_052 (Prefer Durable Fixes, activated in this repo's charter), a diagnosed
structural cause may not simply be dropped as unenforced prose once deferred — it must be
recorded as a tracked follow-up behind an umbrella/epic issue naming the root cause. spec.md's
FR-005 makes that obligation an explicit, binding mission requirement (not a mere
recommendation in research prose): before mission wrap-up, the orchestrator files a GitHub
issue naming the root cause (`_governance_context()` in
`src/runtime/next/prompt_builder.py`), the affected actions (`specify`/`plan`/`tasks`/
`implement`/`review`), the measured magnitude (81–95 KB, 17–19x `analyze`'s 4.9 KB), and the
`#5009` sequencing dependency — and records the resulting issue number back into spec.md's
"Dependencies & Sequencing" section. This is a distinct call-out from the "needs a new CLI
surface" escape hatch in Operator Decision (2) — no new CLI surface is needed for this fix,
but proportionality and the #5009 file-level collision argue for deferring it to its own
mission rather than widening this one.

## 6. Ledger check

Re-executed each pattern individually against `SPEC-KITTY-LEDGER.md` (not asserted from memory
— this mission's own thesis is "measure, don't assert," so its own ledger check must survive
literal re-running):

| Pattern | Hits | Disposition |
|---|---:|---|
| `"too large to load"` | 0 | confirmed zero |
| `"context budget"` | 0 | confirmed zero |
| `"skill prompt"` | 0 | confirmed zero |
| `"prompt_builder"` | 0 | confirmed zero |
| `"analyze/prompt.md"` | 0 | confirmed zero |
| `"prompt.*size"` | 1 (line 3454) | **not** a real hit — the BRE pattern's `.*` also matches inside the unrelated word "synthesized" (`...the-s-i-z-e-d`); the line has no bearing on prompt size |
| `"governance_context"` | **2** (lines 350, 5733) | **real hits, but unrelated to this mission's render-time injection** — see below |

`grep -n "governance_context" SPEC-KITTY-LEDGER.md` returns two hits, both naming an unrelated
Op-dispatch data shape (`governance_context_available` / `governance_context_text` fields on a
dispatch capsule), not the render-time `_governance_context()` injection this mission measures
in `src/runtime/next/prompt_builder.py`. The prior sentence in an earlier draft of this
research.md claimed "zero hits" for this grep; that claim did not survive re-execution and is
corrected here. The underlying diagnosis (no prior ledger entry addresses `analyze` prompt size
specifically) is unaffected — neither hit concerns prompt/context render size — but the
inaccurate "zero hits" claim itself is the kind of unverified assertion this mission's own
diagnosis criticizes, so it is fixed rather than left standing.

The many analyze-phase ledger entries that do exist (e.g. SK-06 at L5588, SK-43 at L5246, SK-47
at L5314, SK-63 at L9360, and SK-141 — **disambiguated: L2780**, "`record-analysis` silently
accepts an unfenced carrier and COMMITS a `verdict: unknown` report instead of failing loudly,"
not the unrelated `SK-141` at L11172 about `MigrationRunner.upgrade()` atomicity, a distinct
entry that happens to share the same "SK-141" heading — a known instance of the ledger's
duplicate-numbering condition) are all about `record-analysis` persistence/verdict-honesty
bugs, a different defect class; noted here for completeness but they do not bear directly on
this defect. They are, however, the same defect *family* that spec.md's FR-001 must not
perpetuate: the stale override omits `record-analysis` persistence entirely, so leaving FR-001
scoped to terminology-only (rather than also adopting the `analysis-findings/v1` carrier and
the `record-analysis` persistence step) would leave this repo's own `analyze` override in the
same no-persistence state this recurring ledger bug class exhibits.

## 7. Charter/CLAUDE.md drift check

No drift found between `.kittify/charter/charter.md` and `CLAUDE.md` bearing on this issue's
diagnosis or remedy. Both agree on the canonical-sources standing order (charter §"Quality &
Tech-Debt Standing Orders" item 6; `CLAUDE.md` "⚠️ CRITICAL: Use Canonical Sources, Never
Improvise"), and neither currently addresses the "size-assumption bypass without measuring"
failure mode identified above — this is the gap FR-002 closes.

## 8. Tooling friction

See `kitty-specs/analyze-prompt-context-load-01M3F4BV/tracer-tooling-friction.md`.

## 9. Operator Decision 5 investigation: why specify/plan/tasks/implement/review actually cost 81–95 KB

Sections 1–8 above are this mission's original diagnosis and stand unmodified — they answer
issue #5005 as filed (`analyze`). This section answers the follow-on question Operator Decision
5 (2026-09-26) puts in scope: **why** `specify`/`plan`/`tasks`/`implement`/`review` measure
81,476–95,139 rendered bytes (§4 above), and where the fix belongs. Everything below is measured
through the real entry point (`charter.activation.scope_router.build_with_scope`, the same
function `runtime.next.prompt_builder._governance_context` calls), never modelled, per this
mission's own "measure, don't assert" thesis.

### 9.1 The 81–95 KB figure is a one-time-per-checkout spike, not a steady-state cost

`_governance_context()` (`src/runtime/next/prompt_builder.py:359`) routes each action through
`charter.activation.scope_router.build_with_scope` → `charter.activation.context.build_charter_context`
(`src/charter/activation/context.py:156`). That function picks one of four render branches:

- `BOOTSTRAP_ACTIONS = frozenset({"specify", "plan", "implement", "review"})`
  (`src/charter/activation/context.py:116`) always attempt the large "bootstrap" render.
  `tasks` is **not** in this literal set but reaches the same render path via
  `_action_node_declared` (a DRG action-node-URN membership check, `context.py:124-153`) — its
  `action:software-dev/tasks` node is declared, so it is not ruled out by the
  `BOOTSTRAP_ACTIONS`-membership fast path.
- `analyze`, `accept`, `research` are **not** in `BOOTSTRAP_ACTIONS` and (confirmed live, §9.2
  below) have no declared DRG action node that survives `_action_node_declared`, so they always
  take `build_non_bootstrap_context_result` (`context_result_builders.py:64`) — a small, fixed
  "compact" render, **regardless of any first-load state**. This is why they were never large.
- Whether a `BOOTSTRAP_ACTIONS`/declared-node action actually renders "bootstrap" (large) or
  "compact" (small — **8.0–12.6 KB for `specify`/`plan`/`tasks`/`implement`/`review` once
  first-loaded, live-measured in §9.7; NOT the ~4.5–4.9 KB figure, which was only ever measured
  for `analyze`/`accept`/`research`'s unrelated always-compact `build_non_bootstrap_context_result`
  path in §9.2's table below — this line previously conflated the two, corrected per round-4
  fix, SPEC-R2-VERIFY-005**) on a given call depends on `_prepare_context_state`
  (`src/charter/activation/context_state.py:89-110`): it reads
  `.kittify/charter/context-state.json` and computes `first_load = action not in
  state["actions"]`. **First load → bootstrap** (`effective_depth = _MIN_EFFECTIVE_DEPTH = 2`).
  **Not first load → compact** (`effective_depth = 1`). Every bootstrap render that runs with
  `mark_loaded=True` (the only mode `_governance_context` ever calls with) immediately persists
  the action into that state file (`_mark_action_loaded`,
  `context_result_builders.py:126-127` / `:183-184`), so the SAME action never renders bootstrap
  again for that checkout.
- **`context-state.json` is local, per-checkout, and untracked**: confirmed via
  `git check-ignore -v .kittify/charter/context-state.json` → matches `.gitignore:90`. It is
  never committed, never shared across worktrees or clones. Consequence: every fresh `git
  clone`, every new mission worktree (`.worktrees/<mission>-lane-<id>`), and every CI checkout
  starts with this file absent and pays the full bootstrap cost again, the first time each of
  `specify`/`plan`/`tasks`/`implement`/`review` is touched in it. The 81–95 KB figure this
  mission's §4 measured is not a one-off historical artifact that has "already been paid for" —
  it recurs on every fresh checkout that touches these five actions, which is the routine case
  for a fresh WP worktree.

**Reproduction (repo-relative, copy-pasteable):**

```bash
cat .kittify/charter/context-state.json   # local, gitignored, per-checkout first-load ledger
git check-ignore -v .kittify/charter/context-state.json   # confirms .gitignore:90 match
```

### 9.2 Real byte breakdown per action, measured with first-load state cleared

To see the true bootstrap render (not the already-marked-loaded compact fallback this mission's
own §4 script left behind on this checkout — running that script the first time is itself
destructive to the state it measures, see §9.4), `.kittify/charter/context-state.json` was
backed up, its `actions` map cleared to `{}`, the script below run, then the file restored
byte-for-byte to its pre-investigation contents (a local, gitignored, non-source file — this
does not touch anything under git). Script (repo-relative; reproduce by pasting into
`.venv/bin/python` from the repo root after clearing the `actions` map as above):

```python
import sys
sys.path.insert(0, "src")
from pathlib import Path

from charter.activation.scope_router import build_with_scope

REPO_ROOT = Path.cwd()
FEATURE_DIR = REPO_ROOT / "kitty-specs" / "analyze-prompt-context-load-01M3F4BV"

for action in ["review", "specify", "plan", "tasks", "implement", "analyze", "accept", "research"]:
    ctx = build_with_scope(REPO_ROOT, FEATURE_DIR, action=action, mark_loaded=True, profile=None)
    text = ctx.text
    b = len(text.encode("utf-8"))
    print(f"{action}: mode={ctx.mode} first_load={ctx.first_load} depth={ctx.depth} bytes={b}")
    lines = text.split("\n")
    ad_idx = next((i for i, line in enumerate(lines) if line.startswith("Action Doctrine (")), None)
    if ad_idx is not None:
        before = "\n".join(lines[:ad_idx]).encode("utf-8")
        after = "\n".join(lines[ad_idx:]).encode("utf-8")
        print(f"  before 'Action Doctrine': {len(before)} bytes; from it onward: {len(after)} bytes")
    print(f"  substitution trailer present: {'Governance payload:' in text}")
```

**Measured results (this checkout, `.venv/bin/python`, first-load state cleared):**

| Action | mode | bytes | bytes before "Action Doctrine" | bytes from "Action Doctrine" onward | % in Action Doctrine | substitution trailer |
|---|---|---:|---:|---:|---:|---|
| review | bootstrap | 93,799 | 24,537 | 69,261 | ~74% | `11 sections substituted (budget=40000)` |
| implement | bootstrap | 95,139 | 24,540 | 70,598 | ~75% | `11 sections substituted (budget=40000)` |
| specify | bootstrap | 81,476 | 23,703 | 57,772 | ~71% | `7 sections substituted (budget=40000)` |
| plan | bootstrap | 82,707 | 23,703 | 59,003 | ~71% | `7 sections substituted (budget=40000)` |
| tasks | bootstrap | 83,431 | 23,703 | 59,727 | ~72% | `7 sections substituted (budget=40000)` |
| analyze | compact | 4,571 | — | — | — | none |
| accept | compact | 4,571 | — | — | — | none |
| research | compact | 4,571 | — | — | — | none |

(Small differences from §4's 4,903 B / 11,891 B figures are because §4 measured through
`prompt_builder.build_prompt()`, which prepends its own mission-context header before calling
this same function; both measurements agree on order of magnitude and on which group is large
vs. small.)

**Reading the table**: every bootstrap render already carries a "sections substituted" trailer —
the NFR-001 budget enforcer (§9.3) is running, not dormant — yet every one still lands at
1.9x–2.4x the 40,000-character `BUDGET_DEFAULT` it targets. The reason is structural, not a
tuning miss: **71–75% of every bootstrap render's bytes live in the "Action Doctrine" block,
and that block is never offered to the budget enforcer as a candidate at all** (confirmed by
source reading, §9.3).

### 9.3 Root cause: the existing NFR-001 budget enforcer has a coverage gap, not a bug in its algorithm

`src/charter/activation/context_renderers/token_budget.py` defines:

- `BUDGET_DEFAULT: int = 40_000` (line 63) — the NFR-001 pin, with its own docstring already
  admitting "real charter payloads run ~65k pre-compaction, so this default is not a production
  ceiling" (lines 75-77) — a known, pre-existing, self-acknowledged gap this mission's fix
  closes, not a new problem this mission introduces.
- `_enforce_token_budget(text, *, action, profile_block, section_block, selection_block="",
  budget=BUDGET_DEFAULT)` (line 587) — called once, at the end of
  `_render_bootstrap_text` (`src/charter/activation/context_renderers/bootstrap_text.py:347-353`),
  on the FULLY joined text (which already includes the Action Doctrine block, added at
  `bootstrap_text.py:314` via `_render_action_doctrine_lines`, well before the budget call).
- Candidate collection inside `_enforce_token_budget` (lines 620-622):
  ```python
  candidates = _collect_section_block_candidates(section_block, action)
  candidates.extend(_collect_profile_block_candidates(profile_block))
  candidates.extend(_collect_selection_block_candidates(selection_block))
  ```
  These three helpers read exactly three pre-rendered strings — `section_block` (Action-Critical
  Charter Sections), `profile_block` (Profile-Cited directives/tactics/…), and `selection_block`
  (Selected paradigms/directives/…) — each built earlier in `_render_bootstrap_text` and passed
  through by name. **None of the three ever includes the Action Doctrine block's content.** The
  Action Doctrine block is assembled straight into `lines` (the same list `text = "\n".join(lines)`
  joins) and is never passed to `_enforce_token_budget` as a labelled block at all — there is no
  fourth `action_doctrine_block` parameter.
- Confirms the measured evidence exactly: the ~23.7–24.5 KB "before Action Doctrine" portion is
  the part `_enforce_token_budget` CAN see, and it is already fully substituted (7–11 candidates
  swapped, per the trailer) — the enforcer is doing its job on the ~24 KB it can see. The
  remaining 57.7–70.6 KB (Action Doctrine) is structurally invisible to it, full stop.
- Inside the Action Doctrine block itself there IS a separate, independent size-control
  mechanism — progressive disclosure (`_pd.requires_closure`, D2c,
  `action_doctrine_bundle.py`/`bootstrap_text.py:140-142`): an artifact reached only via a DRG
  `suggests` edge renders as a fetch stanza; only artifacts within the resolved action's
  `requires`-closure render their full verbatim body inline. The 57.7–70.6 KB measured is
  therefore already the *requires-closure-only* subset, not the full doctrine catalog — the
  `software-dev` mission type's `specify`/`plan`/`tasks`/`implement`/`review` action nodes
  simply have requires-closures large enough, post-D2c, to still blow past 40,000 characters on
  their own. (`BUDGET_DEFAULT`'s own docstring corroborates this history: raised from 32k to 40k
  after commit `3bcdda344` "wired the software-dev doctrine cascade... into action
  reachability," which "legitimately grew the essential Action Doctrine payload.")

**Confirmed root cause, precisely**: NOT a missing or broken budget mechanism — a real one exists,
runs, and reports. The defect is that its candidate-collection surface
(`_collect_section_block_candidates` / `_collect_profile_block_candidates` /
`_collect_selection_block_candidates`, `token_budget.py:398-545`) was never extended to also
draw candidates from the Action Doctrine block when D2c/progressive-disclosure was layered on
top of it, so 71–75% of the render competes for nothing and is never a candidate for
substitution.

**Additional, distinct finding — the trailer is honest about *what* happened but not about
*whether it worked*.** `warning_line()` (`token_budget.py:140-143`) reports only
`f"# Governance payload: {count} sections substituted with fetch commands (budget={budget})."`
— it names a count, never whether the post-substitution text is at, under, or (as measured) 1.9x–2.4x
over that budget. This is not literally silent (a line IS printed), but it is materially
misleading: an operator or agent reading `11 sections substituted with fetch commands
(budget=40000)` on a 93,799-byte render has no signal, from that line, that the budget was
missed by 53,799 bytes. FR-006 in `spec.md` closes this.

### 9.4 A reproducibility hazard the measurement method itself has

`build_with_scope`/`build_charter_context` are always called with `mark_loaded=True` from
`_governance_context` (there is no read-only/dry-run mode). Consequence: **running this
mission's own §4 measurement script mutates `.kittify/charter/context-state.json`** — the very
first run marks `specify`/`plan`/`tasks`/`implement`/`review` as loaded, so re-running the exact
same script again immediately afterward reproduces the SMALL compact numbers for all five, not
the 81–95 KB bootstrap numbers, on the same checkout. This was directly observed while producing
§9.2's table: the first script run (with `actions: {}`) reproduced the large bootstrap renders;
the file was then found to carry that run's own five new timestamps
(`.kittify/charter/context-state.json`, gitignored) immediately afterward. A maintainer
reproducing §4's numbers on a checkout that has already run `spec-kitty next`/`build_prompt()`
for these actions even once will see the small numbers and could wrongly conclude the disparity
is fixed or was never real. **To reproduce the bootstrap numbers, `.kittify/charter/context-state.json`
must have no entries for the action(s) under test** — either a genuinely fresh checkout/worktree,
or (as done here) a deliberate, restored-afterward clearing of the local, gitignored state file.
This hazard is itself evidence for §9.1's point: the 81–95 KB figure is a first-touch spike, not
a stable steady-state measurement.

### 9.5 Chosen fix seam and the PR #5009 overlap, checked not assumed

`gh pr view 5009 --json files,title,state,mergeable,updatedAt` (re-run live in this investigation,
matching the facts supplied in the mission brief) confirms PR #5009's full file list:
`docs/development/owned-checkout-charter-resolution.md`, `pyproject.toml`,
`src/mission_runtime/resolution.py`, `src/runtime/next/decision.py`,
`src/runtime/next/prompt_builder.py`, `src/runtime/next/runtime_bridge.py`,
`src/runtime/next/runtime_bridge_engine.py`, `src/specify_cli/coordination/status_service.py`,
`src/specify_cli/coordination/status_transition.py`, `src/specify_cli/core/mission_creation.py`,
`src/specify_cli/workspace/context.py`, plus three test files. `state=OPEN`,
`mergeable=CONFLICTING`, `updatedAt=2026-09-25T15:20:33Z`.

`gh pr diff 5009` on `src/runtime/next/prompt_builder.py` shows exactly what it touches there: it
threads a new `effective_root: Path | None = None` parameter through `build_prompt`,
`_build_wp_prompt`, and the `_governance_context(...)` **call sites** inside them (e.g.
`_governance_context(effective_root or repo_root, action=action, feature_dir=feature_dir,
profile=agent_profile_id)`), plus `_build_template_prompt`'s `repo_root` argument
(`_build_template_prompt(..., effective_root or repo_root, ...)`). It does **not** touch
`_governance_context`'s own definition, and it touches **zero** files under
`src/charter/activation/` — no `context.py`, no `scope_router.py`, no
`context_renderers/token_budget.py`, no `context_renderers/bootstrap_text.py`, no
`action_doctrine_bundle.py`.

**Conclusion, on the merits (not as a PR-#5009-avoidance move — the file-overlap fact is a
byproduct, not the reason)**: the confirmed defect (§9.3) lives entirely inside
`src/charter/activation/context_renderers/token_budget.py` and
`src/charter/activation/context_renderers/bootstrap_text.py`. `src/runtime/next/prompt_builder.py`
is a thin caller that never assembles a byte of governance content itself — editing it would not
touch the actual defect at all. The fix therefore belongs in the charter-layer renderer files,
which happen to have zero file-level overlap with PR #5009's diff. The one honest residual
interaction: if #5009 lands first and its `effective_root` threading changes which `repo_root`
value reaches `_governance_context` in an owned-checkout scenario, that changes which
`.kittify/charter/` tree (and therefore which DRG/doctrine content) this mission's fix reads from
— a semantic interaction worth a rebase-time smoke test, never a textual merge conflict (the two
changesets share no lines and no files).

No part of this fix requires a new `spec-kitty` CLI command, subcommand, or argument, and no
schema/contract change: `_enforce_token_budget`'s existing `RenderedSection`/fetch-stanza
substitution contract already generalizes to a fourth candidate source: this is an internal
extension of an existing function using its existing data shape, not a new surface. Operator
Decision (2)'s "no new CLI surface" instruction is satisfied without needing its escape hatch.

### 9.6 Existing tests this fix must extend (implementation-phase note, not executed in this pass)

`tests/charter/test_context_token_budget.py` and
`tests/charter/context_renderers/test_token_budget_sonar.py` already cover
`_enforce_token_budget`/`apply_token_budget`; `tests/specify_cli/next/test_wp_prompt_governance_contract.py`
covers the WP-prompt governance render end-to-end. A targeted grep of the latter
(`grep -n "40000\|40_000\|BUDGET_DEFAULT\|byte" tests/specify_cli/next/test_wp_prompt_governance_contract.py`)
returns no hits — it asserts anchor presence (e.g. `DIRECTIVE_032`, glossary path, ADR path), not
exact byte counts, which materially reduces the regression risk of extending the candidate set
(no hard-coded byte-count fixture to update). Not run in this authoring pass — this is scope
information for the implementation-phase work package, not a claim that the fix has been built
or tested yet.

### 9.7 Round-4 fix: exhaustive-substitution floor (SC-005 achievability), the shared `_enforce_token_budget` call site (compact-path blast radius), and re-verified compact-render figures

Three follow-on measurements, added while resolving the spec-r2 squad's confirmed findings
(SPEC-R2-GOV-001, SPEC-R2-ARCH-001, SPEC-R2-VERIFY-005). All three follow this mission's own
"measure, don't assert" thesis: live-executed against this checkout on 2026-09-26, with
`.kittify/charter/context-state.json` backed up before mutation and restored byte-for-byte
after (verified via `diff` — see each subsection).

#### 9.7.1 Does making the Action Doctrine block substitutable actually get any of the five actions under 40,000 bytes? (GOV-001)

§9.3 establishes that FR-005's fix threads Action Doctrine artifact bodies through
`_enforce_token_budget` as candidates, the same way `section_block`/`profile_block`/
`selection_block` already are. To find the *floor* this can reach — the maximal-exhaustion case
where every eligible Action Doctrine candidate has been swapped, the scenario FR-006's "still
over budget after every substitution" trailer describes — `charter.activation.progressive_disclosure.requires_closure`
was monkeypatched to always return an empty set for the duration of one render per action. Since
`_extend_named_artifact_lines` (`bootstrap_text.py` calling into `selection_block.py`) already
renders any artifact URN outside the (now-empty) "requires-closure" as the compact
id/title-stub-plus-fetch-stanza shape D2c's suggests-path uses, this forces every requires-closure
entry through that same shape too — i.e., it reproduces exactly the state the render would be in
if FR-005's substitution loop swapped every single Action Doctrine candidate. `analyze`/`accept`/
`research` are unaffected (they never populate Action Doctrine ids). Script (repo-relative;
`.kittify/charter/context-state.json` backed up, its `actions` map cleared to `{}` before each of
the two runs below, restored byte-for-byte after both — confirmed via `diff` against the backup,
matched):

```python
import sys, json
sys.path.insert(0, "src")
from pathlib import Path
import charter.activation.progressive_disclosure as pd_mod

REPO_ROOT = Path.cwd()
FEATURE_DIR = REPO_ROOT / "kitty-specs" / "analyze-prompt-context-load-01M3F4BV"
state_path = REPO_ROOT / ".kittify" / "charter" / "context-state.json"
backup = state_path.read_text()

from charter.activation.scope_router import build_with_scope

def clear_actions():
    data = json.loads(backup)
    data["actions"] = {}
    state_path.write_text(json.dumps(data))

ACTIONS = ["specify", "plan", "tasks", "implement", "review"]

clear_actions()
baseline = {a: len(build_with_scope(REPO_ROOT, FEATURE_DIR, action=a, mark_loaded=True, profile=None).text.encode("utf-8")) for a in ACTIONS}

clear_actions()
pd_mod.requires_closure = lambda *a, **k: frozenset()  # force every AD entry down the fetch-stanza path
floor = {a: len(build_with_scope(REPO_ROOT, FEATURE_DIR, action=a, mark_loaded=True, profile=None).text.encode("utf-8")) for a in ACTIONS}

state_path.write_text(backup)  # restore byte-for-byte
print("restored:", state_path.read_text() == backup)
for a in ACTIONS:
    print(a, "baseline=", baseline[a], "floor=", floor[a], "reduction=", baseline[a] - floor[a])
```

**Measured (this checkout, 2026-09-26; `context-state.json` restore confirmed `True` via the
script's own `diff`-equivalent check):**

| Action | Baseline (bootstrap, requires-closure inline) | Floor (every AD candidate swapped) | Reduction | ≤ 40,000? |
|---|---:|---:|---:|---|
| specify | 81,476 B | 61,208 B | -20,268 B (-24.9%) | No |
| plan | 82,707 B | 61,808 B | -20,899 B (-25.3%) | No |
| tasks | 83,431 B | 63,000 B | -20,431 B (-24.5%) | No |
| implement | 95,139 B | 70,434 B | -24,705 B (-26.0%) | No |
| review | 93,799 B | 70,380 B | -23,419 B (-25.0%) | No |

**Conclusion**: SC-005's originally-scoped ≤40,000-byte target is not reachable for any of the
five actions purely by extending the budget enforcer's candidate coverage — confirmed by
measurement at the maximal-exhaustion case, not merely hedged as a "some action" possibility.
The achievable ceiling this fix can reach is a 24.5%–26.0% reduction (max post-floor value
70,434 B, for `implement`); spec.md's FR-005/SC-005 are revised to a ≤72,000-byte target
(a small margin above the measured 70,434 B floor) instead of the unreachable ≤40,000 B. Closing
the remaining gap requires DRG-curating the `software-dev` action nodes' `requires`-closures
(reclassifying some artifacts to `suggests`), a content-authoring decision out of this mission's
remit — the same conclusion spec.md's original "Honest residual" paragraph gestured at, now
confirmed by measurement rather than left as an unverified hedge.

#### 9.7.2 `_enforce_token_budget` is shared by the compact render path too (ARCH-001)

`grep -n "_enforce_token_budget" src/charter/activation/context_renderers/*.py` confirms two
call sites, not one: `bootstrap_text.py:347` (`_render_bootstrap_text`, the bootstrap path) and
`compact_governance.py:172` (`_render_compact_governance`, the compact path — whose own comment
reads "compact view shares the budget cap with the bootstrap path"). FR-005 extends
`_enforce_token_budget`'s candidate collection itself, so the extension is live on both call
sites, not scoped to bootstrap. `grep -n "_render_action_doctrine_lines" src/charter/activation/context_renderers/*.py`
confirms its only call site (of the invocation itself; two other lines are its `def` and its own
docstring reference) is `bootstrap_text.py:314` — `compact_governance.py` never calls it
and never assembles an Action Doctrine block by any other path (`render_compact_view`, which
`_render_compact_governance` delegates to, builds its text from `directive_ids`/`tactic_ids`/…
id lists directly, with no Action Doctrine body rendering at all). Consequence: FR-005's new
candidate source is structurally empty on the compact path — a genuine no-op there, not merely
an unreached branch — which is why an already-first-loaded checkout (compact path) would have
been unaffected by the now-dropped FR-005 fix. FR-005/006/007 are dropped from this
mission's scope entirely per Operator Decision 6, so this finding is preserved here only as
part of the historical/evidence-trail record (research.md § 9) the orchestrator hands the
maintainer, alongside spec.md's "Known residual (out of scope): governance-context budget gap"
section — the spec.md Edge Case bullet that once cited this compact-path no-op (labeled
"Operator Decision 5 reflexivity") is itself now retired per Decision 6, and spec.md's current
C-002 no longer names a regression-test requirement for this case.

#### 9.7.3 Re-verified: the real "compact" bytes for specify/plan/tasks/implement/review post-first-load (VERIFY-005)

Independently re-measured (not copied from the confirmed-findings file) against this checkout's
pre-existing `context-state.json` (which already had these five actions marked loaded — no
mutation needed for this measurement, confirmed via `diff` showing no change before/after):

```python
import sys
sys.path.insert(0, "src")
from pathlib import Path
from charter.activation.scope_router import build_with_scope

REPO_ROOT = Path.cwd()
FEATURE_DIR = REPO_ROOT / "kitty-specs" / "analyze-prompt-context-load-01M3F4BV"
for action in ["specify", "plan", "tasks", "implement", "review"]:
    ctx = build_with_scope(REPO_ROOT, FEATURE_DIR, action=action, mark_loaded=True, profile=None)
    print(action, ctx.mode, ctx.first_load, len(ctx.text.encode("utf-8")))
```

**Result (matches the confirmed-findings file exactly, independently reproduced):**
specify=8,002 B, plan=8,308 B, tasks=8,354 B, implement=12,614 B, review=12,492 B — measured via
`build_compact_bundle_context_result` (the real post-first-load path for these five actions),
**not** `build_non_bootstrap_context_result` (§9.2's 4,571 B / §4's 4,903 B figures, which apply
only to `analyze`/`accept`/`research`'s always-compact, never-bootstrap path). §9.1's earlier
"~4.5–4.9 KB" citation for the general `BOOTSTRAP_ACTIONS`/declared-node compact case was wrong
to imply this range covered these five actions too; corrected in place (see §9.1) and
self-contained here (the spec.md Edge Case bullet that once carried this same correction, under
the label "Operator Decision 5 reflexivity," is now retired per Operator Decision 6 — see
spec.md's "Known residual (out of scope): governance-context budget gap" section). The
directional safety conclusion is
unaffected either way (an already-first-loaded checkout, at 8.0–12.6 KB, remains far under the
40,000-byte budget and far smaller than the 81,476–95,139-byte pre-first-load bootstrap render).

## 10. Round-5 addendum (Operator Decision 7, 2026-09-26): merged-branch re-measurement after PR #5133

Between §§ 1-9 above being written and this addendum, upstream PR #5133 ("feat(doctrine):
criterion delivery labels + acceptance-criteria-non-vacuity review tactic," merged
2026-09-26T19:56:16Z into `main`) resynced ALL 10 stale `.kittify/overrides/missions/software-dev/command-templates/`
files -- including `analyze.md` -- to byte-parity with their canonical counterparts, and added a
new test, `tests/cross_cutting/test_kittify_override_parity.py`, that asserts this byte-parity
whenever it runs. That test is real, fast (`pytest.mark.fast`), and currently passing, but it is
not a per-PR merge-blocking check: per this repo's own `.github/ci-module-registry.yml`
disposition, `tests/cross_cutting` (the directory it lands in) has no per-PR CI lane; its only
current automated execution home is the nightly `.github/workflows/ci-nightly.yml`
`interpreter-matrix` job (schedule/`workflow_dispatch` triggers only, Python 3.13-only,
`pytest -m "fast or unit"` over the whole tree) or a manual `make test-full` that no workflow
invokes -- see spec.md's Former Acceptance Scenario 2 rationale (under User Story 1) for the full
CI-wiring citation. This branch has since merged
`origin/main` @ `34b53d78e` (which includes #5133). Operator Decision 7 (2026-09-26) responds by
dropping FR-001 (spec.md) as a build item -- deleting the override now would remove content a new
gate depends on, for no behavior change (the bytes already match canonical). This addendum
records the orchestrator's own re-measurement on this merged checkout, appended here rather than
edited into §§ 1-9's original text, per this document's own existing convention of layering dated
corrections on top of prior sections (see § 9.7's "Round-4 fix" addendum for the same pattern).

### 10.1 The override is no longer stale

```bash
for f in accept analyze implement plan review specify tasks tasks-outline tasks-packages tasks-finalize; do
  cmp -s ".kittify/overrides/missions/software-dev/command-templates/${f}.md" \
         "packs/built-in/missions/mission-steps/software-dev/${f}/prompt.md" \
    && echo "$f: IDENTICAL" || echo "$f: DIFFERS"
done
```

Re-run 2026-09-26 on this checkout: **all 10 IDENTICAL** (accept, analyze, implement, plan,
review, specify, tasks, tasks-outline, tasks-packages, tasks-finalize). `analyze.md`
specifically: `.kittify/overrides/missions/software-dev/command-templates/analyze.md` is 11,555
bytes; `packs/built-in/missions/mission-steps/software-dev/analyze/prompt.md` is also 11,555
bytes -- byte-identical, confirmed both via `cmp -s` and `wc -c`. §§ 2-3 above (which measured
the override as 6,988 B, stale, dated ~April 2026) describe a state that no longer exists on this
checkout; those sections are left unmodified as the historical record of what this mission
originally diagnosed, per this document's own convention of not rewriting prior sections'
original text.

### 10.2 Re-measured `analyze` render on this merged checkout

The exact `build_prompt()` script from § 4 above, unmodified, staged outside this repository
(never committed) and run with `.venv/bin/python` from the repo root, `git status --porcelain`
confirmed empty before and after (the mutated file, `.kittify/charter/context-state.json`, is
gitignored per `.gitignore:90`, so its mutation does not show in `git status` -- consistent with
§ 9.1's finding):

```text
analyze 16458 367 4114.5
```

**Result: 16,458 bytes / 367 lines / ~4,114.5 estimated tokens** (rounds to the same ~4,115
already on record). `resolve_command("analyze.md", repo_root, mission="software-dev")` was also
re-run: it still returns `tier=override`, path
`.kittify/overrides/missions/software-dev/command-templates/analyze.md`, size 11,555 -- **not**
`tier=package_default`, because the override file still exists (Decision 7 does not delete it).

### 10.3 Why this matches the old "post-deletion" projection exactly, without any deletion happening

§ 4's "Post-deletion re-measurement" paragraph projected that once FR-001 deleted the override,
canonical would resolve instead (11,555 B template) and the rendered total would grow to
**16,458 bytes / 367 lines / ~4,115 estimated tokens**. That figure is reproduced exactly above
-- not because FR-001 executed (it did not; Decision 7 drops it), but because #5133 already
resynced the override's *content* to canonical's exact bytes while leaving the *file* in place.
Resolving through the OVERRIDE tier today renders identically to what resolving through
`PACKAGE_DEFAULT` would have rendered post-deletion, because both paths now read the same 11,555
bytes. The pre-#5133-merge-into-this-branch figure (11,891 B / 305 lines / ~2,973 tokens,
measured while the override was still the stale 6,988 B copy) is superseded by this 16,458 B
figure as the accurate, current figure for what an agent resolving `analyze` in this checkout
receives today. This does not change § 5's diagnosis: `analyze`'s render remains small relative
to the 97,175-112,248 B group measured for `specify`/`plan`/`tasks`/`implement`/`review` in § 4
(the exact comparison ratios differ slightly checkout-to-checkout because those five actions'
renders also depend on `.kittify/charter/context-state.json`'s local first-load state, per § 9.1
and § 9.4 -- a variable independent of this mission's scope).

### 10.4 The projected FR-005/006/007 "post-fix" figures never materialize, for an unrelated reason

Separately from § 10.1-10.3 (which concern FR-001/`analyze`'s own override): § 9's FR-005/006/007
governance-context budget-fix figures (the ~24.5%-26.0% achievable-reduction ceiling, landing
~61,000-72,000 bytes) also never materialize in this mission -- but for the reason Operator
Decision 6 already recorded (FR-005/006/007 dropped from scope, deferred to the maintainer), not
because of anything #5133 changed. #5133 does not touch
`src/charter/activation/context_renderers/token_budget.py`,
`src/charter/activation/context_renderers/bootstrap_text.py`, or
`src/runtime/next/prompt_builder.py` at all -- the two non-materializations (FR-001's
post-deletion figure via Decision 7, and FR-005/006/007's post-fix figures via Decision 6) are
independent of each other and should not be conflated.
