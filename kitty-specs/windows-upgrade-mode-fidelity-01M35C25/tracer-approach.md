# Tracer: Approach — windows-upgrade-mode-fidelity

Record the chosen approach and why, evolving as implementation proceeds.

- Scope: #4923 + #4927 folded (shared Windows-POSIX-mode root); #4925 deferred (untraced, needs a Windows run). Operator-confirmed.
- #4923 (crash): close the whole class — a single shared host-safe timestamp/mode helper co-located with `kernel.paths.is_windows`, consumed by all installer.py sites (:174/:963/:969/:981), mirroring the canonical `write_file_verbatim` pattern (asset_preservation/backup.py:38). Plus a non-vacuous arch gate against new unguarded `follow_symlinks` call-sites. Operator-confirmed "close the class".
- #4927 (phantom repairs): extend the existing directory-only `windows_dir_mode_only_divergence` relaxation (skills/command_installer.py) to file/symlink kinds at the planning layer (tool_surface/operations.py:_action, tool_surface/bundles/projection.py:_stage_effect). Suppress chmod effects whose sole divergence is a host-unrepresentable POSIX mode on Windows.
- Verification: Linux CI only, via the is_windows mock seam. Red-first per ADR 2026-07-17-1.
