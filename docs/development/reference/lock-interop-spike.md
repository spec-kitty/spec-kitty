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
- **Windows:** `FileChannel.lock` is enough. It (`LockFileEx`) and `msvcrt.locking` (the C runtime's `LockFile`) take byte-range locks that overlap at byte 0.
- **NO-GO for `FileChannel.lock` on Linux:** it takes an `fcntl` record lock, which Linux keeps independent of `flock`. Neither side excludes the other.
- **`FileChannel.lock` is GO on macOS,** because the macOS lock manager makes `fcntl` and `flock` locks conflict. That does not help: Linux needs the FFM `flock(2)` call anyway, and one Java code path for both POSIX systems is simpler.

Appends from both sides, interleaved under load, land as whole lines. Each line is byte-identical to what its writer wrote, and both the Python status reader and the Java `LedgerLineDecoder` accept the whole log.

Exclusion matters even though ADR D-4 hands each log over whole, one release at a time: an older CLI, still installed in another checkout of the same repository, keeps appending to a log the service already owns, and both take the lock files under the shared git common dir.

This is the first work package of #6193 (Mission Write API step 3, epic #6117). Nothing here changes the CLI, the event row (the `spec-kitty-events` #92 envelope is not used) or any command.

## What was tested

The harness drives the production code on the Python side, never a copy: `kernel.event_log_append.event_log_lock_path`, `event_log_lock` and `append_event_log_lines`, and `kernel.locks.machine_file_lock`.

| Part | Where |
|---|---|
| Python peer | `scripts/ci/lock_interop_peer.py` (unit tests: `tests/ci/test_lock_interop_peer.py`) |
| Java harness | package `org.speckitty.missionstatus.spike.lockinterop` in the test sources of the `event-log` module of `services/mission-status-api` |
| CI evidence | the `lock-interop` job of `.github/workflows/mission-status-api.yml` (ubuntu-24.04, macos-15, windows-2025; GraalVM CE 25.0.2) |

`LockInteropSpikeTest` runs once per Java lock. `java-filechannel` is `FileChannel.tryLock()` over the whole file, on every OS. `java-ffm-flock` is `flock(fd, LOCK_EX | LOCK_NB)` through FFM, on Linux and macOS. Each run uses a fresh git repository, so the lock file is the real `<git-common-dir>/spec-kitty-locks/event-logs/<digest>.lock`. The harness checks four things:

1. **Controls.** Each side acquires the free lock, so a "contended" result is never vacuous. Both sides render a row with the same bytes.
2. **Cross-holding.** Python holds the lock and Java tries it; Java holds it and Python tries it.
3. **Overlap under load.** Three Python processes and the Java writer start together on a barrier. Each repeatedly takes the lock and creates a sentinel file with `O_EXCL` inside it. A create that finds the sentinel present is an overlap: two holders inside the critical section at once. Before each round, each side probes the lock without waiting and counts the probes that find it held ("contended"), which proves the writers really met. The count is a lower bound: an overlap outside a holder's 2 ms stay inside the critical section is not seen.
4. **Appends under load.** Three Python processes (`append_event_log_lines`, one row per call) and the Java writer append at once. The Java writer appends under its lock: it refuses a torn tail, writes the whole line and its LF in one write on an `APPEND` channel, then forces it to disk. The rows are lane transitions in today's `status.events.jsonl` shape, serialised as `json.dumps(row, sort_keys=True)`. Then:
   - every line must be one of the submitted rows, byte for byte, and each must appear exactly once;
   - the file must end with LF and hold no CR (the Windows byte rules of #4182);
   - the Python reader (`specify_cli.status.store.read_events`) must return every row (it reads the file after every writer has finished, as the Java decoder does);
   - `LedgerLineDecoder.decode` must classify every line as a status line, with no tail.

   - the lines must switch between the Java writer and a Python writer at least once ("cross-language switches"), so the appends really interleaved.

A run is **GO** when both cross-holding checks exclude, the Java writer found the lock held by a Python writer at least once, there are zero overlaps, no append is refused, and the appends pass every check above. The job fails when a run records no result (a skipped test or a filter that matches nothing).

## Evidence

CI run [40557031791](https://github.com/spec-kitty/spec-kitty/actions/runs/40557031791) (head `21751d8`); all three `lock-interop` jobs passed, including the guard that requires one recorded result per Java lock.

| OS | Java lock vs Python lock | Python holds: Java excluded | Java holds: Python excluded | overlaps / rounds | contended (Java / Python) | refused / rows | intact / Python reader / Java reader | switches (cross-language / all) | verdict |
|---|---|---|---|---|---|---|---|---|---|
| linux | java-ffm-flock vs fcntl.flock | true | true | 0 / 1730 | 147 / 105 | 0 / 1268 | true / true / true | 484 / 490 | **GO** |
| linux | java-filechannel vs fcntl.flock | false | false | 172 / 495 | 0 / 12 | 0 / 743 | true / true / true | 516 / 520 | **NO-GO** |
| macos | java-ffm-flock vs fcntl.flock | true | true | 0 / 792 | 110 / 109 | 0 / 1950 | true / true / true | 474 / 492 | **GO** |
| macos | java-filechannel vs fcntl.flock | true | true | 0 / 667 | 99 / 103 | 0 / 1214 | true / true / true | 444 / 453 | **GO** |
| windows | java-filechannel vs msvcrt.locking | true | true | 0 / 1779 | 187 / 120 | 0 / 3382 | true / true / true | 560 / 567 | **GO** |

Each row is the `lock-interop result:` record the test writes to `event-log/build/lock-interop/` (artefact `lock-interop-<os>`) and to the job's step summary. The assertions in `LockInteropSpikeTest` pin these outcomes, so a JDK or OS change that moves one turns the job red:

- GO for `java-ffm-flock` on Linux and macOS, and for `java-filechannel` on macOS and Windows;
- no exclusion for `java-filechannel` on Linux.

The workflow runs the job when the Python peer, `src/kernel/locks.py` or `src/kernel/event_log_append.py` change, so a change on the Python lock side re-runs the evidence. The job is not part of `mission-status-api-gate`.

**Without exclusion, the harm is real.** In local Linux runs with `java-filechannel`, the Python append read the log while a Java write was in flight and refused a legitimate append with `EVENT_LOG_TORN_TAIL`. The critical-section count shows the same race directly: about one overlap in three rounds. O_APPEND keeps each line whole on Linux, so the damage shows up as refusals and races in the torn-tail check, not as torn lines.

## What the write service needs (follow-ups, not done here)

- **The first handover is not cleared by this spike.** ADR 2026-10-22-1 names the glossary logs as the first file the service takes over. This spike proves status-shaped rows. The glossary handover still needs:
  - byte parity with `spec_kitty_events.persistence.serialize_record`, which writes the glossary rows;
  - a ruling on the torn-tail policy: the glossary writer repairs a torn tail (it moves the fragment to `<ledger>.torn` under the leaf lock `<ledger>.lock`, `src/glossary/events.py`), while the Java append here refuses one;
  - acceptance of the Java-written log by the glossary reader.
- **Lock path.** The harness hands Java the lock path the Python peer computes. The service must compute `<git-common-dir>/spec-kitty-locks/event-logs/<digest>.lock` itself. `<digest>` is the first 32 hex characters of the SHA-256 of `os.path.normcase(resolved anchor path)` in UTF-8; `normcase` lowercases the path and turns `/` into `\` on Windows. A parity test against `event_log_lock_path` must also cover the git common dir seen from a linked or lane worktree, and the fallback outside a git repository (`<anchor>.event-log.lock` beside the log).
- **The status lock.** `status.events.jsonl` is not appended through the event-log lock: it keeps the Mission status lock (`specify_cli.status.locking`, `<key>.status.lock`). It uses the same `kernel.locks` primitive, so the per-OS result above carries over, but its path rule must be ported too before that log is handed over.
- **Production hardening of the Java lock.** Open the lock file with `O_CLOEXEC` and `O_NOFOLLOW`, as `kernel.locks` refuses a symlink (`open_no_follow`). Make the held lock's release idempotent: closing a raw descriptor number twice can close a reused descriptor and drop another holder's lock.
- **Append parity.** The spike's Java append checks the tail by path, then writes on a second channel. The service should check and write through one descriptor, and cut the log back to its size before the write on a short or failed write, as `append_event_log_lines` does.
- **Native image.** The FFM downcall was proven on the JVM (GraalVM CE 25.0.2). A native image needs the downcall registered in its reachability metadata. This is not tested here.
- **ADR wording.** D-4 says the service takes the lock files "with `flock(2)` semantics (through FFM)". `flock(2)` does not exist on Windows. Proposed amendment: "`flock(2)` through FFM on Linux and macOS, `FileChannel.lock` (`LockFileEx`) on Windows".
- **One holder per JVM.** `FileChannel.lock` throws `OverlappingFileLockException` when a second thread of the same JVM locks the same file. `flock` taken through two descriptors in one process blocks the second. ADR D-4 already serialises writes in process, which avoids both.
