package org.speckitty.missionstatus.domain.model;

import java.util.Objects;
import java.util.Optional;
import java.util.regex.Pattern;

/**
 * The identifier of a Work Package inside one Mission: the letters {@code WP} and at least two ASCII digits, at most 64 characters (contract
 * {@code WpId}). The constructor is strict. {@link #parse} is the lenient factory the adapters call: it returns an empty result for anything
 * that is no identifier and never throws (E-5, D-150), so an adapter turns "empty" into {@code not_found} and no adapter chooses between a
 * 400 and a 404.
 */
public record WpId(String value) {

  private static final int MAX_LENGTH = 64;
  private static final Pattern SHAPE = Pattern.compile("WP[0-9]{2,}");

  public WpId {
    Objects.requireNonNull(value, "value");
    if (!isWellFormed(value)) {
      throw new IllegalArgumentException("not a Work Package id");
    }
  }

  /** The id, or empty for null, an empty string, a wrong case, a short digit run, a non-ASCII digit, a line ending or a value over 64 characters. */
  public static Optional<WpId> parse(String raw) {
    return raw != null && isWellFormed(raw) ? Optional.of(new WpId(raw)) : Optional.empty();
  }

  private static boolean isWellFormed(String value) {
    return value.length() <= MAX_LENGTH && SHAPE.matcher(value).matches();
  }
}
