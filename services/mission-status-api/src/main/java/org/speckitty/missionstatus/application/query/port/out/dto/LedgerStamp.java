package org.speckitty.missionstatus.application.query.port.out.dto;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;

/**
 * The identity of a ledger as the source sees it: a size, a modification time, a file key, the terminated length and the digest of the
 * last terminated line, in whatever form the source chooses. The application only compares stamps with {@code equals}; it never reads
 * a field, and {@code toString} shows none.
 */
public record LedgerStamp(List<Object> parts) {

  public LedgerStamp {
    parts = Collections.unmodifiableList(new ArrayList<>(parts));
  }

  public static LedgerStamp of(Object... parts) {
    return new LedgerStamp(List.of(parts));
  }

  @Override
  public String toString() {
    return "LedgerStamp";
  }
}
