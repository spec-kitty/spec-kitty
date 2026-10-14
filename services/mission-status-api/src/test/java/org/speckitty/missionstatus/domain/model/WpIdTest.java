package org.speckitty.missionstatus.domain.model;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.Optional;
import org.junit.jupiter.api.Test;

/** E-5 / D-150: the typed Work Package identifier. {@code parse} is lenient and never throws; the constructor is strict (WpId.yaml: {@code ^WP[0-9]{2,}$}, at most 64). */
class WpIdTest {

  @Test
  void aWellFormedIdParsesAndKeepsItsValue() {
    assertThat(WpId.parse("WP01")).contains(new WpId("WP01"));
    assertThat(WpId.parse("WP100").orElseThrow().value()).isEqualTo("WP100");
    assertThat(WpId.parse("WP" + "7".repeat(62))).isPresent();
  }

  @Test
  void aMalformedIdParsesToEmptyAndNeverThrows() {
    String[] bad = {
      null,
      "",
      "WP",
      "WP1",
      "wp01",
      "Wp01",
      "WP01\n",
      "WP01 ",
      " WP01",
      "WP0a",
      "WPO1",
      "WP\u0661\u0662",
      "WP01\u0661",
      "WP" + "7".repeat(63),
      "XWP01",
      "WP-01",
      "WP01/../x"
    };
    for (String raw : bad) {
      assertThatCode(() -> WpId.parse(raw)).as(String.valueOf(raw)).doesNotThrowAnyException();
      assertThat(WpId.parse(raw)).as(String.valueOf(raw)).isEqualTo(Optional.empty());
    }
  }

  @Test
  void theConstructorRejectsWhatParseReturnsEmptyFor() {
    assertThatThrownBy(() -> new WpId("WP1")).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new WpId("wp01")).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new WpId("WP01\n")).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new WpId("WP" + "7".repeat(63))).isInstanceOf(IllegalArgumentException.class);
    assertThatThrownBy(() -> new WpId(null)).isInstanceOf(NullPointerException.class);
  }
}
