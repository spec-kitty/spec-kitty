# Tasks: Ownership-Boundary Preservation for Mutating Flows

**Mission**: `ownership-boundary-preservation-01M32KEN`
**Branch**: `fix/ownership-boundary-preservation` (planning base + merge target; `branch_strategy: shared-lane`)
**ATDD base for RED repros**: `main` @ `32cfc272ee` · **GREEN**: each site's final commit
**Inputs**: [spec.md](./spec.md) · [plan.md](./plan.md) · [data-model.md](./data-model.md) · [contracts/ownership-guard-contract.md](./contracts/ownership-guard-contract.md) · [research.md](./research.md) · [quickstart.md](./quickstart.md)

Close the charter class *Ownership Boundaries for Mutating Flows* (charter L463–479) **by
construction**: one shared `specify_cli.asset_preservation` guard (prove-ownership-or-preserve/
archive-with-diagnostic), routed into every same-root destructive site in `cli/commands/init.py`
+ `upgrade/migrations/*.py`, proven closed by a non-vacuous AST gate. 9 work packages, 26
subtasks.

## Cross-cutting constraints (bake into EVERY subtask)

- **ATDD red-first (C-001 / Standing Order #4)** — commit the failing repro BEFORE the fix. It is
  **RED on base `32cfc272ee`** and **GREEN on the WP's final commit**. The reviewer verifies
  red-on-base → green-on-fix.
- **Both directions per routed manifest/canonical site (contract C4)** — the ATDD suite pins BOTH
  (a) an unprovable collision is **PRESERVED** (in place, or archived when the parent is removed)
  with a diagnostic, and (b) a genuinely package-owned target is **STILL REMOVED** and its entry
  pruned. Without the owned-delete direction a preserve-everything guard passes vacuously.
- **In-code ownership-proof rationale (charter L479 / NFR-006)** — every routed site AND every
  allowlist entry carries a one-line in-code comment naming its ownership proof (or why no user
  content can be at that path).
- **Clean gates (NFR-005)** — `ruff check .`, `ruff format --check .`, and `mypy --strict` pass
  with **zero new issues and zero new blanket suppressions** (no new `# noqa` / `# type: ignore`
  / per-file ignore).
- **Terminology + coupling (C-004)** — no new `--feature` CLI surface; **no code in
  `specify_cli/__init__.py`** (avoids the mandatory version-bump + CHANGELOG coupling); no retired
  `sync` tokens in migration prose.
- **Fail-closed toward preservation** — any prover error, unreadable/corrupt manifest, symlink, or
  mixed (tracked+untracked) directory ⇒ unprovable ⇒ preserve.

## Guard API (from [data-model.md](./data-model.md) / [contract C1](./contracts/ownership-guard-contract.md))

```python
guard_destructive_removal(
    path: Path,
    project_path: Path,
    *,
    prover: OwnershipProver,   # ManifestProver | ManagedPathProver | CanonicalContentProver | AnyProver([...])
    backup_parent: Path | None = None,   # MANDATORY when the caller is about to remove path's parent
    dry_run: bool = False,
) -> OwnershipVerdict          # owned=True → caller deletes; owned=False → preserved/archived + diagnostic
```

---

## Subtask Index

| Task | Description | WP | [P] |
|------|-------------|----|----|
| T001 | `OwnershipVerdict` dataclass + `OwnershipProver` Protocol + `__init__`/`__all__` | WP01 | — |
| T002 | `ManifestProver` — two predicates (managed-skills + command-skills), dir all-owned rule | WP01 | — |
| T003 | `ManagedPathProver` — package-managed/regenerable-this-run contract; LEGACY tier never owned | WP01 | — |
| T004 | `CanonicalContentProver` — marker syntaxes + canonical bytes injected as constructor DATA | WP01 | — |
| T005 | `AnyProver` — ordered composite, first non-`None` proof | WP01 | — |
| T006 | `guard.py` decision surface + `backup.py` copy-only core (skills wrapper delegates) | WP01 | — |
| T007 | Unit tests: each prover both directions, guard preserve/owned, in-place-vs-archive, fail-closed, idempotent | WP01 | — |
| T008 | Red-first: FLIP the #4859 bug-locking test to preserve + ADD owned-delete + drifted-hash tests | WP02 | [P] |
| T009 | Route the `apply()` delete loop through `ManifestProver` (managed+command), archive on dir removal | WP02 | [P] |
| T010 | Preserve diagnostic in warnings; prune only actually-removed paths; in-code rationale | WP02 | [P] |
| T011 | Red-first: seed `.kittify/command-templates/custom.md` (config absent AND present) survives; never-seeded ⇒ no dir | WP03 | [P] |
| T012 | Route the `init.py:1568` cleanup `rmtree` via `ManagedPathProver`; in-code rationale | WP03 | [P] |
| T013 | Red-first: "Skipped" governance file survives residual `rmtree`; B1 mission/memory constitution sites | WP04 | [P] |
| T014 | Route `m_3_1_1:~195` (`AnyProver[CanonicalContent,ManagedPath]`) + B1 sites; in-code rationale | WP04 | [P] |
| T015 | Red-first: user `*.sh`/`*.ps1` survive; rewrite expectations "removed N" → "preserved M" | WP05 | [P] |
| T016 | Route `m_0_10_0:175/187` (+ B2 `:250`) via `CanonicalContentProver` ⇒ preserve-all; in-code rationale | WP05 | [P] |
| T017 | Red-first: user `commands/custom.toml` survives; owned toml removed | WP06 | [P] |
| T018 | Route `m_0_10_2:153` via `AnyProver([ManifestProver(command), CanonicalContentProver(# marker)])` | WP06 | [P] |
| T019 | Red-first per site: unprovable clarify/release/profile-context collisions survive | WP07 | [P] |
| T020 | Route m_2_0_11:52, m_2_1_2:55, m_2_2_0:61, m_3_2_0rc43:48 to their provers | WP07 | [P] |
| T021 | Confirm each target carries a version marker (else reclassify) + owned-delete tests + rationale | WP07 | [P] |
| T022 | B3 `m_0_6_7:119`: red-first archive-then-recopy (user member lands in backup) + route | WP08 | [P] |
| T023 | B4 `m_unify:439`: probe bundle divergence → route (canonical) or allowlist with rationale | WP08 | [P] |
| T024 | Extract shared AST census/self-mutation plumbing into `_destructive_op_census.py`; refactor both gates | WP09 | — |
| T025 | Build `test_mutation_ownership_routing.py`: live FS-op census, exhaustiveness, positive-routing, self-mutation, baseline | WP09 | — |
| T026 | `CHANGELOG.md` entry (data-loss class closed; bug-fix, no `__init__.py`/version bump) | WP09 | — |

**[P] legend**: `[P]` = the WP is a parallel lane (Wave 1: WP02–WP08 own disjoint file sets and
run concurrently once WP01 lands). Within a `[P]` lane the red-first subtask still precedes its
fix subtask (ATDD ordering). WP01 (foundation) and WP09 (integration) are not parallel — WP01
blocks all lanes; WP09 goes green only after every lane is routed.

---

## Dependency Graph & Waves

```
WP01  asset_preservation guard + provers + backup + unit tests   (FOUNDATION — blocks all routing)
        │
        ├── WP02  #4859 skill-retirement (flip bug-locking test)      ┐
        ├── WP03  #4861 init command-templates                        │
        ├── WP04  #4862 charter-rename :195 (+ B1 :148/:161)          │  Wave 1 — parallel lanes,
        ├── WP05  scripts m_0_10_0 :175/:187 (+ B2 :250)              │  disjoint owned_files,
        ├── WP06  m_0_10_2 commands/*.toml                            │  no file overlap
        ├── WP07  command retirements (clarify/release/profile-ctx)   │
        └── WP08  borderlines B3 (m_0_6_7) + B4 (m_unify)             ┘
                          │
                          └── WP09  non-vacuous gate + shared plumbing + CHANGELOG  (INTEGRATION — last)
```

- **Sequential (foundation)**: WP01 must land first — every routing WP imports `asset_preservation`.
- **Parallel (Wave 1)**: WP02–WP08 each own exactly one migration module (or `init.py`) + its
  tests — no file overlap, so they run as concurrent lanes.
- **Sequential (integration)**: WP09 (the gate) must land last — its positive-routing + census
  assertions go green only once all sites are routed, and its shared-plumbing extraction depends
  on all routed modules being final.

---

## WP01 — Asset-preservation guard, provers, and backup core

- **Goal**: Build the single shared decision surface `src/specify_cli/asset_preservation/`
  (`__init__.py`, `guard.py`, `provers.py`, `backup.py`) with the four provers, plus its unit
  tests. Every routing WP imports it; no per-site patches.
- **Priority**: Critical — foundation; blocks WP02–WP09.
- **Independent test**: `pytest tests/specify_cli/asset_preservation -q` — every prover proven
  both directions, guard preserve+owned, in-place-vs-archive, fail-closed, idempotent; `mypy
  --strict` clean over the new package.

**Included subtasks**

- T001 `OwnershipVerdict` dataclass + `OwnershipProver` Protocol + `__init__`/`__all__` (WP01)
- T002 `ManifestProver` — two predicates (managed-skills + command-skills), dir all-owned rule (WP01)
- T003 `ManagedPathProver` — package-managed/regenerable-this-run contract; LEGACY tier never owned (WP01)
- T004 `CanonicalContentProver` — marker syntaxes + canonical bytes injected as constructor DATA (WP01)
- T005 `AnyProver` — ordered composite, first non-`None` proof (WP01)
- T006 `guard.py` decision surface + `backup.py` copy-only core (skills wrapper delegates) (WP01)
- T007 Unit tests: each prover both directions, guard preserve/owned, in-place-vs-archive, fail-closed, idempotent (WP01)

**Implementation sketch**

- Reuse `OwnershipProof` (`tool_surface/operations.py:93`, kinds `manifest`/`managed_path`/
  `canonical_content`) as the per-signal vocabulary — do NOT re-declare it. Add `OwnershipVerdict`
  (frozen: `owned`, `proof`, `preserved_path`, `backup_path`, `reason`, `diagnostic`).
- `ManifestProver` wraps two predicates: managed-skills reuse `skills.installer._replacement_is_owned`
  (`content_hash == "sha256:"+sha256(bytes)`, `delivery_mode == "copy"`); command-skills mirror
  `manifest_store.fingerprint_file(path) == entry.content_hash` (bare 64-hex). Directory owned only
  if every tracked member matches and no untracked members exist.
- `CanonicalContentProver` takes `marker_syntaxes` (`<!-- … -->` and `# …`) + optional
  `canonical_bytes` as constructor DATA; one `prove()` path; no marker + no canonical ⇒ `None`.
- `backup.py` extracts a **copy-only** verbatim writer from `skills.installer._archive_existing_path`
  (installer.py:148) EXCLUDING the trailing `_safe_unlink(dest)`; the skills wrapper delegates to it
  (single authority). Dir-granular reuse via `template.manager.back_up_operator_subtrees`.
- Layering: import down to `kernel.atomic`; reuse `template`/`skills`/`manifest_store` peers; nothing
  in `kernel`/`charter` imports `asset_preservation` (NFR-003).

**Deps**: none. **Risks**: prover fragmentation / boundary leak (mitigate: data-injected
`CanonicalContentProver`, `AnyProver` composite); function complexity ≤15 (split guard/provers/
backup). **Est. prompt size**: large (~500 lines; 7 subtasks — split-candidate only if it exceeds
700).

---

## WP02 — Route #4859 standalone-skill retirement through the guard

- **Goal**: Route `m_3_2_0rc45_retire_standalone_skill_surface.apply()`'s delete loop through
  `ManifestProver` (managed **and** command manifests, per path). Preserve/archive an unmanifested
  or byte-drifted retired-basename skill; still remove + prune genuinely-owned ones.
- **Priority**: High — #4859 is a P0 release blocker (silent loss of user-authored governance content).
- **Independent test**: seed an unmanifested `spec-kitty.advise` skill with distinctive bytes; run
  `apply()`; assert bytes survive + `success` + diagnostic — while a manifest-owned retired skill
  (entry + matching hash + copy delivery) is removed and its entry pruned.

**Included subtasks**

- T008 Red-first: FLIP the #4859 bug-locking test to preserve + ADD owned-delete + drifted-hash tests (WP02)
- T009 Route the `apply()` delete loop through `ManifestProver` (managed+command), archive on dir removal (WP02)
- T010 Preserve diagnostic in warnings; prune only actually-removed paths; in-code rationale (WP02)

**Implementation sketch**

- FLIP `test_apply_removes_retired_skill_surface_from_all_known_project_roots` so the unmanifested
  retired skill **SURVIVES** + a diagnostic is asserted (it currently locks in the bug). ADD a NEW
  owned-delete test (managed OR command manifest entry whose `content_hash == sha256(current bytes)`,
  copy delivery, file present ⇒ removed + entry pruned) and a drifted-hash preserve test. Keep
  `test_apply_prunes_managed_and_command_manifests` green (C-006).
- Route the `apply()` delete loop (the `_safe_rmtree`/`_safe_unlink` calls around installer lines
  ~196/198) through `guard_destructive_removal(..., prover=ManifestProver(...))`. When the whole
  skill **directory** is removed, pass `backup_parent` outside the doomed tree
  (`.kittify/.migration-backup/…` or `.backup-<ts>/`) so the archive survives.
- Prune the manifest entry only for actually-removed paths; append `verdict.diagnostic` to
  `warnings` on preservation; add the in-code ownership-proof rationale comment.

**Deps**: WP01. **Risks**: two manifest shapes (managed vs command) — check both per path;
directory removal needs external `backup_parent`. **Est. prompt size**: medium (~300 lines).

---

## WP03 — Preserve user command-templates in init (#4861)

- **Goal**: Route the single `init.py:1568` cleanup `rmtree` (in the 3-name loop
  `("templates","command-templates",".scratch")`) via `ManagedPathProver` so a user-authored
  `.kittify/command-templates/` (LEGACY resolver tier) is preserved while `templates`/`.scratch`
  (regenerable this run) are still deleted.
- **Priority**: High — #4861 is a P0 blocker; closes epic #4792.
- **Independent test**: seed `.kittify/command-templates/custom.md` (known bytes); run the real
  `init` CLI with `config.yaml` ABSENT and (separately) PRESENT; assert bytes survive (in place or
  `.kittify/.backup-<ts>/`), exit 0, diagnostic — while a never-seeded project still ends with no
  `.kittify/command-templates/`.

**Included subtasks**

- T011 Red-first: seed `.kittify/command-templates/custom.md` (config absent AND present) survives; never-seeded ⇒ no dir (WP03)
- T012 Route the `init.py:1568` cleanup `rmtree` via `ManagedPathProver`; in-code rationale (WP03)

**Implementation sketch**

- NEW `tests/init/test_init_command_templates_preservation.py`: seed the custom template, both
  config.yaml states, assert survival + exit 0 + diagnostic; assert never-seeded ⇒ no leftover dir.
  Do NOT edit `test_init_minimal_integration.py:551` — its no-seed deletion case must stay green (C-006).
- It is **ONE** `rmtree` literal in a 3-name loop (init.py:1564-1568) — route it, do NOT allowlist
  (allowlisting a target op would defeat the gate's positive-routing non-vacuity). The
  `ManagedPathProver` returns owned for `templates`/`.scratch` (regenerable) and `None` for
  `command-templates` (operator-authorable LEGACY tier ⇒ never owned-by-name ⇒ preserve).
- Add the in-code ownership-proof rationale comment at the routed site.

**Deps**: WP01. **Risks**: per-name preservation at one literal (proven by behavioural tests, not
the gate); config.yaml-present path must also preserve (US2 scenario 2). **Est. prompt size**:
medium (~280 lines).

---

## WP04 — Preserve "Skipped" governance files in charter-rename (#4862 + B1)

- **Goal**: Route `m_3_1_1_charter_rename.py:~195` `rmtree(constitution_dir)` via
  `AnyProver([CanonicalContentProver, ManagedPathProver])` (preserve-always for governance) so a
  file reported "Skipped" is not destroyed; plus B1 sites (`:148` mission constitution rmtree,
  `:161` stale `memory/constitution.md` unlink).
- **Priority**: High — #4862 (P1), same charter-class root, MVP-launch milestone.
- **Independent test**: `.kittify/constitution/<f>` + a differing `.kittify/charter/<f>`; run the
  migration; assert the "Skipped" file survives (preserved/archived) with a diagnostic and is not
  destroyed by the residual removal — while a no-collision residual dir is still removed.

**Included subtasks**

- T013 Red-first: "Skipped" governance file survives residual `rmtree`; B1 mission/memory constitution sites (WP04)
- T014 Route `m_3_1_1:~195` (`AnyProver[CanonicalContent,ManagedPath]`) + B1 sites; in-code rationale (WP04)

**Implementation sketch**

- Red-first in `test_m_3_1_1_charter_rename.py`: seed constitution + differing charter same-named
  file ⇒ the "Skipped" file SURVIVES; B1: `missions/<m>/constitution` rmtree and stale
  `memory/constitution.md` unlink preserve unless canonical-proven; a no-collision residual dir
  still removes cleanly.
- Governance files carry no marker/canonical ⇒ `AnyProver` returns `None` ⇒ preserve. Where the
  parent (`constitution_dir`) is being removed, archive with an external `backup_parent`; the empty
  residual dir then `rmtree`s fine. This file is one of two permitted to contain "constitution"
  strings — do NOT introduce retired `sync` tokens (C-005).
- Add the in-code ownership-proof rationale comment at each routed site.

**Deps**: WP01. **Risks**: parent-removed archive ordering; "constitution" string permission scope.
**Est. prompt size**: medium (~300 lines).

---

## WP05 — Preserve scripts in python-only migration (m_0_10_0 + B2)

- **Goal**: Route `m_0_10_0_python_only.py:175` (`*.sh`) / `:187` (`*.ps1`) (+ B2 `:250`
  `scripts/tasks/`) via `CanonicalContentProver`, which returns `None` for scripts (no marker, no
  shipped canonical) ⇒ **preserve-all**. Rewrite migration expectations from "removed N" to
  "preserved M unprovable script(s) + warning".
- **Priority**: Medium-High — class closure (charter-mandated preserve-all; the migration currently
  even warns then deletes custom scripts).
- **Independent test**: seed `.kittify/scripts/bash/custom.sh` + `powershell/custom.ps1`; run the
  migration; assert both SURVIVE + a warning; expectation strings assert "preserved M unprovable".

**Included subtasks**

- T015 Red-first: user `*.sh`/`*.ps1` survive; rewrite expectations "removed N" → "preserved M" (WP05)
- T016 Route `m_0_10_0:175/187` (+ B2 `:250`) via `CanonicalContentProver` ⇒ preserve-all; in-code rationale (WP05)

**Implementation sketch**

- Scripts carry no version marker (markers are markdown/`#`-comment for command files, never
  injected into scripts) and the package no longer ships a canonical to byte-match (the migration
  exists *because* it went python-only) ⇒ no content signal ⇒ `CanonicalContentProver.prove()`
  returns `None` ⇒ preserve-all. Document why preserve-all is charter-mandated (charter L472: no
  ownership signal ⇒ preserve + warn); allowlisting these deletes would be dishonest (they delete
  *custom* scripts).
- "owned-delete" is N/A here (no signal) — this migration becomes preserve-all; rewrite its
  expectations and the red-first asserts a user `.sh`/`.ps1` survives. Same rule for B2 `:250`.

**Deps**: WP01. **Risks**: expectation rewrite must not regress the migration's non-script behavior;
`.ps1` on non-Windows fixtures. **Est. prompt size**: medium (~260 lines).

---

## WP06 — Route legacy command TOML sweep (m_0_10_2)

- **Goal**: Route `m_0_10_2_update_slash_commands.py:153` (`commands/*.toml`) via
  `AnyProver([ManifestProver(command-skills), CanonicalContentProver(# marker)])` — prove via the
  command-skills manifest first, `#`-syntax marker as fallback.
- **Priority**: Medium — class closure.
- **Independent test**: seed a user `.kittify/commands/custom.toml`; run the migration; assert it
  survives — while an owned toml (manifest entry with matching hash) is removed.

**Included subtasks**

- T017 Red-first: user `commands/custom.toml` survives; owned toml removed (WP06)
- T018 Route `m_0_10_2:153` via `AnyProver([ManifestProver(command), CanonicalContentProver(# marker)])` (WP06)

**Implementation sketch**

- Prefer the command-skills manifest predicate first: the `.toml` version marker may sit past a
  15-line head window, so a manifest hit is the reliable ownership signal; the `#`-syntax
  `CanonicalContentProver` is the fallback.
- Route the `toml_file.unlink()` at :153 through the guard; delete only on `verdict.owned`; append
  the diagnostic on preservation; add the in-code ownership-proof rationale comment.

**Deps**: WP01. **Risks**: marker past head window (mitigated by manifest-first `AnyProver`).
**Est. prompt size**: small-medium (~220 lines).

---

## WP07 — Route shipped command/skill retirements (clarify/release/profile-context)

- **Goal**: Route four retirement migrations to their provers: `m_2_0_11:52` (clarify, canonical,
  both marker syntaxes), `m_2_1_2:55` (release skill, `ManifestProver`), `m_2_2_0:61`
  (profile-context, canonical), `m_3_2_0rc43:48` (profile-context, canonical). Confirm each target
  actually carries a version marker; else reclassify to manifest / last-shipped-hash.
- **Priority**: Medium — class closure (`m_2_0_11`'s broad `spec-kitty.clarify*` match is exactly
  the charter-warned pattern).
- **Independent test**: per site, a user-authored clarify/release/profile-context file that collides
  by name but is unprovable SURVIVES; a genuinely-owned target is still removed.

**Included subtasks**

- T019 Red-first per site: unprovable clarify/release/profile-context collisions survive (WP07)
- T020 Route m_2_0_11:52, m_2_1_2:55, m_2_2_0:61, m_3_2_0rc43:48 to their provers (WP07)
- T021 Confirm each target carries a version marker (else reclassify) + owned-delete tests + rationale (WP07)

**Implementation sketch**

- Create any missing test files
  (`test_m_2_0_11_remove_clarify_command.py`, `test_m_2_1_2_remove_release_skill.py`,
  `test_m_2_2_0_profile_context_deployment.py`, `test_m_3_2_0rc43_retire_profile_context_command.py`).
- For each canonical site, VERIFY the shipped target carries `spec-kitty-command-version:` in a
  scanned marker syntax; if a target has no marker, reclassify that site to `ManifestProver`
  (command-skills) or a last-shipped-hash `canonical_bytes` — do not over-preserve a genuinely-owned
  target. `m_2_1_2` (`.claude/skills/release`) uses `ManifestProver` (managed skills).
- Each site: route the delete, delete only on `owned`, add owned-delete direction test + in-code
  rationale.

**Deps**: WP01. **Risks**: over-preservation if a marker is absent (mitigated by T021 verification /
reclassification). **Est. prompt size**: medium (~340 lines; 4 sites).

---

## WP08 — Resolve borderlines: ensure-missions recopy (B3) + charter-activation bundle (B4)

- **Goal**: Resolve the two borderline sites by red-first probe. B3 `m_0_6_7:119` — archive-then-
  recopy (in-place preserve impossible: `copytree(dirs_exist_ok=False)` needs dest absent) — archive
  a user/untracked member OUT to an external `backup_parent`, then the legitimate `rmtree`+`copytree`
  proceeds. B4 `m_unify:439` — probe whether the compiled bundle can diverge from `charter.yaml`;
  route (fold-then-delete/canonical) if yes, else allowlist with a documented rationale.
- **Priority**: Medium — class closure; no borderline may be silently dropped.
- **Independent test**: B3 — a user member co-located in an incomplete REQUIRED_MISSION dir lands in
  the backup and the recopy proceeds. B4 — outcome is either a route with a passing preserve test, or
  a documented allowlist entry.

**Included subtasks**

- T022 B3 `m_0_6_7:119`: red-first archive-then-recopy (user member lands in backup) + route (WP08)
- T023 B4 `m_unify:439`: probe bundle divergence → route (canonical) or allowlist with rationale (WP08)

**Implementation sketch**

- B3: red-first — a user/untracked member co-located in an incomplete `REQUIRED_MISSION` dir is
  ARCHIVED (in-place preserve is structurally impossible: `copytree(dirs_exist_ok=False)` needs the
  dest absent). Archive the user member to an external `backup_parent`, then the legitimate
  `rmtree`+`copytree` proceeds; assert the user member lands in the backup.
- B4: probe whether the compiled `governance/directives/metadata/references.yaml` bundle can diverge
  from `charter.yaml`. If it can (content-loss path) → route with a fold-then-delete/canonical check.
  If provably compiled-only → allowlist with an in-code + gate-allowlist rationale (documented, not
  silent). Record the decision in-code either way.

**Deps**: WP01. **Risks**: B3 recopy semantics must not regress the legitimate mission ensure; B4
verdict determines whether it becomes a route or an allowlist row (coordinate with WP09's allowlist).
**Est. prompt size**: medium (~300 lines).

---

## WP09 — Non-vacuous FS-op routing gate + shared plumbing + CHANGELOG

- **Goal**: Extract the shared AST census/self-mutation plumbing from
  `test_destructive_op_routing.py` into `tests/architectural/_destructive_op_census.py` (both gates
  consume it — DIRECTIVE_044); build the new FS-op gate
  `tests/architectural/test_mutation_ownership_routing.py`; register a shrink-only baseline in
  `_baselines.yaml`; add the `CHANGELOG.md` entry.
- **Priority**: High — the class-closure proof; must land last.
- **Independent test**: `pytest tests/architectural/test_mutation_ownership_routing.py
  tests/architectural/test_destructive_op_routing.py -q` — census passes against the real tree,
  planted un-routed op FAILS, drop-one-allowlist-entry FAILS, positive-routing passes per routed
  module; existing git gate still green after the refactor.

**Included subtasks**

- T024 Extract shared AST census/self-mutation plumbing into `_destructive_op_census.py`; refactor both gates (WP09)
- T025 Build `test_mutation_ownership_routing.py`: live FS-op census, exhaustiveness, positive-routing, self-mutation, baseline (WP09)
- T026 `CHANGELOG.md` entry (data-loss class closed; bug-fix, no `__init__.py`/version bump) (WP09)

**Implementation sketch**

- Extract `_iter_py_files`/`_parse`/`_module_string_constants`/`_diff_against_allowlist` + the
  planted-op & drop-one-entry self-mutation harness from `test_destructive_op_routing.py` into
  `_destructive_op_census.py`; refactor BOTH gates to consume it (single authority). The existing
  gate scans git argv literals; the new one scans Python FS `ast.Call`s — complementary, shared
  machinery.
- New gate: LIVE AST census over `cli/commands/init.py` + `upgrade/migrations/*.py` of
  `shutil.rmtree`/`Path.unlink`/`os.unlink`/`os.remove`/`shutil.move`/`Path.rmdir` + `_safe_*`
  wrappers. Each op ∈ {inside guard impl} ∪ {routed via guard chokepoint, no raw literal} ∪
  {frozen rationalized allowlist}. Op-vocabulary EXHAUSTIVENESS self-test. POSITIVE-routing
  assertion per routed module (calls into `asset_preservation`). `rmdir` is an empty-only category
  rationale (raises on non-empty ⇒ cannot silently lose content). Self-mutation BOTH directions.
  Shrink-only baseline registered in `_baselines.yaml`.
- `CHANGELOG.md`: data-loss class closed (init/upgrade migrations now preserve unprovable user
  assets); note it is a bug-fix — **no `__init__.py`/version bump** (C-004).

**Deps**: WP01–WP08 (all routing must be final before census/positive-routing go green).
**Risks**: refactoring the existing gate must keep it green; per-path preservation is proven by
behavioural tests, not the gate (document so readers don't over-trust it). **Est. prompt size**:
large (~500 lines; census + gate machinery — split-candidate only if it exceeds 700).
