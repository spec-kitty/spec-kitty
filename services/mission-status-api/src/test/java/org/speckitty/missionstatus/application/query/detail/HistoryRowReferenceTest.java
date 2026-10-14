package org.speckitty.missionstatus.application.query.detail;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.domain.model.Actor;
import org.speckitty.missionstatus.domain.model.HistoryRow;
import org.speckitty.missionstatus.domain.model.StatusSnapshot;
import org.speckitty.missionstatus.testsupport.DetailFixture;

/**
 * The review reference of a history row (WP15, named edit of {@code HistoryRow} and {@code RowClassifier}): the {@code reference} of the row's
 * {@code review_result} as the ledger wrote it when that is text, else null, from the real decoder and the real reduction. The review-cycle
 * verdicts of the detail are read from it.
 */
class HistoryRowReferenceTest {

  private static List<HistoryRow> history(String ledger) {
    DetailFixture fixture = DetailRoute.fixture(ledger, root -> {});
    StatusSnapshot snapshot = fixture.reduce("alpha");
    return snapshot.resolved().get("WP01").history();
  }

  @Test
  void aTextReferenceIsKeptAsWrittenWithItsVerdict() {
    List<HistoryRow> rows = history(DetailRoute.review(1, "2026-09-01T10:01:00Z", "WP01", "planned", "approved", "\"  review-cycle://alpha/WP01-one/review-cycle-1.md \"", "approved"));

    assertThat(rows).hasSize(1);
    assertThat(rows.get(0).reviewReference()).isEqualTo("  review-cycle://alpha/WP01-one/review-cycle-1.md ");
    assertThat(rows.get(0).reviewVerdict()).isEqualTo("approved");
  }

  @Test
  void aReferenceThatIsNotTextAndARowWithoutAReviewResultHaveNone() {
    List<HistoryRow> rows = history(DetailRoute.review(1, "2026-09-01T10:01:00Z", "WP01", "planned", "approved", "7", "approved") + DetailRoute.ledger().replace("000000000000000000000001", "000000000000000000000002"));

    assertThat(rows).extracting(HistoryRow::reviewReference).containsExactly(null, null);
    assertThat(rows.get(0).reviewVerdict()).isEqualTo("approved");
  }

  @Test
  void theOlderConstructorLeavesTheReferenceNull() {
    HistoryRow row = new HistoryRow("WP01", "E", "2026-09-01T10:00:00Z", "planned", "claimed", Actor.NONE, false, null, null);

    assertThat(row.reviewReference()).isNull();
    assertThat(row).isEqualTo(new HistoryRow("WP01", "E", "2026-09-01T10:00:00Z", "planned", "claimed", Actor.NONE, false, null, null, null));
  }
}
