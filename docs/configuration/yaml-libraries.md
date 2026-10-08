---
title: 'YAML library choice: ruamel.yaml vs PyYAML'
description: 'When Spec Kitty uses ruamel.yaml versus PyYAML: the round-trip-vs-read-only deciding criterion and the named codebase sites that currently deviate from it.'
doc_status: active
updated: '2026-09-08'
---
# YAML library choice: ruamel.yaml vs PyYAML

> **Document status: current-state with known violations.**
> This document describes the *actual* usage patterns found in the codebase as of
> 2026-06-23. It also states the *intended* deciding criterion. Where usage deviates
> from the criterion, the contradiction sites are named explicitly in
> §3 — they are not hidden by asserting a clean invariant.

---

## 1. The deciding criterion

| Criterion | Library |
|-----------|---------|
| **Round-trip read/write** — file must be rewritten while preserving quotes, comments, indentation, and original formatting (e.g., frontmatter, `config.yaml`, doctrine packs) | **ruamel.yaml** |
| **Read-only simple data** — file is only ever consumed (never rewritten by Spec Kitty), contains no user-authored comments or formatting worth preserving, and the data is flat/simple | **PyYAML `safe_load`** |

### Why ruamel.yaml for round-trip

`ruamel.yaml` exposes the `YAML(typ='rt')` (round-trip) parser and the `CommentedMap` type, which preserve:
- inline and end-of-line comments
- quoted-string style (single vs double quotes, block scalars)
- mapping key order and indentation

Spec Kitty rewrites `.kittify/config.yaml`, WP frontmatter files, and doctrine pack YAMLs in-place. Without round-trip parsing, every write would destroy user comments and reformat the file — which breaks diff readability and silently corrupts user customization.

### Why PyYAML `safe_load` for read-only data

PyYAML's `yaml.safe_load` is a single-call read with no write path. It is appropriate when:
1. The file is generated (e.g., `graph.yaml`, migration fragments, DRG fragments) and has no user-authored comments.
2. The caller only inspects the data and never writes it back.
3. A lightweight, stdlib-style call is sufficient and no formatting invariants exist.

`safe_load` is *not* appropriate for any write-back path — calling `yaml.dump` after a `safe_load` will discard all comments and reformulate quoting.

---

## 2. Verified call sites

### 2.1 ruamel.yaml sites (round-trip, read-write)

| Site | Line | Pattern | Purpose |
|------|------|---------|---------|
| `src/charter/offering/drg/org_pack_config.py` | 216–218 | `_yaml()` factory: `YAML(); yaml.preserve_quotes = True` | Read and write `.kittify/config.yaml` — the operator-facing pack registry |
| `src/specify_cli/frontmatter.py` | 16–18 | `from ruamel.yaml import YAML, CommentedMap` | `FrontmatterManager` — read and write WP frontmatter files in place (rule 1: always use ruamel.yaml; rule 4: preserve comments) |
| `src/charter/offering/yaml_utils.py` | 21 | `from ruamel.yaml import YAML` | `canonical_yaml()` — deterministic sorted-key serializer for hashing; uses ruamel for consistent output |
| `src/charter/offering/drg/loader.py` | 12–13 | `from ruamel.yaml import YAML, YAMLError` | Doctrine relationship graph (DRG) loader — round-trip parse |
| `src/charter/activation/pack_manager.py` | 453–454 | `YAML(); yaml.preserve_quotes = True` | `_load_config()` / `_save_config()` — read + write `.kittify/config.yaml` in `ActiveCharterManager` |
| `src/specify_cli/review/artifacts.py` | 20 | `from ruamel.yaml import YAML` | Review artifact serialization — preserve existing frontmatter style |

### 2.2 PyYAML `safe_load` sites (read-only)

