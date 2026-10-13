package org.speckitty.missionstatus.domain.model;

/** The schema versions this build supports: {@code MIN_SUPPORTED_SCHEMA} and {@code MAX_SUPPORTED_SCHEMA} of schema_version.py. */
public final class SupportedSchemaRange {

  public static final int MIN = 3;
  public static final int MAX = 3;

  private SupportedSchemaRange() {}

  public static boolean contains(int version) {
    return version >= MIN && version <= MAX;
  }
}
