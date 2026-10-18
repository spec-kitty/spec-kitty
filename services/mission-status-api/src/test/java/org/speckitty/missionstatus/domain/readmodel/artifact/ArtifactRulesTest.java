package org.speckitty.missionstatus.domain.readmodel.artifact;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.testsupport.LeakPatternsFile;

/** The pure rules of the artifact reads, one test per rule of the reference reader ({@code tests/contract/_mission_status_artifacts.py}). */
class ArtifactRulesTest {

  private final ArtifactText text = new ArtifactText(LeakPatternsFile.load());

  @Test
  void thePathRuleNamesEachReasonInTheReferenceOrder() {
    Map<String, String> reasons =
        Map.ofEntries(
            Map.entry("", "empty"),
            Map.entry("a".repeat(513), "too_long"),
            Map.entry("/etc/passwd", "absolute"),
            Map.entry("~/x", "tilde"),
            Map.entry("C:x", "drive_letter"),
            Map.entry("a\\b", "backslash"),
            Map.entry("a\0b", "nul"),
            Map.entry("a b", "line_break"),
            Map.entry("a\u001cb", "line_break"),
            Map.entry("a/", "trailing_slash"),
            Map.entry("a//b", "empty_segment"),
            Map.entry("./a", "dot_segment"),
            Map.entry("../meta.json", "dotdot_segment"),
            Map.entry("a/./b/../c", "dot_segment"),
            Map.entry("a\uD800b", "not_utf8"));
    reasons.forEach((path, reason) -> assertThat(ArtifactPathRule.malformed(path)).as(path).contains(reason));
    for (String valid : new String[] {"spec.md", "tasks/WP01-example.md", "notes/with space.md", ".hidden", "home/x", "a@b", "été.md", "😀.md", "..a", "a.."}) {
      assertThat(ArtifactPathRule.isValid(valid)).as(valid).isTrue();
    }
  }

  @Test
  void lengthIsCountedInCodePointsNotInUtf16Units() {
    String emoji = "😀";
    assertThat(ArtifactPathRule.isValid(emoji.repeat(512))).isTrue();
    assertThat(ArtifactPathRule.malformed(emoji.repeat(513))).contains("too_long");
    assertThat(ArtifactPathRule.isValid("a".repeat(512))).isTrue();
  }

  @Test
  void aDriveLetterIsAnAsciiLetterThenAColon() {
    assertThat(ArtifactPathRule.malformed("z:")).contains("drive_letter");
    assertThat(ArtifactPathRule.isValid("1:x")).isTrue();
    assertThat(ArtifactPathRule.isValid("é:x")).isTrue();
    assertThat(ArtifactPathRule.isValid("😀:x")).isTrue();
  }

  @Test
  void theClassifierTakesTheFirstMatchingRule() {
    Map<String, ArtifactKind> kinds =
        Map.ofEntries(
            Map.entry("tasks/WP01-x/review-cycle-1.md", ArtifactKind.REVIEW_CYCLE),
            Map.entry("tasks/WP01-x/review-cycle-10.md", ArtifactKind.REVIEW_CYCLE),
            Map.entry("tasks/WP01-x/review-cycle-01.md", ArtifactKind.OTHER),
            Map.entry("tasks/WP01-x/review-cycle-0.md", ArtifactKind.OTHER),
            Map.entry("tasks/a/b/review-cycle-1.md", ArtifactKind.OTHER),
            Map.entry("tasks/WP01-example.md", ArtifactKind.WORK_PACKAGE_PROMPT),
            Map.entry("tasks/WP1-example.md", ArtifactKind.OTHER),
            Map.entry("tasks/WP123-.md", ArtifactKind.WORK_PACKAGE_PROMPT),
            Map.entry("tasks/README.md", ArtifactKind.OTHER),
            Map.entry("spec.md", ArtifactKind.SPEC),
            Map.entry("plan.md", ArtifactKind.PLAN),
            Map.entry("tasks.md", ArtifactKind.TASKS),
            Map.entry("data-model.md", ArtifactKind.DATA_MODEL),
            Map.entry("quickstart.md", ArtifactKind.QUICKSTART),
            Map.entry("analysis-report.md", ArtifactKind.ANALYSIS_REPORT),
            Map.entry("research.md", ArtifactKind.RESEARCH),
            Map.entry("research/notes.csv", ArtifactKind.RESEARCH),
            Map.entry("research", ArtifactKind.OTHER),
            Map.entry("contracts/api.yaml", ArtifactKind.CONTRACT),
            Map.entry("checklists/requirements.md", ArtifactKind.CHECKLIST),
            Map.entry("notes/spec.md", ArtifactKind.OTHER),
            Map.entry("meta.json", ArtifactKind.OTHER));
    kinds.forEach((path, kind) -> assertThat(ArtifactKind.classify(path)).as(path).isEqualTo(kind));
    assertThat(ArtifactKind.REVIEW_CYCLE.wire()).isEqualTo("review_cycle");
    assertThat(ArtifactKind.DATA_MODEL.wire()).isEqualTo("data_model");
  }

