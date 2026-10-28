package org.speckitty.missionstatus.adapter.out.ledger;

import java.io.IOException;
import java.nio.file.Path;
import java.time.Duration;

/** The lock was still held by another holder when the bounded wait elapsed; nothing was done under it. */
public final class LedgerLockTimeoutException extends IOException {

  private static final long serialVersionUID = 1L;

  LedgerLockTimeoutException(Path lockFile, Duration timeout) {
    super("lock " + lockFile + " was not acquired within " + timeout + " because another holder has it");
  }
}
