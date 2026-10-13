package org.speckitty.missionstatus.config;

import org.springframework.core.convert.converter.Converter;

/**
 * Reads the {@code pageSize} query parameter (the only integer the routes bind) the way the operator ruled (analyze.ruling.md,
 * 2026-10-12): text that is not an integer is treated as absent (null, so the default applies), and an integer beyond 32 bits saturates
 * (the application then clamps it to 1..200). An integer is an optional {@code +} or {@code -} followed by ASCII digits and nothing
 * else: no spaces, fraction, exponent, hex or digit separators; a blank value is absent.
 */
final class LenientIntegerConverter implements Converter<String, Integer> {

  @Override
  public Integer convert(String source) {
    int length = source.length();
    int start = length > 0 && (source.charAt(0) == '+' || source.charAt(0) == '-') ? 1 : 0;
    if (length == start) {
      return null;
    }
    for (int i = start; i < length; i++) {
      char c = source.charAt(i);
      if (c < '0' || c > '9') {
        return null;
      }
    }
    boolean negative = source.charAt(0) == '-';
    long value = 0;
    for (int i = start; i < length; i++) {
      value = value * 10 + (source.charAt(i) - '0');
      if (value > Integer.MAX_VALUE) {
        return negative ? Integer.MIN_VALUE : Integer.MAX_VALUE;
      }
    }
    return (int) (negative ? -value : value);
  }
}
