# red-proofs-a (#5353 slice-3 follow-up, workstream A)

Break 1: src/specify_cli/cli/commands/_auth_login.py:160 `elif headless:` -> `elif False:`
- Old test_headless_login_e2e.py: RED only after ~301 s (still running at 40 s timeout in my run; 301.45 s in evidence 01M3RBFC).
- New (autouse fixture patches AuthorizationCodeFlow.login -> AssertionError): 3 failed in 1.98 s (tests themselves <1 s each).
  Failing line: test_headless_login_e2e.py:171 `assert result.exit_code == 0` with
  exception=AssertionError('--headless dispatched to the browser (authorization-code) flow').
- After `git checkout -- src/`: 37 passed (tests/auth/integration), 3.56 s.

Break 2: same line `elif headless:` -> `elif True:`
- Old test_browser_login_e2e.py: RED with real network call ("Device flow failed: Network error requesting device code: 403 Forbidden").
- New (autouse fixture patches DeviceCodeFlow.login -> AssertionError): 3 failed, 2 passed; failing line test_browser_login_e2e.py:225
  `assert result.exit_code == 0`, exception=AssertionError('login dispatched to the device flow instead of the browser flow'); no 403/network text in stdout.
  (Wall time 171 s for the run was host load ~16 + import cost; per-test durations all <1 s.)
- After revert: green. `git diff --stat origin/main..HEAD -- src` empty.

Note: first pytest run in a fresh worktree spends ~54 s in a one-time session fixture (pip install); not the test under change.
Note: `spec-kitty dispatch` wrote kitty-ops/<id>.jsonl to the main checkout (/home/user/spec-kitty/kitty-ops); I copied it into the worktree and committed it there.
