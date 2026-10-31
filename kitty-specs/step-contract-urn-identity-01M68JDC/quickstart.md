# Quickstart — verify step-contract URN identity by hand

## 1. See the bug on the pre-fix tree

```bash
cd <repo-root>
uv run python - <<'PY'
import dataclasses
from pathlib import Path
from charter.activation._drg_helpers import load_validated_graph
from charter.activation.drg_activation import filter_graph_by_activation
from charter.activation.identity_index import IdentityIndex
from charter.activation.pack_context import PackContext
from charter.offering.artifact_kinds import ArtifactKind

repo = Path.cwd()
ctx = dataclasses.replace(
    PackContext.from_config(repo),
    activated_mission_step_contracts=frozenset({"documentation-accept"}),
)
index = IdentityIndex.build(repo)
print("authority:", index.urn(ArtifactKind.MISSION_STEP_CONTRACT, "documentation-accept"))
uris = {n.urn for n in filter_graph_by_activation(load_validated_graph(repo), ctx, identity=index).nodes}
print("node present:", "mission_step_contract:documentation/accept" in uris)
PY
```

Pre-fix: `authority: mission_step_contract:documentation-accept`, `node present: False`
(that URN is no node). Post-fix: `mission_step_contract:documentation/accept`, `True`.

## 2. See the parity report agree

```bash
spec-kitty charter consistency-check --json | jq '{coherent, graph_kind_gaps}'
```

Pre-fix, with a ledger activating one step contract: a `graph_kind_gaps` entry naming it with the
"resynthesize" suggestion. Post-fix: no gap for a step contract whose owning mission type is active.

## 3. Run the gates

```bash
uv run pytest tests/charter/activation/test_step_contract_urn_identity.py -q
uv run pytest tests/architectural/test_drg_urn_identity_parity.py -q
uv run pytest tests/charter/activation/test_deny_identity_space.py tests/charter/test_activation_filtered_drg.py -q
make test-fast
```

## 4. Prove the drift gate is not vacuous

```bash
uv run pytest tests/architectural/test_drg_urn_identity_parity.py -q -k planted
```

The planted-divergence arm builds a synthetic node whose URN tail is a declared id for a
step contract (`mission_step_contract:documentation-accept`) and asserts the gate reports it.
