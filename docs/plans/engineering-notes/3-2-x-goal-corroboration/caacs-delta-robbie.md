---
title: CaaCS DELTA — Did v3.1.10→v3.2.0 Move the Forensic Needle? (researcher-robbie)
description: "Researcher Robbie's CaaCS DELTA analysis: did v3.1.10 to v3.2.0 move the forensic needle? A quantitative before-after read, read-only."
doc_status: deprecated
updated: '2026-09-30'
---
# CaaCS DELTA — Did v3.1.10→v3.2.0 Move the Forensic Needle? (researcher-robbie)

**Author:** Researcher Robbie (CaaCS quantitative data engine — DELTA / before-after lens).
**Branch:** `design/naming-identity-ssot-alignment` @ 3.2.0 (read-only; no commit, no branch switch).
**Range:** `v3.1.10` (6975ee2, 2026-06-04) .. `v3.2.0` (40e5209, 2026-06-16) — 2317 commits, 2160 non-merge.
**Companion to:** the 3-POV squad (`corroboration-{priti,alphonso,paula}-*.md`) and the static
CaaCS snapshot (`naming-identity-ssot-strangler/caacs-*.md`). Their lenses were *static* (the
shape at HEAD); this note is the **temporal SHIFT** — what the forensic metrics looked like
**before** the strangle vs **after**.

---

## Directives & tactic applied (governance)

- **DIRECTIVE_003 — Decision Documentation Requirement.** Every number below carries the exact
  `git show` / `git log` / `radon cc -s -a` / `git grep` command that produced it, reproducible
  on this branch. No verdict is asserted without a traceable before→after pair.
