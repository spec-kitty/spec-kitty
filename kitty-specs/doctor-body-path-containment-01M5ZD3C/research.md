# Research — doctor-body-path-containment-01M5ZD3C

Grounding evidence and the red-first reproduction: [research/phase0-grounding.md](research/phase0-grounding.md).

## D1 — Where the escape check lives

- **Decision**: a pure predicate `find_body_path_escapes(fragment, pack_root)` in `charter.offering.drg.org_pack_loader`, plus a registry-aware wrapper `find_org_body_path_escapes(repo_root, fragments)` in `charter.activation.drg_activation`. The doctor calls only the wrapper.
- **Rationale**: the fragment model and the containment primitive are both in `charter.offering.drg`. The pack-root join is already done by `load_org_drg` in `drg_activation`. Both doctor halves import from `drg_activation` today, so one call site serves both.
- **Alternatives considered**: (a) a check inside `_charter_pack_collect.py`. Rejected: the renderer may not import the collect layer, and a second copy would let the halves drift, which is the defect class the renderer's docstring records. (b) Refuse at `load_org_pack`. Rejected: it changes activation/runtime for every caller (C-002); it is a follow-up candidate.

## D2 — Which nodes

- **Decision**: `fragment.authored_nodes` only (operator Decision Moment).
- **Rationale**: an authored node's `body_path` is pack-root-relative by contract. A discovered node's `body_path` is relative to its own artifact file and owned by that kind's validator (pack skills: `pack_skills/validation.py`).
- **Alternatives considered**: all nodes. Rejected: a discovered node's `body_path` is not pack-root-relative (a pack skill's is relative to its `.skill.yaml`), so judging it against the pack root would apply the wrong anchor; its kind's validator (`charter pack validate`) owns it. (Corrected at closeout: an earlier example here claimed `../b.md` from a nested skill is valid; pack-skill validation rejects any escape from the skill directory.)

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

## D6 — Asset sidecars (closeout, pre-merge squad MAJOR)

- **Decision**: the doctor also reports an org pack's asset sidecar whose `path` escapes its `assets/` root, by resolving every org-provenance asset through `AssetRepository.resolve_path` per pack and catching `AssetPathEscapeError`. It is reported as `org_drg.asset_path_escapes` (code `ORG_ASSET_PATH_ESCAPE`) plus messages on `errors`.
- **Rationale**: promise PR-CHARTER-SHARING-004 ("a shared asset that reaches outside its own pack folder is not accepted as sound") cites `AssetPathEscapeError`. Without this, the promise would read as bound while an escaping sidecar exits 0. Reusing the repository's own resolve keeps one authority for asset anchoring (org `assets/` dir) and containment.
- **Alternatives considered**: narrowing the promise (operator rejected); reusing `pack_validator._check_asset_path_containment` (private; it re-derives the anchor the repository already owns).

## D7 — Stable finding codes (closeout)

- **Decision**: each `body_path_escapes` entry carries `code: ORG_FRAGMENT_BODY_PATH_ESCAPE`, and each `asset_path_escapes` entry carries `code: ORG_ASSET_PATH_ESCAPE`.
- **Rationale**: `reason` is free text and can embed the host path; the keys have no consumers yet, so adding codes now is free. This aligns with the charter service's `PackFindingCode` style.

## Squad dispositions (pre-merge, 2026-10-27)

| Finding | Lens | Disposition |
|---|---|---|
| SHARING-004 over-claims vs asset sidecars (MAJOR) | correctness | accepted → FR-007 / D6 |
| NUL byte in one body_path aborts the whole check (MINOR) | correctness | accepted → per-node handling of resolve errors |
| Symlink loop reported as "escapes" (NIT) | correctness | accepted → message says "is not contained in the pack root" |
| "body_path escapes: none" reads as a whole-pack verdict (NIT) | correctness | accepted → human label names the fragment nodes |
| Pack root resolved twice / registry re-read (MINOR) | architecture | deferred_with_rationale → follow-up issue (typed root on the fragment); not folded to keep the approved, reviewed seam stable at closeout |
| Chain-authority gate detection hole (MINOR) | architecture | deferred_with_rationale → follow-up issue (gate change, own non-vacuity proof) |
| New activation reach behind baselined rows (MINOR) | architecture | deferred_with_rationale → recorded in PR as priced debt; resolved by the typed-root follow-up |
| `org_drg.body_path_escapes` undocumented, no code (MINOR) | architecture | accepted → D7 + docs/api/charter-commands.md |
| Docstring overclaims "the one containment authority" (MINOR) | architecture | accepted → docstring softened; D2 example corrected |
| `charter status` / `charter org validate` disagree with doctor (MINOR) | architecture | deferred_with_rationale → follow-up issue (C-002 scope) |
| spec-kitty-charter PackPolicy drift (MINOR) | architecture | deferred_with_rationale → follow-up issue in spec-kitty-charter |
| TYPE_CHECKING import bypasses `charter.drg` facade (NIT) | architecture | accepted |
| Half-parity pinned only indirectly (NIT) | architecture | deferred_with_rationale → covered by the typed-root follow-up |
| Pack-skill containment hand-roll (campsite) | architecture | deferred_with_rationale → follow-up issue |
