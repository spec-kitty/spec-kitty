# Endpoint-validation model — #5833

Audience: software-engineer. Updated: 2026-10-09.

This is the supplied design's in-memory contract; no persisted product schema changes.

| Concept | Fields / relationship | Invariant |
|---|---|---|
| Loaded org fragment | existing nodes and edges; authored_nodes/authored_edges accessors | Loader owns provenance; discovered/projected subtypes do not add serialized fields; authored metadata/order/deduplication preserved |
| Schema-trusted identity projection | set of qualified string URNs from successful existing scan validations | Profiles use profile-id; ordinary artifacts id; legacy both-intent shortcut supplies no trust; no second schema scan |
| Canonical known-node universe | built-ins + trusted identities + explicit authored declarations | Explicit declarations require no backing file; graph-document declarations cannot cross-rescue |
| Local bare-id map | existing fragment ordering, filtered by explicit declaration or trusted URN; remaining trusted URNs deterministically added | Preserve last-assignment behavior; local bindings win over built-in ambiguity |
| Endpoint record | raw source/target token, canonical binding if successful, role/cause on refusal | Resolve both sides independently; relation value is neither needed nor fabricated |
| Generic endpoint graph view | read-only ordered edges with string source/target; node_urns() | Existing dangling_endpoints membership predicate is the sole authority; DRGGraph remains structurally compatible |
| Validation finding | existing severity/category/artifact_type/file/artifact_id/message | One error per missing side; source then target; role/cause in message, no new JSON fields |

Load state distinguishes absent optional fragment, successfully loaded fragment, and load failure with existing attributed findings. Failed load produces no derived canonical endpoint findings. Individual invalid artifacts only remove file-backed trust; explicit nodes can independently confer existence.

No new entity lifecycle or persistence transition is introduced. WP/subtask progress continues to use the existing append-only status event log, not Markdown checkboxes.
