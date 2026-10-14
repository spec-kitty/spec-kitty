package org.speckitty.missionstatus.domain.redaction;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.ArrayList;
import java.util.List;
import java.util.regex.Pattern;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestFactory;
import org.speckitty.missionstatus.testsupport.LeakPatternsFile;

/**
 * {@link LeakClasses#compile(String)} against Python's {@code re}. Python's {@code \w \s \d} on a {@code str} are not Java's
 * {@code UNICODE_CHARACTER_CLASS} classes (Java's {@code \w} also matches combining marks, connector punctuation and join controls, and
 * its {@code \s} omits U+001C to U+001F), and a redaction pattern that reads them differently leaks: the lookbehind of a host path
 * and of an address is {@code [\w.~-]}. Two checks hold the line: every code point from U+0000 to U+10FFFF is matched by the compiled
 * classes exactly as the recorded run of CPython matched it, and a table of edge characters (expected values from the real patterns of
 * {@code leak_patterns.py}) gets the verdicts Python gave.
 */
class LeakClassesPythonParityTest {

  private final LeakClasses leaks = LeakPatternsFile.load();

  @TestFactory
  List<DynamicTest> everyProbeGetsTheVerdictOfThePythonPatterns() {
    return LeakProbeCases.all().stream()
        .map(
            probe ->
                DynamicTest.dynamicTest(
                    probe.name(),
                    () -> {
                      assertThat(leaks.strictLeak(probe.text())).as("strictLeak").isEqualTo(probe.strictLeak());
                      assertThat(leaks.humanLeak(probe.text())).as("humanLeak").isEqualTo(probe.humanLeak());
                      LeakClasses.Replaced paths = leaks.redactHumanHostPaths(probe.text(), "[path]");
                      assertThat(paths.text()).as("paths").isEqualTo(probe.pathsRedacted());
                      assertThat(paths.count()).as("path count").isEqualTo(probe.pathCount());
                      LeakClasses.Replaced emails = leaks.redactEmails(probe.text(), "[email]");
                      assertThat(emails.text()).as("emails").isEqualTo(probe.emailsRedacted());
                      assertThat(emails.count()).as("email count").isEqualTo(probe.emailCount());
                    }))
        .toList();
  }

  @Test
  void theProbeTableCoversTheEdgeCharactersOfTheFinding() {
    List<String> names = LeakProbeCases.all().stream().map(LeakProbeCases.Probe::name).toList();
    assertThat(names).doesNotHaveDuplicates();
    for (String code : List.of("U+0301", "U+200D", "U+203F", "U+001C", "U+001D", "U+001E", "U+001F")) {
      assertThat(names).as(code).anyMatch(name -> name.startsWith(code + " before-path")).anyMatch(name -> name.startsWith(code + " before-email"));
    }
    // The table is not vacuous: Python redacted and left alone in both directions, so a pattern that ignores the class cannot pass.
    assertThat(LeakProbeCases.all()).anyMatch(probe -> probe.pathCount() > 0).anyMatch(probe -> probe.pathCount() == 0).anyMatch(probe -> probe.emailCount() > 0);
  }

  @Test
  void theWordSpaceAndDigitClassesMatchEveryCodePointAsPythonDoes() {
    boolean[] word = new boolean[0x110000];
    boolean[] space = new boolean[0x110000];
    boolean[] digit = new boolean[0x110000];
    readRanges(word, space, digit);
    // Outside a class, inside one, negated inside one, and the complement forms; the translator has a branch for each.
    assertClass("\\w", word, false);
    assertClass("\\W", word, true);
    assertClass("[\\w]", word, false);
    assertClass("[^\\w]", word, true);
    assertClass("[\\W]", word, true);
    assertClass("[^\\W]", word, false);
    assertClass("\\s", space, false);
    assertClass("\\S", space, true);
    assertClass("[\\s]", space, false);
    assertClass("[^\\s]", space, true);
    assertClass("[\\S]", space, true);
    assertClass("[^\\S]", space, false);
    assertClass("\\d", digit, false);
    assertClass("\\D", digit, true);
    assertClass("[\\d]", digit, false);
    assertClass("[^\\d]", digit, true);
    assertClass("[\\D]", digit, true);
    assertClass("[^\\D]", digit, false);
    // The exact classes of the leak patterns: a lookbehind and a negated set that hold other members besides the shorthand.
    boolean[] lookbehind = word.clone();
    for (char member : ".~-".toCharArray()) {
      lookbehind[member] = true;
    }
    assertClass("[\\w.~-]", lookbehind, false);
    assertLookbehind("(?<![\\w.~-])x", lookbehind);
    assertLookbehind("(?<![\\w])x", word);
    boolean[] notSpaceOrSlash = space.clone();
    notSpaceOrSlash['/'] = true;
    assertClass("[^\\s/]", notSpaceOrSlash, true);
    assertClass("[^/\\s]", notSpaceOrSlash, true);
  }

