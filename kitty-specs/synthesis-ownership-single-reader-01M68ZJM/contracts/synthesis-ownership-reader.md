# Contract: the synthesis ownership reader

Applies to every consumer that answers "which artifacts of this kind did synthesis create?":
`charter.activation.synthesizer.manifest` (the reader), `reach_only.reach_only_ids`, the
`charter.activation.api` seam, `synthesized_urns`' two callers (`synthesis_owned_directive_ids`
and the reach-only delivery path) and the `charter synthesize --json` envelope. Converged in
#6767 from three readers that disagreed on source, fallback and error (#6454, #6510).

## The record

One record, three files, all under `.kittify/charter/`:

| File | Role |
| --- | --- |
| `synthesis-manifest.yaml` | the commit record: one entry per artifact synthesis wrote |
| `provenance/<kind>-<slug>.yaml` | per-entry sidecar: `artifact_urn` (`<kind>:<id>`) and the writing `adapter_id` |
| `synthesized-artifacts.yaml` (+ legacy `synthesized-tactics.yaml`) | every id synthesis has ever created, per kind; the one fallback |

## The reader

```python
synthesized_urns(repo_root: Path, kind: str) -> frozenset[str]   # URNs, e.g. {"directive:PROJECT_001"}
synthesized_slugs(repo_root: Path, kind: str) -> frozenset[str]  # id segments
```

| Condition | Answer |
| --- | --- |
| Manifest absent (not even a dangling symlink) | `frozenset()` — nothing was synthesized; no other file is read |
| Manifest unreadable or schema-invalid | the created-artifacts record's ids of `kind`, or the coded error |
| Entry's sidecar readable, `adapter_id != project-direct-write` | the sidecar's `artifact_urn` |
| Entry's sidecar readable, `adapter_id == project-direct-write` | not owned by that entry (a registration, not synthesis) |
| Sidecar unreadable, and `kind`'s node identity is its slug (every kind but `directive`) | `<kind>:<slug>` from the entry — the manifest is the creation record, and this is the fail-closed direction |
| Sidecar unreadable, `kind == directive` | the created-artifacts record; it does not track directives, so the coded error |

A URN is owned when **at least one** entry recording it is synthesis-written: a synthesized
artifact re-registered as `project-direct-write` stays owned.

## The one error

```
SynthesisMembershipUnreadableError  (code SYNTHESIS_MEMBERSHIP_UNREADABLE)
```

- Bases: `SynthesisError` (so existing synthesis catch sites and their remedy panels match) and
  `KittyInternalConsistencyError` (so `charter context` renders code + body).
- Attributes: `code`, `body` (operator-facing: what could not be read, which file, why, the
  remedy), `record_path`, `offending_artifact`, `reason`, `kind`. `str()` is `body`.
- Never an empty set: an empty ownership set would re-root every synthesized artifact and deliver
  the doctrine of an inactive directive.
- `charter context` exits 1 printing the code and the body. `charter synthesize` renders the body
  in its error panel.

## The display path

`_artifact_id_from_sidecar` wraps `sidecar_artifact_urn(repo_root, entry, owned_only=False)` and
catches the coded error → `None`. The `charter synthesize --json` envelope keeps its four-field
entry shape (`path`, `kind`, `slug`, `artifact_id`) and never raises; `artifact_id` is populated
for directive entries only, including `project-direct-write` registrations (the envelope reports
what the manifest committed, not the ownership verdict).

## Invariants a change must not break

1. `synthesized_urns` is defined once, in the record module; no other module resolves ownership
   from the manifest.
2. `artifact_urn` is parsed by one function (`sidecar_artifact_urn`); no second YAML parse.
3. `SYNTHESIS_MEMBERSHIP_UNREADABLE` is constructed in one place.
4. The record files' on-disk shape is unchanged by this contract.
