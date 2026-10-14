package org.speckitty.missionstatus.adapter.out.filesystem.codec;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import org.speckitty.missionstatus.domain.model.ReviewCycleMeta;

/** Row M11 and AC-3.9 at the codec: the review time and reviewer of a review-cycle file, or two nulls; a byte is never replaced. */
class ReviewCycleCodecTest {

  private static final String VALID =
      "cycle_number: 1\nwp_id: WP01\nmission_slug: alpha-mission\nreviewer_agent: claude\nreviewed_at: '2026-09-01T10:00:00+00:00'\n";

  private static ReviewCycleMeta decode(String text) {
    return ReviewCycleCodec.decode(text.getBytes(StandardCharsets.UTF_8));
  }

  private static ReviewCycleMeta file(String yaml) {
    return decode("---\n" + yaml + "---\n\n## Findings\n");
  }

  @Test
  void aWellFormedFileGivesItsReviewTimeAndReviewer() {
    assertThat(file(VALID)).isEqualTo(new ReviewCycleMeta("2026-09-01T10:00:00+00:00", "claude"));
  }

  @Test
  void aReviewTimeThatIsNotRfc3339IsNullWhileTheReviewerIsKept() {
    ReviewCycleMeta meta = file(VALID.replace("2026-09-01T10:00:00+00:00", "yesterday"));
    assertThat(meta.reviewedAt()).isNull();
    assertThat(meta.reviewer()).isEqualTo("claude");
  }

  @ParameterizedTest
  @ValueSource(
      strings = {
        "2026-09-01T10:00:00Z", "2026-09-01t10:00:00z", "2026-09-01T10:00:00.5+05:30", "2026-09-01T10:00:00-23:59", "2026-12-31T23:59:60Z",
        "2024-02-29T00:00:00Z"
      })
  void anRfc3339DateTimeIsServed(String instant) {
    assertThat(ReviewCycleCodec.isRfc3339DateTime(instant)).as(instant).isTrue();
  }

  @ParameterizedTest
  @ValueSource(
      strings = {
        "2026-09-01", "2026-09-01T10:00:00", "2026-09-01 10:00:00Z", "2026-13-01T00:00:00Z", "2026-02-30T00:00:00Z", "2025-02-29T00:00:00Z",
        "0000-01-01T00:00:00Z", "2026-09-01T24:00:00Z", "2026-09-01T10:60:00Z", "2026-09-01T10:00:61Z", "2026-09-01T10:00:00+24:00",
        "2026-09-01T10:00:00+05:60", "2026-09-01T10:00:00+5:00", "2026-09-01T10:00Z", "", "not a time", "2026-09-01T10:00:00Z\n\n"
      })
  void anythingElseIsNotADateTime(String instant) {
    assertThat(ReviewCycleCodec.isRfc3339DateTime(instant)).as(instant).isFalse();
  }

  @Test
  void aTrailingLineFeedIsAcceptedBecausePythonsDollarAllowsOne() {
    assertThat(ReviewCycleCodec.isRfc3339DateTime("2026-09-01T10:00:00Z\n")).isTrue();
  }

  @Test
  void anUnquotedTimestampIsATimestampNotAStringSoTheWholeFileDoesNotParse() {
    assertThat(file(VALID.replace("'2026-09-01T10:00:00+00:00'", "2026-09-01T10:00:00+00:00"))).isEqualTo(ReviewCycleMeta.UNPARSED);
  }

  @Test
  void eachMissingOrInvalidFieldMakesTheFileUnparsed() {
    for (String field : new String[] {"cycle_number", "wp_id", "mission_slug", "reviewer_agent", "reviewed_at"}) {
      String without = VALID.lines().filter(line -> !line.startsWith(field + ":")).reduce("", (all, line) -> all + line + "\n");
      assertThat(file(without)).as("without " + field).isEqualTo(ReviewCycleMeta.UNPARSED);
    }
    assertThat(file(VALID.replace("wp_id: WP01", "wp_id: ''"))).isEqualTo(ReviewCycleMeta.UNPARSED);
    assertThat(file(VALID.replace("reviewer_agent: claude", "reviewer_agent: 5"))).isEqualTo(ReviewCycleMeta.UNPARSED);
    assertThat(file(VALID.replace("mission_slug: alpha-mission", "mission_slug: [a]"))).isEqualTo(ReviewCycleMeta.UNPARSED);
  }

  @Test
  void theCycleNumberMustReadAsAPositiveInteger() {
    for (String ok : new String[] {"1", "'3'", "2.9", "0x2", "' 4 '"}) {
      assertThat(file(VALID.replace("cycle_number: 1", "cycle_number: " + ok)).reviewer()).as(ok).isEqualTo("claude");
    }
    for (String bad : new String[] {"0", "-1", "true", "false", "abc", "~", "[1]", "{a: 1}", "0.5", ".nan", ".inf", "2026-09-01", "''"}) {
      assertThat(file(VALID.replace("cycle_number: 1", "cycle_number: " + bad))).as(bad).isEqualTo(ReviewCycleMeta.UNPARSED);
    }
    assertThat(file(VALID.replace("cycle_number: 1\n", ""))).as("absent").isEqualTo(ReviewCycleMeta.UNPARSED);
  }

