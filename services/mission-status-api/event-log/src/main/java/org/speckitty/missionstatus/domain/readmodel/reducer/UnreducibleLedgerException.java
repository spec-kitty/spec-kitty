package org.speckitty.missionstatus.domain.readmodel.reducer;

import org.speckitty.missionstatus.domain.model.MalformedReason;

/** A malformed line makes the log unreducible (Python's {@code DiaryError}); the line number is the only thing it names. */
public final class UnreducibleLedgerException extends RuntimeException {

  private static final long serialVersionUID = 1L;

  private final long lineNumber;
  private final MalformedReason reason;

  public UnreducibleLedgerException(long lineNumber, MalformedReason reason) {
    super("ledger line " + lineNumber + " is malformed");
    this.lineNumber = lineNumber;
    this.reason = reason;
  }

  public long lineNumber() {
    return lineNumber;
  }

  public MalformedReason reason() {
    return reason;
  }
}
