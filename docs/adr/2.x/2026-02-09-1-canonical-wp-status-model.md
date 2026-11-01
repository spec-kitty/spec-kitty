---
title: Canonical WP Status Model Using Append-Only JSONL Event Log
description: Replaces five mutable status artifacts with one append-only JSONL event log and a derived snapshot, giving work package state a single, replayable authority.
status: Accepted
date: '2026-02-09'
doc_status: active
kind: ADR
updated: '2026-02-09T00:00:00Z'
---

## Context and Problem Statement

Work package and feature status in Spec Kitty is spread across multiple mutable artifacts: `meta.json`, `tasks.md` checkboxes, WP front-matter `lane` fields, `.kittify/` workspace context, and target-repo implementation state. This distributed authority causes observable failure modes:

1. **Phantom state**: Lane updates written to non-authoritative artifacts appear real but aren't canonical.
2. **Split-brain**: Planning artifacts say one thing while implementation evidence says another.
3. **Monotonic conflict resolution**: "Most done wins" can override a valid review rollback.
4. **Unauditable force transitions**: Status can be changed without durable record of who, when, or why.
5. **Workspace residue**: Stale worktree contexts cause phantom ownership and noisy operations.

The system needs a single canonical, auditable source of truth for WP and feature status that supports concurrent multi-agent work, offline operation, and deterministic merge.

## Decision Drivers

* **Auditability** — Every status change must be recorded with actor, timestamp, and context
* **Git-native merges** — Concurrent branches must merge without manual conflict resolution
* **Offline-first** — Must work entirely in git with no network dependency
* **Replayability** — Must be able to reconstruct state at any historical point
* **Multi-agent safety** — Multiple human and AI agents must be able to work concurrently

## Considered Options

* **Option 1:** Front-matter / tasks.md canonical (current implicit model)
* **Option 2:** Mutable snapshot-only (`status.json`) canonical
* **Option 3:** SQLite file in git
* **Option 4:** External database canonical (SaaS Postgres)
* **Option 5:** Append-only JSONL event log with derived snapshot

## Decision Outcome

**Chosen option:** "Option 5: Append-only JSONL event log with derived snapshot", because it provides git-friendly merges (line-append), full audit trail, event replay, offline capability, and deterministic merge semantics for concurrent multi-agent work.

### Implementation

* **Canonical state**: `kitty-specs/<feature>/status.events.jsonl` — per-feature append-only log
* **Derived state**: `kitty-specs/<feature>/status.json` — materialized snapshot (regeneratable)
* **Generated views**: `tasks.md` status sections and WP front-matter `lane` field are generated from the snapshot, never edited as authority
* **Read/write contract**: All state changes append to the event log; a deterministic reducer materializes `status.json`

### Consequences

#### Positive

* Git-friendly — appending lines to JSONL rarely causes merge conflicts
* Full audit trail — every status change is an immutable record with actor, timestamp, and context
* Replayable state — can reconstruct status at any historical point
* Offline-capable — entire system works in git with no network dependency
* Foundation for deterministic merge (see ADR 2026-02-09-3)

#### Negative

* No direct querying without materializing the snapshot first
* JSONL file grows unbounded without compaction strategy
* Extra tooling required — reducer, materializer, and validator must be built
* Migration complexity — existing WP status must be bootstrapped into event log format

#### Neutral

* Extends the event-sourcing principle from the SaaS event log to local git-based project status tracking using JSONL instead of a database
* `status emit` automatically materializes after each event, so reads are always fast

### Confirmation

* `status validate` CI check confirms materialized `status.json` matches reducer output, catching any drift
* Phased migration (PRD Section 14) reduces risk: immediate hardening → dual write → read cutover → cross-repo native

## Pros and Cons of the Options

### Front-matter / tasks.md canonical (current model)

Continue using WP front-matter `lane` fields and tasks.md checkboxes as the source of truth.

**Pros:**

* Already exists — zero migration cost
* Human-readable and editable in any text editor
* Familiar to all current users

**Cons:**

* No audit trail — status changes overwrite previous values
* Merge conflicts on concurrent edits to the same YAML front-matter block
* No transition validation — any state can be written directly
* Multiple artifacts can disagree with no reconciliation mechanism

### Mutable snapshot-only (`status.json`)

Replace front-matter with a single `status.json` file per feature as authoritative source.

**Pros:**

* Structured and queryable (JSON)
* Single file replaces multiple scattered fields

**Cons:**

* No history — current state only, previous states lost on write
* Merge conflicts on concurrent writes (entire JSON object is one blob)
* No audit trail for forced transitions or rollbacks

### SQLite file in git

Store status in a SQLite database file committed to git.

**Pros:**

* Powerful querying (SQL)
* Transactional writes (ACID guarantees)

**Cons:**

* Binary diffs in git — poor merge semantics under concurrent writers
* Reduced review clarity — reviewers cannot see status changes in pull request diffs
* Page-level conflicts require manual resolution or custom merge drivers

### External database canonical

Store status in the SaaS platform's Postgres instance.

**Pros:**

* Powerful querying and real-time access
* Native concurrent write support

**Cons:**

* Requires centralized service — violates offline-first principle
* Contradicts non-goal: "Not replacing git with an online control plane"
* CLI cannot function without network access

## More Information

**Related ADRs:**
* ADR 2026-02-09-2 (WP Lifecycle State Machine) — consumes events from this log
* ADR 2026-02-09-3 (Event-Log Merge Semantics) — operates on this log
* ADR 2026-02-09-4 (Cross-Repo Evidence Completion) — extends this log with evidence payloads

**References:**
* Martin Fowler: Event Sourcing — https://martinfowler.com/eaaDev/EventSourcing.html
* JSONL Specification — https://jsonlines.org/
* PRD: Feature Status State Model Remediation (Sections 2, 3, 5, 6, 15)
