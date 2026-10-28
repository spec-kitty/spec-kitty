# Pre-merge adversarial squad: dispositions

Point-cut: pre-merge. Question: what in this change would mislead the people building the write-service client and service, leak a credential, or fail CI? Cast (profile-loaded, read-only, run in parallel): `architect-alphonso` (protocol coherence), `java-jenny` (implementability against the Java toolchain), `lexical-larry` (terminology and conventions). The WP03 reviewer's three non-blocking follow-ups are dispositioned here too. Every finding has exactly one disposition.

Evidence commits: the RED tests in `test: pin the pre-merge squad folds ...`, the fold in `fix: fold the pre-merge squad into the mission-write contract and client shapes`, the ADR fold in `docs: fold the pre-merge squad into ADR 2026-10-27-1 ...`.

## architect-alphonso

| Finding | Disposition | Evidence |
|---|---|---|
| HIGH: the parent ADR D-3 sends a command; this contract sends rows | changed: the strangler sends rows, and the command form with service-side `lane_head` stamping arrives at migration step 4; the parent's amendment now says so | ADR 2026-10-27-1 D-3; ADR 2026-10-22-1 Amendment 2026-10-27 |
| HIGH: endpoint file single-instance and delete race | accepted: an exclusive `service.lock` held for life, publication by rename, and deletion only while the file names the service's own `instance_id`; the launcher (#6676) owns start and stale recovery | ADR D-2 "One service per clone" |
| HIGH: torn tail and partial replay | accepted as provisional defaults: a partial overlap is `EVENT_ID_CONFLICT`, and a torn tail is refused until repaired (the repair rule belongs to #6193) | ADR open questions 1 and 2; `WriteRefusalCode` EVENT_ID_CONFLICT |
| MEDIUM: facts the port cannot supply (destination ref, owned checkout, missionId) | accepted: listed, with how the #6195 adapter derives `missionId` | ADR D-3 "What the port does not hold yet" |
| MEDIUM: `repositoryId` canonical string across languages | accepted: forward-slash real path, UTF-8, case as reported; the cross-language fixture lands with #6192 | ADR D-4; `repository_id` |
| MEDIUM: a refused batch cannot name its unit | changed: `Problem.instance` carries `#/units/<index>`, so `_shared` is unchanged (C-004) | `WriteRefusal` description; example `WriteRefusal.batch-unit.yaml` |
| MEDIUM: `fsyncs: 1` vs a fully replayed batch | accepted: `fsyncs` is 0 or 1, 0 exactly when every unit was replayed; `fsynced` means durable | `BatchDurabilityAck`, `DurabilityAck`; client check |
| MEDIUM: provisional items vs closed responses | accepted: every provisional element is settled before `1.0.0`, and an unknown code is strict (open question 10) | ADR open questions; module CHANGELOG |
| LOW: 64 units under 413 vs `maxItems` 400 | accepted: more than 64 units is `REQUEST_MALFORMED` | ADR open question 7; batch path description |
| LOW: endpoint vs handshake versions | accepted: the handshake wins | ADR D-2 fields |
| LOW: derived clauses unmarked | accepted | ADR D-2, D-4 markers |
| Concession: emitter half has no operation | accepted: stated as outside #6195 | ADR D-3 last bullet |

## java-jenny

| Finding | Disposition | Evidence |
|---|---|---|
| HIGH: codes as `oneOf` of `const` skip enum lint and pins | changed: the two real enums (`WriteSurface`, `HealthStatus`) are pinned; the codes and reasons stay constants because the lint admits only snake_case/PascalCase enums, and their governance is the parity test (contract, client vocabulary and inventory held equal, each CLI literal read from its file) | `contracts/tools/enum_pins.json`; ADR D-6 last bullet |
| HIGH: verbatim bytes vs re-serialization; replay comparison | accepted: rows are written in the CLI's canonical encoding (ADR 2026-10-22-1 D-7) and a retry is compared as JSON values | `TransitionUnit` description; ADR D-5 |
| MEDIUM: `wpId` vs rows, missionId vs rows, partial persistence | accepted: mismatches are `REQUEST_MALFORMED`; partial persistence is `EVENT_ID_CONFLICT`; the client refuses mixed `wp_id` rows | `TransitionUnit`; `transition_unit_from`; ADR D-3 |
| MEDIUM: batch refusal names no unit | changed (as for the architect finding) | `instance` pointer |
| MEDIUM: check precedence, non-integer header | accepted: the order is stated, and a non-integer header is `PROTOCOL_VERSION_UNSUPPORTED` | `openapi.yaml` description; parameter; ADR D-6 |
| MEDIUM: draining reuses `SERVICE_BUSY` | accepted: `SERVICE_DRAINING` (503, protocol-only, provisional), meaning "re-read the endpoint file" | `WriteRefusalCode`; `ServiceBusy` response; parity inventory |
| MEDIUM: 500/503 on handshake/health/shutdown; second shutdown | deferred_with_rationale: those operations write nothing and have no domain failure of their own; transport errors are not part of the vocabulary; the shutdown behaviour is open question 6 | ADR open question 6 |
| LOW: 401 without `WWW-Authenticate` | accepted | `TokenInvalid` response |
| LOW: `const` dropped by the generator | deferred_with_rationale: harmless; the implementer sets the constant | n/a |
| LOW: `/health` requires the protocol header | accepted: `/health` needs no header, so a launcher can probe before it negotiates | `paths/health.yaml`; test |

## lexical-larry

| Finding | Disposition | Evidence |
|---|---|---|
| HIGH: `primary_checkout_append` freezes a retired alias | accepted: the wire value is `checkout_append`; the client maps the CLI's `EventLogWriteTarget` | `WriteSurface`; `_SURFACE_BY_TARGET`; test |
| MEDIUM: one concept, three names (missionDirectory / write location) | accepted: "the Mission directory (the write location)" throughout; `checkout` for a coordination append is the coordination worktree | `RequestContext`; ADR D-3; client docstring |
| MEDIUM: provisional codes marked in prose only | accepted: the module CHANGELOG states that removing one later is a breaking change | module CHANGELOG `### Provisional` |
| LOW: bare "routes", "coordination surface" | accepted | `WriteRefusalCode` |
| LOW: "wrong lane" | accepted: "wrong status lane" | `WriteRefusalReason` |
| LOW: "is proven by #6194" | accepted: "will be proven" | ADR D-3 |
| LOW: no Pros and Cons section | accepted | ADR "Pros and Cons of the Options" |
| LOW: "flat-shell append" in a docstring | accepted | `transition_unit_from` docstring |

## WP03 reviewer follow-ups

| Finding | Disposition | Evidence |
|---|---|---|
| Provisional codes in prose only; `WRITE_LOCATION_UNVERIFIED` names no open decision | accepted: the code now names its open decision (ADR 2026-10-22-1 open question 2) | `WriteRefusalCode` |
| Path patterns accept `..`, backslashes, drive letters | accepted: the pattern refuses them and absolute paths | `RequestContext`; tests |
| Reason-code pairing not enforced | accepted: one `if type then code` branch per reason, held equal to the client's `REASON_CODE` | `WriteRefusal`; tests |
