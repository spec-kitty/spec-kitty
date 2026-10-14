package org.speckitty.missionstatus.domain.model;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

/** FR-020 / AC-20.1: the seven assignment handles. The four resolver sentinels read as null, never as their text; a value that is no handle is null. */
class AssignmentTest {

  @Test
  void anEmptyAssignmentHasSevenNullHandles() {
    assertThat(Assignment.EMPTY).isEqualTo(new Assignment(null, null, null, null, null, null, null));
  }

  @Test
  void aHandleIsKeptInItsOwnSlot() {
    Assignment assignment = new Assignment("claude", "alice", "implementer", "java-jenny", "1.2", "sonnet", "anthropic");
    assertThat(assignment.agent()).isEqualTo("claude");
    assertThat(assignment.assignee()).isEqualTo("alice");
    assertThat(assignment.role()).isEqualTo("implementer");
    assertThat(assignment.agentProfile()).isEqualTo("java-jenny");
    assertThat(assignment.agentProfileVersion()).isEqualTo("1.2");
    assertThat(assignment.model()).isEqualTo("sonnet");
    assertThat(assignment.provider()).isEqualTo("anthropic");
  }

  @Test
  void theFourResolverSentinelsAreNullNotTheirText() {
    Assignment assignment =
        new Assignment(null, null, null, "__resolved_profile_absent__", "__resolved_profile_version_absent__", "__resolved_model_absent__", "__resolved_provider_absent__");
    assertThat(assignment).isEqualTo(Assignment.EMPTY);
  }

  @Test
  void aSentinelInAnotherSlotIsStillNullBecauseNoSlotCanHoldASentinel() {
    assertThat(new Assignment("__resolved_model_absent__", null, null, null, null, null, null).agent()).isNull();
  }

  @Test
  void aValueThatIsNoHandleIsNull() {
    Assignment assignment = new Assignment("a b", "user@example.com", "", "x".repeat(129), "ok\n", null, "good");
    assertThat(assignment).isEqualTo(new Assignment(null, null, null, null, null, null, "good"));
  }
}
