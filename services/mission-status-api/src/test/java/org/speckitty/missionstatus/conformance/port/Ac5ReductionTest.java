package org.speckitty.missionstatus.conformance.port;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Arrays;
import java.util.Map;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.application.query.port.in.dto.PageRequest;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.readmodel.overview.LifecycleStatus;
import org.speckitty.missionstatus.domain.readmodel.overview.MissionOverview;
import org.speckitty.missionstatus.domain.readmodel.overview.ProjectHeader;
import org.speckitty.missionstatus.testsupport.PortFixtures;
import org.speckitty.missionstatus.testsupport.PortLevelTest;
import org.speckitty.missionstatus.testsupport.Rows;

/**
 * AC-5a and AC-5c: the two interleaved Missions reduce to the lanes and counts of the Python oracle, through the inbound port only. The
 * expected values were produced by the oracle (see {@link PortFixtures}); a sort by parsed instant, a text comparison in
 * {@code lastActivityAt}, a missing first-occurrence dedup or an event-id-first sort each change at least one of them.
 */
public class Ac5ReductionTest {

  private static MissionOverview overview(MissionStatusQuery query, String slug) {
    return query.missions(new PageRequest(null, null)).items().stream().filter(item -> item.slug().equals(slug)).findFirst().orElseThrow();
  }

  private static Map<Lane, Integer> lanes(MissionOverview overview) {
    return overview.statusLaneCounts();
  }

  @PortLevelTest("AC-5a/alpha-sort-and-dedup")
  public void alphaReducesToTheOracleLanesAndCounts() {
    MissionOverview alpha = overview(PortFixtures.open(PortFixtures.interleavedPair()), "interleaved-alpha");

    // WP01: file order says blocked, (at, event_id) order says claimed (the blocked row then no longer continues the lane in force). WP05: the duplicated event id keeps its first row (claimed).
    assertThat(alpha.wpTotal()).isEqualTo(5);
    assertThat(lanes(alpha).get(Lane.CLAIMED)).isEqualTo(5);
    assertThat(lanes(alpha).values().stream().mapToInt(Integer::intValue).sum()).isEqualTo(5);
    assertThat(alpha.eventCount()).as("distinct event ids").isEqualTo(6);
    // The last event in (at-text, event_id) order is the +02:00 row, not the latest instant.
    assertThat(alpha.lastEventId()).isEqualTo(Rows.id(9));
    // lastActivityAt is the latest INSTANT among the work packages' own strings: the .123456 row, not the text-greatest +02:00 row.
    assertThat(alpha.lastActivityAt()).isEqualTo("2026-09-01T11:00:00.123456Z");
    assertThat(alpha.progress().weightedPercentage()).isEqualTo(5.0);
    assertThat(alpha.progress().donePercentage()).isEqualTo(0.0);
    assertThat(alpha.progress().doneCount()).isZero();
    assertThat(alpha.lifecycleStatus()).isEqualTo(LifecycleStatus.ACTIVE);
    // The oracle's poll_once over the same bytes: offset 1666, SHA-256 of the last line.
    assertThat(alpha.streamCursor().offset()).isEqualTo(1666);
    assertThat(alpha.streamCursor().invariant()).isEqualTo("7ca63b2c762f119d04b1600f8cb2c916990f66d13e6bbadfc48583c2aaa943d4");
  }

  @PortLevelTest("AC-5a/beta-at-before-event-id")
  public void betaOrdersByAtBeforeEventId() {
    MissionOverview beta = overview(PortFixtures.open(PortFixtures.interleavedPair()), "interleaved-beta");

    // WP01 ends in for_review (the latest at) although an event with a larger id sorts earlier; WP02 ends in in_progress.
    assertThat(beta.wpTotal()).isEqualTo(2);
    assertThat(lanes(beta).get(Lane.FOR_REVIEW)).isEqualTo(1);
    assertThat(lanes(beta).get(Lane.IN_PROGRESS)).isEqualTo(1);
    assertThat(lanes(beta).get(Lane.CLAIMED)).isZero();
    assertThat(beta.eventCount()).isEqualTo(6);
    assertThat(beta.lastEventId()).isEqualTo(Rows.id(26));
    assertThat(beta.lastActivityAt()).isEqualTo("2026-09-01T09:40:00Z");
    // As the oracle SERVES it: the raw float is 44.99999999999999 and build_overview writes round(progress.percentage, 4)
    // (tests/contract/_mission_status_payloads.py lines 885-886), which is 45.0; Java's Progress is rounded the same way and renders "45.0".
    assertThat(beta.progress().weightedPercentage()).isEqualTo(45.0);
    assertThat(org.speckitty.missionstatus.domain.readmodel.overview.Progress.render(beta.progress().weightedPercentage())).isEqualTo("45.0");
    assertThat(beta.streamCursor().offset()).isEqualTo(1419);
    assertThat(beta.streamCursor().invariant()).isEqualTo("fb3f6df8edb15d2aee6e7e2f4d85a6454ad3c6b25df5d4c780145fdea811075e");
  }

  @PortLevelTest("AC-5a/project-last-activity")
  public void theProjectHeaderTakesTheLatestInstant() {
    ProjectHeader header = PortFixtures.open(PortFixtures.interleavedPair()).project();

    assertThat(header.missionCount()).isEqualTo(2);
    assertThat(header.lastActivityAt()).isEqualTo("2026-09-01T11:00:00.123456Z");
  }

  @PortLevelTest("AC-5c")
  public void theReductionNeedsNoSpringContext() {
    MissionStatusQuery query = PortFixtures.open(PortFixtures.interleavedPair());

    // The reduction runs here with no Spring context: neither this class nor the service behind the port carries a Spring annotation.
    assertThat(overview(query, "interleaved-alpha").eventCount()).isEqualTo(6);
    for (Class<?> type : new Class<?>[] {Ac5ReductionTest.class, query.getClass()}) {
      assertThat(Arrays.stream(type.getAnnotations()).map(annotation -> annotation.annotationType().getName()))
          .as("annotations of %s", type.getSimpleName())
          .noneMatch(name -> name.startsWith("org.springframework"));
    }
  }
}
