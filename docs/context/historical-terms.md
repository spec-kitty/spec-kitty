---
title: Historical Terms and Mappings
description: "Legacy Spec Kitty terminology mapped to its current canonical term, with applicable version scope and migration notes for each historical wording."
doc_status: active
kind: Explanation
updated: '2026-11-13T00:00:00Z'
audience:
- profile: internal/lead-developer
  guidance_text: Read this to map a legacy word you meet in old code or docs to the current canonical term.
- profile: internal/ai-collaboration-agent
  guidance_text: Read this before writing output, so you use the current term and never a retired alias.
related:
- context
- context/naming-decision-tool-vs-agent
---
# Historical Terms and Mappings

| Historical term | Current term | Applicable to | Notes |
|---|---|---|---|
| AI agent tooling (runtime executable) | Tool | `1.x`, `2.x` | Use "tool" for concrete products such as Claude Code/Codex/opencode. |
| Agent identity/profile language | Agent | `1.x`, `2.x` | Use "agent" for logical collaborator identity and role. |
| Mission as reusable blueprint | Mission Type | `1.x`, `2.x` | Plain `mission` is no longer canonical for the reusable blueprint layer. |
| Feature as generic tracked-item noun | Mission | `1.x`, `2.x` | `Feature` is a retired alias, prohibited for the Mission domain object in active surfaces (Terminology Canon). Legacy machine keys such as `feature_dir` are still emitted as output aliases. |
| Feature as runtime primary identity | Mission Run (runtime), Mission (tracked item) | `1.x`, `2.x` | A Mission Run is keyed by `run_id`; tracked-item identity is `mission_id` / `mission_slug`. |
| Workflow as primary domain object | Mission Type / Mission Action / Procedure | `1.x`, `2.x` | Keep `workflow` as umbrella prose only. |
| Ad-hoc term definitions in prompts | Canonical glossary entries + append-only events | `1.x`, `2.x` | Preserve decisions and replay history. |
