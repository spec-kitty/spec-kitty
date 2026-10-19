package org.speckitty.missionstatus.domain.readmodel.artifact;

import java.util.Map;
import java.util.Set;

/**
 * The two root status records of a Mission, {@code status.events.jsonl} and {@code status.json}, which are not artifacts. A path names
 * one when its Python {@code str.casefold()} equals the record's name. Both names are ASCII, so the comparison needs only the ASCII
 * letters and the eleven code points whose case fold is ASCII (computed over every code point with Python's {@code str.casefold});
 * any other code point folds to text that is not ASCII and can never match.
 */
public final class StatusRecordNames {

  private static final Set<String> NAMES = Set.of("status.events.jsonl", "status.json");

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
          Map.entry(0xFB06, "st"));

  private StatusRecordNames() {}

  /** Whether {@code path} (relative to the Mission directory) is one of the two root status records. */
  public static boolean isStatusRecord(String path) {
    StringBuilder folded = new StringBuilder(path.length());
    for (int i = 0; i < path.length(); ) {
      int codePoint = path.codePointAt(i);
      i += Character.charCount(codePoint);
      if (codePoint < 0x80) {
        folded.append(codePoint >= 'A' && codePoint <= 'Z' ? (char) (codePoint + ('a' - 'A')) : (char) codePoint);
      } else {
        String fold = NON_ASCII_FOLDS.get(codePoint);
        if (fold == null) {
          return false;
        }
        folded.append(fold);
      }
    }
    return NAMES.contains(folded.toString());
  }
}
