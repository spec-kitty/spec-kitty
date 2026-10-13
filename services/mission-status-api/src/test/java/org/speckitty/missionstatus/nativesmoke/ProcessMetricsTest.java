package org.speckitty.missionstatus.nativesmoke;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

/** The carrier match on kernel thread names, including names that merely look like a carrier's. */
class ProcessMetricsTest {

  @Test
  void theRealCarrierNamesAreRecognisedWholeAndTruncated() {
    assertThat(ProcessMetrics.isCarrierName("ForkJoinPool-1-worker-1")).as("untruncated").isTrue();
    assertThat(ProcessMetrics.isCarrierName("Pool-1-worker-1")).as("last 15 characters").isTrue();
    assertThat(ProcessMetrics.isCarrierName("ool-1-worker-10")).as("last 15 characters, two-digit worker").isTrue();
    assertThat(ProcessMetrics.isCarrierName("ol-1-worker-24")).as("shorter than 15 is not a truncation of a longer name").isFalse();
    assertThat(ProcessMetrics.isCarrierName("Pool-12-worker-1")).as("16 characters cannot come from the kernel").isFalse();
  }

  @Test
  void lookalikeNamesAreNotCarriers() {
    assertThat(ProcessMetrics.isCarrierName("pool-1-worker-1")).as("lower-case p").isFalse();
    assertThat(ProcessMetrics.isCarrierName("XPool-1-worker-1")).isFalse();
    assertThat(ProcessMetrics.isCarrierName("MyForkJoinPool-1-worker-1")).isFalse();
    assertThat(ProcessMetrics.isCarrierName("io-worker-1")).isFalse();
    assertThat(ProcessMetrics.isCarrierName("http-nio-8080-exec-1")).isFalse();
    assertThat(ProcessMetrics.isCarrierName("events-12")).isFalse();
    assertThat(ProcessMetrics.isCarrierName("custom-1-worker-2")).isFalse();
    assertThat(ProcessMetrics.isCarrierName("")).isFalse();
  }

  @Test
  void aRealThreadOfThisJvmIsNotMistakenForACarrierByItsKernelName() {
    assertThat(ProcessMetrics.isCarrierName(Thread.currentThread().getName())).isFalse();
  }
}
