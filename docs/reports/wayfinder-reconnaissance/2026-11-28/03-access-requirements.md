---
doc_status: draft
updated: '2026-11-28'
---

# Outstanding access requirements

The session can see these repositories but has not attached them. Attaching is a scope decision for the human architect. All use would be read-only: clone, read, and run analysis in disposable copies. Nothing would be pushed to them.

Missing access is recorded as a coverage limit. It is never treated as evidence of an architectural defect.

## 1. Repositories requested

| Priority | Repository | Needed for | What is lost without it |
|---|---|---|---|
| High | `spec-kitty/spec-kitty-planning` | A: the programme constitution (`PROGRAM.md`), planning ADRs and the 2026-09-27 shared-architecture review that core documents cite as a target architecture. C: programme decisions that date the remediation | The approved-plan view rests on core's citations of documents that cannot be read; the prior review's findings cannot be reused or checked |
| High | `spec-kitty/EXPERIMENTAL-spec-kitty` (archived) | C: issues and pull requests of the EXPERIMENTAL line, 2026-08-19 to 2026-09-05, for corrective chains and review intensity (M01g, M02) | Those measures are not assessable for that line |
| High | `spec-kitty/spec-kitty-tracker` | B, D: source of a package core depends on by range; its contract surface | Assessed from the published wheel only |
| Medium | `spec-kitty/spec-kitty-orchestrator` | F: the external consumer of the orchestrator API; D: an existing external consumer of a core contract | M07 classifies that locus from core's side only |
| Medium | `spec-kitty/EXPERIMENTAL-spec-kitty-end-to-end-testing` | E: the cross-repository harness that the events repository requires as a check; M02 detection routes | Cross-repository gate coverage is described from workflow files only |
| Medium | `spec-kitty/fleet-kitty`, `spec-kitty/spec-kitty-container` | F: where execution responsibilities sat, or were meant to sit, outside core | Recorded as external loci of unknown content |
| Medium | `spec-kitty/spec-kitty-planning-archive` | A, C: decisions before the planning repository's current history, if `spec-kitty-planning` proves incomplete | Requested only if needed |
| Low | `spec-kitty/event-router` | A, C: the hosted surfaces removed from core in 2026-10; what the produce seam was designed against | Historical context only |
| Low | `spec-kitty/spec-kitty-pack-composer`, `spec-kitty/spec-kitty-mcp` | D: other consumers of public contracts | Fewer external-consumer data points |
| Low | `spec-kitty/EXPERIMENTAL-spec-kitty-events`, `spec-kitty/EXPERIMENTAL-spec-kitty-tracker` (archived) | C: tracker references cited in the events changelog | Some references stay unresolved |

Not requested: `spec-kitty-saas`, website, design and brand repositories. They serve hosted or presentation concerns outside this investigation.

One question for the architect: the pre-2026-09-07 public line was tracked under the `Priivacy-ai` organisation. If those issues and pull requests did not move with the repository, read access to that tracker would be needed for M01g and M02 before the org move. The investigation will check what transferred before asking.

## 2. Surfaces already available

- Issues and pull requests of the five in-scope repositories, read-only.
- PyPI and the events service release assets.
- The published documentation site.

## 3. Blocked or constrained in this environment

| Item | State | Handling |
|---|---|---|
| `spec-kitty-events` Gradle build | Blocked: dependency retrieval from Maven Central is rate-limited through the proxy | Retried at the start of workstreams B and D. If still blocked, Events Java is analysed statically (ruling R11) and marked so |
| Container images from Docker Hub | Rate-limited | A mirror registry works; network access from inside containers is untested |
| Docker daemon | No system daemon; one can be started in scratch space | Used only for disposable environments |
| `spec-kitty-cli` 4.0.0rc9 | Not published; 4.0.0rc8 is the latest pre-release, 3.2.7 the latest stable | The released view uses rc8 and 3.2.7; `head` is assessed from source |
| GitHub GraphQL and the `gh pr` commands | Not available | REST and the GitHub connector are used instead |

## 4. Decisions asked of the architect

1. Which of the repositories in section 1 may be attached, read-only.
2. The maintenance window for H01, as two dates or two revisions, recorded before any series is shown (pre-registration section 2.2).
3. Whether the outside observer's predictions will be collected by the architect and returned for recording, or whether the packet should be delivered another way.
