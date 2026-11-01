# Approach

1. Ground: read the six callers, the #6481 helper and its five pins, the operator triage on
   #6488, and the installed `platformdirs` 4.9.6 source. Recorded as `research.md` D1–D7.
2. Specify: operator ruling fixes the rule (platformdirs semantics) and the scope list.
3. Plan: IC-01 authority → IC-02 callers → IC-03 pins/guard → IC-04 legacy discard →
   IC-05 docs. Four work packages at most.
4. Implement red-first: write the convergence guard against the pre-fix tree and watch it
   fail for `pack_fetch`/`service_artifacts`/`upgrade_notifier` on a faked macOS before
   touching `kernel/user_dirs.py`.
5. Review the integrated diff, then changelog and docs, then a draft PR.

## Mutation proof of the convergence guard (WP04 / T013)

Each caller was reverted, in turn, to its pre-#6488 composition and
`tests/kernel/test_user_dirs_convergence.py` re-run. The file was restored after each run
(`git checkout -- <file>`); no revert is in the diff.

| Reverted caller | pre-#6488 composition used | Result |
|---|---|---|
| `upgrade_notifier` | `user_cache_dir() / "spec-kitty" / "upgrade-check.json"` | 3 failed — `[upgrade_notifier-linux]`, `-darwin`, `-windows` |
| `compat.cache` | `user_cache_dir().parent / ".cache" / "spec-kitty"` | 3 failed — `[compat.cache-linux]`, `-darwin`, `-windows` |
| `pack_fetch` | `user_cache_dir() / "spec-kitty" / "open-packs"` | 3 failed — `[pack_fetch-linux]`, `-darwin`, `-windows` |
| `service_artifacts` | `user_cache_dir() / "spec-kitty" / "services"` | 3 failed — `[service_artifacts-linux]`, `-darwin`, `-windows` |
| `runtime_pkg_notice` | `user_state_dir() / "spec-kitty" / <marker>` | 3 failed — `[runtime_pkg_notice-linux]`, `-darwin`, `-windows` |
| `compat.config` | `user_config_dir().parent / ".config" / "spec-kitty"` | 3 failed — `[compat.config-linux]`, `-darwin`, `-windows` |

6 of 6 detected, each naming the reverted caller. The control run (nothing reverted) is
24 passed.
