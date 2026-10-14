package org.speckitty.missionstatus.domain.readmodel.derive;

import java.util.OptionalInt;
import java.util.regex.Pattern;

/**
 * The file names and pointers of review cycles: the oracle's {@code _CYCLE_NAME} ({@code ^review-cycle-([1-9][0-9]*)\.md$}) and its
 * {@code cycle_pointer} ({@code build_review_cycle_pointer} and {@code validate_review_cycle_pointer} of the product, held to the contract's own
 * pattern). Pure functions over text.
 */
public final class CycleNames {

  private static final String PREFIX = "review-cycle-";
  private static final String SUFFIX = ".md";
  /** More digits than this never fit an {@code int} ({@code Integer.MAX_VALUE} has ten). */
  private static final int MAX_INT_DIGITS = 10;
  private static final String SCHEME = "review-cycle://";
  /** The product's safe path segment: ASCII, starts with a letter or a digit, no {@code ..} anywhere. */
  private static final Pattern SEGMENT = Pattern.compile("[A-Za-z0-9][A-Za-z0-9._-]*");

  private CycleNames() {}

  /**
   * The cycle number of a file name, or empty when the name is no review-cycle file or its number does not fit the served {@code int}
   * (see {@link #isCycleName}: the oracle's pattern is unbounded, so such a name is a cycle the contract cannot show).
   */
  public static OptionalInt cycleNumber(String name) {
    if (!isCycleName(name)) {
      return OptionalInt.empty();
    }
    String digits = name.substring(PREFIX.length(), name.length() - SUFFIX.length());
    if (digits.length() > MAX_INT_DIGITS) {
      return OptionalInt.empty();
    }
    long value = Long.parseLong(digits);
    return value > Integer.MAX_VALUE ? OptionalInt.empty() : OptionalInt.of((int) value);
  }

  /** Whether the name matches the oracle's {@code _CYCLE_NAME}: ASCII digits, the first not zero, whatever the size of the number. */
  public static boolean isCycleName(String name) {
    if (!name.startsWith(PREFIX) || !name.endsWith(SUFFIX) || name.length() <= PREFIX.length() + SUFFIX.length()) {
      return false;
    }
    String digits = name.substring(PREFIX.length(), name.length() - SUFFIX.length());
    if (digits.charAt(0) == '0') {
      return false;
    }
    for (int i = 0; i < digits.length(); i++) {
      if (digits.charAt(i) < '0' || digits.charAt(i) > '9') {
        return false;
      }
    }
    return true;
  }

  /**
   * The canonical pointer {@code review-cycle://<mission directory>/<work package directory>/<file>}, or null when the product's builder or
   * validator refuses a segment (not a safe single ASCII segment, or {@code ..} inside it) or the file is no review-cycle file.
   */
  public static String pointer(String missionDirectory, String workPackageSlug, String fileName) {
    if (!safe(missionDirectory) || !safe(workPackageSlug) || !safe(fileName) || !isCycleName(fileName)) {
      return null;
    }
    return SCHEME + missionDirectory + "/" + workPackageSlug + "/" + fileName;
  }

  private static boolean safe(String segment) {
    return SEGMENT.matcher(segment).matches() && !segment.contains("..");
  }
}
