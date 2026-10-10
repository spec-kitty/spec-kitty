# Quickstart — verifying One org-pack chain authority

A reviewer can confirm the mission's outcomes without reading the implementation.

## 1. A later org pack is first-class everywhere

Set up a repo with two org packs (`pack1`, then `pack2`) where a directive
`c-directive` exists only in `pack2`:

```bash
spec-kitty charter list --repo-root <repo> --all        # c-directive now appears in the ORG tier
spec-kitty charter activate directive c-directive --repo-root <repo>   # succeeds (single chain-aware scan)
spec-kitty charter context --include directive:c-directive --repo-root <repo>   # renders pack2's body
```

A directive declared in both packs renders **pack2's** body (last-declared-wins)
on list, `--include`, context, and the loader.

## 2. One authority, enforced

```bash
# The empty-allowlist gate; add a chain-assembly call outside the authority → red.
.venv/bin/python -m pytest tests/architectural/test_org_pack_chain_single_authority.py -q
```

The gate's allowlist has zero entries; a planted violation turns it red, removing
it turns it green, and the owner-bypass control proves the census sees the
authority module.

## 3. A declared-but-missing pack fails loudly where it matters

Declare a pack whose `local_path` does not exist:

```bash
spec-kitty charter activate directive some-id --repo-root <repo>   # refuses, names the pack + `spec-kitty charter fetch`
spec-kitty charter list --repo-root <repo> --all                   # still lists what exists (silent degrade)
```

## 4. Requirement-kinds loader (seam for #5956)

```python
from charter.activation.manifest_loader import load_requirement_kinds
decl = load_requirement_kinds("research", repo_root)   # built-in → org (last-wins) → project; project wins
```

A pack-2 `requirement-kinds.yaml` overrides pack-1 (whole file); a project file
overrides both; a present-but-invalid file refuses; a declared-but-missing pack
refuses (strict chain).

## Scope reminder

The #5956 gate handlers, glossary terms, and grammar integration are **out of
scope** — only the model + loader ship here.
