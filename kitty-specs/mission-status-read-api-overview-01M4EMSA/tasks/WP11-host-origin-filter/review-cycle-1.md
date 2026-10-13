---
affected_files: []
cycle_number: 1
mission_slug: mission-status-read-api-overview-01M4EMSA
reproduction_command:
reviewed_at: '2026-10-12T17:36:47Z'
reviewer_agent: reviewer-renata
wp_id: WP11
---

# WP11 review cycle 1: REJECT (reviewer-renata), orchestrator dispositions

The full evidence is in wp11-review-verdict.md (orchestrator scratchpad). The tables match the spec, ANL-005 and research T007 exactly. 28 extra raw probes on the JVM and the native binary were refused correctly, the mutations went red, the service fails closed until its port is known, the architecture rules hold, and `check` and native are green.

The orchestrator settled F1 and F3 from the spec text. FR-009 says the guard covers error paths, so option (a) is the single remedy that meets the spec. Option (b) would amend the spec and is not taken.

| id | severity | where | problem | remedy |
|---|---|---|---|---|
| F1 | high | config/HostOriginRegistration.java (dispatch types REQUEST only); HostOriginFilter (OncePerRequestFilter skips ERROR dispatch) | A container `sendError` reaches Boot's `/error` through an ERROR dispatch the filter never sees. `TRACE /api/v1/project` with `Host: evil.example` answers 405 with Boot error JSON that echoes the path. This happens on the JVM and on native. | Register the filter for REQUEST and ERROR dispatch, and override `shouldNotFilterErrorDispatch()` to return false. A foreign Host on an ERROR dispatch then gets the 403 Problem. Add real-socket rows: TRACE with a foreign Host gives 403; a 404 path with a foreign Host gives 403; an accepted-Host error still gives its normal Problem. Extend the RegistrationTest pin to REQUEST+ERROR. Make sure a request that already passed on REQUEST is not double-refused or double-counted on its ERROR redispatch: the accepted-Host 404/405/500 must keep their Problem bodies. Check native. Add revert rows for ERROR dispatch removed and for `shouldNotFilterErrorDispatch` restored. |
| F2 | medium | hostorigin/HostOriginRig.java:21 (TARGETS) | T061 step 5 and plan row 4b need foreign-Host rows for the springdoc paths. | Add `/v3/api-docs`, `/v3/api-docs.yaml`, `/swagger-ui.html` and `/swagger-ui/index.html` with a foreign Host, expecting a literal 403 with reachesFilter true. |
| F3 | low | spec FR-009 / DD-111 | `OPTIONS *` with a foreign Host answers 200 (empty body, `Allow` header) and `CONNECT` answers 501 (container page). The container answers both before any filter, as with the AC-9b container 400 rows. | After F1, observe both again. If the ERROR dispatch now refuses either, pin that. Whatever the container still answers by itself, pin as a literal container-owned row (reachesFilter false, no Mission read, no echo), the same treatment as rows 8 and E1–E3. Report which. The orchestrator records them as container-answered. |
| F4 | low | hostorigin tests | The "first Origin only" revert is caught only by a mock test. | Add a raw-socket row to OriginTableTest that sends a good Origin then a bad Origin (and the reverse), expecting 403. |
| F5 | low | OriginTableTest.theStreamRouteOpensForTheAcceptedFormsOnly | The stream control only uses the `127.0.0.1` Host. | Parameterise it over both accepted Host forms. |

F6 (the precedence pin replacing the lowest-precedence revert) is accepted and recorded in DD-111.

Run all mutations in a scratch worktree.
