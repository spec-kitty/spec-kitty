# Research: Windows upgrade POSIX-mode fidelity

Phase 0 decisions. This mission was grounded by a two-lens squad (alignment + scope) against
current `main` and challenged by a post-spec adversarial lens; the load-bearing findings were
verified against the code before folding.

## Decision 1 — Fold #4923 + #4927; defer #4925

- **Decision**: One mission for #4923 (crash) + #4927 (phantom repairs); #4925 (exit-1 no-op) deferred.
- **Rationale**: #4923 and #4927 share the Windows-POSIX-mode root (mode divergence per managed file). #4925's exit-1 is fed by neither the phantom-chmod path nor `surface_drift_failed` (`drifted_reported` is populated only from `consent_required` dispositions — `cli/commands/upgrade.py`); it is genuinely untraced and cannot be faithfully red-first-tested on Linux. Operator-confirmed.
- **Alternatives considered**: (a) all three folded — rejected: #4925 would ship unverifiable, against red-first; (b) #4923 alone — rejected: leaves the cheap, confirmed #4927 fix on the table and both are the same POSIX-mode family.

## Decision 2 — #4923: close the class via `kernel.no_follow`

- **Decision**: Add a host-safe timestamp helper (and a host-safe path-chmod helper) to the **existing** `kernel.no_follow` module; migrate all five `follow_symlinks=False` sites in `skills/installer.py` — {172, 174, 963, 969, 981} — to consume it. Guard with a non-vacuous, shrink-only architectural gate.
- **Rationale**: On Windows `os.utime`/`os.chmod` are not in `os.supports_follow_symlinks`, so every one of the five raises `NotImplementedError`. `kernel.no_follow` already owns the analogous no-`fchmod` handling, so it is the canonical authority (DIRECTIVE_044) — minting a new helper next to `kernel.paths.is_windows` would be a second authority. The canonical default-follow pattern at `asset_preservation/backup.py:38` (no flag) is the shape for regular files and is explicitly NOT part of the class.
- **Alternatives considered**: drop the flag inline at each site (rejected — no single authority, gate can't be non-vacuous); proven-crash-site-only :981 (rejected by operator — leaves :172/174/963/969 latent).
- **Adversarial disposition**: F2 (missing site 172) — **accepted**, folded into FR-001/002. F8 (authority home `kernel.no_follow`, exclude backup.py:38) — **accepted**, folded into C-001/NFR-003.

## Decision 3 — #4927: extend the mode-divergence relaxation to file/symlink

- **Decision**: The phantom-chmod driver is the canonical project-skill projection in `skills/installer.py`: the `write()` chmod branch (`elif before.mode != after.mode`, ~592–593) comparing Windows-observed `before.mode` against the fixed-POSIX `after.mode` from `_expected_project_entries` (~725, `S_IMODE(...) & ~0o222`), reached via canonical/unchanged detection (~785–814). Extend the existing directory-only `windows_dir_mode_only_divergence` (`skills/command_installer.py`) host-aware relaxation to file/symlink kinds, and apply it at the projection so no phantom `chmod` is emitted on Windows. Thread the same relaxation through the completion-recheck seams (`installer.py:_command_parent_receipts` ~507, `managed_skills.py:_recheck_command_completion` ~181).
- **Rationale**: 184 == the plan's per-file chmod count; command skills do not phantom-chmod (`command_installer.install_command` reuses observed mode). Emission-side suppression alone is insufficient — the recheck seams also reject file-mode divergence and would fail a legitimate Windows write with `precondition_changed`.
- **Adversarial disposition**: F1 (site retarget away from `operations._action`/`projection._stage_effect`) — **accepted**, folded into FR-004 (both were wrong: `operations._action` is a shared structural classifier used in effect validation; `projection._stage_effect` is the plugin-bundle path, not the upgrade repair path). F4 (recheck seams) — **accepted**, added FR-005.

## Decision 4 — Extend vs fork the helper (pinned assertion tension)

- **Decision**: Extend the host-aware relaxation under the same authority. `test_managed_skills_host_aware.py` pins `windows_dir_mode_only_divergence(file→False)` ("file modes are never relaxed"); generalizing the helper requires updating that now-outdated dir-only assertion (delete-the-assertion-not-the-test, DIRECTIVE_041) OR a coordinated sibling sharing the same host-detection seam. Plan-level: WP02 picks the concrete shape; a second independent divergence authority is prohibited (C-002).
- **Adversarial disposition**: F3 — **accepted**, folded into C-002.

## Decision 5 — Linux-CI verifiability with a faithful repro

- **Decision**: Mock `kernel.paths.is_windows` for host simulation. For the #4923 crash repro the seam must **raise** on `follow_symlinks=False` (patch `os.utime`/`Path.chmod` or `os.supports_follow_symlinks`), because pre-fix code passes the flag unconditionally and Linux accepts it. Do NOT reuse `_simulate_windows_dir_modes` (it patches `Path.chmod` to a no-op, which masks the crash — passes for the wrong reason).
- **Rationale**: DIRECTIVE_041 — a repro that passes for the wrong reason is worse than none. Use mtime-carrying (backup-restore / symlink) vectors for the utime crash; use a non-suppressed chmod vector (:172/:969) for the chmod crash, since :963 stops firing once #4927 lands (F7).
- **Adversarial disposition**: F5 (raise-not-noop), F6 (mtime vector), F7 (vector sequencing) — all **accepted**, folded into NFR-001 and the US1 scenarios.

## Decision 6 — Gate scope

- **Decision**: Scope the arch gate to chmod/utime with `follow_symlinks=False` in the managed-skill apply surface; reuse the `tests/architectural/test_os_detection_ban.py` + `_os_detection_scan.py` + `_exemptions/` shrink-only template with a self-mutation proof.
- **Rationale**: A bare `follow_symlinks` regex would flag safe `stat`/`is_file` sites and the legitimate `backup.py:38` utime — a false-positive/vacuous gate. F9 — **accepted**, folded into NFR-003.

## Cross-issue note (F10, accepted)

Fixing #4927 turns a converged Windows `upgrade` into a genuine zero-effect no-op — exactly
#4925's precondition. #4925 stays deferred (C-003) but is expected to become cleanly
reproducible on Windows after this lands; that is the deferred re-verification handoff.

## No contested findings dropped

Every adversarial finding (F1–F11) has a recorded disposition above or in the spec:
accepted+folded (F1–F10) or narrowed (F11, symlink-on-Windows edge → "must not raise" only).