| Site | Line | What is read |
|------|------|-------------|
| `src/charter/offering/drg/org_pack_loader.py` | 504 | `fragment.yaml` from an org pack's `drg/` subdirectory — generated, no comments |
| `src/charter/offering/drg/org_pack_loader.py` | 617 | Individual doctrine artifact YAML files — read-only inspection of `id` key |
| `src/charter/offering/drg/override_policy.py` | 130 | Override policy file — read-only load |
| `src/charter/offering/packs/pack_assembler.py` | 667–669 | Generated graph fragment and `org-charter.yaml` — write path uses `pyyaml.safe_dump`, not round-trip |
| `src/runtime/next/_internal_runtime/discovery.py` | 128, 191 | Runtime discovery config files — read-only |

---

## 3. Known mixed-usage / to-reconcile

> This section names sites where the **same conceptual file** (or file class) is read
> via different libraries in different callers. These are the contradiction sites — not
> a clean invariant.

### 3.1 Primary contradiction: `.kittify/config.yaml`

**The same `.kittify/config.yaml` data is read via two different libraries:**

- `src/charter/offering/drg/org_pack_config.py` (line 216–218): uses **ruamel.yaml** with `preserve_quotes=True`. This is the **write** path — `save_pack_registry()` writes back via the same ruamel instance.
- `src/charter/activation/pack_manager.py` (line 447–476): uses **ruamel.yaml** for reads *and* writes (`_load_config()` / `_save_config()`). This is consistent with the criterion.

However, several *other* callers read `config.yaml`-class data via PyYAML `safe_load`:

- `src/specify_cli/agent_utils/status.py` (line 134): `_yaml.safe_load(config_file.read_text())` reads a config file that is the same shape as `.kittify/config.yaml`.
- `src/specify_cli/cli/commands/agent/tasks_status_cmd.py` (line 910): `yaml.safe_load(config_file...)` reads `.kittify/config.yaml` for the `agent tasks` command. (Two former callers — the sync runtime's config read and an older `agent tasks` call site — were deleted or moved with the sync transport's retirement, Convergence #3881.)

These callers are read-only (no write-back) so PyYAML `safe_load` does not corrupt the file; however they are inconsistent with the pattern in the canonical write paths. If any of these callers were extended to perform writes, they would need to be converted to ruamel.yaml to avoid formatting loss.

### 3.2 Secondary: `pack_assembler.py` dual-use

`src/charter/offering/packs/pack_assembler.py` imports both ruamel (top-level, line 38) for the main assembly pipeline and PyYAML (`import yaml as pyyaml`, lines 667–669) for write-back of generated `graph.yaml` and `org-charter.yaml`. The generated files have no user-authored comments, so `safe_dump` is acceptable. (A former `# ruamel.yaml or pyyaml` ambiguity in the local dashboard's glossary handler went away when the bundled dashboard was removed.)

---

## 4. Aspirational rule (not yet enforced)

The criterion in §1 is the **intended** long-term rule. The following enforcement gaps exist in the current codebase:

1. **No lint guard** enforces the criterion. A developer can add a `yaml.safe_load` call to a write-path module without any automated warning.
2. **Several read-only callers of `config.yaml`** use `safe_load` (§3.1). These are safe today but diverge from the pattern and risk write-back misuse.
3. **`pack_assembler.py`** holds both libraries in the same file without a documented rationale explaining why the fallback to PyYAML is intentional.

A future hardening step (tracked upstream) would:
- Add a ruff or import-guard rule banning `import yaml` (PyYAML) in modules that contain any ruamel import.
- Consolidate all `.kittify/config.yaml` reads through `org_pack_config.load_pack_registry()` so the library choice is centralised.

---

## 5. Quick reference

```
Need to READ AND WRITE a file?
  → ruamel.yaml (YAML(); yaml.preserve_quotes = True)

Need to READ ONLY a generated/simple file?
  → PyYAML: yaml.safe_load(path.read_text(encoding="utf-8"))

Unsure?
  → Default to ruamel.yaml. It is always safe; PyYAML `safe_load` is an
    optimisation for callers with no write-back path.
```

---

*See also:* [`docs/development/3-2-information-architecture.md`](https://github.com/spec-kitty/spec-kitty/blob/main/docs/archive/plans/3-2-doc-publication/3-2-information-architecture.md) — documentation IA index for the `docs/development/` tree.
