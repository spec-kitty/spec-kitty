package org.speckitty.missionstatus.application.query.port.out.exceptions;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Arrays;
import org.junit.jupiter.api.Test;

/**
 * D-91 and D-68: the text-read port has its own fault type, so {@code SourceFault.Kind} keeps its five values. A sixth constant would
 * break the four exhaustive switches (ChangeFeed#metaStageCode, ChangeFeed#ledgerStageCode, MissionStatusQueryService#ledgerFault,
 * MissionStatusQueryService#omitted); this test makes it a review item.
 */
class SourceFaultKindsTest {

  @Test
  void sourceFaultKindStillHasExactlyItsFiveValues() {
    assertThat(Arrays.stream(SourceFault.Kind.values()).map(Enum::name).toList())
        .containsExactly("VANISHED", "PATH_REFUSED", "META_UNPARSEABLE", "DIR_UNREADABLE", "LEDGER_UNREADABLE");
  }

  @Test
  void textFaultIsItsOwnUncheckedTypeWithFourKindsAndNoMessage() {
    assertThat(Arrays.stream(TextFault.Kind.values()).map(Enum::name).toList()).containsExactly("PATH_REFUSED", "VANISHED", "DIR_UNREADABLE", "FILE_UNREADABLE");
    assertThat(RuntimeException.class).isAssignableFrom(TextFault.class);
    assertThat(SourceFault.class.isAssignableFrom(TextFault.class)).isFalse();
    TextFault fault = new TextFault(TextFault.Kind.VANISHED);
    assertThat(fault.kind()).isEqualTo(TextFault.Kind.VANISHED);
    assertThat(fault.getMessage()).isNull();
    assertThat(fault.getCause()).isNull();
    assertThat(java.lang.reflect.Modifier.isFinal(TextFault.class.getModifiers())).isTrue();
  }

  @Test
  void aTextFaultKindCannotBeNull() {
    org.assertj.core.api.Assertions.assertThatThrownBy(() -> new TextFault(null)).isInstanceOf(NullPointerException.class);
  }
}
