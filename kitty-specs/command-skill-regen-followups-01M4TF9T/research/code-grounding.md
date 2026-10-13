# Research & Code-Grounding — #6155 command-skill regeneration follow-ups (Phase 0)

**Mission**: `command-skill-regen-followups-01M4TF9T` · **Issue**: spec-kitty/spec-kitty#6155
**Grounded against**: the POST-#6113 shape (`origin/issue-702-codex-skills-drift`, merge-base `c75b82f51eef` = current `main`).
**Prerequisite (BLOCKING)**: PR #6113 (closes #702) is OPEN and **not merged** (`mergeable_state: blocked`). #6155 extends #6113's not-yet-merged `preserve()` change, so the **implement run is held** until #6113 lands on `main`; research/specify/plan/tasks proceed now.

> This note is committed before any spec/plan exists, per the semi-auto-delivery
> grounding-first standing order. It records the responsibility map, the invariants
> that must survive, the gates implicated, the test seams, interactions with open
> P0s / sibling runs, 90-day churn, and the two discovery-squad verdicts.

---

## 1. Is the change still real post-#6113? (alignment gate)

Yes. #6113 began regenerating a drifted DERIVED command-skill projection in
`_CommandBatch.preserve()` **unconditionally** (on the non-`adopt_only` path) and
deferred three follow-ups in its landing summary. Those three deferrals are #6155's
three items verbatim (confirmed against the PR body's *Deferred* bullets and the
2026-10-13 amendment to ADR `docs/adr/4.x/2026-10-04-3-upgrade-reports-one-outcome.md`).
None is resolved on the #6113 branch; all three are genuine on the post-#6113 code.

The premise the whole mission rests on is already true and enforced:
- `.agents/skills/spec-kitty.<command>/SKILL.md` is **DERIVED / git-IGNORED**
  (`shared_skills_projection`, `src/specify_cli/state/contract.py:461`;
  `authority=AuthorityClass.DERIVED`, `git_class=GitClass.IGNORED`).
- `.agents/` is git-ignored in this repo (`.gitignore:136-137`, with the explanatory
  comment at `.gitignore:82`), backfilled by migration
  `src/specify_cli/upgrade/migrations/m_3_2_5_agents_skills_gitignore_backfill.py`
  (cited by the ADR amendment as the premise guarantee).

## 2. Responsibility map of the target files (POST-#6113 line counts)

| File | Lines | Role for #6155 |
|------|------:|----------------|
| `src/specify_cli/skills/command_installer.py` | 1225 | **Primary surface.** `_CommandBatch.preserve()` (drift branch, items 1+2) and `remove_entry()` (item 3); `InstallReport` dataclass + `report_kind` fan-out for item 1's install-side surfacing. |
| `src/specify_cli/state/contract.py` | 1184 | **Read-only authority.** `STATE_SURFACES`, `shared_skills_projection` (`:461`), `AuthorityClass`/`GitClass`. Item 2 reads it at runtime. Pre-dates #6113, byte-identical to main. |
| `src/specify_cli/tool_surface/providers/command_skills.py` | 450 | Provider that builds `overwrite_paths` (`:385-389`) and composes the upgrade assessment. Item 2 edits only the `overwrite_paths` provider comment. Pre-dates #6113. |
| `src/specify_cli/cli/commands/upgrade.py` | 2309 | `upgrade` surfacing: `_apply_prepared_surface_repairs` (~`:1157`), `_surface_repair_payload` (~`:426`), the `--json` payload builders. Item 1's upgrade leg. |
| `src/specify_cli/tool_surface/repair.py` | 521 | `DriftPolicySummary` buckets (~`:345`) + `render_surface_summary_lines` (~`:350`): the shared human renderer for init + upgrade surface summaries. Item 1's human line. |
| `src/specify_cli/cli/commands/init.py` | 1640 | `_install_command_skill_agents` → `command_installer.install(project, agent_key)` (`:155`). Item 1's init leg. |
| `src/specify_cli/cli/commands/agent/config.py` | — | `_register_skill_agent` → `command_installer.install(repo_root, agent_key)` (`:188`), driven by `sync_agents` (`:659`). Item 1's `agent config sync` leg. |

