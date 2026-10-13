package org.speckitty.missionstatus.adapter.out.filesystem.codec;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.DynamicTest;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.TestFactory;
import org.speckitty.missionstatus.domain.model.Actor;
import org.speckitty.missionstatus.domain.model.LedgerLine;
import org.speckitty.missionstatus.domain.model.LineKind;
import org.speckitty.missionstatus.domain.model.MalformedReason;

/**
 * The {@code actor} of a lane-transition row against the real oracle ({@link ActorOracleCases}): the served projection
 * {@code Projector.actor}, behind the {@code decode_actor} validity gate. A string, a structured record, the four resolver sentinels and
 * the shapes {@code decode_actor} refuses all get the oracle's answer. The one decided difference is {@link #DIVERGENCES}: the oracle's
 * handle pattern ends in a Python {@code $}, which also matches before a trailing newline; the contract's pattern does not, and the Java
 * follows the contract.
 */
class ActorOracleParityTest {

  /** Case name to the Java answer where it differs from the oracle, on purpose. */
  private static final Map<String, String> DIVERGENCES = Map.of("string-trailing-newline", "||");

  private static final String NONE = "||";

  private static String row(String actorJson) {
    return "{\"actor\":"
        + actorJson
        + ",\"at\":\"2026-02-08T12:00:00+00:00\",\"event_id\":\"01HXYZ0000000000000000000A\",\"evidence\":null,\"execution_mode\":\"worktree\","
        + "\"force\":false,\"from_lane\":\"planned\",\"reason\":null,\"review_ref\":null,\"to_lane\":\"claimed\",\"wp_id\":\"WP01\"}\n";
  }

  private static String verdict(String actorJson) {
    LedgerLine line = LedgerLineDecoder.decodeLine(1, row(actorJson).getBytes(StandardCharsets.UTF_8));
    return switch (line.kind()) {
      case LineKind.Status status -> part(status.event().actor().tool()) + "|" + part(status.event().actor().role()) + "|" + part(status.event().actor().profile());
      case LineKind.Malformed malformed -> malformed.reason() == MalformedReason.UNUSABLE_ROW ? "raise" : "malformed:" + malformed.reason();
      default -> "unexpected:" + line.kind();
    };
  }

  private static String oracle(ActorOracleCases.Case testCase) {
    return testCase.expected();
  }

  private static String expectedJava(ActorOracleCases.Case testCase) {
    return DIVERGENCES.getOrDefault(testCase.name(), oracle(testCase));
  }

  private static String part(String handle) {
    return handle == null ? "" : handle;
  }

  @TestFactory
  List<DynamicTest> everyShapeOfTheActorGetsTheAnswerOfLivePython() {
    return ActorOracleCases.all().stream()
        .map(
            testCase ->
                DynamicTest.dynamicTest(
                    testCase.name(), () -> assertThat(verdict(testCase.actorJson())).as(testCase.name() + " " + testCase.actorJson()).isEqualTo(expectedJava(testCase))))
        .toList();
  }

  @Test
  void everyDivergenceReallyDiffersFromTheOracleSoNoneIsStale() {
    for (ActorOracleCases.Case testCase : ActorOracleCases.all()) {
      String decision = DIVERGENCES.get(testCase.name());
      if (decision != null) {
        assertThat(decision).as(testCase.name()).isNotEqualTo(oracle(testCase));
      }
    }
    assertThat(ActorOracleCases.all().stream().map(ActorOracleCases.Case::name)).containsAll(DIVERGENCES.keySet());
  }

  @Test
  void theTableCoversStringsRecordsAndTheInvalidShapesAndEveryAnswerClassOccurs() {
    List<String> names = ActorOracleCases.all().stream().map(ActorOracleCases.Case::name).toList();
    assertThat(names).doesNotHaveDuplicates();
    for (String prefix : List.of("string-", "structured-", "float", "int", "list-", "sentinel-string-", "sentinel-record-")) {
      assertThat(names).as(prefix).anyMatch(name -> name.startsWith(prefix));
    }
    List<String> answers = ActorOracleCases.all().stream().map(ActorOracleCases.Case::expected).toList();
    assertThat(answers).contains("raise", NONE, "claude||", "claude|implementer|java-jenny", "claude|implementer|", "|implementer|java-jenny");
  }

  @Test
  void aRecordWithTheModelKeyButNoModelHandleIsStillACompleteRecord() {
    assertThat(verdict("{\"role\":\"r\",\"profile\":\"p\",\"tool\":\"t\",\"model\":null}")).isEqualTo("t|r|p");
    assertThat(LedgerLineDecoder.decodeLine(1, row("\"claude\"").getBytes(StandardCharsets.UTF_8)).kind())
        .isInstanceOfSatisfying(LineKind.Status.class, status -> assertThat(status.event().actor()).isEqualTo(new Actor("claude", null, null)));
  }
}
