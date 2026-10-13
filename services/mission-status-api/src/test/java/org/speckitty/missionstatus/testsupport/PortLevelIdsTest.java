package org.speckitty.missionstatus.testsupport;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
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
