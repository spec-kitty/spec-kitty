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
| Entry's sidecar readable, `adapter_id == project-direct-write` | not owned by that entry — see the two registration rows below |
| Sidecar unreadable, and `kind`'s node identity is its slug (every kind but `directive`) | `<kind>:<slug>` from the entry — the manifest is the creation record, and this is the fail-closed direction |
| Sidecar readable and `project-direct-write`, but the created-artifacts record lists the id (slug-keyed kinds) | owned — project registration replaces the entry *and* its sidecar for a slug-keyed kind, and that record is the durable memory of creation |
| Sidecar readable and `project-direct-write`, the record unreadable (slug-keyed kinds) | owned — the registration cannot be told from synthesis output, so fail closed |
| Sidecar unreadable, `kind == directive` | the created-artifacts record; it does not track directives, so the coded error |

A synthesized artifact re-registered as `project-direct-write` stays owned. Two shapes exist
because project registration keys the manifest by `(kind, slug)`: for a directive the derived
slug differs from the synthesized entry's, so both survive and the sidecar decides; for a
slug-keyed kind the registration *replaces* the single entry and its sidecar, so the
created-artifacts record decides.

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

Two cells are stricter than the lenient parser this replaced, and both count as "damaged": a
sidecar whose `artifact_urn` kind does not match the manifest entry now yields `None` instead of
a garbage id, and a `provenance_path` outside `.kittify/charter/provenance/` (or resolving
outside the repository) is refused instead of read.

## Invariants a change must not break

1. `synthesized_urns` is defined once, in the record module; no other module resolves ownership
   from the manifest.
2. The sidecar shape has one parser: the validated model loader, and one ownership reader
   (`synthesized_urns` / `sidecar_artifact_urn`). No module parses a sidecar with raw YAML, and
   the modules that read one at all are a pinned census in
   `tests/architectural/test_single_synthesis_ownership_reader.py` — the pre-existing best-effort
   probes (edge backing, registration pruning, the registered-artifact split, resynthesis inputs,
   status display) are enumerated there and are the #6767 follow-up, not this convergence.
3. `SYNTHESIS_MEMBERSHIP_UNREADABLE` is constructed in one place.
4. The record files' on-disk shape is unchanged by this contract.
