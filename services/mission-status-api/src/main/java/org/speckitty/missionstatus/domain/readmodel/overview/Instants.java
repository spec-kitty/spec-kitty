package org.speckitty.missionstatus.domain.readmodel.overview;

import java.time.Instant;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeParseException;

/** Parsing of the timestamps that are compared as instants (the text-ordered {@code at} of the reducer is a separate rule). */
public final class Instants {

  private Instants() {}

  /** An offset-less timestamp is read as UTC; Python would read it in the local zone, which no deterministic service can. */
  public static Instant parse(String text) {
    try {
      return OffsetDateTime.parse(text).toInstant();
    } catch (DateTimeParseException withoutOffset) {
      try {
        return LocalDateTime.parse(text).toInstant(ZoneOffset.UTC);
      } catch (DateTimeParseException invalid) {
        throw new InvalidInstantException();
      }
    }
  }
}
