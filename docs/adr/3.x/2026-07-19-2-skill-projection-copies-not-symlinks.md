---
title: 'Skill projection delivers copies, not symlinks'
description: 'Skill projection always copies files rather than symlinking a machine-global root, ending cross-project action-at-a-distance; stale symlinks convert on the next upgrade.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-07-19'
---

# Skill projection delivers copies, not symlinks

**Status:** Accepted · **Date:** 2026-07-19 · **Supersedes:** the per-project wiring half of [ADR 2026-04-08-3](2026-04-08-3-global-skill-installation-per-project-symlinks.md) (its global-canonical-install decision stands and is reaffirmed here) · **Related:** [#2412](https://github.com/Priivacy-ai/spec-kitty/issues/2412), [ADR 2026-07-07-1](2026-07-07-1-ignored-surface-backfill-migration-pattern.md) (IGNORED-surface backfill pattern)

## Context and Problem Statement

ADR 2026-04-08-3 established two things: canonical skills live in user-global roots (`~/.kittify/agent-skills/`, later `~/.agents/skills/` and per-agent homes), and per-project agent directories reference them **via absolute symlinks**, with a copy fallback for filesystems that cannot symlink.

Issue #2412 first surfaced the commit-side hazard of that wiring: an absolute symlink whose blob is `/Users/<name>/...` is machine-local by construction, and nothing gitignored it. That half was fixed by PR #2423 (contract-registered `IGNORED` surfaces + backfill migration). The issue's remaining ask — *should skills be delivered into the repo root as symlinks at all?* — is what this ADR decides.

The gitignore fix made symlinks safe to **commit**. It did not make them safe to **use**:

1. **Dev-containers and remote mounts.** Mount the repo into a container or sync it to a remote box and every projected skill points at a home directory that does not exist there. The agent sees a dangling link; skills silently vanish with no diagnosable error.
2. **Sandboxed agent harnesses.** Harnesses that restrict file reads to the repo root refuse to resolve a symlink whose target is outside it. The whole point of `.agents/skills/` is to feed third-party agent tooling whose sandboxing spec-kitty does not control.
3. **Global-root moves.** Uninstalling or relocating the CLI's canonical root dangles every projected skill in every repo on the machine simultaneously, until each runs a repair.

## Decision Drivers

* **Skills must be readable wherever the repo is readable.** The projection exists for third-party agents; delivery must not assume the reader can escape the project root or see the author's `$HOME`.
* **Freshness must not regress.** The original symlink rationale — one upgrade touch-point — must be preserved in practice.
* **No per-project state divergence.** Projected files remain managed, regenerated artifacts, never hand-edited project content.
* **Minimal mechanism.** Prefer deleting a delivery mode over adding configuration for one.

## Considered Options

* **Option A: Deliver copies, always (chosen)**
* **Option B: Keep absolute symlinks (status quo, post-#2423)**
* **Option C: Configurable delivery mode (symlink opt-in)**

## Decision Outcome

**Chosen option: Option A — `_project_skill_file` always delivers a copy; the symlink preference is removed rather than made optional.**

The freshness argument that justified symlinks in ADR 2026-04-08-3 is weaker than it looked: the installer re-projects the **full skill set on every init/upgrade/repair run**, so copies refresh whenever the project itself is touched. What symlinks added on top was *cross-project action-at-a-distance* — refreshing the global root silently changed the skill content of every repo on the machine, including repos whose generated command surfaces still matched an older CLI. Per-project refresh on that project's own upgrade is the more correct semantic, not a compromise.

### Mechanics

* `skills/installer.py::_project_skill_file` copies (`shutil.copy2`), never symlinks. A destination file whose content hash already matches the source is left untouched (idempotent re-runs); divergent content is archived to the migration backup root exactly as before.
* A pre-existing projection **symlink** found at the destination is unlinked and replaced with a copy — conversion of existing projects happens organically on their next init/upgrade run, with **no dedicated migration**.
* `skills/verifier.py::repair_skills` always repairs to a copy and records `delivery_mode: "copy"`, healing legacy manifest entries as they are repaired. Verify-side tolerance for not-yet-converted symlinks remains.
* Copies inherit the canonical root's read-only mode (`copy2` preserves it) — deliberate: the projection is not user-editable, matching the symlink-era semantics. Local edits are drift, detected and repairable as before.
* The `delivery_mode` manifest field and its `"symlink"` value remain readable for pre-conversion manifests; new entries are always `"copy"`.

### Consequences

#### Positive

* Projected skills work in dev-containers, remote mounts, and repo-root-restricted sandboxes.
* A global-root move no longer breaks existing projects; their copies keep working until the next refresh.
* Net code deletion: the verifier's symlink repair branch and its global-root resync helper are gone.

#### Negative

* A global-root refresh no longer propagates to a project until that project's next init/upgrade/repair run.
* Duplicate markdown bytes per project (negligible at skill-pack scale).

#### Neutral

* `.agents/skills/` and friends remain `IGNORED` state surfaces (#2423): copies are still per-machine regenerated content, not project content.

## Pros and Cons of the Options

### Option B: Keep absolute symlinks

**Pros:** instant cross-project freshness; zero migration motion.
**Cons:** dangles in containers/remote mounts; unreadable to repo-root sandboxes; global-root moves break every repo at once; the failure mode is always *silent* skill absence.
**Why rejected:** the projection's consumers are exactly the tools most likely to run containerized or sandboxed.

### Option C: Configurable delivery mode

**Pros:** preserves symlink freshness for users who want it.
**Cons:** a config knob, two persistent code paths, and doc/test surface for a mode whose only benefit is marginal freshness; the hazard cases are environmental, not preferential — the user in a dev-container did not choose to be there.
**Why rejected:** minimal-mechanism driver; nobody should have to configure their skills to be readable.

## More Information

* **Issue:** [#2412](https://github.com/Priivacy-ai/spec-kitty/issues/2412) — ask 3 (asks 1–2 landed via PR #2423)
* **Code locations:** `src/specify_cli/skills/installer.py::_project_skill_file`, `src/specify_cli/skills/verifier.py::repair_skills`
* **Superseded wiring:** [ADR 2026-04-08-3](2026-04-08-3-global-skill-installation-per-project-symlinks.md) — the global canonical install target it defines is unchanged