Common install entry for init / agent-config / doctor: `command_installer.install()`
(`command_installer.py:1125`) → `InstallReport`. `upgrade` does **not** use `install()`;
it goes through `prepare_commands(..., prune=True)` + the provider assessment.

## 3. The three items → exact change points (call-site map)

### Item 1 — name each regenerated path (human + `--json surface_repair`), exactly once

**Signal origin (single point):** `_CommandBatch.preserve()` non-adopt drift branch —
`command_installer.py` `if existing is not None and before.sha256 not in (existing.content_hash, digest): if not adopt_only: ... return False`. This `return False` IS the regenerate. Record the `rel` there (e.g. a `_CommandBatch.regenerated: set[str]` / a new `"regenerated"` disposition), distinct from:
- in-sync (`same == True`) → disposition `"unchanged"` → **silent** (acceptance requires silence);
- on-disk == recorded hash but ≠ render (template-version bump) → never enters the drift branch (`before.sha256 in (...)`), lands as `report_kind="added"`/effect `action="update"` → **must stay silent** ("one equal to the recorded hash produces no line").

**Surfacing, two legs** (do not change exit code or outcome kind):
- **install()-based legs (init, agent config sync):** extend `InstallReport`
  (`command_installer.py:185-209`) with a `regenerated` field via a new
  `report_kind="regenerated"` so the existing `getattr(report, command.report_kind).append(...)`
  fan-out (`~:1131`) fills it. Print one per-path notice at `init.py:158` and at
  `agent/config.py:196`.
- **upgrade leg:** the provider path buckets succeeded effects in
  `upgrade.py:_apply_prepared_surface_repairs` (`~:1166-1168`) by `effect.action`
  (`create`→created, else→repaired). A drift-regenerate is `action=="update"` and today
  lands silently in `repaired` (count only). Route the regenerated subset to a new
  `DriftPolicySummary.regenerated` bucket (`repair.py ~:345`), read via a sibling of
  `_preserved_for_consent` (`upgrade.py ~:1177`). Human: one line per path in
  `repair.py:render_surface_summary_lines` (`~:350`). `--json`: add `"regenerated": [...]`
  under `surface_repair` in `upgrade.py:_surface_repair_payload` (`~:426`), threaded through
  the migration / no-migrations payload builders.

