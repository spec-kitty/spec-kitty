package org.speckitty.missionstatus.perf;

import static org.assertj.core.api.Assertions.assertThat;

import java.lang.management.ManagementFactory;
import java.lang.management.MemoryMXBean;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.domain.model.LedgerLine;
import org.speckitty.missionstatus.domain.model.LineKind;
import org.speckitty.missionstatus.domain.model.StatusEvent;
import org.speckitty.missionstatus.domain.model.StatusSnapshot;
import org.speckitty.missionstatus.domain.model.WpResolved;
import org.speckitty.missionstatus.domain.readmodel.reducer.AtThenEventId;
import org.speckitty.missionstatus.domain.readmodel.reducer.StatusReducer;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.InMemoryMissionEventSource;

/**
 * NFR-009 (AC-20.5): caching the resolved Work Package state costs at most 64 MiB over 500 Missions of 10 Work Packages and 100
 * transition rows each. The asserted quantity is a same-run difference (ADR 2026-10-05-2, D-127): the heap retained by the real
 * snapshots minus the heap retained by the same snapshots rebuilt through the four-argument {@link StatusSnapshot} constructor, which
 * carries no resolved map and no lifecycle types. {@code ProjectionCache.Entry} holds the whole snapshot, so this is the cost of the
 * resolved members in the cache, measured over public API only. A sensitivity control retains ten independent copies of the resolved structure
 * and must measure more growth than one copy by a stated factor, so the measurement can see growth. A miss fails once; there is no retry.
 */
@Tag("perf")
class Nfr009CacheGrowthTest {

  /** NFR-009: INITIAL and PROVISIONAL (ADR 2026-10-05-2); amended only by a measurement of the spec row, never by a retry. */
  static final long CEILING_BYTES = 64L * 1024 * 1024;

  /** The corpus size of the criterion. */
  static final int MISSIONS = 500;

  /** The control must grow at least this many times as much as one copy of the structure it multiplies (the ideal factor is ten). */
  static final double CONTROL_FACTOR = 4.0;

  /** How many copies of the resolved structure the sensitivity control retains. */
  static final int CONTROL_COPIES = 10;

  private static final MemoryMXBean MEMORY_BEAN = ManagementFactory.getMemoryMXBean();
  private static final StatusReducer REDUCER = new StatusReducer(new AtThenEventId());

  @Test
  void theCorpusHasTenWorkPackagesOfTenRowsInTheStatedOrderInEveryMission() {
    FixtureSpec spec = MissionCorpus.nfr009Spec(MISSIONS);
    assertThat(spec.missions()).hasSize(MISSIONS);
    InMemoryMissionEventSource source = InMemoryMissionEventSource.from(spec);
    for (FixtureSpec.Mission mission : spec.missions()) {
      List<LedgerLine> lines = linesOf(source, mission.name());
      assertThat(lines).as(mission.name() + " rows").hasSize(100);
      Map<String, List<String>> movesByPackage = new LinkedHashMap<>();
      long previousMinute = -1;
      for (LedgerLine line : lines) {
        StatusEvent event = ((LineKind.Status) line.kind()).event();
        movesByPackage.computeIfAbsent(event.wpId(), id -> new ArrayList<>()).add(event.fromLane().wire() + ">" + event.toLane().wire());
        long minute = Long.parseLong(event.at().substring(14, 16)) + 60L * Long.parseLong(event.at().substring(11, 13));
        assertThat(minute).as("timestamps ascend").isGreaterThan(previousMinute);
        previousMinute = minute;
      }
      assertThat(movesByPackage).as(mission.name() + " work packages").hasSize(10);
      List<String> expected = new ArrayList<>();
      for (String[] step : MissionCorpus.NFR009_STEPS) {
        expected.add(step[0] + ">" + step[1]);
      }
      assertThat(movesByPackage.values()).as(mission.name() + " moves per work package").allSatisfy(moves -> assertThat(moves).isEqualTo(expected));
    }
  }

