package org.speckitty.missionstatus.domain.model;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

class ReviewCycleMetaTest {

  @Test
  void anUnparsedFileHasTwoNullMembersAndEqualsAnyOtherPairOfNulls() {
    assertThat(ReviewCycleMeta.UNPARSED.reviewedAt()).isNull();
    assertThat(ReviewCycleMeta.UNPARSED.reviewer()).isNull();
    assertThat(ReviewCycleMeta.UNPARSED).isEqualTo(new ReviewCycleMeta(null, null));
  }

  @Test
  void aRecordCarriesItsMembers() {
    ReviewCycleMeta meta = new ReviewCycleMeta("2026-09-01T10:00:00Z", "claude");
    assertThat(meta.reviewedAt()).isEqualTo("2026-09-01T10:00:00Z");
    assertThat(meta.reviewer()).isEqualTo("claude");
    assertThat(meta).isNotEqualTo(ReviewCycleMeta.UNPARSED).hasSameHashCodeAs(new ReviewCycleMeta("2026-09-01T10:00:00Z", "claude"));
  }
}
