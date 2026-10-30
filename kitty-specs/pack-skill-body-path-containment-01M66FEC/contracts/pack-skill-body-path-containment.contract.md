# Pack-skill `body_path` containment contract

Covers: `charter.offering.pack_skills` (issue #6734). The single authority is
`charter.offering.drg.org_pack_config.resolve_relative_path_within_root`,
anchored at the declaring `*.skill.yaml` file's directory (NOT the pack root —
that anchor belongs to the org-DRG `find_body_path_escapes` contract).

## Accepted inputs

| Input | Behavior |
| --- | --- |
| `body_path` relative, no `..`, resolves inside the skill directory | Resolved path returned; the body is read (`body_text`) or validated (`_read_body`). |
| `body_path` relative, contained, target file missing | Load-time validation: `PackSkillViolation` "body file … not found" (a finding, not an escape). Read-time `body_text`: `FileNotFoundError` from `read_text` (unchanged). |
| Empty / absent `body_path` on a prompt-form skill | Rejected by the model (`models.py` requires it). `body_text` returns `None` for a falsy `body_path`. |

## Refused inputs (identical on both read paths, fail-closed)

| Input | Behavior |
| --- | --- |
| Absolute path (POSIX `/…`, Windows `C:\…`, UNC `\\server\…`) | `PackSkillViolation` "… escapes the skill directory (…)" — wrapped from `OrgPackSubdirEscapeError`. |
| Any `..` component, including a string-level `..` that resolves back inside (e.g. `nested/../body.md`) | Refused. **Stricter than the pre-#6734 hand-roll**, which accepted string-level `..` that resolved inside. |
| Symlink resolving outside the skill directory, including a swap after load (TOCTOU) | Refused at read time, every read. |
| A path that cannot be resolved (symlink loop, embedded NUL byte) | Refused (the primitive converts loops to its escape error; the shared helper also wraps a raw resolve `ValueError`). |

## Invariants

1. Load-time validation (`validate_pack_skill` → `_read_body`) and read-time
   access (`PackSkillRepository.body_text`) judge containment through the ONE
   shared helper `resolve_body_path`; they cannot drift apart.
2. No hand-rolled resolve-then-`is_relative_to` containment exists under
   `charter/offering/pack_skills/` (tier bookkeeping uses are not containment).
3. Load-time skip-and-warn for invalid files is unchanged; the read-time guard
   is defense-in-depth (post-load symlink swap, injected records).
4. `None` from `body_text` is reserved for an unknown id, a missing source, or
   an empty `body_path` — never for an escape.

## Consumers

- `charter/activation/skill_preparation.py::_prepare_one` (renders `SKILL.md`
  into agent folders) — a raise propagates to the stage-2 boundary in
  `specify_cli/skills/catalog.py`, which classifies it as a controlled
  `PackSkillCatalogError` with `__cause__` preserved.
