package org.speckitty.missionstatus.adapter.out.filesystem.codec;

import java.math.BigInteger;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import org.speckitty.missionstatus.adapter.out.filesystem.codec.WpFrontmatterCodec.Yaml12;
import org.speckitty.missionstatus.domain.model.ReviewCycleMeta;

/**
 * The pure decoder of a review-cycle file (row M11, D-46): the review time and the reviewer, as the oracle's
 * {@code ReviewCycleArtifact.from_file} reads them. It is deliberately not the Work Package decoder: this reader splits the text at the
 * first {@code \n---} (not at a stripped {@code ---} line), keeps a byte order mark in the text (so a file that starts with one does not
 * parse), and demands a different set of fields. A file that does not parse, in any of the ways the oracle's reader refuses it, gives
 * {@link ReviewCycleMeta#UNPARSED}. Bytes that are not strict UTF-8 are never repaired.
 *
 * <p>The YAML is read by the same YAML 1.2 reader as a Work Package file, so an unquoted timestamp is a timestamp and not a string, as
 * the oracle's reader has it.
 */
public final class ReviewCycleCodec {

  private static final String DELIMITER = "---";
  private static final String CLOSING = "\n---";
  private static final Pattern DATE_TIME =
      Pattern.compile(
          "^(?<y>\\d{4})-(?<mo>\\d{2})-(?<d>\\d{2})[Tt](?<h>\\d{2}):(?<mi>\\d{2}):(?<s>\\d{2})(?:\\.\\d+)?"
              + "(?:[Zz]|[+-](?<oh>\\d{2}):(?<om>\\d{2}))$",
          Pattern.UNICODE_CHARACTER_CLASS | Pattern.UNIX_LINES);

  private ReviewCycleCodec() {}

  /** Decodes the bytes of one review-cycle file. */
  public static ReviewCycleMeta decode(byte[] bytes) {
    if (!(StrictUtf8.decode(bytes) instanceof StrictUtf8.Decoded.Text decoded)) {
      return ReviewCycleMeta.UNPARSED;
    }
    String text = WpFrontmatterCodec.translateNewlines(decoded.text());
    if (!text.startsWith(DELIMITER)) {
      return ReviewCycleMeta.UNPARSED;
    }
    String rest = text.substring(DELIMITER.length());
    if (rest.startsWith("\n")) {
      rest = rest.substring(1);
    }
    int closing = rest.indexOf(CLOSING);
    if (closing < 0) {
      return ReviewCycleMeta.UNPARSED;
    }
    try {
      if (!(Yaml12.parse(rest.substring(0, closing)) instanceof Yaml12.Mapping mapping)) {
        return ReviewCycleMeta.UNPARSED;
      }
      return meta(mapping);
    } catch (Yaml12.Refusal refusal) {
      return ReviewCycleMeta.UNPARSED;
    }
  }

  /** {@code ReviewCycleArtifact.from_dict}: every field the oracle checks, then the two members a response shows. */
  private static ReviewCycleMeta meta(Yaml12.Mapping mapping) {
    Yaml12.Node cycle = field(mapping, "cycle_number");
    String wpId = nonEmptyText(field(mapping, "wp_id"));
    String slug = nonEmptyText(field(mapping, "mission_slug"));
    String reviewer = nonEmptyText(field(mapping, "reviewer_agent"));
    String reviewedAt = nonEmptyText(field(mapping, "reviewed_at"));
    boolean valid =
        positiveInteger(cycle)
            && wpId != null
            && slug != null
            && reviewer != null
            && reviewedAt != null
            && affectedFiles(field(mapping, "affected_files"))
            && optionalText(field(mapping, "reproduction_command"));
    if (!valid) {
      return ReviewCycleMeta.UNPARSED;
    }
    return new ReviewCycleMeta(isRfc3339DateTime(reviewedAt) ? reviewedAt : null, reviewer);
  }

  private static Yaml12.Node field(Yaml12.Mapping mapping, String name) {
    for (Yaml12.Entry entry : mapping.entries()) {
      if (entry.key() instanceof Yaml12.Scalar key && key.type() == Yaml12.Type.STR && key.text().equals(name)) {
        return entry.value();
      }
    }
    return null;
  }

  private static String nonEmptyText(Yaml12.Node node) {
    return node instanceof Yaml12.Scalar scalar && scalar.type() == Yaml12.Type.STR && !scalar.text().isEmpty() ? scalar.text() : null;
  }

  private static boolean optionalText(Yaml12.Node node) {
    return node == null || (node instanceof Yaml12.Scalar scalar && (scalar.type() == Yaml12.Type.STR || scalar.type() == Yaml12.Type.NULL));
  }

  /** {@code int(cycle_number) >= 1}, where a missing or null value and a boolean are refused. */
  private static boolean positiveInteger(Yaml12.Node node) {
    if (!(node instanceof Yaml12.Scalar scalar)) {
      return false;
    }
    BigInteger value =
        switch (scalar.type()) {
          case INT -> (BigInteger) scalar.value();
          case STR -> Yaml12.pyInt(scalar.text());
          case FLOAT -> truncated((Double) scalar.value());
          case BOOL, NULL, TIMESTAMP, UNSUPPORTED -> null;
        };
    return value != null && value.signum() > 0;
  }

  private static BigInteger truncated(double number) {
    return Double.isNaN(number) || Double.isInfinite(number) ? null : new java.math.BigDecimal(number).toBigInteger();
  }

  /** {@code data.get("affected_files", [])}: a list whose entries are mappings with a non-empty {@code path} and a string or null {@code line_range}. */
  private static boolean affectedFiles(Yaml12.Node node) {
    if (node == null) {
      return true;
    }
    if (!(node instanceof Yaml12.Sequence sequence)) {
      return false;
    }
    for (Yaml12.Node item : sequence.items()) {
      if (!(item instanceof Yaml12.Mapping entry) || nonEmptyText(field(entry, "path")) == null || !optionalText(field(entry, "line_range"))) {
        return false;
      }
    }
    return true;
  }

  /** The contract tools' {@code is_rfc3339_date_time}: RFC 3339 section 5.6 with the calendar and clock ranges of Python's {@code datetime}. */
  static boolean isRfc3339DateTime(String value) {
    Matcher matcher = DATE_TIME.matcher(value);
    if (!matcher.find()) {
      return false;
    }
    int year = number(matcher.group("y"));
    int month = number(matcher.group("mo"));
    int day = number(matcher.group("d"));
    if (year < 1 || month < 1 || month > 12 || day < 1 || day > java.time.YearMonth.of(year, month).lengthOfMonth()) {
      return false;
    }
    boolean hasOffset = matcher.group("oh") != null;
    if (hasOffset && (number(matcher.group("oh")) > 23 || number(matcher.group("om")) > 59)) {
      return false;
    }
    return number(matcher.group("h")) <= 23 && number(matcher.group("mi")) <= 59 && number(matcher.group("s")) <= 60;
  }

  /** The value of a run of Unicode decimal digits, as Python's {@code int()} reads them. */
  private static int number(String digits) {
    int value = 0;
    for (int i = 0; i < digits.length(); i++) {
      value = value * 10 + Character.digit(digits.charAt(i), 10);
    }
    return value;
  }
}
