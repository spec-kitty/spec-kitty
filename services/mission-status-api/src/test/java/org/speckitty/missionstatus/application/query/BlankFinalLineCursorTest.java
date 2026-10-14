package org.speckitty.missionstatus.application.query;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.catchThrowable;
import static org.speckitty.missionstatus.application.query.StreamFx.ALPHA;

import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamBatch;
import org.speckitty.missionstatus.application.query.port.in.dto.PageRequest;
import org.speckitty.missionstatus.application.query.port.in.exceptions.StreamRefused;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamScope;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamEvent;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamSignal;
import org.speckitty.missionstatus.application.query.port.in.Subscription;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionOverview;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.Rows;

/**
 * The stream cursor of a ledger whose last terminated line is blank: the invariant is the digest of THAT line (a bare newline), not of
 * the last non-blank row. The oracle decides, and it was run on a ledger of one row and a blank line
 * ({@code {"a":1}\n\n}, 9 bytes), with the tail reader of the CLI ({@code specify_cli.status.tail_reader}):
 *
 * <pre>
 * sha256('{"a":1}\n') = e346432021b04179518d9614f3560ccd71354a4ee101ddcb893d6959a9d6301c
 * sha256('\n')        = 01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b
 * validate_resume_cursor(9, non-blank digest)  -> refused content_mismatch
 * poll_once(9, non-blank digest)               -> events [log_truncated(content_mismatch, detected_at_offset 9)], cursor 0
 * validate_resume_cursor(9, blank-line digest) -> accepted 9
 * poll_once(9, blank-line digest)              -> events [], cursor 9
 * </pre>
 *
 * So a cursor that carries the last non-blank digest is refused by Python itself when the final line is blank, and the cursor the service
 * hands out must carry the digest of the blank line.
 */
class BlankFinalLineCursorTest {

  private static final String BLANK_LINE_DIGEST = "01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b";

  private static final String ROW_THEN_BLANK = "{\"a\":1}\n\n";
  private static final String ROW_DIGEST = "e346432021b04179518d9614f3560ccd71354a4ee101ddcb893d6959a9d6301c";

  private static Fx fx() {
    return new Fx(FixtureSpec.of(Fx.mission("alpha", Rows.ALPHA_ID, StreamFx.CREATED, ledger())));
  }

  private static String ledger() {
    return StreamFx.alphaHistory() + "\n";
  }

  private static long size() {
    return ledger().getBytes(StandardCharsets.UTF_8).length;
  }

  @Test
  void theOraclesDigestsAreTheDigestsOfTheTwoLinesOfTheOracleLedger() {
    assertThat(StreamCursor.digestOf("{\"a\":1}\n".getBytes(StandardCharsets.UTF_8))).isEqualTo(ROW_DIGEST);
    assertThat(StreamCursor.digestOf("\n".getBytes(StandardCharsets.UTF_8))).isEqualTo(BLANK_LINE_DIGEST);
    assertThat(ROW_THEN_BLANK.getBytes(StandardCharsets.UTF_8)).hasSize(9);
  }

  @Test
  void theOverviewCursorOfALedgerEndingInABlankLineCarriesTheDigestOfThatBlankLine() {
    Fx fx = fx();

    MissionOverview alpha = fx.service.missions(new PageRequest(null, null)).items().getFirst();

    assertThat(alpha.streamCursor()).isEqualTo(new StreamCursor(size(), BLANK_LINE_DIGEST));
    assertThat(alpha.eventCount()).as("a blank line is not an event").isEqualTo(2);
  }

  @Test
  void aCursorWithTheBlankLineDigestIsAcceptedAndOneWithTheLastRowsDigestIsRefusedAsContentMismatch() {
    Fx fx = fx();

    StreamBatch accepted = fx.service.changesSince(StreamScope.mission(ALPHA), Optional.of(new StreamCursor(size(), BLANK_LINE_DIGEST)));
    assertThat(accepted.events()).isEmpty();
    assertThat(accepted.cursor()).isEqualTo(new StreamCursor(size(), BLANK_LINE_DIGEST));

    String lastRow = StreamFx.alphaHistory().split("(?<=\n)")[2];
    Throwable refused = catchThrowable(() -> fx.service.changesSince(StreamScope.mission(ALPHA), Optional.of(new StreamCursor(size(), StreamCursor.digestOf(lastRow.getBytes(StandardCharsets.UTF_8))))));
    assertThat(refused).isInstanceOfSatisfying(StreamRefused.class, error -> assertThat(error.kind()).isEqualTo(StreamRefused.Kind.CONTENT_MISMATCH));
  }

  @Test
  void aStreamOpenedOverALedgerEndingInABlankLineSeesTheNextRowAndNoTruncation() {
    Fx fx = fx();
    String row = Rows.status(Rows.id(4), Fx.T2, "WP01", "in_progress", "for_review");
    try (Subscription scoped = fx.service.subscribe(StreamScope.mission(ALPHA), Optional.empty());
        Subscription unscoped = fx.service.subscribe(StreamScope.all(), Optional.empty());
        Subscription resumed = fx.service.subscribe(StreamScope.mission(ALPHA), Optional.of(new StreamCursor(size(), BLANK_LINE_DIGEST)))) {
      fx.source.appendLedger("alpha", row);
      fx.executor.tick();

      for (Subscription subscription : java.util.List.of(scoped, unscoped, resumed)) {
        var signals = StreamFx.drain(subscription);
        assertThat(signals).noneMatch(signal -> signal instanceof StreamSignal.Events events && events.events().stream().anyMatch(event -> event instanceof StreamEvent.LogTruncated));
        var changes = StreamFx.changes(signals);
        assertThat(StreamFx.eventIds(changes)).containsExactly(Rows.id(4));
        assertThat(changes.getFirst().resumeCursor().orElseThrow()).isEqualTo(StreamFx.cursorAfter(ledger() + row, 5));
      }
      fx.clock.advance(Duration.ofSeconds(2));
      fx.executor.tick();
      assertThat(StreamFx.drain(scoped)).isEmpty();
    }
    assertThat(fx.handles.diagnostics()).isEmpty();
  }
}
