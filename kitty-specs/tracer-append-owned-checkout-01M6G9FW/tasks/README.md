# Tasks Directory

This directory contains work package (WP) prompt files.

## Directory Structure (v0.9.0+)

```
tasks/
├── WP01-owned-fact-write-surface.md
├── WP02-changelog-docs-record.md
└── README.md
```

All WP files are stored flat in `tasks/`. Status is tracked in `status.events.jsonl`, not in WP
frontmatter.

## Status Tracking

Use `spec-kitty agent tasks move-task` to change WP status:

```bash
spec-kitty agent tasks move-task <WPID> --to <lane>
```

## File Naming

- Format: `WP01-kebab-case-slug.md`
- Examples: `WP01-owned-fact-write-surface.md`, `WP02-changelog-docs-record.md`
