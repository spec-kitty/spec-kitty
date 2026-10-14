package org.speckitty.missionstatus.domain.readmodel.derive;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.domain.model.Actor;
import org.speckitty.missionstatus.domain.model.HistoryRow;

/**
 * AC-20.3: the history of a Work Package is ordered by the PARSED instant, then the event id (data-model.md section 4.9; the oracle's
 * {@code _history_order_key}). Each expectation below was checked against the oracle's key.
 */
class HistoryOrderTest {

  private static HistoryRow row(String eventId, String at) {
    return new HistoryRow("WP01", eventId, at, "planned", "claimed", Actor.NONE, false, null, null);
  }

  private static List<String> ids(List<HistoryRow> rows) {
    return rows.stream().map(HistoryRow::eventId).toList();
  }

  @Test
  void stampsThatMixZFractionsAndOffsetsOrderByInstantNotByText() {
    // As text ".5Z" sorts before "Z" and the "+02:00" stamp sorts after "11:00:00Z". By instant: B (10:00:00Z) < A (10:00:00.5Z) < C (10:30Z) < D (11:00Z).
    List<HistoryRow> rows = List.of(row("D", "2026-09-01T11:00:00Z"), row("C", "2026-09-01T12:30:00+02:00"), row("A", "2026-09-01T10:00:00.5Z"), row("B", "2026-09-01T10:00:00Z"));
    assertThat(ids(HistoryOrder.order(rows))).containsExactly("B", "A", "C", "D");
    // the control: a text order differs, so the test can see the trap
    assertThat(rows.stream().map(HistoryRow::at).sorted().toList()).isNotEqualTo(HistoryOrder.order(rows).stream().map(HistoryRow::at).toList());
  }

  @Test
  void equalInstantsTieBreakOnTheEventIdAsTextByCodePoint() {
    List<HistoryRow> rows = List.of(row("E5", "2026-09-01T12:00:00+02:00"), row("E3", "2026-09-01T10:00:00Z"), row("E10", "2026-09-01T10:00:00Z"), row("e1", "2026-09-01T10:00:00Z"));
    assertThat(ids(HistoryOrder.order(rows))).containsExactly("E10", "E3", "E5", "e1");
  }

  @Test
  void aStampThatIsNoInstantSortsAfterEveryRealOneByItsOwnTextThenItsEventId() {
    List<HistoryRow> rows = List.of(row("1", "zzz"), row("2", "2099-01-01T00:00:00Z"), row("3", "garbage"), row("4", "garbage"), row("0", "garbage"));
    assertThat(ids(HistoryOrder.order(rows))).containsExactly("2", "0", "3", "4", "1");
  }

  @Test
  void aMissingStampOrEventIdCountsAsTheTextNoneAsStrOfNoneDoes() {
    List<HistoryRow> rows = List.of(row("B", null), row("A", "2026-09-01T10:00:00Z"), row(null, "2026-09-01T10:00:00Z"));
    // The null event id compares as "None" ("A" < "None"), so A comes first and the nameless row second; the null stamp is "None", no instant, so last.
    assertThat(ids(HistoryOrder.order(rows))).containsExactly("A", null, "B");
  }

  @Test
  void rowsEqualOnTheWholeKeyKeepTheirLedgerOrder() {
    HistoryRow first = new HistoryRow("WP01", "E1", "2026-09-01T10:00:00Z", "planned", "claimed", new Actor("first", null, null), false, null, null);
    HistoryRow second = new HistoryRow("WP01", "E1", "2026-09-01T10:00:00Z", "claimed", "in_progress", new Actor("second", null, null), false, null, null);
    assertThat(HistoryOrder.order(List.of(first, second))).containsExactly(first, second);
    assertThat(HistoryOrder.order(List.of(second, first))).containsExactly(second, first);
  }

  @Test
  void anOffsetlessStampIsReadAsUtcAndAFractionBeyondTheMicrosecondIsTruncated() {
    List<HistoryRow> rows = List.of(row("B", "2026-09-01T10:00:00.0000019Z"), row("A", "2026-09-01T10:00:00.0000011Z"), row("C", "2026-09-01T09:59:59"));
    // C (offset-less, read as UTC) is the earliest; A and B are the same microsecond, so the event id decides
    assertThat(ids(HistoryOrder.order(rows))).containsExactly("C", "A", "B");
  }

  @Test
  void theInputIsNotModifiedAndTheComparatorSortsInPlaceIdentically() {
    List<HistoryRow> rows = List.of(row("B", "2026-09-01T11:00:00Z"), row("A", "2026-09-01T10:00:00Z"));
    List<HistoryRow> before = new ArrayList<>(rows);
    List<HistoryRow> ordered = HistoryOrder.order(rows);
    assertThat(rows).isEqualTo(before);
    List<HistoryRow> inPlace = new ArrayList<>(rows);
    inPlace.sort(HistoryOrder.comparator());
    assertThat(inPlace).isEqualTo(ordered);
  }
}
