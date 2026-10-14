package org.speckitty.missionstatus.conformance.port;

import static org.assertj.core.api.Assertions.assertThat;
import static org.speckitty.missionstatus.testsupport.Rows.id;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.List;
import java.util.Optional;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamEvent;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamBatch;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamScope;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.PortLevelTest;
import org.speckitty.missionstatus.testsupport.Rows;

/**
 * The port legs of AC-3g (a valid cursor resumes with exactly the forwarded rows after it) and AC-3i (rows appended in one write arrive
 * as K changes in log order, each with the cursor after its own row). The cursor after row j is computed here from the raw fixture
 * text: the offset is the UTF-8 byte length of the first j rows and the invariant is the SHA-256 ({@link MessageDigest} directly) of the
 * last terminated row, so no expected cursor is read back from the code under test.
 */
public class Ac3ResumeAndBatchTest {

  private static final String T0 = "2026-09-01T10:00:00Z";
  private static final String T1 = "2026-09-01T10:05:00Z";

  /** Seven physical rows; rows 3 (annotation) and 5 (an unknown lifecycle type) are never forwarded. */
  private static List<String> rows() {
    return List.of(
        Rows.lifecycle(id(1), "MissionCreated", T0),
        Rows.status(id(2), T0, "WP01", "planned", "claimed"),
        Rows.annotation(id(3), T0, "WP01"),
        Rows.status(id(4), T1, "WP01", "claimed", "in_progress"),
        Rows.unknownType(id(5)),
        Rows.lifecycle(id(6), "SpecifyStarted", T1),
        Rows.status(id(7), T1, "WP01", "in_progress", "for_review"));
  }

  private static final List<Integer> FORWARDED = List.of(1, 2, 4, 6, 7);

  private static String prefix(List<String> rows, int count) {
    return String.join("", rows.subList(0, count));
  }

  private static StreamCursor cursorAfterRow(List<String> rows, int count) {
    if (count == 0) {
      return StreamCursor.start();
    }
    try {
      byte[] last = rows.get(count - 1).getBytes(StandardCharsets.UTF_8);
      byte[] digest = MessageDigest.getInstance("SHA-256").digest(last);
      return new StreamCursor(prefix(rows, count).getBytes(StandardCharsets.UTF_8).length, HexFormat.of().formatHex(digest));
    } catch (NoSuchAlgorithmException impossible) {
      throw new AssertionError(impossible);
    }
  }

  private static String eventId(StreamEvent change) {
    return switch (change) {
      case StreamEvent.StatusTransition status -> status.eventId();
      case StreamEvent.Lifecycle lifecycle -> lifecycle.eventId();
      default -> throw new AssertionError("a change is a status or lifecycle row");
    };
  }

  private static MissionStatusQuery over(String ledger) {
    return PortFixtures.open(FixtureSpec.of(PortFixtures.mission("resume", Rows.ALPHA_ID, PortFixtures.CREATED, ledger)));
  }

  @PortLevelTest("AC-3g/resume-after-k")
  public void aCursorResumesWithTheForwardedRowsAfterIt() {
    List<String> rows = rows();
    MissionStatusQuery query = over(String.join("", rows));
    StreamScope scope = StreamScope.mission(PortFixtures.ALPHA);

    // After forwarded row 2 (k = 2), and after the annotation row 3 that is not forwarded: both resume with rows 4, 6, 7.
    for (int k : List.of(2, 3)) {
      StreamBatch batch = query.changesSince(scope, Optional.of(cursorAfterRow(rows, k)));

      assertThat(batch.events()).as("changes after row %d", k).extracting(Ac3ResumeAndBatchTest::eventId).containsExactly(id(4), id(6), id(7));
      assertThat(batch.events()).extracting(change -> change.resumeCursor().orElseThrow()).containsExactly(cursorAfterRow(rows, 4), cursorAfterRow(rows, 6), cursorAfterRow(rows, 7));
      assertThat(batch.cursor()).as("the cursor to resume from").isEqualTo(cursorAfterRow(rows, 7));
    }

    // From the very start: every forwarded row, none of the others, each with the cursor after its own physical row.
    StreamBatch all = query.changesSince(scope, Optional.of(StreamCursor.start()));
    List<StreamCursor> expected = new ArrayList<>();
    FORWARDED.forEach(row -> expected.add(cursorAfterRow(rows, row)));
    assertThat(all.events()).extracting(Ac3ResumeAndBatchTest::eventId).containsExactly(id(1), id(2), id(4), id(6), id(7));
    assertThat(all.events()).extracting(change -> change.resumeCursor().orElseThrow()).containsExactlyElementsOf(expected);

    // At the tip: nothing replayed.
    assertThat(query.changesSince(scope, Optional.of(cursorAfterRow(rows, 7))).events()).isEmpty();
  }

  @PortLevelTest("AC-3g/no-cursor-live-only")
  public void noCursorReceivesNoneOfTheExistingRows() {
    List<String> rows = rows();
    MissionStatusQuery query = over(String.join("", rows));

    StreamBatch batch = query.changesSince(StreamScope.mission(PortFixtures.ALPHA), Optional.empty());

    assertThat(batch.events()).as("a connection without a cursor is live only").isEmpty();
    assertThat(batch.cursor()).as("it starts at the current tip").isEqualTo(cursorAfterRow(rows, 7));
  }

  @PortLevelTest("AC-3i/batch-order")
  public void rowsAppendedInOneWriteArriveInLogOrderEachWithItsOwnCursor() {
    List<String> rows = rows();
    int before = 3; // rows 1 to 3 are on disk when the burst of rows 4 to 7 is written in one write
    StreamCursor start = cursorAfterRow(rows, before);
    MissionStatusQuery query = over(String.join("", rows));

    StreamBatch batch = query.changesSince(StreamScope.mission(PortFixtures.ALPHA), Optional.of(start));

    assertThat(batch.events()).extracting(Ac3ResumeAndBatchTest::eventId).as("K forwarded rows, in log order, none missing or repeated").containsExactly(id(4), id(6), id(7));
    assertThat(batch.events()).extracting(change -> change.resumeCursor().orElseThrow()).containsExactly(cursorAfterRow(rows, 4), cursorAfterRow(rows, 6), cursorAfterRow(rows, 7));
    assertThat(batch.events()).extracting(change -> change.resumeCursor().orElseThrow()).doesNotHaveDuplicates();
  }
}
