package org.speckitty.missionstatus.nativesmoke;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.LinkedHashMap;
import java.util.Map;
import org.junit.jupiter.api.Test;

/** The locale the smoke harness gives the binary it launches (FR-004, D-90): UTF-8 off Windows, untouched on Windows. */
class NativeSmokeLocaleTest {

  @Test
  void aPosixHostGetsAUtf8LocaleForTheChild() {
    Map<String, String> environment = new LinkedHashMap<>(Map.of("PATH", "/usr/bin"));

    NativeSmokeTest.applyLocale(environment, false);

    assertThat(environment).containsEntry("LC_ALL", "C.UTF-8").containsEntry("PATH", "/usr/bin");
  }

  @Test
  void windowsIsLeftAsItIs() {
    Map<String, String> environment = new LinkedHashMap<>(Map.of("PATH", "C:\\Windows"));
    Map<String, String> before = new LinkedHashMap<>(environment);

    NativeSmokeTest.applyLocale(environment, true);

    assertThat(environment).isEqualTo(before);
  }

  @Test
  void aDifferentLocaleAlreadyInTheEnvironmentIsOverridden() {
    Map<String, String> environment = new LinkedHashMap<>(Map.of("LC_ALL", "C"));

    NativeSmokeTest.applyLocale(environment, false);

    assertThat(environment).containsEntry("LC_ALL", "C.UTF-8").hasSize(1);
  }
}
