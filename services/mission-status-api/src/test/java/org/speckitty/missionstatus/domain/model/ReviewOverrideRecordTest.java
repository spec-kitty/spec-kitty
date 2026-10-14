package org.speckitty.missionstatus.domain.model;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;

/** The review override slot ({@code ReviewOverride}): four stored texts, where empty means absent. {@code complete} is plain truthiness of all four. */
class ReviewOverrideRecordTest {

  @Test
  void allFourPresentIsComplete() {
    ReviewOverrideRecord record = new ReviewOverrideRecord("2026-09-01T10:00:00+00:00", "arbiter", "WP01", "because");
    assertThat(record.complete()).isTrue();
    assertThat(record.releaseSentinel()).isFalse();
  }

  @Test
  void aBlankReasonMakesItPartialButNotAReleaseSentinel() {
    ReviewOverrideRecord record = new ReviewOverrideRecord("2026-09-01T10:00:00+00:00", "arbiter", "WP01", "");
    assertThat(record.complete()).isFalse();
    assertThat(record.releaseSentinel()).isFalse();
  }

  @Test
  void whitespaceIsAValue() {
    assertThat(new ReviewOverrideRecord(" ", " ", " ", " ").complete()).isTrue();
  }

  @Test
  void allFourEmptyIsTheReleaseSentinel() {
    ReviewOverrideRecord record = new ReviewOverrideRecord("", "", "", "");
    assertThat(record.releaseSentinel()).isTrue();
    assertThat(record.complete()).isFalse();
  }

  @Test
  void nullMembersAreRefused() {
    assertThatThrownBy(() -> new ReviewOverrideRecord(null, "", "", "")).isInstanceOf(NullPointerException.class);
    assertThatThrownBy(() -> new ReviewOverrideRecord("", null, "", "")).isInstanceOf(NullPointerException.class);
    assertThatThrownBy(() -> new ReviewOverrideRecord("", "", null, "")).isInstanceOf(NullPointerException.class);
    assertThatThrownBy(() -> new ReviewOverrideRecord("", "", "", null)).isInstanceOf(NullPointerException.class);
  }

  @Test
  void eachSingleEmptyMemberMakesItIncompleteAndNotAReleaseSentinel() {
    ReviewOverrideRecord[] partial = {
      new ReviewOverrideRecord("", "b", "c", "d"), new ReviewOverrideRecord("a", "", "c", "d"), new ReviewOverrideRecord("a", "b", "", "d"), new ReviewOverrideRecord("a", "b", "c", "")
    };
    for (ReviewOverrideRecord record : partial) {
      assertThat(record.complete()).as(record.toString()).isFalse();
      assertThat(record.releaseSentinel()).as(record.toString()).isFalse();
    }
    ReviewOverrideRecord[] oneSet = {
      new ReviewOverrideRecord("a", "", "", ""), new ReviewOverrideRecord("", "b", "", ""), new ReviewOverrideRecord("", "", "c", ""), new ReviewOverrideRecord("", "", "", "d")
    };
    for (ReviewOverrideRecord record : oneSet) {
      assertThat(record.releaseSentinel()).as(record.toString()).isFalse();
    }
  }
}
