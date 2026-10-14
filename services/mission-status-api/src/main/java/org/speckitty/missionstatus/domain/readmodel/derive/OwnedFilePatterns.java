package org.speckitty.missionstatus.domain.readmodel.derive;

/** The owned-file helpers of the Work Package detail: the oracle's {@code is_glob_pattern} of {@code src/specify_cli/ownership/validation.py}. */
public final class OwnedFilePatterns {

  private OwnedFilePatterns() {}

  /** True when the pattern holds a glob metacharacter: {@code *}, {@code ?}, {@code [} or {@code {}. */
  public static boolean isGlob(String pattern) {
    return pattern.indexOf('*') >= 0 || pattern.indexOf('?') >= 0 || pattern.indexOf('[') >= 0 || pattern.indexOf('{') >= 0;
  }
}
