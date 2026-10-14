package org.speckitty.missionstatus.domain.readmodel.derive;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.domain.model.Lane;
import org.speckitty.missionstatus.domain.model.WpId;
import org.speckitty.missionstatus.domain.model.WpState;
import org.speckitty.missionstatus.domain.readmodel.detail.Readiness;

/**
 * The port of {@code dependency_readiness_for_wp}: approved and done satisfy a dependency, canceled only with operator provenance, every
 * other lane (and an id that names no Work Package) does not.
 */
class ReadinessDeriverTest {

  private static WpState state(Lane lane, String reasonSource) {
    return new WpState(lane, "2026-09-01T10:00:00+00:00", "000000000000000000000000Z9", 0, null, reasonSource, null);
  }

  private static WpId wp(String id) {
    return new WpId(id);
  }

  @Test
  void noDependenciesIsSatisfied() {
    assertThat(ReadinessDeriver.derive(List.of(), Map.of())).isEqualTo(new Readiness(true, List.of()));
  }

  @Test
  void approvedAndDoneSatisfyAndEveryOtherLaneDoesNot() {
    Map<String, WpState> states = new LinkedHashMap<>();
    int index = 1;
    List<WpId> all = new java.util.ArrayList<>();
    for (Lane lane : Lane.values()) {
      String id = String.format("WP%02d", index++);
      states.put(id, state(lane, null));
      all.add(wp(id));
    }

    Readiness readiness = ReadinessDeriver.derive(all, states);

    List<String> unsatisfied = readiness.unsatisfied().stream().map(WpId::value).toList();
    for (Lane lane : Lane.values()) {
      String id = String.format("WP%02d", lane.ordinal() + 1);
      boolean satisfied = lane == Lane.APPROVED || lane == Lane.DONE;
      assertThat(unsatisfied.contains(id)).as(lane.wire()).isEqualTo(!satisfied);
    }
    assertThat(readiness.satisfied()).isFalse();
  }

  @Test
  void canceledSatisfiesOnlyWithOperatorProvenance() {
    Map<String, WpState> states =
        Map.of(
            "WP01", state(Lane.CANCELED, "operator"),
            "WP02", state(Lane.CANCELED, "synthetic"),
            "WP03", state(Lane.CANCELED, null),
            "WP04", state(Lane.CANCELED, "Operator"));

    Readiness readiness = ReadinessDeriver.derive(List.of(wp("WP01"), wp("WP02"), wp("WP03"), wp("WP04")), states);

    assertThat(readiness.unsatisfied()).containsExactly(wp("WP02"), wp("WP03"), wp("WP04"));
  }

  @Test
  void anIdThatNamesNoWorkPackageStaysUnsatisfied() {
    Readiness readiness = ReadinessDeriver.derive(List.of(wp("WP99")), Map.of("WP01", state(Lane.DONE, null)));

    assertThat(readiness).isEqualTo(new Readiness(false, List.of(wp("WP99"))));
  }

  @Test
  void theUnsatisfiedListKeepsDependencyOrderAndRepeats() {
    Map<String, WpState> states = Map.of("WP02", state(Lane.DONE, null), "WP05", state(Lane.PLANNED, null), "WP03", state(Lane.IN_PROGRESS, null));

    Readiness readiness = ReadinessDeriver.derive(List.of(wp("WP05"), wp("WP02"), wp("WP03"), wp("WP05")), states);

    assertThat(readiness.unsatisfied()).containsExactly(wp("WP05"), wp("WP03"), wp("WP05"));
    assertThat(readiness.satisfied()).isFalse();
  }

  @Test
  void aSatisfiedListIsSatisfied() {
    Map<String, WpState> states = Map.of("WP01", state(Lane.APPROVED, null), "WP02", state(Lane.DONE, null));

    assertThat(ReadinessDeriver.derive(List.of(wp("WP01"), wp("WP02")), states)).isEqualTo(new Readiness(true, List.of()));
  }

  @Test
  void readyToStartNeedsAPlannedLaneAndSatisfiedDependencies() {
    Readiness satisfied = new Readiness(true, List.of());
    Readiness unsatisfied = new Readiness(false, List.of(wp("WP01")));

    assertThat(ReadinessDeriver.readyToStart(Lane.PLANNED, satisfied)).isTrue();
    assertThat(ReadinessDeriver.readyToStart(Lane.PLANNED, unsatisfied)).isFalse();
    assertThat(ReadinessDeriver.readyToStart(null, satisfied)).as("a null lane is never ready").isFalse();
    for (Lane lane : Lane.values()) {
      if (lane != Lane.PLANNED) {
        assertThat(ReadinessDeriver.readyToStart(lane, satisfied)).as(lane.wire()).isFalse();
      }
    }
  }
}
