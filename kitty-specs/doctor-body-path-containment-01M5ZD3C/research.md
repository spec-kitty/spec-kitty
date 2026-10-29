# Research — doctor-body-path-containment-01M5ZD3C

Grounding evidence and the red-first reproduction: [research/phase0-grounding.md](research/phase0-grounding.md).

## D1 — Where the escape check lives

- **Decision**: a pure predicate `find_body_path_escapes(fragment, pack_root)` in `charter.offering.drg.org_pack_loader`, plus a registry-aware wrapper `find_org_body_path_escapes(repo_root, fragments)` in `charter.activation.drg_activation`. The doctor calls only the wrapper.
- **Rationale**: the fragment model and the containment primitive are both in `charter.offering.drg`. The pack-root join is already done by `load_org_drg` in `drg_activation`. Both doctor halves import from `drg_activation` today, so one call site serves both.
- **Alternatives considered**: (a) a check inside `_charter_pack_collect.py`. Rejected: the renderer may not import the collect layer, and a second copy would let the halves drift, which is the defect class the renderer's docstring records. (b) Refuse at `load_org_pack`. Rejected: it changes activation/runtime for every caller (C-002); it is a follow-up candidate.

## D2 — Which nodes

- **Decision**: `fragment.authored_nodes` only (operator Decision Moment).
- **Rationale**: an authored node's `body_path` is pack-root-relative by contract. A discovered node's `body_path` is relative to its own artifact file and owned by that kind's validator (pack skills: `pack_skills/validation.py`).
- **Alternatives considered**: all nodes. Rejected: a skill at `skills/sub/a.skill.yaml` with `body_path: ../b.md` is valid relative to its own folder and would be misreported.

## D3 — Output contract

- **Decision**: `org_drg.body_path_escapes` is always present, a list of `{pack, node, kind, body_path, reason}`; each escape is also a message on `org_drg.errors`. The human section prints a `body_path escapes:` verdict line (`none`, or a count plus bullets) after the pack list.
- **Rationale**: `errors` is the only channel the health verdict reads. The structured list follows the `dangling_endpoints` precedent (always present, so "ran and found none" differs from "never ran"). The early-return paths (pack missing, load error) leave it `[]`, with the cause already in `errors`.
- **Alternatives considered**: errors only. The operator chose the structured key.

## D4 — When the check runs

- **Decision**: right after `load_org_drg` succeeds, before the merge, independent of the merge outcome.
- **Rationale**: an escape is a property of the pack, not of the merged graph. A refused merge must not hide it ("more breakage must not read as fewer findings").

## D5 — Message wording

- **Decision**: `org pack '<pack>': node '<node>' (<kind>) body_path '<body_path>' escapes the pack root: <reason>`. `reason` is the primitive's own message.

## Adversarial evidence

No dependency decision, so the DIRECTIVE_051 adversarial pass does not apply at plan time. The pre-PR adversarial squad runs at closeout.
