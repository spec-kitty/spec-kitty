package org.speckitty.missionstatus.domain.readmodel.artifact;

import java.util.Map;

/**
 * Python's {@code str.casefold()}, exact on its ASCII part. ASCII letters fold to lower case; the eleven code points whose case fold is
 * ASCII fold to it; the seven whose case fold starts with an ASCII letter and goes on with a combining mark fold to that letter and
 * {@link #NOT_ASCII}; every other code point folds to {@link #NOT_ASCII}. (Both tables are computed over every code point with
 * Python's {@code str.casefold}.) So the result equals an ASCII text, or starts with one, exactly when Python's case fold does.
 */
final class AsciiCaseFold {

  /** The stand-in for any case fold that is not ASCII: it equals no ASCII text. */
  static final char NOT_ASCII = '�';

  private static final Map<Integer, String> NON_ASCII_FOLDS =
      Map.ofEntries(
          Map.entry(0x00DF, "ss"),
          Map.entry(0x017F, "s"),
          Map.entry(0x1E9E, "ss"),
          Map.entry(0x212A, "k"),
          Map.entry(0xFB00, "ff"),
          Map.entry(0xFB01, "fi"),
          Map.entry(0xFB02, "fl"),
          Map.entry(0xFB03, "ffi"),
          Map.entry(0xFB04, "ffl"),
          Map.entry(0xFB05, "st"),
          Map.entry(0xFB06, "st"),
          Map.entry(0x0130, "i" + NOT_ASCII),
          Map.entry(0x01F0, "j" + NOT_ASCII),
          Map.entry(0x1E96, "h" + NOT_ASCII),
          Map.entry(0x1E97, "t" + NOT_ASCII),
          Map.entry(0x1E98, "w" + NOT_ASCII),
          Map.entry(0x1E99, "y" + NOT_ASCII),
          Map.entry(0x1E9A, "a" + NOT_ASCII));

  private AsciiCaseFold() {}

  static String fold(String text) {
    StringBuilder folded = new StringBuilder(text.length());
    for (int i = 0; i < text.length(); ) {
      int codePoint = text.codePointAt(i);
      i += Character.charCount(codePoint);
      if (codePoint < 0x80) {
        folded.append(codePoint >= 'A' && codePoint <= 'Z' ? (char) (codePoint + ('a' - 'A')) : (char) codePoint);
      } else {
        folded.append(NON_ASCII_FOLDS.getOrDefault(codePoint, String.valueOf(NOT_ASCII)));
      }
    }
    return folded.toString();
  }
}
