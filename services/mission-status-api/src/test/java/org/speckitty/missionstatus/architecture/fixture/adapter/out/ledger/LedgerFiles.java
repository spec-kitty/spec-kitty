package org.speckitty.missionstatus.architecture.fixture.adapter.out.ledger;

/** Architecture-rule fixture: conforming ledger file mechanics, the one place outside the filesystem adapter that rule 7 lets use file APIs. */
public final class LedgerFiles {
  public long size(java.nio.file.Path ledger) throws java.io.IOException {
    return java.nio.file.Files.size(ledger);
  }
}
