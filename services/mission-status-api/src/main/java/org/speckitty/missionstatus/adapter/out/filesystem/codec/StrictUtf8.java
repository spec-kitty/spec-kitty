package org.speckitty.missionstatus.adapter.out.filesystem.codec;

import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CharsetDecoder;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;

/**
 * The one strict UTF-8 decode of every text read this service adds (D-70). A malformed, overlong, surrogate or truncated sequence, or a
 * code point above U+10FFFF, is reported and never replaced and never repaired; a leading byte order mark stays in the text. It is a
 * JDK {@link CharsetDecoder} with {@link CodingErrorAction#REPORT} for malformed input and for unmappable characters. It sits here
 * because the architecture rules allow {@code ByteBuffer} in this package and nowhere in {@code domain} or {@code application}.
 *
 * <p>The decision about a NUL byte is not made here; it stays with the application over the decoded text.
 */
public final class StrictUtf8 {

  /** What decoding gave. */
  public sealed interface Decoded {

    /** The bytes were valid UTF-8; this is their text. */
    record Text(String text) implements Decoded {}

    /** The bytes were not strict UTF-8. */
    record Rejected() implements Decoded {}
  }

  private StrictUtf8() {}

  /** Decodes {@code bytes} as strict UTF-8. */
  public static Decoded decode(byte[] bytes) {
    CharsetDecoder decoder =
        StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT).onUnmappableCharacter(CodingErrorAction.REPORT);
    try {
      return new Decoded.Text(decoder.decode(ByteBuffer.wrap(bytes)).toString());
    } catch (CharacterCodingException malformed) {
      return new Decoded.Rejected();
    }
  }
}
