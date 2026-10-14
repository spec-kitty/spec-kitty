package org.speckitty.missionstatus.domain.model;

import java.util.Objects;
import java.util.Optional;
import java.util.regex.Pattern;

/** The canonical Mission identity: a 26-character ULID. */
public record MissionId(String value) {

  private static final Pattern ULID = Pattern.compile("^[0-9A-HJKMNP-TV-Z]{26}$");

  public MissionId {
    Objects.requireNonNull(value, "value");
    if (!ULID.matcher(value).matches()) {
      throw new IllegalArgumentException("not a ULID");
    }
  }

  /**
   * The lenient factory the adapters call (E-5, D-150): empty for null, an empty string, lowercase, a wrong length, a Crockford-excluded
   * letter or any other ill-formed text, and it never throws. An empty result becomes {@code not_found}, so no adapter chooses between a 400
   * and a 404. A {@code mid8}, a slug and a number are not ULIDs.
   */
  public static Optional<MissionId> parse(String raw) {
    return raw != null && ULID.matcher(raw).matches() ? Optional.of(new MissionId(raw)) : Optional.empty();
  }

  /** The first eight characters, used to disambiguate branch and worktree names. */
  public String mid8() {
    return value.substring(0, 8);
  }
}
