# Contract: `lane_test_invocation`

Appears in `spec-kitty implement --json` (new key; every existing key unchanged) and,
rendered, in the implement banner and the implement/review prompts. It is never persisted;
each surface re-derives and re-probes it.

```json
{
  "lane_test_invocation": {
    "cwd": "/abs/path/.worktrees/<slug>-lane-a",
    "command": "PYTEST_ADDOPTS=\"--junitxml={output_file}\" make test-fast",
    "env_set": {"SPEC_KITTY_TEST_DB_NAME": "test_<slug>_lane_a", "PYTHONPATH": "/abs/.../src"},
    "env_unset": ["PYTHONPATH", "UV_PROJECT_ENVIRONMENT", "VIRTUAL_ENV"],
    "path_prepend": [],
    "probe": {
      "status": "verified",
      "origins": {"specify_cli": "/abs/.../src/specify_cli/__init__.py"},
      "foreign": [],
      "reason": null,
      "interpreter": "/usr/bin/python3"
    }
  }
}
```

- `command` is `null` when `review.test_command` is unset; the probe still runs.
- Environment: base minus `env_unset`, plus `env_set`, with `path_prepend` placed in front of
  `PATH`. A lane with its own `.venv` gets that venv's script directory in `path_prepend` and
  no `PYTHONPATH`; a lane without one gets `PYTHONPATH=<lane>/src` (when it has tracked
  `src/` packages) and an empty `path_prepend`. (`path_prepend` added at close-out, aggregate
  review: a bare `python`/`pytest` must run the interpreter the probe checks.)
- An origin that is not an absolute file path (`frozen`, `built-in`) is `unverified`, never
  `foreign`.
- Planning-lane workspaces return `null` for the key; `single_branch` code work packages
  (write checkout) get an invocation rooted at the write checkout.
- `probe.status` ∈ {`verified`, `foreign`, `unverified`}.
