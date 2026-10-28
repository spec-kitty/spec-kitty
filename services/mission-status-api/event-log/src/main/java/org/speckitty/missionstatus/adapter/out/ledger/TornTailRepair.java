package org.speckitty.missionstatus.adapter.out.ledger;

import java.io.IOException;
import java.lang.System.Logger.Level;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.Path;
import java.nio.file.StandardOpenOption;
import java.time.Duration;
import java.util.Objects;
import java.util.Optional;

/**
 * The Java port of the glossary ledger's torn-tail repair ({@code glossary.events._repair_torn_tail}). A torn tail is what a write cut short
 * by a crash leaves after the last newline. The repair appends those bytes, as one line, to the quarantine file {@code <ledger>.torn}, makes
 * that durable, then cuts the ledger back to its last newline and makes that durable too, so no byte is lost. It runs under the leaf lock
 * {@code <ledger>.lock}, the same lock file the Python repair takes, and re-reads the tail inside it, so a second repairer finds the tail
 * whole and changes nothing.
 *
 * <p>Byte for byte it does what the Python repair does: {@code torn-tail/repair-cases.json} (test resources) holds the goldens both sides
 * are tested against. Only a newline byte ends a line; the fragment is moved as raw bytes and never decoded.
 *
 * <p>An interrupt between the quarantine write and the cut leaves the fragment in both files; a later repair then quarantines it a second
 * time. No byte is lost. As in the Python repair, the new quarantine file's directory entry is not fsynced.
 *
 * <p>The caller decides when to repair. The glossary's Python writer repairs when its append is refused with a torn tail, while holding
 * the interim event-log lock of the log; a Java writer that takes a glossary ledger over must do the same.
 */
public final class TornTailRepair {

  /** Suffix of the quarantine file beside the ledger ({@code glossary.events.TORN_TAIL_SUFFIX}). */
  public static final String TORN_TAIL_SUFFIX = ".torn";

  /** Suffix of the repair's leaf lock file beside the ledger ({@code glossary.events._REPAIR_LOCK_SUFFIX}). */
  public static final String REPAIR_LOCK_SUFFIX = ".lock";

  /** The bounded wait for the leaf lock ({@code glossary.events._REPAIR_LOCK_TIMEOUT_S}). */
  public static final Duration REPAIR_LOCK_TIMEOUT = Duration.ofSeconds(10);

  /** The backward scan for the last newline reads this many bytes at a time ({@code glossary.events._TAIL_SCAN_BLOCK}). */
  static final int TAIL_SCAN_BLOCK = 64 * 1024;

  private static final byte NEWLINE = '\n';
  private static final System.Logger LOG = System.getLogger(TornTailRepair.class.getName());

  /** A repair that moved {@code movedBytes} bytes of torn tail to {@code quarantine}. */
  public record Repair(Path quarantine, long movedBytes) {
    public Repair {
      Objects.requireNonNull(quarantine, "quarantine");
    }
  }

  private TornTailRepair() {}

  /** Repairs {@code ledger} under this OS's ledger lock with the Python repair's timeout. */
  public static Optional<Repair> repair(Path ledger) throws IOException {
    return repair(ledger, LedgerLocks.forThisOs(), REPAIR_LOCK_TIMEOUT);
  }

  /**
   * Repairs {@code ledger}, holding {@code lock} on {@code <ledger>.lock}.
   *
   * @return the repair, or empty when the ledger was empty or ended in a newline (nothing was changed)
   * @throws java.nio.file.NoSuchFileException the ledger does not exist (nothing is created)
   * @throws LedgerLockTimeoutException another holder kept the leaf lock past {@code timeout} (nothing was changed)
   */
  public static Optional<Repair> repair(Path ledger, LedgerLock lock, Duration timeout) throws IOException {
    Path lockFile = sibling(ledger, REPAIR_LOCK_SUFFIX);
    Path quarantine = sibling(ledger, TORN_TAIL_SUFFIX);
    try (LedgerLock.Held held = lock.acquire(lockFile, timeout);
        FileChannel log = FileChannel.open(ledger, StandardOpenOption.READ, StandardOpenOption.WRITE)) {
      long size = log.size();
      long keep = completeLength(log, size);
      if (keep == size) {
        return Optional.empty();
      }
      try (FileChannel sidecar =
          FileChannel.open(quarantine, StandardOpenOption.CREATE, StandardOpenOption.WRITE, StandardOpenOption.APPEND)) {
        transferFully(log, keep, size - keep, sidecar);
        writeFully(sidecar, ByteBuffer.wrap(new byte[] {NEWLINE}));
        sidecar.force(true);
      }
      log.truncate(keep);
      log.force(true);
      LOG.log(Level.WARNING, "Repaired torn tail of {0}: moved {1,number,#} byte(s) to {2}", ledger, size - keep, quarantine);
      return Optional.of(new Repair(quarantine, size - keep));
    }
  }

  /** The length of the ledger up to and including its last newline; {@code 0} when it holds none. */
  static long completeLength(FileChannel channel, long size) throws IOException {
    ByteBuffer block = ByteBuffer.allocate(TAIL_SCAN_BLOCK);
    long end = size;
    while (end > 0) {
      long start = Math.max(0, end - TAIL_SCAN_BLOCK);
      block.clear().limit((int) (end - start));
      while (block.hasRemaining()) {
        if (channel.read(block, start + block.position()) < 0) {
          throw new IOException("the ledger shrank while its tail was scanned");
        }
      }
      for (int i = block.limit() - 1; i >= 0; i--) {
        if (block.get(i) == NEWLINE) {
          return start + i + 1;
        }
      }
      end = start;
    }
    return 0;
  }

  private static Path sibling(Path ledger, String suffix) {
    return ledger.resolveSibling(ledger.getFileName() + suffix);
  }

  private static void transferFully(FileChannel from, long position, long count, FileChannel to) throws IOException {
    long done = 0;
    while (done < count) {
      long moved = from.transferTo(position + done, count - done, to);
      if (moved <= 0) {
        throw new IOException("the ledger shrank while its torn tail was quarantined");
      }
      done += moved;
    }
  }

  private static void writeFully(FileChannel to, ByteBuffer bytes) throws IOException {
    while (bytes.hasRemaining()) {
      to.write(bytes);
    }
  }
}
