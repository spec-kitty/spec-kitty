package org.speckitty.missionstatus.adapter.out.filesystem.codec;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;

/** AC-7.3 unit control: the strict decoder rejects each malformed shape and never replaces a byte (D-70). */
class StrictUtf8Test {

  private static byte[] bytes(int... values) {
    byte[] out = new byte[values.length];
    for (int i = 0; i < values.length; i++) {
      out[i] = (byte) values[i];
    }
    return out;
  }

  private static void assertRejected(String label, byte[] input) {
    assertThat(StrictUtf8.decode(input)).as(label).isInstanceOf(StrictUtf8.Decoded.Rejected.class);
  }

  @Test
  void eachMalformedShapeIsRejected() {
    assertRejected("overlong C0 AF", bytes(0xC0, 0xAF));
    assertRejected("encoded surrogate ED A0 80", bytes(0xED, 0xA0, 0x80));
    assertRejected("above U+10FFFF F4 90 80 80", bytes(0xF4, 0x90, 0x80, 0x80));
    assertRejected("truncated E2 82", bytes(0xE2, 0x82));
    assertRejected("lone lead C3", bytes(0xC3));
    assertRejected("lone continuation 80", bytes(0x80));
    assertRejected("0xFF", bytes(0xFF));
    assertRejected("valid text then a lone lead", bytes('o', 'k', 0xC3));
  }

  @Test
  void aValidFourByteCharacterABomAndEmptyInputDecode() {
    byte[] smiley = "😀".getBytes(StandardCharsets.UTF_8);
    assertThat(smiley).hasSize(4);
    assertThat(StrictUtf8.decode(smiley)).isEqualTo(new StrictUtf8.Decoded.Text("😀"));
    assertThat(StrictUtf8.decode(bytes(0xEF, 0xBB, 0xBF, 'a'))).as("a leading byte order mark stays in the text").isEqualTo(new StrictUtf8.Decoded.Text("﻿a"));
    assertThat(StrictUtf8.decode(new byte[0])).isEqualTo(new StrictUtf8.Decoded.Text(""));
  }

  @Test
  void aLiteralReplacementCharacterInTheInputIsKeptNotMistakenForAnError() {
    assertThat(StrictUtf8.decode(bytes(0xEF, 0xBF, 0xBD))).isEqualTo(new StrictUtf8.Decoded.Text("�"));
  }

  @Test
  void aNulByteDecodesBecauseTheNulDecisionBelongsToTheApplication() {
    assertThat(StrictUtf8.decode(bytes('a', 0, 'b'))).isEqualTo(new StrictUtf8.Decoded.Text("a\u0000b"));
  }

  @Test
  void anAccentedAndAMultiByteTextRoundTrips() {
    String text = "café € 😀 end";
    assertThat(StrictUtf8.decode(text.getBytes(StandardCharsets.UTF_8))).isEqualTo(new StrictUtf8.Decoded.Text(text));
  }
}
