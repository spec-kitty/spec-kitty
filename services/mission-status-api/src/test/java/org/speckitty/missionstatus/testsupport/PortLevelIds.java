package org.speckitty.missionstatus.testsupport;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * The committed id list of the port-level subset, {@code src/test/resources/portlevel-tests.txt} (FR-013, AC-13a), and its grammar.
 *
 * <p>Grammar, version 1. One test per line: {@code <id> <ClassName>#<method>}, the two fields separated by one space. Blank lines and
 * lines starting with {@code #} are ignored. {@code <id>} is {@code <criterion>[/<case>...]} where the criterion is an acceptance
 * criterion such as {@code AC-4a} and each case is {@code [A-Za-z0-9][A-Za-z0-9-]*}; ids are unique. {@code <ClassName>} is the simple
 * name of a top-level class in {@link #PORT_PACKAGE}; {@code <method>} is a method of it that carries {@link PortLevelTest} with the
 * same id. The second-leg launcher of a later work package parses the same lines through {@link #load()}.
 */
public final class PortLevelIds {

  public static final String RESOURCE = "/portlevel-tests.txt";
  public static final String PORT_PACKAGE = "org.speckitty.missionstatus.conformance.port";

  /**
   * The ids FR-013 names, as id groups: a group is met by a listed id equal to it or starting with {@code group + "/"}. This is the
   * recorded floor of the file (FR-013): an emptied or trimmed list fails.
   */
  public static final List<String> FR013_GROUPS =
      List.of(
          "AC-2a/interleaved", "AC-2a/lifecycle-only", "AC-2a/no-ledger", "AC-2a/log-truncated", "AC-2a/crlf-and-listing",
          "AC-2b", "AC-5a", "AC-5c", "AC-3g", "AC-3i",
          "AC-4a/L1", "AC-4a/L3a", "AC-4a/L3b", "AC-4a/L4", "AC-4a/L4b");

  /**
   * The ids that cannot run yet: the AC-2a shells delegate to {@link Ac2aGoldenHook}, which has no goldens to compare until the golden
   * work package lands, so it skips them. The interim run check executes every listed id except these and requires exactly these to be
   * skipped. The golden work package deletes this constant together with that check.
   */
  public static final Set<String> INTERIM_GOLDEN_DEPENDENT_IDS =
      Set.of("AC-2a/interleaved", "AC-2a/lifecycle-only", "AC-2a/no-ledger", "AC-2a/log-truncated", "AC-2a/crlf-and-listing");

  private static final Pattern LINE = Pattern.compile("^(AC-[0-9]+[a-z]?(?:/[A-Za-z0-9][A-Za-z0-9-]*)*) ([A-Z][A-Za-z0-9]*)#([a-z][A-Za-z0-9]*)$");

  private PortLevelIds() {}

  /** One line of the file. */
  public record Entry(String id, String className, String method) {

    public String qualifiedClassName() {
      return PORT_PACKAGE + "." + className;
    }
  }

  /** The entries of the committed file, in file order. */
  public static List<Entry> load() {
    try (InputStream in = PortLevelIds.class.getResourceAsStream(RESOURCE)) {
      if (in == null) {
        throw new IllegalStateException(RESOURCE + " is not on the test classpath");
      }
      return parse(new String(in.readAllBytes(), StandardCharsets.UTF_8));
    } catch (IOException unreadable) {
      throw new IllegalStateException("cannot read " + RESOURCE, unreadable);
    }
  }

  /** Parses the grammar; a malformed line or a duplicate id is an error naming the line. */
  public static List<Entry> parse(String text) {
    List<Entry> entries = new ArrayList<>();
    Set<String> seen = new LinkedHashSet<>();
    int number = 0;
    for (String raw : text.split("\n", -1)) {
      number++;
      String line = raw.stripTrailing();
      if (line.isEmpty() || line.startsWith("#")) {
        continue;
      }
      Matcher matcher = LINE.matcher(line);
      if (!matcher.matches()) {
        throw new IllegalArgumentException("portlevel-tests.txt line " + number + " does not match '<id> <ClassName>#<method>'");
      }
      if (!seen.add(matcher.group(1))) {
        throw new IllegalArgumentException("portlevel-tests.txt line " + number + " repeats id " + matcher.group(1));
      }
      entries.add(new Entry(matcher.group(1), matcher.group(2), matcher.group(3)));
    }
    return List.copyOf(entries);
  }

  public static Set<String> ids(List<Entry> entries) {
    Set<String> ids = new LinkedHashSet<>();
    entries.forEach(entry -> ids.add(entry.id()));
    return ids;
  }

  /** The distinct qualified class names the list names. */
  public static Set<String> classNames(List<Entry> entries) {
    Set<String> names = new LinkedHashSet<>();
    entries.forEach(entry -> names.add(entry.qualifiedClassName()));
    return names;
  }

  /** The FR-013 groups that no listed id meets (empty when the floor is met). */
  public static List<String> unmetFloorGroups(List<Entry> entries) {
    Set<String> ids = ids(entries);
    return FR013_GROUPS.stream().filter(group -> ids.stream().noneMatch(id -> id.equals(group) || id.startsWith(group + "/"))).toList();
  }
}
