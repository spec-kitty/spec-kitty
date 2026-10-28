package org.speckitty.missionstatus.adapter.out.ledger;

import java.util.Locale;

/** The ledger lock for this operating system. */
public final class LedgerLocks {

  private LedgerLocks() {}

  /**
   * {@code flock(2)} on Linux and macOS, the lock {@code kernel.locks} takes there ({@code FileChannel.lock} does not exclude it on Linux);
   * {@code FileChannel.lock} on Windows, which overlaps {@code msvcrt.locking}'s byte-range lock.
   */
  public static LedgerLock forThisOs() {
    return System.getProperty("os.name").toLowerCase(Locale.ROOT).contains("win") ? new ChannelLedgerLock() : new FlockLedgerLock();
  }
}
