package org.speckitty.missionstatus.domain.readmodel.artifact;

import java.nio.charset.StandardCharsets;
import java.util.Objects;
import java.util.regex.Pattern;
import org.speckitty.missionstatus.domain.redaction.LeakClasses;

/**
 * The decision over the bytes of an artifact ({@code _decide_bytes} of the reference reader): more than the cap is 413, a NUL byte
 * or text that is not strict UTF-8 is 415, a credential is 422, and anything else is the text with every human host path replaced by
 * {@value #PATH_TOKEN} and every e-mail address by {@value #EMAIL_TOKEN}. Strict UTF-8 refuses what Python's {@code utf-8} codec
 * refuses (overlong forms, encoded surrogates, code points above U+10FFFF) and keeps a leading byte order mark. A scan that cannot
 * finish (the regex engine runs out of stack on a pathological input) is {@code artifact_unreadable}, never served unchecked.
 */
public final class ArtifactText {

  /** The largest artifact whose content is served, in bytes. */
  public static final int MAX_CONTENT_BYTES = 262_144;

  public static final String PATH_TOKEN = "[path]";
  public static final String EMAIL_TOKEN = "[email]";

  /** The outcome of the decision: a refusal code, or the redacted text and whether redaction changed it. */
  public record Decision(ArtifactRefusalCode refusal, String content, boolean redacted) {

    static Decision refused(ArtifactRefusalCode code) {
      return new Decision(code, null, false);
    }

    public boolean served() {
      return refusal == null;
    }
  }

  private final LeakClasses leaks;

  public ArtifactText(LeakClasses leaks) {
    this.leaks = Objects.requireNonNull(leaks, "leaks");
  }

  /** The decision over {@code data}, which holds at most {@link #MAX_CONTENT_BYTES} + 1 bytes of the file. */
  public Decision decide(byte[] data) {
    if (data.length > MAX_CONTENT_BYTES) {
      return Decision.refused(ArtifactRefusalCode.ARTIFACT_TOO_LARGE);
    }
    for (byte b : data) {
      if (b == 0) {
        return Decision.refused(ArtifactRefusalCode.ARTIFACT_NOT_TEXT);
      }
    }
    if (!isWellFormedUtf8(data)) {
      return Decision.refused(ArtifactRefusalCode.ARTIFACT_NOT_TEXT);
    }
    String text = new String(data, StandardCharsets.UTF_8);
    try {
      if (holdsCredential(text)) {
        return Decision.refused(ArtifactRefusalCode.ARTIFACT_SECRET);
      }
      String redacted = leaks.redactEmails(leaks.redactHumanHostPaths(text, PATH_TOKEN).text(), EMAIL_TOKEN).text();
      return new Decision(null, redacted, !redacted.equals(text));
    } catch (StackOverflowError scanTooDeep) {
      // java.util.regex recurses once per repetition of a variable-width group (the PEM header and the address patterns), so a few
      // kilobytes of such repetitions overflow the stack where Python's re answers. The scan did not finish, so the text is neither
      // known to be free of a credential nor redacted: fail closed with a contracted refusal (a recorded divergence, see the README).
      return Decision.refused(ArtifactRefusalCode.ARTIFACT_UNREADABLE);
    }
  }

  /**
   * Whether {@code data} is well-formed UTF-8 in the sense of Unicode Table 3-7, the rule Python's strict {@code utf-8} decoder applies:
   * no overlong form, no encoded surrogate (U+D800 to U+DFFF), nothing above U+10FFFF, no truncated or stray continuation byte.
   */
  static boolean isWellFormedUtf8(byte[] data) {
    int i = 0;
    while (i < data.length) {
      int lead = data[i] & 0xff;
      int length;
      int low = 0x80;
      int high = 0xbf;
      if (lead < 0x80) {
        i++;
        continue;
      } else if (lead >= 0xc2 && lead <= 0xdf) {
        length = 2;
      } else if (lead >= 0xe0 && lead <= 0xef) {
        length = 3;
        low = lead == 0xe0 ? 0xa0 : 0x80;
        high = lead == 0xed ? 0x9f : 0xbf;
      } else if (lead >= 0xf0 && lead <= 0xf4) {
        length = 4;
        low = lead == 0xf0 ? 0x90 : 0x80;
        high = lead == 0xf4 ? 0x8f : 0xbf;
      } else {
        return false;
      }
      if (i + length > data.length) {
        return false;
      }
      int second = data[i + 1] & 0xff;
      if (second < low || second > high) {
        return false;
      }
      for (int k = 2; k < length; k++) {
        int next = data[i + k] & 0xff;
        if (next < 0x80 || next > 0xbf) {
          return false;
        }
      }
      i += length;
    }
    return true;
  }

  /** Whether a credential pattern of {@code leak_patterns.SECRET_PATTERNS} matches {@code text}. */
  public boolean holdsCredential(String text) {
    for (Pattern secret : leaks.secrets()) {
      if (secret.matcher(text).find()) {
        return true;
      }
    }
    return false;
  }
}
