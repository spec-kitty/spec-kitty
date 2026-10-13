package org.speckitty.missionstatus.nativesmoke;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.nio.charset.StandardCharsets;
import java.util.Map;
import org.junit.jupiter.api.Test;

/** The replay's own guards (T065 steps 1, 2 and 4) that need no server: raw-byte comparison and the failure-on-empty rules. */
class ReplayGuardsTest {

  private static byte[] bytes(String text) {
    return text.getBytes(StandardCharsets.UTF_8);
  }

  @Test
  void aBodyEqualToTheGoldenAsADocumentButNotAsBytesFails() {
    byte[] golden = bytes("{\"a\":1,\"b\":2}\n");
    Replay.compareToGolden("x", bytes("{\"a\":1,\"b\":2}\n"), golden);
    assertThatThrownBy(() -> Replay.compareToGolden("x", bytes("{\"b\":2,\"a\":1}\n"), golden)).isInstanceOf(AssertionError.class).hasMessageContaining("x");
    assertThatThrownBy(() -> Replay.compareToGolden("x", bytes("{ \"a\":1,\"b\":2 }\n"), golden)).isInstanceOf(AssertionError.class);
    assertThatThrownBy(() -> Replay.compareToGolden("x", bytes("{\"a\":1,\"b\":2}"), golden)).isInstanceOf(AssertionError.class);
    assertThatThrownBy(() -> Replay.compareToGolden("x", bytes("{\"a\":1.0,\"b\":2}\n"), golden)).isInstanceOf(AssertionError.class);
  }

  @Test
  void aSingleChangedByteOfTheGoldenFails() {
    byte[] golden = bytes("{\"name\":\"fixture-project\"}\n");
    byte[] changed = golden.clone();
    changed[10] ^= 0x01;
    assertThatThrownBy(() -> Replay.compareToGolden("project", golden, changed)).isInstanceOf(AssertionError.class).hasMessageContaining("project");
  }

  @Test
  void zeroRequestsReplayedFails() {
    assertThatThrownBy(() -> Replay.requireCounts(0, 0)).isInstanceOf(AssertionError.class).hasMessageContaining("no request");
  }

  @Test
  void zeroBodiesComparedFails() {
    assertThatThrownBy(() -> Replay.requireCounts(3, 0)).isInstanceOf(AssertionError.class).hasMessageContaining("no body");
    Replay.requireCounts(3, 3);
  }

  @Test
  void fewerRequestsThanAnyStageFloorFails() {
    SmokeRequests requests = SmokeRequests.load();
    int base = requests.floor("base");
    int hostOrigin = requests.floor("hostOrigin");
    assertThatThrownBy(() -> Replay.requireFloors(requests, Map.of("base", base - 1, "hostOrigin", hostOrigin))).isInstanceOf(AssertionError.class).hasMessageContaining("base");
    assertThatThrownBy(() -> Replay.requireFloors(requests, Map.of("base", base, "hostOrigin", hostOrigin - 1))).isInstanceOf(AssertionError.class).hasMessageContaining("hostOrigin");
    assertThatThrownBy(() -> Replay.requireFloors(requests, Map.of("base", base))).isInstanceOf(AssertionError.class).hasMessageContaining("hostOrigin");
    assertThatThrownBy(() -> Replay.requireFloors(requests, Map.of())).isInstanceOf(AssertionError.class).hasMessageContaining("base");
    Replay.requireFloors(requests, Map.of("base", base, "hostOrigin", hostOrigin));
  }

  @Test
  void thePortPlaceholderIsFilledInHeaderValuesAndInThePathAndNowhereElse() {
    Map<String, String> headers = Replay.withPort(Map.of("Host", "evil.example:<port>", "Origin", "http://127.0.0.1:<port>", "Accept", "text/event-stream"), 4321);
    assertThat(headers).containsEntry("Host", "evil.example:4321").containsEntry("Origin", "http://127.0.0.1:4321").containsEntry("Accept", "text/event-stream");
    assertThat(Replay.withPort("/api/v1/project?x=<port>", 4321)).isEqualTo("/api/v1/project?x=4321");
    assertThat(Replay.withPort(Map.of("Host", "no-placeholder"), 4321)).containsEntry("Host", "no-placeholder");
  }
}