  @Test
  void theMediaTypeComesFromTheExtensionWithItsCase() {
    assertThat(ArtifactMediaType.of("spec.md")).isEqualTo("text/markdown");
    assertThat(ArtifactMediaType.of("contracts/api.yaml")).isEqualTo("application/yaml");
    assertThat(ArtifactMediaType.of("a.yml")).isEqualTo("application/yaml");
    assertThat(ArtifactMediaType.of("status.events.jsonl")).isEqualTo("application/x-ndjson");
    assertThat(ArtifactMediaType.of("a.json")).isEqualTo("application/json");
    assertThat(ArtifactMediaType.of("r/x.csv")).isEqualTo("text/csv");
    assertThat(ArtifactMediaType.of("README.MD")).isEqualTo("text/plain");
    assertThat(ArtifactMediaType.of("Makefile")).isEqualTo("text/plain");
    assertThat(ArtifactMediaType.of(".md")).isEqualTo("text/markdown");
    assertThat(ArtifactMediaType.of("a.")).isEqualTo("text/plain");
    assertThat(ArtifactMediaType.of("dir.md/file")).isEqualTo("text/plain");
  }

  @Test
  void theRootStatusRecordsMatchByPythonCaseFold() {
    for (String path : new String[] {"status.json", "STATUS.JSON", "Status.Events.Jsonl", "ſtatus.json", "ﬆatus.json", "ﬅatus.events.jsonl"}) {
      assertThat(StatusRecordNames.isStatusRecord(path)).as(path).isTrue();
    }
    for (String path : new String[] {"tasks/status.json", "status.jsonl", "status.events.json", "İtatus.json", "status.json.bak"}) {
      assertThat(StatusRecordNames.isStatusRecord(path)).as(path).isFalse();
    }
  }

  @Test
  void theModifiedTimeIsWholeSecondsInUtcWithZ() {
    assertThat(ArtifactTimestamp.format(0)).isEqualTo("1970-01-01T00:00:00Z");
    assertThat(ArtifactTimestamp.format(1_758_537_000L)).isEqualTo("2025-09-22T10:30:00Z");
  }

  @Test
  void theTextDecisionFollowsTheReferenceOrder() {
    assertThat(text.decide(new byte[ArtifactText.MAX_CONTENT_BYTES + 1]).refusal()).isEqualTo(ArtifactRefusalCode.ARTIFACT_TOO_LARGE);
    assertThat(text.decide(new byte[] {'a', 0, 'b'}).refusal()).isEqualTo(ArtifactRefusalCode.ARTIFACT_NOT_TEXT);
    String token = "gh" + "p_" + "A".repeat(36);
    assertThat(text.decide(("x " + token + " y").getBytes(StandardCharsets.UTF_8)).refusal()).isEqualTo(ArtifactRefusalCode.ARTIFACT_SECRET);
    String key = "-----BEGIN " + "RSA PRIVATE KEY-----";
    assertThat(text.decide(key.getBytes(StandardCharsets.UTF_8)).refusal()).isEqualTo(ArtifactRefusalCode.ARTIFACT_SECRET);
    ArtifactText.Decision empty = text.decide(new byte[0]);
    assertThat(empty.served()).isTrue();
    assertThat(empty.content()).isEmpty();
    assertThat(empty.redacted()).isFalse();
  }

