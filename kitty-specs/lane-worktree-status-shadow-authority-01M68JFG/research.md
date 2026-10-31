# Research — lane worktree status shadow authority (#6466)

Recorded during the discovery step, after the reproduction was already run against current `main`
(`4.0.0rc8`, `35318ef51c`). Everything below is evidence gathered from the live CLI and the
resolver seam, not from the issue text alone.

## Q1 — Does the reported divergence still exist, and in which topology?

**Decision**: the reported symptom is `--force` on a routine `for_review` transition, caused by a
status read answering from the wrong copy. It reproduces only through the **lane-worktree-rooted
read**, and only for the branch-flat `lanes` topology.

Evidence (real mission, real lane worktree, built through the orchestrator-api
`start-implementation` surface):

| Topology | `status.events.jsonl` / `status.json` in the lane worktree | Authority | Lane-rooted read |
| --- | --- | --- | --- |
| `lanes_with_coord` (default) | absent — neither file exists in the lane worktree | coordination husk | already resolves the husk |
| `lanes` (branch-flat) | present: the fork-time log (1 event, lane `planned`) | primary / mission-branch copy (3 events, lane `in_progress`) | **answers from the fork-time copy: `planned`** |

`planned -> for_review` is not a legal edge, so the transition refuses and points at `--force`;
that is the reported symptom, reduced to one seam.

## Q2 — Which copy is authoritative?

**Decision**: the **resolved status surface** — the coordination husk on a coordination-routed
mission, the primary/mission-branch copy otherwise. Never the invoking checkout's copy, and never
"whichever file has the newer timestamp".

Evidence: `src/specify_cli/coordination/surface_resolver.py` is the single resolution authority
(FR-001/FR-007) and documents exactly this; `src/specify_cli/status/reducer.py` states the event log
is authoritative and `status.json` is a derived snapshot that can be regenerated from it
(`status/rematerialize.py`, `status/views.py`). The existing changelog records the same rule from
two earlier fixes: coordination missions keep their status log on the coordination branch only
(#5440), and `status.json` is regenerated from the merged event log when it is the only conflict
(#5160 / #4955).

## Q3 — Why does the lane copy still answer at all?

**Decision**: because `resolve_handle_to_read_path` (the single guarded read-side seam) documented
its `repo_root` parameter as "absolute repository root (primary checkout)" but never enforced it. A
caller that handed in a lane worktree root — an agent harness, a script treating `cwd` as the
root, a future surface — got a surface composed from that root, and every downstream read
(primary-meta probe, mid8 cascade, topology classification, composed surface) answered from the
fork-time copy.

Evidence: `MissionStatus.load(repo_root=lane)` already re-anchors correctly (returns the primary
`read_dir`), and `agent tasks status --json` run inside the lane worktree reports `in_progress`. So
the aggregate and the CLI already hold the invariant; only the raw seam did not.

## Q4 — Fix shape

**Decision**: canonicalize the handed root in that one seam, before anything is composed, when the
worktree registry classifies it as a lane worktree (`WorktreeTopology.LANE_WORKTREE`).

Rejected alternatives:

- **Newest-timestamp-wins / copy-sync from the lane worktree** (the issue's proposal 1): makes a
  derived file a second authority and would let a stale copy win; contradicts Q2.
- **A lenient transition guard** (proposal 2 read literally): removes the `--force` by weakening a
  gate. The gate is right; the read it acts on was wrong.
- **Message-only disambiguation** (proposal 3): leaves the wrong answer in place.

Boundaries that must not move, and how they are held: the coordination worktree is itself a linked
worktree and stays the authority (keyed on the classified topology, not on "is a linked worktree");
an independent clone is not a linked worktree and keeps its own checkout; a husk (unregistered) and
an unreadable worktree registry keep today's behaviour (never guess a root).

## Open questions

- None blocking. The lenient diagnostic resolver `candidate_feature_dir_for_mission` still composes
  from the handed root by design (it is not a read authority); if a lane-rooted diagnostic ever
  misleads an operator, re-anchoring it is a separate, smaller fix.
