# Research — CLI Boundary Robustness (Phase 0)

All NEEDS CLARIFICATION resolved before planning; no open markers. Findings below
consolidate the pre-spec squad (researcher-robbie, architect-alphonso,
analyst-annie, reviewer-renata) and the post-spec brownfield squad (paula-patterns,
planner-priti, reviewer-renata). Full detail: [research/post-spec-squad-findings.md](./research/post-spec-squad-findings.md).

## Decision 1 — Canonical `--json` envelope
- **Decision**: Honor the test-frozen #4242 precedent. Errors → `{"ok": false, "error": {"code": <slug>, "message": <text>}}` (`error` is an object). Empty-success → the command's normal success payload with empty collections (no `error` key). `--json` exit code == the command's own non-json exit code (per-command: mostly 1; exit 2 only for `doctor` shim-registry/contracts/tool-surfaces). stdout JSON-only; prose to stderr.
- **Rationale**: DIRECTIVE_044 canonical-source unification; the envelope + `test_doctor_json_not_in_project.py` already exist and are frozen. Inventing a second contract would create split-brain.
- **Alternatives rejected**: a new/uniform envelope (breaks frozen tests, second authority); uniform "exit 2 for not-in-project" (factually wrong — the frozen tests are per-command; would break exit-1 rows and contradict `get_project_root_or_exit`).
- **Ratified**: Decision Moment `01M2NQDWFQ6HY5A8A90VQ0E69H`.

## Decision 2 — Class-closure scope for `--json`
- **Decision**: Bounded — the enumeration gate asserts (a) `json.loads`-parseability on EVERY `--json`-capable command (discovered by structural Typer introspection over 4 flag vocabularies: `json_output`, `--json`, `json: bool`, `output_json`), and (b) canonical error-envelope SHAPE on the error paths of commands this mission ADOPTS. Converge divergent shapes inside touched files. Defer full cross-repo shape convergence (~12 residual shapes) to a filed follow-up.
- **Rationale**: honors expand+close-the-class for the touched surface, keeps the 4.0.0 MVP blast radius bounded (~10–12 files), keeps SC-005/NFR-004 honest, files the residual (DIRECTIVE_040).
- **Alternatives rejected**: full convergence now (~24-file blast radius, touches files with no filed issue); parse-only gate (leaves 8 divergent shapes; re-report risk).
- **Ratified**: Decision Moment `01M2NRXNA9Y4P8QVTRMHP0D5KH`.
- **Post-plan refinement (alphonso Amendment B, within the same bounded intent)**: "parse over ALL --json commands" is narrowed to "parse over an ALLOW-LIST (adopted ∪ verified-already-parseable)". A one-time WP06 discovery/triage classifies all ~70 discovered commands; discovered-but-non-parseable commands (confirmed: `cli/commands/events.py` → error JSON to stderr, empty stdout) are recorded and deferred to the convergence follow-up, excluded from the gate so it cannot red on an unowned command. This preserves the bounded/honest intent of the original resolution rather than reversing it.

## Decision 3 — Config read-site partition (#4600)
- **Decision**: Partition by read *site*, not per-command. Import-time pointer read (`bootstrap/env_file.py`, runs via `__init__.py:35`) fails SOFT (widen `except OSError` → `(OSError, UnicodeDecodeError)`, matching sibling `_read_tier`); content-load reads fail LOUD with a file-naming message rendered in the command layer. env_file stays import-pure (stdlib+kernel; no import-time `os.environ`).
- **Rationale**: the crash is at import for *all* commands; fail-soft there preserves `--version`/`doctor`. A per-command allow/deny list is unnecessary and fragile.
- **Alternatives rejected**: fail-loud at the import site (would re-brick `--version`); per-command classification (fragile, not needed).

## Decision 4 — OptionInfo remedy (#4597/#4598)
- **Decision**: Fix the two OLD-style leak sites + ONE behavioral/output-based negative-assertion guard (no `OptionInfo`/`ArgumentInfo` repr in any `invoke_without_command=True` callback output), parameterized over all 5 such callbacks. Fix #4598 at the call site (pass `include_inactive=False`). No AST/binding-style gate.
- **Rationale**: the class is near-closed (only 2 leak); an output-based guard cannot mislabel the safe `Annotated[...] = <real>` form (it never inspects binding style). Operator-ratified fix-2+small-guard.
- **Alternatives rejected**: AST arch-gate (low-value against a near-empty class; risks mislabeling safe sites); callee sentinel-coercion (spreads the defense).

## Decision 5 — #4643 ownership boundary
- **Decision**: `agent_utils/status.py` returns pure data (no `console.print`, no stray `error` key on the exit-0 empty-success payload); `tasks_status_cmd.py` owns the stream/format decision and routes through the seam.
- **Rationale**: removes the ownership confusion (data-builder usurping the stream decision), not just the symptom.

## Foldable issues (planner-priti census)
- **Fold (closed-by-construction)**: #4533 (add `archive.py`/`materialize.py` to gate surfaces), #4532.
- **Parent link**: #4646 (OptionInfo family) — #4597/#4598 are closed instances; #2779 deferred.
- **Sibling epic (not parent)**: #2899 (traversal-guard `ValueError`). **Defer**: #4642, #4637 (state-file robustness), #2605 (`implement --json` stdout).
- No duplicates of the 5 filed issues.

## Supply-chain security (DIRECTIVE_051)
- **N/A — no dependency added, upgraded, or removed.** The mission uses existing pinned deps (typer, rich, ruamel.yaml, pytest). No registry-authenticity, freshness, or lifecycle-script (`preinstall`/`postinstall`) exposure. No Node/npm surface. No adversarial supply-chain evidence required.

## Adversarial evidence dispositions (contracts/adversarial-evidence-contract)
Post-spec squad contested findings and their disposition:
- Exit-code "exit 2 for not-in-project" over-claim (renata A) → **changed** (C-001 corrected).
- Parse-only gate under-closes the class (paula B1) → **changed** (bounded shape-gate, Decision 2).
- Helper ripple to unowned files (paula O1) → **changed** (defaulted param + WP05 assignment).
- SC-005 tri-state not decidable (renata E) → **changed** (2-state reframe).
- NFR-004 success-shape over-reach (renata H) → **changed** (error-envelope only).
- Full cross-repo convergence (paula L4) → **deferred_with_rationale** (filed follow-up).
No contested finding silently dropped.
