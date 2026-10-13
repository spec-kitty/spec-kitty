package org.speckitty.missionstatus.nativesmoke;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Tag;
import org.junit.jupiter.api.Test;

/** Skeleton (WP13 replaces the body): the binary-dependent perf probe only checks that its input is wired. */
@Tag("native-binary")
class NativePerfTest {

  @Test
  void theNativeBinaryPropertyIsForwardedByTheNativePerfTask() {
    assertThat(System.getProperty("nativeBinary")).as("the nativeBinary system property (-PnativeBinary)").isNotBlank();
  }
}
