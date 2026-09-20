# Data Model — Tool-surface projection honesty

## Entity: Orientation writer applicability (Seam A)

| Attribute | Value |
|-----------|-------|
| Writer | `MarkdownRulesWriter(tool, rules_path, append_mode, check_dir)` (`session_presence/writers/`) |
| `can_write(root)` today | `(root / check_dir).exists()` — correct for nested files (cursor/windsurf/kiro), wrong for root-level files that carry a sibling `check_dir` |
| Root-level files | `GEMINI.md` (`check_dir=".gemini"`), `LLXPRT.md` (`check_dir=".llxprt"`) — file parent is the repo root; these are the ONLY two registry rows with a root-level path + sibling check_dir |
| **Surgical fix (post-plan squad)** | **Drop `check_dir` from the gemini/llxprt rows in `writers/registry.py:42-43`** (then `can_write` → nested-parent default = repo root, always present, matching `AgentsMdWriter`). Do NOT mutate the generic `can_write` body — cursor/windsurf/kiro depend on the check_dir gate. |
| Invariant INV-A1 | A root-level context file is writable iff its real parent (repo root) exists — never gated on a sibling command dir. |
| Invariant INV-A2 (NFR-002) | For every supported selected writer: `detect-applicable == repair-applicable`. |
| Invariant INV-A3 (FR-004/009) | A selected, detected-stale surface is repaired or reported `failed` — never silently `not_applicable`. |

**Repair disposition transitions (Seam A):**
```
selected + stale + writable        → repaired
selected + stale + truly unwritable → FAILED (named)            [was: silent not_applicable/exit-0]
not selected (harness absent)      → not_applicable (legitimate)
already current                    → unchanged
```

## Entity: Command-effect completion re-check (Seam B)

| Attribute | Value |
|-----------|-------|
| Function | `_recheck_command_completion` (`tool_surface/providers/managed_skills.py:165-200`) |
| Directory effect | shared parent `.agents/skills` pinned `mode=0o755` (`:127-132`), created `mkdir(0o755); chmod(0o755)` (`command_installer.py:900-901`) |
| Comparison today | `replace(state, mtime_ns=effect.after.mtime_ns) != effect.after` at **`:179`** → for a dir reduces to `mode` (vs pinned `0o755`). Relax `:179` — `:195`/`:199`/`:308` are observed-vs-observed same-host and stay strict. |
| **Twin gate (found in WP02)** | `skills/installer.py:498` `_command_parent_receipts` (via `apply_project_skills:996`) does the SAME planned-`0o755`-vs-observed dir comparison during the **doctrine** apply and is also host-unaware — relaxing `:179` alone leaves doctrine skills refusing on Windows. Both gates get the identical `is_windows()`-gated, dir-mode-only relaxation for FR-006/SC-002 to hold. |
| Host gate | `kernel.paths.is_windows()` (called through the module attribute; monkeypatchable), scoped to **directory** effects diverging only by `mode`. |
| Invariant INV-B1 (NFR-001) | A single `upgrade`/`--fix` converges; an immediate second run makes zero changes. |
| Invariant INV-B2 (NFR-003) | Mode comparison is host-aware: on Windows a dir differing only by mode is satisfied; on POSIX a wrong mode is still a real drift (0o700-on-POSIX tests stay green). |
| Invariant INV-B3 (#4777) | Once converged, `upgrade --dry-run` reports zero repairs (no re-planned `chmod`). |
| Invariant INV-B4 (#4134) | `installed_at` is **excluded from the recheck comparison hash** (mirror `managed_skills.py:702 _expected_entries`), so a cross-invocation wall-clock diff never drives phantom drift; the stored manifest value stays real (preserved-timestamp contract intact). Command seam = `command_installer.py:514/610` + `manifest_store`, NOT `manifest.py:_retain_entry_times`. |

**Completion transitions (Seam B, Windows):**
```
dir created, observed mode ≠ 0o755, host can't represent → SATISFIED (was: raise "Completed command output changed")
dir created, observed mode ≠ expected, host CAN represent → real drift (repair/report)
file content == plan (installed_at stable)              → satisfied
```

## Entity: Repair/upgrade outcome (both seams)

| Field | Meaning |
|-------|---------|
| `repaired[]` | surfaces actually written |
| `skipped[]` / `not_applicable` | ONLY legitimately-unselected surfaces |
| `failed[]` | residual unrepairable drift, named (FR-009) — drives non-zero exit |
| convergence | one invocation reaches canonical state; second run is a no-op |

## Out-of-scope surfaces (C-004, tracked under umbrella)
- #2527 doctrine-skill manifest-hash drift + stray `dist/` (different mechanism/surface).
- Orientation-refresh split-brain: `SessionPresenceManager` / `RefreshOrientationBlockMigration` / `SessionPresenceProvider.repair` — DIRECTIVE_044 structural unification, deferred.
