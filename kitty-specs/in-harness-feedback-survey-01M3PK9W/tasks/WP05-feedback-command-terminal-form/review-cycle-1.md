---
affected_files: []
cycle_number: 1
mission_slug: in-harness-feedback-survey-01M3PK9W
reproduction_command:
reviewed_at: '2026-09-30T15:50:52Z'
reviewer_agent: cursor:claude:reviewer-renata:reviewer
wp_id: WP05
---

# WP05 Review Feedback — REQUEST_CHANGES

**Reviewer:** cursor:claude:reviewer-renata:reviewer  
**Reviewed at:** 2026-09-30T15:50:00Z  
**Lane worktree:** `.worktrees/in-harness-feedback-survey-01M3PK9W-lane-e`  
**Commits reviewed:** `d92c477f4` (red-first), `09e045e3b` (impl)

## Verdict

**REQUEST_CHANGES** — return to `planned` for fixes. Do not approve until both blocking items below are green under the real `uv run --frozen spec-kitty feedback` entry point (unsandboxed).

---

## Blocking

### B1. EOF / `click.Abort` exits 1 with `Aborted.` (survey must always exit 0)

**Requirement:** WP05 success criteria — “exit status is always 0 for the survey paths”; Review adversarial checklist (f) — Ctrl-C / EOF → clean exit, nothing sent, no traceback. `terminal_form.py` docstring claims it never raises EOF to the caller.

**Observed (real CLI, isolated HOME):**

```text
printf '' | uv run --frozen spec-kitty feedback
# stdout: How would you rate your experience? (1-5):
# stderr: Aborted.
# exit: 1

printf '4\n' | uv run --frozen spec-kitty feedback   # EOF after rating
# exit: 1, "Aborted."
```

Nothing was POSTed (good). No traceback (good). Exit code **1** and Click’s `Aborted.` message (bad).

**Root cause:** `_default_ask` uses `typer.prompt`, which raises `click.exceptions.Abort` on EOF — **not** `EOFError`. `run_form` only catches `(KeyboardInterrupt, EOFError)`, so Abort propagates and Typer exits 1.

Injected-ask unit tests pass because they raise `EOFError` / `KeyboardInterrupt` directly; they never exercise the real prompt path.

**Fix guidance (implementer owns the change):**

- Catch `click.exceptions.Abort` in `run_form` (alongside KI/EOF) and return `FormResult(outcome="aborted", ...)`.
- Ensure `_run_bare_form` still `typer.Exit(0)` on aborted/declined/skipped.
- Add a CliRunner (or real-CLI) acceptance that empty / mid-flow EOF yields **exit_code == 0** and no `Aborted.` line.
- Optionally catch Abort at the command boundary as belt-and-braces.

### B2. `_completion_manifest.json` is not canonical regenerate output

**Requirement:** T028 + Review Guidance — regenerate via `python -m specify_cli.completion --regenerate`; reviewer must confirm byte-identical to canonical output; hand-edit/drift is blocking.

**Observed:**

| Rev | Encoding | Has `feedback` |
|-----|----------|----------------|
| `09e045e3b^` (pre-impl) | literal Unicode (`—`, `✓`) — matches `ensure_ascii=False` | no |
| `09e045e3b` / HEAD | `\u2014` / `\u2713` escapes — `ensure_ascii=True` style | yes |

`completion.render_manifest_json` uses `json.dumps(..., ensure_ascii=False)`. Regenerating in a TEMP copy of the lane produces a file that is **not** byte-identical to the committed manifest (repo-wide escape churn), though **parsed** JSON equals live `generate_manifest()` so `test_completion_manifest_freshness` still passes.

WP05’s in-process workaround re-encoded the entire manifest incorrectly.

**Fix guidance:**

- From the lane: `uv run --frozen python -m specify_cli.completion --regenerate`
- Commit the file that command writes (must be byte-identical to a second regen in a clean TEMP copy).
- Re-confirm `tests/architectural/test_completion_manifest_freshness.py` and `tests/specify_cli/cli/commands/test_completion_fast_path.py`.
- `docs/api/cli-commands.md` freshness already passes; re-run `scripts/docs/build_cli_reference.py` only if that regen dirties it. Do **not** drift `docs/api/agent-subcommands.md` (no WP05 diff today — keep it that way).

---

## Non-blocking

1. **Test gap:** `test_aborted_on_eof` injects `EOFError` only — does not pin `click.Abort` from `typer.prompt` (allowed B1 to ship green).
2. **Coverage:** `feedback.py` 99% (lines 180–181 unreachable `else` after `Choice`); `terminal_form.py` 100%. Fine; optional dead-branch cleanup.
3. **EOF mid-flow exit codes were 1** on both empty and after-rating cases — same B1 defect.

---

## What passed (do not regress)

### Commands / counts (reviewer-run, unsandboxed, lane-e)

| Probe | Result |
|-------|--------|
| Red-first at `d92c477f4` scratch worktree | **8 failed** (tests-only, genuinely RED) |
| `uv run --frozen pytest tests/specify_cli/feedback tests/specify_cli/cli/commands/test_feedback.py -q` | **290 passed, 3 skipped** |
| Coverage (`pytest-cov`) | terminal_form **100%**, feedback.py **99%** |
| `mypy --strict` on feedback + command | **Success: no issues found in 11 source files** |
| `ruff check` + `ruff format --check` + C901 | **All checks passed** |
| Arch: terminology + cli parity + completion freshness + layer_rules | **180 passed** |
| Lazy import + register shape | **12 passed** |
| Egress consent boundary | **43 passed, 2 xfailed** |
| Freshness trio (manifest + cli parity + fast path) | **30 passed** |
| `agent-subcommands.md` vs mission base | **0 diff lines** |

### Real E2E loopback (local HTTP server; isolated HOME/XDG)

| Case | Result |
|------|--------|
| (a) Piped `feedback` → rating/comment/blank email/`y` | **1 POST**; body allowlisted; `trigger=on_demand`, `harness=cli`, **no `email` key**; prompts show `Send feedback? [y/N]` **without URL**; thank-you |
| (b) `--agent-check/--agent-submit/--agent-choice --json` | Contract-valid JSON; submit → **exactly 1 POST**; JSON has **no answers**; consent_question `Send feedback?` |
| (c) `--status` / `--prompts off\|on` | Persists; status has no answers; `https://user:sekrit@host` redacts to host (no userinfo) |
| (d) Dormant (no endpoint) | Calm `No feedback endpoint is configured.`; **nothing sent** |
| (e) Endpoint `127.0.0.1:9` down | Exit **0**, thank-you, **no traceback** |
| (f) EOF | Nothing sent, no traceback — **but exit 1 / Aborted. → B1** |
| (g) `SPEC_KITTY_NON_INTERACTIVE=1` | Hint, immediate return, nothing sent; timeout helpers real + unit-tested |
| Lean `--help` | Hidden agent flags absent; no “telemetry”; `--status`/`--prompts` present |
| Decline `n` | Nothing sent; “Feedback was not sent.” |
| Reuse | `wording.py` only; `is_interactive()` (no raw `isatty`); WP01/03/04 APIs; noqa S105 has rationale; complexity ≤ 15 |

---

## Required re-review evidence

1. Real CLI: empty stdin and mid-flow EOF → **exit 0**, no `Aborted.`, nothing sent.
2. TEMP-copy `python -m specify_cli.completion --regenerate` → **cmp** identical to committed `_completion_manifest.json`.
3. Re-run the feedback pytest path + freshness gates above.
