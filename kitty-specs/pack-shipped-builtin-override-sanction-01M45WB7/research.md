# Research: Pack-shipped built-in override sanction

The full evidence is in [research/code-grounding.md](research/code-grounding.md). It comes from the grounding squad, run before specify, and the post-specify adversarial squad, with these profiles: architect-alphonso, doctrine-daphne, researcher-robbie, reviewer-renata and debugger-debbie.

## D1. Sanction delivery: read in place from the pack (option a)
- **Decision:** `doctor doctrine` reads the pack's own sanction in place and unions it with the consumer allowlist.
- **Rationale:** No copy exists, so there is nothing to drift. Scoping per pack is possible because provenance is `org:<registry name>`, stamped by the loader (`org_pack_loader.py:562`). #2594 can absorb it.
- **Alternatives:**
  - (b) Fetch installs the file into the consumer repo. Rejected: the copy drifts on the next promotion, scoping is lost, it mutates consumer governance, it never runs for local-path packs, and it has no lifecycle (#5243).
  - (c) A per-node `replaces:` marker. Rejected: the marker is absent at promotion time, and it would widen a strict node schema.

## D2. Placement: a pack-root `replaceable-builtins.yaml`, not an `org-charter.yaml` key
- **Decision:** a file at the pack root with the same grammar as the consumer file.
- **Rationale:** `OrgCharterPolicy` uses `extra="forbid"` (`org_charter.py:133`), so a new key breaks every CLI that has already shipped. `validate_pack` has no root-file allowlist (`pack_validator.py:373-519`). The assembler rebuilds `org-charter.yaml` from 4 keys only (#5770). The sanction logic must live in `charter.offering`, which cannot import `OrgCharterPolicy`.
- **Alternatives:** an org-charter key gated by schema version. This helps only future CLIs. Follow-up: tolerate unknown keys when the schema version is newer, as groundwork for #2594.

## D3. Scope by contributing pack; adjudicate the surviving node only
- **Decision:** a pack entry sanctions an override only when the surviving node's provenance is `org:<that pack>`.
- **Rationale:** without this, one pack could waive another pack's override. Precedence (last pack wins) stays unchanged (C-005).
- **Out of scope:** edges from a losing pack, and edge-form augmentation. Tracked in #5769.

## D4. Pack roots come from the loaded fragments
- **Decision:** build the roots as `{frag.pack_name: Path(frag.source_ref)}`.
- **Rationale:** a second registry resolution can diverge (a lenient load returns an empty registry). Taking the roots from the fragments means the sanction root equals the contributing root by construction.

## D5. Consumer revocation, per URN or per pack
- **Decision:** add `revoked_pack_sanctions: [{urn} | {pack}]` to the consumer file.
- **Rationale:** delegation must stay revocable. Revoking a whole pack catches newly self-sanctioned overrides that arrive with a refresh. Older CLIs ignore the key.

## D6. Isolation, containment and eager reads
- **Decision:** read every pack's file eagerly. A failure voids only that pack's sanctions and is reported. Reads are contained via `resolve_relative_path_within_root` and require a regular file.
- **Rationale:** NFR-004 of `doctrine-governance-fidelity-01KW42KY` requires fail-closed behaviour. #5760 shows the failure mode of silently dropping a sanction. Containment prevents a symlink escape from echoing outside content.

## D7. The legacy-template hint prints entries, not a copy command
- **Decision:** for an unsanctioned override, the hint prints (1) the pack-author remedy, which is to move the file to the pack root, and (2) the exact `{urn, reason}` entry to append. Output is escaped.
- **Rationale:** a whole-file `cp` would overwrite consumer entries and revocations, bypass scoping and drift again. This is the hint the brief's rc6 fallback asked for, in a safer form. It is transitional and is removed with #2594.

## D8. Integrity
- **Decision:** the sanction file is not added to the pack-manifest constituents.
- **Rationale:** the `Constituent` model refuses non-kind entries (C-001). Git and https fetches already hash the whole tree (`snapshot.py:572-596`), and local-path packs carry no integrity check.

## Supply chain
No dependency changes, so N/A.
