package org.speckitty.missionstatus.domain.redaction;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * The compiled leak patterns of {@code contracts/tools/leak_patterns.py}, handed in by the caller (the domain reads no file). Patterns
 * are compiled with {@link #compile(String)}, which rewrites {@code \w \W \s \S \d \D} to the classes Python's {@code re} uses on a
 * {@code str}. {@link Pattern#UNICODE_CHARACTER_CLASS} is not that: Java's {@code \w} then also matches combining marks, connector
 * punctuation and join controls (Python's does not), and its {@code \s} omits U+001C to U+001F (Python's has them), which makes a
 * lookbehind such as {@code (?<![\w.~-])} read a character differently and leaves a host path or an address unredacted.
 *
 * @param strictHostPaths host-path patterns of the strict field class
 * @param humanHostPaths host-path patterns of the human field class
 * @param email the detection pattern of an e-mail address (use it to ask whether one is present)
 * @param emailAnchored the same grammar without the leading lookbehind, applied only at the position where the previous match ended
 * @param secrets the secret and token patterns, which apply to every string field
 */
public record LeakClasses(List<Pattern> strictHostPaths, List<Pattern> humanHostPaths, Pattern email, Pattern emailAnchored, List<Pattern> secrets) {

  /** A text with a number of spans replaced. */
  public record Replaced(String text, int count) {}

  public LeakClasses {
    strictHostPaths = List.copyOf(Objects.requireNonNull(strictHostPaths, "strictHostPaths"));
    humanHostPaths = List.copyOf(Objects.requireNonNull(humanHostPaths, "humanHostPaths"));
    Objects.requireNonNull(email, "email");
    Objects.requireNonNull(emailAnchored, "emailAnchored");
    secrets = List.copyOf(Objects.requireNonNull(secrets, "secrets"));
  }

  /** Python's {@code \w} on a {@code str}: {@code str.isalnum()} or an underscore, which is the letters, the numbers and the underscore. */
  private static final String WORD = "\\p{L}\\p{N}_";

  /** Python's {@code \s} on a {@code str}: {@code str.isspace()}, which is tab to carriage return, U+001C to U+001F, U+0085 and the Z categories. */
  private static final String SPACE = "\\x{9}-\\x{d}\\x{1c}-\\x{1f}\\x{85}\\p{Z}";

  private static final String GUARD_START = "(?:";

  private static final String GUARD_END = ")|(?!)\uD800\uDC00";

  /** What {@code \W} stands for as a member of a class: neither a letter, nor a number, nor an underscore. */
  private static final String NOT_WORD = "[\\P{L}&&\\P{N}&&[^_]]";

  /** What {@code \S} stands for as a member of a class: not a space in Python's sense. */
  private static final String NOT_SPACE = "[\\P{Z}&&[^\\x{9}-\\x{d}\\x{1c}-\\x{1f}\\x{85}]]";

  /**
   * Compiles a pattern source the way Python reads a {@code str} pattern: {@code \w \W \s \S \d \D} are rewritten to Python's Unicode
   * classes (also inside a character class), a bracket or an ampersand pair inside a class is made literal, as in Python, and a word
   * boundary, which Python defines through its {@code \w}, is refused rather than read the Java way.
   */
  public static Pattern compile(String source) {
    return Pattern.compile(guarded(translate(source)));
  }

  /**
   * {@code java.util.regex} looks one UTF-16 unit back in a lookbehind unless the pattern text holds a supplementary character after
   * the lookbehind starts; a supplementary letter, digit or mark before the match then goes unseen, where Python sees it as one
   * character. A lookbehind pattern is therefore wrapped with an alternative that can never match and holds one (U+10000).
   */
  private static String guarded(String translated) {
    return translated.contains("(?<") ? GUARD_START + translated + GUARD_END : translated;
  }

  /** The translated source of a guarded pattern, without the guard. */
  private static String unguarded(String translated) {
    return translated.startsWith(GUARD_START) && translated.endsWith(GUARD_END)
        ? translated.substring(GUARD_START.length(), translated.length() - GUARD_END.length())
        : translated;
  }

  /** The source with Python's shorthand classes spelled out; the one place that knows the difference. */
  private static String translate(String source) {
    StringBuilder out = new StringBuilder(source.length() + 16);
    boolean inClass = false;
    int i = 0;
    while (i < source.length()) {
      char c = source.charAt(i);
      if (c == '\\' && i + 1 < source.length()) {
        char next = source.charAt(i + 1);
        String shorthand = shorthand(next, inClass);
        if (shorthand != null) {
          out.append(shorthand);
        } else if (next == 'b' || next == 'B') {
          throw new IllegalArgumentException("a word boundary has no Python-faithful translation: " + source);
        } else {
          out.append(c).append(next);
        }
        i += 2;
      } else if (!inClass && c == '[') {
        inClass = true;
        out.append(c);
        i++;
        if (i < source.length() && source.charAt(i) == '^') {
          out.append('^');
          i++;
        }
        if (i < source.length() && source.charAt(i) == ']') {
          out.append("\\]");
          i++;
        }
      } else if (inClass && c == ']') {
        inClass = false;
        out.append(c);
        i++;
      } else if (inClass && (c == '[' || c == '&')) {
        out.append('\\').append(c);
        i++;
      } else {
        out.append(c);
        i++;
      }
    }
    return out.toString();
  }

  /** The replacement for {@code \<letter>} when it is one of Python's shorthand classes, else null. */
  private static String shorthand(char letter, boolean inClass) {
    return switch (letter) {
      case 'w' -> inClass ? WORD : "[" + WORD + "]";
      case 'W' -> NOT_WORD;
      case 's' -> inClass ? SPACE : "[" + SPACE + "]";
      case 'S' -> NOT_SPACE;
      case 'd' -> "\\p{Nd}";
      case 'D' -> "\\P{Nd}";
      default -> null;
    };
  }

  /** True when the text is shaped like a host path of the strict class; this is the predicate the project header takes. */
  public boolean strictHostPath(String text) {
    return anyFound(strictHostPaths, text);
  }

  /** True when the text holds a strict host path, an address or a secret. */
  public boolean strictLeak(String text) {
    return anyFound(strictHostPaths, text) || email.matcher(text).find() || anyFound(secrets, text);
  }

  /** True when the text holds a human host path, an address or a secret. */
  public boolean humanLeak(String text) {
    return anyFound(humanHostPaths, text) || email.matcher(text).find() || anyFound(secrets, text);
  }

  /**
   * Every human host path replaced by the token, each one together with the rest of its token (a run of non-space characters).
   * Python widens each pattern with {@code \S*} and substitutes the patterns one after the other.
   */
  public Replaced redactHumanHostPaths(String text, String token) {
    String current = text;
    int total = 0;
    for (Pattern pattern : humanHostPaths) {
      Pattern widened = Pattern.compile(guarded(unguarded(pattern.pattern()) + translate("\\S*")), pattern.flags());
      Replaced replaced = replaceAll(widened, current, token);
      current = replaced.text();
      total += replaced.count();
    }
    return new Replaced(current, total);
  }

  /**
   * Every address replaced by the token. The detection pattern starts only at the start of a token; the anchored form is tried at
   * the position where the previous match ended, which finds an address glued onto the end of one (Python's {@code email_matches}).
   */
  public Replaced redactEmails(String text, String token) {
    StringBuilder out = new StringBuilder();
    int last = 0;
    int count = 0;
    int position = 0;
    while (position <= text.length()) {
      Matcher found = position == 0 ? null : anchoredAt(text, position);
      if (found == null) {
        Matcher search = email.matcher(text);
        found = search.find(position) ? search : null;
      }
      if (found == null) {
        break;
      }
      out.append(text, last, found.start()).append(token);
      last = found.end();
      count++;
      position = found.end();
    }
    out.append(text, last, text.length());
    return new Replaced(out.toString(), count);
  }

  private Matcher anchoredAt(String text, int position) {
    Matcher matcher = emailAnchored.matcher(text);
    matcher.region(position, text.length());
    matcher.useTransparentBounds(true);
    matcher.useAnchoringBounds(false);
    return matcher.lookingAt() ? matcher : null;
  }

  private static boolean anyFound(List<Pattern> patterns, String text) {
    for (Pattern pattern : patterns) {
      if (pattern.matcher(text).find()) {
        return true;
      }
    }
    return false;
  }

  private static Replaced replaceAll(Pattern pattern, String text, String token) {
    Matcher matcher = pattern.matcher(text);
    List<int[]> spans = new ArrayList<>();
    while (matcher.find()) {
      spans.add(new int[] {matcher.start(), matcher.end()});
    }
    StringBuilder out = new StringBuilder();
    int last = 0;
    for (int[] span : spans) {
      out.append(text, last, span[0]).append(token);
      last = span[1];
    }
    out.append(text, last, text.length());
    return new Replaced(out.toString(), spans.size());
  }
}
