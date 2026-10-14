package org.speckitty.missionstatus.conformance.golden;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.stream.Collectors;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.testsupport.Fixture;
import org.speckitty.missionstatus.testsupport.FixtureFactory;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.PortLevelIds;
import org.speckitty.missionstatus.testsupport.PortLevelIds.Entry;
import org.speckitty.missionstatus.testsupport.PortLevelRun;
import org.speckitty.missionstatus.testsupport.PortLevelRun.Outcome;
import org.speckitty.missionstatus.testsupport.PortLevelRun.Status;
import org.speckitty.missionstatus.testsupport.PortSourceSelector;

/**
 * T051 (AC-13a, AC-13b): the port-level subset of {@code portlevel-tests.txt} runs on BOTH sources. The first leg is the in-memory
 * source, the second the real filesystem source, installed through {@link PortSourceSelector#override}. This class imports
 * {@code testsupport} only, so ArchUnit rule 11 stays true; the {@code conformance.port} classes are not touched.
 */
class PortSubsetSecondLegTest {

  /** What one leg did: the outcome per id and how many fixtures each id opened through the selector. */
  private record Leg(Map<String, Outcome> outcomes, Map<String, Integer> opened, Set<Class<?>> fixtureTypes) {}

  private static Leg run(String name, java.util.function.Function<org.speckitty.missionstatus.testsupport.FixtureSpec, Fixture> factory) throws Exception {
    Map<String, Outcome> outcomes = new LinkedHashMap<>();
    Map<String, Integer> opened = new LinkedHashMap<>();
    Set<Class<?>> types = new LinkedHashSet<>();
    AtomicInteger counter = new AtomicInteger();
    try (AutoCloseable installed =
        PortSourceSelector.override(
            spec -> {
              counter.incrementAndGet();
              Fixture fixture = factory.apply(spec);
              types.add(fixture.getClass());
              return fixture;
            })) {
      for (Entry entry : PortLevelIds.load()) {
        int before = counter.get();
        outcomes.putAll(PortLevelRun.run(List.of(entry)));
        opened.put(entry.id(), counter.get() - before);
      }
    }
    assertThat(PortSourceSelector.isDefault()).as(name + " restores the default source").isTrue();
    return new Leg(outcomes, opened, types);
  }

  private static Set<String> idsWith(Leg leg, Status status) {
    return leg.outcomes().values().stream().filter(outcome -> outcome.status() == status).map(outcome -> outcome.entry().id()).collect(Collectors.toCollection(LinkedHashSet::new));
  }

  @Test
  void theSamePortLevelIdsRunOnBothSourcesAndEqualTheFilesIds() throws Exception {
    List<Entry> entries = PortLevelIds.load();
    Set<String> fileIds = PortLevelIds.ids(entries);

    Leg memory = run("in-memory", FixtureFactory::build);
    Leg filesystem = run("filesystem", FilesystemFixtureFactory::fromSpec);

    for (Map.Entry<String, Leg> leg : Map.of("in-memory", memory, "filesystem", filesystem).entrySet()) {
      Leg value = leg.getValue();
      assertThat(idsWith(value, Status.FAILED)).as(leg.getKey() + " failed: " + value.outcomes().values().stream().filter(o -> o.status() == Status.FAILED).toList()).isEmpty();
      assertThat(idsWith(value, Status.SKIPPED)).as(leg.getKey() + " skipped").isEmpty();
      assertThat(idsWith(value, Status.EXECUTED)).as(leg.getKey() + " executed ids equal the file's ids").isEqualTo(fileIds);
    }
    assertThat(idsWith(filesystem, Status.EXECUTED)).as("the second run executes as many ids as the first").hasSameSizeAs(idsWith(memory, Status.EXECUTED));
    assertThat(filesystem.opened().keySet()).isEqualTo(memory.opened().keySet());
  }

  @Test
  void theSecondLegReallyWentThroughTheFilesystemSourceAndTheFirstThroughMemory() throws Exception {
    Leg memory = run("in-memory", FixtureFactory::build);
    Leg filesystem = run("filesystem", FilesystemFixtureFactory::fromSpec);

    assertThat(memory.fixtureTypes()).containsExactly(FixtureFactory.Built.class);
    assertThat(filesystem.fixtureTypes()).containsExactly(FilesystemFixtureFactory.Built.class);
    for (String id : List.of("AC-2a/interleaved", "AC-2a/lifecycle-only", "AC-2a/no-ledger", "AC-2a/log-truncated", "AC-2a/crlf-and-listing", "AC-2b/page-size-one", "AC-4a/L4", "AC-3g/resume-after-k")) {
      assertThat(filesystem.opened().get(id)).as(id + " opened a filesystem fixture").isPositive();
      assertThat(memory.opened().get(id)).as(id + " opened an in-memory fixture").isPositive();
    }
    Set<String> noFixtureInMemory = memory.opened().entrySet().stream().filter(e -> e.getValue() == 0).map(Map.Entry::getKey).collect(Collectors.toCollection(LinkedHashSet::new));
    Set<String> noFixtureOnDisk = filesystem.opened().entrySet().stream().filter(e -> e.getValue() == 0).map(Map.Entry::getKey).collect(Collectors.toCollection(LinkedHashSet::new));
    assertThat(noFixtureOnDisk).as("the ids that open no fixture are the same on both legs").isEqualTo(noFixtureInMemory);
    assertThat(noFixtureOnDisk).as("every id opens a fixture on the second leg").isEmpty();
  }

  @Test
  void theFileHoldsAtLeastTheIdsFr013NamesAndAnEmptiedListFails() {
    List<Entry> entries = PortLevelIds.load();

    assertThat(PortLevelIds.unmetFloorGroups(entries)).as("the FR-013 floor").isEmpty();
    assertThat(PortLevelIds.ids(entries)).contains("AC-2a/interleaved", "AC-2a/lifecycle-only", "AC-2a/no-ledger", "AC-2a/log-truncated", "AC-2a/crlf-and-listing");
    assertThat(entries.size()).isGreaterThanOrEqualTo(PortLevelIds.FR013_GROUPS.size());
    assertThat(PortLevelIds.unmetFloorGroups(new ArrayList<>())).as("an emptied list leaves every group unmet").containsExactlyElementsOf(PortLevelIds.FR013_GROUPS);
  }
}
