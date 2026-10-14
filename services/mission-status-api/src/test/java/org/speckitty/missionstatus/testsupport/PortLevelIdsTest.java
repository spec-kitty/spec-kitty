package org.speckitty.missionstatus.testsupport;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.testsupport.PortLevelIds.Entry;

class PortLevelIdsTest {

  @Test
  void aLineIsAnIdAClassAndAMethod() {
    List<Entry> entries = PortLevelIds.parse("# a comment\n\nAC-4a/L3a Ac4aPortLegsTest#someMethod\nAC-5c Ac5ReductionTest#other\n");

    assertThat(entries).containsExactly(new Entry("AC-4a/L3a", "Ac4aPortLegsTest", "someMethod"), new Entry("AC-5c", "Ac5ReductionTest", "other"));
    assertThat(entries.getFirst().qualifiedClassName()).isEqualTo("org.speckitty.missionstatus.conformance.port.Ac4aPortLegsTest");
  }

  @Test
  void aMalformedLineIsRefusedNamingItsNumber() {
    assertThatThrownBy(() -> PortLevelIds.parse("AC-2b Ac2bPagingTest#ok\nAC-2b not a line\n")).hasMessageContaining("line 2");
    assertThatThrownBy(() -> PortLevelIds.parse("ac-2b Ac2bPagingTest#ok\n")).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> PortLevelIds.parse("AC-2b/ Ac2bPagingTest#ok\n")).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> PortLevelIds.parse("AC-2b Ac2bPagingTest.ok\n")).isInstanceOf(IllegalArgumentException.class);
  }

  @Test
  void aRepeatedIdIsRefused() {
    assertThatThrownBy(() -> PortLevelIds.parse("AC-2b Ac2bPagingTest#one\nAC-2b Ac2bPagingTest#two\n")).hasMessageContaining("repeats id AC-2b");
  }

  @Test
  void theCommittedFileParsesAndMeetsTheFr013Floor() {
    List<Entry> entries = PortLevelIds.load();

    assertThat(PortLevelIds.unmetFloorGroups(entries)).as("FR-013 id groups with no listed id").isEmpty();
    assertThat(entries.size()).as("the recorded id count").isGreaterThanOrEqualTo(PortLevelIds.FR013_GROUPS.size());
  }

  @Test
  void everyListedIdRunsExceptTheInterimGoldenDependentOnes() {
    List<Entry> entries = PortLevelIds.load();

    assertThat(PortLevelIds.INTERIM_GOLDEN_DEPENDENT_IDS).as("a skip list may only name AC-2a ids of the file").isSubsetOf(PortLevelIds.ids(entries));
    assertThat(PortLevelIds.INTERIM_GOLDEN_DEPENDENT_IDS).allMatch(id -> id.startsWith("AC-2a/"));

    Map<String, PortLevelRun.Outcome> outcomes = PortLevelRun.run(entries);

    assertThat(outcomes.values().stream().filter(o -> o.status() == PortLevelRun.Status.FAILED)).as("failed ids").isEmpty();
    assertThat(statusIds(outcomes, PortLevelRun.Status.SKIPPED)).as("skipped ids").isEqualTo(PortLevelIds.INTERIM_GOLDEN_DEPENDENT_IDS);
    Set<String> expectedExecuted = new HashSet<>(PortLevelIds.ids(entries));
    expectedExecuted.removeAll(PortLevelIds.INTERIM_GOLDEN_DEPENDENT_IDS);
    assertThat(statusIds(outcomes, PortLevelRun.Status.EXECUTED)).as("executed ids").isEqualTo(expectedExecuted);
  }

  private static Set<String> statusIds(Map<String, PortLevelRun.Outcome> outcomes, PortLevelRun.Status status) {
    return outcomes.entrySet().stream().filter(e -> e.getValue().status() == status).map(Map.Entry::getKey).collect(Collectors.toSet());
  }

  @Test
  void anEmptiedListFailsTheFloor() {
    assertThat(PortLevelIds.unmetFloorGroups(List.of())).isEqualTo(PortLevelIds.FR013_GROUPS);
    assertThat(PortLevelIds.unmetFloorGroups(PortLevelIds.parse("AC-2b/page-size-one Ac2bPagingTest#x\n"))).doesNotContain("AC-2b").contains("AC-5a");
  }

  @Test
  void aGroupIsMetByItsOwnIdOrACaseUnderIt() {
    assertThat(PortLevelIds.unmetFloorGroups(PortLevelIds.parse("AC-4a/L1/discarded Ac4aPortLegsTest#x\n"))).doesNotContain("AC-4a/L1").contains("AC-4a/L3a");
    assertThat(PortLevelIds.unmetFloorGroups(PortLevelIds.parse("AC-4a/L10 Ac4aPortLegsTest#x\n"))).contains("AC-4a/L1");
  }
}
