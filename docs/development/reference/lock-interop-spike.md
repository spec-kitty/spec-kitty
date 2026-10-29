---
title: Lock-interop spike (#6193)
description: 'Verdict and CI evidence of the #6193 spike: which Java lock excludes the CLI''s event-log lock on Linux, macOS and Windows, and whether mixed appends pass both readers.'
doc_status: active
updated: '2026-10-27'
audience: docs/context/audience/internal/maintainer.md
type: reference
related:
- docs/adr/4.x/2026-10-22-1-the-java-write-service-is-the-canonical-event-writer.md
- docs/development/reference/events-in-core.md
---

# Lock-interop spike (#6193)

**Verdict: GO for the design of ADR 2026-10-22-1 D-4**, on all three operating systems:

- **Linux and macOS:** the Java writer must call `flock(2)` through the Foreign Function and Memory (FFM) API. That takes the very lock `kernel.locks` takes with `fcntl.flock`.
- **Windows:** `FileChannel.lock` is enough. It and `msvcrt.locking` both take `LockFileEx` byte-range locks that overlap at byte 0.
- **NO-GO for `FileChannel.lock` on Linux:** it takes an `fcntl` record lock, which Linux keeps independent of `flock`. Neither side excludes the other. MACOS_FILECHANNEL_SENTENCE

Appends from both sides, interleaved under load, land as whole lines. Each line is byte-identical to what its writer wrote, and both the Python status reader and the Java `LedgerLineDecoder` accept the whole log.

This is the first work package of #6193 (Mission Write API step 3, epic #6117). Nothing here changes the CLI, the event row (the `spec-kitty-events` #92 envelope is not used) or any command.

## What was tested

The harness drives the production code on the Python side, never a copy: `kernel.event_log_append.event_log_lock_path`, `event_log_lock` and `append_event_log_lines`, and `kernel.locks.machine_file_lock`.

| Part | Where |
|---|---|
| Python peer | `scripts/ci/lock_interop_peer.py` (unit tests: `tests/ci/test_lock_interop_peer.py`) |
| Java harness | `services/mission-status-api/event-log/src/test/java/org/speckitty/missionstatus/spike/lockinterop/` |
| CI evidence | the `lock-interop` job of `.github/workflows/mission-status-api.yml` (ubuntu-24.04, macos-15, windows-2025; GraalVM CE 25.0.2) |

`LockInteropSpikeTest` runs once per Java lock. `java-filechannel` is `FileChannel.tryLock()` over the whole file, on every OS. `java-ffm-flock` is `flock(fd, LOCK_EX | LOCK_NB)` through FFM, on Linux and macOS. Each run uses a fresh git repository, so the lock file is the real `<git-common-dir>/spec-kitty-locks/event-logs/<digest>.lock`. The harness checks four things:

1. **Controls.** Each side acquires the free lock, so a "contended" result is never vacuous. Both sides render a row with the same bytes.
2. **Cross-holding.** Python holds the lock and Java tries it; Java holds it and Python tries it.
3. **Overlap under load.** Three Python processes and the Java writer start together on a barrier. Each repeatedly takes the lock and creates a sentinel file with `O_EXCL` inside it. A create that finds the sentinel present is an overlap: two holders inside the critical section at once.
4. **Appends under load.** Three Python processes (`append_event_log_lines`, one row per call) and the Java writer append at once. The Java writer appends under its lock: it refuses a torn tail, writes the whole line and its LF in one write on an `APPEND` channel, then forces it to disk. The rows are lane transitions in today's `status.events.jsonl` shape, serialised as `json.dumps(row, sort_keys=True)`. Then:
   - every line must be one of the submitted rows, byte for byte, and each must appear exactly once;
   - the file must end with LF and hold no CR (the Windows byte rules of #4182);
   - the Python reader (`specify_cli.status.store.read_events`) must return every row, over the same bytes (same SHA-256);
   - `LedgerLineDecoder.decode` must classify every line as a status line, with no tail.

A run is **GO** when both cross-holding checks exclude, there are zero overlaps, no append is refused, and the appends pass every check above.

## Evidence

CI run [40553799689](https://github.com/spec-kitty/spec-kitty/actions/runs/40553799689) (head `c9d5950`) EVIDENCE_RUN_NOTE

| OS | Java lock vs Python lock | Python holds: Java excluded | Java holds: Python excluded | overlaps / rounds | refused / rows | intact / Python reader / Java reader | verdict |
|---|---|---|---|---|---|---|---|
EVIDENCE_ROWS

Each row is the `lock-interop result:` record the test writes to `event-log/build/lock-interop/` (artefact `lock-interop-<os>`) and to the job's step summary. The assertions in `LockInteropSpikeTest` pin these outcomes, so a JDK or OS change that moves one turns the job red:

- GO for `java-ffm-flock` on Linux and macOS, and for `java-filechannel` on Windows;
- no exclusion for `java-filechannel` on Linux.

**Without exclusion, the harm is real.** In an earlier local Linux run with `java-filechannel`, the Python append read the log while a Java write was in flight and refused a legitimate append with `EVENT_LOG_TORN_TAIL`. The critical-section count shows the same race directly: 170 overlaps in 468 rounds. O_APPEND keeps each line whole on Linux, so the damage shows up as refusals and races in the torn-tail check, not as torn lines.

## What the write service needs (follow-ups, not done here)

- **Lock path.** The harness hands Java the lock path the Python peer computes. The service must compute `<git-common-dir>/spec-kitty-locks/event-logs/<digest>.lock` itself, where `<digest>` is the first 32 hex characters of the SHA-256 of `os.path.normcase(resolved anchor path)` in UTF-8. `normcase` lowercases the path and turns `/` into `\` on Windows. The Java port needs a parity test against `event_log_lock_path`.
- **The status lock.** `status.events.jsonl` is not appended through the event-log lock: it keeps the Mission status lock (`specify_cli.status.locking`, `<key>.status.lock`). It uses the same `kernel.locks` primitive, so the per-OS result above carries over, but its path rule must be ported too before that log is handed over.
- **Native image.** The FFM downcall was proven on the JVM (GraalVM CE 25.0.2). A native image needs the downcall registered in its reachability metadata. This is not tested here.
- **ADR wording.** D-4 says the service takes the lock files "with `flock(2)` semantics (through FFM)". `flock(2)` does not exist on Windows. The Windows half is `FileChannel.lock` (`LockFileEx`), which this spike shows interoperates with `msvcrt.locking`.
- **One holder per JVM.** `FileChannel.lock` throws `OverlappingFileLockException` when a second thread of the same JVM locks the same file. `flock` taken through two descriptors in one process blocks the second. ADR D-4 already serialises writes in process, which avoids both.
