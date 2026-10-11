# Status Doctor Observable Contract

Audience: software-engineer and automation-agent. Updated: 2026-10-11.

Existing entry points: `specify_cli.status.doctor.run_doctor` and `spec-kitty agent status doctor --mission <handle>` (add `--json` for machine output). Use resolved Mission location; no new endpoint or schema is introduced.

| Input | Public result |
|-------|---------------|
| Unreadable/corrupt log, snapshot absent | Return ERROR finding, unhealthy, no expected read/parse exception escape |
| Same log, valid snapshot present | Same failure semantics, no drift traceback |
| CLI text | Visible error and safe recovery, exit 1, no traceback |
| CLI JSON | Existing result shape with `healthy: false`, ERROR finding and safe recovery, exit 1 |
| Accepted mixed/blank/missing/empty history | Existing results preserved; corruption finding absent for legitimate inputs |
| Real drift or WP reconciliation mismatch | Existing findings preserved when history is readable |

Finding message identifies resolved status.events.jsonl path and actual reason; physical record line is 1-based when available. File-I/O failure has no invented line. Recommended action: preserve evidence, restore trusted authoritative history or fix access, rerun doctor; materialize only after readability is restored. No blind deletion/automatic repair/backfill-only guidance for corruption.

Every invocation preserves log/snapshot bytes and absent-file state. Tests include repaired variants on the same fixtures so the diagnosis probe demonstrably distinguishes readable from unreadable authority.