  @Test
  void anEscapedBackslashIsNotAShorthandAndABracketInAClassIsALiteral() {
    assertThat(LeakClasses.compile("\\\\w").matcher("\\w").matches()).isTrue();
    assertThat(LeakClasses.compile("\\\\w").matcher("\\a").matches()).isFalse();
    assertThat(LeakClasses.compile("\\\\\\w").matcher("\\a").matches()).isTrue();
    assertThat(LeakClasses.compile("[[]").matcher("[").matches()).isTrue();
    assertThat(LeakClasses.compile("[a[b]").matcher("[").matches()).isTrue();
    assertThat(LeakClasses.compile("[a&&b]").matcher("&").matches()).isTrue();
    assertThat(LeakClasses.compile("[a&&b]").matcher("b").matches()).isTrue();
    assertThat(LeakClasses.compile("[]a]").matcher("]").matches()).isTrue();
    assertThat(LeakClasses.compile("[^]a]").matcher("b").matches()).isTrue();
    assertThat(LeakClasses.compile("[^]a]").matcher("]").matches()).isFalse();
    assertThat(LeakClasses.compile("a\\.b").matcher("a.b").matches()).isTrue();
    assertThatThrownBy(() -> LeakClasses.compile("a\\")).isInstanceOf(java.util.regex.PatternSyntaxException.class);
  }

  @Test
  void aWordBoundaryHasNoPythonEquivalentHereSoItIsRefusedRatherThanReadWrongly() {
    assertThatThrownBy(() -> LeakClasses.compile("\\bfoo")).isInstanceOf(IllegalArgumentException.class).hasMessageContaining("\\b");
    assertThatThrownBy(() -> LeakClasses.compile("foo\\B")).isInstanceOf(IllegalArgumentException.class);
  }

  private static void assertClass(String source, boolean[] expected, boolean complement) {
    Pattern pattern = LeakClasses.compile(source);
    List<String> wrong = new ArrayList<>();
    int checked = 0;
    for (int codePoint = 0; codePoint < expected.length; codePoint++) {
      boolean want = expected[codePoint] != complement;
      boolean got = pattern.matcher(new String(Character.toChars(codePoint))).matches();
      checked++;
      if (got != want && wrong.size() < 10) {
        wrong.add(String.format("U+%04X java=%s python=%s", codePoint, got, want));
      }
    }
    assertThat(checked).isEqualTo(0x110000);
    assertThat(wrong).as(source).isEmpty();
  }

  /** A negative lookbehind sees the whole character before the match, supplementary ones included: x is found after a code point that is not in the set. */
  private static void assertLookbehind(String source, boolean[] inSet) {
    Pattern pattern = LeakClasses.compile(source);
    List<String> wrong = new ArrayList<>();
    for (int codePoint = 0; codePoint < inSet.length; codePoint++) {
      String before = new String(Character.toChars(codePoint));
      boolean found = pattern.matcher(before + "x").find(before.length());
      if (found == inSet[codePoint] && wrong.size() < 10) {
        wrong.add(String.format("U+%04X found=%s", codePoint, found));
      }
    }
    assertThat(wrong).as(source).isEmpty();
  }

  private static void readRanges(boolean[] word, boolean[] space, boolean[] digit) {
    fill(word, PythonReClasses.WORD);
    fill(space, PythonReClasses.SPACE);
    fill(digit, PythonReClasses.DIGIT);
  }

  private static void fill(boolean[] target, String ranges) {
    for (String range : ranges.split(",")) {
      String[] bounds = range.split("-");
      for (int codePoint = Integer.parseInt(bounds[0], 16); codePoint <= Integer.parseInt(bounds[1], 16); codePoint++) {
        target[codePoint] = true;
      }
    }
  }

  /** AC-5.6: the artifact corpus. Each secret pattern at its minimum length is found, one short of it is not; assembled at test time (C-006). */
  @Test
  void theCredentialPredicateAgreesWithTheSecretPatternsAtTheirMinimumLengths() {
    for (String kind : List.of("p", "o", "u", "s", "r")) {
      assertThat(leaks.credential("gh" + kind + "_" + "A".repeat(36))).as("gh" + kind + " 36").isTrue();
      assertThat(leaks.credential("gh" + kind + "_" + "A".repeat(35))).as("gh" + kind + " 35").isFalse();
    }
    assertThat(leaks.credential("github" + "_pat_" + "A".repeat(40))).isTrue();
    assertThat(leaks.credential("github" + "_pat_" + "A".repeat(39))).isFalse();
    assertThat(leaks.credential("AK" + "IA" + "A".repeat(16))).isTrue();
    assertThat(leaks.credential("AK" + "IA" + "A".repeat(15))).isFalse();
    assertThat(leaks.credential("AK" + "IA" + "A".repeat(17))).as("a longer run of the same class is not a key id").isFalse();
    assertThat(leaks.credential("-----BEGIN " + "EC PRIVATE KEY-----")).isTrue();
    assertThat(leaks.credential("x" + "ghp_" + "A".repeat(36))).as("the lookbehind: glued onto a word character").isFalse();
  }
}
