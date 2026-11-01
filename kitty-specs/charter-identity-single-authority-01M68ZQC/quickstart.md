# Quickstart: verify the identity authority by hand

All commands run in a checkout of this branch.

## 1. The facades and the index agree, in both directions

```bash
uv run python - <<'PY'
from charter.activation.catalog import resolve_offering_root
from charter.activation.identity_index import IdentityIndex
from charter.activation.kind_vocabulary import ArtifactKind, resolve_artifact_urn, resolve_config_id
root = resolve_offering_root()
idx = IdentityIndex.from_roots(offering_root=root, org_roots=None, layer_roots=None)
for token in ("024-locality-of-change", "DIRECTIVE_024", "directive:DIRECTIVE_024", "24"):
    print(token, "->", resolve_artifact_urn(ArtifactKind.DIRECTIVE, token, offering_root=root),
          "| index:", idx.declared_id(ArtifactKind.DIRECTIVE, token))
print("inverse:", resolve_config_id("directive:24", offering_root=root))
PY
```

Expected: all four tokens print `directive:DIRECTIVE_024`, and the inverse prints
`024-locality-of-change`.

## 2. `--cascade` starts from the artifact you named, however you spelled it

In a scratch git project with `.kittify/config.yaml` = `{}` and an activation ledger that
lists the directive (`spec-kitty charter activate directive 024-locality-of-change`):

```bash
spec-kitty charter activate directive directive:DIRECTIVE_024 --cascade all
```

Expected: the output carries the same `Cascade-activated: directive/...` line as the
by-stem run. Before this Mission it printed none, and the ledger silently lacked the
cascaded artifact.

## 3. Unknown tokens still behave as documented

```bash
uv run pytest tests/charter/activation/test_unknown_token_policies_6433.py -q
```

Four rows, one per surface: the runtime gate warns and keeps, the consistency check reports
once and keeps, compile refuses, cascade-source resolution yields no source.
