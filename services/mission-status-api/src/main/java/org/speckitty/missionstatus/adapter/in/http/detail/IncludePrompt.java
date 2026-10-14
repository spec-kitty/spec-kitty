package org.speckitty.missionstatus.adapter.in.http.detail;

import java.util.List;
import java.util.Optional;

/**
 * The {@code includePrompt} parameter of the Work Package route. Absent is {@code false}; exactly one value, {@code true} or {@code false}
 * in lower case, is that boolean; anything else (a number, another case, an empty value, a repeated parameter) is refused. A refusal is an
 * empty result: the controller answers it with the {@code invalid_parameter} Problem before any file is read.
 */
public final class IncludePrompt {

  private IncludePrompt() {}

  /** The flag, or empty when the raw values are refused. */
  public static Optional<Boolean> parse(List<String> rawValues) {
    if (rawValues.isEmpty()) {
      return Optional.of(Boolean.FALSE);
    }
    if (rawValues.size() > 1) {
      return Optional.empty();
    }
    return switch (rawValues.get(0)) {
      case "true" -> Optional.of(Boolean.TRUE);
      case "false" -> Optional.of(Boolean.FALSE);
      default -> Optional.empty();
    };
  }
}
