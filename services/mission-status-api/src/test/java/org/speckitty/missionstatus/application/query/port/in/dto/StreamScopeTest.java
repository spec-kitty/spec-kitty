package org.speckitty.missionstatus.application.query.port.in.dto;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.speckitty.missionstatus.application.query.port.in.exceptions.StreamRefused;
import org.speckitty.missionstatus.domain.model.MissionId;
import org.speckitty.missionstatus.testsupport.Rows;

/** {@code StreamScope.parse}: the mapping that used to live in the HTTP controller, now one rule for every adapter. */
class StreamScopeTest {

  @Test
  void noMissionIdIsEveryMission() {
    assertThat(StreamScope.parse(null)).isEqualTo(StreamScope.all());
  }

  @Test
  void aUlidIsThatMission() {
    assertThat(StreamScope.parse(Rows.ALPHA_ID)).isEqualTo(StreamScope.mission(new MissionId(Rows.ALPHA_ID)));
  }

  @ParameterizedTest
  @ValueSource(strings = {"", "not-a-ulid", "01J0100000000000000000000", "01J010000000000000000000011", "01j01000000000000000000001", "../etc", "01J0100000000000000000000!"})
  void anythingElseIsAnUnknownMission(String text) {
    assertThatThrownBy(() -> StreamScope.parse(text))
        .isInstanceOfSatisfying(StreamRefused.class, refused -> assertThat(refused.kind()).isEqualTo(StreamRefused.Kind.UNKNOWN_MISSION))
        .satisfies(thrown -> assertThat(((StreamRefused) thrown).detail()).isEmpty());
  }
}
