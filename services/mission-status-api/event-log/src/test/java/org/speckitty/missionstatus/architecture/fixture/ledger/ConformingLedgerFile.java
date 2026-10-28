package org.speckitty.missionstatus.architecture.fixture.ledger;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;

/** Conforms: ledger file mechanics with the JDK alone. */
public final class ConformingLedgerFile {

  private ConformingLedgerFile() {}

  public static long size(Path ledger) throws IOException {
    return Files.size(ledger);
  }
}
