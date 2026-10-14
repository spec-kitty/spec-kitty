package org.speckitty.missionstatus.adapter.out.filesystem.codec;

import static org.assertj.core.api.Assertions.assertThat;

import java.nio.charset.StandardCharsets;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.domain.model.LanesManifest;
import org.speckitty.missionstatus.domain.model.LanesResult;
import tools.jackson.databind.json.JsonMapper;

/** FR-003, AC-3.5 and row W3 at the codec: a current manifest, the legacy shape (SK-351), and every way a file is corrupt. */
class LanesCodecTest {

  private static final JsonMapper JSON = JsonMapper.builder().build();

  private static final String CURRENT =
      """
      {"version": 1, "mission_slug": "alpha-mission", "mission_id": "00000000000000000000000001", "mission_branch": "kitty/mission-alpha-mission",
       "target_branch": "main", "computed_at": "2026-09-01T10:00:00+00:00", "computed_from": "fixture",
       "lanes": [{"lane_id": "lane-a", "wp_ids": ["WP01", "WP02"], "write_scope": [], "predicted_surfaces": [], "depends_on_lanes": [], "parallel_group": 0},
                 {"lane_id": "lane-b", "wp_ids": ["WP03"]}]}
      """;

  private static LanesResult decode(String json) {
    return LanesCodec.decode(json.getBytes(StandardCharsets.UTF_8));
  }

  private static LanesManifest manifest(String json) {
    LanesResult result = decode(json);
    assertThat(result).isInstanceOf(LanesResult.Manifest.class);
    return ((LanesResult.Manifest) result).manifest();
  }

  @Test
  void aCurrentManifestKeepsTheSlugTheIdAndTheLanesInOrder() {
    LanesManifest manifest = manifest(CURRENT);
    assertThat(manifest.missionSlug()).isEqualTo("alpha-mission");
    assertThat(manifest.missionId()).isEqualTo("00000000000000000000000001");
    assertThat(manifest.lanes()).extracting(LanesManifest.Lane::laneId).containsExactly("lane-a", "lane-b");
    assertThat(manifest.lanes().get(0).wpIds()).containsExactly("WP01", "WP02");
    assertThat(manifest.laneFor("WP03")).map(LanesManifest.Lane::laneId).contains("lane-b");
    assertThat(manifest.laneFor("WP09")).isEmpty();
  }

  @Test
  void aMissionIdThatIsNotAStringOrIsAbsentIsNull() {
    assertThat(manifest(CURRENT.replace("\"mission_id\": \"00000000000000000000000001\"", "\"mission_id\": null")).missionId()).isNull();
    assertThat(manifest(CURRENT.replace("\"mission_id\": \"00000000000000000000000001\", ", "")).missionId()).isNull();
    assertThat(manifest(CURRENT.replace("\"00000000000000000000000001\"", "7")).missionId()).isNull();
  }

  @Test
  void theLegacyShapeIsItsOwnResultAndNotAManifest() {
    String legacy = CURRENT.replace("mission_slug", "feature_slug");
    assertThat(decode(legacy)).isInstanceOf(LanesResult.Legacy.class);
    assertThat(decode("{\"feature_slug\": \"x\"}")).as("the check is on the missing mission_slug, before the other keys").isInstanceOf(LanesResult.Legacy.class);
    assertThat(decode(CURRENT.replace("mission_slug", "other_slug"))).as("neither slug").isInstanceOf(LanesResult.Corrupt.class);
  }

  @Test
  void bothSlugsPresentIsReadAsTheCurrentShape() {
    assertThat(decode(CURRENT.replace("\"version\": 1,", "\"version\": 1, \"feature_slug\": \"old\","))).isInstanceOf(LanesResult.Manifest.class);
  }

  @Test
  void documentsThatAreNotJsonObjectsAreCorrupt() {
    for (String text : new String[] {"", "not json", "[]", "\"x\"", "5", "null", "{", CURRENT + "x", "{'a': 1}", "{\"a\": 01}"}) {
      assertThat(decode(text)).as(text).isInstanceOf(LanesResult.Corrupt.class);
    }
  }

  @Test
  void aByteOrderMarkAndBytesThatAreNotUtf8AreCorrupt() {
    assertThat(LanesCodec.decode(("\ufeff" + CURRENT).getBytes(StandardCharsets.UTF_8))).isInstanceOf(LanesResult.Corrupt.class);
    byte[] valid = CURRENT.getBytes(StandardCharsets.UTF_8);
    byte[] broken = new byte[valid.length + 1];
    System.arraycopy(valid, 0, broken, 0, valid.length);
    broken[valid.length] = (byte) 0xC3;
    assertThat(LanesCodec.decode(broken)).isInstanceOf(LanesResult.Corrupt.class);
  }

  @Test
  @SuppressWarnings("unchecked")
  void aMissingRequiredKeyIsCorrupt() {
    for (String key : new String[] {"version", "mission_branch", "target_branch", "computed_at", "computed_from", "lanes"}) {
      Map<String, Object> document = (Map<String, Object>) PythonJson.parse(CURRENT);
      assertThat(document.remove(key)).as("the key was present").isNotNull();
      assertThat(decode(JSON.writeValueAsString(document))).as("without " + key).isInstanceOf(LanesResult.Corrupt.class);
    }
  }

