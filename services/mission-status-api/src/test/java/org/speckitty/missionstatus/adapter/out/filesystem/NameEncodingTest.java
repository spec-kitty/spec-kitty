package org.speckitty.missionstatus.adapter.out.filesystem;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

/** FRESH3-004: the host probe for file-name decoding; the stub leg runs under any locale (AC-4.8, AC-6.6). */
class NameEncodingTest {

  @Test
  void aWindowsHostIsTrustworthyWhateverTheJnuEncoding() {
    assertThat(new NameEncoding(true, "ISO-8859-1").trustworthy()).isTrue();
    assertThat(new NameEncoding(true, null).trustworthy()).isTrue();
  }

  @Test
  void aNonWindowsHostIsTrustworthyOnlyWithAUtf8JnuEncoding() {
    assertThat(new NameEncoding(false, "UTF-8").trustworthy()).isTrue();
    assertThat(new NameEncoding(false, "utf-8").trustworthy()).isTrue();
    assertThat(new NameEncoding(false, "UTF8").trustworthy()).isTrue();
    assertThat(new NameEncoding(false, "ANSI_X3.4-1968").trustworthy()).isFalse();
    assertThat(new NameEncoding(false, "ISO-8859-1").trustworthy()).isFalse();
    assertThat(new NameEncoding(false, null).trustworthy()).isFalse();
  }

  @Test
  void theHostProbeReadsTheRunningJvm() {
    boolean windows = System.getProperty("os.name", "").toLowerCase(java.util.Locale.ROOT).startsWith("windows");
    String jnu = System.getProperty("sun.jnu.encoding");
    assertThat(NameEncoding.host().trustworthy()).isEqualTo(windows || (jnu != null && jnu.replace("-", "").equalsIgnoreCase("UTF8")));
  }

  @Test
  void aFixedAnswerStubIsAvailableForTestsUnderAnyLocale() {
    assertThat(NameEncoding.fixed(true).trustworthy()).isTrue();
    assertThat(NameEncoding.fixed(false).trustworthy()).isFalse();
  }
}
