package org.speckitty.missionstatus.perf;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

/** Pre-merge fold J10: the NFR-004 heap figure is a median of at least three GC-settled samples, so one outlier cannot decide it. */
@Tag("perf")
class Nfr004HeapMedianTest {

  @Test
  void theMedianIgnoresOneOutlierInEitherDirection() {
    assertThat(Nfr004SseConnectionsTest.median(new long[] {20, 21, 500, 19, 22})).isEqualTo(21);
    assertThat(Nfr004SseConnectionsTest.median(new long[] {500, 20, 21, 22, 23})).isEqualTo(22);
  }

  @Test
  void atLeastThreeSamplesAreTaken() {
    assertThat(Nfr004SseConnectionsTest.HEAP_SAMPLES).isGreaterThanOrEqualTo(3);
  }
}