  @Test
  void strictUtf8RefusesWhatPythonRefusesAndKeepsAByteOrderMark() {
    byte[][] refused = {
      {(byte) 0xff}, {(byte) 0xc0, (byte) 0x80}, {(byte) 0xe0, (byte) 0x80, (byte) 0x80}, {(byte) 0xed, (byte) 0xa0, (byte) 0x80},
      {(byte) 0xf4, (byte) 0x90, (byte) 0x80, (byte) 0x80}, {(byte) 0xf5, (byte) 0x80, (byte) 0x80, (byte) 0x80}, {(byte) 0xe2, (byte) 0x82},
      {(byte) 0x80}, {'a', (byte) 0xc3}
    };
    for (byte[] bytes : refused) {
      assertThat(text.decide(bytes).refusal()).isEqualTo(ArtifactRefusalCode.ARTIFACT_NOT_TEXT);
    }
    ArtifactText.Decision bom = text.decide(new byte[] {(byte) 0xef, (byte) 0xbb, (byte) 0xbf, 'h', 'i'});
    assertThat(bom.content()).isEqualTo("﻿hi");
    ArtifactText.Decision supplementary = text.decide("😀 € é".getBytes(StandardCharsets.UTF_8));
    assertThat(supplementary.content()).isEqualTo("😀 € é");
  }

  @Test
  void hostPathsAndAddressesAreRedactedWithTheirWholeToken() {
    String home = "/" + "home/alice/project/x.md";
    String mail = "alice" + "@" + "example.com";
    ArtifactText.Decision decision = text.decide(("Work happened in " + home + " and the question went to " + mail + ".\n").getBytes(StandardCharsets.UTF_8));
    assertThat(decision.content()).isEqualTo("Work happened in [path] and the question went to [email].\n");
    assertThat(decision.redacted()).isTrue();
    assertThat(text.decide("plain text".getBytes(StandardCharsets.UTF_8)).redacted()).isFalse();
  }

  @Test
  void aScanThatOverflowsTheRegexStackFailsClosedInsteadOfThrowing() {
    // java.util.regex recurses once per repetition of a variable-width group; these inputs overflow the stack (review finding B1).
    String pem = "-----BEGIN " + "A ".repeat(20_000);
    String address = "a" + "@" + "b" + ".c".repeat(120_000);
    for (String hostile : new String[] {pem, address}) {
      ArtifactText.Decision decision = text.decide(hostile.getBytes(StandardCharsets.UTF_8));
      assertThat(decision.served()).isFalse();
      assertThat(decision.refusal()).isEqualTo(ArtifactRefusalCode.ARTIFACT_UNREADABLE);
      assertThat(decision.content()).isNull();
    }
  }

  @Test
  void everyRefusalCodeCarriesTheStatusOfTheContract() {
    assertThat(ArtifactRefusalCode.INVALID_ARTIFACT_PATH.status()).isEqualTo(400);
    assertThat(ArtifactRefusalCode.NOT_FOUND.status()).isEqualTo(404);
    assertThat(ArtifactRefusalCode.ARTIFACT_TOO_LARGE.status()).isEqualTo(413);
    assertThat(ArtifactRefusalCode.ARTIFACT_NOT_TEXT.status()).isEqualTo(415);
    assertThat(ArtifactRefusalCode.ARTIFACT_SECRET.status()).isEqualTo(422);
    assertThat(ArtifactRefusalCode.ARTIFACT_UNREADABLE.status()).isEqualTo(500);
    assertThat(ArtifactRefusalCode.ARTIFACT_LISTING_UNREADABLE.status()).isEqualTo(500);
    assertThat(ArtifactRefusalCode.ARTIFACT_TOO_LARGE.detail()).isEqualTo("The file is larger than 262144 bytes.");
  }
}