Proposed literal (clean of the terminology guard's gated terms):
`Regenerated a generated command skill that differed from the current version: <path>`.

### Item 2 — read the surface class from the state contract at runtime

No by-name helper exists in `contract.py` (only `get_surfaces_by_root/_git_class/_authority`
`:993-1005`). Canonical runtime read (matches the premise-guard test):

```python
from specify_cli.state import contract
_surface = next((s for s in contract.STATE_SURFACES if s.name == "shared_skills_projection"), None)
_regenerate_ok = (
    _surface is not None
    and _surface.authority is contract.AuthorityClass.DERIVED
    and _surface.git_class is contract.GitClass.IGNORED
)
```

`command_installer.py` does **not** import `specify_cli.state.contract` today → a new
intra-layer import is required (no layer-rule impact — both are inside `specify_cli`).
Gate the `return False` regenerate behind `not adopt_only AND _regenerate_ok`; otherwise
**fall through** to the existing consent branch. Compute the lookup once per `_CommandBatch`
(e.g. in `__init__`) rather than per command.

### Item 3 — same rule in `remove_entry` for a retired command's drifted projection

`_CommandBatch.remove_entry()` top guard currently conflates two cases:
`if before.kind == "directory" or (before.kind == "file" and before.sha256 != entry.content_hash): disposition("consent_required", "Edited owned prune/remove candidate retained"); return`.
Split it: **keep refusing** `before.kind == "directory"`; for the **drifted-file** case,
when the same DERIVED/IGNORED gate holds, fall through to the existing delete/prune path
(`self.effect(entry.path, FileState("absent"), ...)` + empty-parent cleanup +
`self.manifest.remove_path(entry.path)`). `remove_entry` is only ever called on **manifest
entries** (`command_installer.py ~:955-959`), so "never touch an unowned path" is
structurally already satisfied — the regression test must still witness it.

## 4. overwrite_paths — reconcile (relocate), do not delete

Post-#6113 the `overwrite_paths` check is reachable **only** on the `adopt_only` path
(after `if not adopt_only: return False`). Item 2's fall-through restructures `preserve()`
so the consent branch is shared by the adopt-only path AND the non-adopt-not-gated path,
which **revives** `overwrite_paths` as the live operator-consent fallback on both paths:

```python
if not adopt_only and _regenerate_ok:
    # record regenerate (item 1), then:
    return False                      # regenerate — DERIVED/IGNORED surface
if rel in self.inputs.consent.overwrite_paths:
    return False                      # explicit exact-path consent (now live on both paths)
self.disposition(rel, "consent_required", "Managed command content has drifted")
return True
```

So **RECONCILE**, not remove. Rewrite the inline DERIVED/IGNORED comment in `preserve()`
(which currently asserts "overwrite_paths consent is subsumed … unconditional") to describe
the runtime gate, and update the provider comment at
`command_skills.py:385-386` so it states that `overwrite_paths` is consulted only on the
fall-through path (surface not DERIVED/IGNORED); on the normal DERIVED/IGNORED surface the
regenerate is unconditional and does not consult consent. (#6155 item 2 names exactly this
comment reconciliation.)

## 5. Invariants that must survive (with citations)

- **Outcome contract unchanged** — item 1 adds a report line only; the exit code and
  `outcome` kind are owned by `UpgradeOutcome` and must not change
  (ADR `2026-10-04-3`; amendment: "this surface simply no longer produces drift"). #6155
  explicitly says: do **not** change the exit code or outcome kind.
- **Decision 5 holds for every OTHER surface** — slash-command files, `.claude/skills/**`
  managed skills, `.claude/agents/*.md` profiles, plugin-bundle components stay as-is
  (ADR `2026-10-04-3` Decision 5, reaffirmed by the amendment; #6155 *Out of scope*).
- **Never clobber non-manifest / third-party paths** — the `existing is None` branch of
  `preserve()` is untouched; `remove_entry` only iterates manifest entries
  (User-Customization-Preservation charter section; installer NFR-002,
  `command_installer.py` module contract).
- **Single canonical authority** — the regenerate decision reads the ONE authority for
  this surface's class (`shared_skills_projection`), rather than hard-coding a second
  premise; the existing premise-guard test pins it (charter Governing Principles;
  CLAUDE.md "Use Canonical Sources").
- **Red-first** — items 2 and 3 are behaviour corrections: the drifted-projection-kept
  (item 2, non-DERIVED fall-through) and the retired-prune (item 3) cases must witness the
  bug through the real reconcile/provider entry points before the fix (charter Standing
  Order #4; ATDD-First Discipline). Item 1 is an added report line → test the human and
  `--json` output.
- **Smallest viable diff / locality** — all behaviour change concentrates in
  `preserve()` + `remove_entry()` in one file; surfacing threads a single new field/bucket
  through existing renderers (charter `change-apply-smallest-viable-diff`, `DIRECTIVE_024`).

## 6. Gates implicated (named individually — per NO_FULL_HEAVY_SUITES_IN_MISSION)

Run the SPECIFIC files, never the bare `tests/architectural/` directory:
- `tests/architectural/test_no_legacy_terminology.py` — terminology guard (gates
  `ceremony` / `status commit` / `status-writing`). The new literal "Regenerated a
  generated command skill that differed from the current version" is clean of all three;
  run per CLAUDE.md's pre-push rule because item 1 adds user-facing prose.
- No `test_pyproject_shape.py` / `test_shared_package_boundary.py` / `test_layer_rules.py`
  impact: the only new import (`specify_cli.state.contract`) is intra-`specify_cli`.
- ADR `2026-10-04-3`'s own gate `tests/architectural/test_upgrade_outcome_single_rendering.py`
  must stay green — item 1 adds a report line but must NOT make presentation code build
  status/errors/closing-line/exit-code itself. Surface the regenerated paths as data the
  outcome/summary owns, consumed by the renderer. (Confirm at implement time that the new
  line routes through the sanctioned `surface_repair` summary, not an ad-hoc `console.print`
  in a presentation function, or the gate fails.)

## 7. Test seams (owning dirs) and cost

- `tests/specify_cli/skills/` — `test_command_installer.py` (install/preserve/remove_entry
  unit coverage, touched by #6113) + the #6113 regression file
  `test_command_installer_derived_regeneration_702.py` (branch-only; carries the premise
  guard `test_702_shared_skills_projection_is_derived_and_ignored` and the in-sync negative
  control). Fast.
- `tests/specify_cli/tool_surface/providers/test_command_skills.py` — provider comment +
  `repair()` overwrite_paths + assessment.
- `tests/specify_cli/cli/commands/test_upgrade_command_skill_drift.py` — the real-CLI
  `upgrade --json` drift leg; item 1 adds assertions on a new
  `surface_repair["regenerated"]` key and the human notice; `#5574` stale-recorded-hash
  convergence case must stay silent.
- `tests/specify_cli/cli/commands/test_doctor_skills.py` — item 3 reaches `prune_stale`
  via `_command_surface_doctor.py:329/362`; `doctor skills` must be green after a retired
  command's drifted projection is pruned.
- Baseline: `make test-fast` (`tests/unit tests/status tests/cli tests/specify_cli/runtime`).
  Known pre-existing env reds live in `tests/upgrade/` (documented in #6113's body:
  `.claude/commands` held-file FileNotFoundError, shallow-clone pinned-ref, wheel-build
  fixture) — classify, do not chase; re-sync a stale venv with
  `uv sync --frozen --all-extras` before attributing a red.

## 8. Interactions with open P0s / sibling runs

- **#6113 (PREREQUISITE, OPEN):** #6155 edits the exact lines #6113 introduces. Merge-
  conflict risk is concentrated in `command_installer.py:~734-781` (`preserve()` +
  `remove_entry()`). **Hold implement until #6113 is on `main`**, then `git fetch origin main`,
  rebase this branch, and build on the merged base.
- **#5710 (OPEN, adjacent):** upgrade has not healed a stale command-skill manifest /
  removed unsafe `.agents/skills` symlinks since the prepared-repair path landed — same
  surface, different gap (manifest healing + symlink safety). Could touch item-2/3 code
  regions. **File-and-link; out of #6155's three items.**
- **#5677 (OPEN, adjacent):** `doctor tool-surfaces --fix` overwrites user-edited managed
  command skills + agent profiles without naming them (gitignored edits lost, exit 0) —
  same "gitignored edit silently replaced" family as item 1's visibility concern, but on
  the `doctor --fix` path, not the reconcile path. **Separate item; file-and-link.**
- No known P0 reproduction (`p0_repro`) touches this surface.

## 9. 90-day churn

`git log --since=2026-07-13 --oneline -- src/specify_cli/skills/command_installer.py
src/specify_cli/tool_surface/providers/command_skills.py src/specify_cli/state/contract.py`
over `main` returns essentially one unrelated commit (`7022b8e7` native-next authoring
lock). All three files are **cold on `main`** in the window (this is a shallow EXPERIMENTAL
checkout). Every #6155-relevant change is concentrated in #6113's single production commit
`5cb93521` (`preserve()`). `contract.py:shared_skills_projection` and
`command_skills.py` `canonical_digest`/`_is_canonical_bytes` pre-date #6113 and are
byte-identical to main → stable read surfaces. `preserve()`/`remove_entry()` in
`command_installer.py` is the one genuine hot spot and the common change point for all three
items.

---

## Discovery squad verdicts

### A. Tracked-issues / related-issues squad

| Issue | What it is | Disposition |
|-------|-----------|-------------|
| **#702** | Parent defect (OPEN, P1): tracked command-skill manifest vs git-ignored `.agents/skills/` projection drift | **PREREQUISITE** — root defect; its fix is PR #6113. |
| **#6113** | OPEN PR (`issue-702-codex-skills-drift`, closes #702): regenerates drifted DERIVED projections in `preserve()` | **PREREQUISITE** — not yet merged; introduces the branch #6155 extends and carries the ADR amendment. All three #6155 items are its *Deferred* bullets. |
| **#5574** | CLOSED: byte-identical-to-render projection misclassified as drift (`upgrade` exited 1) | **REFS** — fixed (#5593); same surface, opposite direction; must stay silent (recorded-hash-stale ≠ regenerate). |
| **#5575** | CLOSED: managed-surface drift had no consent route | **REFS** — fixed (#5593); multi-surface; the other surfaces are the ones Decision 5 leaves unchanged. |
| **#5709** | CLOSED/MERGED PR for #4925: "upgrade reports one outcome"; created ADR 2026-10-04-3 | **REFS** — origin of the contract #6155 operates under; not blocking. |
| **#5745** | OPEN decision: should `upgrade` exit non-zero on unresolved drift? | **OUT OF SCOPE** — fenced out by #6155 and the ADR amendment; this surface stops producing drift, orthogonal to the exit-code decision. |
| **#1780** | OPEN: `doctor` should distinguish missing Codex command skills from `AGENTS.md` session-presence | **OUT OF SCOPE** — different concern/surface (`AGENTS.md`, not the projection). |
| **#1670** | CLOSED: disposition of `spec-kitty.advise` skill + `.agents/` gitignore policy | **REFS** (closed) — historical; no live overlap. |

**#6155 subsumes** exactly its three items; **Refs** #702, #6113, ADR 2026-10-04-3
(amendment 2026-10-13), #5574, #5575, #5745. **Closes** #6155. **No newer sibling** touching
command skills / `agents/skills` / `shared_skills_projection` exists after 2026-10-12.
Adjacent open items #5710 and #5677 are file-and-link (§8), not subsumed, not blocking.

### B. Similar-surfaces / code-grounding squad

Swept every surface that emits `"surface_repair"` effects. **Only command-skills are in
scope.** The `preserve()` + `remove_entry()` pair in `command_installer.py` is the single
change locus for all three items; surfacing threads one new field (`InstallReport.regenerated`
/ `DriftPolicySummary.regenerated`) through existing renderers (init, agent-config,
upgrade). **In-scope-now:** the call sites in §3. **File-and-link (other managed surfaces,
Decision 5 unchanged):** agent_profiles, native_config, session_presence,
bundles/projection repair; and repair.py's 6-rule `run_surface_repair` drift→overwrite path
(it reports command-skill drift as `drifted_reported`, does not regenerate). "No other
command-skill sibling surface in scope" is stated explicitly, not omitted.

---

## Delivery-shape decision (Mission vs Ops)

Blast radius spans a behaviour correction in two methods of one module **plus** reporting
threaded through three CLI surfaces (init, agent-config, upgrade) and their `--json`, with
red-first regressions for two behaviours and output tests for the third — a coherent,
multi-touch change on one surface family. Per the operator brief and semi-auto-delivery's
blast-radius rule, this runs as **one governed Mission** (`single_branch` topology, mirroring
#6113), not an Op.
