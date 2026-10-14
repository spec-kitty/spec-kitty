package org.speckitty.missionstatus.application.query.artifact;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;

/** J-S3b: Windows drops a trailing dot or space from a file name, so {@code status.json.} opens the root status record. */
class EligibilityWindowsNamesTest {

  @Test
  void onWindowsATrailingDotOrSpaceDoesNotHideARootRecord() {
    for (String alias : new String[] {"status.json.", "status.json ", "STATUS.JSON. .", "status.events.jsonl.", "status.events.jsonl . "}) {
      assertThat(Eligibility.isRootRecord(alias, true)).as(alias).isTrue();
    }
  }

  @Test
  void onOtherPlatformsThoseNamesAreDistinctFilesAsInThePythonOracle() {
    for (String name : new String[] {"status.json.", "status.json ", "status.events.jsonl."}) {
      assertThat(Eligibility.isRootRecord(name, false)).as(name).isFalse();
    }
  }

  @Test
  void theOrdinaryRulesHoldOnBothPlatforms() {
    for (boolean windows : new boolean[] {true, false}) {
      assertThat(Eligibility.isRootRecord("status.json", windows)).isTrue();
      assertThat(Eligibility.isRootRecord("STATUS.events.JSONL", windows)).isTrue();
      assertThat(Eligibility.isRootRecord("spec.md", windows)).isFalse();
      assertThat(Eligibility.isRootRecord("sub/status.json", windows)).isFalse();
    }
  }
}
