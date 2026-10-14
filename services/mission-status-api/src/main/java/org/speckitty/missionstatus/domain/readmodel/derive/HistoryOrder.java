package org.speckitty.missionstatus.domain.readmodel.derive;

import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Comparator;
import java.util.List;
import org.speckitty.missionstatus.domain.model.CodePoints;
import org.speckitty.missionstatus.domain.model.HistoryRow;
import org.speckitty.missionstatus.domain.readmodel.overview.InvalidInstantException;
import org.speckitty.missionstatus.domain.readmodel.overview.Instants;

/**
 * The order of a Work Package's history: the oracle's {@code _history_order_key} (data-model.md section 4.9). Rows sort by the PARSED
 * instant of {@code at} (stamps mix {@code Z}, fractions and offsets, so text order is wrong), then by the event id as text. A stamp that is
 * not an instant sorts after every real one, by its own text and then its event id, so that the contract check names it instead of the sort
 * raising. The sort is stable: rows equal on the whole key keep their order in the ledger. This is not the fold's order, which compares
 * the stamp as text ({@code AtThenEventId}).
 *
 * <p>The instant is read as Python reads it up to the microsecond (Python truncates a longer fraction to six digits) and an offset-less stamp
 * is read as UTC, where Python reads it in the local zone ({@link Instants}); that is a documented difference, not a bug to chase. A missing
 * stamp or event id compares as the text {@code None}, as {@code str(None)} does.
 */
public final class HistoryOrder {

  private static final String NONE = "None";
  private static final Comparator<HistoryRow> ORDER = Comparator.comparing(HistoryOrder::key);

  private static final Comparator<Keyed> BY_KEY = (left, right) -> left.key().compareTo(right.key());

  private HistoryOrder() {}

  /** The rows of one Work Package, in history order. The input is not modified. */
  public static List<HistoryRow> order(List<HistoryRow> rows) {
    int size = rows.size();
    if (size < 2) {
      return new ArrayList<>(rows);
    }
    // decorate, sort, undecorate: each stamp is parsed once per row, not once per comparison
    Keyed[] keyed = new Keyed[size];
    int index = 0;
    for (HistoryRow row : rows) {
      keyed[index++] = new Keyed(key(row), row);
    }
    Arrays.sort(keyed, BY_KEY);
    List<HistoryRow> sorted = new ArrayList<>(size);
    for (Keyed entry : keyed) {
      sorted.add(entry.row());
    }
    return sorted;
  }

  /** The comparator itself, for a caller that sorts in place. */
  public static Comparator<HistoryRow> comparator() {
    return ORDER;
  }

  private static Key key(HistoryRow row) {
    String stamp = row.at() == null ? NONE : row.at();
    String eventId = row.eventId() == null ? NONE : row.eventId();
    try {
      return new Key(0, Instants.parse(stamp).truncatedTo(ChronoUnit.MICROS), "", eventId);
    } catch (InvalidInstantException notAnInstant) {
      return new Key(1, Instant.EPOCH, stamp, eventId);
    }
  }

  private record Keyed(Key key, HistoryRow row) {}

  /** {@code (group, instant, stamp, eventId)}; the stamp text is part of the key only for a stamp that is no instant. */
  private record Key(int group, Instant instant, String stamp, String eventId) implements Comparable<Key> {
    @Override
    public int compareTo(Key other) {
      int byGroup = Integer.compare(group, other.group);
      if (byGroup != 0) {
        return byGroup;
      }
      int byInstant = instant.compareTo(other.instant);
      if (byInstant != 0) {
        return byInstant;
      }
      int byStamp = CodePoints.compare(stamp, other.stamp);
      return byStamp != 0 ? byStamp : CodePoints.compare(eventId, other.eventId);
    }
  }
}