- **Tactic `forensic-repository-audit` (CaaCS, after Tornhill's *Your Code as a Crime Scene*).**
  Steps applied: (1) exclusion scope, (2) churn hotspots, (6) bug-hotspot, (7) complexity overlay
  (`radon cc`, since `cloc` absent — Python-only scope makes `wc -l` SLOC acceptable), and the
  change-coupling (co-change) extension. Adapted to a **DELTA** frame: every metric is computed
  at *both* tags. **Failure modes honoured:** no rename-following in bulk recipes (flagged per
  file where it bites); complexity overlay is mandatory (raw churn does not measure hardness);
  the v3.2.0 release is **squash/rebase-divergent from v3.1.10** (`git merge-base --is-ancestor`
  returns false) so the in-range churn is the rebased-replay history, not a clean linear ancestry —
  counts are directional and I note where the squash collapses signal.
- **Modes:** *investigation* (mine the two tag boundaries) + *synthesis* (reconcile with the squad).
- **Avoidance boundary:** I supply the empirical before/after dataset; I do not adjudicate
  code-design correctness (alphonso/randy) nor make the final release call.

**Exclusion list (tactic step 1):** lockfiles, `__pycache__`, generated agent dirs (`.claude/`
etc., naturally outside `src/`), JSONL/JSON mission state. Surface is hand-curated Python source.

---

## The before/after metric table — authorities vs consumers

Complexity via `radon cc -s -a` on the blob at each tag (`git show <tag>:<path> | radon`); SLOC via
`wc -l`; in-range churn via `git log v3.1.10..v3.2.0 -- <path>`. **maxCC** = worst single block
(ruff/Sonar ceiling is 15). Δ columns: SLOC and maxCC change. Decimal points normalised from the
locale comma.

### Authority modules (should COOL if strangling works)

| File | v3.1.10 SLOC / avgCC / **maxCC** | v3.2.0 SLOC / avgCC / **maxCC** | ΔSLOC | ΔmaxCC | in-range churn (commits, +/−) | Verdict |
|---|---|---|---|---|---|---|
| `lanes/branch_naming.py` | 321 / 3.3 / **8** | 844 / 2.8 / **8** | +523 | **0** | 7 · +541/−18 | **COOL** (grew in size as the grammar centralised, but **avgCC fell 3.3→2.8 and maxCC held at 8** — pure additive primitives, no hot block) |
| `mission_runtime/context.py` *(net-new; predecessor `core/execution_context.py`)* | 287 / 5.0 / **17** *(as exec_context)* | 274 / 1.5 / **3** | −13 | **−14** | 2 · +290/−15 (new) ; predecessor 9 · +86/−368 | **COOL — strongest** (the authority was **re-extracted simpler**: avgCC 5.0→1.5, maxCC 17→3; predecessor hollowed by **−368 lines** into a shim) |
| `mission_runtime/resolution.py` *(net-new)* | — | 815 / 4.2 / **11** | (born) | (born ≤15) | 5 · +899/−83 | **BORN-COLD** (net-new authority, maxCC 11 under the 15 ceiling at birth) |
| `missions/_read_path_resolver.py` *(net-new)* | — | 424 / 3.2 / **8** | (born) | (born) | 8 · +499/−74 | **BORN-COLD** (maxCC 8, avgCC 3.2) |
| `coordination/surface_resolver.py` *(net-new)* | — | 568 / 3.2 / **14** | (born) | (born) | 8 · +634/−65 | **BORN-COLD** (maxCC 14 — at the ceiling but under it) |
| `coordination/types.py` *(net-new)* | — | 160 / 1.2 / **2** | (born) | (born) | 4 · +166/−5 | **BORN-COLD** (value-object module, avgCC 1.2) |
| `ownership/validation.py` | 261 / 5.6 / **12** | 384 / 4.8 / **12** | +123 | **0** | 7 · +146/−23 | **COOL** (avgCC 5.6→4.8, maxCC held at 12) |
| `status/emit.py` | 479 / 5.5 / **23** | 852 / 7.4 / **40** | +373 | **+17** | 18 · +560/−187 | **HEAT** (the one authority that warmed: avgCC ↑, **maxCC 23→40**, busiest authority by churn) |
| `status/reducer.py` | 213 / 5.0 / **14** | 345 / 7.2 / **24** | +132 | **+10** | 6 · +160/−28 | **HEAT (mild)** (maxCC 14→24 — crossed the ceiling) |
| `status/transitions.py` | 358 / 5.3 / **14** | 131 / 3.4 / **6** | **−227** | **−8** | 4 · +115/−342 | **COOL — clean** (the matrix was **extracted out**: −227 SLOC, maxCC 14→6) |

### Consumer hotspots (should HEAT if under-adopted)

| File | v3.1.10 SLOC / avgCC / **maxCC** | v3.2.0 SLOC / avgCC / **maxCC** | ΔSLOC | ΔmaxCC | in-range churn (commits, +/−, bugfix) | Verdict |
|---|---|---|---|---|---|---|
| `cli/commands/implement.py` | 678 / 8.4 / **34** | 1355 / 6.9 / **57** | **+677** | **+23** | 34 · +1013/−336 · 28 bugfix | **HEAT** (doubled in size, maxCC 34→57; avgCC fell only because volume diluted it) |
| `cli/commands/merge.py` | 1218 / 11.6 / **60** | 3340 / 7.9 / **102** | **+2122** | **+42** | 52 · +2791/−668 · 43 bugfix | **HEAT — severe** (2.7× SLOC, maxCC 60→**102**) |
| `cli/commands/agent/tasks.py` | 3041 / 15.9 / **118** | 4539 / 11.9 / **178** | **+1498** | **+60** | 53 · +2020/−522 · 47 bugfix | **HEAT — severe** (already a god-module; maxCC 118→**178**) |
| `cli/commands/agent/workflow.py` | 1816 / 13.2 / **71** | 2731 / 8.5 / **84** | **+915** | **+13** | 54 · +1789/−852 · 46 bugfix | **HEAT** (+50% SLOC, maxCC 71→84) |
| `cli/commands/agent/mission.py` | 2165 / 11.6 / **158** | 3939 / 10.5 / **220** | **+1774** | **+62** | 60 · +2608/−833 · 46 bugfix | **HEAT — severe** (1.8× SLOC, maxCC 158→**220**, highest churn of the whole surface) |
| `dashboard/scanner.py` | 784 / 5.8 / **21** | 891 / 5.6 / **22** | +107 | +1 | 11 · +322/−130 · 10 bugfix | **STABLE** (the one consumer that did NOT heat materially — small, contained) |

**Reading the table (the load-bearing before/after):**

- **Every extracted authority is COOL or BORN-COLD by max-block complexity** — except the
  `status/` write-side (`emit`/`reducer` HEAT). `mission_runtime/context.py` is the cleanest
  proof the extraction worked: the *same* authority went `avgCC 5.0→1.5, maxCC 17→3` while the
  old home (`core/execution_context.py`) was hollowed by **−368 lines** into a re-export shim.
  `status/transitions.py` lost **227 SLOC** as the matrix was pulled out (maxCC 14→6).
- **Every consumer god-module HEATED hard** — 4 of 6 grew their worst block past it: `merge`
  60→102, `tasks` 118→178, `mission` 158→220. They grew **+677…+2122 SLOC** each and carry
  **28–47 bugfix commits** apiece in-range. The danger migrated *out* of the seam and *into* the
  un-consolidated callers — exactly the squad's "extract-then-under-adopt".
- **The two exceptions are diagnostic.** `status/emit` HEATED *as an authority* (the write-side
  is the live coordination strangler the goals-doc defers to **3.3.x** — so its warming is
  scheduled, not drift). `dashboard/scanner.py` stayed STABLE — the one consumer small enough to
  carry its inline `mid8` without bloating.

---

## Coupling-shift finding (Question 3)

Change-coupling = co-change pairs among the strangled surface, mined with
`git log --name-only --pretty=format:'@%H'` + an AWK pair-counter. The two windows are
**volume-comparable** (consumer-cluster commits: 166 before vs 159 in-range), so per-commit
density is a fair before/after.

| Window | Σ consumer-pair co-changes | consumer-cluster commits | **coupling density (pairs/commit)** |
|---|---|---|---|
| **BEFORE** (`..v3.1.10`) | 213 | 166 | **1.28** |
| **IN-RANGE** (`v3.1.10..v3.2.0`) | 170 | 159 | **1.07** |

**Per-commit consumer coupling dropped ≈16%.** And the *intensity profile flattened*: the
single dominant pre-range edge (`tasks↔workflow` = **40** co-changes, the old whack-a-mole spine)
fell to **16** in-range, with no single pair exceeding 18. So the **tight 2-file ping-pong loosened**.

**But the coupling did NOT dissolve — it broadened.** In-range the top edges spread across the
*whole* orchestrator quad fairly evenly (`tasks↔merge` 18, `mission↔workflow` 18, `mission↔tasks`
16, `tasks↔workflow` 16, `tasks↔implement` 15) and `agent/mission.py` *entered* the hot cluster
(absent pre-range top-12, now in 3 of the top edges). Net: the coupling **moved from one fragile
edge to a diffuse 5-node clique**. Authority↔consumer coupling is the encouraging signal —
consumers now co-change with `status/emit` (8×), `surface_resolver` (6×), `_read_path_resolver`
(6×): they are *starting* to move with the seams, which is what adoption looks like mid-flight.

**Verdict: coupling-density DROPPED (good), but the absolute co-change among the un-consolidated
orchestrators PERSISTS as a diffuse clique (the adoption gap).**

---

## The ratchet law, quantified (Question 4)

Occurrence counts across `src/**/*.py` via `git grep -E <pattern> <tag>`. This is the empirical
test of the squad's law: **"what is ratcheted shrinks; what is not, grows."**

| Idiom | Ratcheted? | v3.1.10 | v3.2.0 | Δ | Reading |
|---|---|---|---|---|---|
| `from specify_cli.status.<sub>` deep-imports (status boundary bypass) | **YES** (`test_status_module_boundary.py`, shrinking allowlist) | **182** | **43** | **−139 (−76%)** | **RATCHETED → SHRANK HARD.** The single clearest "needle moved" number in the dataset. |
| `status/transitions.py` matrix SLOC | YES (extracted behind facade) | 358 | 131 | −227 SLOC | RATCHETED → SHRANK. |
| `kitty/mission…` f-strings (worktree-name guard scope) | PARTIAL (`test_no_worktree_name_guess.py`) | 42 | 63 | +21 | Mixed — the guarded *subset* shrank (squad: 7→5) but the broad token grew as the grammar spread. |
| `mission_id[:8]` (mid8 hand-roll) | **NO literal-ban ratchet** (only 2 incidental test refs; neither a ban) | **4** | **26** | **+22 (+550%)** | **UN-RATCHETED → GREW.** 7 of the 26 are *inside* `mission_runtime` (legit authority-internal); ~19 are consumer hand-rolls. |
| `[:8]` (any 8-slice) | NO | 15 | 46 | +31 | UN-RATCHETED → GREW. |
| `parents[2]` (path re-derive) | NO production ban (38 test refs are fixture math, not a guard) | 4 | 10 | +6 (+150%) | UN-RATCHETED → GREW. |

**The counter-evidence that proves the extraction is real, not cosmetic** — the SSOT vocabulary
spread in lockstep with (and to the same magnitude as) the hand-roll it is meant to replace:

| Canonical SSOT surface | v3.1.10 | v3.2.0 | Δ |
|---|---|---|---|
| `mid8` token (the SSOT grammar) | 67 | **605** | +538 (9×) |
| `resolve_mid8` (canonical mid8 helper) | **0** | **26** | born + adopted to *parity* with the 26 raw `mission_id[:8]` |
| `resolve_action_context` (context SSOT entrypoint) | 3 | 27 | +24 (9×) |
| `branch_naming` SSOT import (consumers routing to the seam) | 14 | 64 | +50 (4.6×) |

**Quantified ratchet law — CORROBORATED.** The one class that got a *shrinking-allowlist ratchet*
(status boundary imports) collapsed **182→43**. Every class left *un-ratcheted* (`mission_id[:8]`
+550%, `parents[2]` +150%, `[:8]` +207%) grew. Meanwhile the canonical replacements were built and
adopted at scale (`mid8` 9×, `resolve_mid8` 0→26, `resolve_action_context` 9×, `branch_naming`
import 4.6×) — so this is **co-existence, not failure**: the SSOT is in place and climbing; the
old idiom persists *only where no ratchet forces the cut*. The law is not a metaphor here — it is
the literal mechanism separating the shrinking surfaces from the growing ones.

---

## Per-goal forensic verdict (Question 5)

| Goal | Forensic SHIFT evidence | Verdict |
|---|---|---|
| **G1** Doctrine→runtime depth | Out of direct scope for this surface set, but the *substrate* cooled: `mission_runtime/{context,resolution}` born-cold (maxCC 3/11) give the `next` loop a clean context authority to render doctrine against. No authority for G1's own seam heated. | **SUPPORTED-for-direction** (substrate cooled; not the focus of this delta) |
| **G2** Core-domain strangler → SSOT | **The headline corroboration.** Authorities COOL/born-cold (context maxCC 17→3; transitions −227 SLOC; 4 net-new authorities born ≤ ceiling), consumers HEAT (merge maxCC 60→102, mission 158→220), and the canonical grammar spread 9× (`mid8` 67→605). The extract→route arc is *visible in the metric shift*, not just the ADRs. | **SUPPORTED — strongest** (the before/after shift directly shows extract-then-under-adopt) |
| **G3** DevEx & enablers | The ratchet that *exists* (status boundary) moved the needle **76%** (182→43) — empirical proof the ratchet enabler works. The gap is enabler *coverage*: no `[:8]`/`parents[2]` literal-ban, so those grew. G3's job for 3.2.x is to *extend* the ratchet wall to the un-guarded idioms. | **SUPPORTED — with a named coverage gap** |

### Biggest un-closed adoption gap

**It is NOT status.** The squad/alphonso flagged status' ~245 bypass imports as the worry; the
**delta shows status is the domain that visibly CLOSED** — deep-imports **182 → 43 (−76%)** under
its module-boundary ratchet, and `transitions.py` shed 227 SLOC. Status is the *success story* of
this range.

**The biggest un-closed gap is IDENTITY / mid8 derivation.** It is the only domain where the
authority is fully built and named (`resolve_mid8` 0→26, `mid8` grammar 67→605) **yet the raw
hand-roll grew in lockstep** (`mission_id[:8]` 4→26, +550%) **because it has no literal-ban
ratchet** (confirmed: only 2 incidental test references, neither a guard). The SSOT and its
bypass now sit at numerical *parity* (26 vs 26) with nothing forcing the cut. That is the
canonical "extract-then-under-adopt" frozen in the metrics — and the cheapest, highest-ROI
3.2.x action is a `mission_id[:8]` literal-ban ratchet pointed at `resolve_mid8`, which would
flip identity from the worst gap to a closing one exactly as the status boundary ratchet did.

### Overall forensic corroboration verdict

**The v3.1.10→v3.2.0 strangling DID move the forensic needle, asymmetrically and exactly as a
mid-flight strangler-fig should.** Authorities cooled or were born cold; consumers heated; the
one domain with a real ratchet (status) collapsed its bypass surface 76%; the domains without one
(identity, path-derivation) grew their bypass even as the SSOT was built beside it. The shift is
**real and directional (the extraction worked), incomplete (adoption lags), and self-limiting
(the ratchet mechanism is proven to close gaps where applied)** — which is the empirical signature
of "extract authority → route consumers, even if adoption lags," not drift.

---

## Reproduction (every command, per DIRECTIVE_003)

```bash
RADON=<path-to-radon>
# complexity+SLOC at a tag:
git show v3.1.10:src/specify_cli/cli/commands/merge.py | $RADON cc -s -a -   # avg + per-block CC
git show v3.1.10:src/specify_cli/cli/commands/merge.py | wc -l               # SLOC
# in-range churn (squash/rebase-divergent range — directional):
git log --oneline v3.1.10..v3.2.0 -- <path> | wc -l
git log --numstat --format='' v3.1.10..v3.2.0 -- <path>                       # +/- lines
# occurrence delta (ratchet law):
git grep -h -E 'mission_id\[:8\]' v3.1.10 -- 'src/**/*.py' | wc -l
git grep -h -E 'mission_id\[:8\]' v3.2.0  -- 'src/**/*.py' | wc -l
# status boundary bypass:
git grep -h -E 'from specify_cli\.status\.[a-z]' v3.1.10 -- 'src/**/*.py' | wc -l   # 182
git grep -h -E 'from specify_cli\.status\.[a-z]' v3.2.0  -- 'src/**/*.py' | wc -l   # 43
# change-coupling: git log --name-only --pretty=format:'@%H' <range> -- <paths> | awk <pair-counter>
```

**Caveats (tactic failure-modes):** (1) v3.2.0 is **squash/rebase-divergent** from v3.1.10
(`git merge-base --is-ancestor v3.1.10 v3.2.0` = false), so in-range churn is the rebased-replay
history — directional, and the squash collapses some per-file granularity. (2) bulk recipes do
**not** follow renames; `mission_runtime/context.py` is tracked against its predecessor
`core/execution_context.py` manually (the −368-line hollowing is the predecessor's in-range delta).
(3) Conventional-Commits inflates raw bugfix %, so the **absolute** bugfix counts are reported, not
densities. (4) `radon mi` floors at 0.0 for the largest modules; maxCC is the load-bearing
complexity series here, not MI.
