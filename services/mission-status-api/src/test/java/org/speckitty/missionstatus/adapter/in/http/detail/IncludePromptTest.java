package org.speckitty.missionstatus.adapter.in.http.detail;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.Test;

/** {@code includePrompt}: absent is false; exactly one {@code true} or {@code false} is that boolean; anything else is refused (OQ-2, AC-2.5). */
class IncludePromptTest {

  @Test
  void absentIsFalse() {
    assertThat(IncludePrompt.parse(List.of())).contains(false);
  }

  @Test
  void trueAndFalseAreThemselves() {
    assertThat(IncludePrompt.parse(List.of("true"))).contains(true);
    assertThat(IncludePrompt.parse(List.of("false"))).contains(false);
  }

  @Test
  void everythingElseIsRefused() {
    for (String value : new String[] {"1", "0", "yes", "no", "TRUE", "False", "True", "", " true", "true ", "tru"}) {
      assertThat(IncludePrompt.parse(List.of(value))).as("value '%s'", value).isEqualTo(Optional.empty());
    }
  }

  @Test
  void aRepeatedParameterIsRefusedEvenWhenBothAgree() {
    assertThat(IncludePrompt.parse(List.of("true", "true"))).isEmpty();
    assertThat(IncludePrompt.parse(List.of("true", "false"))).isEmpty();
  }
}
