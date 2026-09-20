# Phase 0 Research — Tool-surface projection honesty

Deep grounding: [durable-fix-investigation.md](./durable-fix-investigation.md). Design decisions below.

## Decision 1 — Root-level context files: writable by repo root, not a sibling harness dir (#4782)
- **Decision**: A `MarkdownRulesWriter` whose managed file lives at the repo root (`GEMINI.md`, `LLXPRT.md`) must report `can_write` based on the file's real parent (the repo root, always present), not a `check_dir` sibling command directory. Model on `AgentsMdWriter.can_write` (always True at root). Apply to both gemini and llxprt.
- **Rationale**: detection has no such gate, so the repair gate is the sole cause of the detected-stale-but-skipped no-op. The harness *command* directory is irrelevant to whether a root *context* file can be written.
- **Alternatives rejected**: (a) fix only at the provider `_prepare` seam without touching the writer — leaves `can_write` semantically wrong for other callers; (b) hand-edit `GEMINI.md` — violates C-001/DIRECTIVE_044. Chosen: fix the writer's applicability (narrow, correct) AND ensure the provider never dispositions a selected detected-stale surface `not_applicable` silently — it repairs or reports `failed` (FR-004/FR-009).
- **Guard (NFR-002)**: an enumeration test asserts, for every supported selected writer, detect-applicable == repair-applicable.

## Decision 2 — Completion re-check tolerates host-unrepresentable mode (#4776 + #4777)
- **Decision**: In `_recheck_command_completion` (and the `mode=0o755` pin / `chmod` planning), make directory-mode comparison **host-aware**: where `os.chmod` cannot represent a POSIX mode (Windows), a directory whose only divergence from the plan is that mode is treated as satisfied. On POSIX hosts, full mode correctness is retained (NFR-003).
- **Rationale**: the freshly-created `.agents/skills` can never observe as `0o755` on Windows, so the re-check aborts before doctrine skills apply — needing 3 runs (#4776); the same gap re-plans `chmod` effects forever in `--dry-run` (#4777). One host-aware fix closes both.
- **Alternatives rejected**: (a) drop mode checking entirely — weakens POSIX correctness (violates C-003); (b) always `chmod` then re-observe — the OS still can't represent it, so it loops. Chosen: compare mode only where the host can represent it; otherwise treat the create as satisfied by existence+kind.

## Decision 3 — Deterministic command-skills manifest content (#4134)
- **Decision**: Make re-assessing an unchanged command skill produce byte-stable manifest content — a wall-clock `installed_at` must not drive a completion-re-check file-hash diff (retain prior `installed_at` on same-identity re-write across first-write and multi-skill single-pass churn).
- **Rationale**: distinct from the directory-mode cause but on the same function; a race that makes the re-check fail on a file-sha mismatch.
- **Alternatives rejected**: excluding `installed_at` from the re-check comparison only — leaves the manifest itself non-deterministic for other consumers. Chosen: stabilize the written content.

## Decision 4 — Honest failure, never silent exit-0 (FR-009)
- **Decision**: A residual unrepairable drift (a genuinely unwritable surface, a re-check that legitimately fails on a real difference) is surfaced as a `failed` disposition / non-zero outcome naming the file(s). `not_applicable` is reserved for surfaces the harness genuinely doesn't select — never for a selected, detected-stale, writable surface.
- **Rationale**: the charter honesty standing order; the class the whole mission targets.

## Decision 5 — No new dependencies / no packs edits
- **Decision**: reuse existing stack; orientation is runtime-generated Python (`SessionPresenceContent.render`), not a `packs/` SOURCE → **no regen-assets gate**, supply-chain section N/A.

## Adversarial evidence (post-plan brownfield squad)
No security-impacting dependency decision. Two brownfield lenses ran at the post-plan point-cut. Both **refined** the fix (narrower/more surgical); no operator-blocking scope decision. Dispositions:

| # | Finding | Sev | Disposition |
|---|---------|-----|-------------|
| A1 | Fix must be scoped to the gemini/llxprt **registry rows** (`writers/registry.py:42-43`, drop `check_dir`) — NOT the generic `MarkdownRulesWriter.can_write` body (`markdown_rules.py:134-138`), which the cursor/windsurf/kiro nested-dir contract depends on (`test_agents_md_writer.py:214-256`). | BLOCKER | **CHANGED** — Decision 1 + plan Concern A retargeted to `registry.py:42-43` only; `can_write` body untouched. |
| A2 | `can_write` is a redundant 3rd gate; config membership (`tool in configured`) + `configured_tools` already guard, so dropping the `.gemini` dependence cannot open an unconfigured-write path. FR-004/009 resolve structurally for gemini/llxprt (applicable→repaired/failed); no new disposition branch. | — | **ACCEPTED** — safety proof; the cursor/windsurf/kiro sibling silent-skip stays out of scope. |
| A3 | Test-hint correction: `test_markdown_rules_writer.py:207-216` is **cursor** (keep). Need NEW tests: registry-level `can_write` for gemini AND llxprt; repair-path regression (selected+stale+no-dir → repaired, not skipped); NFR-002 detect==repair parity table; migration backfill test. | SHOULD | **ACCEPTED** — folded into Concern A task list. |
| B1 | Windows-detection: use `kernel.paths.is_windows()` **through the module attribute** (monkeypatchable; never fake `os.name`), scoped to **directory** effects diverging only by `mode`. Not a blanket skip, not feature-detection. | BLOCKER | **CHANGED** — Decision 2 + plan Concern B specify `is_windows()` gate, dir-scoped. |
| B2 | Only the `:179` comparison (observed-vs-planned-`0o755`) needs relaxing; `:195`/`:199`/`:308` are observed-vs-observed same-host and must NOT be touched (over-broadening masks a real parent swap). | BLOCKER | **CHANGED** — Concern B narrowed to `:179` only. |
| B3 | #4134 seam mis-located: `manifest.py:120 _retain_entry_times` is the DOCTRINE manifest; the COMMAND seam is `command_installer.py:514/610` + `manifest_store`. Fix by **excluding `installed_at` from the comparison hash** (mirror `managed_skills.py:702 _expected_entries` `installed_at=""`), NOT by nulling the stored value (breaks preserved-timestamp contract `test_manifest.py:313-321`). | BLOCKER | **CHANGED** — Decision 3 corrected; plan Concern B retargeted. |
| B4 | No POSIX-masking blocker if `is_windows()`-gated + dir-scoped. Existing `[mode]` tests (0o700-on-POSIX, `test_managed_skills.py:1371/1409`) stay green and are the over-broad tripwire. Add a POSIX file-mode-drift guard test. | SHOULD | **ACCEPTED** — NFR-003 guard folded; Seam B is purely additive (new red-first tests only). |
| B5 | Arch gates: `is_windows()` already imported (no dead-symbol exposure); new helpers intra-module (no `__all__`); run `make format-check`. | NOTE | **ACCEPTED**. |

No contested finding dropped. Both seams confirmed file-disjoint (two lanes).