  @Test
  void aSlugThatIsNotAStringAndLanesThatAreNotAListAreCorrupt() {
    assertThat(decode(CURRENT.replace("\"alpha-mission\"", "5"))).isInstanceOf(LanesResult.Corrupt.class);
    assertThat(decode(CURRENT.replaceAll("(?s)\"lanes\": \\[.*\\]\\}", "\"lanes\": {\"a\": 1}}"))).isInstanceOf(LanesResult.Corrupt.class);
    assertThat(manifest(CURRENT.replaceAll("(?s)\"lanes\": \\[.*\\]\\}", "\"lanes\": {}}")).lanes()).as("iterating an empty mapping yields no lane").isEmpty();
    assertThat(decode(CURRENT.replaceAll("(?s)\"lanes\": \\[.*\\]\\}", "\"lanes\": 5}"))).isInstanceOf(LanesResult.Corrupt.class);
    assertThat(decode(CURRENT.replaceAll("(?s)\"lanes\": \\[.*\\]\\}", "\"lanes\": []}"))).as("no lanes is a manifest").isInstanceOf(LanesResult.Manifest.class);
  }

  @Test
  void aLaneMustBeAMappingWithAStringIdAndAListOfStringIds() {
    assertThat(decode(CURRENT.replace("{\"lane_id\": \"lane-b\", \"wp_ids\": [\"WP03\"]}", "\"lane-b\""))).isInstanceOf(LanesResult.Corrupt.class);
    assertThat(decode(CURRENT.replace("\"lane_id\": \"lane-b\", ", ""))).isInstanceOf(LanesResult.Corrupt.class);
    assertThat(decode(CURRENT.replace("\"lane_id\": \"lane-b\"", "\"lane_id\": 2"))).isInstanceOf(LanesResult.Corrupt.class);
    assertThat(decode(CURRENT.replace("\"wp_ids\": [\"WP03\"]", "\"wp_ids\": \"WP03\""))).as("a string would be split into characters by the oracle").isInstanceOf(LanesResult.Corrupt.class);
    assertThat(decode(CURRENT.replace("\"wp_ids\": [\"WP03\"]", "\"wp_ids\": [3]"))).isInstanceOf(LanesResult.Corrupt.class);
    assertThat(decode(CURRENT.replace("\"lane_id\": \"lane-b\", \"wp_ids\": [\"WP03\"]", "\"lane_id\": \"lane-b\""))).isInstanceOf(LanesResult.Corrupt.class);
  }

  @Test
  void theOptionalLaneMembersMustBeIterableAsTheOraclesTupleCallDemands() {
    assertThat(decode(CURRENT.replace("\"write_scope\": []", "\"write_scope\": 5"))).isInstanceOf(LanesResult.Corrupt.class);
    assertThat(decode(CURRENT.replace("\"predicted_surfaces\": []", "\"predicted_surfaces\": null"))).isInstanceOf(LanesResult.Corrupt.class);
    assertThat(decode(CURRENT.replace("\"depends_on_lanes\": []", "\"depends_on_lanes\": true"))).isInstanceOf(LanesResult.Corrupt.class);
    assertThat(decode(CURRENT.replace("\"write_scope\": []", "\"write_scope\": \"a\""))).isInstanceOf(LanesResult.Manifest.class);
    assertThat(decode(CURRENT.replace("\"write_scope\": []", "\"write_scope\": {\"a\": 1}"))).isInstanceOf(LanesResult.Manifest.class);
  }

  @Test
  void aCollapseReportIsReadByTheOracleAndAMalformedOneIsCorrupt() {
    String ok = CURRENT.replace("\"version\": 1,", "\"version\": 1, \"collapse_report\": {\"events\": [{\"wp_a\": \"a\", \"wp_b\": \"b\", \"rule\": \"r\", \"evidence\": \"e\"}]},");
    assertThat(decode(ok)).isInstanceOf(LanesResult.Manifest.class);
    assertThat(decode(CURRENT.replace("\"version\": 1,", "\"version\": 1, \"collapse_report\": {},"))).isInstanceOf(LanesResult.Manifest.class);
    assertThat(decode(CURRENT.replace("\"version\": 1,", "\"version\": 1, \"collapse_report\": null,"))).isInstanceOf(LanesResult.Corrupt.class);
    assertThat(decode(CURRENT.replace("\"version\": 1,", "\"version\": 1, \"collapse_report\": {\"events\": 5},"))).isInstanceOf(LanesResult.Corrupt.class);
    assertThat(decode(CURRENT.replace("\"version\": 1,", "\"version\": 1, \"collapse_report\": {\"events\": [5]},"))).isInstanceOf(LanesResult.Corrupt.class);
    assertThat(decode(CURRENT.replace("\"version\": 1,", "\"version\": 1, \"collapse_report\": {\"events\": [{\"wp_a\": \"a\"}]},"))).isInstanceOf(LanesResult.Corrupt.class);
  }

  @Test
  void duplicateKeysTakeTheLastValueAsPythonsJsonDoes() {
    assertThat(manifest(CURRENT.replace("\"mission_slug\": \"alpha-mission\",", "\"mission_slug\": \"first\", \"mission_slug\": \"alpha-mission\",")).missionSlug())
        .isEqualTo("alpha-mission");
  }
}
