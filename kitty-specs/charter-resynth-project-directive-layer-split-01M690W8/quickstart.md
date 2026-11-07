# Quickstart: verify the project-directive layer split by hand

Proves [#6768](https://github.com/spec-kitty/spec-kitty) before and after the change, on a
throwaway project.

## 1. Build a "synthesized once" project with an authored project directive

Use the fixture shape from
`tests/charter/synthesizer/test_resynthesis_after_activation_6510.py` (it drives
`charter generate --from-interview` and one `charter synthesize`), then:

```bash
# project root = the fixture project
cat > .kittify/charter-packs/directive/007-local-guardrail.directive.yaml <<'YAML'
id: PROJECT_007
schema_version: '1.0'
title: Local Guardrail
intent: Guard local risk.
enforcement: advisory
YAML

spec-kitty charter activate directive 007-local-guardrail --no-compile
mkdir -p .kittify/charter/generated/tactics
cat > .kittify/charter/generated/tactics/how-we-apply-project-007.tactic.yaml <<'YAML'
id: how-we-apply-project-007
schema_version: '1.0'
name: how-we-apply-project-007
purpose: Apply the local guardrail.
steps:
  - title: Apply
    description: Apply it.
YAML
```

`charter activate` records the directive as `adapter_id: project-direct-write`, which is
deliberately **not** synthesis ownership — that is the state the defect needs.

## 2. Before the fix — the refusal

```bash
spec-kitty charter resynthesize --topic directive:PROJECT_007 --json
```

Expected on `main` before the change (exit 1):

```json
{"error": "Project DRG validation failed (1 error(s)): Additive-only violation
 (FR-020 / EC-6): URN 'directive:PROJECT_007' is already present in the
 synthesis input graph. … colliding_urn='directive:PROJECT_007'", "result": "error"}
```

## 3. After the fix — the regeneration

Same command, exit 0:

```json
{"result": "success", "topic": "directive:PROJECT_007", "matched_form": "kind_slug",
 "regenerated": ["directive:local-guardrail"]}
```

Then confirm the positive control still refuses — a target whose URN is genuinely a shipped
built-in node must still raise the same error. The regression test does that at the emitter
(`emit_project_layer`) level with the real shipped graph; by hand, the cheapest check is:

```bash
python - <<'PY'
from pathlib import Path
from charter.offering.drg.loader import load_built_in_graph
from charter.activation.synthesizer.project_drg import emit_project_layer
from charter.activation.synthesizer.request import SynthesisTarget

built_in = load_built_in_graph()
urn = built_in.nodes[0].urn
kind, _, ident = urn.partition(":")
target = SynthesisTarget(kind=kind, slug=ident, title="collision", artifact_id=ident,
                         source_section="manual")
try:
    emit_project_layer([target], "4.0.0", built_in, Path.cwd())
except Exception as exc:  # ProjectDRGValidationError
    print("still refuses:", exc)
else:
    raise SystemExit("FAIL: built-in shadowing was allowed")
PY
```

## 4. Confirm the reference universe still resolves

```bash
spec-kitty charter resynthesize --topic tactic:how-we-apply-project-007 --json
```

Exit 0, and `.kittify/charter-packs/graph.yaml` keeps the
`directive:PROJECT_007 --suggests--> tactic:how-we-apply-project-007` edge.

## 5. The automated proof

```bash
uv run pytest tests/charter/synthesizer/test_project_directive_layer_split_6768.py -q
uv run pytest tests/charter/synthesizer tests/charter -q
```
