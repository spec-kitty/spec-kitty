package org.speckitty.missionstatus.adapter.out.filesystem;

import java.util.Locale;

/**
 * The host probe for file-name decoding (D-31, FRESH3-004). On a non-Windows host the JDK decodes directory entries with
 * {@code sun.jnu.encoding}, which follows the process locale; when that is not UTF-8 a name that is not pure ASCII cannot be told from a
 * mangled one. Windows decodes names itself, so it is trustworthy. Injectable, so the stub legs of AC-4.8 and AC-6.6 run under any locale.
 *
 * @param windows whether the host is Windows
 * @param jnuEncoding the value of {@code sun.jnu.encoding}, or null
 */
public record NameEncoding(boolean windows, String jnuEncoding) {

  /** The answer for the running host. */
  public static NameEncoding host() {
    return new NameEncoding(System.getProperty("os.name", "").toLowerCase(Locale.ROOT).startsWith("windows"), System.getProperty("sun.jnu.encoding"));
  }

  /** A stub with a fixed answer, for tests that must run under any locale. */
  public static NameEncoding fixed(boolean trustworthy) {
    return new NameEncoding(false, trustworthy ? "UTF-8" : "ANSI_X3.4-1968");
  }

  /** Whether the names this host decodes can be believed. */
  public boolean trustworthy() {
    return windows || (jnuEncoding != null && jnuEncoding.replace("-", "").equalsIgnoreCase("UTF8"));
  }
}
