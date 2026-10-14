package org.speckitty.missionstatus.domain.readmodel.overview;

import java.time.Instant;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeParseException;

/** Parsing of the timestamps that are compared as instants (the text-ordered {@code at} of the reducer is a separate rule). */
public final class Instants {

  private Instants() {}

  /**
   * An offset-less timestamp is read as UTC; Python would read it in the local zone, which no deterministic service can.
   *
   * <p>This is narrower than the oracle's {@code datetime.fromisoformat}, which also takes a space separator, a date alone and the
   * basic (unseparated) format: a hand-edited {@code created_at} such as {@code "2026-09-01 10:00:00+00:00"} is refused here (the read
   * fails, {@code meta_unparseable}) where Python serves it, and a date-valued member that fails here is served as null.
   */
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
