package org.speckitty.missionstatus.domain.readmodel.overview;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import org.junit.jupiter.api.Test;

class InstantsTest {

  @Test
  void parsesOffsetsAndFractionsToTheSameInstantScale() {
    assertThat(Instants.parse("2026-09-01T09:00:00Z")).isEqualTo(Instant.parse("2026-09-01T09:00:00Z"));
    assertThat(Instants.parse("2026-09-01T11:00:00+02:00")).isEqualTo(Instant.parse("2026-09-01T09:00:00Z"));
    assertThat(Instants.parse("2026-09-01T09:00:00+00:00")).isEqualTo(Instant.parse("2026-09-01T09:00:00Z"));
    assertThat(Instants.parse("2026-09-01T11:00:00.123456Z")).isEqualTo(Instant.parse("2026-09-01T11:00:00.123456Z"));
  }

  @Test
  void anOffsetlessTimestampIsReadAsUtc() {
    assertThat(Instants.parse("2026-09-01T09:00:00")).isEqualTo(Instant.parse("2026-09-01T09:00:00Z"));
  }

  @Test
  void anInvalidInstantIsATypedErrorNotAGuess() {
    assertThatThrownBy(() -> Instants.parse("yesterday")).isInstanceOf(InvalidInstantException.class);
    assertThatThrownBy(() -> Instants.parse("")).isInstanceOf(InvalidInstantException.class);
  }
}
