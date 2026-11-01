---
title: 'Context: Dossier'
description: 'Glossary context for the dossier: the local artifact inventory, integrity validation, and drift-detection system covering mission-lifecycle artifacts.'
doc_status: active
updated: '2026-03-10'
related:
- context/technology-foundations
---
## Context: Dossier

Terms describing the local artifact inventory, integrity validation, and drift detection system.

### Artifact

| | |
|---|---|
| **Definition** | Any file produced or consumed during the mission lifecycle (e.g., `spec.md`, `plan.md`, `tasks.md`, prompt files). Artifacts are identified by content hash and classified by role. |
| **Context** | Dossier |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [ArtifactRef](#artifactref), [Artifact Class](#artifact-class), [Artifact Key](#artifact-key) |

---

### Mission Dossier

| | |
|---|---|
| **Definition** | Local artifact inventory and integrity validation system. It answers three questions: (1) "What artifacts exist for this mission?" — scans a feature directory, catalogs every file as an ArtifactRef with a content hash. (2) "Are all required artifacts present?" — checks against a manifest of expected artifacts per mission type/step. (3) "Have artifacts changed since I last looked?" — compares a deterministic parity hash against a cached baseline. |
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
| **Definition** | Classification of an artifact's role in the mission lifecycle. Six values: `input`, `workflow`, `output`, `evidence`, `policy`, `runtime`. |
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
| **Definition** | Checksum computed from all artifact content hashes in a dossier, sorted to guarantee the same result regardless of scan order. If any artifact's content changes, the parity hash changes too. Used to answer "has anything in this dossier changed?" |
| **Context** | Dossier |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Content Hash](#content-hash), [Parity Baseline](#parity-baseline), [Parity Drift](#parity-drift) |

---

### Parity Baseline

| | |
|---|---|
| **Definition** | A saved parity hash representing the last accepted state of a dossier. Scoped to a specific project, feature, branch, and mission so that baselines from different contexts can never be confused with each other. Drift is detected by comparing the current parity hash against this baseline. |
| **Context** | Dossier |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Parity Hash](#parity-hash), [Baseline Key](#baseline-key), [Parity Drift](#parity-drift) |

---

### Baseline Key

| | |
|---|---|
| **Definition** | The combination of identifiers (project, node, feature, branch, mission, manifest version) that uniquely scopes a parity baseline. Ensures that a baseline captured in one context is never accidentally compared against artifacts from a different context. |
| **Context** | Dossier |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Parity Baseline](#parity-baseline) |

---

### Parity Drift

| | |
|---|---|
| **Definition** | When the current parity hash no longer matches the saved baseline, something in the dossier has changed since it was last accepted. This mismatch is called parity drift. It tells the curator "artifacts have been modified — review what changed." |
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
| **Definition** | The process of walking through a feature directory, identifying each artifact file, computing its content hash, and recording it in the dossier. Also checks for any required artifacts that are missing. |
| **Context** | Dossier |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [ArtifactRef](#artifactref), [Content Hash](#content-hash), [Missing Detection](#missing-detection) |

---

### Missing Detection

| | |
|---|---|
| **Definition** | When artifact indexing finds that a required artifact is absent or unreadable, it records the gap with a reason code explaining why: `not_found` (file doesn't exist), `unreadable` (file exists but can't be read), `invalid_format` (file exists but isn't valid), or `deleted_after_scan` (file disappeared during indexing). |
| **Context** | Dossier |
| **Status** | candidate |
| **Applicable to** | `1.x`, `2.x` |
| **Related terms** | [Artifact Indexing](#artifact-indexing), [Expected Artifact Manifest](#expected-artifact-manifest) |
