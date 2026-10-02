# Tracer — Adversarial Squad Findings (planning point-cut)

Post-plan adversarial review (skeptic + correctness + patterns lenses). Confirmed
findings folded into the design BEFORE implementation.

## Red-first proof (repro squad, real CLI, 4.0.0rc5 on current main)
- **#5390 copy** REPRODUCED: `next` in the copy left the copy's cursor unchanged but
  advanced the ORIGINAL's `completed_steps` `[scoping] → [scoping, methodology]`; the
  methodology artifact existed only in the copy. Root: absolute `run_dir`.
- **#5390 move** REPRODUCED: continuation exit 1, `RUN_STATE_MISSING` at the pre-move
  absolute path.
- **#5389 concurrent** REPRODUCED at count=6: 6 starts, 6 run dirs, only 5 index entries;
  resuming the lost mission created a REPLACEMENT run (run_id changed, step replayed).
  (Note: the stock #5389 reproducer has a *setup* blocker — back-to-back protected-target
  single_branch `mission create` refuses on uncommitted scaffold; the faithful variant uses
  `--commit-to-target` + a commit between creates. Reproducer-setup only, not product.)

## Folded design corrections
- **C1 (resolve-on-load / tokenize-on-save):** the port materializes the ABSOLUTE, contained
  `run_dir` into in-memory entries at the LOAD seam and tokenizes only at the SAVE seam, so
  every existing consumer (`_require_run_state`, `_build_run_ref`, `_resolve_run_dir_for_mission`)
  sees an absolute path unchanged. Tested: a reused `run_ref.run_dir` is absolute.
- **C2 (tokenize must not crash):** the save-side tokenizer relativizes ONLY paths inside
  `repo_root`; a foreign/out-of-tree absolute entry is left untouched (deferred to heal). Tested
  with a mixed index.
- **C3 (same-mission orphan):** start stays outside the lock; inside the lock we re-check the
  mission key — if it now exists we abandon+`rmtree` the just-started orphan and reuse the
  existing entry (same run_id). Tested: same-mission concurrent start → one surviving run dir.
- **I2 (containment realpath):** containment compares `run.resolve()` against
  `repo_root.resolve()` (macOS `/var`↔`/private/var`, symlinked roots); the RETURNED path is the
  lexical `repo_root / token` (or the stored absolute-inside path) so existing equality asserts
  hold. Tested with a symlinked repo root.
- **I3 (single-reader gate wording):** gate = the string literal `feature-runs.json` appears as
  a real string CONSTANT in exactly one module (the port); `state/contract.py` imports the
  constant; AST scan excludes comments/docstrings. `load/save_feature_runs` stay thin delegates
  so monkeypatch seams survive.
- **I4 (concurrency test determinism):** added a deterministic forced-interleave 2-thread test
  (patched `_load_run_index` sleeps after read so the pre-fix unlocked RMW reliably loses; the
  post-fix lock serializes) ALONGSIDE the multi-process two-process guard.
- **I1 (owned-checkout root):** analysis — resolution anchor is always the SAME root that
  loaded the index (each function loads + resolves against one `repo_root`), and the writer
  tokenizes relative to that same root, so there is no NEW root mismatch. Guarded by an
  owned-mission OC-resolution test to prove no regression.
- **N4:** file the audit follow-up issue (template_path/event-log/review-lock) BEFORE close.

## Pre-PR review squad (aggregate diff) — verdict SHIP, no CRITICAL
Folded:
- **IMPORTANT-1** heal now preserves an in-tree absolute's subpath (via
  `serialize_run_dir`) and only re-anchors OUT-of-tree absolutes by run id
  (`_healed_token`) — a working in-place project is never relocated.
- **NIT-2** Phase-3 orphan `rmtree` moved BEFORE resolving the winner, so the
  orphan is cleaned even if winner resolution raises.
- **NIT-3** doctor `_run_index_audit` annotated `repo_root: Path` (dropped the
  `# type: ignore`); command fn renamed `run_index_command`.
- **NIT-1** gate docstring softened to "duplication ratchet, not adversarial
  obfuscation guard" (kept: concatenated-literal evasion is out of scope by design).
Kept as-is: everything else (concurrency, containment, save_index, cross-OS heal
idempotency, contract preservation) reviewed CORRECT.
