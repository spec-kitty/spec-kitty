# Research: Skill surfaces converge

## R-1 Where the historical renders come from
- **Decision**: generate from git history of `src/doctrine/skills/` and `src/charter/offering/skills/` (every commit touching either; ~207 commits, ~563 distinct (path, blob) pairs over ~118 skill paths at `a053b674`), plus the working tree. Key = `<skill>/<relative path>`; value = sorted sha256 hex digests. For `SKILL.md` each historical source also contributes today's shared and native frontmatter projections (`project_skill_bytes`).
- **Rationale**: #7700 proved the stale files are byte-equal to shipped blobs at those paths (`dd83e5b6f`, `b04da00e1`, `7b4f0a63b`, `28890c916`, `53abf91c7`, `4cbba1fbd`; all ancestors of HEAD). Project-root installs hold projected bytes, which the projection variants cover (#2527).
- **Alternatives**: raw blobs only (misses projected project copies); runtime git reads (C-001 forbids); per-release tags only (misses main builds people install, #7700 was a main build).
- **Residual**: an older build whose own projection differed from today's projector is not covered; such files stay kept and reported (never deleted).

## R-2 Storage and regeneration (operator ruling Q1=A, 2026-11-20)
- Package data `src/specify_cli/skills/data/historical_skill_renders.json` (shipped by the existing `src/specify_cli/**/*.json` wheel artifact glob). Generator `scripts/skills/build_historical_skill_digests.py` unions with the existing file (never drops a digest). Test: every current render (raw + projections) is present. `RELEASE_CHECKLIST.md` gains "generator leaves no diff".
- CI clones are shallow, so the test checks current renders (no git), and append-only is enforced by the generator's union (unit-tested).

## R-3 Inventory anchor (#7722)
- **Finding**: `global_asset_root` anchors on `commonpath(home, *roots).parent`; schema-1 inventory keys are relative to that anchor, so moving one root outside home re-anchors and every key stops resolving.
- **Decision**: schema 2 writes absolute POSIX keys. On load, schema-2 keys under the current anchor become anchor-relative in memory (no change to `asset`/`retire`/`prune_missing`); keys outside it are carried through verbatim on write. Schema-1 keys are migrated once: try candidate anchors = ancestors of `$HOME` from the deepest (`home.parent`) to the filesystem root, plus the current anchor; take the first candidate whose resolved path lies under `$HOME`, the kittify home or a current root. A key that resolves under none is dropped from proof (the file stays on disk and is reported by the normal unproven path).
- **Alternatives**: one inventory per root (multiplies files, locks and the inventory's role in `check_assets`); a fixed anchor at the filesystem root (changes every reported path and many tests; Windows multi-drive breaks `commonpath`).

## R-4 #2527 reproduction (FR-012)
- Reproduced on `a053b674` (editable install of this checkout): `spec-kitty init . --ai claude` in an isolated `HOME`, replace `.claude/skills/spk-meta-skill-map/references/spk-skill-map.md` with a shipped earlier blob while the manifest records today's hash, run `spec-kitty doctor tool-surfaces --fix --json`: the surface is listed under `repair.skipped` with no reason, and the file stays stale. **Folded in** (IC-02 refresh, IC-03 reason).

## R-5 #5281 / #2460 current behaviour
- `command_installer.verify` compares disk only to the manifest hash; the strict xfail `tests/specify_cli/skills/test_crlf_skill_render_4998.py::test_doctor_skills_fix_converges_self_consistent_drift` pins the gap.
- `verifier.verify_installed_skills` falls back to the recorded hash when the skill is absent from the registry, so a hash-clean retired entry reads `ok`; `ManagedSkillsProvider._delegate_repair` returns early on `ok`, so `assess_project_skills(retire=True)` never runs.

## R-6 Old-root leftovers (#7723, Q2=A)
- Old root = `Path.home() / <project-relative root>` (e.g. `~/.claude/commands`, `~/.claude/skills`) when the resolved user-global root differs. Proof as in plan IC-06. Report only; follow-up #7758 covers opt-in removal.

## Adversarial evidence
No dependency decision; no security-impacting supply-chain change. An adversarial squad is advisory (charter SO#1); the review step uses an independent reviewer from the orchestrator.
