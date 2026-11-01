# Tasks — Frontmatter Contract Completion (#6931)

Five work packages, all on `issue-6931-frontmatter-contract`.

| WP | Title | Depends on | Requirements |
| --- | --- | --- | --- |
| WP01 | Frontmatter contract module + upstream parity | — | FR-001, FR-002, NFR-004, C-001 |
| WP02 | Contract validator gate (published sections only) | WP01 | FR-007, NFR-001, NFR-005, C-002, SC-001, SC-004 |
| WP03 | Port the in-repo Divio readers to `kind` | WP01 | FR-009, FR-010, SC-005 |
| WP04 | Corpus migration + body immutability proof | WP01, WP03 | FR-003, FR-004, FR-005, FR-006, FR-008, NFR-002, NFR-003, C-003, SC-003 |
| WP05 | Changelog, gate docs, recorded deferral | WP02, WP04 | FR-011, C-004, C-005, C-006, SC-006 |

Execution order is the table order. WP03 is deliberately before WP04: the readers
must already read `kind` when the migration removes the Divio `type`.
