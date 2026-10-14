package org.speckitty.missionstatus.adapter.out.filesystem.codec;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.domain.model.LineKind;
import org.speckitty.missionstatus.domain.model.StatusEvent;

/**
 * The seed marker and the canonical key of a reconstruction seed (spec-kitty-events 10.4.6: {@code _is_reconstruction_seed},
 * {@code _canonical_key}). Each expected key is the live output of {@code json.dumps(StatusEvent.from_dict(row).to_dict(),
 * sort_keys=True, default=str)} for the row beside it, produced by the installed package.
 */
class SeedKeyTest {

  private static final List<String[]> ROW_AND_PYTHON_KEY =
      List.of(
      new String[] {"{\"actor\": \"migration:backfill_runtime_state\", \"at\": \"2026-09-01T09:00:00Z\", \"event_id\": \"E1\", \"evidence\": null, \"execution_mode\": \"worktree\", \"force\": false, \"from_lane\": \"planned\", \"mission_id\": \"01J05000000000000000000005\", \"mission_slug\": \"s\", \"policy_metadata\": null, \"reason\": null, \"review_ref\": null, \"to_lane\": \"claimed\", \"wp_id\": \"WP01\"}",
          "{\"actor\": \"migration:backfill_runtime_state\", \"at\": \"2026-09-01T09:00:00Z\", \"event_id\": \"E1\", \"evidence\": null, \"execution_mode\": \"worktree\", \"force\": false, \"from_lane\": \"planned\", \"mission_id\": \"01J05000000000000000000005\", \"mission_slug\": \"s\", \"policy_metadata\": null, \"reason\": null, \"review_ref\": null, \"to_lane\": \"claimed\", \"wp_id\": \"WP01\"}"},
      new String[] {"{\"actor\": {\"role\": null, \"profile\": \"p\", \"tool\": \"migration:x\", \"model\": null}, \"at\": \"2026-09-01T09:00:00Z\", \"event_id\": \"E2\", \"evidence\": {\"review\": {\"reviewer\": \"r\", \"verdict\": \"approved\", \"reference\": \"x\", \"extra\": 1}, \"repos\": [{\"repo\": \"a\", \"branch\": \"b\", \"commit\": \"c\", \"files_touched\": [\"f\", \"g\"]}], \"verification\": []}, \"execution_mode\": \"worktree\", \"force\": false, \"from_lane\": \"in_review\", \"feature_slug\": \"legacy\", \"policy_metadata\": {\"z\": 1.5, \"a\": [1e+20, 1e-05, \"\\u00e9\\u0001\\ud83d\\ude00\\u007f\"], \"n\": null, \"t\": true, \"big\": 123456789012345678901234567890, \"neg\": -0.0, \"mid\": 123456.789}, \"reason\": \"r\", \"review_ref\": \"x\", \"review_result\": {\"reviewer\": \"r\", \"verdict\": \"approved\", \"reference\": \"x\", \"feedback_path\": null}, \"to_lane\": \"approved\", \"wp_id\": \"WP01\"}",
          "{\"actor\": {\"model\": null, \"profile\": \"p\", \"role\": null, \"tool\": \"migration:x\"}, \"at\": \"2026-09-01T09:00:00Z\", \"event_id\": \"E2\", \"evidence\": {\"repos\": [{\"branch\": \"b\", \"commit\": \"c\", \"files_touched\": [\"f\", \"g\"], \"repo\": \"a\"}], \"review\": {\"reference\": \"x\", \"reviewer\": \"r\", \"verdict\": \"approved\"}}, \"execution_mode\": \"worktree\", \"force\": false, \"from_lane\": \"in_review\", \"mission_slug\": \"legacy\", \"policy_metadata\": {\"a\": [1e+20, 1e-05, \"\\u00e9\\u0001\\ud83d\\ude00\\u007f\"], \"big\": 123456789012345678901234567890, \"mid\": 123456.789, \"n\": null, \"neg\": -0.0, \"t\": true, \"z\": 1.5}, \"reason\": \"r\", \"review_ref\": \"x\", \"review_result\": {\"reference\": \"x\", \"reviewer\": \"r\", \"verdict\": \"approved\"}, \"to_lane\": \"approved\", \"wp_id\": \"WP01\"}"},
      new String[] {"{\"actor\": {\"role\": \"migration:role\", \"profile\": null, \"tool\": \"\", \"model\": null}, \"at\": \"2026-09-01T09:00:00Z\", \"event_id\": \"E3\", \"evidence\": null, \"execution_mode\": \"worktree\", \"force\": 1, \"from_lane\": \"planned\", \"mission_slug\": \"\", \"feature_slug\": \"fallback\", \"policy_metadata\": {}, \"reason\": null, \"review_ref\": null, \"review_result\": {\"reviewer\": \"r\", \"verdict\": \"changes_requested\", \"reference\": \"feedback://x\", \"feedback_path\": \"/p\"}, \"to_lane\": \"claimed\", \"wp_id\": \"WP01\"}",
          "{\"actor\": {\"model\": null, \"profile\": null, \"role\": \"migration:role\", \"tool\": \"\"}, \"at\": \"2026-09-01T09:00:00Z\", \"event_id\": \"E3\", \"evidence\": null, \"execution_mode\": \"worktree\", \"force\": 1, \"from_lane\": \"planned\", \"mission_slug\": \"fallback\", \"policy_metadata\": {}, \"reason\": null, \"review_ref\": null, \"review_result\": {\"feedback_path\": \"/p\", \"reference\": \"feedback://x\", \"reviewer\": \"r\", \"verdict\": \"changes_requested\"}, \"to_lane\": \"claimed\", \"wp_id\": \"WP01\"}"});

