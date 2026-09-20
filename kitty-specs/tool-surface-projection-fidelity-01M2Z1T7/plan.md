# Implementation Plan: Tool-surface projection honesty

**Branch**: `fix/tool-surface-projection-fidelity` | **Date**: 2026-09-20 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `kitty-specs/tool-surface-projection-fidelity-01M2Z1T7/spec.md`
**Investigation**: [research/durable-fix-investigation.md](./research/durable-fix-investigation.md) (DIRECTIVE_052)

## Summary

Make the tool-surface repair projection **honest**: repair every surface its detector flags, converge in one invocation, and report residual drift as a failure instead of exiting 0. Two independent root-cause seams under one anti-pattern:

1. **Session-presence repair applicability (#4782, +llxprt).** A root-level context file (`GEMINI.md`, `LLXPRT.md`) is judged writable by its own parent (the repo root), not a sibling harness command dir (`.gemini/`, `.llxprt/`). A detected-stale, selected surface is never silently `not_applicable`; unrepairable drift is reported `failed`.
2. **Managed-skills completion re-check (#4776 + #4777 + #4134).** `_recheck_command_completion` tolerates host-legitimate non-identity: a directory whose only divergence is a POSIX `mode` the host `os.chmod` cannot represent (Windows) is treated as satisfied, so `upgrade` converges in one run and `--dry-run` reports no phantom `chmod` re-plans; and command-skills manifest content is deterministic (`installed_at`) so a re-check does not fail on a wall-clock diff.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: existing (`typer`, `rich`) — **no new dependency** (supply-chain section N/A)
**Storage**: generated agent-surface files (`GEMINI.md`, `.agents/skills/`, `.claude/`…) + `.kittify/{skills-manifest,command-skills-manifest}.json`; repaired in place
**Testing**: pytest, ATDD red-first; Windows simulated by monkeypatching observed directory `mode` (POSIX-vacuity pattern), never skipped
**Target Platform**: Linux/macOS/Windows CLI
**Project Type**: single (`src/specify_cli/`)
**Performance Goals**: single-pass convergence (NFR-001) — no repeated-invocation requirement introduced; no extra filesystem scan
**Constraints**: detect/repair applicability parity (NFR-002); POSIX correctness preserved off-Windows (NFR-003/C-003); fix generating code, never generated files (C-001); no `packs/` edits (orientation is runtime-generated → no regen gate, NFR-004); honest failure never silent exit-0 (FR-009)
**Scale/Scope**: ~4-5 source files across 2 packages + focused tests

## Constitution Check

- **DIRECTIVE_052 (Prefer Durable Fixes)**: PASS — two systemic seams diagnosed to file:line, both reproduced; #4777 folded (same Windows root cause), #4134 folded (same function); #2527 + orientation-refresh split-brain deferred behind an umbrella epic (`research/durable-fix-investigation.md`).
- **DIRECTIVE_044 (canonical sources / unification)**: PASS for the P0 fix (single shared `SurfaceRepairService`); the orientation-refresh split-brain (≥3 impls) is noted as a deferred structural item, not patched per-copy.
- **DIRECTIVE_034 / C-011 ATDD-first**: PASS by construction (red-first per FR).
- **Honesty standing order**: the fix's core acceptance is "converge or report failed, never exit-0 silent" (FR-009).
- **Template Source Location (C-001)**: PASS — repair the projecting code, never a generated `GEMINI.md`. No `packs/` SOURCE touched → no regen-assets gate.
- **ADRs**: aligned with `2026-06-07-2` (session-presence multi-harness: "do not silently skip a supported harness" — the fix restores this), `2026-07-23-1` (surface vocabulary), `2026-07-19-2` (skill projection). No amendment.
- **`__all__`/dead-symbol**: providers self-register (no `__all__`); keep new helpers intra-module unless consumed cross-module.

## Project Structure

```
kitty-specs/tool-surface-projection-fidelity-01M2Z1T7/
├── plan.md · spec.md · research/{durable-fix-investigation,research}.md
├── data-model.md · quickstart.md · contracts/ · tasks.md (later)

src/specify_cli/
├── session_presence/
│   ├── writers/registry.py            # gemini/llxprt writer defs (check_dir)      [Seam A]
│   └── writers/markdown_rules.py      # MarkdownRulesWriter.can_write               [Seam A]
├── tool_surface/providers/
│   ├── session_presence.py            # repair/_prepare applicability + failed-vs-skip [Seam A]
│   └── managed_skills.py              # _recheck_command_completion, mode pin 0o755  [Seam B]
└── skills/
    ├── command_installer.py           # mkdir/chmod 0o755; installed_at            [Seam B]
    └── manifest.py                    # installed_at determinism (#4134)            [Seam B]

tests/specify_cli/
├── session_presence/                  # writer can_write + orientation refresh
├── tool_surface/{providers,integration}/  # provider repair + doctor/upgrade CLI
└── skills/                            # command_installer / manifest
```

**Structure Decision**: single-project CLI; changes confined to `src/specify_cli/{session_presence,tool_surface,skills}/` + mirrored tests. No packaging/pyproject changes ⇒ `tests/architectural/` only if a gate trips.

## Implementation Concern Map (→ work packages)

| Concern | Files | Requirements | Notes (refined by post-plan brownfield squad) |
|---------|-------|--------------|-------|
| **A. Session-presence repair applicability** | `session_presence/writers/registry.py:42-43` (surgical); `tool_surface/providers/session_presence.py` (tests only) — **do NOT touch `writers/markdown_rules.py` `can_write` body** | FR-001,002,003,004,009; NFR-002 | **Drop `check_dir` from the gemini (`:42`) and llxprt (`:43`) registry rows** so the root-level file is writable by the repo root (matches `AgentsMdWriter`). `can_write` is a redundant 3rd gate (config membership + `configured_tools` guard first), so this can't open an unconfigured-write path; FR-004/009 then resolve structurally (applicable→repaired/failed). Red-first NEW tests: registry `can_write` gemini AND llxprt; repair-path regression (selected+stale+no-dir → repaired, not skipped); NFR-002 detect==repair parity table; migration backfill. KEEP the cursor test `test_markdown_rules_writer.py:207-216` green. |
| **B. Managed-skills completion re-check (host-aware) + manifest determinism** | `tool_surface/providers/managed_skills.py:179` (only); `skills/command_installer.py:514/610` + `manifest_store` for #4134 — **do NOT touch `manifest.py:_retain_entry_times` (wrong/doctrine manifest), do NOT touch `:195`/`:199`/`:308`** | FR-005,006,007,008; NFR-001,003 | Relax ONLY the `:179` directory-effect mode comparison, gated on `kernel.paths.is_windows()` (called through the module attribute), dir-scoped — POSIX behavior unchanged. #4134: exclude `installed_at` from the recheck **comparison hash** (mirror `managed_skills.py:702 _expected_entries` `installed_at=""`), never null the stored value. Red-first NEW tests: Windows-simulated (monkeypatch `kernel.paths.is_windows`→True + observed dir mode≠0o755) single-pass convergence + clean second run + zero `--dry-run` repairs; POSIX file-mode-drift guard; cross-invocation `installed_at` stability. KEEP `[mode]` tests (`test_managed_skills.py:1371/1409`, 0o700-on-POSIX) green — they are the NFR-003 tripwire. |
| **C. Integration verification + CHANGELOG + umbrella** | tests (blast radius), `CHANGELOG.md` | SC-001..006; FR-009 | e2e over both seams incl. honest-failure path; open umbrella epic + file #2527/split-brain under it (bookkeeping at close-out); CHANGELOG entry, no version bump. |

## Parallel Work Analysis

### Dependency graph
```
Concern A (session_presence) ─┐
                              ├─► Concern C (integration verify + CHANGELOG)
Concern B (managed_skills)   ─┘
```
- **A and B are file-disjoint across two packages** → two independent lanes, run in parallel.
- **C** is the capstone (depends on A + B).

### Work distribution
- **A** — session-presence writer + provider (one lane). **B** — managed-skills recheck + skills manifest (one lane). **C** — integration + docs (capstone lane).
- Agent: python-pedro for A/B/C; reviewer-renata reviews each.

### Coordination points
- After A: writer `can_write` + provider repair tests green; enumeration parity test green.
- After B: Windows-mode single-pass convergence + `--dry-run` no-phantom + manifest-determinism tests green; POSIX-correctness regression test green.
- After C: blast-radius green; honest-failure e2e green; CHANGELOG updated (no version bump).

## Complexity Tracking

No charter violations requiring justification. The one tension — DIRECTIVE_052 licensing a broader fix vs locality — was reconciled with the operator (Core + Windows + #4134; #2527 and split-brain deferred behind an umbrella). No unbounded scope.
