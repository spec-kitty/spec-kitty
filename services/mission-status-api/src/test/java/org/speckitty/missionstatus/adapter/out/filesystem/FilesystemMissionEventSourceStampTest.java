package org.speckitty.missionstatus.adapter.out.filesystem;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.FileTime;
import java.time.Instant;
import java.util.Map;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamBatch;
import org.speckitty.missionstatus.application.query.port.in.dto.StreamScope;
import org.speckitty.missionstatus.domain.readmodel.cursor.StreamCursor;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionOverview;
import org.speckitty.missionstatus.testsupport.Rows;

/**
 * AC-7c and AC-7d at the adapter, through the real service over the real source: an equal-length rewrite is seen when the last line
 * changes (the stamp digests it) or when the modification time moves, and it is NOT seen when only a middle line changes and the
 * modification time is restored. That last case is the documented limit of the stamp (the threat model of the oracle's
 * {@code tail_reader}: the writer only ever appends or truncates a suffix), named as such here; it serves the stale reduction and
 * raises no {@code log_truncated}.
 */
class FilesystemMissionEventSourceStampTest {

  private static final FileTime FIXED = FileTime.from(Instant.parse("2026-09-01T10:00:00Z"));

  @TempDir Path sandbox;
  AdapterServiceHarness harness;
  Path ledger;

  @BeforeEach
  void setUp() throws IOException {
    Path root = Files.createDirectory(sandbox.resolve("project"));
    AdapterServiceHarness.healthyProject(root);
    harness = new AdapterServiceHarness(root);
    ledger = root.resolve("kitty-specs").resolve(AdapterServiceHarness.ALPHA).resolve("status.events.jsonl");
  }

  private void seed(String text) throws IOException {
    AdapterServiceHarness.mission(harness.root, AdapterServiceHarness.ALPHA, Rows.ALPHA_ID, "2026-09-01T09:00:00+00:00", text);
    Files.setLastModifiedTime(ledger, FIXED);
  }

  private void rewrite(String text, FileTime mtime) throws IOException {
    Files.write(ledger, text.getBytes(StandardCharsets.UTF_8));
    Files.setLastModifiedTime(ledger, mtime);
  }

  private MissionOverview only() {
    return harness.overviews().get(0);
  }

  private static String row(int n, String wp, String to) {
    return AdapterServiceHarness.laneRow(n, wp, "planned", to);
  }

  private static Map<Lane, Integer> counts(MissionOverview overview) {
    return overview.statusLaneCounts();
  }

  @Test
  void aRewriteOfTheLastLineOnlyIsSeenEvenWithTheModificationTimeRestored() throws IOException {
    String first = row(1, "WP01", "claimed");
    seed(first + row(2, "WP02", "claimed"));
    assertThat(counts(only()).get(Lane.CLAIMED)).isEqualTo(2);
    String before = only().streamCursor().invariant();

    rewrite(first + row(2, "WP02", "blocked"), FIXED);

    MissionOverview fresh = only();
    assertThat(counts(fresh).get(Lane.CLAIMED)).as("served fresh: the last line changed").isEqualTo(1);
    assertThat(counts(fresh).get(Lane.BLOCKED)).isEqualTo(1);
    assertThat(fresh.streamCursor().invariant()).isNotEqualTo(before);
  }

  @Test
  void aRewriteOfAMiddleLineWithTheModificationTimeAdvancedIsSeen() throws IOException {
    seed(row(1, "WP01", "claimed") + row(2, "WP02", "claimed") + row(3, "WP03", "claimed"));
    assertThat(counts(only()).get(Lane.CLAIMED)).isEqualTo(3);

    rewrite(row(1, "WP01", "claimed") + row(2, "WP02", "blocked") + row(3, "WP03", "claimed"), FileTime.from(Instant.parse("2026-09-01T10:00:05Z")));

    MissionOverview fresh = only();
    assertThat(counts(fresh).get(Lane.CLAIMED)).as("served fresh: the stamp's modification time moved").isEqualTo(2);
    assertThat(counts(fresh).get(Lane.BLOCKED)).isEqualTo(1);
  }

  @Test
  void aRewriteOfAMiddleLineWithTheModificationTimeRestoredIsServedStaleAndRaisesNoTruncation() throws IOException {
    seed(row(1, "WP01", "claimed") + row(2, "WP02", "claimed") + row(3, "WP03", "claimed"));
    MissionOverview first = only();
    StreamCursor end = first.streamCursor();

    // THE DOCUMENTED LIMIT: size, last-line digest and (restored) modification time all equal the cached stamp.
    rewrite(row(1, "WP01", "claimed") + row(2, "WP02", "blocked") + row(3, "WP03", "claimed"), FIXED);

    MissionOverview stale = only();
    assertThat(counts(stale)).as("served stale, as documented").isEqualTo(counts(first));
    assertThat(stale.streamCursor()).isEqualTo(end);

    StreamBatch batch = harness.query.changesSince(new StreamScope.OneMission(new MissionId(Rows.ALPHA_ID)), Optional.of(end));
    assertThat(batch.events()).as("no log_truncated and nothing forwarded: the last line is unchanged").isEmpty();
    assertThat(batch.cursor()).isEqualTo(end);
  }
}
