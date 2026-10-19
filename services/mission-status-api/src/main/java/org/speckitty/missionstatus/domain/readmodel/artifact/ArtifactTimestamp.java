package org.speckitty.missionstatus.domain.readmodel.artifact;

import java.time.Instant;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;

/** The {@code modifiedAt} of a listing entry: the modification time floored to whole seconds, in UTC with the suffix {@code Z}. */
public final class ArtifactTimestamp {

  private static final DateTimeFormatter FORMAT = DateTimeFormatter.ofPattern("uuuu-MM-dd'T'HH:mm:ss'Z'").withZone(ZoneOffset.UTC);

  private ArtifactTimestamp() {}

  /** The text of a modification time given in whole seconds since the epoch (already floored). */
  public static String format(long epochSecond) {
    return FORMAT.format(Instant.ofEpochSecond(epochSecond));
  }
}
