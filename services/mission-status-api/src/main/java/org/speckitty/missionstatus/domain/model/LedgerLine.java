package org.speckitty.missionstatus.domain.model;

import java.util.Objects;

/**
 * One physical ledger line already decoded by the outbound codec. {@code rawLineSha256} is the cursor invariant.
 *
 * <p>Two members read the row itself, independently of how it was classified (D-98): {@code eventType} is the row's own {@code event_type}
 * when that is a string (the oracle's {@code _lifecycle_types} counts it whatever else the row lacks, so a phase-marker row without a string
 * {@code event_id} or {@code timestamp}, which classifies {@code Ignored}, is still counted); {@code historyRow} is the oracle's
 * {@code history_entries} reading of a row that has a {@code to_lane} key and a string {@code wp_id}. Both are null for every other line.
 */
public record LedgerLine(long lineNumber, String rawLineSha256, long byteLength, LineKind kind, String eventType, HistoryRow historyRow) {

  public LedgerLine {
    Objects.requireNonNull(rawLineSha256, "rawLineSha256");
    Objects.requireNonNull(kind, "kind");
  }

  /** A line that carries neither an event type nor a history row. */
  public LedgerLine(long lineNumber, String rawLineSha256, long byteLength, LineKind kind) {
    this(lineNumber, rawLineSha256, byteLength, kind, null, null);
  }
}
