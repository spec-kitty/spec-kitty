package org.speckitty.missionstatus.domain.redaction;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Objects;
import java.util.regex.Pattern;

/**
 * AC-9g redaction: the port of the oracle's {@code Projector.strict} and {@code Projector.human}. A strict field (identifiers, handles,
 * path-like values) is served clean, nulled when it may be null and is not clean, and refused when it may not be null and is not
 * representable. A human field (free text) has each host path replaced by {@code [path]} and each address by {@code [email]}; a leak
 * that is left after that is refused. A refusal carries the field name and a fixed reason, never the value.
 *
 * <p>Which contract field is strict and which is human is the oracle's choice (recorded in the conformance manifest): {@code missionId},
 * {@code slug}, {@code missionType} and {@code targetBranch} are strict, {@code friendlyName} and {@code nextAction} are human.
 *
 * <p>One instance records the redactions of one projection run and is not thread-safe.
 */
public final class Projector {

  private static final String PATH_TOKEN = "[path]";
  private static final String EMAIL_TOKEN = "[email]";

  /** What a redaction did to a field. */
  public enum Kind {
    NULLED,
    PATH,
    EMAIL
  }

  /** One redaction: the field and what was done to it. */
  public record Redaction(String field, Kind kind) {}

  private final LeakClasses leaks;
  private final List<Redaction> redactions = new ArrayList<>();

  public Projector(LeakClasses leaks) {
    this.leaks = Objects.requireNonNull(leaks, "leaks");
  }

  /** A strict field without a shape pattern. */
  public String strict(String value, String fieldName, boolean nullable) {
    return strict(value, fieldName, nullable, null);
  }

  /**
   * A strict field: a clean string (non-empty, no leak, and matching the pattern from its start when one is given), else null when
   * nullable, else a {@link ProjectionError}.
   */
  public String strict(String value, String fieldName, boolean nullable, Pattern pattern) {
    if (value == null) {
      if (nullable) {
        return null;
      }
      throw new ProjectionError(fieldName, ProjectionError.Reason.MISSING);
    }
    boolean clean = !value.isEmpty() && !leaks.strictLeak(value) && (pattern == null || pattern.matcher(value).lookingAt());
    if (clean) {
      return value;
    }
    if (nullable) {
      redactions.add(new Redaction(fieldName, Kind.NULLED));
      return null;
    }
    throw new ProjectionError(fieldName, ProjectionError.Reason.NOT_REPRESENTABLE);
  }

  /** A human text field: clean text passes through; only the matching substrings are replaced, and a leak left over is refused. */
  public String human(String value, String fieldName) {
    if (value == null) {
      return null;
    }
    LeakClasses.Replaced paths = leaks.redactHumanHostPaths(value, PATH_TOKEN);
    if (paths.count() > 0) {
      redactions.add(new Redaction(fieldName, Kind.PATH));
    }
    LeakClasses.Replaced emails = leaks.redactEmails(paths.text(), EMAIL_TOKEN);
    if (emails.count() > 0) {
      redactions.add(new Redaction(fieldName, Kind.EMAIL));
    }
    if (leaks.humanLeak(emails.text())) {
      throw new ProjectionError(fieldName, ProjectionError.Reason.LEAK_REMAINS);
    }
    return emails.text();
  }

  /** A read-only snapshot of the redactions recorded so far. */
  public List<Redaction> redactions() {
    return Collections.unmodifiableList(new ArrayList<>(redactions));
  }
}
