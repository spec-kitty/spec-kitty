package org.speckitty.missionstatus.application.query.stream;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Duration;
import org.junit.jupiter.api.Test;

/** The bound on open streams is one of the stream knobs: at least one, 128 by default, and the old three-argument form still builds. */
class StreamSettingsTest {

  @Test
  void aBoundBelowOneIsRefusedWithTheMovedMessage() {
    assertThatThrownBy(() -> new StreamSettings(Duration.ofMillis(500), Duration.ofSeconds(1), 1024, 0))
        .isInstanceOf(IllegalArgumentException.class)
        .hasMessage("mission-status.stream.max-connections must be at least 1");
    assertThatThrownBy(() -> StreamSettings.defaults().withMaxConnections(-1)).isInstanceOf(IllegalArgumentException.class).hasMessage("mission-status.stream.max-connections must be at least 1");
  }

  @Test
  void theThreeArgumentFormDefaultsTheBoundTo128() {
    StreamSettings settings = new StreamSettings(Duration.ofMillis(500), Duration.ofSeconds(1), 7);

    assertThat(settings.maxConnections()).isEqualTo(128).isEqualTo(StreamSettings.DEFAULT_MAX_CONNECTIONS);
    assertThat(settings.queueCapacity()).isEqualTo(7);
    assertThat(StreamSettings.defaults().maxConnections()).isEqualTo(128);
  }

  @Test
  void theWithersChangeOnlyTheirOwnKnob() {
    StreamSettings base = StreamSettings.defaults();

    assertThat(base.withMaxConnections(3)).isEqualTo(new StreamSettings(base.pollInterval(), base.relistInterval(), base.queueCapacity(), 3));
    assertThat(base.withQueueCapacity(9)).isEqualTo(new StreamSettings(base.pollInterval(), base.relistInterval(), 9, base.maxConnections()));
    assertThat(base.withMaxConnections(3).withQueueCapacity(9).maxConnections()).as("withQueueCapacity keeps the bound").isEqualTo(3);
  }
}
