package org.speckitty.missionstatus.application.query;

import java.util.List;
import java.util.Map;
import java.util.Objects;
import java.util.Optional;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;
import org.speckitty.missionstatus.application.query.port.out.dto.LedgerStamp;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.model.LedgerLine;
import org.speckitty.missionstatus.domain.model.StatusSnapshot;
import org.speckitty.missionstatus.domain.readmodel.reducer.StatusReducer;

/**
 * The reduced ledger of each Mission, keyed by the {@link LedgerStamp} the source reported. An equal stamp is a hit: the ledger is not
 * read and not reduced again. A changed stamp invalidates that Mission only. The stamp is compared with {@code equals}; its fields
 * are never read.
 */
final class ProjectionCache {

  /** What is kept per Mission: the reduction and the cursor of the terminated prefix it describes. */
  record Entry(StatusSnapshot snapshot, StreamCursor cursor) {}

  private record Keyed(LedgerStamp stamp, Entry entry) {}

  private final StatusReducer reducer;
  private final Map<MissionRef, Keyed> entries = new ConcurrentHashMap<>();
  private final AtomicInteger reductions = new AtomicInteger();

  ProjectionCache(StatusReducer reducer) {
    this.reducer = Objects.requireNonNull(reducer, "reducer");
  }

  /** The entry for this stamp, if the cache holds exactly this stamp for the Mission. */
  Optional<Entry> lookup(MissionRef ref, LedgerStamp stamp) {
    Keyed keyed = entries.get(ref);
    return keyed != null && keyed.stamp().equals(stamp) ? Optional.of(keyed.entry()) : Optional.empty();
  }

  /**
   * Reduces the lines (counting the reduction), keeps the result under the stamp and returns it.
   *
   * @throws org.speckitty.missionstatus.domain.readmodel.reducer.UnreducibleLedgerException when a line is malformed; nothing is kept
   */
  Entry load(MissionRef ref, LedgerStamp stamp, List<LedgerLine> lines) {
    StatusSnapshot snapshot = reducer.reduceLines(lines);
    reductions.incrementAndGet();
    Entry entry = new Entry(snapshot, cursorOf(lines));
    entries.put(ref, new Keyed(stamp, entry));
    return entry;
  }

  /** Forgets every Mission that is not in the set. */
  void retainOnly(Set<MissionRef> live) {
    entries.keySet().retainAll(live);
  }

  /** How many times a ledger was reduced. */
  int reductions() {
    return reductions.get();
  }

  int size() {
    return entries.size();
  }

  /** The cursor after the last terminated line: its byte offset, and the digest of that single line (of nothing at offset 0). */
  static StreamCursor cursorOf(List<LedgerLine> lines) {
    if (lines.isEmpty()) {
      return StreamCursor.start();
    }
    long offset = 0;
    for (LedgerLine line : lines) {
      offset += line.byteLength();
    }
    return new StreamCursor(offset, lines.getLast().rawLineSha256());
  }
}
