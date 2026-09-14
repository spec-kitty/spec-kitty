# WP04 Review Feedback #1 — REJECT

**Reviewer**: independent reviewer (curator lens)
**Commit under review**: `ab7dc7782` — `packs/built-in/styleguides/drupal-security-performance.styleguide.yaml` (193 lines, +193/-0)
**Verdict**: **Reject** — one BLOCKER (factual, user-harming), two minors.

The structural work is good. Nine patterns, all with paired examples, zero name overlap with WP03,
a genuinely strong personalization-leak entry and a genuinely strong credential entry. The reject is
on a single sentence that is factually wrong and actively misleads — which is precisely the class of
defect C-S8 and NFR-006 exist to catch.

---

## BLOCKER — B1: the `accessCheck` version claim is wrong (C-S8, NFR-006)

### What the file says

Two places:

`principles[1]`:
> "Access-check every entity query: `accessCheck(TRUE)` is required from Drupal 10.2 and mandatory in Drupal 12."

`patterns[Entity Query Access Check].description`:
> "`accessCheck(TRUE)` is required on entity queries from Drupal 10.2; omitting it raises deprecation
> warnings today and becomes mandatory in Drupal 12."

### What is actually true

Verified against the official Drupal change record **[node/3201242 — "Access checking must be
explicitly specified on content entity queries"](https://www.drupal.org/node/3201242)**, plus the
canonical deprecation message emitted by core:

> `Relying on entity queries to check access by default is deprecated in drupal:9.2.0 and an error
> will be thrown from drupal:10.0.0.`

| | Claimed | Actual |
|---|---|---|
| Deprecated from | Drupal 10.2 | **Drupal 9.2.0** |
| Current behaviour on Drupal 10/11 | "raises deprecation warnings today" | **throws an error** |
| Becomes mandatory in | Drupal 12 | **Drupal 10.0.0** (already enforced) |

Change-record metadata: *Introduced in branch* `9.2.x`, *Introduced in version* `9.2.0`.

I also searched drupal.org specifically for a Drupal 10.2-scoped `accessCheck` change record to see
whether the claim could be rescued by some later, narrower change. **There is none.** node/3201242 is
the only change record governing this requirement.

### Why this is a blocker, not a nit

This profile targets Drupal 10.x / 11.x (the source guide says so at its line 23). On those exact
versions, omitting `accessCheck()` on a content entity query is a **fatal error**. The styleguide
tells the reader it is a warning they have until Drupal 12 to address. A developer trusting this
guidance would deprioritise a change that breaks their site today. Wrong-and-reassuring is worse than
silent.

### Aggravating detail

The file's own `references` block cites the refuting source:

```yaml
- "Drupal.org: entity query access checking change record -- https://www.drupal.org/node/3201242"
```

The correct change record was cited but not read. The WP prompt's Risks table
("Getting the `accessCheck` versions wrong | C-S8 spot-checks this claim; **verify against Drupal's
own change record**") and its Reviewer Guidance ("Verify the version claims in T022 against official
Drupal documentation — a wrong version here actively misleads") both directed exactly this check.

### Mitigating detail — and why it still does not save the commit

**The implementer conformed to the written contract.** The error is upstream:

- The amazee.io source is wrong at its line 701: *"Drupal 10.2+ requires explicit access checking on
  entity queries. Omitting it throws deprecation warnings and will be required in Drupal 12."*
- `contracts/styleguide-toolguide-contract.md` **C-S8, line 158** copied that error verbatim into the
  mission contract as what the file "Must state".

So T022's checkbox "Version claims match C-S8 exactly" was legitimately satisfied. But C-S8's stated
purpose is *"Content assertions a reviewer can verify against official Drupal documentation. These
exist because schema validity says nothing about whether the advice is true."* A C-S8 row that fails
its own verification is a defect in C-S8, not a licence to ship the falsehood.

### Required remediation

**This needs two coordinated changes — do not silently diverge from the contract.**

1. **Escalate to the orchestrator to amend C-S8 line 158.** Proposed corrected row:

   | Claim | Must state |
   |-------|-----------|
   | `accessCheck(TRUE)` | Explicit `accessCheck()` deprecated from Drupal 9.2.0; an error is thrown from Drupal 10.0.0, so it is already mandatory on Drupal 10/11. `accessCheck(FALSE)` remains a legitimate, explicit, commented choice for internal queries. |

2. **Then correct both sites in the styleguide.** Suggested wording:

   `principles[1]`:
   > "Access-check every entity query: explicit `accessCheck()` has been required since Drupal 9.2 and
   > throws an error from Drupal 10.0 — on Drupal 10/11 an unchecked query is a hard failure, not a warning."

   `patterns[Entity Query Access Check].description` opening:
   > "Explicit `accessCheck()` on content entity queries was deprecated in Drupal 9.2.0 and throws an
   > error from Drupal 10.0.0 — on any supported Drupal (10/11) an entity query without it fails
   > outright, so this is a correctness requirement, not a lint. …"

   Keep the rest of that description unchanged — the `accessCheck(FALSE)` treatment and the WP03
   cross-reference are both correct and well-judged.

3. **Record the upstream error.** The profile distils a source that is wrong here. Note in the WP
   notes (and for WP08) that the styleguide deliberately **corrects** the source at anti-pattern 7
   rather than propagating it, so a later fidelity audit does not "restore" the error as a
   faithfulness fix. Consider a short `references` annotation to the same effect.

---

## Minor — M1: C-S8's Twig row is only partly satisfied (low)

C-S8's Twig escaping row requires the guidance to state: *"use `#type => 'processed_text'` or
`check_markup()` for intentional HTML"*. Source anti-pattern 3 says the same.

WP04's `Twig Output Escaping` good_example instead uses `{{ comment.body.processed }}` and never
names `#type => 'processed_text'` or `check_markup()`. The `.processed` idiom is valid Drupal Twig
and not wrong, but it is not what C-S8 asks the file to state, and T021 assigned anti-pattern 3 to
this file.

Partially mitigated: WP03's `Twig Auto-Escaping` entry *does* name `#type => 'processed_text'`, so
the pair covers the requirement jointly. Either add the named construct to WP04's entry, or record
explicitly that WP03 carries that half of C-S8's Twig row.

## Minor — M2: `#markup` used two patterns after telling readers not to (low)

`Cache Contexts For Personalized Output` builds both examples with:

```php
'#markup' => $this->t('Welcome back, @name', ['@name' => $account->getDisplayName()]),
```

This is **technically safe** — `t()`'s `@` placeholder escapes via `Html::escape()` — so it is not a
security defect. But it sits in visible tension with this same file's `Plain Text Over Markup`
pattern, and `getDisplayName()` is user-controlled data, which is exactly the shape that pattern
warns about. A reader skimming for the house style gets a mixed signal. Prefer `#plain_text`, or
restructure the example so the cache-context point is made without `#markup` carrying user data.

## Informational — I1: example formatting diverges from WP03 (no action required in WP04)

WP04's PHP examples open with `<?php`; WP03's are bare fragments (`$nids = ...`). Both are internally
consistent; the inconsistency is only visible across the pair. Flagging for WP08 to normalise at
integration if it cares.

---

## What I verified and what passed

Evidence I ran personally, in
`/Users/nicolas/Projects/spec-kitty/.worktrees/drupalling-dries-profile-01M28X69-lane-d`:

| Check | Method | Result |
|---|---|---|
| Scope: one file only | `git show --stat ab7dc7782` | **PASS** — 1 file, +193/-0, no `*.graph.yaml` |
| Line count 150–200 | `wc -l` | **PASS** — 193 |
| Valid YAML | `yaml.safe_load` | **PASS** |
| Loads via repository | `pytest -k security_performance` → `test_drupal_security_performance_styleguide_loads` | **PASS** (WP01 presence assertion) |
| Schema shape | diffed top-level + pattern keys vs `python-conventions.styleguide.yaml` | **PASS** — identical (optional `anti_patterns` absent; patterns carry bad/good) |
| 8–10 principles | parsed | **PASS** — 9 |
| Every `bad_example` paired with `good_example` | parsed all 9 patterns | **PASS** — 0 unpaired |
| **C-S3 disjointness with WP03** | **ran the T025 script for real** — extracted `drupal-conventions.styleguide.yaml` from `kitty/…-lane-c` (where WP03 has landed) and compared | **PASS — `overlap: set()`** |
| Anti-pattern map 3/6/7/10/11 | cross-read source list at lines 690–730 | **PASS** — map is accurate |
| No WP03 anti-patterns (1,2,4,5,8,9,12,13,14) written here | compared both pattern lists | **PASS** — none |
| Personalization leak framed as security incident | read entry | **PASS — strong** |
| Credential entry: history retention ⇒ rotation | read entry | **PASS — strong** |
| Provenance credited (FR-010) | read `references` | **PASS** — amazee.io `drupal-agents-md` (Vanilla) + URL |
| No invented thresholds | read `tooling`, `max-age` values | **PASS** — `3600`/`range(0,50)` are illustrative, not asserted standards |
| `accessCheck(FALSE)` exception covered | read entry | **PASS** — cron-sweep case, explicit and commented |
| **`accessCheck` version claim (C-S8)** | **drupal.org change record node/3201242 + core deprecation message + targeted search for a 10.2 record** | **FAIL — see B1** |

### The C-S3 disjointness check WAS run

Contrary to the implementation note, WP03's `drupal-conventions.styleguide.yaml` **is** available —
it has landed on `kitty/mission-drupalling-dries-profile-01M28X69-lane-c`. I extracted it with
`git show` and ran T025's script against it:

- WP03 patterns (17): Constructor Dependency Injection, Entity Query Over Raw SQL, Config Versus
  State, Plugin With Annotation, Settings Form On ConfigFormBase, Route And Controller, Thin Module
  File, Focused Form Alter, Views Data With Table Aliases, Twig Auto-Escaping, Library Declaration,
  Drupal Behaviors, Preprocess Function, Render Array Over Markup, Avoid Hardcoded IDs And Paths,
  Entity Type Manager Over Deprecated Loaders, Injected Request Over Superglobals
- WP04 patterns (9): Twig Output Escaping, Plain Text Over Markup, Entity Query Access Check, Render
  Array Cacheability, Cache Contexts For Personalized Output, Cache Tag Invalidation, Credentials Out
  Of Version Control, Query Efficiency, Batch And Queue For Long Operations
- **`overlap: set()`**

I checked the two semantically adjacent name pairs by hand — WP03 `Twig Auto-Escaping` vs WP04 `Twig
Output Escaping`, and WP03 `Entity Query Over Raw SQL` vs WP04 `Entity Query Access Check`. In both
cases **WP03 explicitly cross-references this file** ("See drupal-security-performance for the |raw
prohibition" / "see drupal-security-performance for the full access-check treatment") and WP04
cross-references back. The boundary is deliberate and correctly drawn on both sides. C-S3 is
genuinely satisfied, not merely satisfied by renaming.

### Failures correctly attributed elsewhere (not WP04's)

`pytest tests/doctrine/styleguides/test_drupal_styleguide_presence.py` → 10 failed, 1 passed. Every
failure references another package's artifact and none is WP04's:

- `agent_profile:drupalling-dries` missing → **WP02**
- `drupal-conventions` styleguide not in this worktree → **WP03** (it exists on lane-c; this is a
  lane-isolation artefact, not an absence)
- `toolguide:drupal-review-checks` missing → **WP05**
- graph-vs-filesystem disagreement / `suggests` edges absent → **WP07** (graph regeneration; STALE is
  expected and WP04 correctly did not touch any `*.graph.yaml`)

Notably `test_new_styleguide_ids_are_shipped_on_disk` fails *only* because `drupal-conventions` is
absent from this lane — `drupal-security-performance` is present in the shipped-ids set.

---

## Summary

Reject on **B1** alone. The remediation is two sentences in the styleguide plus a C-S8 amendment —
small in diff, but it must go through the contract rather than around it. Address M1 and M2 in the
same pass. Everything else in this commit is sound, and the cacheability and credential entries are
better than the contract required.
