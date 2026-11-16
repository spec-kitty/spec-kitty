---
title: 'Context: Dossier'
description: 'Glossary context for the dossier: the local artifact inventory, integrity validation, and drift-detection system covering mission-lifecycle artifacts.'
doc_status: active
kind: Explanation
updated: '2026-11-13T00:00:00Z'
audience:
- profile: internal/lead-developer
  guidance_text: Read this to know what the dossier indexes, how its hashes are built, and which drift check runs today.
- profile: internal/ai-collaboration-agent
  guidance_text: Read this before reporting dossier drift or a missing artifact, so you use the reason codes the code records.
related:
- context/technology-foundations
---
## Context: Dossier

Terms describing the local artifact inventory, integrity validation, and drift detection system.

### Artifact

| | |
|---|---|
| **Definition** | Any file produced or consumed during the mission lifecycle (e.g., `spec.md`, `plan.md`, `tasks.md`, prompt files). Artifacts are identified by an artifact key, fingerprinted by content hash, and classified by role. |
| **Context** | Dossier |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [ArtifactRef](#artifactref), [Artifact Class](#artifact-class), [Artifact Key](#artifact-key) |

---

### Mission Dossier

| | |
|---|---|
| **Definition** | Local artifact inventory and integrity validation system. It answers three questions: (1) "What artifacts exist for this mission?" — scans a Mission directory, catalogs every file as an ArtifactRef with a content hash. (2) "Are all required artifacts present?" — checks against a manifest of expected artifacts per mission type/step. (3) "Have artifacts changed since I last looked?" — recomputes the snapshot hash and compares it with the recorded snapshot (`<Mission directory>/.kittify/dossiers/<mission_slug>/snapshot-latest.json`); `spec-kitty reconcile --mission <slug>` runs that check and names each differing artifact. Code: `src/specify_cli/dossier/`. |
| **Context** | Dossier |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Artifact](#artifact), [Dossier Snapshot](#dossier-snapshot), [Parity Hash](#parity-hash) |

---

### ArtifactRef

| | |
|---|---|
| **Definition** | Immutable reference to a single indexed artifact carrying identity (artifact key), location (path), content hash (SHA256), and provenance metadata. |
| **Context** | Dossier |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Artifact](#artifact), [Artifact Key](#artifact-key), [Content Hash](#content-hash) |

---

### Artifact Class

| | |
|---|---|
| **Definition** | Classification of an artifact's role in the mission lifecycle. Six values in the expected-artifact manifest (`ArtifactClassEnum`): `input`, `workflow`, `output`, `evidence`, `policy`, `runtime`. An indexed `ArtifactRef` also accepts a seventh value, `other`. |
| **Context** | Dossier |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |

---

### Artifact Key

| | |
|---|---|
| **Definition** | Stable, unique identifier for an artifact within a dossier, following the pattern `{class}.{type}.{qualifier}` (e.g., `input.spec.main`). |
| **Context** | Dossier |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Artifact Class](#artifact-class) |

---

### Content Hash

| | |
|---|---|
| **Definition** | A checksum of the artifact's contents (using SHA256) that locks in what the artifact contains. Any changes to the artifact will cause the calculated hash to change as well, making it useful for detecting modifications. |
| **Context** | Dossier |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Parity Hash](#parity-hash), [SHA256](./technology-foundations.md#sha256) |

---

### Expected Artifact Manifest

| | |
|---|---|
| **Definition** | Registry of required and optional artifacts per mission type and step, defining the completeness contract for a dossier. |
| **Context** | Dossier |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Completeness Status](#completeness-status), [Missing Detection](#missing-detection) |

---

### Completeness Status

| | |
|---|---|
| **Definition** | Whether all required artifacts in the manifest are present: `complete`, `incomplete`, or `unknown` (no manifest). |
| **Context** | Dossier |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Expected Artifact Manifest](#expected-artifact-manifest) |

---

### Parity Hash

| | |
|---|---|
| **Definition** | Checksum computed from the `(relative path, content hash)` pairs of every present artifact in a dossier, sorted by path to guarantee the same result regardless of scan order, and written as `sha256:<64 hex>` (`compute_dossier_snapshot_hash`). If any artifact's content or path changes, the parity hash changes too. Used to answer "has anything in this dossier changed?" |
| **Context** | Dossier |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Content Hash](#content-hash), [Parity Baseline](#parity-baseline), [Parity Drift](#parity-drift) |

---

### Parity Baseline

| | |
|---|---|
| **Definition** | A saved parity hash representing the last accepted state of a dossier. Scoped to a specific project, Mission, target branch, and mission type so that baselines from different contexts can never be confused with each other. Drift is detected by comparing the current parity hash against this baseline. |
| **Note** | The only writer of a parity baseline (`parity-baseline.json`, from `dossier/drift_detector.py`, deleted in commit `e7f777652b`, issue #116) is gone, so nothing writes one today. Drift is now checked against the recorded dossier snapshot (see [Mission Dossier](#mission-dossier)). The path stays declared in `src/specify_cli/state/contract.py`. |
| **Context** | Dossier |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Parity Hash](#parity-hash), [Baseline Key](#baseline-key), [Parity Drift](#parity-drift) |

---

### Baseline Key

| | |
|---|---|
| **Definition** | The combination of identifiers (`project_uuid`, `node_id`, `mission_slug`, `target_branch`, `mission_type`, `manifest_version`) that uniquely scopes a parity baseline. Ensures that a baseline captured in one context is never accidentally compared against artifacts from a different context. |
| **Note** | No code in `src/` builds this key since the drift detector was deleted (commit `e7f777652b`, issue #116). |
| **Context** | Dossier |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Parity Baseline](#parity-baseline) |

---

### Parity Drift

| | |
|---|---|
| **Definition** | When the current parity hash no longer matches the saved baseline, something in the dossier has changed since it was last accepted. This mismatch is called parity drift. It tells the curator "artifacts have been modified — review what changed." |
| **Note** | Today `spec-kitty reconcile` reports drift as `DIVERGENCE`, naming each differing artifact. The `MissionDossierParityDriftDetected` event emitter (`emit_parity_drift_detected`) is defined but has no caller in `src/`. |
| **Context** | Dossier |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Parity Hash](#parity-hash), [Parity Baseline](#parity-baseline) |

---

### Dossier Snapshot

| | |
|---|---|
| **Definition** | A frozen picture of a dossier at a specific moment: which artifacts are present, how many are required vs optional, whether all required artifacts exist, and the parity hash at that time. Scanning the same unchanged content always produces the same snapshot. |
| **Context** | Dossier |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Mission Dossier](#mission-dossier), [Parity Hash](#parity-hash), [Completeness Status](#completeness-status) |

---

### Artifact Indexing

| | |
|---|---|
| **Definition** | The process of walking through a Mission directory, identifying each artifact file, computing its content hash, and recording it in the dossier. Also checks for any required artifacts that are missing. |
| **Context** | Dossier |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [ArtifactRef](#artifactref), [Content Hash](#content-hash), [Missing Detection](#missing-detection) |

---

### Missing Detection

| | |
|---|---|
| **Definition** | When artifact indexing finds that a required artifact is absent or unreadable, it records the gap with a reason code explaining why. The indexer sets `not_found` (file doesn't exist), `unreadable` (file exists but can't be read) or `invalid_utf8` (file is not valid UTF-8). The `ArtifactRef` model also documents `invalid_format` and `deleted_after_scan`, which no code path in `src/` sets. |
| **Context** | Dossier |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Artifact Indexing](#artifact-indexing), [Expected Artifact Manifest](#expected-artifact-manifest) |
