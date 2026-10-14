package org.speckitty.missionstatus.domain.readmodel.derive;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.speckitty.missionstatus.domain.model.PyText;

/**
 * The subtask titles of one Work Package in {@code tasks.md}: a port of the oracle's {@code title_rows} (the two row formats, the section
 * rule and the title cleaning). Pure functions over text; the caller reads the file and decodes it strictly.
 *
 * <p>What Python's {@code str} does, and what a Java port must therefore do by hand: the text is split on {@code \n} only (a {@code \r} stays
 * at the end of a CRLF line and inside a title, and a leading byte order mark stays), every {@code strip} removes Python's whitespace
 * (including U+00A0, U+0085, U+2028), and {@code \d} and {@code \b} are Unicode: an Arabic-Indic digit is a digit, and a letter, a number or
 * an underscore is a word character. The regular expressions of the oracle are therefore spelled out as scans, not compiled.
 *
 * <p>A section opens at the heading whose first {@code WP} token is this Work Package and closes for good at the next heading that names
 * another; a heading that names this Work Package again does not re-open it. A fenced block holds no rows. A checkbox row belongs to its
 * section; a table row belongs to the Work Package its cells after the title name, else to its section. The first row of an id wins.
 */
public final class TitleRows {

  private static final String PARALLEL_TAG = "[P]";
  private static final String BOLD = "**";
  private static final int MIN_TASK_DIGITS = 3;
  private static final int MIN_WP_DIGITS = 2;

  private TitleRows() {}

  /**
   * Subtask id to its cleaned title (null when the cleaned title is empty), in file order, for the rows of {@code wpId}. An id that has a
   * row has a key, whatever its title.
   */
  public static Map<String, String> titles(String text, String wpId) {
    Walk walk = new Walk(wpId);
    Map<String, String> rows = new LinkedHashMap<>();
    for (String line : text.split("\n", -1)) {
      if (!walk.feed(line)) {
        continue;
      }
      String stripped = PyText.strip(line);
      String[] checkbox = checkbox(stripped);
      if (checkbox != null) {
        if (walk.open && !rows.containsKey(checkbox[0])) {
          rows.put(checkbox[0], cleanTitle(checkbox[1]));
        }
        continue;
      }
      List<String> table = tableRow(stripped);
      if (table == null) {
        continue;
      }
      List<String> named = wpTokens(String.join(" ", table.subList(2, table.size())));
      boolean mine = named.isEmpty() ? walk.open : named.contains(wpId);
      if (mine && !rows.containsKey(table.get(0))) {
        rows.put(table.get(0), cleanTitle(table.get(1)));
      }
    }
    return rows;
  }

  /** A leading {@code [P]} tag is dropped, one pair of {@code **} markers is stripped and the result is trimmed; empty is null. */
  static String cleanTitle(String raw) {
    String text = PyText.strip(raw);
    if (text.startsWith(PARALLEL_TAG)) {
      text = PyText.strip(text.substring(PARALLEL_TAG.length()));
    }
    if (text.length() >= 2 * BOLD.length() && text.startsWith(BOLD) && text.endsWith(BOLD)) {
      text = text.substring(BOLD.length(), text.length() - BOLD.length());
    }
    text = PyText.strip(text);
    return text.isEmpty() ? null : text;
  }

  /** The section rule: a heading belongs to the Work Package of its first token. */
  private static final class Walk {
    private final String wpId;
    private boolean open;
    private boolean done;
    private boolean fenced;

    Walk(String wpId) {
      this.wpId = wpId;
    }

    /** Advances over one line; true when the line is a row candidate (not a fence line, not inside a fence, not a heading). */
    boolean feed(String line) {
      String stripped = PyText.strip(line);
      if (stripped.startsWith("```") || stripped.startsWith("~~~")) {
        fenced = !fenced;
        return false;
      }
      if (fenced) {
        return false;
      }
      if (isHeading(line)) {
        List<String> tokens = wpTokens(line);
        if (!tokens.isEmpty() && tokens.get(0).equals(wpId) && !done) {
          open = true;
        } else if (open && !tokens.isEmpty()) {
          open = false;
          done = true;
        }
        return false;
      }
      return true;
    }
  }

