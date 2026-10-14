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
import org.speckitty.missionstatus.testsupport.FixtureSpec;
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

  // ---- AC-20.2: the resolved Work Package state does not move the overview ------------------------------------------------------

  private static final String PLAIN_SLUG = "resolved-plain";
  private static final String RICH_SLUG = "resolved-rich";

  /** Three transitions of two work packages; the same rows, with nothing resolved, are the control. */
  private static String plainLedger() {
    return Rows.status(Rows.id(1), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed")
        + Rows.status(Rows.id(2), "2026-09-01T10:10:00Z", "WP01", "claimed", "in_progress")
        + Rows.status(Rows.id(3), "2026-09-01T10:05:00Z", "WP02", "planned", "claimed");
  }

  /** The same transitions carrying every resolved member: a claim agent, a review result, annotations, marker and history rows, a repeated id. */
  private static String richLedger() {
    return Rows.status(Rows.id(1), "2026-09-01T10:00:00Z", "WP01", "planned", "claimed").replace("}\n", ",\"policy_metadata\":{\"agent\":\"claude\",\"shell_pid\":7}}\n")
        + Rows.status(Rows.id(2), "2026-09-01T10:10:00Z", "WP01", "claimed", "in_progress")
            .replace("}\n", ",\"review_result\":{\"reviewer\":\"rev\",\"verdict\":\"approved\",\"reference\":\"cycle-1\"}}\n")
        + Rows.status(Rows.id(3), "2026-09-01T10:05:00Z", "WP02", "planned", "claimed")
        + annotation(Rows.id(11), "2026-09-01T10:20:00Z", "WP01", "{\"release_runtime_claim\":true,\"role\":\"implementer\",\"subtasks\":{\"T1\":\"done\"}}")
        + annotation(Rows.id(12), "2026-09-01T10:21:00Z", "WP01", "{\"review\":{\"at\":\"2026-09-01T10:21:00+00:00\",\"actor\":\"arb\",\"wp_id\":\"WP01\",\"reason\":\"ok\"}}")
        + "{\"event_type\":\"PlanStarted\",\"timestamp\":\"2026-09-01T10:30:00Z\"}\n"
        + "{\"event_type\":\"DecisionX\",\"event_id\":\"D1\",\"wp_id\":\"WP01\",\"from_lane\":\"claimed\",\"to_lane\":\"done\",\"at\":\"2026-09-01T10:31:00Z\"}\n"
        + Rows.status(Rows.id(2), "2026-09-01T10:40:00Z", "WP01", "in_progress", "done");
  }

  private static String annotation(String eventId, String at, String wpId, String delta) {
    return Rows.annotation(eventId, at, wpId).replace("{\"note\":\"hello\"}", delta);
  }

  private static MissionStatusQuery resolvedPair() {
    return PortFixtures.open(
        FixtureSpec.of(
            PortFixtures.mission(PLAIN_SLUG, Rows.ALPHA_ID, PortFixtures.CREATED, plainLedger()),
            PortFixtures.mission(RICH_SLUG, Rows.BETA_ID, PortFixtures.CREATED, richLedger())));
  }

  @PortLevelTest("AC-20/empty-members-control")
  public void aLedgerWithNoResolvedMembersReducesToTheHandDerivedOverview() {
    MissionOverview plain = overview(resolvedPair(), PLAIN_SLUG);

    // WP01 ends in in_progress (the later at), WP02 in claimed
    assertThat(plain.wpTotal()).isEqualTo(2);
    assertThat(lanes(plain).get(Lane.IN_PROGRESS)).isEqualTo(1);
    assertThat(lanes(plain).get(Lane.CLAIMED)).isEqualTo(1);
    assertThat(plain.eventCount()).isEqualTo(3);
    assertThat(plain.lastEventId()).isEqualTo(Rows.id(2));
    assertThat(plain.lastActivityAt()).isEqualTo("2026-09-01T10:10:00Z");
  }

  @PortLevelTest("AC-20/resolved-members")
  public void everyResolvedMemberInTheLedgerLeavesTheOverviewByteIdentical() {
    MissionStatusQuery query = resolvedPair();
    MissionOverview plain = overview(query, PLAIN_SLUG);
    MissionOverview rich = overview(query, RICH_SLUG);

    // The rich ledger repeats event id 2 with a different move (the dedup keeps the first, so the history lists a row the fold dropped) and
    // adds annotation, marker and history-only rows; none of them may reach an overview member.
    assertThat(rich.wpTotal()).isEqualTo(plain.wpTotal());
    assertThat(rich.eventCount()).as("annotation, marker and history rows are not transitions").isEqualTo(plain.eventCount());
    assertThat(rich.lastEventId()).isEqualTo(plain.lastEventId());
    assertThat(lanes(rich)).isEqualTo(lanes(plain));
    assertThat(rich.progress()).isEqualTo(plain.progress());
    assertThat(rich.lastActivityAt()).isEqualTo(plain.lastActivityAt());
    assertThat(rich.lifecycleStatus()).isEqualTo(plain.lifecycleStatus());
    assertThat(rich.streamCursor().offset()).as("the rich ledger is longer, so the cursor is where the difference may show").isGreaterThan(plain.streamCursor().offset());
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
