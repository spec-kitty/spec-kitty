package org.speckitty.missionstatus.domain.readmodel.overview;

import java.time.Instant;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.YearMonth;
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
    Instant canonical = parseCanonical(text);
    if (canonical != null) {
      return canonical;
    }
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

  /**
   * The common form, read by hand: {@code YYYY-MM-DDThh:mm:ss}, an optional fraction of one to nine digits, then {@code Z} or
   * {@code +hh:mm}/{@code -hh:mm}. The formatter machinery costs microseconds a call on a cold JVM, and a Work Package history parses one stamp per
   * row. Anything else, and anything out of range, returns null so that {@link #parse} falls through to the formatters, which stay the authority:
   * the result here is the one they give, on every text this method accepts.
   */
  private static Instant parseCanonical(String text) {
    int length = text.length();
    if (length < 20 || text.charAt(4) != '-' || text.charAt(7) != '-' || text.charAt(10) != 'T' || text.charAt(13) != ':' || text.charAt(16) != ':') {
      return null;
    }
    int year = digits(text, 0, 4);
    int month = digits(text, 5, 2);
    int day = digits(text, 8, 2);
    int hour = digits(text, 11, 2);
    int minute = digits(text, 14, 2);
    int second = digits(text, 17, 2);
    if (year < 0 || month < 1 || month > 12 || day < 1 || hour < 0 || hour > 23 || minute < 0 || minute > 59 || second < 0 || second > 59) {
      return null;
    }
    if (day > YearMonth.of(year, month).lengthOfMonth()) {
      return null;
    }
    int at = 19;
    int nanos = 0;
    if (text.charAt(at) == '.') {
      int start = ++at;
      while (at < length && at - start < 9 && isDigit(text.charAt(at))) {
        nanos = nanos * 10 + (text.charAt(at) - '0');
        at++;
      }
      int fraction = at - start;
      if (fraction == 0) {
        return null;
      }
      for (int pad = fraction; pad < 9; pad++) {
        nanos *= 10;
      }
    }
    int offsetSeconds;
    if (at == length - 1 && text.charAt(at) == 'Z') {
      offsetSeconds = 0;
    } else if (at == length - 6 && (text.charAt(at) == '+' || text.charAt(at) == '-') && text.charAt(at + 3) == ':') {
      int offsetHours = digits(text, at + 1, 2);
      int offsetMinutes = digits(text, at + 4, 2);
      if (offsetHours < 0 || offsetHours > 17 || offsetMinutes < 0 || offsetMinutes > 59) {
        return null;
      }
      offsetSeconds = (offsetHours * 3600 + offsetMinutes * 60) * (text.charAt(at) == '-' ? -1 : 1);
    } else {
      return null;
    }
    long epochSecond = LocalDate.of(year, month, day).toEpochDay() * 86_400L + hour * 3600L + minute * 60L + second - offsetSeconds;
    return Instant.ofEpochSecond(epochSecond, nanos);
  }

  private static boolean isDigit(char c) {
    return c >= '0' && c <= '9';
  }

  /** The {@code count} ASCII digits at {@code from} as a number, or -1 when any of them is not an ASCII digit. */
  private static int digits(String text, int from, int count) {
    int value = 0;
    for (int i = from; i < from + count; i++) {
      char c = text.charAt(i);
      if (!isDigit(c)) {
        return -1;
      }
      value = value * 10 + (c - '0');
    }
    return value;
  }

  /**
   * Whether the text is an instant with an explicit offset: the form the contract's {@code format: date-time} (RFC 3339) requires of a
   * served value. {@link #parse} stays lenient (comparison only); a field that is served must pass this.
   */
  public static boolean hasOffset(String text) {
    try {
      OffsetDateTime.parse(text);
      return true;
    } catch (DateTimeParseException withoutOffset) {
      return false;
    }
  }
}
