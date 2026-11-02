# Design decisions

- A full-mode test failure stays a failed job. Full-mode run-all is achieved by matrix cancellation policy and unconditional uploads, not by exit-zero wrappers.
- Router owns static validation; CI Quality owns package construction and genuine clean-install checks. Stable required names remain unchanged.
- Cross-run policy caching is default-branch-only. The HMAC key travels with the cached result and is not authentication against a cache writer. Actions' namespace is the trust boundary, so PR and merge-queue events never restore or publish the directory. Live digest/runtime checks remain, and there is no guard-skip flag.
- Wheel work may be omitted only for nonempty documentation prose outside declared build inputs. Metadata, hooks, pins, source, tests, configuration, unknown events and uncertain diffs build normally.
- No blanket cache deletion, arbitrary debounce, extra module workers, mutable repository sharing or automatic mainline merge.
