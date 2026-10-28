# Approach

- **[2026-10-27][plan] Registry first, command second.** #5212's per-surface `CleanupPolicy` lands first (WP01); the engine (WP02) selects its scope only through that policy and the CLI (WP03) is a thin self-registering doctor sibling. Disposition: planned.
- **[2026-10-27][plan] Reader/doctor-side only.** No event-log door is called; locks are probed with the kernel primitive so ADR 2026-10-22-1's single-writer direction is not affected. Disposition: planned.
