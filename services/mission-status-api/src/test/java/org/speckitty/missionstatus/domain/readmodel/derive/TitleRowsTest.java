package org.speckitty.missionstatus.domain.readmodel.derive;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Stream;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.MethodSource;

/**
 * {@link TitleRows} against the oracle's {@code title_rows}: every case below was run through the Python function
 * ({@code tests/contract/_mission_status_detail.py}) and the rows it gave are the expected rows, in the order it gave them. The cases are
 * the hard ones: Python's whitespace (U+00A0, U+0085, U+2028, the separators U+001C to U+001F), Unicode digits and word characters, a byte
 * order mark, CRLF and lone CR, fences, the section rule and the first-row-wins rule. A Java port that used {@code String.strip}, ASCII
 * {@code \d}, a Java line reader or newline translation fails some of them (AC-3.4).
 */
class TitleRowsTest {

  /** One oracle case: the text, the Work Package asked for and the rows (id, title or null) in order. */
  record Case(String name, String text, String wpId, List<String[]> rows) {
    @Override
    public String toString() {
      return name;
    }
  }

  static Stream<Case> cases() {
    return Stream.of(
        new Case("plain checkbox rows", "## WP01 First\n- [ ] T001 Set up\n- [x] T002 Write the test\n- [X] T003 Done\n", "WP01", List.<String[]>of(new String[] {"T001", "Set up"}, new String[] {"T002", "Write the test"}, new String[] {"T003", "Done"})),
        new Case("checkbox with spaces and tag", "## WP01\n-   [ ]   T001   [P] Parallel one\n- [ ] T002 **Bold title**\n- [ ] T003 [P] **Both**\n", "WP01", List.<String[]>of(new String[] {"T001", "Parallel one"}, new String[] {"T002", "Bold title"}, new String[] {"T003", "Both"})),
        new Case("bold needs four characters", "## WP01\n- [ ] T001 ****\n- [ ] T002 ***\n- [ ] T003 **a**\n", "WP01", List.<String[]>of(new String[] {"T001", null}, new String[] {"T002", "***"}, new String[] {"T003", "a"})),
        new Case("empty title is null", "## WP01\n- [ ] T001\n- [ ] T002   \n- [ ] T003 [P]\n", "WP01", List.<String[]>of(new String[] {"T001", null}, new String[] {"T002", null}, new String[] {"T003", null})),
        new Case("first row of an id wins even when null", "## WP01\n- [ ] T001\n- [ ] T001 Later title\n- [ ] T002 First\n- [ ] T002 Second\n", "WP01", List.<String[]>of(new String[] {"T001", null}, new String[] {"T002", "First"})),
        new Case("section closes for good", "## WP01\n- [ ] T001 In\n## WP02\n- [ ] T002 Other\n## WP01 again\n- [ ] T003 Reopened\n", "WP01", List.<String[]>of(new String[] {"T001", "In"})),
        new Case("section before the heading is not ours", "- [ ] T000 Before\n## WP01\n- [ ] T001 In\n", "WP01", List.<String[]>of(new String[] {"T001", "In"})),
        new Case("heading depths", "# WP01\n- [ ] T001 One hash\n### WP01\n- [ ] T002 Three\n#### WP02\n- [ ] T003 Four other\n", "WP01", List.<String[]>of(new String[] {"T002", "Three"})),
        new Case("five hashes is no heading", "## WP01\n- [ ] T001 In\n##### WP02\n- [ ] T002 Still in\n", "WP01", List.<String[]>of(new String[] {"T001", "In"}, new String[] {"T002", "Still in"})),
        new Case("heading without a token keeps the section", "## WP01\n- [ ] T001 In\n## Notes\n- [ ] T002 Still in\n", "WP01", List.<String[]>of(new String[] {"T001", "In"}, new String[] {"T002", "Still in"})),
        new Case("heading with two tokens uses the first", "## WP02 and WP01\n- [ ] T001 Other\n## WP01 after WP02\n- [ ] T002 Mine\n", "WP01", List.<String[]>of(new String[] {"T002", "Mine"})),
        new Case("fenced block holds no rows", "## WP01\n```\n- [ ] T001 Fake\n```\n- [ ] T002 Real\n~~~\n- [ ] T003 Fake\n~~~\n", "WP01", List.<String[]>of(new String[] {"T002", "Real"})),
        new Case("fence inside heading section toggles", "## WP01\n  ```text\n- [ ] T001 Fake\n  ```\n- [ ] T002 Real\n", "WP01", List.<String[]>of(new String[] {"T002", "Real"})),
        new Case("unterminated fence swallows the rest", "## WP01\n- [ ] T001 Real\n```\n- [ ] T002 Fake\n", "WP01", List.<String[]>of(new String[] {"T001", "Real"})),
        new Case("table rows", "## WP01\n| T001 | Table title | |\n| T002 | Other title | |\n", "WP01", List.<String[]>of(new String[] {"T001", "Table title"}, new String[] {"T002", "Other title"})),
        new Case("table row names another work package", "## WP01\n| T001 | Mine | WP01 |\n| T002 | Theirs | WP02 |\n| T003 | Both | WP02, WP01 |\n", "WP01", List.<String[]>of(new String[] {"T001", "Mine"}, new String[] {"T003", "Both"})),
        new Case("table row outside any section names this one", "| T001 | Named | WP01 |\n| T002 | Unnamed | |\n", "WP01", List.<String[]>of(new String[] {"T001", "Named"})),
        new Case("table with extra pipes", "## WP01\n||| T001 | Title | |||\n| T002 |\n| T003 | | |\n", "WP01", List.<String[]>of(new String[] {"T001", "Title"}, new String[] {"T003", null})),
        new Case("table id needs three digits", "## WP01\n| T01 | Short | |\n| T0001 | Long | |\n| T001x | Word | |\n", "WP01", List.<String[]>of(new String[] {"T0001", "Long"})),
        new Case("checkbox id needs a boundary", "## WP01\n- [ ] T001x Not a row\n- [ ] T001_ Not a row\n- [ ] T001-Row Dash is a boundary\n- [ ] T0020 Four digits\n", "WP01", List.<String[]>of(new String[] {"T001", "-Row Dash is a boundary"}, new String[] {"T0020", "Four digits"})),
        new Case("crlf lines", "## WP01\r\n- [ ] T001 Title one\r\n- [ ] T002 Title two\r\n", "WP01", List.<String[]>of(new String[] {"T001", "Title one"}, new String[] {"T002", "Title two"})),
        new Case("crlf heading keeps the section", "## WP01\r\n- [ ] T001 In\r\n## WP02\r\n- [ ] T002 Out\r\n", "WP01", List.<String[]>of(new String[] {"T001", "In"})),
        new Case("lone carriage return stays inside", "## WP01\n- [ ] T001 Left\rRight\n", "WP01", List.<String[]>of(new String[] {"T001", "Left\rRight"})),
        new Case("byte order mark hides the first heading", "\ufeff## WP01\n- [ ] T001 Hidden\n", "WP01", List.of()),
        new Case("byte order mark on a later line", "## WP01\n\ufeff- [ ] T001 Not a row\n- [ ] T002 Row\n", "WP01", List.<String[]>of(new String[] {"T002", "Row"})),
        new Case("no breaking space is stripped", "## WP01\n- [ ] T001 \u00a0Padded\u00a0\n\u00a0- [ ] T002 Lead\n", "WP01", List.<String[]>of(new String[] {"T001", "Padded"}, new String[] {"T002", "Lead"})),
        new Case("next line and line separator are stripped", "## WP01\n- [ ] T001 \u0085Title\u2028\n- [ ] T002 \u2029T\u001c\n", "WP01", List.<String[]>of(new String[] {"T001", "Title"}, new String[] {"T002", "T"})),
        new Case("unit separators are whitespace", "## WP01\n- [ ] T001 \u001fTitle\u001d\n", "WP01", List.<String[]>of(new String[] {"T001", "Title"})),
        new Case("zero width space is not", "## WP01\n- [ ] T001 \u200bTitle\n", "WP01", List.<String[]>of(new String[] {"T001", "\u200bTitle"})),
        new Case("arabic indic task id", "## WP01\n- [ ] T\u0661\u0662\u0663 Digits\n| T\u0662\u0663\u0664 | Table digits | |\n", "WP01", List.<String[]>of(new String[] {"T\u0661\u0662\u0663", "Digits"}, new String[] {"T\u0662\u0663\u0664", "Table digits"})),
        new Case("arabic indic wp token", "## WP\u0661\u0662 Heading\n- [ ] T001 Not ours\n", "WP01", List.of()),
        new Case("arabic indic wp token as cell", "## WP01\n| T001 | Title | WP\u0661\u0662 |\n| T002 | Title | WP01 |\n", "WP01", List.<String[]>of(new String[] {"T002", "Title"})),
        new Case("wp token boundaries", "## xWP01\n- [ ] T001 No\n## WP011\n- [ ] T002 No\n## WP01a\n- [ ] T003 No\n## _WP01\n- [ ] T004 No\n", "WP01", List.of()),
        new Case("wp token next to punctuation", "## (WP01)\n- [ ] T001 Yes\n", "WP01", List.<String[]>of(new String[] {"T001", "Yes"})),
        new Case("wp token next to a letter number", "## WP01\u2160\n- [ ] T001 Roman numeral is a word character\n", "WP01", List.of()),
        new Case("wp token with one digit", "## WP1\n- [ ] T001 No\n## WP01\n- [ ] T002 Yes\n", "WP01", List.<String[]>of(new String[] {"T002", "Yes"})),
        new Case("long digit wp ids", "## WP100\n- [ ] T001 Hundred\n", "WP100", List.<String[]>of(new String[] {"T001", "Hundred"})),
        new Case("surrogate pair between", "## WP01\n- [ ] T001 \ud83d\ude00 smile\n- [ ] T002 \ud835\udfd8 digit\n", "WP01", List.<String[]>of(new String[] {"T001", "\ud83d\ude00 smile"}, new String[] {"T002", "\ud835\udfd8 digit"})),
        new Case("math digit task id", "## WP01\n- [ ] T\ud835\udfcf\ud835\udfd0\ud835\udfd1 Math digits\n", "WP01", List.<String[]>of(new String[] {"T\ud835\udfcf\ud835\udfd0\ud835\udfd1", "Math digits"})),
        new Case("dash then no checkbox", "## WP01\n- T001 Not a checkbox\n- [] T002 Empty box\n- [y] T003 Wrong mark\n- [ ]T004 No space\n", "WP01", List.<String[]>of(new String[] {"T004", "No space"})),
        new Case("indented rows are stripped", "## WP01\n    - [ ] T001 Indented\n\t| T002 | Tab | |\n", "WP01", List.<String[]>of(new String[] {"T001", "Indented"}, new String[] {"T002", "Tab"})),
        new Case("heading must start the line", "## WP01\n- [ ] T001 In\n x## WP02\n- [ ] T002 Still in\n  ## WP03\n- [ ] T003 Indented heading is no heading\n", "WP01", List.<String[]>of(new String[] {"T001", "In"}, new String[] {"T002", "Still in"}, new String[] {"T003", "Indented heading is no heading"})),
        new Case("empty text", "", "WP01", List.of()),
        new Case("no section at all", "- [ ] T001 Orphan\n| T002 | Orphan table | |\n", "WP01", List.of()),
        new Case("title with pipes in checkbox", "## WP01\n- [ ] T001 a | b | c\n", "WP01", List.<String[]>of(new String[] {"T001", "a | b | c"})),
        new Case("title holds hash and fence markers", "## WP01\n- [ ] T001 ``` not a fence\n- [ ] T002 Real\n", "WP01", List.<String[]>of(new String[] {"T001", "``` not a fence"}, new String[] {"T002", "Real"})),
        new Case("bold across title cell", "## WP01\n| T001 | **Bold cell** | |\n| T002 | [P] **Tag and bold** | |\n", "WP01", List.<String[]>of(new String[] {"T001", "Bold cell"}, new String[] {"T002", "Tag and bold"})),
        new Case("tag only after strip", "## WP01\n- [ ] T001 \u00a0[P]\u00a0Tagged\n", "WP01", List.<String[]>of(new String[] {"T001", "Tagged"})),
        new Case("other work package asked", "## WP01\n- [ ] T001 One\n## WP02\n- [ ] T002 Two\n", "WP02", List.<String[]>of(new String[] {"T002", "Two"})),
        new Case("trailing newline variants", "## WP01\n- [ ] T001 One", "WP01", List.<String[]>of(new String[] {"T001", "One"})),
        new Case("percent of rows", "## WP01\n- [ ] T001 Row 1\n- [ ] T002 Row 2\n- [ ] T003 Row 3\n- [ ] T004 Row 4\n- [ ] T005 Row 5\n- [ ] T006 Row 6\n- [ ] T007 Row 7\n- [ ] T008 Row 8\n- [ ] T009 Row 9\n- [ ] T010 Row 10\n- [ ] T011 Row 11\n- [ ] T012 Row 12\n- [ ] T013 Row 13\n- [ ] T014 Row 14\n- [ ] T015 Row 15\n- [ ] T016 Row 16\n- [ ] T017 Row 17\n- [ ] T018 Row 18\n- [ ] T019 Row 19\n- [ ] T020 Row 20\n- [ ] T021 Row 21\n- [ ] T022 Row 22\n- [ ] T023 Row 23\n- [ ] T024 Row 24\n", "WP01", List.<String[]>of(new String[] {"T001", "Row 1"}, new String[] {"T002", "Row 2"}, new String[] {"T003", "Row 3"}, new String[] {"T004", "Row 4"}, new String[] {"T005", "Row 5"}, new String[] {"T006", "Row 6"}, new String[] {"T007", "Row 7"}, new String[] {"T008", "Row 8"}, new String[] {"T009", "Row 9"}, new String[] {"T010", "Row 10"}, new String[] {"T011", "Row 11"}, new String[] {"T012", "Row 12"}, new String[] {"T013", "Row 13"}, new String[] {"T014", "Row 14"}, new String[] {"T015", "Row 15"}, new String[] {"T016", "Row 16"}, new String[] {"T017", "Row 17"}, new String[] {"T018", "Row 18"}, new String[] {"T019", "Row 19"}, new String[] {"T020", "Row 20"}, new String[] {"T021", "Row 21"}, new String[] {"T022", "Row 22"}, new String[] {"T023", "Row 23"}, new String[] {"T024", "Row 24"})));
  }

