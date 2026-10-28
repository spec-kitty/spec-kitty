package org.speckitty.missionstatus.architecture.fixture.ledger;

import tools.jackson.core.json.JsonFactory;

/** Planted violation: ledger file mechanics that parse rows (the ledger package moves bytes and never reads a row). */
public final class DecodingLedgerFile {

  private DecodingLedgerFile() {}

  public static boolean parses(String line) {
    return new JsonFactory().createParser(line).nextToken() != null;
  }
}
