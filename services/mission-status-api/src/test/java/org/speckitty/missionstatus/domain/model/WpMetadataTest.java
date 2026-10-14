package org.speckitty.missionstatus.domain.model;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatNullPointerException;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;

class WpMetadataTest {

  private static WpMetadata of(String id, List<String> list) {
    return new WpMetadata(id, "t", "p", "tt", "pr", "em", "mt", "pb", "r", "ap", "m", list, list, list, list, list, false);
  }

  @Test
  void aRecordHoldsItsMembersAndEqualsAnotherWithTheSameValues() {
    WpMetadata metadata = of("WP01", List.of("a"));
    assertThat(metadata.workPackageId()).isEqualTo("WP01");
    assertThat(metadata.title()).isEqualTo("t");
    assertThat(metadata).isEqualTo(of("WP01", List.of("a"))).hasSameHashCodeAs(of("WP01", List.of("a")));
    assertThat(metadata).isNotEqualTo(of("WP02", List.of("a")));
  }

  @Test
  void theListsAreCopiedSoALaterChangeOfTheSourceDoesNotReachTheRecord() {
    List<String> source = new ArrayList<>(List.of("a"));
    WpMetadata metadata = of("WP01", source);
    source.add("b");
    assertThat(metadata.dependencies()).containsExactly("a");
    assertThat(metadata.subtasks()).containsExactly("a");
    assertThatThrownBy(() -> metadata.ownedFiles().add("x")).isInstanceOf(UnsupportedOperationException.class);
  }

  @Test
  void theIdentifierIsRequiredAndTheListsMayNotBeNull() {
    assertThatNullPointerException().isThrownBy(() -> of(null, List.of()));
    assertThatNullPointerException().isThrownBy(() -> new WpMetadata("WP01", null, null, null, null, null, null, null, null, null, null, null, List.of(), List.of(), List.of(), List.of(), false));
  }

  @Test
  void theTextMembersMayBeNull() {
    WpMetadata metadata = new WpMetadata("WP01", null, null, null, null, null, null, null, null, null, null, List.of(), List.of(), List.of(), List.of(), List.of(), true);
    assertThat(metadata.title()).isNull();
    assertThat(metadata.subtasksRefused()).isTrue();
  }
}