  @ParameterizedTest(name = "{0}")
  @MethodSource("cases")
  void theRowsAreTheOraclesRowsInTheOraclesOrder(Case oracle) {
    Map<String, String> expected = new LinkedHashMap<>();
    oracle.rows().forEach(row -> expected.put(row[0], row[1]));

    Map<String, String> served = TitleRows.titles(oracle.text(), oracle.wpId());

    assertThat(served).containsExactlyEntriesOf(expected);
  }

  @Test
  void theCorpusIsNotEmptyAndHoldsRowsAndNoRows() {
    long withRows = cases().filter(oracle -> !oracle.rows().isEmpty()).count();
    long withoutRows = cases().filter(oracle -> oracle.rows().isEmpty()).count();

    assertThat(withRows).isGreaterThan(40);
    assertThat(withoutRows).isGreaterThan(3);
  }

  @Test
  void cleaningDropsTheTagOnePairOfBoldMarkersAndPythonWhitespace() {
    assertThat(TitleRows.cleanTitle("  [P]  **x**  ")).isEqualTo("x");
    assertThat(TitleRows.cleanTitle("\u00a0x\u00a0")).isEqualTo("x");
    assertThat(TitleRows.cleanTitle("****")).isNull();
    assertThat(TitleRows.cleanTitle("")).isNull();
    assertThat(TitleRows.cleanTitle("[P]")).isNull();
    assertThat(TitleRows.cleanTitle("***")).isEqualTo("***");
  }
}
