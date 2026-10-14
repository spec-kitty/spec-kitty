package org.speckitty.missionstatus.domain.model;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

/** The latest review result of a Work Package (contract ReviewResult): reviewer handle, verdict text, reference text. Each may be absent. */
class ReviewResultRecordTest {

  @Test
  void itHoldsTheThreeMembersAsGiven() {
    ReviewResultRecord record = new ReviewResultRecord("reviewer-1", "approved", "feedback://x");
    assertThat(record.reviewer()).isEqualTo("reviewer-1");
    assertThat(record.verdict()).isEqualTo("approved");
    assertThat(record.reference()).isEqualTo("feedback://x");
  }

  @Test
  void aReviewerThatIsNoHandleIsNullAndTheOtherMembersMayBeNull() {
    ReviewResultRecord record = new ReviewResultRecord("not a handle", null, null);
    assertThat(record.reviewer()).isNull();
    assertThat(record.verdict()).isNull();
    assertThat(record.reference()).isNull();
  }

  @Test
  void aSentinelReviewerIsNull() {
    assertThat(new ReviewResultRecord("__resolved_model_absent__", "approved", "r").reviewer()).isNull();
  }
}