  @Test
  void affectedFilesAreCheckedAsTheOracleChecksThem() {
    assertThat(file(VALID + "affected_files: []\n").reviewer()).isEqualTo("claude");
    assertThat(file(VALID + "affected_files:\n- path: a.py\n  line_range: 1-5\n- path: b.py\n  line_range:\n").reviewer()).isEqualTo("claude");
    assertThat(file(VALID + "affected_files: nope\n")).isEqualTo(ReviewCycleMeta.UNPARSED);
    assertThat(file(VALID + "affected_files:\n")).isEqualTo(ReviewCycleMeta.UNPARSED);
    assertThat(file(VALID + "affected_files: [a.py]\n")).isEqualTo(ReviewCycleMeta.UNPARSED);
    assertThat(file(VALID + "affected_files:\n- path: ''\n")).isEqualTo(ReviewCycleMeta.UNPARSED);
    assertThat(file(VALID + "affected_files:\n- path: a\n  line_range: 5\n")).isEqualTo(ReviewCycleMeta.UNPARSED);
    assertThat(file(VALID + "reproduction_command: 'make test'\n").reviewer()).isEqualTo("claude");
    assertThat(file(VALID + "reproduction_command: 5\n")).isEqualTo(ReviewCycleMeta.UNPARSED);
    assertThat(file(VALID + "verdict: rejected\nreview_artifact_override_actor: 5\n").reviewer()).as("stray and override keys are tolerated").isEqualTo("claude");
  }

  @Test
  void aFileThatDoesNotFrameParseOrMapIsUnparsed() {
    assertThat(decode("no frontmatter")).isEqualTo(ReviewCycleMeta.UNPARSED);
    assertThat(decode("---\n" + VALID)).as("no closing delimiter").isEqualTo(ReviewCycleMeta.UNPARSED);
    assertThat(decode("---\n---\n")).as("an empty frontmatter has no \\n--- after the opening one").isEqualTo(ReviewCycleMeta.UNPARSED);
    assertThat(file("a: [\n")).as("a YAML syntax error").isEqualTo(ReviewCycleMeta.UNPARSED);
    assertThat(file(VALID + "wp_id: WP02\n")).as("a duplicate key").isEqualTo(ReviewCycleMeta.UNPARSED);
    assertThat(file("- a\n- b\n")).as("not a mapping").isEqualTo(ReviewCycleMeta.UNPARSED);
    assertThat(file("~\n")).as("a null document").isEqualTo(ReviewCycleMeta.UNPARSED);
    assertThat(file(VALID + "x: &a 1\n")).as("an anchor is refused").isEqualTo(ReviewCycleMeta.UNPARSED);
  }

  @Test
  void theFrontmatterEndsAtTheFirstNewlineTripleDashEvenWithTextAfterIt() {
    assertThat(decode("---\n" + VALID + "---x\nbody").reviewer()).isEqualTo("claude");
  }

  @Test
  void aByteOrderMarkMakesTheFileUnparsedBecauseTheTextMustStartWithTheDashes() {
    byte[] content = ("\ufeff---\n" + VALID + "---\n").getBytes(StandardCharsets.UTF_8);
    assertThat(ReviewCycleCodec.decode(content)).isEqualTo(ReviewCycleMeta.UNPARSED);
  }

  @Test
  void crLfLineEndingsAreTranslatedAsPythonReadsTheFile() {
    String crlf = ("---\n" + VALID + "---\n\nbody\n").replace("\n", "\r\n");
    assertThat(decode(crlf).reviewer()).isEqualTo("claude");
  }

  @Test
  void bytesThatAreNotStrictUtf8AreNeverRepairedAndAReplacementCharacterInTextIsKept() {
    byte[] valid = ("---\n" + VALID + "---\n").getBytes(StandardCharsets.UTF_8);
    byte[] broken = new byte[valid.length + 1];
    System.arraycopy(valid, 0, broken, 0, valid.length);
    broken[valid.length] = (byte) 0xC3;
    assertThat(ReviewCycleCodec.decode(broken)).isEqualTo(ReviewCycleMeta.UNPARSED);
    ReviewCycleMeta literal = decode("---\n" + VALID.replace("reviewer_agent: claude", "reviewer_agent: cl\ufffdude") + "---\n");
    assertThat(literal.reviewer()).as("a U+FFFD that was in the file is kept as it is").isEqualTo("cl\ufffdude");
  }
}
