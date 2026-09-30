---
title: 'ADR: The Egress-Consent Boundary — Consent Is Keyed on the Record Being Sent, Never on Ambient Context'
description: 'Egress consent is keyed on the record being sent, never on ambient context: one refusal presentation where only `None` is permission, with per-transport identifier fragments.'
status: Accepted
date: '2026-08-04'
---

## Context and Problem Statement

Two SaaS transports put project-identifying text on the wire: the tracker transport
(`specify_cli/tracker/saas_client.py`) and the widen-mode SaaS client
(`specify_cli/saas_client/client.py`). A mission slug is a
[client engagement name](../../context/identity.md#engagement), so *which project consented*
is a confidentiality question, not a convenience one.

**The boundary that answers it had no presence in either charter authority path.** Measured
before this ADR existed, with a controlled diagnostic (a known-present term returned 12 hits,
a nonsense term returned 0):

```
grep -rn "resolve_egress_consent\|ConsentedBatch\|project_egress_refusal" docs/adr/3.x/ docs/context/
  -> 0 hits
```

A P0 mission (#3030) built `ConsentedBatch`, a boundary guard and a renamed registry seam, and
recorded the rationale only in a mission-local tracer file that no maintainer editing a transport
will read — while the charter instructs every agent to read `docs/adr/3.x/` when they change a
structural boundary. This ADR is the durable record. It is the only part of mission
`egress-refusal-consolidation-3110-01KYW895` that acts on **recurrence** rather than on an
instance.

### The instance that forced it: #3111 is consent *laundering*

`spec-kitty agent decision widen` resolved the project root from the **operator's location**
(`locate_project_root() or Path.cwd()`, `cli/commands/decision.py`) while `decision_id` is an
**operator-supplied argument**. Standing in consenting project A and widening a decision owned
by B sent **B's identifier to A's team, under A's token** — and **every consent gate answered
truthfully, about the wrong project.**

That distinction matters for the fix. It is not unconsented egress: the gate at
`saas_client/client.py` runs *before* `url = f"{self._base_url}{path}"`, so a non-consenting
checkout already transmits nothing. Nothing was bypassed. The wrong question was asked.

## Decision Drivers

* The same policy was written twice — once per transport — as two near-identical modules a future
  editor could change independently.
* The bug class recurs: it has been found and closed **five** times before this mission, each
  time in a new place, and **twice more during *review of this mission*** — seven in total,
  which is the row count of the table below. (An earlier draft said "six … and twice more",
  i.e. eight, contradicting its own table. The five are enumerated in the mission handoff:
  the current working directory, `repo_root`, machine-global arming, daemon scope, and a
  checkout-level grant.)
* The existing protection is an AST guard whose reach is syntactic, and reading it as an ownership
  proof is a live hazard.

## Decision Outcome

Three things are decided, and all three are load-bearing.

### 1. The boundary is one presentation: `src/specify_cli/egress.py`

`project_egress_refusal(project_root, identifiers) -> str | None` is the single editable
presentation of the project-egress refusal policy. **`None` — and only `None` — is permission.**
Both transports now reach the policy through it; the module is owned by neither.

* Each transport passes **its own identifier-set fragment as an argument** —
  `TRACKER_EGRESS_IDENTIFIER_KINDS = "mission and engagement identifiers"`,
  `SAAS_EGRESS_IDENTIFIER_KINDS = "mission and decision identifiers"`. The sets are asymmetric on
  purpose: the tracker carries no `decision_id`, so a union sentence would tell a tracker operator
  that a decision id was at stake which that transport cannot transmit. The fragments are
  *arguments*, not second presentations.
* The module does **not** re-derive the checkout → project → consent chain. It asks
  `invocation.adapters.resolve_egress_consent`, a CORE registry slot that `sync` fills with
  `_egress_consent_resolver` — the one derivation, the same funnel the drain, the emitter, the
  daemon and `local_commit` all walk.
* Consolidation changed **no operator-visible text**: both refusal strings render byte-for-byte as
  before.

**What would overturn this:** a second module that renders a refusal sentence; an identifier kind
hard-coded into the shared template (that hands one transport the other's vocabulary); or a local
re-derivation of consent inside `egress.py`. A "consolidation" that left two templates and merely
parameterised them would not satisfy this decision either.

### 2. The provenance invariant — and it **supersedes** the framing this mission started with

> **Consent must be keyed on something derived from the RECORD BEING SENT, never from ambient
> context.**

The earlier framing was *"a path-typed seam is the defect"* — take a `project_uuid` instead of a
`Path` and the class closes. **That framing is superseded and should not be re-proposed.**
`resolve(project_uuid_of(locate_project_root()))` is the same defect respelled: it is still
ambient. **A type cannot express provenance.** That is why a uuid-typed seam is *optional* rather
than indicated (open question Q3 / follow-up FU-5): it would not have prevented #3111.

The converse also holds, and is the reason a path-keyed site is not automatically suspect: some
path-keyed sites are **sound because the path is derived from the data.**
`tracker.origin.bind_mission_origin` walks *up* from the `feature_dir` whose `meta.json` supplies
the very `mission_id` and `mission_slug` being sent; `mission_creation` builds that directory under
the same root the issue title is read from. Owner and root agree by derivation, not by locality.

The substitute-for-the-record's-own-project is what recurs. Found and closed so far:

| Substitute | Where |
|---|---|
| the current working directory | `decision widen`'s root resolution (#3111) |
| `repo_root` | construction sites that attributed the client to the checkout, not the payload |
| machine-global arming | `SPEC_KITTY_ENABLE_SAAS_SYNC` — one export carried five never-opted-in projects (2026-07-27 incident) |
| daemon scope | a long-lived process reusing one client across projects |
| a checkout-level grant | consent recorded for the checkout rather than for the project |
| **a symlinked `kitty-specs/`** | *found in review of this mission, not in its design* |
| **a symlinked `<mission>/decisions/`** (or `decisions/index.json`) | *found in review of this mission, not in its design* |

The last two are the sharpest evidence that the invariant is about provenance and not about types:
both were reached through code written **specifically to prevent** #3111, and both reproduced #3111's
request line verbatim — B's identifier, addressed to A's team, under A's token. With
`A/kitty-specs -> B/kitty-specs` the command exited 0 and put B's `decision_id` on the wire; the
paired control (no symlink) refused with zero requests. `.resolve()` follows the link, so every
downstream `is_relative_to(specs_root)` was measured against the *resolved target* and containment
held trivially.

They are closed by **containment, asserted at three depths**: `specs_root.is_relative_to(root)` before any
`stat(2)`, and again on the file actually opened, measured against the **acting root** rather than
the mission directory — because the mission-directory check sits two levels above the file a
symlinked `decisions/` redirects. The third is the **resolved mission candidate** itself
(`ownership.py:387`), which predates this mission's symlink findings and is what the two new
checks bracket. A symlink *within* the root still works, so monorepo layouts are unaffected.

**What would overturn this:** a consent decision keyed on `Path.cwd()`, an env flag, a destination
team, a token's existence, or any root not derived from the record. **What it does not cover, by
construction:** `mount --bind B/kitty-specs A/kitty-specs` is transparent to `realpath`, so no
path-based containment check can see it. That is a limit of the approach, recorded rather than
papered over; closing it needs a different mechanism, not a stricter path check.

### 3. The attribution guard is **SYNTACTIC** — it is not an ownership proof

`test_every_production_construction_site_attributes_its_project` AST-scans `src/` and proves that
a project root **was passed** to every construction site. Its own docstring concedes the limit:

> *"It cannot prove the root is the **right** one."*

Say it here so a future reader does not read a green guard as an ownership proof. Two safety nets
stand behind it and neither replaces it — a root that is not a project root resolves to no uuid and
therefore **denies**, and a checkout declaring a *different* uuid is ignored by the consent vote.
What neither net catches is the case the precondition exists for: a **valid root for the wrong
project.** What actually bounds `decision widen`, the one site where root and subject can
legitimately diverge, is the ownership check below — not the guard.

**This one has no falsifier, and that is the point.** It is a stated limit, not a claim awaiting
disproof. What *would* overturn it is a guard that could decide ownership from source text, and
that requires a mapping which does not exist:

## Ownership is **positional**, which is why the check is a within-checkout search

There is no `decision_id` → owning-project mapping anywhere, locally or remotely.
`decisions.models.IndexEntry` is `frozen=True, extra="forbid"` and carries only `mission_id` +
`mission_slug`, so a `project_uuid` **cannot even be present** in a valid ledger file; record
creation takes `repo_root`, uses it and discards it; and the SaaS client's five endpoints include
no "get decision".

> **Ownership is encoded by which directory a ledger sits in, never as data.**

So the search enumerates mission directories one level under `<repo_root>/kitty-specs/` and
membership-tests each ledger. Its outcome is *owns it* / *ownership not established* — and it can
**never** name project B (constraint C-009). Re-resolving token and team "from the owning root" is
therefore not implementable here; what blocks it is the absence of a **checkout enumeration**,
which is a different and buildable thing, deferred.

**There is no fall-through to the acting root** — not in the broad form, and not in the narrow
"no `kitty-specs/` at all, so allow it" form, which reinstates exactly the leak this closes.
An unreadable ledger never vetoes a positive hit elsewhere: refusal is correct only when the search
terminates with **no hit AND at least one unreadable ledger.** Measured: 49 ledgers across 333
mission directories in this repository, so an unrelated corrupt file is not theoretical; the
one-level enumeration and a repo-wide `rglob` return the same 49 with 0 missed.

**What would overturn this:** an owner field appearing on a ledger entry — a `project_uuid`, or any
data that identifies the owning project. That would make an identifying answer possible and would
change the shape of the check, not merely its performance.

## `Path.exists()` is EACCES-divergent, and this mission removed it three times

This is the single most repeated defect in the mission. `store.load_index` opened with
`if not path.exists(): return DecisionIndex(...)`. For a ledger whose containing `decisions/`
directory is unreadable, `stat(2)` needs search permission on the parent (POSIX, not an interpreter
quirk), and `Path.exists()` handles the resulting `EACCES` **differently per interpreter**.
Measured in this clone, non-root euid, through `load_index` itself, control first:

```
                      3.11.15            3.12.13            3.14.4
CONTROL readable      1 entry, hit       1 entry, hit       1 entry, hit
file=0o000            PermissionError    PermissionError    PermissionError
decisions/=0o000      PermissionError    PermissionError    OK, 0 entries
```

The last row is the trap: on **both CI interpreters** it raises uncaught — a traceback where an
operator-actionable refusal belongs — while on 3.14 it silently yields an empty index. **It ships
a traceback from a local run that was green.**

* `Path.is_dir()` is the same call with the same divergence.
* `Path.glob` is the mirror-image hazard: it **swallows** `EACCES` and returns `[]` on all three
  interpreters, so an `except OSError` wrapped around a glob is unreachable — effect-free handling
  that reads as a handled case while handling nothing.
* **The remedy is `Path.stat()` / `os.stat`, and only those.** They raise `EACCES` on *every*
  interpreter; it is the predicate that changed, and **at 3.14, not 3.13**. Measured on four,
  non-root euid, via a symlink into a `0o000` directory:

  ```
                             3.11.15   3.12.13   3.13.12   3.14.4
  Path.stat() / os.stat      RAISES    RAISES    RAISES    RAISES
  Path.is_dir()              RAISES    RAISES    RAISES    False
  ```

  3.14 rewrote the predicate to `if follow_symlinks: return os.path.isdir(self)`, and
  `os.path.isdir` swallows every `OSError`. Through 3.13 it was `S_ISDIR(self.stat().st_mode)`
  under `except OSError: if not _ignore_error(e): raise`, and `_ignore_error` covers only
  `ENOENT`/`ENOTDIR`/`EBADF`/`ELOOP`, so `EACCES` propagated. Where the code must *observe* an
  unreadable path — to record it, refuse on it, or say which one it was — the predicate cannot
  express that and `S_ISDIR(p.stat().st_mode)` can.

  Two traps in measuring this, both of which caught us. `hasattr(pathlib, "_ignore_error")` is
  `False` from 3.13, because 3.13 makes `pathlib` a package and moves the helper out of the
  top-level namespace — a layout change that reads exactly like the behaviour change, one minor
  version early. And the non-default `follow_symlinks=False` branch still goes through `stat()`,
  so a probe that passes it measures the arm the code does not take. **Measure the call as
  called, not the namespace around it.**

  This mission shipped that defect once and then closed it, which is the part worth recording.
  `_mission_dirs` classified candidates with `resolved.is_dir()`, so on 3.14+ an unreadable
  candidate took the bare `continue` instead of the `except OSError` that records it — **LOW-8's
  original defect, reintroduced by LOW-8's own fix.** It was measured (`33 passed` on 3.11.15 and
  3.12.13; `2 failed, 31 passed` on 3.14.4), filed as
  [#3177](https://github.com/Priivacy-ai/spec-kitty/issues/3177), and deferred — the reasoning
  being that it is fail-closed (`owned=False`, nothing transmits) and therefore a *diagnosis*
  defect rather than a leak.

  Deferring it was the wrong call, for a reason the deferral itself records: `requires-python`
  is `>=3.11`, so 3.14 is admitted, and **no CI job runs pytest above 3.12** — the deferral would
  have parked a known regression where no gate could ever rediscover it, with two tests left
  permanently red to mark the spot. It is closed here instead, by the remedy #3177 itself
  proposed: route the candidate through an explicit probe rather than a predicate.

  How strong "supported" is here is worth stating plainly rather than settling: `requires-python`
  admits 3.14, but the trove classifiers stop at 3.13, `.python-version` pins 3.11.15, and the
  owning shard pins 3.12. So 3.14 is reachable but neither claimed nor exercised. That caps the
  severity — it does not make a silently-wrong diagnosis in shipped code correct.

  The generalisable rule is about the *direction* of the divergence. A call that raises where you
  expected a value fails loudly. A call that returns a value where you expected a raise leaves the
  handler beneath it **present and inert** — code that reads as a handled case while handling
  nothing, indistinguishable from correct on inspection and on any interpreter that still raises.
* The correct probes are `open()` and `iterdir()`, which ask the kernel the same question and get
  the same answer everywhere. `iterdir` also answers *absent* vs *unlistable* in one call, so the
  divergent call is not needed at all.

Removed **three** times in one module: `load_index`'s `exists()`; a `specs_root.exists()` guard
added while fixing something else; and `candidate.is_dir()` on mission directories. There is now a
**standing AST guard** — `test_ownership_module_has_no_unguarded_eacces_divergent_stat_call` —
which permits these calls only inside a `try`.

**What would overturn the ban:** a supported-interpreter floor at 3.14+, at which point the
divergence disappears. It has not been reached. **What detects a regression:** the AST guard reds.

## Identity is a **detector**, never an **actuator**

`from X import f` binds by value. Patching the shared module's definition site is therefore
**inert** at both decision points — measured: after patching the definition alone, both decision
points still returned the pre-patch value. **No module or package layout changes that.**

What the single-module form buys is *detection*: the definition site **is** the imported name, so
patching it makes the identity assertion red. Under the earlier package form the same patch was
inert **and** the assertion stayed green — an undetectable no-op.

> The single-module form converts a silent no-op into a **detected** one. It does not make
> one-name patching effective.

Recording this closure as *"the patch now reaches both decision points"* would re-arm the exact
error it corrects.

**What would overturn this:** a mutation experiment showing a definition-site patch changing a call
site's behaviour without any change to the import form.

## Consequences

### Positive

* One place to edit the refusal policy, and a stated invariant a reviewer can apply to a new
  construction site without re-deriving six incidents.
* The bug class is named in the form that generalises (provenance), so the next instance is
  recognisable even when it does not look like a path.
* Three limits are on the record — the guard's syntactic reach, C-009's unidentifiability, and
  bind-mount invisibility — so none of them can be mistaken for a green.

### Negative / accepted trade-offs

* The ownership answer is deliberately weaker than operators may expect: it can refuse, but it can
  never tell you *who* owns the decision. That is C-009, not an omission.
* Containment is asserted at **three** depths — `ownership.py:303`, `:387`, `:440`. A **fourth**
  would need a fourth assertion; the pattern is not self-extending. An earlier draft said two,
  omitting the pre-existing mission-candidate check at `:387` — which meant a reader auditing
  the module against this ADR would find an assertion the ADR implied should not yet exist,
  and could not tell whether it was the pattern extending itself or an undocumented addition.
* `decision widen` remains the weakest of the four SaaS construction sites by design — its subject
  is not derived from its root — and it is bounded by a check rather than by structure.

### Neutral

* `egress.py` is classified INTEGRATION, so it may reach `specify_cli.sync`. The layering rule did
  not force the registry route; the single-derivation ground did.
* The earlier per-transport `*/egress_consent.py` modules are deleted, not shimmed.

### Confirmation — and what this ADR does **not** prove

The criterion attached to this ADR (SC-019) is a **grep-gate**, and its own text says so:

```
grep -rn "resolve_egress_consent\|ConsentedBatch\|project_egress_refusal" docs/adr/3.x/ docs/context/
```

must return a non-zero count with the file named. **A file containing only those three search
terms passes it.** That is accepted rather than papered over — the alternative pins prose wording,
and this document's value is in being read, not in being matched. **So its content is a review
item, not a criterion.** If you are here to check the boundary, read the three decisions; do not
trust the green.

Two further honesty notes, so a successor does not re-take measurements that were never made:

* Every green on this mission's test surface was taken as an **isolated single-file run** (#3115's
  sync half is open, deferred to #3136). A full-suite red on these files is not attributable to
  them.
* No CI run has been *observed* executing the shard that carries the consolidated module's tests.
  The claim that it runs rests on a parse of the workflow YAML plus a reading of the job's `if:`,
  which agree — but agreement between two readings of the same file is not an execution.

## Alternatives considered

* **A uuid-typed seam** (`resolve(project_uuid)` instead of `resolve(Path)`). Rejected as the
  *fix*, kept as optional cleanup: a type cannot express provenance, and the uuid can be derived
  from ambient context just as easily as the path was.
* **Re-resolve token and team from the owning root.** Not implementable: it requires identifying
  project B, which C-009 forbids with the data that exists.
* **Keep two per-transport presentations and parameterise them.** Rejected — that is two editable
  presentations wearing one interface, which is the defect, not its repair.
* **A ULID shape check at the CLI as the bound.** Rejected as *the* bound and kept as
  defence-in-depth: a well-formed ULID present in another project's ledger is exactly the attack,
  so shape proves nothing about ownership. The claim that the exposure was benign "because the id
  is a ULID and therefore carries no engagement name" was **measured false** — the value is
  interpolated raw into the request line, so any text an operator types reaches the wire.

## More Information

* `src/specify_cli/egress.py` — the one presentation, the attribution precondition, and the
  per-site enumeration of every construction site that must satisfy it.
* `src/specify_cli/decisions/ownership.py` — the positional-ownership search, the three
  *could-not-look* conditions and their distinct operator actions.
* `tests/specify_cli/saas_client/test_client_consent_gate_3030.py`,
  `tests/sync/tracker/test_saas_client_consent_gate_3030.py` — the two syntactic attribution
  guards.
* `tests/specify_cli/decisions/test_ownership_3111.py` — the containment and EACCES guards,
  including the standing AST guard on divergent `stat` calls.
* [Glossary: engagement](../../context/identity.md#engagement) — why a mission slug is
  confidential.
* Issues: #3110 (consolidation), #3111 (the laundering instance), #3030 (the boundary's origin),
  #3136 (the deferred sync half of #3115).
