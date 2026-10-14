package org.speckitty.missionstatus.domain.readmodel.overview;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeParseException;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Random;
import org.junit.jupiter.api.Test;

class InstantsTest {

  @Test
  void parsesOffsetsAndFractionsToTheSameInstantScale() {
    assertThat(Instants.parse("2026-09-01T09:00:00Z")).isEqualTo(Instant.parse("2026-09-01T09:00:00Z"));
    assertThat(Instants.parse("2026-09-01T11:00:00+02:00")).isEqualTo(Instant.parse("2026-09-01T09:00:00Z"));
    assertThat(Instants.parse("2026-09-01T09:00:00+00:00")).isEqualTo(Instant.parse("2026-09-01T09:00:00Z"));
    assertThat(Instants.parse("2026-09-01T11:00:00.123456Z")).isEqualTo(Instant.parse("2026-09-01T11:00:00.123456Z"));
  }

  @Test
  void anOffsetlessTimestampIsReadAsUtc() {
    assertThat(Instants.parse("2026-09-01T09:00:00")).isEqualTo(Instant.parse("2026-09-01T09:00:00Z"));
  }

  @Test
  void anInvalidInstantIsATypedErrorNotAGuess() {
    assertThatThrownBy(() -> Instants.parse("yesterday")).isInstanceOf(InvalidInstantException.class);
    assertThatThrownBy(() -> Instants.parse("")).isInstanceOf(InvalidInstantException.class);
  }

  /** The hand-read common form must give exactly what the formatters give, and refuse exactly what they refuse. */
  @Test
  void theCanonicalFastPathAgreesWithTheFormattersOnEveryShape() {
    List<String> texts = new ArrayList<>(
        List.of(
            "2026-09-01T09:00:00Z", "2026-09-01T09:00:00z", "2026-09-01t09:00:00Z", "2026-09-01T09:00:00-00:00", "2026-09-01T09:00:00+18:00",
            "2026-09-01T09:00:00-18:00", "2026-09-01T09:00:00+17:59", "2026-09-01T09:00:00+19:00", "2026-09-01T09:00:00+02:60", "2026-09-01T09:00:00+0200",
            "2026-09-01T09:00:00+02", "2026-09-01T09:00:00+02:00:30", "2026-09-01T09:00:00.Z", "2026-09-01T09:00:00.1234567890Z",
            "2026-09-01T09:00:00.123456789Z", "2026-09-01T09:00:00.1", "2026-09-01T09:00:00.", "2026-02-29T09:00:00Z", "2024-02-29T09:00:00Z",
            "2026-02-30T09:00:00Z", "2026-13-01T09:00:00Z", "2026-00-01T09:00:00Z", "2026-09-00T09:00:00Z", "2026-09-01T24:00:00Z",
            "2026-09-01T23:59:60Z", "2026-09-01T09:60:00Z", "0000-01-01T00:00:00Z", "9999-12-31T23:59:59Z", "-0001-01-01T00:00:00Z",
            "+12026-01-01T00:00:00Z", "2026-09-01T09:00:00Zjunk", "2026-09-01T09:00:00 Z", "2026-09-01 09:00:00Z", "2026-09-01T09:00Z",
            "2026-09-01T09:00:00", "2026-09-01T09:00:00.5", "2026-9-1T09:00:00Z", "2026-09-01T09:00:00[UTC]", "\u0662026-09-01T09:00:00Z",
            "2026-09-01T09:00:0\u0660Z", "", "None", "yesterday", "2026-09-01T09:00:00+02:00+02:00", "2026-09-01T09:00:00Z\n"));
    Random random = new Random(7);
    for (int i = 0; i < 4000; i++) {
      texts.add(
          String.format(
              Locale.ROOT,
              "%04d-%02d-%02dT%02d:%02d:%02d%s%s",
              random.nextInt(10_000),
              random.nextInt(14),
              random.nextInt(33),
              random.nextInt(26),
              random.nextInt(62),
              random.nextInt(62),
              random.nextBoolean() ? "." + "123456789".substring(0, random.nextInt(11) % 10) : "",
              switch (random.nextInt(4)) {
                case 0 -> "Z";
                case 1 -> String.format(Locale.ROOT, "%+03d:%02d", random.nextInt(41) - 20, random.nextInt(62));
                case 2 -> "";
                default -> "z";
              }));
    }
    int accepted = 0;
    for (String text : texts) {
      Instant expected = reference(text);
      if (expected == null) {
        assertThatThrownBy(() -> Instants.parse(text)).as(text).isInstanceOf(InvalidInstantException.class);
      } else {
        assertThat(Instants.parse(text)).as(text).isEqualTo(expected);
        accepted++;
      }
    }
    assertThat(accepted).as("the corpus holds accepted texts as well as refused ones").isBetween(500, texts.size() - 500);
  }

  /** The formatters alone: the behaviour before the fast path. */
  private static Instant reference(String text) {
    try {
      return OffsetDateTime.parse(text).toInstant();
    } catch (DateTimeParseException withoutOffset) {
      try {
        return LocalDateTime.parse(text).toInstant(ZoneOffset.UTC);
      } catch (DateTimeParseException invalid) {
        return null;
      }
    }
  }
}