  private static StatusEvent decode(String row) {
    LineKind kind = LedgerLineDecoder.decodeLine(1, (row + "\n").getBytes(StandardCharsets.UTF_8)).kind();
    return ((LineKind.Status) kind).event();
  }

  @Test
  void theKeyEqualsWhatPythonDumpsForTheDecodedRow() {
    for (String[] pair : ROW_AND_PYTHON_KEY) {
      assertThat(decode(pair[0]).seedKey()).isEqualTo(pair[1]);
    }
  }

  @Test
  void aSeedIsAStringActorOrAStructuredToolThenRoleStartingMigration() {
    // E1: a string actor. E2: the tool. E3: an empty tool falls through to the role.
    for (String[] pair : ROW_AND_PYTHON_KEY) {
      assertThat(decode(pair[0]).isSeed()).as(pair[0]).isTrue();
    }
  }

  @Test
  void aRealActorOrAnActorThatOnlyContainsThePrefixIsNotASeed() {
    String base = ROW_AND_PYTHON_KEY.getFirst()[0];
    for (String actor : List.of("\"claude\"", "\"x-migration:y\"", "\"Migration:y\"", "5", "null", "{\"role\":null,\"profile\":null,\"tool\":\"claude\",\"model\":\"migration:m\"}")) {
      StatusEvent event = decode(base.replace("\"migration:backfill_runtime_state\"", actor));
      assertThat(event.isSeed()).as(actor).isFalse();
      assertThat(event.seedKey()).isNull();
    }
  }

  @Test
  void pythonFloatRepr() {
    assertThat(SeedKey.pyFloat(1e20)).isEqualTo("1e+20");
    assertThat(SeedKey.pyFloat(1e-5)).isEqualTo("1e-05");
    assertThat(SeedKey.pyFloat(1.5e-7)).isEqualTo("1.5e-07");
    assertThat(SeedKey.pyFloat(1e16)).isEqualTo("1e+16");
    assertThat(SeedKey.pyFloat(123456789012345.0)).isEqualTo("123456789012345.0");
    assertThat(SeedKey.pyFloat(0.0001)).isEqualTo("0.0001");
    assertThat(SeedKey.pyFloat(-2.5)).isEqualTo("-2.5");
    assertThat(SeedKey.pyFloat(100.0)).isEqualTo("100.0");
  }
}