  @Test
  void theResolvedMembersCostLessThanTheCeilingOverTheHistorylessSnapshots() {
    FixtureSpec spec = MissionCorpus.nfr009Spec(MISSIONS);

    long realBytes = retained(() -> reduceAll(spec, false));
    long historylessBytes = retained(() -> reduceAll(spec, true));
    long difference = realBytes - historylessBytes;

    long oneCopy = retained(() -> resolvedCopies(spec, 1));
    long tenCopies = retained(() -> resolvedCopies(spec, CONTROL_COPIES));

    System.out.println(
        String.format(
            Locale.ROOT,
            "PERF NFR-009 retained real %d B, history-less %d B, difference %d B (ceiling %d B); control: one copy %d B, %d copies %d B; %d cpus",
            realBytes,
            historylessBytes,
            difference,
            CEILING_BYTES,
            oneCopy,
            CONTROL_COPIES,
            tenCopies,
            Runtime.getRuntime().availableProcessors()));

    assertThat(difference).as("heap retained by the resolved members over the history-less snapshots").isLessThanOrEqualTo(CEILING_BYTES);
    assertThat(difference).as("the real leg retains the resolved members, so the measurement sees them").isPositive();
    assertThat((double) tenCopies).as("the sensitivity control sees " + CONTROL_COPIES + " times the resolved structure").isGreaterThanOrEqualTo(CONTROL_FACTOR * oneCopy);
  }

  /** Decodes and reduces every Mission; {@code historyless} rebuilds each snapshot through the four-argument constructor. */
  private static List<StatusSnapshot> reduceAll(FixtureSpec spec, boolean historyless) {
    List<StatusSnapshot> snapshots = new ArrayList<>(spec.missions().size());
    InMemoryMissionEventSource source = InMemoryMissionEventSource.from(spec);
    for (FixtureSpec.Mission mission : spec.missions()) {
      StatusSnapshot snapshot = REDUCER.reduceLines(linesOf(source, mission.name()));
      snapshots.add(historyless ? new StatusSnapshot(snapshot.workPackages(), snapshot.eventCount(), snapshot.lastEventId(), snapshot.materializedAt()) : snapshot);
    }
    return snapshots;
  }

  /** The decoded lines of one Mission, through the production codec (test classes reach it only by way of the test source). */
  private static List<LedgerLine> linesOf(InMemoryMissionEventSource source, String name) {
    MissionRef ref = new MissionRef(name);
    return source.readLedger(ref, source.stampLedger(ref)).lines();
  }

  /**
   * The sensitivity control: {@code copies} independent reductions of every Mission, of which only the resolved map is kept, so the heap grown
   * is {@code copies} times the resolved structure of the real leg (a copy of the map would share the records and prove nothing).
   */
  private static List<Map<String, WpResolved>> resolvedCopies(FixtureSpec spec, int copies) {
    List<Map<String, WpResolved>> held = new ArrayList<>();
    InMemoryMissionEventSource source = InMemoryMissionEventSource.from(spec);
    for (FixtureSpec.Mission mission : spec.missions()) {
      for (int copy = 0; copy < copies; copy++) {
        held.add(REDUCER.reduceLines(linesOf(source, mission.name())).resolved());
      }
    }
    return held;
  }

  /** The GC-settled heap retained by whatever the supplier builds: median of {@link Nfr004SseConnectionsTest#HEAP_SAMPLES} readings. */
  private static long retained(java.util.function.Supplier<Object> build) {
    long before = usedHeap();
    Object held = build.get();
    long after = usedHeap();
    java.lang.ref.Reference.reachabilityFence(held);
    return after - before;
  }

  private static long usedHeap() {
    long[] samples = new long[Nfr004SseConnectionsTest.HEAP_SAMPLES];
    for (int sample = 0; sample < samples.length; sample++) {
      for (int i = 0; i < 3; i++) {
        System.gc();
        try {
          Thread.sleep(100);
        } catch (InterruptedException interrupted) {
          Thread.currentThread().interrupt();
          throw new IllegalStateException(interrupted);
        }
      }
      samples[sample] = MEMORY_BEAN.getHeapMemoryUsage().getUsed();
    }
    return Nfr004SseConnectionsTest.median(samples);
  }
}
