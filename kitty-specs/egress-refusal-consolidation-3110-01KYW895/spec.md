# Mission Specification: One Wrapper, One Shape — Project Egress Refusal Consolidation

**Mission Branch**: `pr/egress-refusal-consolidation-3110`
**Created**: 2026-07-31
**Revised**: 2026-07-31 — post-specify adversarial squad remediation, **round 1** (four opus lenses; 2 CRITICAL, 3 BLOCKER, 17 HIGH, ~20 MEDIUM/LOW, all adjudicated in `SQUAD-FINDINGS.md` §1/§1.5)
**Revised**: 2026-07-31 — **round 2** remediation (`SQUAD-FINDINGS.md` §1-R2: reviewer-renata N-1…N-11, debugger-debbie DB-1…DB-5, both ACCEPT-WITH-CHANGES, no BLOCKER surviving). Round 2 also **applies the operator's Q2 decision** (per-caller fragment in a shared template) and **cuts the round-1 over-correction**: FR-007 folded, FR-025/SC-017 retired, NFR-001 folded into NFR-003, SC-013's SaaS half deleted, Q8 closed.
**Revised**: 2026-07-31 — **round 3 closing fixes**, operator-authorised after the escalation gate tripped (`SQUAD-FINDINGS.md` §1-R3 + ESCALATION GATE). Closes the two surviving HIGHs (SC-014's mandated test could not reach the branch it tests; SC-004 had no clause that reds), folds the confirmed MEDIUMs (SC-013's two per-class **match** assertions with the non-match proposal **withdrawn**; SC-002's must-not-veto half; the corrected `store.py` anchors), and takes the duplication cuts both lenses agreed on. **These fixes were not re-reviewed.**
**Status**: Draft
**Input**: Bundle B — `#3110` (duplicated project-egress refusal wrapper), `#3111` (`decision widen` answers consent for the wrong project), and the residual open question from `#3109` (keep-or-delete `register_saas_client_factory`).

---

## How to use this document

**Implementers work from three blocks, and only those three: *Edge Cases*, *Success Criteria*, and
the *Requirement → Success Criterion coverage* table.** They are contiguous and self-contained:
every criterion carries its own anti-vacuity clause, its measurement, and its `[standing]` /
`[one-off]` tag, and the coverage table says which requirement each one discharges. An implementer
working from those three blocks alone builds the right thing.

**The Requirements tables (functional, non-functional, constraints) and *Falsifiers and
preconditions* are the justification record, not the implementation surface.** They exist so a
reviewer can check *why* each criterion is shaped as it is, and so a successor does not re-litigate
a settled decision on a ground the squad already measured false. Their cells carry history and
corrections rather than instructions. **Working from the Requirements table instead of the criteria
is the predicted failure mode of a document this long** (reviewer-renata, round 3: *"implementable,
but only by accident of structure, and the spec should say so"*), and this note is the spec saying so.

---

## How to read the identifiers in this document

Three independent ID spaces meet in this spec. They are always qualified:

| Form used here | Means |
|---|---|
| **Decision D-1 … D-6** | An *orchestrator* decision. D-1 lives in `ORCHESTRATOR-NOTES.md`; D-2…D-6 in `SQUAD-FINDINGS.md` §1.5. Each is binding on the plan and each carries a falsifier below. |
| **finding P-n / R-n / D-n / A-n** *(always prefixed with the lens)* | An adversarial-squad finding — paula-patterns, reviewer-renata, debugger-debbie, architect-alphonso respectively. Cited as e.g. "debugger finding D-5". |
| **F-A*/F-B*/F-ENV*, C-1…C-4** | Measured evidence and orchestrator self-corrections in `ORCHESTRATOR-NOTES.md`. |

Constraint IDs in this spec are `C-001…C-011` and are *not* the orchestrator's `C-1…C-4` corrections.

**Retired identifiers (round 2).** IDs are not renumbered, so the gaps below are deliberate and a
successor should not read them as missing rows:

| Retired | Where it went | Why |
|---|---|---|
| **FR-025** | Folded into **SC-004**, and in round 3 into SC-004's **binding-identity** clause | It was a vacuously-satisfiable conditional ("*any test that* patches…"); write no such test and it passed while the hazard stood (reviewer finding N-6, debugger finding P-2). **The rot-mode-5 hazard it was written for is stated once, at SC-004 clause 3** — not restated here |
| **SC-017** | Folded into **SC-004** | Same defect, same fix |
| **NFR-001** | Folded into **NFR-003** | The same integer with the opposite inequality, both mapping to SC-007 (round-2 cut list #4) |
| **SC-013's round-1 SaaS half** *(the `mod.SaasClient(...)` **match** assertion)* | Deleted in round 2; **not** restored | It required the SaaS guard to match `mod.SaasClient(...)`, the exact shape FR-016 requires it to *exclude* (reviewer finding N-3 / debugger finding P-1, converged). Reasoning stated once, at SC-013 |
| **The proposed `mod.SaasClient(...)` non-match pin** *(round-2 successor to the row above)* | **Withdrawn entirely in round 3 — it must not survive anywhere in this document** | Measured: the SaaS predicate is already the **stricter** of the two, so unifying can only *loosen* it — the guard would see **more** constructions, a coverage **gain**. A non-match pin would red on a coverage improvement and **collide with FU-8**, which exists precisely because `mod.SaasClient.from_env(x)` is unguarded and closing it means widening a predicate. SC-013's SaaS half is instead a **match** assertion on the correct analogue, `SaasClient(project_root=…)` (debugger round 3, orchestrator ruling overturned on measurement) |

---

## Context this specification is built on

Every factual claim below is measured, at `upstream/main` = `bb2020fea`, and recorded with
`file:line` in `ORCHESTRATOR-NOTES.md` (findings `F-ENV-*`, `F-A*`, `F-B*`, decision `D-1`) or in
`SQUAD-FINDINGS.md` (the four lenses' independent measurements). This spec does not re-derive them.
The three items are bundled because they meet at one surface: the seam between a transport and the
single project-consent chain.

Three framings are corrected up front, because the issue text is wrong about the first two and a
successor reading only the issues will design for the wrong problem. The third was established by
the squad and supersedes an earlier framing of the orchestrator's own.

1. **What is duplicated is the wrapper, not the chain.** Both packages already reach one
   resolver (`invocation.adapters.resolve_egress_consent`). Exactly **one runtime string**
   differs between `saas_client/egress_consent.py` and `tracker/egress_consent.py`; the other
   five diff hunks are comments and docstrings (F-A1). The consolidation is a presentation-layer
   change, and it must not disturb the layering that made the single chain possible.

2. **`#3111` is consent laundering, not unconsented egress.** The gate runs before the URL is
   used, so a non-consenting checkout transmits nothing. The failure is that standing in
   consenting project A and widening a decision owned by project B sends **B's identifier to
   A's team, under A's token**, and every gate answers truthfully about the wrong project
   (F-B2). In this product a `mission_slug` is a client engagement name, so the identifier
   *is* the confidential content — there is no "it's only metadata" defence available here.

3. **The invariant is about the argument's *provenance*, not its *type*.** Consent must be keyed
   on something derived from the record being sent, never from ambient context. Uuid-typing the
   seam would not make the substitutions inexpressible, only one call longer —
   `resolve(project_uuid_of(locate_project_root()))` is the same bug respelled. Conversely some
   path-keyed sites are already sound, because they derive the path *from the data*
   (`bind_mission_origin`'s `_resolve_repo_root(feature_dir)`). A type cannot express provenance;
   a constructor that refuses to build the sender's input without a data-derived consent answer
   can — which is what `ConsentedBatch` does (`delivery/consent_gate.py:1-20`). This replaces the
   orchestrator's earlier "the path-typed seam is the structural defect" framing (paula finding
   P-7, conceded). It is why Q3 is optional and why FR-022's ADR must name provenance explicitly.

**A fourth fact, not a framing but a boundary condition on everything below:** ownership of a
decision is positional — encoded by which directory the record sits in — and there is **no**
`decision_id`→project mapping locally or remotely (C-009 / F-B1). Every requirement here is
shaped by that, and any design that assumes such a mapping can be queried is invalid.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An operator cannot leak one client's engagement to another client's team (Priority: P1)

An operator stands in the checkout for client A (a consenting project) and runs
`spec-kitty agent decision widen <id> --invited 12,13`. The decision named by `<id>` belongs to
client B. Today the command resolves the repository root from the operator's location, asks A's
consent, gets a truthful "yes", and transmits B's identifier in the request line to **A's**
Teamspace under **A's** token. B never consented to that, and A's team learns an identifier from
an engagement that is not theirs.

The operator's outcome should be: the command establishes that the acting checkout owns the
decision before it touches the network, and either acts under that project's consent and
credentials, or refuses with a message naming what could not be established. Nothing crosses the
wire on the mismatch path.

**Why this priority**: This is the only item in the bundle that is a live confidentiality defect
rather than a maintainability one. It is reachable today with no server change: `decision_id` has
no format validation anywhere on the path, and the client interpolates whatever the operator types
directly into the request line (F-B2). Server acceptance controls the *effect*; the client already
controls the *disclosure*.

**Independent Test**: Fully testable on its own. Construct two project checkouts, **write both
checkouts' `.kittify/config.yaml` on disk** and pass both roots explicitly (C-010 — the candidate
test directories' autouse fixtures otherwise fabricate consent), put a decision ledger under B's
`kitty-specs/<slug>/decisions/index.json`, run the widen path from A's checkout with a stub
transport, and assert that no request was constructed **and** that B's `decision_id` appears in no
transmitted text. Delivers the confidentiality property with no part of Stories 2–4 implemented.

**Acceptance Scenarios**:

1. **Given** consenting project A and a decision owned by project B, **When** the operator runs
   widen from A's checkout naming B's decision, **Then** no HTTP request is constructed, B's
   `decision_id` reaches no request line, and the error names **the acting root, the missions
   searched within it, and that ownership was not established**.
   *(Weakened deliberately, converging paula finding P-3 and reviewer finding R-3: with no
   `decision_id`→project mapping and no cross-checkout enumeration, "found, owned elsewhere" is
   not a state this design can enter. The error must not claim to name project B.)*
2. **Given** a decision owned by the checkout the operator is standing in, **When** widen runs,
   **Then** it behaves exactly as today — one request, same endpoint, same payload. This is the
   **positive control** for scenario 1 and must live in the same test module, built from the same
   fixture (debugger finding D-1).
3. **Given** `SPECIFY_REPO_ROOT` pointing at project A while the cwd is inside project B,
   **When** widen names a decision owned by B, **Then** the same divergence is detected; the
   environment variable is not a way around the check (F-B4).
4. **Given** a `decision_id` that is not a well-formed identifier (for example a mission slug
   typed by mistake), **When** widen runs, **Then** the command refuses before any URL is built,
   and the rejected string does not appear in any transmitted request line. *(This is
   defence-in-depth only — see FR-005. It does not discharge scenario 1.)*
5. **Given** a checkout whose project has **not** consented, **When** widen runs with a decision
   that checkout does own, **Then** the existing refusal still fires and is unchanged in
   behaviour — this mission does not weaken the existing gate.
6. **Given** an operator-supplied `--mission-slug` naming a mission outside the acting root,
   **When** widen runs, **Then** the slug does not cause any ledger outside the acting root to be
   consulted (paula finding P-1 — the slug is the fourth divergence route).

---

### User Story 2 - Every refusal an operator sees says the same true thing (Priority: P2)

An operator hits the project-consent refusal from two different commands — one going through the
tracker transport, one through the SaaS client. Today they receive two texts that differ in
exactly one place: one says "mission and **decision** identifiers must not be transmitted", the
other "mission and **engagement** identifiers". Neither is wrong for its own caller; each is
incomplete for the other. There is one refusal policy, and the operator should meet one refusal
*voice* — one sentence shape, one set of verdict branches, one place to edit them — while
remaining accurate about what *this* transport was about to send.

**What "one voice" means here, fixed by the operator's Q2 decision (2026-07-31).** The shared
module owns the template, the four verdict branches, `UNDETERMINED_PROJECT_REFUSAL`, the `None`
guard and the import-failure degradation; **each transport passes its own identifier-set fragment as
an argument**, so both current `DENIED` strings survive **verbatim**. The full record — the rejected
alternatives, the four consequences, the falsifier — is stated **once**, in "Operator decision on
Q2" under *Falsifiers and preconditions*.

**Why this priority**: P2 rather than P1 because no operator is harmed today by the divergence —
each string is true where it is used. The value is that a single policy stops having two
independently-editable presentations, which is how the two copies drift apart into two policies.

**Independent Test**: Testable by driving **both real transports** into the same consent verdict
along their real refusal paths, capturing the operator-visible rendering from each, and comparing
the two *rendered* strings **outside their identifier-set fragments**. Comparing two imports of one
shared constant compares an object to itself and proves nothing (reviewer finding R-7). Requires
nothing from Stories 1, 3, or 4.

**Acceptance Scenarios**:

1. **Given** a non-consenting project, **When** the refusal is produced **via the tracker
   transport** and **via the SaaS client transport** — each driven end-to-end through its own
   refusal path, as `test_saas_client_consent_gate_3030.py:352` and
   `test_client_consent_gate_3030.py:376` already do — **Then** the two operator-visible texts are
   byte-identical **outside the identifier-set fragment**, and each transport's fragment names
   exactly its own enumerated set.
   *(Restated under Q2. Requiring byte-identity of the **whole** string, conjoined with AS2's "and
   implies no kind this transport cannot transmit", was an **empty solution set** — the two sets are
   asymmetric by 15 kinds, so no single string can name each transport's own set without naming
   kinds it cannot transmit (reviewer finding N-2). Byte-identity survives as the **mechanism** goal
   — one template — not as the goal for the rendered string.)*
2. **Given** that same refusal, **When** an operator reads it, **Then** it names every identifier
   kind the transport it came from can transmit (the enumerated sets in Key Entities), and implies
   no identifier kind that transport cannot transmit. Under Q2 these two clauses are no longer in
   tension: the fragment is per-caller, so both are satisfiable at once.
3. **Given** the "no checkout offered" case, **When** the refusal is produced from either
   transport, **Then** the text still contains the substring `could not be determined`. Note this
   substring occurs in **two** branches — `UNDETERMINED` and `UNANSWERABLE` (orchestrator
   correction C-1) — so the four existing assertions cannot distinguish them; NFR-004 carries the
   distinguishability requirement, not this scenario.
4. **Given** the hosted-sync package cannot be imported at all, **When** either transport asks for
   consent, **Then** the outcome is a refusal naming the import failure, never a permit, and the
   refusal is *reachable* — the transport module must remain importable in order to be asked
   (architect finding A-3; this is why Q1 option (a) is eliminated, Decision D-5).

---

### User Story 3 - A future contributor cannot add an unattributed sender without CI saying so (Priority: P2)

A maintainer adds a new construction site for either transport and forgets to tell it whose data
it carries. Each package carries its own AST guard that scans `src/`, reds, and names the file and
line. That protection must survive this mission at full strength for **both** packages.

**Framing correction — this story is not purely preservation.** Two lenses established
independently (reviewer finding R-9, architect findings A-1/A-2) that the CI routing property this
story assumes is **already false at `bb2020fea`, with no merge**:

- Zero of the four `SaasClient` construction sites live under `src/specify_cli/saas_client/**`.
  They are in `cli/commands/charter/interview.py:216`, `cli/commands/decision.py:558`,
  `missions/plan/plan_interview.py:150`, `missions/plan/specify_interview.py:150`.
- A PR confined to `cli/**` sets `cli=true` and nothing else; `fast-tests-core-misc`'s gate
  (`ci-quality.yml:1580`) lists ten groups and **`cli` is absent**; `fast-tests-cli` (`:1540`)
  never collects `tests/specify_cli/saas_client/`.
- ⇒ **Adding a fifth unattributed `SaasClient.from_env(...)` to `cli/commands/decision.py` today
  produces a PR on which the SaaS attribution guard does not run.** That file is exactly what this
  mission edits for `#3111`.
- The tracker guard has the mirror-image problem: it is `pytest.mark.fast` under `tests/sync/`,
  and `tracker/**` is not a member of the `sync` dorny filter, so a tracker-only diff already does
  not run it.

Per **Decision D-4** this splits: the narrow, provable half is in mission (FR-017); the general
re-keying is a follow-up issue (see "Follow-up issues").

**Why this priority**: This is the property that makes Story 2 safe to do at all. There are four
concrete mechanisms by which merging the two guards silently halves coverage (F-A3), and
debugger finding D-5 measured that a per-class count floor catches **only one** of them:
`scanned += 1` executes *before* the attribution test in both guards, so vocabulary widening
leaves the counts exactly unchanged, and unifying on the stricter predicate leaves the tracker
count sitting exactly at its floor while permanently blinding the guard to `mod.SaaSTrackerClient(...)`.

**Independent Test**: Testable without consolidating anything: strengthen the existing guards'
non-vacuity assertions to per-class floors, add the per-class *rejection* and *unused-shape*
assertions (FR-015/FR-016), and prove they bite by removing a known attribution in each package
independently.

**Acceptance Scenarios**:

1. **Given** the attribution guards, **When** **any one** construction site of one transport class
   is removed or renamed while the other transport's sites remain, **Then** that class's guard reds
   — it does not stay green on the surviving class's count (F-A3 Mechanism 1). Named floors:
   tracker 3, SaaS client 4, independently reproduced three times (F-A3, reviewer, architect).
2. **Given** a pull request whose diff is confined to `src/specify_cli/cli/**` — the shape of this
   mission's own `#3111` change — **When** CI selects jobs, **Then** the selected set includes a
   job that collects the SaaS-client attribution guard (FR-017, Decision D-4).
3. **Given** a newly added construction site that passes its root by a keyword the *other*
   transport accepts but this one does not, **When** the guard runs, **Then** it reds. Widening
   the accepted attribution vocabulary is the silent direction and must not happen
   (F-A3 Mechanism 2) — and it is invisible to every count, because the count is incremented first.
4. **Given** a construction shape no `src/` site uses today — `mod.SaaSTrackerClient(project_root=…)`,
   an attribute-receiver call the **tracker** guard's `getattr(func, "attr", None)` predicate accepts
   — **When** the tracker guard runs against a synthetic sample of that shape, **Then** it matches
   it. Nothing in the current corpus exercises this (all three tracker sites are bare `ast.Name`
   callees), so nothing protects it, and unifying on the SaaS guard's stricter predicate would blind
   the guard to it while leaving the count exactly at its floor (debugger finding D-5).
   *(Corrected in round 2: this scenario previously named the **SaaS** class on the shape
   `mod.SaasClient(...)`, whose predicate is defined to **exclude** it. The SaaS class has its own
   unused-but-matching analogue — bare `SaasClient(project_root=…)` — and SC-013 asserts it as a
   **match** in round 3. Both halves, their measurements, and why a **non-match** pin was withdrawn
   are stated once, at SC-013.)*

---

### User Story 4 - The empty SaaS-client seam reads as a decision, not an oversight (Priority: P3)

A maintainer opens `invocation/adapters.py`, finds `register_saas_client_factory` with no
production caller, and reads it as leftover. Its docstring actively supports that reading: it
says "Called once at sync package startup", which has been false since the phantom-reader deletion
that landed under mission `#3109` (its requirement 032 — the identifier is spelled out rather than
written as a bare `FR-###` token because the tasks gate harvests every such literal in this file as
*this* mission's requirement, and it is not ours). The maintainer
either deletes it, or wires a transport somewhere else that is not behind the propagator's
consent gate.

The outcome wanted: the seam states plainly that nothing registers a factory today and why, and
points at the canonical record of the hazard; and a test pins the seam's **export** so removing it
from the package surface is a deliberate act with a red build.

**Why this priority**: P3 because nothing is broken today. The read side is **executed on every
propagation and returns `None` by construction until a factory is registered** (`propagator.py:137`,
early-return at `:138-139`) — architect finding A-7 corrected the orchestrator's looser phrase
"the read side is live", which was ambiguous in exactly the way that matters. The absence of a
registration is already pinned. It is in the bundle because it is the residual open question from
`#3109` and it is two cheap edits.

**Independent Test**: Testable in isolation — assert the symbol is exported from the
`specify_cli.invocation` package, and read the docstring for the facts it must state. No dependency
on Stories 1–3.

**Acceptance Scenarios**:

1. **Given** the seam, **When** `register_saas_client_factory` is removed from
   `invocation/__init__.py`'s re-export (`:21`) or from its `__all__` (`:111`), **Then** a test
   reds naming the symbol.
   *(Narrowed per debugger finding D-4. The **export half** is genuinely unpinned. Deleting the
   `def` itself is **not** a valid before-state: `tests/invocation/test_adapters.py:29` imports the
   symbol at module scope and `tests/specify_cli/invocation/test_propagator_consent_gate_3030.py:53`
   does the same, so deleting the `def` is a collection-time ImportError in two files, and
   `tests/architectural/baselines/fast-tests-core-misc-nodeids.txt:1841` pins a node id naming it.
   The spec previously claimed "the same deletion leaves the suite green"; that was measured false.)*
2. **Given** the seam's docstring, **When** a maintainer reads it, **Then** it no longer contains
   the false sentence, it names `request_text`, and it points to `propagator._get_saas_client` as
   the canonical record of the hazard rather than restating it (architect finding A-9).
3. **Given** a factory *is* registered, **When** the suite runs, **Then**
   `test_sync_registers_no_saas_client_factory` still reds by design — this mission does not
   relax that pin.

---

### Edge Cases

- **The operator names a decision that exists in no mission under the acting checkout.**
  Ownership is *not established*, which is not the same as "owned elsewhere" and not the same as
  "owned by the cwd". Fail closed with a message naming the acting root and the missions searched.
  It must **not** claim to identify the owning project — under C-009 and Decision D-2 that
  information does not exist (paula finding P-3, reviewer finding R-3).
- **`--mission-slug` is supplied and disagrees with the checkout.** Under Decision D-2 the slug is
  a *narrowing hint over the acting checkout's own missions*, never an instruction to look
  elsewhere. A slug naming a mission the acting root does not contain is an ownership failure, not
  a redirection.
- **`--mission-slug` is omitted.** No longer a dilemma: the within-checkout search answers "does
  this checkout own this decision?" with no slug at all (Decision D-2). No currently-succeeding
  invocation becomes a refusal.
- **The decision ledger under a searched mission is MISSING.** Measured: `load_index`
  (`decisions/store.py:61-67`) returns an **empty index** for a missing file — `if not
  path.exists(): return DecisionIndex(mission_id="", entries=())` at `:64-65`. A missing ledger is
  therefore *not* an error; it is a mission that owns no decisions, and the search simply moves on.
  It contributes **no** unreadable-ledger flag. *(Re-measured in round 2: the earlier cite
  `store.py:58-64` / `:63` was off by up to three lines. The correct anchors are `def load_index`
  `:61`, `path.exists()` `:64`, `json.loads` `:66`, `model_validate` `:67`.)*
- **The decision ledger under a searched mission is MALFORMED.** Measured: `load_index` **raises** —
  `json.JSONDecodeError` from `json.loads` at `:66` for bad JSON, pydantic `ValidationError` from
  `model_validate` at `:67` for schema-invalid content. This is a **measurably different** behaviour
  from "missing" and the spec previously lumped the two (reviewer finding N-1). It is an
  *unreadable* ledger: ownership cannot be established from it, and unreadable ownership is not
  consent.
  **Scoping rule — mandatory, and it is what keeps SC-002 true.** An unreadable ledger in a mission
  that is **not** the answer must **not** veto a positive membership hit elsewhere. It may be
  reported as a warning. **Refusal is correct only when the search terminates with no positive hit
  AND at least one ledger was unreadable.** Without this rule a decision owned by healthy mission Y
  would be refused because unrelated mission X happens to carry a corrupt `index.json` — measured:
  49 ledgers across 333 mission dirs in this repository, so the odds of an unrelated corrupt file
  are not theoretical, and **that invocation succeeds today** because `cmd_widen` reads no ledger at
  all.
  **This edge case sits directly on a recorded interpreter divergence** (debugger finding D-11,
  measured live in the plan phase): `Path.exists()` **returns `False` on 3.12+** and **raises
  `PermissionError` on 3.11** for an `EACCES` path — and `store.py:64` is exactly that call,
  inside the function Decision D-2 mandates FR-001 reuse. A permission-denied ledger therefore takes
  the "missing" branch locally and **raises on CI**.
  **Which permission denial reaches that call, measured (uid 1000, Python 3.14.4) and independently
  reproduced — this is the anchor SC-014's test shape is built on:**

  ```
  decisions/ directory mode 0o000 (file readable)  -> Path.exists() == False   <- the divergent branch
  index.json file mode 0o000 (directory readable)  -> Path.exists() == True    ; PermissionError
                                                      arrives later, from read_text() at :66
  ```

  `stat(2)` requires **search permission on the parent directory**, not read permission on the file —
  POSIX-level, not interpreter-dependent — so **only the directory case reaches `:64`'s divergence**;
  the file case is a `read_text` failure at `:66` and behaves identically on 3.11 and 3.14.
  Consequence for the design: the ownership
  module **cannot rely on `load_index` alone** — it needs an explicit `except OSError` alongside the
  `JSONDecodeError` / `ValidationError` handling, and it must be **executed** under 3.11 to prove
  it. NFR-006 and SC-014 carry that.
- **The search terminates with no positive hit and every ledger was readable.** Ownership is not
  established. Refuse. **The forbidden repair, stated so a successor cannot reach for it:** *do not
  fall through to the acting root when the ledger does not list the decision.* That fall-through is
  the obvious fix for an SC-002 red and it **reinstates exactly the leak this mission closes** — it
  restores "the acting checkout answers consent for a record it may not own" (debugger finding
  DB-1). If SC-002 reds, the correct responses are: confirm the ledger is present (`git pull`),
  narrow with `--mission-slug`, or accept the refusal. Not a fall-through.
- **The checkout is not a project root at all.** Resolves to no uuid and therefore denies today.
  That safety net must remain, and must not be mistaken for the ownership check — it does not
  catch a *valid* root for the *wrong* project.
- **`--dry-run`.** The dry-run branch prints the endpoint with the id interpolated and transmits
  nothing. Ownership checking must apply to the live path; whether dry-run also refuses on
  mismatch is a design choice (Q5), but dry-run must not become a way to get the id formatted for
  copy-paste into a real invocation without ever seeing the mismatch warning.
- **A refusal string that is true of one transport and merely vacuous for the other.** "Your
  engagement identifiers must not be transmitted" is not false for a transport that carries none,
  but it misinforms the operator about what was about to happen. Vacuous truth is not the bar.
  **Closed by Q2**: the identifier-set fragment is per-caller, so no transport is ever handed the
  other's vocabulary. The residual hazard is now the *template*, not the fragment — a future edit
  that hard-codes an identifier kind into the shared sentence reintroduces this case, which is what
  SC-004's per-transport fragment assertion catches.
- **A brand-new package as the shared module's home.** It matches no CI filter group, so it routes
  to `run_all` — loud by design (F-A3) — but it is unclassified by the architectural landscape
  (C-005), and **no existing gate notices if the classification edit is forgotten.** The
  measurement behind that claim, and the assertion that closes it, are stated once at **SC-025**.
- **Renaming during consolidation.** The literal text `project_egress_refusal` must remain present
  in `src/specify_cli/tracker/saas_client.py` or an existing seam-allowance gate reds (F-A5) — but
  that gate is a *substring* test and the import line at `tracker/saas_client.py:34` already
  satisfies it on its own. Deleting the call at `:329` keeps the gate green. See C-004 and FR-027.
- **Partial consolidation leaving a re-export.** A surviving `tracker/egress_consent.py` re-export
  renders the **identical correct string** a correct consolidation renders, so no text comparison
  distinguishes the two states. **The hazard (rot-mode 5 — by-value binding at import time), its
  measurement, and the assertion that closes it are stated once, at SC-004 clause 3.** Not restated
  here.

---

## Requirements *(mandatory)*

### Functional Requirements

Labels: **[build]** = change-forcing, **[ratchet]** = already true at `bb2020fea`, must stay true,
no build work expected, **[folded]** = a restatement of another requirement, carrying no independent
cost and no independent criterion. A `[ratchet]` row with no Success Criterion is a deliberate
omission, not a coverage gap (reviewer findings R-11, R-20).

**One honesty note on `[build]`, added in round 2.** `[build]` covers two different kinds of work:
new *behaviour*, and a new *assertion* over behaviour that already holds. FR-014, FR-015 and FR-016
are the second kind — the guards already behave as required; what does not exist is a test that
would notice if they stopped. Those rows say so explicitly in their text. This is not a `[ratchet]`,
because a ratchet is a row where no *production* change is forced; here a real guard behaviour is
being observed for the first time.

**Round-3 refinement, so the two labels stay honest.** Three rows are `[ratchet]` **and** carry a
criterion that must still be written: **NFR-004**, **FR-027** and — new in round 3 — **FR-009**.
The distinguishing test is *whether the mission has to make anything true*. For FR-014/015/016 the
assertion is the first observation of a guard property nothing watches; for the three ratchet rows
the property is already observed or already fixed by an operator decision, and the criterion exists
only to **pin** it. **A criterion attached to a `[ratchet]` row does not discriminate a correct
implementation from an incorrect one**, and each such criterion now says so in its own text — which
is exactly the defect round 3 found in SC-004 (HIGH-2).

| ID | Title | User Story | Priority | Label | Status |
|----|-------|------------|----------|-------|--------|
| FR-001 | Establish that the acting checkout owns the decision before egress | As an operator, I want `decision widen` to determine, from local files under the acting root only, whether the named decision belongs to a mission in that checkout, before any request is built — so that consent is asked about the project that owns the record. Mechanism fixed by Decision D-2: glob `<repo_root>/kitty-specs/*/decisions/index.json` and membership-test with the existing `load_index` — `index_path` `decisions/store.py:46`, `def load_index` `:61` — reusing the membership shape at `store.py:115-118`. **Anchors corrected in round 3 (reviewer finding RM-2): the earlier `:58-64` / `:112-120` cites were stale and `:58` is a comment banner.** What `load_index` does on a **missing** vs a **malformed** vs an **unreadable** file is stated once, in *Edge Cases* — build against that, not against a restatement. | High | build | Open |
| FR-002 | Fail closed when ownership is not established | As an operator, I want the command to refuse — transmitting nothing — when the acting checkout is not shown to own the decision, so that "not established" is never treated as "mine". The refusal names the acting root and the missions searched; it does **not** name another project, because it cannot (C-009). **Absorbs FR-004 and FR-007** (both `[folded]`): "consent is answered for the owning project" and "credentials and team never cross project boundaries" are the same property stated from the consent side and the transport side. **Forbidden repair, binding on the implementer:** when the search finds no positive hit, do **not** fall through to the acting root. See the edge case "the search terminates with no positive hit"; the fall-through reinstates the leak (debugger finding DB-1). | High | build | Open |
| FR-003 | `--mission-slug` becomes load-bearing on the live path | As an operator, I want the mission slug I pass to affect the real invocation and not only `--dry-run`. **Stated as an unfakeable differential** (reviewer finding R-13): holding `decision_id`, cwd and `--invited` fixed, changing `--mission-slug` from the owning mission to a non-owning mission **of the same checkout** must flip the outcome from one request to zero. Printing the slug does not satisfy this. FR-003 **must not land without FR-001 and FR-002** — alone it widens the disclosure surface by making an operator-typed slug affect the live path for the first time (debugger finding D-9). | High | build | Open |
| FR-004 | *(Folded)* Consent is answered for the owning project | Restatement of the invariant FR-002 delivers, retained because other requirements reference it. Under Decision D-2 every path that reaches the consent gate has acting root == owning root **by construction**, so there is no assertion of the form "the resolver received the owner's root" that can distinguish the fixed code from `bb2020fea` (reviewer finding R-4). **FR-004 therefore carries no independent Success Criterion and no independent implementation cost.** It is discharged by SC-001 + SC-011. | High | folded | Open |
| FR-005 | `decision_id` is shape-checked before it reaches a URL | As a client whose engagement name is confidential, I want a mistyped or slug-shaped identifier rejected at the CLI boundary. **This is defence-in-depth. It does not satisfy FR-001 or FR-002.** A ULID regex alone would make a naive reading of SC-001 green with no ownership logic at all (reviewer finding R-5) — which is why SC-001 now requires a well-formed ULID present in project B's ledger. | High | build | Open |
| FR-006 | All **four** root/ownership divergence routes are covered | As an operator, I want cwd, `SPECIFY_REPO_ROOT`, the `or Path.cwd()` fallback **and the operator-supplied `--mission-slug`** to be subject to the same ownership check, so that no one of them is a bypass. The first three converge in `locate_project_root` and hold by construction; the fourth is new with FR-003 and is slug-shaped, not root-shaped (paula finding P-1). | High | build | Open |
| FR-007 | *(Folded into FR-002)* Credentials and team never cross project boundaries | As a project owner, I want a request carrying my project's identifiers to be authorised by, and addressed to, my project's team — or **not sent at all**. **Folded explicitly in round 2, as FR-004 was**: under Decision D-3's refuse-on-divergence shape, "no request crosses a project boundary" *is* "FR-002 refused", and FR-007's coverage row was byte-identical to FR-002's. Two folds is honest; one fold and one unlabelled twin is not. **FR-007 carries no independent Success Criterion and no independent implementation cost.** — *Ground corrected in round 2 (debugger finding DB-3), stated in full at Decision D-3*: the re-resolve shape is deleted **not** because C-009 forbids it, but because **it is not expressible under Decision D-2's within-checkout design; the cross-checkout search that would express it is deferred to FU-4 under C-011.** | High | folded | Open |
| FR-008 | Exactly one editable presentation of the refusal policy, enforced mechanically | As a maintainer, I want it to be impossible for the verdict→message mapping to acquire a second independently-editable copy. Stated outcome-first (reviewer finding R-14) so that Q1 option (e) — two files plus an equivalence gate — remains a legal answer: the requirement is *one editable presentation, mechanically enforced*, not *one file*. The plan must name the enforcement mechanism (shared module, or the gate) and SC-015 asserts it. | Medium | build | Open |
| FR-009 | The merged refusal wording is true of its own caller, against enumerated sets | As an operator, I want the refusal to name every identifier kind the transport I used can transmit, and imply none it cannot. **Mechanical, not aesthetic** (reviewer finding R-6), and **fully mechanical under the operator's Q2 decision**: the shared module owns the template; each transport passes its **own** identifier-set fragment. Each transport's test therefore asserts two things against the enumerated sets in Key Entities — (i) its own set is **fully named** in the rendered string, and (ii) **no other transport's kinds appear** in it. Both halves are checkable against a fixed list the implementer did not choose, so the implementer can no longer both pick the wording and write the assertion that blesses it. **The union string is explicitly not the requirement** — naming `decision_id` to a tracker operator overstates exposure, and FR-009's second clause forbids it. **Relabelled `[ratchet]` in round 3 (debugger HIGH-2 knock-on): the operator's Q2 decision fixes the required rendered text to the strings that already exist — both current `DENIED` strings survive *verbatim* — so this mission produces no wording and SC-004 clause 2's outcome holds of the unconsolidated state by construction. The build work is the assertion, the same shape as NFR-004 and FR-027, not the FR-014/015/016 shape.** Its criterion must therefore not be read as discriminating: SC-004 clause 2 is a ratchet, and what discriminates in SC-004 is **clause 3**. *Bound on the relabel*: if SC-004 clause 2's check against the Key-Entities sets fails on the **existing** text, the fix is a wording change and FR-009 returns to `[build]` — see the `[ratchet]` audit. | Medium | ratchet | Open |
| FR-010 | Pinned refusal text survives byte-identical | The `could not be determined` phrasing is preserved exactly so the four existing assertions keep testing what they were written to test. **Already true; must stay true.** Per `delete-the-assertion-not-the-test`, the four existing assertions are not to be modified — the new `DENIED` pin (FR-024) is *added* alongside (reviewer finding R-10). | Medium | ratchet | Open |
| FR-011 | `UNDETERMINED_PROJECT_REFUSAL` stays unexported | The constant is kept out of every `__all__`, so the symbol-level dead-code ratchet stays honest. **Self-enforcing**: `test_no_dead_symbols.py:13-24` walks *every* `*.py` under `src/`, so a new package's `__all__` is scanned too — this survives Q1 option (d) with no extra work (debugger finding D-13). | Medium | ratchet | Open |
| FR-012 | The consent chain remains single | The shared wrapper keeps resolving through `invocation.adapters.resolve_egress_consent` and never re-derives checkout→project→consent locally. **Already true; must stay true** (C-003). | High | ratchet | Open |
| FR-013 | Import failure still degrades to a refusal | An unimportable hosted-sync package produces a refusal naming the failure, never a permit. **Already true; must stay true** — and its contract depends on the `import specify_cli.sync` remaining **lazy and inside the function** (`saas_client/egress_consent.py:107-113`). Placement choices that force `specify_cli/sync/__init__.py` to execute at transport-import time defeat it structurally (architect finding A-3; see Decision D-5). | High | ratchet | Open |
| FR-014 | Per-class non-vacuity floor in the attribution guards | Each guard asserts a floor **per transport class** rather than one global count, so losing every site of one class cannot be masked by the other class's sites. **Necessary and nowhere near sufficient** — see the falsifier. | High | build | Open |
| FR-015 | Per-class attribution vocabulary preserved | Each transport class keeps accepting exactly the attribution forms it accepts today, so unification does not silently widen either class to accept forms its guard rejects (`repo_root=` / bare positional for SaaS `from_env`; `project_root=` only for tracker). **The property already holds; the assertion is the build work.** Verified per class by SC-012 — and note the SaaS half needs a *specific* witness: "tracker accepts `project_root=`, which the SaaS guard already accepts for direct construction" is **vacuously true** and bites nothing (debugger finding DB-4). The witness that bites is on `from_env`. | High | build | Open |
| FR-016 | Per-class construction-site match predicates preserved | Each class's site-matching strictness is kept as it is today — **tracker**: `getattr(func, "attr", None)`; **SaaS**: a literal `Name("SaasClient")` receiver. **The property already holds; the assertion is the build work.** Verified by SC-013, which asserts, **per class, that an unused-but-matching construction shape still matches**: tracker `mod.SaaSTrackerClient(project_root=…)`, SaaS `SaasClient(project_root=…)`. **No non-match is pinned anywhere in this spec** — round 3 withdrew that proposal on measurement. The `mod.SaasClient(...)` reasoning — why it is excluded by design, and why pinning that exclusion would red on a coverage *improvement* and collide with FU-8 — is stated once, at SC-013. **`mod.SaasClient.from_env(x)` is unguarded on *both* guards and named by no requirement here** — deliberate, filed as FU-8, recorded so the silence is not mistaken for coverage. | Medium | build | Open |
| FR-017 | The guard covering this mission's own construction-site edit runs on this mission's own diff | **Narrowed per Decision D-4.** This mission edits `cli/commands/decision.py:558` — a `SaasClient` construction site. Therefore a pull request whose diff is confined to `src/specify_cli/cli/**` must select a CI job that collects the SaaS-client attribution guard. Non-negotiable: otherwise this mission's own change is unguarded (architect finding A-2). Mechanism for asserting it: `tests/architectural/_gate_coverage.py`'s `filter_groups` (`:476`) and `job_gating_groups` (`:474`, `:612`), which already parse `dorny/paths-filter` steps (`:357`, `:531-533`). **The general re-keying of guard routing on construction-site locations — including the tracker guard's `tests/sync/` placement — is out of scope and filed as a follow-up issue.** | High | build | Open |
| FR-018 | The seam docstring states the truth and points at the canonical record | `register_saas_client_factory`'s docstring must (i) drop the false sentence "Called once at sync package startup" (`adapters.py:135`), (ii) state that nothing registers a factory today, and (iii) **point to** `propagator._get_saas_client` (`propagator.py:70-83`) as the canonical record of the `request_text` hazard rather than restating it — a second independently-editable copy of one rationale is the exact defect FR-008 exists to remove (architect finding A-9). **Trap: the identical sentence appears on the sibling registrar `register_egress_consent_resolver` (`adapters.py:113`), where it is TRUE — sync does register that resolver. A grep-and-replace across `adapters.py` would break a correct docstring.** | Low | build | Open |
| FR-019 | The seam's **export** is pinned | A test reds if `register_saas_client_factory` is removed from `invocation/__init__.py`'s re-export (`:21`) or its `__all__` (`:111`). **Scope narrowed to the export half** because deleting the `def` is already loudly red — two test modules import it at module scope and a node-id baseline names it (debugger finding D-4). Pinning the `def` would land a pin with no demonstrated discriminating power. | Low | build | Open |
| FR-020 | The ownership derivation is one named function, **outside `cli/commands/**`**, importable by a non-CLI caller | As the next transport author, I want "which project owns this record" to be answerable by calling something, not by re-reading `cmd_widen`. FR-001's logic must be a **single named function** with a **stated module home** — a constraint of the same weight as C-003 carries for the consent chain. **Stated as a positive property, not only as a forbidden shape** (reviewer finding N-7): the forbidden inline block in `cmd_widen` has a *permitted near neighbour* — a module-private `def _owns_decision(...)` at the bottom of `cli/commands/decision.py` — which satisfies "one named function with a stated home" and satisfies SC-018, **and is still the fifth private answer**. The positive property that distinguishes a seam from a helper: the function **must not live under `src/specify_cli/cli/commands/**`**, must not be name-mangled or module-private, and **must be importable and callable by a non-CLI caller** — a test in a non-CLI test tree imports it by its public path and calls it. **Its home is `src/specify_cli/decisions/ownership.py`, NOT `src/specify_cli/egress/`** — see the post-acceptance correction below. | High | build | Open |
| FR-021 | Ambient inputs to ownership resolution are explicit, and containment is asserted | Any path used to answer the ownership question must be proved to lie under the acting root **before its index is consulted**. This is aimed at `resolve_feature_dir_for_mission` (`missions/_read_path_resolver.py:1608-1631`), which accepts ambient context through **three** parameters — `mission_slug`, `cwd` and `env` (`env` being the channel `SPECIFY_REPO_ROOT` already travels on, F-B4) — delegates to a topology-aware selector, and returns `Path(context.feature_dir)` **with no assertion that the result lies under `repo_root`** (paula finding P-1). Two admissible discharges, plan's choice: **(i)** call it with `cwd`/`env` passed explicitly and add a `Path.is_relative_to(repo_root)` assertion, or **(ii)** do not use it at all — restrict the slug to selecting among the mission directories the FR-001 glob has already enumerated under `repo_root`, which makes containment hold by construction. **The two discharges are verified differently, and SC-018 is conditional on the choice** (reviewer finding N-4): under (i) the containment check must be shown **biting**; under (ii) the outside-root case cannot be constructed at all, and the substitute is an **enumeration equality**. **Both discharges additionally carry the glob-path obligations** — `.resolve()` before the containment test, and the one-level depth assumption pinned (reviewer finding N-5). All three are stated once, at SC-018. | High | build | Open |
| FR-022 | The boundary is recorded in a one-page ADR | As the maintainer who edits a transport six months from now, I want the egress-consent boundary to exist in the charter authority path. Measured: `grep -rn "resolve_egress_consent\|ConsentedBatch\|project_egress_refusal" docs/adr/3.x/ docs/context/` returns **0 hits** (controlled diagnostic: a known-present term returns 12, a nonsense term returns 0), while the charter instructs every agent to read `docs/adr/3.x/` when changing a structural boundary. The ADR must name: the boundary; the **provenance invariant** (framing 3 above); and the fact that **the attribution guard is syntactic** — it can prove a root was passed, never that it was the owning root. Cheapest item in the bundle and the only one acting on *recurrence* rather than on an instance (paula finding P-4). | Medium | build | Open |
| FR-023 | "Engagement" is defined in the terminology authority | `grep -ril engagement docs/context/` returns **0 of 22 entries** (probe non-vacuous: the same grep for `mission_slug` returns 1). This spec builds its central confidentiality argument on "a `mission_slug` is a client engagement name", and FR-009 bakes the word into an operator-facing string. **Unconditional as of round 2**: round 1 offered an escape — "*or* resolve Q2 toward vocabulary the glossary already knows" — and the operator's **Q2 decision keeps "engagement" verbatim in the tracker fragment**, so the escape is closed. The term must be defined in `docs/context/` as part of this mission. Do not ship an operator-facing term the glossary does not know (DIR-032; reviewer finding R-17). | Medium | build | Open |
| FR-024 | The merged `DENIED` wording is pinned in **both** packages' test trees | The runtime string that actually changes in this consolidation is the `DENIED` branch (`saas_client/egress_consent.py:127` "decision" vs `tracker/egress_consent.py:190` "engagement"), and **nothing pins either side** — grep for `decision identifiers` / `engagement identifiers` across `tests/` returns zero hits. SC-010 would stay green if the `DENIED` branch were deleted entirely. Add a content assertion on the merged wording in each package's test tree (reviewer finding R-10). Additive only — the four existing assertions are not touched. | Medium | build | Open |
| ~~FR-025~~ | *Retired in round 2 — folded into SC-004* | FR-025 was written as a **conditional over tests** — "*any test that* patches or mutates…" — so writing no such test satisfied it while the hazard stood untouched. The hazard is a property of the **consolidation**, not of any test. It is now an **unconditional** clause of SC-004, and in round 3 that clause became a **binding-identity assertion** (two `is` comparisons) rather than a reporting instruction — a reporting instruction only helps an author who already knows to look. **The hazard itself is stated once, at SC-004 clause 3.** | — | retired | — |
| FR-026 | The per-site enumeration in `saas_client/egress_consent.py` is corrected | Item 4 of the enumeration at `saas_client/egress_consent.py:52-76` currently argues the `decision widen` entry is benign because `decision_id` "is a ULID rather than a slug — so no engagement name crosses the wire on this path". **F-B2 falsified that**: there is no validation anywhere on the path and the string is interpolated raw into the URL. The prose carrying the correctness argument is stale, and the attribution guard cannot catch it (paula finding P-5). Rewrite the entry for the post-FR-001 state. | Medium | build | Open |
| FR-027 | `project_egress_refusal` remains a **live call** on the transmit path, asserted behaviourally | C-004's gate is a plain substring test over the whole file, and `tracker/saas_client.py` contains the literal at `:34` (import) **and** `:329` (call). Deleting the call at `:329` leaves the import satisfying the gate; a docstring mention would satisfy it with no code at all. The consolidation is precisely the change most likely to produce that state (architect finding A-5, correcting F-A5's over-claim). **Relabelled `[ratchet]` in round 2 (reviewer finding N-8 / debugger, converged): the behavioural assertion already exists, twice**, in `tests/sync/tracker/test_saas_client_consent_gate_3030.py` — `test_unconsented_project_transmits_no_engagement_name` (`:258-289`; writes a non-consenting config at `:267`, drives `SaaSTrackerClient(project_root=…)` at `:269`, asserts `sink == []` at `:279` and a non-`None` refusal at `:283`) and `test_project_local_refusal_is_honoured` (`:311-324`). Both reach the refusal through the call at `saas_client.py:329`. **No new test is required.** The requirement is that these two stay passing through the consolidation; a change that leaves only the import at `:34` reds them. Carrying it as `[build]`/High was a ratchet wearing build clothing. | — *(ratchet)* | ratchet | Open |

**POST-ACCEPTANCE CORRECTION to FR-020 (orchestrator ruling, after plan reconciliation; grounds
re-ordered at plan review round 1).**

> *Placement note.* This block was previously inserted **inside** the table above, between the
> FR-020 and FR-021 rows, which stopped FR-021…FR-027 from rendering as table rows at all. It is
> now below the table. **Content-preserving except for the ground re-ordering recorded in the
> final item.**

Round-3 text read *"Under the resolved Q1 its home is `src/specify_cli/egress/`."* **That was
wrong, and it is exactly the conflation reviewer finding P-2 warned about** — Q1 answered
*"where does the refusal **wrapper** live"*, which is a different question from *"where does
the **ownership derivation** live"*. **Its home is `src/specify_cli/decisions/ownership.py`.**
Grounds, in descending force:

1. **Bounded-context ownership (DIR-031) — the load-bearing ground.** *"Which project owns this
   record"* is a question in the **decisions** bounded context: it is answered by reading the
   decision ledger and it means nothing outside it. `egress` is a **presentation wrapper for a
   refusal string** — a sentence template, four verdict branches, and one constant. Putting a
   **ledger reader** inside it makes it a **two-concern module**, and those are precisely the two
   concerns FR-020 exists to keep apart: reviewer finding P-8 records **three live spellings** of
   "which project owns this data" and warns the plan not to merge them. Merging the ownership
   derivation into the refusal wrapper would re-create that conflation **inside the fix for it**.
2. **The operative criterion never said otherwise.** **SC-018 names no module or package** — it
   requires a single named function, in a stated module, outside `src/specify_cli/cli/commands/**`,
   importable by a non-CLI caller. `decisions/ownership.py` satisfies every clause. Per this
   document's own *How to use this document*, SC-018 is the implementation surface and the
   Requirements table is the justification record; where they disagreed, the table was the
   stale side. **Decisive on its own.**
3. **Cohesion.** The ledger lives in `specify_cli/decisions/`; the derivation that reads it
   belongs beside it. And structurally: it adds a dependency to a module **whose entire value is
   its emptiness** — `egress` earns its place by importing nothing interesting, and a
   `specify_cli.decisions.store` import turns "one function and one constant" into "a module that
   reads ledgers", while stranding the function away from the ledger code it is a client of.

**A ground this block used to LEAD with, now demoted because it was falsified by measurement —
recorded so it is not re-proposed.** The former ground 1 read *"It would break the premise
`egress/` rests on"*: that a `specify_cli.decisions.store` edge would fire Q2's falsifier **F2**
and undermine the Q1 placement. **False on two counts, both measured at plan review round 1
(architect finding PA-5):** (a) **F2's antecedent is an import from `saas_client/` or `tracker/`**
— F2 is about *transport* neutrality, and an edge to `specify_cli.decisions.store` does not
satisfy it; (b) the module-level closure probe, run controls-first (a known `specify_cli.sync`
importer must measure YES; `saas_client` 6 modules NO, `tracker` 11 NO, `delivery` 4 NO), gives
**`specify_cli.decisions.store` closure = 2 modules, reaches `specify_cli.sync` = NO** — so the
edge endangers neither F2 nor FR-013. The surviving true part of that claim is the weaker
structural point now folded into ground 3. **The reason this matters enough to correct in an
ACCEPTED spec: a falsifiable claim in the lead position of a ruling invites a successor to
overturn the whole ruling by falsifying it.** The ruling stands on grounds 1 and 2, which
measurement cannot touch.

**Consequence recorded, because deletion moved an anchor:** SC-022 cites the per-site
enumeration at `saas_client/egress_consent.py:52-76`. Under the plan's PB-5 decision that file
is **deleted**, so the enumeration relocates to the shared module. **Substance preserved, anchor
moves** — a reviewer must not read SC-022 as unsatisfiable, and the PR body must say so.

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| ~~NFR-001~~ | *Retired in round 2 — folded into NFR-003* | NFR-001 ("count unchanged **or lower**") and NFR-003 ("count **at least** the baseline") were the same per-class integer with opposite inequalities, both mapping to SC-007, both carrying the same blind-spot caveats. **NFR-003 is the survivor** and now states both inequalities. *Why NFR-003 rather than NFR-001*: NFR-003's **lower** bound is the change-forcing half for this mission — the live hazard is guard-coverage **halving** during consolidation (F-A3's four mechanisms), and reviewer finding R-18 established that the per-class integer floor, not SC-005's red, is what forces work. NFR-001's upper bound is a by-product SC-007 already asserts, and NFR-001 itself conceded it "is not a proof about egress surface". Keeping the weaker-claim row as the survivor would have left the change-forcing property carried by a row that disclaims itself. | — | — | — |
| NFR-002 | The ownership check adds no network round-trip | `decision widen` performs at most the same number of HTTP requests as today (exactly one on the success path, zero on every refusal path). Ownership is established from local files under the acting root only — there is no remote decision-owner lookup to call (F-B1) and Decision D-2 introduces no cross-checkout enumeration. | Performance | High | Open |
| NFR-003 | **Scanned-site count** neither decreases nor grows unaccounted *(absorbs NFR-001)* | After the change, the per-class **scanned-site** counts are greater than or equal to the `bb2020fea` measurements (tracker 3, SaaS client 4), asserted per class rather than in aggregate — **and the count of name-matched network-transmitting construction sites has not increased**; any change to either total in either direction must be named and justified in the plan. **Stated bound, inherited verbatim from the retired NFR-001 — this is a count over *name-matched* sites, not a proof about egress surface.** Three documented holes make an unchanged count compatible with a new sink: (i) the scans match a literal class name — `ast.Name(id="SaasClient")` / `name != "SaaSTrackerClient"` — so an **aliased import, a factory, or a transport injected as a parameter is invisible** (debugger finding D-10); (ii) the parent mission's own Limit 7 (`egress-inventory.md:300-309`) — a file may hold more than one sink and an allowance covers them all; (iii) `#3113`'s positional-call blind spot, which is a property of the *boundary* guard, not these (see the Bundle A table). **Retitled from "Guard coverage does not decrease" because the metric cannot support that claim** (debugger finding D-5): in both guards `scanned += 1` executes *before* the attribution test (`test_client_consent_gate_3030.py:340` vs `:342-346`; `test_saas_client_consent_gate_3030.py:387` vs `:388`), so vocabulary widening leaves the counts exactly unchanged, and unifying on the SaaS guard's stricter predicate leaves `scanned["SaaSTrackerClient"] == 3` — exactly at the floor — while permanently blinding the guard to `mod.SaaSTrackerClient(...)`. Coverage is carried by FR-015/FR-016 and SC-012/SC-013, not by this count. | Security / Reliability | High | Open |
| NFR-004 | Every refusal branch is operator-actionable, pinned per branch | Each distinct refusal string names a concrete next action or the specific condition to correct; no branch returns a bare "denied". **Verified by per-branch content pins, not by "non-empty and distinguishable"** — five strings `"denied 1".."denied 5"` satisfy the weaker form, which is a defect-masking assertion under DIR-041 (reviewer finding R-8). Minimum pins, all five of which already hold at `bb2020fea`: the `DENIED` branch contains `sync opt-in`; the import-failure branch contains the exception text; the `NO_RESOLVER` branch names the resolver; `UNDETERMINED` and `UNANSWERABLE` remain **distinguishable from each other** despite both containing `could not be determined` (orchestrator correction C-1). | Usability | Medium | Open |
| NFR-005 | Each new or changed test passes in single-file isolation | Every test added or modified by this mission passes when invoked as a single-file `pytest` run from this clone's root, not only inside a full-suite run. **The evidence must state the count and the file list**, not merely "all isolated runs passed" — an empty set satisfies the bare claim (reviewer finding R-22). Required because shard-parallel isolation (`#3115`) has not landed and full-suite reds on this surface are not attributable. | Reliability | High | Open |
| NFR-006 | No interpreter-specific green — **executed, not asserted** | Behaviour asserted by this mission's tests must hold on the Python versions CI runs (3.11/3.12), not only on the locally installed 3.14 (F-ENV-2: 3.14 is the only local interpreter). **Executable form**: create a dedicated environment with `uv venv --python 3.11`, run this mission's touched test files plus **both** attribution guards under it, and quote the resulting `N passed` line verbatim in the mission's evidence. Asking the implementer to "identify divergent branches in the plan" is a judgement made on the wrong interpreter and is not verification (reviewer finding R-15). **Live and load-bearing here**: this mission's own "unreadable ledger" edge case sits on a recorded `Path.exists()`/`EACCES` interpreter divergence at `decisions/store.py:64`, inside the `load_index` Decision D-2 mandates FR-001 reuse — **the measurement is stated once, in *Edge Cases***. **A green 3.11 run over files that never touch the branch is a true statement about nothing** (debugger finding DB-5) — so NFR-006 additionally requires that a test *constructing* an unreadable ledger exist, be part of the 3.11 run, **and be shaped so that it can actually reach that branch** (round-3 HIGH-1: the round-2 shape could not). SC-014 names both. | Portability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | CORE placement is forbidden | The shared wrapper must not live in `invocation/`, `core/`, `status/`, or `readiness/`. Its lazy `import specify_cli.sync` is caught by the integration-boundary gate's full-AST walk, and the exemption allowlist is ratcheted at zero and described as permanently closed (F-A4). | Technical | High | Open |
| C-002 | Both transport **classes** remain independently guarded | Whatever is extracted, each transport **class** retains an attribution guard that can red on its own class's sites alone. Merging the two guards into one shared scanner is permitted only if FR-014, FR-015, FR-016 and FR-017 all hold. **Corrected from "per package"** (architect finding A-11): both guards already scan the **entire** `src/specify_cli` tree via `rglob("*.py")` (`test_client_consent_gate_3030.py:319-324`, `test_saas_client_consent_gate_3030.py:373-378`), so they are independent per class, not per package. **Useful consequence: wherever the shared wrapper lands, neither guard's scan scope changes — placement cannot shrink coverage.** Only merging the counters (F-A3 Mechanism 1) or the predicates (Mechanisms 2–3) can. | Technical | High | Open |
| C-003 | Project consent is represented once | The shared wrapper consumes the existing resolver; it does not read `sync.consent`, checkout routing, or config directly. Inherited verbatim from the parent mission's C-003. | Technical | High | Open |
| C-004 | The seam symbol name must remain textually present — **and that is all this gate proves** | The literal string `project_egress_refusal` must remain in `src/specify_cli/tracker/saas_client.py`, because a seam-allowance gate asserts the allowance's `seam_symbol` appears in the named `seam_module` file. Renaming the function reds that gate. **But the gate is a substring test and the file contains the literal at two independent places — `:34` (import) and `:329` (call) — so deleting the call still satisfies it.** The *text* is protected; the *seam* is not. C-004 must not be read by the plan as "the seam is protected" (architect finding A-5). FR-027 supplies the behavioural companion. | Technical | High | Open |
| C-005 | A new home must be classified — **and classification does not close the laundering route** | If the shared wrapper lands in a new `src/specify_cli/<name>.py` **module** *or* a new `src/specify_cli/<name>/` **package**, that module or package must be added to the integration-boundary gate's INTEGRATION prefixes (a one-line addition; verified to need no second edit, because `test_layer_rules.py:_DEFINED_LAYERS` enumerates **top-level** `src/` packages only via `_SRC.iterdir()` at `:202-208`, filtered on `p.is_dir()`). **Both forms are covered because the hazard is what the thing imports, not whether it is a directory** — the gate matches `mod == prefix or mod.startswith(prefix + ".")` (`test_integration_boundary.py:151-152`), so a module is caught by the first arm. *(Antecedent widened at plan review round 1 alongside SC-025's; the package-only wording was a latent gap regardless of Q1's answer. Under the resolved Q1 the wrapper is the module `src/specify_cli/egress.py`.)* **Restated honestly as "do not add a tenth"** (architect finding A-4): a module-level transitive-closure scan over 937 modules found **nine CORE modules already reaching `specify_cli.sync` transitively through unclassified packages**, all green under the gate — e.g. `status/aggregate.py:620 → coordination.status_transition:288 → git.commit_helpers:1148 → sync.local_commit`. Classification prevents this package from becoming the tenth; it does **not** close the route. The transitive-reach scan is a separate mission (see Follow-up issues). **And no existing gate notices if the classification edit is forgotten — SC-025 is the assertion that does**, and the measurement behind that claim, plus why round 1's discharge was a sentence rather than an assertion, are stated once at SC-025. | Technical | High | Open |
| C-006 | Bundle A has not landed; verification is constrained | `#3115` (shard-parallel test isolation) and `#3113` (egress-guard positional-call blind spot) are both OPEN as measured on 2026-07-31. Consequences are named per requirement in "Dependency on Bundle A" below. | Technical | High | Open |
| C-007 | Identifier validation applies only where the identifier is operator-supplied | FR-005's shape check binds the CLI argument of `decision widen`. It must not be applied to identifiers read back from a local store by the charter and plan interview paths. **The load-bearing reason, stated precisely** (paula finding P-9): those sites read the data **through** the root — `_get_mission_id(repo_root, slug)`, `WidenPendingStore(repo_root, slug)` — so a root-scoped read **cannot reach another project's record by construction**. Stated that way, C-007 also supplies the admission test for any future site: it is excluded only if its identifier is obtained through the same root the consent gate is asked about. | Technical | Medium | Open |
| C-008 | The command is `spec-kitty agent decision widen` | There is no top-level `decision` typer; the subcommand is reached through the `agent` group and is `hidden`. Any acceptance test, docs change, or reproduction must use the real invocation (F-B5). | Technical | Low | Open |
| C-009 | Ownership is positional and there is no mapping to consult | No `decision_id`→project mapping exists locally or remotely: the ledger entry schema is frozen with `extra="forbid"` and carries no project identity, the creating call takes `repo_root` and discards it, and the SaaS client's five endpoints include no decision-lookup. Any design that assumes such a mapping can be queried is invalid (F-B1). **This is what forces AS1 to weaken** (paula finding P-3 / reviewer finding R-3). **What it is *not*** (round 2, debugger finding DB-3): C-009 is **not** the ground on which FR-007's re-resolve shape is deleted — see Decision D-3. | Technical | High | Open |
| C-010 | Consent preconditions are written on disk, never inherited from a directory fixture | Both candidate test directories fabricate the very precondition US1 depends on: `tests/specify_cli/saas_client/conftest.py:51,74` and `tests/sync/tracker/conftest.py:55,166` each carry an **autouse** fixture that injects a **consenting** `project_root` whenever the kwarg is omitted. The widen path itself is safe as written (`from_env` always passes `project_root` explicitly, `client.py:136-142`), **but any `#3111` test that constructs a client inline in those directories inherits fabricated consent** (debugger finding D-12). The `#3111` acceptance test must therefore write **both** checkouts' `.kittify/config.yaml` on disk, pass roots explicitly, and carry an **in-file positive control** proving A's consent actually grants. This is the recorded trap twice over — the filename-matched guard (`tracer-tooling-friction.md:104-122`) and tests green only because a directory fixture arranged their premise (`:666-686`). | Technical | High | Open |
| C-011 | Hard scope bound | The delivered surface is bounded to: within-checkout ownership resolution (Decision D-2), CLI identifier validation, the wrapper consolidation, the guard hardening (FR-014–FR-016), FR-017's **narrow** routing fix, the seam edits, the ADR, and the glossary entry. **If the plan concludes that a cross-checkout search (Q4's rejected option) or a uuid-typed seam (Q3) is required, that work defers to a follow-up issue and this mission ships the within-checkout resolution.** Any one of those is comparable in size to the entire `#3110` half (reviewer finding R-16). | Process | High | Open |

### Key Entities

- **Decision record**: a `DecisionPoint` identified by `decision_id`. Its owning project is
  encoded *positionally* — by which repository's `kitty-specs/<mission-slug>/decisions/index.json`
  contains it — and never as a field on the record.
- **Owning project root**: the checkout that contains the record a request will carry. Distinct
  from the *acting* root (cwd, `SPECIFY_REPO_ROOT`, or the `Path.cwd()` fallback). The whole of
  `#3111` is the case where these two differ.
- **Owning project of a record** — *the concept, and its three current spellings.* After this
  mission the codebase holds three live notions of "which project owns this data", and the plan
  must not conflate them (paula finding P-8):
  1. **Envelope-carried uuid** — `delivery/consent_gate.py:181-207` plus the `ConsentedBatch`
     mint. Authoritative for the delivery path; the only spelling that is structurally unfakeable.
  2. **Positional / locality** — three interview sites, three tracker sites, invocation Op records.
     Authoritative wherever the data is read *through* the root it is attributed to (C-007).
  3. **FR-001's ledger-membership derivation**, at one call site. This is the **first mechanical
     reader of positional ownership** in the codebase, which is a good thing. It becomes
     split-brain only if inlined and unnamed — which is what FR-020 forbids.
- **Consent verdict**: the value returned by the single resolver. `permits_egress` true is the
  only permission; every other member, present or future, is a refusal.
- **Refusal string**: the operator-facing rendering of a verdict. This is the thing that is
  duplicated today, and the only thing this mission's `#3110` half consolidates.
- **Identifier kinds each transport can transmit** — enumerated from source so FR-009 is
  mechanical rather than aesthetic (reviewer finding R-6):

  | Transport | Identifier kinds on the wire | Derived from |
  |---|---|---|
  | **SaaS client** (`saas_client/client.py`) | `team_slug` (URL path), `mission_id` (URL path; documented "ULID **or** slug", and a slug is a client engagement name), `decision_id` (URL path), `invited_user_ids` (Teamspace user ids, JSON body) | `_team_path` `:208`; `:236`, `:274`, `:301`, `:346`; `post_widen` body `:275` |
  | **Tracker client** (`tracker/saas_client.py`) | `provider`, `project_slug` **or** `binding_ref` (routing key), `mission_id`, `mission_slug`, `external_issue_id` / `external_issue_key` / `external_issue_url`, `external_title` (verbatim issue title text), `operation_id`, `cursor`, and arbitrary `items` payloads on push | `_routing_params` `:266-290`; `pull` `:523-531`; `bind_mission_origin` `:652-681`; `push` `:775-786` |

  **These two sets are the arguments Q2's per-caller fragment renders from** — each transport
  passes its own, the shared template renders it, and SC-004 asserts each against the row above.
  The asymmetry is the whole reason: **the tracker carries no `decision_id`, and the SaaS client
  carries no `project_slug` and no issue titles.** Reviewer finding N-2 counted the symmetric
  difference at 15 kinds; on the table above, **`mission_id` is the only member the two sets share**.
  A single byte-identical string naming the union would therefore tell a tracker operator that
  `decision_id` was at stake, which US2-AS2 forbids — the conjunction of "byte-identical" and
  "implies no kind this transport cannot transmit" was an **empty solution set**, and the operator's
  Q2 decision is what makes it non-empty.
- **Attribution guard**: an AST scan over the whole `src/specify_cli` tree that reds when a
  transport is constructed without being told whose data it carries. Two of them exist, one per
  transport **class** (not per package — C-002), they are fully independent, and their
  independence is load-bearing. **The guard is syntactic by construction**: it proves a root was
  passed, never that it was the *owning* root — its own docstring concedes this verbatim at
  `test_client_consent_gate_3030.py:312-315` ("It cannot prove the root is the right one").
- **The SaaS-client seam**: `register_saas_client_factory` (write side, no production caller) and
  `get_saas_client` (read side — **executed on every propagation, returning `None` by construction
  until a factory is registered**, `propagator.py:137` with the early return at `:138-139`). A
  deliberately empty, gated slot — not an orphan.

---

## Falsifiers and preconditions

The parent mission's most useful habit was recording, for each decision, the observation that
would falsify it. Repeated here for every non-obvious requirement and for **every decision this
spec takes**. Requirements that assert an **absence** additionally state how one would know the
absence was real rather than vacuous.

### Decisions taken in this specification

**Decision D-2 — `--mission-slug` is optional; ownership is answered by a within-checkout search.**
Glob `<repo_root>/kitty-specs/*/decisions/index.json` and membership-test with the existing
`load_index` — `index_path` `decisions/store.py:46`, `def load_index` `:61` — reusing the membership
shape at `store.py:115-118`. *(Anchors corrected in round 3, reviewer finding RM-2; `:58` is a
comment banner. `load_index`'s missing/malformed/unreadable behaviour is stated once, in
*Edge Cases*.)*
*Why*: it dissolves the SC-002-vs-FR-002/FR-003 contradiction (no currently-succeeding invocation
becomes a refusal), needs **no** `decision_id`→project mapping (C-009 stands), needs **no**
mandatory `--mission-slug` (no compatibility break on a hidden automation-facing command), makes
**no** network call (NFR-002 holds), and performs **no** cross-checkout enumeration (no new
disclosure surface). It is strictly better than both options Q4 originally offered.
*Falsifier*: **if a `decision_id`→owning-project mapping ever lands** — a ledger schema column, a
`meta.json` field, or a server endpoint — the search stops being the only option and the design
should be revisited. C-009 is a measurement of today, not a law.

**Decision D-3 — FR-007 resolves to refuse-on-divergence; the re-resolve option is deleted.**
*Why it is forced, not merely preferred* — **ground corrected in round 2** (debugger finding DB-3;
the conclusion stands, the stated ground was imprecise): re-resolving token and team "from the
owning root" requires **knowing the owning root**. Round 1 attributed that impossibility to C-009.
**That is wrong.** C-009 is about the missing `decision_id`→project **mapping**; what actually
blocks re-resolve is the absence of a **checkout enumeration** — a different thing, and a
**buildable** one. Measured: `checkout_roots` has exactly **two** callers, both building a
**one-element** list from `locate_project_root(cwd)` (`delivery/selection.py:103-111`,
`sync/background.py:255-278`), and a grep for any machine-level checkout or project enumeration in
`src/specify_cli/` returns **zero**. Nothing forbids building one; this mission simply is not
building one. **Correct statement: re-resolve is not expressible under Decision D-2's
within-checkout design; the cross-checkout search that would express it is deferred to FU-4 under
C-011.** The within-checkout search returns *owns it* / *ownership not established* — never an
identified project B. Refuse-on-divergence is therefore the only shape implementable **within this
mission's scope**, and it matches the parent mission's discipline: inability to determine consent is
not consent. *Recorded because the spec contradicted itself*: FU-4's own row already conceded that a
cross-checkout search would make the re-resolve shape "expressible" — a decision recorded on a false
ground invites re-litigation the moment a successor notices the contradiction.
*Falsifier*: the same mapping that falsifies D-2 also makes re-resolve **expressible** — at which
point it must be re-evaluated on its own merits (sending B's identifier to B's team under B's
token is a real design option, not obviously wrong). Additionally, if Q4 is ever reopened toward a
cross-checkout search, an identified project B exists and FR-007's second shape returns to the
table with its own disclosure analysis.
*Consequence recorded so a successor does not re-propose it*: FR-007's falsifier block no longer
admits two shapes. A plan that takes re-resolve would send exactly one request and red both SC-001
and US1-AS1 — and rewriting an acceptance criterion to fit an implementation is how a red-first
proof is lost (debugger finding D-3).

**Decision D-4 — FR-017 splits into a narrow in-mission requirement plus a follow-up issue.**
*Why*: the CI routing gap is **pre-existing**, it affects **both** guards, and keying the fix on
construction-site *locations* generally is materially larger than the spec's original version and
may cost the 5-edit atomic dorny-group registration (F-ENV-6). The in-mission half is
non-negotiable because this mission edits a `SaasClient` construction site
(`cli/commands/decision.py:558`) and would otherwise ship unguarded.
*Falsifier*: **if this mission's final diff touches no `SaasClient` construction site** — for
example if FR-001 lands entirely in a new module and `cli/commands/decision.py` is left unchanged
— the narrow requirement's premise dissolves and FR-017 collapses into the follow-up issue.
Conversely, if a real CI observation on a `cli`-only diff shows the SaaS guard already running,
FR-017 becomes a `[ratchet]`.
*Explicit unverified premise*: architect finding A-1/A-2's chain is a **reading of the workflow
YAML and the dorny/`needs` evaluation model, not a run.** The architect lens asked that it be
confirmed by an actual CI observation on a single-group diff before the plan commits to a fix
shape. That cannot be done pre-implementation — it needs a pushed diff — so it is carried as a
stated premise, not as a measurement.

**Decision D-5 — Q1 loses option (a) (`sync/`); the remaining candidates stay open for the plan.**
*Why*: placing the wrapper in `specify_cli.sync` converts FR-013's operator-actionable refusal into
an `ImportError` at *transport-import time* under module-level caller imports — the transport
cannot be imported in order to be asked, so US2-AS4 becomes unreachable and NFR-004 is answered by
a traceback. That is a structural defect, not a trade-off (architect finding A-3).
*Falsifier*: the mechanism requires a **module-scope** `from specify_cli.sync.<mod> import ...` in
a caller. If the plan can show that every consumer imports the symbol lazily inside a function —
and can pin that with a gate — A-3's mechanism does not fire and `sync/` becomes admissible again.
(Measured so as not to overstate the cost: `sync/__init__.py` defers heavy deps via `__getattr__`
at `:11-12` and its module-level closure is 3 modules, and there is no import cycle. The objection
is about *semantics*, not load time.)

**Decision D-6 — Q6's fallback is struck; `_gate_coverage` is the named mechanism.**
Q6 previously claimed that reading CI filter definitions from a test "is the only mechanism… and
there is no precedent for it in this repository", and offered as a fallback "keep one guard per
package in its existing tree, which makes the routing property hold by construction". **Two lenses
measured the premise false** (debugger finding D-7, architect finding A-6):
`tests/architectural/_gate_coverage.py` already parses `dorny/paths-filter` steps (`:357`,
`:531-533`), builds `filter_groups` (`:476`) and `job_gating_groups` (`:474`, `:612`), enumerates
always-on ungated jobs (`:1539`) and maps `src/specify_cli/<dir>` to its covering dorny glob
(`:1587`); `tests/architectural/test_gate_coverage.py` is its live guard suite. **And the fallback
describes the arrangement that is currently broken** (A-1/A-2). The orchestrator's earlier reading
that the fallback was "likely the right answer" is **retracted**.
*Falsifier*: if `_gate_coverage`'s `filter_groups`/`job_gating_groups` are removed or stop
modelling the dorny filters, the mechanism no longer exists and Q6 must be reopened. The fallback
becomes correct only *after* guard routing is re-keyed on construction-site locations (the D-4
follow-up) — at which point "one guard per package in its existing tree" would hold by
construction rather than by assumption.
*Related invariant, recorded so it is not mistaken for coverage*:
`test_ci_collection_completeness.py:1-16` asserts every collected node is selected by ≥1 job **on
a push to `main`** — and on the push path `github.event_name == 'push'` makes every gate true.
That is exactly why the A-1 gap survives it. The existing invariant is push-path; FR-017 is a
**PR-path** question.

**Operator decision on Q2 — per-caller identifier fragment in a shared template (2026-07-31).**
The shared module owns the sentence template, the four verdict branches,
`UNDETERMINED_PROJECT_REFUSAL`, the `None` guard and the import-failure degradation. **Each
transport passes its own identifier-set fragment as an argument.** Rendered outcome — **both current
`DENIED` strings survive verbatim**: `saas_client` → "…so its **mission and decision identifiers**
must not be transmitted; …"; `tracker` → "…so its **mission and engagement identifiers** must not
be transmitted; …".
*Why the alternatives were rejected, recorded so they are not re-proposed*:
- **Union in one fixed string** — would tell a tracker operator that *decision* identifiers were at
  stake when the tracker cannot transmit one, and the reverse for the SaaS client. **Overstating
  exposure in a confidentiality message is the wrong direction to be wrong**, and it violates
  FR-009's second clause ("implies none it cannot").
- **Superordinate "identifiers"** — never untrue, but drops the specificity that is the point of the
  message. Where `mission_slug` values are client engagement names, *what* would have crossed is the
  operator's actual question.
- **Don't merge (Q1 option (e))** — would have fired falsifier F2 by choice and removed the
  placement work entirely. Not taken.
*Consequences, which close three open items*:
1. **Falsifier F2 does not fire.** The fragment is passed *as an argument*, so the shared module
   never imports from a transport and the neutral-package premise holds. **Q1's option (d) —
   `src/specify_cli/egress/` — stands** and the package may be created.
2. **FR-009 becomes mechanical rather than aesthetic** (closing reviewer finding R-6): there is a
   fixed per-caller set to check against, so the implementer can no longer both pick the wording and
   write the assertion that blesses it.
3. **SC-004 becomes satisfiable at all** (closing reviewer finding N-2): byte-identity moves from
   the *rendered string* to the *non-fragment portion*.
4. **Risk reduction:** the consolidation changes **no** operator-visible text on this branch. The
   `decision`/`engagement` divergence — the only runtime string that differed, and the one nothing
   pins — is preserved rather than resolved. F-A1's "which word survives" question is answered by
   *both do*.
*Still required despite the verbatim preservation*: FR-024/SC-016 stand. The `DENIED` wording is
unpinned today, and "we did not change it" is not a guarantee about the next author. Per
`delete-the-assertion-not-the-test`: **add** pins, do not touch the existing four.
*Falsifier*: **if a future endpoint makes the two transports' identifier sets identical**, the
per-caller fragment becomes ceremony and the union string becomes correct and simpler. Revisit then.
Also: if FR-023's glossary entry cannot be landed, the word "engagement" would have to leave the
tracker fragment, and Q2's rendered outcome changes even though its shape does not.

**Decision on Q8 — "Demonstrated" resolves per criterion, and the rule is stated once (2026-07-31).**
Q8 asked whether SC-005 / SC-006 / SC-008's "Demonstrated" means a standing gate or one-off PR
evidence. **Closed here rather than carried, because three criteria's meaning depends on it**
(reviewer finding R-19; round-2 cut list #6). The rule:

> **Any property that could regress later is a standing gate.** Any *mutation demonstration* — the
> act of breaking something to show the gate discriminates — is **one-off PR evidence**, quoted in
> the mission's evidence at landing time and not preserved as machinery.

*Why split it that way*: a mutation demonstration performed once and not preserved rots immediately
— which is the precise failure FR-019 exists to prevent for the seam. But preserving it as a
standing test means building a synthetic-corpus harness that must itself be maintained and **can
drift from the real guard**, at which point the harness is green and the guard is blind. Keeping the
*property* standing and the *demonstration* one-off gets the discriminating power recorded without
paying for a second copy of the guard. **The per-criterion application is carried by each criterion's
own `[standing]` / `[one-off]` tag in *Success Criteria*** — round 3 deleted the table that restated
it here, because two surfaces for one mapping is the drift shape this rule is itself guarding against.

*Falsifier*: if a standing gate is ever found to be green while the real guard is blind — the drift
failure this rule is trading against — the trade was wrong for that criterion and it should be
re-argued, not silently deleted.

### Requirement-level falsifiers

**FR-001 / FR-002 / FR-004 / FR-007 — ownership before egress.**
*Anti-vacuity*: the test must first demonstrate the bad outcome is reachable. Construct the
divergent case against the pre-fix code path and observe a request being built carrying B's
identifier under A's team; only then assert the fixed path builds none. A test that only asserts
"no request" proves nothing about whether one was ever possible. **Three independent short-circuits
already produce zero requests at `bb2020fea`**, and each one would make a naive SC-001 green with no
production change:
1. **Non-consent** — `_refuse_unless_project_consents` is called at `client.py:181` (and `:157`)
   *before* `url = f"{self._base_url}{path}"` at `:182`. Closed by SC-001's "**consenting** A"
   clause (debugger finding D-1).
2. **Malformed identifier** — a bare ULID regex refuses a slug-shaped id with no ownership logic at
   all. Closed by SC-001's "**well-formed ULID present in B's ledger**" clause (reviewer finding
   R-5).
3. **Unauthenticated fixture** — `SaasClient.from_env` calls `load_auth_context`, which raises
   `SaasAuthError` when no token resolves (`saas_client/auth.py:66-69`); `SaasAuthError` subclasses
   `SaasClientError` (`errors.py:12,24`), which `cmd_widen` catches at
   `cli/commands/decision.py:570`. So a fixture that simply never sets a token sends nothing.
   **No clause of SC-001 closes this one.** What discriminates it is **SC-002's positive control,
   built from the same fixture and in the same module** — if the fixture were unauthenticated,
   SC-002's "exactly one request" would red. Recorded so the red-first order (SC-001 first) is not
   mistaken for evidence (debugger finding DB-2).
*Ledger-completeness assumption, named explicitly*: this design substitutes *"this checkout's
committed `kitty-specs/*/decisions/index.json` lists the decision"* for *"the decision exists"*.
**Those are not the same set**, and the assumption is that the acting checkout's committed ledger is
complete for the decisions it owns. Where it is not, a currently-succeeding invocation becomes a
refusal — see SC-002.
*Falsifier*: as Decision D-2 above.

**FR-003 — the slug becomes load-bearing.**
*Anti-vacuity*: "load-bearing" is not an observable; printing the slug satisfies a literal reading.
The differential in the requirement text is the assertion (reviewer finding R-13).
*Falsifier*: if the plan finds no caller ever passes `--mission-slug` on the live path, FR-003's
value is confined to the operator-typo case and it may be demoted — but the flag must then be
rejected rather than silently ignored, because silently ignoring it is the current defect.

**FR-005 — shape check before URL interpolation.**
*Status*: **defence-in-depth. It does not discharge FR-001 or FR-002.**
*Precondition being closed*: the recorded precondition "if that endpoint ever accepts a slug, the
entry stops being benign" is **already satisfied today** — not because the server accepts a slug,
but because the client transmits whatever the operator types, in the request line, before the
server has any say. Server acceptance controls the effect; the client controls the disclosure.
*Anti-vacuity*: assert on the constructed request line, not on the response. A 404 is not evidence
of non-disclosure.
*Falsifier*: if the endpoint family's documented contract ("ULID **or** slug") is ever made
authoritative for widen specifically, a hard ULID check becomes wrong and must be replaced by
ownership resolution alone.

**FR-006 / FR-021 — the four routes and the containment check.**
*How you would know the fourth route is real*: `resolve_feature_dir_for_mission`
(`missions/_read_path_resolver.py:1608-1631`) delegates to
`mission_runtime.resolve_action_context(feature=mission_slug, cwd=cwd, env=env)` — a topology-aware
selector — and returns `Path(context.feature_dir)` with **no assertion that the result lies under
`repo_root`**. The lens that found this was explicit that it did **not** prove a traversal is
reachable; it reports an *unconstrained seam*, not a measured leak, and that distinction is kept.
The cost of closing it is one `Path.is_relative_to` check, or not using the function at all.
*Anti-vacuity, and it differs by discharge* (reviewer finding N-4): under (i) the containment test
must construct a case where the resolver would otherwise return a path outside `repo_root` and show
the check firing — a test that only calls the happy path proves nothing. Under (ii) that case cannot
be constructed, so "no test, because the case can't happen" is **not** a discharge; the substitute
is the enumeration equality at SC-018.
*The glob path is a second, separate hole* (reviewer finding N-5): containment covers the **slug**
path only. `Path.glob` follows a symlinked mission directory and `Path.is_relative_to` on the
**unresolved** result returns `True`. Measured: **0 symlinks under `kitty-specs/` today** — a
**shape assumption, not a live leak**, which is exactly why it must be written down rather than
relied on. Obligations at SC-018.

**FR-008 / FR-009 — one presentation, one wording.**
*Falsifier of the premise*: the issue implies substantial duplication. Measurement says one runtime
string and five comment hunks. If the plan finds the extraction costs more structure than the
duplication costs, "keep two modules and pin their equivalence with a gate" is a legitimate answer
to the same requirement (Q1, option (e)) — which is why FR-008 is stated outcome-first.
*Anti-vacuity for FR-009*: a message can be vacuously true of a transport that carries none of the
named identifier kinds. The test must assert coverage in **both** directions against the
**enumerated sets in Key Entities** — for each transport, every identifier kind it *can* transmit is
named, **and no kind from the other transport's set appears** — not merely that the string is not
false. Under Q2 both halves are checkable because the fragment is per-caller; before Q2 they were
jointly unsatisfiable alongside whole-string byte-identity (reviewer finding N-2).
*What Q2 did and did not settle*: it settled the **shape** (template + per-caller fragment) and the
**rendered text** (both current `DENIED` strings verbatim). It did **not** make FR-008 vacuous — the
template, the four verdict branches and `UNDETERMINED_PROJECT_REFUSAL` still have to end up with
exactly one editable presentation, and SC-015 is what asserts that. A "consolidation" that leaves
two templates and merely parameterises them is not FR-008.

**FR-010 / FR-024 — pinned text.**
*How you would know FR-010 would otherwise have broken*: four assertions in two test files target
the substring `could not be determined`. They are the only text assertions on this surface anywhere
in the repo. So the shared substring is pinned and **the divergent string is not** — consolidation
cannot break a text gate by accident, only by touching that substring.
*Why that is a weakness, not a comfort*: the substring occurs in **two** branches
(`saas_client/egress_consent.py:86` and `:138`; `tracker/egress_consent.py:141` and `:201` —
orchestrator correction C-1), so the four assertions cannot distinguish `UNDETERMINED` from
`UNANSWERABLE`, and a consolidation merging those two branches would stay green while collapsing a
distinction the source explicitly says must not collapse (`tracker/egress_consent.py:136-139`).
NFR-004 carries that, and FR-024 pins the branch that actually changes.

**FR-011 — unexported constant.**
*How you would know*: the dead-symbol gate requires every `__all__` name to have a non-test `src/`
importer, and explicitly does not count tests as callers. The constant has zero external consumers.
Adding it to `__all__` reds immediately — so this requirement is self-enforcing, and it stays
self-enforcing under Q1 option (d) because the gate walks every `*.py` under `src/`.

**FR-014 — per-class floor.**
*How you would know the coverage loss would otherwise be silent*: today's non-vacuity assertion is
`assert scanned` on a single global integer. It is per-package only because there is one guard per
package. Merge into one parametrised scanner accumulating into one counter, then drop or rename one
transport class, and the counter stays positive from the other class — green, with half the
construction sites unscanned.
***Stated limit — this must be in the plan, not discovered by a reviewer.*** **The floor is
necessary and not sufficient, and the guard is syntactic by construction.** FR-014–FR-017 and
NFR-003 make the guard harder to render *vacuous*; **none of them moves it from "a root was
passed" to "the owning root was passed"** (paula finding P-5). The guard's own docstring concedes
this verbatim at `test_client_consent_gate_3030.py:312-315`. A reviewer reading FR-014–FR-017 plus
SC-005/SC-007 would reasonably conclude ownership is now guarded. It is not — FR-001 guards
ownership, at one call site, and FR-026 exists because the prose carrying the old correctness
argument is stale.

**FR-015 / FR-016 — attribution vocabulary and match predicates.**
*Direction matters*: narrowing is loud (it flags real call sites immediately). Widening is silent —
and, critically, **invisible to every count**, because `scanned += 1` runs before the attribution
test in both guards. The tests must therefore prove the *rejection* (FR-015) and the *match on an
unused shape* (FR-016) directly. Measured: all three tracker construction sites are bare
`ast.Name` callees, so unifying on the SaaS guard's stricter predicate leaves the tracker count
sitting **exactly at its floor** while blinding the guard to `mod.SaaSTrackerClient(...)`
(debugger finding D-5).
*The unused-shape assertion exists per class, and the two classes reach it through different shapes*
(reviewer finding N-3 / debugger finding P-1 in round 2; **corrected in round 3**). The probed
shapes and their measured results:

```
mod.SaaSTrackerClient(project_root=r)   -> tracker guard  MATCHED / attributed   (already true; unused by any src/ site)
SaasClient(project_root=r)              -> SaaS guard     MATCHED / attributed   (already true; corpus is direct=0, from_env=4)
mod.SaasClient(project_root=r)          -> SaaS guard     NOT MATCHED            (excluded BY DESIGN, FR-016)
mod.SaasClient.from_env(r)              -> BOTH guards    NOT MATCHED            (unguarded; named by no requirement — FU-8)
```

⇒ **SC-013 asserts a *match* for each class**, on that class's own unused-but-matching shape.
**No non-match is asserted for either class**: the round-2 proposal to pin `mod.SaasClient(...)` as
a must-not-match was **withdrawn in round 3 on measurement** and must not be reintroduced — the
grounds are stated once, at SC-013. This block exists to hold the measurement, not the reasoning.

**FR-017 — CI routing.**
*How you would know*: see Decision D-4 above, including its explicit unverified premise.
*Safe direction*: a brand-new `src/specify_cli/<x>/` matches no named filter group and falls
through to `run_all` — a loud alarm by design, not a gap.

**FR-018 / FR-019 — the seam (Decision D-1).**
The orchestrator has decided: **keep** `register_saas_client_factory`, and pin its export. The
option set is **four**, not three (architect finding A-8 — the orchestrator's original (c) bundled
two separable deletions):
- **(a) Keep the whole seam** — chosen.
- **(b) Delete only the registrar** — dominated: it removes the only mechanism by which the getter
  could ever become meaningful, while keeping the getter and its consumer, converting a *usable*
  empty seam into a *permanently* dead branch. *(Note the corrected reasoning: the getter already
  can never return non-`None` today — `propagator.py:64-72` says so in source. The original ground
  for dismissing (b) was therefore also true of (a) and did not distinguish them.)*
- **(c) Delete `register`, `get`, and the propagator's egress branch** — rejected on scope: it
  edits the gated egress path `#3030` hardened, outside "one wrapper, one shape".
- **(d) Delete `register` and `get`, keep the propagator's consent gate and the recorded
  `request_text` refusal** — *recorded and dismissed*: it preserves the refusal's record in a more
  discoverable place but still edits `propagator.py`, so it loses ground 1 (scope) while (a) keeps
  both grounds.
*Ground strength, recorded so it is not over-quoted*: ground 2 ("keeping the empty slot keeps the
consent gate in front of it") is the **weakest** — nothing makes a future author find a seam with
no production caller (orchestrator correction C-3). FR-022's ADR is what gives the refusal a
durable home; once it exists, ground 2 weakens honestly while ground 1 (scope) and ground 3
(absence is already pinned) still hold, and a future mission gains a clean falsifier for deleting
the seam. **Strictly better end state.**
*Falsifiers of D-1, any one of which reopens it*:
- The propagator's egress branch is removed, leaving `get_saas_client` with no production reader.
  The read side dies too, and deleting the whole seam becomes correct.
- A real transport is registered. The existing absence pin reds by design; that is the moment to
  prove the propagator's consent gate holds against the new transport *before* landing it.
- The repository adopts a policy that empty seams must not exist regardless of read-side liveness.
  Then D-1's second ground is overridden by policy.

**SC-004's rot-mode-5 clause** *(formerly FR-025/SC-017, retired in round 2; converted from a
reporting instruction to a **binding-identity assertion** in round 3)*.
*How you would know*: `saas_client/client.py:23` and `tracker/saas_client.py:34` both do
`from … import project_egress_refusal` at module scope — a by-value binding, with the decisions at
`client.py:157` and `tracker/saas_client.py:329`. Patching the shared module after consolidation
leaves both deciding modules inert. **C-004 does not prevent the collapse route either**: the
seam-allowance gate only requires the literal `project_egress_refusal` in `tracker/saas_client.py`,
and the import line at `:34` already satisfies it.
*Anti-vacuity*: a **sameness** is the friction doc's explicitly flagged suspect kind
(`tracer-tooling-friction.md:468-478`), and round 3 measured that no text comparison available under
Q2 discriminates — a surviving re-export renders the identical correct string. **Identity, not text,
is the assertion**: `is` comparisons over the three names. Stated once, at SC-004 clause 3.
*Why it is unconditional*: as FR-025 it read "*any test that* patches or mutates…" — a conditional
over a set the implementer controls. The spec had already caught and fixed this exact shape for
NFR-005/SC-009 ("evidence must state the count and the file list") and did not carry the fix across
(reviewer finding N-6 / debugger finding P-2, converged). The hazard belongs to the
**consolidation**, so the obligation attaches to it: SC-004 clause 3 runs every time, over three
named bindings, always.

**C-005 — classification of a new home.**
*How you would know the hole is real*: the integration-boundary scan classifies files by an
explicit list of CORE directories and matches imports against an explicit list of INTEGRATION
prefixes. A package in neither list is invisible to it in both directions. The laundering path is
mechanical, not hypothetical — nine CORE modules already reach `sync` transitively today. Closing
this instance is a one-line addition, but nothing currently fails if it is forgotten, and the
package's ~150–250 LOC lands under `T_LOC = 500`, so the LOC-gated coverage detector does not fire
either.

**C-006 — Bundle A.**
*Falsifier / recheck*: `grep addopts pytest.ini`. If the line still reads exactly
`addopts = --tb=short`, the global-timeout gap is still open and a hung suite consumes the run
instead of failing it. Re-measure `#3113` and `#3115` at plan time rather than inheriting this
spec's snapshot. `#3113`'s specific check: `sed -n '/def _transmits_a_body/,/^def /p'
tests/architectural/test_egress_consent_boundary.py` — if the body still derives `kwargs` solely
from `node.keywords`, it is not fixed.

**C-010 — fabricated consent.**
*How you would know*: read `tests/specify_cli/saas_client/conftest.py:51,74` and
`tests/sync/tracker/conftest.py:55,166`. Both fixtures are **autouse**. The in-file positive
control is what distinguishes "A's consent was honoured" from "A's consent was never consulted".

---

## Dependency on Bundle A

Both Bundle A issues were measured OPEN on 2026-07-31. Naming exactly which verification they
touch, so a successor does not treat a green or a red as more informative than it is:

| Bundle A item | State | Which requirements' verification it affects | Effect |
|---|---|---|---|
| `#3113` — egress guard positional-call blind spot | OPEN | **The egress-consent *boundary* guard only** (`test_egress_consent_boundary.py`) | `_transmits_a_body` (`:295-306`) reads `node.keywords` only, never `node.args`, so a fully positional `poster(url, data, headers)` is not classified as a sink at all. **Narrowed per reviewer finding R-12 / debugger finding D-10, correcting an over-application of F-ENV-5**: the two **attribution** guards match by class name and count every match regardless of call form — `SaasClient.from_env(root)` positional is counted *and* treated attributed via `bool(node.args)`; `SaaSTrackerClient(root)` positional is counted *and* flagged unattributed, loudly. **They have no positional blind spot.** Leaving the wider attribution would hand a successor a ready-made excuse ("my coverage claim is bounded by `#3113`") for a claim that is not in fact bounded. |
| **Not a Bundle A item — a distinct hole, named separately** | — | NFR-003, FR-014–FR-016 *(and the retired NFR-001, whose bound NFR-003 now carries)* | The attribution guards match a **literal class name**: `ast.Name(id="SaasClient")` / `from_env` on a `Name("SaasClient")` receiver (`test_client_consent_gate_3030.py:330-337`) and `name != "SaaSTrackerClient"` (`test_saas_client_consent_gate_3030.py:381-384`). **An aliased import, a factory, or a transport injected as a parameter is invisible**, so "count unchanged or lower" is satisfiable while a new egress surface is added. This is a different scan with a different hole from `#3113`'s and must not be credited to it. |
| `#3115` — shard-parallel test isolation | OPEN | Every requirement whose evidence is a CI run; FR-017 most directly, since its evidence *is* a CI job-selection observation | Full-suite CI reds on this mission's surface are not reliably attributable. NFR-005 exists to compensate: each new or changed test must also pass as an isolated single-file run, with the count and file list stated. |
| Global pytest timeout gap (`pytest.ini` carries no `--timeout`) | OPEN | All | A hang is not a measurement. Any plan that budgets "run the suite" must account for a hang consuming the run rather than failing it, and for a large fixed per-invocation collection cost (a single trivial test measured 69 s wall-clock, essentially all collection). |

Additionally, a **local environment hazard** that is not Bundle A's but has the same effect on
measurement: a user-site editable install makes a bare `python3 -c "import specify_cli"` resolve to
a *different checkout* that is concurrently being edited. `pytest` from this clone's root is safe
(measured — `pytest.ini` sets `pythonpath = src`, inserted ahead of the user-site `.pth`);
everything else must set `PYTHONPATH` to this clone's `src` explicitly. This applies to the
NFR-006 `uv venv --python 3.11` run.

---

## Open design questions

Recorded rather than resolved. The plan phase owns what is still open. **Q4 and Q6 closed in
round 1** (Decisions D-2 and D-6); **Q2 and Q8 closed in round 2**; **Q1, Q5 and Q7 were resolved by
the plan phase** and are recorded here so the spec and the plan do not disagree. Each is retained
with its resolution and its falsifier so a successor does not reopen it blind. **Q3 remains open.**

**Q1 — Where does the shared wrapper live? — RESOLVED by the plan phase: option (d),
`src/specify_cli/egress/`,** with two mandatory one-line accompaniments (neither is F-ENV-6's
5-edit atomic new-group registration): `"specify_cli.egress"` added to `INTEGRATION_PREFIXES`
(C-005, asserted by **SC-025**), and `'src/specify_cli/egress/**'` added to the **existing**
`core_misc` glob. *Trade-off accepted plainly*: a new package for one function and one constant,
plus two edits that no pre-existing gate would notice if forgotten (~150–250 LOC against
`T_LOC = 500`). *Falsifiers*: **F1** — if `specify_cli.delivery` ever enters
`INTEGRATION_PREFIXES`, option (f) becomes genuinely classified at zero marginal cost and Q1 should
revisit toward it. **F2** — if the merged wrapper could not be written without importing from a
transport, the neutral premise would be false and (e) would be the honest answer; **F2 does not
fire**, because the operator's Q2 decision passes each transport's identifier fragment *as an
argument*, so the shared module imports from neither transport.

The candidate table is retained below because the falsifiers reference it. Two of its cells were
**measured wrong** and are corrected in place — recorded rather than silently deleted, because both
errors were arguments *for* the option that won. Also recorded up front, because it remains the
reason the choice was free rather than forced: **the
constraint set is not over-determined — every remaining candidate is legal.** C-004 is a
*substring* test and `tracker/saas_client.py` contains the literal at two independent places;
C-001 excludes only the four CORE dirs; C-005 is a one-line `INTEGRATION_PREFIXES` addition needing
no second edit. Candidates and their trade-offs:

| Candidate | For | Against |
|---|---|---|
| ~~(a) `src/specify_cli/sync/`~~ **ELIMINATED (Decision D-5)** | — | A module-scope `from specify_cli.sync.<mod> import project_egress_refusal` forces `specify_cli/sync/__init__.py` to execute first; an unimportable sync package then raises `ImportError` at *transport-import time*, so the transport cannot be imported in order to be asked. FR-013's operator-actionable refusal becomes a traceback and US2-AS4 is unreachable. Structural defect, not a trade-off. |
| (b) `src/specify_cli/saas_client/`, imported by `tracker/` | No new package; both are INTEGRATION so the import is legal. | Implies the SaaS client owns the tracker's refusal. Creates a tracker→saas_client edge that did not exist. |
| (c) `src/specify_cli/tracker/`, imported by `saas_client/` | Symmetric to (b); the seam-symbol constraint (C-004) already anchors a name in the tracker tree. | Same objection as (b) with the roles swapped. |
| **(d) A new `src/specify_cli/egress/`** — **CHOSEN** | Neutral; owned by neither transport. Matches no CI filter group so it routes to `run_all`, a loud default. ~~The **only** candidate that preserves FR-013 under module-level caller imports (architect finding A-3).~~ **CORRECTED — this cell was false.** The plan measured the module-level import closure of every surviving candidate (controls: `saas_client`/`tracker` must be NO because FR-013 works today; a known column-0 sync importer must be YES) and found **only `sync/` reaches `specify_cli.sync` at module level**. ⇒ **FR-013 eliminates option (a) and discriminates nothing else.** A-3's elimination of (a) stands (Decision D-5 is unaffected); A-3's "only candidate" clause is **overturned by measurement** and must not be re-raised as an argument for (d). (d) was re-justified on the other grounds in this row. | Must be classified (C-005) or it becomes the tenth CORE→sync laundering route — **and no pre-existing gate notices if the classification is forgotten**, because ~150–250 LOC is under `T_LOC = 500` (debugger finding D-8). SC-025 is the assertion that notices. Adds a package for one function and one constant. |
| (e) No shared module — keep both files and pin their equivalence with a gate | Honest to the measurement: the duplication is one runtime string. Preserves guard independence trivially. Zero layering risk. Satisfies FR-008 as restated (one *editable presentation*, enforced by the gate). | The gate becomes the thing that must not drift, and a text-equality gate is brittle against legitimate per-caller wording. |
| **(f) `src/specify_cli/delivery/`** *(restored — architect finding A-10; the orchestrator's own F-A4 named it and Q1 had silently dropped it)* | Measured: `src/specify_cli/delivery/**` is in the `core_misc` filter group (`ci-quality.yml:273`), routing to `fast-tests-core-misc` / `integration-tests-core-misc` — **the same jobs that already run the SaaS guard, a stronger routing position than (d)'s `run_all`-by-accident.** ~~Already classified, so no C-005 edit.~~ **CORRECTED — this cell conflated two senses of "classified."** `delivery/**` **is** in the `core_misc` **dorny filter group**, but `specify_cli.delivery` is **not** in the integration-boundary gate's **`INTEGRATION_PREFIXES`**. Architect finding A-10 stated this correctly; the conflation entered when it was transcribed into this table. **In C-005's sense `delivery/` is unclassified**, so option (f) carries D-8's gap too — it does not avoid it. Filed as FU-7. `delivery/` is also where `ConsentedBatch` lives, i.e. where the provenance invariant is already expressed. | `delivery` already imports `specify_cli.sync`, so it carries the same transitive-reach exposure as (d) — **and, per the correction opposite, without C-005 binding it either**, which means the exposure is unrecorded rather than absent. Puts a transport-presentation concern in the delivery package. |

**Q2 — Which wording survives? — RESOLVED by the operator, 2026-07-31: a per-caller identifier
fragment injected into a shared template.** Exactly one runtime string diverged (`decision` vs
`engagement` identifiers) and no test pinned either. The union string and the superordinate
"identifiers" were both rejected; **both current `DENIED` strings survive verbatim**. The full
record — why each alternative was rejected, the four consequences, and Q2's own falsifier — is in
"Operator decision on Q2" under *Falsifiers and preconditions*. Consequences carried into the
requirements: FR-009 (mechanical, per-caller, both directions), SC-004 (byte-identity of the
**non-fragment portion** only), Q1 falsifier F2 (does not fire, so option (d) stands).
**FR-023 is now mandatory, not conditional**: the answer keeps the word "engagement" in
operator-facing text, so the glossary entry must land.

**Q3 — Does the seam become uuid-typed?** The consent chain would accept a `project_uuid` and is
uuid-primary; the seam above it is path-typed end to end. `#3111` can be fixed *without* touching
the seam. **Framing 3 above is the reason this is optional rather than indicated**: the invariant
is about provenance, not type, and uuid-typing the seam would not make the substitutions
inexpressible. Under C-011 a uuid-typed seam defers to a follow-up issue if the plan concludes it
is required.

**Q4 — What is the contract of `--mission-slug` after this? — RESOLVED (Decision D-2).**
**Optional, with a within-checkout search.** Neither of the two options this question originally
offered is taken: the slug is not made mandatory (no compatibility break on a hidden
automation-facing command, and SC-002 stays true), and no cross-checkout enumeration is performed
(no new disclosure surface). When supplied, the slug **narrows** the search over the acting
checkout's own missions and is verified, never trusted. When omitted, the glob answers the question
on its own. The residual sub-question — *is a slug that disagrees with the checkout an error or an
instruction?* — is answered by C-009: it can only be an ownership failure, because there is no
"elsewhere" this design can address.

**Q5 — Does `--dry-run` participate? — RESOLVED by the plan phase: dry-run *warns* but does not
refuse.** It transmits nothing, so it is not an egress path; but it is the path an operator uses to
*check* an invocation, and a dry-run that renders the endpoint without flagging a mismatch is a
trap. Warning-without-refusing keeps the inspection value at the cost of a second code path.
*Falsifier*: if dry-run ever gains a side effect that leaves the machine — telemetry, a log shipped
off-host — it stops being a non-egress path and must refuse like the live path.

**Q6 — How is FR-017 asserted? — RESOLVED (Decision D-6).** By reading the workflow's filter
definitions from a test, using `tests/architectural/_gate_coverage.py`'s `filter_groups` and
`job_gating_groups`, which already do exactly this and are already guarded by
`tests/architectural/test_gate_coverage.py`. The question's "no precedent" premise was measured
false by two lenses, and its fallback ("keep one guard per package in its existing tree, which
makes the routing property hold by construction") **is struck** — that arrangement is the one that
is currently broken.

**Q7 — Is the ULID check the right shape for FR-005? — RESOLVED by the plan phase: exactly one
check, at the CLI boundary, reusing an existing ULID regex.** ULID regexes exist in at least three
other modules (`decisions/verify.py:40`, `invocation/record.py:30`, `context/mission_resolver.py:55`)
and **none guards this argument**. Adding a fourth at the CLI and a fifth in the client would make
five spellings of one shape check — this mission's own whack-a-field (paula finding P-10). One
check, at the boundary where the value's provenance changes from keyboard to store, reusing an
existing regex rather than writing a fourth. *Falsifier*: if the widen endpoint's documented
contract ("ULID **or** slug") is ever made authoritative for widen specifically, a hard ULID check
becomes wrong and must be replaced by ownership resolution alone (FR-005's own falsifier).

**Q8 — Is "Demonstrated" in SC-005 / SC-006 / SC-008 a standing gate or one-off PR evidence? —
RESOLVED in round 2** (reviewer finding R-19; carried in round 1, closed here because three
criteria's meaning depends on it and a carried question is not a resolution). **The rule: any
property that could regress later is a standing gate; any mutation demonstration is one-off PR
evidence.** The full statement, the reasoning for the split and its falsifier are in "Decision on
Q8" under *Falsifiers and preconditions*. **The per-criterion application lives in one place only:
each affected criterion's own **[standing]** / **[one-off]** tag** — the restating table was deleted
in round 3 as redundant with those tags.

**Q3 is the only question still open.** It is a design option, not a gap: `#3111` can be fixed
without touching the seam's type, and under C-011 a uuid-typed seam defers to FU-5 if the plan
concludes it is required.

---

## Out of scope, and why

Stated so a successor does not re-open them. Items that generate a **follow-up issue** are listed
again in the next section with their falsifiers.

- **Re-doing the `#3109` phantom-reader deletion (that mission's requirement 032).** It has already
  landed at `bb2020fea`. The only residual
  was keep-or-delete `register_saas_client_factory`, and that is decided (D-1): keep and pin.
- **Removing the propagator's egress branch.** Options (c) and (d) of the D-1 analysis; both
  rejected on scope. A future mission may take them — the falsifiers for D-1 above say exactly when.
- **Extending the `ConsentedBatch` pattern to the `saas_client` and `tracker` transports** — making
  `_get`/`_post`/`_request` refuse a bare path attribution and require a value that cannot be
  constructed without a data-derived consent answer. This is the structurally correct end state
  implied by framing 3, and it is explicitly **not** this mission. Seven construction sites across
  four dorny CI groups. Follow-up issue.
- **The nine pre-existing CORE→`sync` transitive reaches.** Needs a transitive-reach scan, which is
  a separate mission. C-005 is restated as "do not add a tenth". Follow-up issue.
- **Re-keying guard routing on construction-site locations generally** (including the tracker
  guard's `tests/sync/` placement). Decision D-4. Follow-up issue.
- **Anything touching E20 / operator-configured tracker connectors.** Recorded by the parent
  mission as an open collection surface under its C-006. Real, and a different mission — it needs a
  consent representation that does not exist yet, not a refusal wrapper.
- **Adding a project-identity column to the decision ledger, or a decision-owner endpoint on the
  server.** The entry schema is frozen with `extra="forbid"`, so this is a migration touching every
  existing ledger, and the server side is a separate repository's contract. Positional ownership is
  sufficient for `#3111` and does not require either. *(If it ever lands, it falsifies Decisions
  D-2 and D-3 — see their falsifiers.)*
- **Adopting import-linter.** There is no import-linter configuration in this repository; the
  layering gates are pytest files. Introducing a second enforcement mechanism is not this mission's
  job.
- **Renaming `project_egress_refusal`.** Forbidden by C-004 in the tracker file specifically, and
  gratuitous elsewhere.
- **Fixing the `pytest.ini` global-timeout gap.** Belongs with Bundle A's test-infrastructure work.
  Recorded here only as a verification hazard (C-006).
- **Changing the registry indirection through `invocation.adapters`.** It is a C-003 choice
  recorded verbatim in source, not an accident of layering.

---

## Follow-up issues

Everything the adjudication carries as out-of-scope, written where a successor will find it. Each
carries a one-line rationale and, where the squad supplied one, its own falsifier.

| # | Issue to file | Rationale | Falsifier for the issue itself |
|---|---|---|---|
| FU-1 | **Re-key attribution-guard CI routing on construction-site locations.** For every source directory containing a scanned construction site, a diff confined to that directory must select a job that collects the guard covering that class. Derive the directory set from the guards' own scan. Covers the tracker guard's `tests/sync/` placement (architect finding A-1) and any future site migration. | The gap is **pre-existing**, affects both guards, and is materially larger than this mission's narrow FR-017 — it may cost the 5-edit atomic dorny-group registration (F-ENV-6). Decision D-4. | If a real CI observation on a single-group diff shows both guards already running, the premise is false and the issue closes. The YAML-reading chain is a reading, not a run. |
| FU-2 | **Extend the `ConsentedBatch` pattern to the `saas_client` and `tracker` transports.** `_get`/`_post`/`_request` stop accepting a bare path attribution and accept a value that cannot be constructed without a data-derived consent answer. | This is what framing 3 (provenance, not type) actually implies structurally; a refusal wrapper does not deliver it. Seven construction sites across four dorny CI groups. | **If a `decision_id`→project mapping ever lands**, the positional derivation stops being the only option and the design is revisited. |
| FU-3 | **Scan for CORE modules transitively reaching `specify_cli.sync` through unclassified packages.** Nine exist today, all green under the integration-boundary gate; hand-verified chain: `status/aggregate.py:620 → coordination.status_transition:288 → git.commit_helpers:1148 → sync.local_commit`. | The boundary gate matches import prefixes **per file** and knows nothing of transitive reach. C-005 prevents a tenth; it closes nothing. | If the integration-boundary gate ever gains transitive-closure analysis, the issue is subsumed. |
| FU-4 | **Cross-checkout ownership search**, if it is ever wanted. Not needed for `#3111` under Decision D-2. | Would enable naming the actual owning project (making US1-AS1's original strong form and FR-007's re-resolve shape expressible), at the cost of a new disclosure surface: it reveals which projects exist on the machine to the logic. | Only worth revisiting if the weakened AS1 error message proves insufficient in practice, or if a mapping lands and makes the search unnecessary. |
| FU-5 | **Uuid-typed egress-consent seam** (`resolve_egress_consent` / `project_egress_refusal` signatures), if the plan concludes it is required. | Deferred by C-011: comparable in size to the entire `#3110` half, and framing 3 says a type cannot express provenance anyway. | If a future site is found where the path-typed seam makes the *correct* attribution inexpressible, the type change earns its cost. |
| FU-6 | **Global `pytest` timeout in `pytest.ini`.** | Bundle A's test-infrastructure surface; recorded here only because a hang consumes this mission's runs rather than failing them. | `grep addopts pytest.ini` no longer reads exactly `addopts = --tb=short`. |
| FU-7 | **Classify `specify_cli.delivery` in `INTEGRATION_PREFIXES`.** `delivery/**` is in the `core_misc` **dorny filter group** but `specify_cli.delivery` is **not** in the integration-boundary gate's INTEGRATION prefixes — two different senses of "classified", conflated in this spec's Q1 table until round 2. | `delivery/` already imports `specify_cli.sync`, so it carries the same unrecorded transitive-reach exposure C-005 exists to record for a new package. One line, same shape as C-005's edit. | Landing it fires Q1's falsifier **F1**: option (f) becomes genuinely classified at zero marginal cost and Q1's placement choice should be revisited toward it. |
| FU-8 | **Guard `mod.SaasClient.from_env(...)`,** which is matched by **neither** attribution guard today and is named by no requirement in this spec (measured, round 2). | Not a regression this mission introduces, and closing it means widening a predicate — the silent direction FR-015/FR-016 forbid inside this mission's blast radius. It needs its own analysis of what widening costs. | If a `src/` site of that shape ever lands, the hole stops being theoretical and the issue becomes urgent rather than latent. |

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Running `spec-kitty agent decision widen` from a **consenting** checkout A that does
  **not** own the named decision — where the `decision_id` is a **well-formed ULID that is present
  in project B's ledger and absent from every mission under A** — produces **zero outbound HTTP
  requests**, over **two** divergence routes: the operator-supplied **`--mission-slug`** route, and
  **one** root-shaped route (`SPECIFY_REPO_ROOT`, per US1-AS3).
  *Why two and not four* (round-2 cut, debugger's own over-correction list): FR-006 itself concedes
  that the three root-shaped routes — cwd, `SPECIFY_REPO_ROOT`, and the `or Path.cwd()` fallback —
  **converge in `locate_project_root` and hold by construction**. Three parameterisations of one
  code path is one piece of evidence, not three, and "100% of four routes" bought coverage
  arithmetic rather than discriminating power. The remaining two are genuinely different code: the
  slug route is **new with FR-003** and is slug-shaped, not root-shaped. **The other two root routes
  are held by construction at the named convergence point, `locate_project_root`** — if a future
  change makes any of them stop converging there, this reduction is wrong and SC-001 must go back to
  four.
  *Why every clause is load-bearing*: without "consenting", the criterion is vacuously passable at
  `bb2020fea` with zero production change, because a non-consenting checkout already sends nothing
  (debugger finding D-1). Without "well-formed ULID present in B's ledger", a bare regex satisfies
  it with no ownership logic at all (reviewer finding R-5). **And a third short-circuit no clause of
  SC-001 closes**: an unauthenticated fixture also sends nothing at `bb2020fea`
  (`saas_client/auth.py:66-69` → `errors.py:12,24` → caught at `decision.py:570`). **SC-002's
  positive control is what discriminates it** — see SC-002 and the FR-001 falsifier block. A green
  SC-001 alone is therefore *not* evidence that the fix works; the pair is.
- **SC-002**: **In the same test module, built from the same fixture as SC-001**, the same command
  run from the checkout that *does* own the decision is unchanged: same endpoint, same payload,
  exactly one request. This is SC-001's positive control, not a co-listed sibling — co-listing lets
  an implementer satisfy each from a different arrangement.
  *It is also SC-001's **auth** control*: if the shared fixture were unauthenticated, SC-002's
  "exactly one request" reds. That is the only thing in the spec that discriminates SC-001's third
  short-circuit (debugger finding DB-2), which is why the shared-module/shared-fixture wording is
  not decoration.

  *Compatibility clause — restated in round 2, because the round-1 version was scoped entirely to
  `--mission-slug` and the breaks are not all flag-driven* (debugger finding DB-1, subsuming
  reviewer finding N-1):

  **(a) The ledger-completeness assumption, named.** This design substitutes *"this checkout's
  committed `kitty-specs/*/decisions/index.json` lists the decision"* for *"the decision exists"*.
  **Those are not the same set.** At `bb2020fea` `cmd_widen` reads **no** ledger
  (`cli/commands/decision.py:523-572`), so **every ULID the server accepts succeeds today**. After
  FR-001/FR-002, these currently-succeeding invocations become refusals with zero requests:
  a decision recorded on another machine or branch, **pushed but not yet pulled here** — which is
  also the lane-worktree case, because `locate_project_root` returns the **main** repo root even
  when invoked from a worktree (`core/paths.py:184-186`, and its docstring says so), so FR-001's
  glob reads the main checkout's `kitty-specs/` and "a lane worktree cut before the ledger entry
  landed" is not a separate break; and any checkout where `kitty-specs/` is filtered,
  sparse-checked-out or cleaned. **SC-002 does not claim these keep working. It claims they refuse
  loudly and for a stated reason.** *(Merged in round 3, reviewer finding RM-3 — the two bullets
  were one case, and the `locate_project_root` behaviour is named here so a successor does not chase
  a break that does not exist.)*

  **(b) A stale or absent entry refuses.** The refusal must name the acting root, the missions
  searched, and the operator action: **`git pull` (or otherwise restore `kitty-specs/`), then
  retry.** Silence here is what makes the fall-through look reasonable.

  **(c) The malformed-ledger scoping rule — two-sided, and *both* sides are asserted** (reviewer
  finding N-1; the second side added in round 3, debugger MEDIUM). An unreadable ledger in a mission
  that is **not** the answer must **not** veto a positive membership hit elsewhere; it may be warned
  about. **Refusal is correct only when the search terminates with no positive hit AND at least one
  ledger was unreadable.** The missing / malformed / unreadable behaviours of `load_index` are
  measurably different and must not be lumped — **stated once, in *Edge Cases***.

  - **The refuse half** — no positive hit, at least one unreadable ledger ⇒ refuse — is asserted by
    SC-014's unreadable-ledger test.
  - **The must-not-veto half** — **and nothing asserted it until round 3**: a test must construct
    **an unreadable ledger under mission X together with a positive membership hit under mission
    Y**, and assert the invocation produces **the normal single request** (same endpoint, same
    payload), **not a refusal**. Without this case, an implementation that refuses on *any*
    unreadable index passes every other criterion in this spec while breaking widen invocations that
    succeed today because of one corrupt `index.json` in an unrelated mission — measured: 49 ledgers
    across 333 mission dirs in this repository, so an unrelated corrupt file is not theoretical. It
    is also **the one fall-through variant SC-001 does not catch**, because no request carrying B's
    identifier is involved.

  **(d) The forbidden repair, stated in the criterion itself.** An implementer meeting a mid-flight
  SC-002 red has an obvious fix — *"fall through to the acting root when the ledger doesn't list
  it"* — **which reinstates exactly the leak this mission closes.** It is forbidden. If SC-002 reds,
  the admissible responses are: restore the ledger, narrow with `--mission-slug`, fix the scoping
  rule in (c), or record the case as an intended behaviour change. Never a fall-through. **The
  danger in this criterion is not the break; it is the repair.**

  **(e) The one deliberate flag-driven exception is FR-003's differential**: an invocation that today
  succeeds *while passing a slug that disagrees with the record* succeeds only because the flag is
  silently ignored on the live path (`decision.py:550`), and making it stop is the point of FR-003.
  That case is in scope for SC-001, not for SC-002, and the plan must state it as an intended
  behaviour change rather than let it surface as an SC-002 red.
- **SC-003**: An operator-supplied `decision_id` that fails the shape check never appears in any
  constructed request line — asserted against the request, not the response.
- **SC-004** *(restated under Q2; absorbs the retired FR-025/SC-017; **clause 3 converted from a
  reporting instruction to a binding-identity assertion in round 3**)* **[standing]**: Drive **both**
  transports end-to-end through their own real refusal paths to an operator-visible string — the
  idiom at `test_saas_client_consent_gate_3030.py:352` and `test_client_consent_gate_3030.py:376` —
  and assert **three** things. **The three are not equal in discriminating power, and the criterion
  says which is which**, so a green SC-004 is not over-read (round-3 HIGH-2: as written in round 2,
  *nothing in SC-004 could red*):

  1. **`[ratchet]` — already true at `bb2020fea`. The non-fragment portion of the two rendered
     strings is byte-identical.** Not the whole string: whole-string byte-identity, conjoined with
     US2-AS2's "implies no kind this transport cannot transmit", is an **empty solution set** — the
     two identifier sets are asymmetric (only `mission_id` is common), so no single string can name
     each transport's own set without naming kinds it cannot transmit (reviewer finding N-2, closed
     by the operator's Q2 decision). Byte-identity survives as the **mechanism** goal — one template
     — not as the goal for the rendered text. **Measured in round 3**: the two `DENIED` strings are
     four-part concatenations differing in **exactly one word** (`saas_client/egress_consent.py:125-130`
     vs `tracker/egress_consent.py:187-192`); everything else is byte-identical **today**. So this
     clause must **stay** true; it does not distinguish a correct consolidation from an incorrect one.
  2. **`[ratchet]` — true of the unconsolidated state by construction. Each transport's fragment
     names exactly its own enumerated identifier set** (Key Entities): every kind it can transmit is
     named, and **no kind from the other transport's set appears**. Both current `DENIED` strings
     must survive **verbatim** — `saas_client` "mission and decision identifiers", `tracker`
     "mission and engagement identifiers". The strings that must survive are the strings that
     already exist, which is why **FR-009 is labelled `[ratchet]`** and why this clause must not be
     read as discriminating either. *One live edge*: the "fully named / no foreign kind" check runs
     against the Key-Entities enumeration. If it **fails on the existing text**, that is a real
     finding — the fix is a wording change and FR-009 goes back to `[build]`. It is the only way
     this clause can red, and it would red at `bb2020fea` too.
  3. **`[standing]` — this is the clause that reds. Binding identity, asserted mechanically.** After
     consolidation, both of these must hold:

     ```
     specify_cli.saas_client.client.project_egress_refusal   is specify_cli.egress.project_egress_refusal
     specify_cli.tracker.saas_client.project_egress_refusal  is specify_cli.egress.project_egress_refusal
     ```

     Two `is` comparisons, standing, zero cost. They red on the state nothing else in this spec
     detects: a partial consolidation in which `tracker/egress_consent.py` (or its SaaS twin)
     survives as a **re-export**, so the deciding module's by-value binding
     (`saas_client/client.py:23`, `tracker/saas_client.py:34`, decisions at `client.py:157` and
     `tracker/saas_client.py:329`) still points at the old object.
     *Why identity and not text* — **and why this is strictly stronger than the string comparison Q2
     removed**: a surviving re-export renders the **identical correct string**, so three correct
     text observations are exactly what a correct consolidation *and* a stale re-export both
     produce; text cannot separate them (reviewer finding RM-1). Once **identity** is pinned, **any**
     future patch of the shared module provably reaches **both** decision points — which is the
     property the friction doc's rot-mode-5 rule was written to obtain, and which no string
     comparison delivers. SC-015 does not close it either: a re-export is not "a second definition".
     *Anti-vacuity*: the comparison must be **between two independently imported names**, never two
     imports of one path — comparing an object to itself proves nothing (reviewer finding R-7). It
     is **unconditional**: an obligation on the consolidation, not a conditional on tests that happen
     to patch the symbol (the FR-025/SC-017 defect, reviewer finding N-6 / debugger finding P-2).
     It also makes FR-008's "exactly one editable presentation" **behaviourally** checkable rather
     than a source scan.
- **SC-005** **[standing: the named integers] + [one-off: the removal demonstration]**: Removing
  **any one** construction site of either transport class reds **that class's** guard, with the
  floor stated as a named integer: **tracker 3, SaaS client 4**.
  *Q8 split*: the **standing** half is the two named integers living in the guards' own non-vacuity
  assertions, so any drop reds on every run thereafter. The **one-off** half is the demonstration —
  actually removing one site of each class and quoting the two reds in the mission evidence. Do not
  build a synthetic-corpus harness to keep the demonstration standing: a harness that can drift from
  the real guard is a gate that goes green while the guard goes blind.
  *Note it is the named integers that are change-forcing, not the red itself*: both guards already
  `assert scanned` on a per-guard counter, which reds at zero, so deleting **all** sites of either
  class reds today (reviewer finding R-18). The single-site floor is the new property.
- **SC-006** **[standing: the `_gate_coverage` assertion] + [one-off: the real CI observation]**: A
  pull request whose diff is confined to `src/specify_cli/cli/**` — the shape of this mission's own
  `#3111` change — selects a CI job set that includes the SaaS-client attribution guard, asserted by
  reading `filter_groups` / `job_gating_groups` from `tests/architectural/_gate_coverage.py`.
  **Narrow scope per Decision D-4**; the general property is FU-1.
  *Q8 split*: the assertion is a test in `tests/architectural/`, so it **stands** — round 1's
  guess that SC-006 "is arguably one-off by nature (a CI observation)" was made before Decision D-6
  named the mechanism, and is superseded. The **one-off** half is a real CI observation on a
  `cli`-only diff, which is separately required because it is what discharges Decision D-4's
  **explicit unverified premise**: the dorny/`needs` chain behind A-1/A-2 is a reading of the
  workflow YAML, not a run.
- **SC-007**: Per-class **scanned** construction-site counts are at least the `bb2020fea` baseline
  (tracker 3, SaaS client 4), and the count of name-matched network-transmitting construction sites
  has not increased. **This is a count over name-matched sites, not a proof about egress surface**
  — the alias/indirection blind spot is stated in NFR-003 and in the Bundle A table.
- **SC-008** **[standing: the export pin] + [one-off: the removal demonstration]**: Removing
  `register_saas_client_factory` from `invocation/__init__.py`'s re-export (`:21`) or from its
  `__all__` (`:111`) reds at least one test that names the symbol. **Export half only** — deleting
  the `def` is already a collection-time `ImportError` in two test modules and is pinned by a node-id
  baseline, so it is not a valid before-state (debugger finding D-4).
  *Before-state independently verified in round 2*: `invocation/adapters.py` has **zero** `__all__`
  declarations, `grep "from specify_cli.invocation import" src/` returns **zero** hits, and
  `test_all_declarations_required.py:1-20` gates only `src/charter/` and `src/kernel/`. **The export
  half is genuinely unpinned today.**
- **SC-009**: Every test added or changed by this mission passes both inside a full run and as an
  isolated single-file invocation from this clone's root. **The evidence states the count of files
  and lists them** — "all isolated runs passed" over an unstated set is vacuous.
- **SC-010**: The four pre-existing assertions on the `could not be determined` refusal text pass
  **unmodified**. *Already true at `bb2020fea`; labelled a ratchet.* This criterion does **not**
  protect the branch that actually changes — SC-016 does.
- **SC-011**: Project B's `decision_id` appears in **no** constructed request line, and **no
  request line addressed to A's `team_slug` carries it**. Asserted over the transport's recorded
  requests with the in-repo idiom `transmitted_text(sink)`
  (`tests/specify_cli/saas_client/test_client_consent_gate_3030.py:293`).
  *Why this exists*: SC-003 attaches the byte-level assertion to the **secondary** defect — an id
  that fails the shape check. The consent-laundering defect (a well-formed ULID owned by B,
  transmitted to A's team under A's token) was covered by request **count alone**, and a count of
  zero is also what an unrelated upstream short-circuit produces
  (`tracer-tooling-friction.md:632-645`). The standing rule is to assert the engagement-relevant
  identifier reaching the transport, not a flag or a tally (debugger finding D-2).
- **SC-012** **[standing]**: For each transport class, the guard **rejects** an attribution form it
  does not accept today. Asserted against synthetic samples, per class (FR-015):
  - **Tracker**: a `SaaSTrackerClient(repo_root=…)` construction is **flagged unattributed** — the
    tracker guard accepts `project_root=` only.
  - **SaaS**: **`SaasClient.from_env(project_root=r)` is matched and FLAGGED unattributed**, because
    `from_env` accepts only a bare positional or `repo_root=`.
  *The SaaS witness is named explicitly because the obvious one is vacuous* (debugger finding DB-4):
  "the SaaS guard's accepted forms are not widened to admit tracker-only spellings" is **vacuously
  true** — the tracker accepts exactly `{project_root=}`, which the SaaS guard **already** accepts
  for *direct construction*. That phrasing bites nothing. The `from_env` form is the one that flips
  the moment the SaaS vocabulary is widened. Nothing in the current corpus exercises either
  assertion, and no count can detect their loss.
- **SC-013** **[standing]** *(round 3: **two per-class MATCH assertions**; the round-2 non-match
  proposal is **withdrawn entirely**)*: For **each** transport class, the guard **matches** a
  construction shape that **no `src/` site uses today**, asserted against a synthetic sample rather
  than against the live corpus. Both are **already true at `bb2020fea` (measured: matched and
  attributed); the build work is the assertion, not the behaviour** (FR-016).
  - **Tracker — `mod.SaaSTrackerClient(project_root=…)`**, an attribute-receiver call its
    `getattr(func, "attr", None)` predicate accepts. All three tracker construction sites are bare
    `ast.Name` callees, so this shape is exercised by nothing in the corpus; unifying on the SaaS
    guard's stricter predicate would blind the guard to it **while leaving the count exactly at its
    floor** (debugger finding D-5).
  - **SaaS — `SaasClient(project_root=…)`**, bare direct construction. Measured corpus:
    **`direct=0, from_env=4`** — every live SaaS site goes through `from_env`, so direct
    construction is **matched but unused**, exactly parallel to the tracker's attribute-receiver
    shape. A unification that collapses onto the `from_env` form drops it **silently, with no count
    moving**.

  *Why there is no non-match assertion here, recorded so it is not re-proposed* (round 3, on
  measurement; this **overturns** an earlier orchestrator ruling): pinning
  `mod.SaasClient(project_root=r)` as a **must-not-match** was proposed and is **rejected**.
  `mod.SaasClient(...)` is indeed excluded by design — FR-016 requires a literal `Name("SaasClient")`
  receiver — but **the SaaS predicate is already the stricter of the two, so a unification can only
  *loosen* it**: the guard would see **more** constructions, which is a coverage **gain**, not
  Mechanism 3's defect. A non-match pin would therefore (a) **red on a change that improves
  coverage**, and (b) **collide directly with FU-8**, which this spec files precisely because
  `mod.SaasClient.from_env(x)` is unguarded on both guards and *closing it means widening a
  predicate*. **A non-match pin would cement the hole FU-8 exists to close.** The genuinely silent
  and harmful directions are widening the **attribution vocabulary** (FR-015 — SC-012) and applying
  the **stricter** predicate to the **tracker** (SC-013's tracker half); both are covered above.
  *(Round 1's symmetric form — requiring `mod.SaasClient(...)` to **match** — is separately retired:
  it handed an implementer a red whose only repair was widening the SaaS predicate, so the criterion
  instructed the very defect it was added to prevent. See "Retired identifiers".)*
  *Also recorded, and named by no requirement*: **`mod.SaasClient.from_env(x)` is matched by neither
  guard.** Genuinely unguarded on both, not a regression this mission introduces — filed as FU-8 so
  the silence is not mistaken for coverage.
- **SC-014** **[standing: the unreadable-ledger test] + [one-off: the 3.11 run]**: This mission's
  touched test files **and both attribution guards** are executed once under
  `uv venv --python 3.11`, and the resulting `N passed` line is quoted verbatim in the mission
  evidence. A plan-phase judgement about version-divergent branches does not satisfy this (NFR-006).
  **And the run must include a test that actually reaches the divergent branch** (debugger finding
  DB-5), **in the one shape that can reach it** (round-3 HIGH-1 — the shape mandated in round 2
  could not):

  - **Mandated shape — chmod the containing `decisions/` *directory* to `0o000`, leaving the
    `index.json` file itself readable.** The expectation to assert is: at `decisions/store.py:64`,
    `Path.exists()` returns **`False` on 3.12+** and **raises `PermissionError` on 3.11**. That is
    the swallow-EACCES branch, and it is what makes the ownership module's explicit `except OSError`
    load-bearing. The test is **named in the evidence as one the 3.11 run included**.
  - **Why not the file.** `stat(2)` requires **search permission on the parent directory**, not read
    permission on the file — POSIX-level, not interpreter-dependent. Measured (uid 1000, Python
    3.14.4), and independently reproduced: with **`file=0o000`**, `Path.exists()` returns **`True`**
    on both interpreters and the `PermissionError` arrives **later**, from `read_text` at
    `store.py:66`. Round 2 mandated exactly that shape while telling the implementer to *"expect this
    test to behave differently on the two interpreters — which is the point"*. It behaves
    **identically**, and the honest reading of an identical result is *"no divergence, NFR-006
    discharged"* — **a false negative in this mission's only portability gate, produced by a claim
    the spec presented as measured.**
  - **Optional companion, and it must be labelled.** A `file=0o000` case **may** be kept, but only
    as an assertion that `read_text` raises `PermissionError` at **`store.py:66`** — i.e. that the
    malformed/unreadable handling covers `OSError` from the read as well as from `exists()`. **It is
    explicitly *not* the version-divergent path** and must not be offered as evidence for NFR-006.

  Without a test in the directory shape, SC-014 is *"a green 3.11 run over tests that never touch
  the branch — a true statement about nothing."* The divergence itself is measured and stated once,
  in *Edge Cases*.
  *Skip honestly*: if the test cannot run as root or on a filesystem ignoring mode bits, it must
  **skip with a stated reason**, not pass. A `0o000` test that silently succeeds because the process
  can read anything is the vacuous case — and this applies to the directory shape as well as the
  file shape.
- **SC-015** **[standing: the mechanism] + [one-off: the divergence demonstration]**: The mechanism
  enforcing "exactly one editable presentation" is named and exercised: under the resolved Q1
  (option (d)) the shared module in `src/specify_cli/egress/` is the only definition site of the
  **template and the four verdict branches**, asserted by a test that fails if a second definition
  appears. **Q2 does not weaken this**: per-caller identifier fragments are *arguments*, not second
  presentations; a "consolidation" that leaves two templates and merely parameterises them does not
  satisfy FR-008.

  > **POST-ACCEPTANCE CORRECTION to SC-015 (same mechanism as the FR-020 correction at `:472`).**
  >
  > **(a) The path in SC-015's own text is superseded.** SC-015 above still names
  > `src/specify_cli/egress/` — a **package**. **Q1 was subsequently resolved to a plain module,
  > `src/specify_cli/egress.py`**, and **SC-025 already carries the corrected form**. The package
  > form is not a harmless spelling difference: it was **measured** to re-create rot-mode 5 (an
  > `__init__.py` re-export creates a **fourth** name for `project_egress_refusal`, at which MUT-1 is
  > inert while SC-004 clause 3 stays green — 8 cases, PR-1), and WP02's two `egress.py` dorny globs
  > would then match nothing. **Read every `src/specify_cli/egress/` in this criterion as
  > `src/specify_cli/egress.py`.** A directory appearing under that name is a reject (WP03 review
  > guidance), and a split would have to land **with a third `is` comparison** — a reversal of the
  > decision, not a refactor.
  >
  > **(b) The `[one-off]` half is an obligation, not decoration.** SC-015 is tagged
  > **[standing: the mechanism] + [one-off: the divergence demonstration]**, and **both halves are
  > required**. FR-008 — *exactly one editable presentation*, this mission's headline — maps to
  > **SC-015 alone**, and **no mutation in the suite targets it**. The `[one-off]` half is: introduce
  > a **second definition** of the template or of a verdict branch in a **throwaway worktree**, run
  > the standing test, and **quote the red's assertion text**. Without it the standing half is
  > satisfiable by `assert not (SRC / "saas_client" / "egress_consent.py").exists()` — a
  > **file-absence check**, which passes forever and **can never red on a second definition appearing
  > in a new file**. **The mandated mechanism is therefore an AST or text scan over `src/` asserting
  > that the template and the four verdict branches have exactly ONE definition site — not a
  > file-absence check.** Carried by WP03/T021.
  >
  > **(c) The same substitution applies to the residual `egress/` mentions elsewhere in this
  > document.** `:728` still reads "the package may be created", and `:1017`/`:1019` (Q1's
  > resolution text) still name `src/specify_cli/egress/` and direct adding
  > `'src/specify_cli/egress/**'` to the `core_misc` glob — a glob that matches the module **not at
  > all**, since Q1 resolved to a plain module, `src/specify_cli/egress.py` (the work packages
  > correctly mandate `'src/specify_cli/egress.py'`). Both `:728` and `:1017`/`:1019` are
  > justification-record text — the *Open design questions* / falsifier record, not the *Edge Cases*,
  > *Success Criteria*, or coverage-table blocks this document's own reading rule directs implementers
  > to work from — so the operative route through them is already closed twice over. Read every
  > `src/specify_cli/egress/` at `:728`, `:1017`, `:1019` as `src/specify_cli/egress.py`, and every
  > `'src/specify_cli/egress/**'` glob instruction there as `'src/specify_cli/egress.py'`, exactly as
  > clause (a) above directs for SC-015's own text.
- **SC-016**: The merged `DENIED` wording is pinned by a content assertion in **both** packages'
  test trees, added alongside the existing four assertions rather than replacing them. Deleting the
  `DENIED` branch reds (FR-024, reviewer finding R-10).
- **~~SC-017~~**: *Retired in round 2 — folded into SC-004 clause 3, unconditionally.* It was a
  vacuously-satisfiable conditional over tests; the hazard is a property of the consolidation. See
  "Retired identifiers" and SC-004.
- **SC-018** **[standing]**: The ownership derivation is a single named function in a stated module,
  **outside `src/specify_cli/cli/commands/**`**, called by `decision widen` **and imported by name
  from a non-CLI test module** — the last clause is what distinguishes a seam from a helper, because
  a module-private `def _owns_decision(...)` at the bottom of `cli/commands/decision.py` would
  otherwise satisfy this criterion and still be the fifth private answer to the ownership question
  (reviewer finding N-7, FR-020).
  **The containment half is conditional on the FR-021 discharge the plan takes** (reviewer finding
  N-4) — round 1 stated only the discharge-(i) form, which makes SC-018 unsatisfiable under (ii):
  - **Under discharge (i)** (call `resolve_feature_dir_for_mission` with `cwd`/`env` explicit, plus
    a containment assertion): a test constructs a case where the resolver would otherwise return a
    path outside the acting root, and **observes the check biting**.
  - **Under discharge (ii)** (do not use that resolver; the slug only selects among directories the
    FR-001 glob already enumerated): the outside-root case **cannot be constructed**, so the
    substitute is an **enumeration equality** — a test asserts that **every path fed to `load_index`
    is a member of the glob's own result set**. Nothing else is admissible; "no test, because the
    case can't happen" is not a discharge.
  - **Under either**: candidate paths are `.resolve()`d **before** the containment or membership
    test (`Path.glob` follows a symlinked mission directory and `is_relative_to` on the unresolved
    path returns `True`), and the one-level depth of the glob is pinned. Measured: **0 symlinks**
    under `kitty-specs/` today, and one-level glob vs repo-wide `rglob` both return **49** with
    **0 missed** — a shape assumption held by measurement, not by construction (reviewer finding
    N-5).
- **SC-019** **[standing, but see the honesty note]**: A one-page ADR exists under `docs/adr/3.x/`
  naming the egress-consent boundary, the provenance invariant, and the fact that the attribution
  guard is syntactic. Verified by the same grep that measured zero:
  `grep -rn "resolve_egress_consent\|ConsentedBatch\|project_egress_refusal" docs/adr/3.x/
  docs/context/` returns a non-zero count, with the file named (FR-022).
  **Honesty note, added in round 2** (reviewer finding N-10, converged with debugger): **this is a
  grep-gate. Its presence half is mechanical; its content half is not enforceable by it.** A file
  containing only the three search terms passes. That is accepted rather than papered over — the
  alternative (asserting the three *contents* by substring) buys a brittle gate that pins prose
  wording, and the ADR's value is in being read, not in being matched. **The content is a
  plan-review and PR-review item, not a criterion**, and the reviewer must read the ADR rather than
  trust the green. FR-022 is kept regardless: it is the only recurrence-acting item in the bundle.
- **SC-020** **[standing, but see the honesty note]**: `grep -ril engagement docs/context/` returns
  at least one entry, and that entry defines the term as used in the operator-facing refusal string
  (FR-023). **No longer conditional**: round 1 offered an escape — "*or* Q2 resolved away from the
  word" — and **Q2 resolved to keep "engagement" in the tracker fragment**, so the escape is closed
  and the glossary entry is mandatory.
  **Honesty note**: same shape as SC-019. **A grep-gate.** Presence is mechanical; whether the entry
  actually *defines* the term is a plan/PR-review item. Stated so the green is not over-read.
- **SC-021** **[ratchet — already true at `bb2020fea`; no new test required]**:
  `project_egress_refusal` is a **live call** on the tracker transmit path, asserted behaviourally:
  the tracker transport is driven into a non-consenting project and the refusal is observed. A
  substring check over `tracker/saas_client.py` does **not** satisfy this — the import line at `:34`
  alone satisfies C-004's gate (FR-027, architect finding A-5).
  **The two existing tests that already assert it** (reviewer finding N-8 / debugger, converged;
  both in `tests/sync/tracker/test_saas_client_consent_gate_3030.py`):
  - `test_unconsented_project_transmits_no_engagement_name` (`:258-289`) — writes a non-consenting
    config at `:267`, constructs `SaaSTrackerClient(project_root=…)` at `:269`, asserts `sink == []`
    at `:279` and a non-`None` refusal carrying `error_code == "project_consent_denied"` at
    `:283-284`.
  - `test_project_local_refusal_is_honoured` (`:311-324`) — the committed `sync.enabled: false` case,
    same shape.

  Both reach the refusal through the call at `tracker/saas_client.py:329`. **The requirement is that
  these two keep passing through the consolidation**; a change that leaves only the import at `:34`
  reds them. Carrying FR-027/SC-021 as `[build]`/High was a ratchet wearing build clothing.
- **SC-022**: The per-site enumeration at `saas_client/egress_consent.py:52-76` no longer asserts
  that the `decision widen` entry is bounded because `decision_id` "is a ULID rather than a slug",
  and describes the post-FR-001 state (FR-026).
- **SC-023**: `register_saas_client_factory`'s docstring contains `request_text` and does **not**
  contain "Called once at sync package startup"; **and** the identical sentence on
  `register_egress_consent_resolver` (`adapters.py:113`) is **unchanged**, because there it is true
  (FR-018, architect finding A-9 — a grep-and-replace across `adapters.py` would break a correct
  docstring).
- **SC-024**: The `#3111` acceptance test writes **both** checkouts' `.kittify/config.yaml` on
  disk, passes both roots explicitly rather than relying on a kwarg default, and contains an
  **in-file positive control** proving A's consent actually grants. Both candidate test directories
  carry autouse fixtures that fabricate consent when the kwarg is omitted (C-010, debugger finding
  D-12).

  > **POST-ACCEPTANCE CORRECTION to SC-024 (same mechanism as the FR-020 correction at `:472`).**
  >
  > **The clause *"passes both roots explicitly rather than relying on a kwarg default"* is
  > SUPERSEDED, and it must not be restored.** It is **not executable** under C-008's mandatory real
  > invocation (`spec-kitty agent decision widen`): the test never constructs a client — **`cmd_widen`
  > does**, through `SaasClient.from_env(...)` at `decision.py:558`. **There is no kwarg for the test
  > to pass.** An implementer "restoring" the clause would construct a client inline and thereby drop
  > C-008's real entry point **and the FR-003 `--mission-slug` route with it** — i.e. the clause as
  > written instructs precisely the thing WP04 exists to prevent.
  >
  > **Read that clause as: convey A's root through `SPECIFY_REPO_ROOT`** (`core/paths.py:224`, the
  > highest-priority tier in `locate_project_root`), set via `monkeypatch.setenv`. **The rest of
  > SC-024 is unchanged and still binds** — both `.kittify/config.yaml` files written on disk, and the
  > in-file positive control. **The fabricated-consent hazard the superseded clause was reaching for
  > is instead closed by the compensating runtime assertion `client._project_root == A_ROOT`**
  > (WP04/T028 item 9), which reds on either side of the two-file reopening condition; the kwarg
  > phrasing never could. **A reviewer checking WP04 against this criterion must check the corrected
  > form; WP04 is not non-compliant for omitting the superseded clause.**
- **SC-025** *(new in round 2; antecedent widened at plan review round 1)* **[standing]**: **If this
  mission lands a new `src/specify_cli/<name>.py` MODULE or a new `src/specify_cli/<name>/`
  PACKAGE** — which under the resolved Q1 it does, `src/specify_cli/egress.py` — a test asserts that
  that module's or package's dotted name appears in the integration-boundary gate's INTEGRATION
  prefixes. The assertion must red if the classification line is removed.
  *Why the antecedent covers both forms* **(plan review round 1, architect finding PA-5 / debugger
  finding PR-1)**: this criterion was written package-shaped when Q1's answer was a package. The plan
  subsequently resolved Q1 to a **plain module**, because a package's `__init__.py` re-export creates
  a **fourth** name for `project_egress_refusal` at which a mutation is inert while SC-004 clause 3
  stays green (measured, 8 cases). A package-shaped antecedent would then be **false**, SC-025 would
  assert nothing, and the classification would silently return to the ungated state N-9 flagged.
  **This widening is not an accommodation of that choice.** The hazard SC-025 gates is *an
  unclassified thing that lazily imports `specify_cli.sync`* — a property of **what the thing
  imports**, not of whether it is a directory or a file; the boundary gate's own matcher is
  `mod == prefix or mod.startswith(prefix + ".")` (`test_integration_boundary.py:151-152`), whose
  first arm is exactly the module case. **The package-shaped antecedent was a latent gap regardless
  of Q1's answer**, and closing it improves this spec independently of the module decision.
  *Why it exists*: C-005's discharge was the sentence "it must be an explicitly listed task with its
  own assertion", and **no such assertion existed anywhere in the spec** — a blank cell wearing a
  sentence, and **the only requirement here with no enforcement at all** (reviewer finding N-9).
  C-005 itself records that **no pre-existing gate notices a forgotten classification**: a new
  package matches no CI filter group and lands at ~150–250 LOC, under `_gate_coverage.py:1205`'s
  `T_LOC = 500`, so neither the integration-boundary gate nor the LOC-gated unclaimed-src-dir
  worklist fires. **For a module the LOC argument is not even needed** — `_gate_coverage`'s worklist
  iterates direct child **directories** of `src/specify_cli/` and `_src_dir_of_glob` returns `None`
  for any `src/specify_cli/<file>.py` glob, so a module is **structurally outside** that detector at
  any size. SC-025 is the gate that notices, in both forms.
  *Scope note*: this pins the **classification**, not the transitive-reach hole. Nine CORE modules
  already reach `specify_cli.sync` transitively through unclassified packages and stay green;
  classification prevents a tenth and closes nothing (architect finding A-4, FU-3).
  *Anti-vacuity*: the assertion must name the module/package as a value compared against the gate's
  own prefix list, not restate the list. A test that asserts `"specify_cli.egress" in
  ["specify_cli.egress"]` is the vacuous form.

### Requirement → Success Criterion coverage

Every requirement resolves to a criterion, a `[ratchet]` label, or an explicit fold. **A blank cell
is a defect in this table, and so is a cell containing a sentence instead of a criterion** — the
round-1 C-005 row claimed "an explicitly listed task with its own assertion" when no such assertion
existed, which is the failure mode this table is supposed to expose rather than host (reviewer
findings R-11, N-9). Retired rows are listed so the ID gaps read as deliberate.

| Requirement | Label | Criterion / disposition |
|---|---|---|
| FR-001 | build | SC-001, SC-011, SC-024 |
| FR-002 | build | SC-001, SC-011, **SC-002 (the compatibility clause and its forbidden repair)** |
| FR-003 | build | SC-001 (the `--mission-slug` route), plus the FR-003 differential asserted in the same module |
| FR-004 | **folded** | **Into FR-002** — no independent criterion by construction (reviewer finding R-4) |
| FR-005 | build | SC-003 |
| FR-006 | build | SC-001 — **two** routes asserted (`--mission-slug`, `SPECIFY_REPO_ROOT`); the other two root routes are **held by construction** at the convergence point `locate_project_root`, stated in SC-001 |
| FR-007 | **folded** | **Into FR-002** — coverage row was byte-identical to FR-002's; no independent criterion, no independent cost (round-2 cut list #1) |
| FR-008 | build | SC-015 |
| FR-009 | **ratchet** | SC-004 **clause 2**, and clause 2 is itself labelled `[ratchet]` — under Q2 both current `DENIED` strings survive verbatim, so the required outcome already holds at `bb2020fea`; the build work is the assertion, as for NFR-004/FR-027. **Read alongside SC-004 clause 3, which is the clause that discriminates** (round-3 HIGH-2) |
| FR-010 | **ratchet** | SC-010 (already true; must stay true) |
| FR-011 | **ratchet** | Self-enforcing — the dead-symbol gate reds immediately; **no SC needed, deliberately** |
| FR-012 | **ratchet** | C-003; **no SC needed, deliberately.** **POST-ACCEPTANCE CORRECTION (same mechanism as `:472`):** *"no SC"* is not *"no carrier"*. FR-012 is **High-impact and ungated**, and its **only written rationale anywhere in the repository** is the prose in `src/specify_cli/tracker/egress_consent.py` (`:18-45` — why the wrapper asks `resolve_egress_consent` rather than re-deriving checkout→project→consent, i.e. C-003's single-chain argument) — **a file WP03/T017 deletes.** `saas_client/egress_consent.py:20` defers to it in writing and is deleted too. **WP03 must therefore relocate that rationale into `src/specify_cli/egress.py` (or name WP06's ADR as its home, stated in both places) and name `resolve_egress_consent` and "never re-derive the chain locally" in the module's content list, citing FR-012.** Deleting it would leave an ungated High-impact requirement with nothing written down that a future editor could trip over. |
| FR-013 | **ratchet** | US2-AS4; protected structurally by Decision D-5; **no SC needed, deliberately** |
| FR-014 | build *(assertion)* | SC-005, SC-007 |
| FR-015 | build *(assertion)* | SC-012 |
| FR-016 | build *(assertion)* | SC-013 — **two per-class MATCH assertions**: tracker `mod.SaaSTrackerClient(project_root=…)`, SaaS `SaasClient(project_root=…)`, each an unused-but-matching shape whose loss no count would show. **No non-match is asserted anywhere** — that proposal was withdrawn on measurement in round 3 (it would red on a coverage *gain* and collide with FU-8); grounds stated once, at SC-013 |
| FR-017 | build | SC-006 |
| FR-018 | build | SC-023 |
| FR-019 | build | SC-008 |
| FR-020 | build | SC-018 (including the "outside `cli/commands/**`, importable by a non-CLI caller" clause) |
| FR-021 | build | SC-018 — **conditional on the discharge taken**: (i) containment biting, (ii) enumeration equality |
| FR-022 | build | SC-019 — **a grep-gate; presence only.** Content is a plan/PR-review item, stated in SC-019 |
| FR-023 | build | SC-020 — **a grep-gate; presence only.** Content is a plan/PR-review item, stated in SC-020 |
| FR-024 | build | SC-016 |
| ~~FR-025~~ | **retired** | Folded into **SC-004 clause 3**, unconditionally (round-2 cut list #2); clause 3 became a **binding-identity** assertion in round 3 |
| FR-026 | build | SC-022 |
| FR-027 | **ratchet** | SC-021 — already true, evidenced by two existing tests cited in SC-021; no new test required |
| ~~NFR-001~~ | **retired** | Folded into **NFR-003**, which now states both inequalities (round-2 cut list #4) |
| NFR-002 | build | SC-002 (exactly one request on the success path), SC-001 (zero on refusal paths) |
| NFR-003 | build | SC-007 — bounded; the alias/indirection blind spot is stated in NFR-003 itself and in the Bundle A table |
| NFR-004 | **ratchet** | SC-016 plus the per-branch pins named in NFR-004 itself — **all five pins already hold at `bb2020fea`**; the build work is pinning them |
| NFR-005 | build | SC-009 |
| NFR-006 | build | SC-014 — including the mandatory unreadable-ledger test named there, **in the mandated shape: `decisions/` *directory* at `0o000`, file readable**. The `0o000`-*file* shape does not reach the version-divergent branch and does not discharge NFR-006 (round-3 HIGH-1) |
| C-001 / C-003 / C-006 / C-008 / C-009 | constraint | Constraints on the design space; verified by inspection at plan review, not by a criterion |
| C-002 | constraint | SC-005, SC-012, SC-013 |
| C-004 | constraint | SC-021 (behavioural companion; the substring gate itself is pre-existing) |
| **C-005** | constraint | **SC-025** — the classification is asserted by a test that reds if the INTEGRATION-prefix line is removed. *(Round 1 had a sentence here and no assertion; that was the table's own defect and it is closed — reviewer finding N-9.)* |
| C-007 | constraint | Verified by inspection: no shape check is added to the three interview sites |
| C-010 | constraint | SC-024 |
| C-011 | constraint | Verified at plan review: if the plan proposes cross-checkout search or a uuid-typed seam, it is deferred to FU-4 / FU-5 |

**Criteria with no requirement row, by design**: SC-011 (belongs to FR-001/FR-002 jointly),
SC-024 (belongs to C-010), SC-025 (belongs to C-005). **Retired criteria**: SC-017 (→ SC-004),
and SC-013's **round-1** SaaS half — the `mod.SaasClient(...)` **match** assertion, deleted in round
2 and **not** restored. SC-013 does carry a SaaS half again as of round 3, on a different shape
(`SaasClient(project_root=…)`, a **match**); the round-2 proposal to pin a **non-match** was
withdrawn entirely and appears nowhere in this document. See "Retired identifiers".

**`[ratchet]` audit — each row below is claimed already-true at `bb2020fea`, with what makes it so**:
FR-009 (**the required rendered text is fixed by the operator's Q2 decision to the strings that
already exist** — both current `DENIED` strings survive **verbatim**, so no wording is produced by
this mission and SC-004 clause 2's outcome is true of the unconsolidated state by construction;
measured in round 3, the two strings differ in exactly one word and are byte-identical elsewhere.
**Stated bound**: this is a ratchet over *what Q2 fixed*, not a claim that today's fragments are a
complete enumeration of each transport's identifier set — FR-009's "fully named" clause is checked
against Key Entities by SC-004 clause 2, and if that check fails on the existing text the fix is a
wording change and FR-009 returns to `[build]`); FR-010 (four `could not be determined` assertions exist
and pass); FR-011 (the constant is in no
`__all__`; `test_no_dead_symbols.py:13-24` walks every `*.py` under `src/`); FR-012 (both wrappers
already resolve through `invocation.adapters.resolve_egress_consent`); FR-013 (the lazy in-function
`import specify_cli.sync` at `saas_client/egress_consent.py:107-113` already degrades to a refusal);
FR-027 (two behavioural tests cited in SC-021, verified in round 2); NFR-004 (all five per-branch
pins hold today — the requirement is to *assert* them, not to create them).

**Round-3 note on `[ratchet]` rows that carry a criterion.** FR-009 joins NFR-004 and FR-027 as a
ratchet whose criterion exists to *pin* an already-true property. Such a criterion **must not be
read as discriminating**, and each now says so in its own text (SC-004 clauses 1–2, SC-010, SC-021).
The `[build]` honesty note above still holds for FR-014/015/016, where the assertion is over
behaviour the guards have but nothing observes; the difference for FR-009 is that Q2 removed the
wording work entirely, leaving nothing to build but the assertion.
