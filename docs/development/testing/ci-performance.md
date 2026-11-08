---
title: CI performance and evidence boundaries
description: Explain how CI reuses immutable inputs without weakening test and coverage evidence.
doc_status: active
kind: Explanation
updated: '2026-11-02T00:00:00Z'
---

# CI performance and evidence boundaries

For maintainers changing the CI pipeline, a faster green is useful only when it still describes the tested revision. Measure time to required checks, aggregate active job time, and dispatch gaps separately. Parallel jobs overlap; their elapsed times cannot be added into a PR latency estimate.

## One owner for each check

CI Router owns Ruff lint/format (including import-boundary rules) and lock validation. Its stable `router gate` waits for both. CI Quality owns wheel construction and the stable `Clean install verification` check. Commit-subject output and advisory Markdown style run as steps rather than separate jobs; they are not represented as enforced commit-message validation.

The wheel optimization is deliberately conservative: only nonempty documentation prose outside declared packaging inputs can omit construction and clean installation. Source, metadata, build hooks, pins, root readme/license, tests, CI configuration, uncertain diffs and non-PR events still verify a real wheel. The selector considers declared metadata/build paths and symlinked input targets. If packaging starts reading another documentation input, declare that input and extend its regression controls in the same change. The stable check still reports on a proven irrelevant change, and a paused PR still refuses.

## Cache candidates are not verdicts

Warmup consumes the caller's checkout. It uses the actual locked events version in PR mode, resolves the upstream release in full mode, syncs the environment and verifies the installed version. It caches dependency material and the managed interpreter rather than a virtual environment with external interpreter symlinks. Pack clones are restored before an editable build hook can fetch; placement still verifies pinned digests. Service extras and host-native assets use distinct cache identities.

The collection-policy action restores results only on trusted default-branch push, schedule and manual runs. PR, merge-queue and other events never restore or publish this policy directory. The key covers all test/helper source content, configuration, dependency lock and interpreter identity. The scanner reads live inputs and checks its digest and HMAC, but the HMAC key travels with the cache: it detects local corruption, not a malicious cache writer. Actions' ref-scoped namespace is the trust boundary. A default-branch source-only edit can reuse an unchanged scan without a new producer job; PRs retain fresh local enforcement. Scratch mutation controls must still observe changed input immediately.

In CI the scanner prints `policy-scan` metrics for source reading/hashing, lock/setup wait, scan/write and cache hit. Compare those with independently named installation, pack placement, selection and pytest steps; a step formerly labeled `uv sync` could contain several minutes of tests.

Cache capacity is an operational concern, not permission to delete all entries. Review actual size, access and dependency-key behavior before changing quotas or retention. Actions cache scope remains part of the trust boundary: PR-produced bytes must not become executable privileged default-branch input.

## Timings describe test identities

Fresh module timing captures retain node identities instead of attaching seconds by collection position. Unchanged identities keep measured weights; new tests receive a deterministic median fallback, and missing/stale identities are reported. Legacy positional captures cannot be assigned identities honestly merely because counts match. Recapture them through the existing capture command and review provenance rather than hand-labeling them.

Do not blindly add shards while dispatch gaps dominate. An additional consolidation shard can reduce computation but repeats setup and consumes another runner slot. Evaluate the complete gate and keep per-test mutable repositories isolated. Module shards do not gain unrestricted internal parallelism from this optimization.

## Failure and coverage truthfulness

Both PR and full-mode module jobs propagate pytest's actual status. Full-mode run-all behavior comes from disabling matrix fail-fast; report upload remains unconditional. A failed shard is never made successful to let its siblings finish.

Nightly Sonar selects coverage only for the checked-out source revision. Missing or unusable matching evidence is reported explicitly; another revision's report is not a fallback. Sonar remains informational rather than a new merge requirement. Dependency/tool caches never replace acceptance scenario execution or cache acceptance verdicts.

Superseded Windows PR runs can cancel one another, while independent mainline pushes retain separate evidence. Existing module/router cancellation, pause-label semantics, historical git consumers and cross-package coverage breadth remain intact.

## Validate a performance change

Use equivalent runners and representative prose-only, charter, consolidation and broad-core changes. Record cold and warm results, selected node-ID unions, coverage/source identity, first-failure latency, job count and abandoned work. Keep mutation controls and actual-shell failure tests. Run focused tests and the bounded fast baseline locally; CI owns full heavy suites. Do not claim a percentage improvement from a structural estimate alone.
