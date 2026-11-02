# Tooling friction

- The shared VM was heavily loaded (load average above 190); use bounded workers and do not mistake local profiling timeouts for GitHub performance measurements.
- GitHub API calls intermittently returned 502 or stalled. The review sample is diagnostic, not a complete seven-day audit.
- Existing workflow-shape tests pinned duplicate job lists; update those contracts with explicit checks that the stable router gate still owns Ruff and lock validation.
