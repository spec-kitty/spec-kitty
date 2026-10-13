package org.speckitty.missionstatus.domain.model;

import java.util.Objects;
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

  /** The first eight characters, used to disambiguate branch and worktree names. */
  public String mid8() {
    return value.substring(0, 8);
  }
}
