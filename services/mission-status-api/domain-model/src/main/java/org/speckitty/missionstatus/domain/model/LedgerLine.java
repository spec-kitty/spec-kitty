package org.speckitty.missionstatus.domain.model;

import java.util.Objects;

/** One physical ledger line already decoded by the outbound codec. {@code rawLineSha256} is the cursor invariant. */
public record LedgerLine(long lineNumber, String rawLineSha256, long byteLength, LineKind kind) {

  public LedgerLine {
    Objects.requireNonNull(rawLineSha256, "rawLineSha256");
    Objects.requireNonNull(kind, "kind");
  }
}
