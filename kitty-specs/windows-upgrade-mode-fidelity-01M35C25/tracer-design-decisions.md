# Tracer: Design Decisions — windows-upgrade-mode-fidelity

Record decisions with rationale.

- DM 01M35C3V2KNMH4NHEHGEVFRF14 (resolved): fix breadth = "close the class" for #4923 — all sites + shared helper + arch gate (Standing Order #5), not proven-crash-site-only. Rationale: :174/:963/:969 share the class and would remain latent; a call-site gate closes it by construction.
- Grounding: alignment lens REFUTED the naive "#4925 == #4927 shared plumbing" theory (surface_drift_failed is not fed by chmod effects); confirmed #4923 + #4927 share only the deeper Windows-POSIX-mode ancestry. Hence #4925 is a genuinely separate, untraced defect — deferred, not folded.
- C-001/C-002: single canonical authority — one host-safe helper, extend (not fork) the existing divergence relaxation. DIRECTIVE_044.

## Post-spec adversarial fold (Reviewer Renata lens, 2026-09-22)

Verdict was "needs specific fixes before plan". Folded (verified F1/F2/F8 against main first):
- F1: #4927 driver retargeted to installer.py write() chmod branch (~592-593) fed by fixed-POSIX _expected_project_entries (~725, `& ~0o222`) + canonical/unchanged detection (~785-814). Dropped operations._action (shared structural classifier) and projection._stage_effect (plugin-bundle path, not upgrade) as WRONG targets. Command skills don't phantom-chmod (reuse observed mode).
- F2: #4923 class = installer.py {172,174,963,969,981} — added missing site 172 (symlink-backup chmod). All five raise on Windows.
- F3/C-002: helper collision — windows_dir_mode_only_divergence is dir-only by design, test pins file→False. FR-004 must generalize the helper (updating the pinned assertion, delete-the-assertion-not-the-test) OR add a coordinated sibling under the same authority; plan resolves. No second divergence authority.
- F4/FR-005: added — must thread relaxation through recheck/receipt seams (installer.py:507, managed_skills.py:181), not just emission, else Windows apply reports precondition_changed.
- F5/NFR-001: repro MUST raise on follow_symlinks=False (is_windows flip alone leaves pre-fix green on Linux); forbid reusing _simulate_windows_dir_modes (no-op chmod masks the crash).
- F6/F7: crash repro must use mtime-carrying (backup-restore/symlink) or non-suppressed chmod vectors; ordinary reconcile writes carry mtime=None and skip line 981; file chmod :963 stops firing once FR-004 lands.
- F8/C-001: authority home = existing kernel.no_follow (not a new helper); exclude backup.py:38 (legit default-follow) from fix+gate.
- F9/NFR-003: gate scoped to chmod/utime follow_symlinks=False in the managed-skill apply surface; reuse test_os_detection_ban.py / _os_detection_scan.py / _exemptions shrink-only pattern.
- F10: FR-004 may newly surface #4925 (converged no-op); noted in Assumptions, stays deferred.
- F11: symlink-on-Windows edge narrowed to "must not raise"; fidelity out of scope.