  /** {@code ^#{2,4}[^#]}: two to four hashes at the start of the line, then a character that is not one. */
  private static boolean isHeading(String line) {
    int hashes = 0;
    while (hashes < line.length() && line.charAt(hashes) == '#') {
      hashes++;
    }
    // the engine backtracks: 2 to 4 hashes, then one non-hash character, so a run of five or more never matches
    return hashes >= 2 && hashes <= 4 && hashes < line.length();
  }

  /**
   * {@code ^-\s*\[[ xX]\]\s*(T\d{3,})\b(.*)$} on a stripped line: the id and the rest of the line, or null when the line is no checkbox row.
   */
  private static String[] checkbox(String stripped) {
    if (!stripped.startsWith("-")) {
      return null;
    }
    int i = skipSpace(stripped, 1);
    if (i + 2 >= stripped.length() || stripped.charAt(i) != '[' || " xX".indexOf(stripped.charAt(i + 1)) < 0 || stripped.charAt(i + 2) != ']') {
      return null;
    }
    i = skipSpace(stripped, i + 3);
    int end = taskIdEnd(stripped, i);
    return end < 0 ? null : new String[] {stripped.substring(i, end), stripped.substring(end)};
  }

  /** The end of a {@code T\d{3,}} that starts at {@code from} and ends on a word boundary, or -1. */
  private static int taskIdEnd(String text, int from) {
    if (from >= text.length() || text.charAt(from) != 'T') {
      return -1;
    }
    int j = from + 1;
    int digits = 0;
    while (j < text.length() && isDecimal(text.codePointAt(j))) {
      j += Character.charCount(text.codePointAt(j));
      digits++;
    }
    boolean boundary = j >= text.length() || !isWord(text.codePointAt(j));
    return digits >= MIN_TASK_DIGITS && boundary ? j : -1;
  }

  /** The cells of a table row whose first cell is a subtask id ({@code id}, {@code title}, then the rest), or null. */
  private static List<String> tableRow(String stripped) {
    if (!stripped.startsWith("|")) {
      return null;
    }
    int start = 0;
    int end = stripped.length();
    while (start < end && stripped.charAt(start) == '|') {
      start++;
    }
    while (end > start && stripped.charAt(end - 1) == '|') {
      end--;
    }
    List<String> cells = new ArrayList<>();
    for (String cell : stripped.substring(start, end).split("\\|", -1)) {
      cells.add(PyText.strip(cell));
    }
    if (cells.size() < 2) {
      return null;
    }
    String first = cells.get(0);
    return taskIdEnd(first, 0) == first.length() ? cells : null;
  }

  /** {@code re.findall(r"\bWP\d{2,}\b", text)}: the tokens in order, each with its own digits. */
  private static List<String> wpTokens(String text) {
    List<String> tokens = new ArrayList<>();
    int i = 0;
    while (i < text.length()) {
      boolean atWord = i == 0 || !isWord(text.codePointBefore(i));
      if (atWord && text.startsWith("WP", i)) {
        int j = i + 2;
        int digits = 0;
        while (j < text.length() && isDecimal(text.codePointAt(j))) {
          j += Character.charCount(text.codePointAt(j));
          digits++;
        }
        if (digits >= MIN_WP_DIGITS && (j >= text.length() || !isWord(text.codePointAt(j)))) {
          tokens.add(text.substring(i, j));
          i = j;
          continue;
        }
      }
      i += Character.charCount(text.codePointAt(i));
    }
    return tokens;
  }

  private static int skipSpace(String text, int from) {
    int i = from;
    while (i < text.length() && PyText.isBlank(text.substring(i, i + Character.charCount(text.codePointAt(i))))) {
      i += Character.charCount(text.codePointAt(i));
    }
    return i;
  }

  /** Python's {@code \d} on a {@code str}: a decimal digit of any script. */
  private static boolean isDecimal(int codePoint) {
    return Character.getType(codePoint) == Character.DECIMAL_DIGIT_NUMBER;
  }

  /** Python's {@code \w} on a {@code str}: {@code str.isalnum()} or an underscore, the letters, the numbers and the underscore. */
  private static boolean isWord(int codePoint) {
    return codePoint == '_' || Character.isLetter(codePoint) || isNumber(codePoint);
  }

  private static boolean isNumber(int codePoint) {
    int type = Character.getType(codePoint);
    return type == Character.DECIMAL_DIGIT_NUMBER || type == Character.LETTER_NUMBER || type == Character.OTHER_NUMBER;
  }
}
