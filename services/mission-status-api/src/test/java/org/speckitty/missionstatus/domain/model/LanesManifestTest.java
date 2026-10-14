package org.speckitty.missionstatus.domain.model;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatNullPointerException;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;

class LanesManifestTest {

  private static final LanesManifest.Lane A = new LanesManifest.Lane("lane-a", List.of("WP01", "WP02"));
  private static final LanesManifest.Lane B = new LanesManifest.Lane("lane-b", List.of("WP02", "WP03"));

  @Test
  void theFirstLaneThatHoldsTheWorkPackageIsReturned() {
    LanesManifest manifest = new LanesManifest("alpha", "id", List.of(A, B));
    assertThat(manifest.laneFor("WP02")).contains(A);
    assertThat(manifest.laneFor("WP03")).contains(B);
    assertThat(manifest.laneFor("WP99")).isEmpty();
  }

  @Test
  void theListsAreCopiedAndTheRequiredMembersChecked() {
    List<String> ids = new ArrayList<>(List.of("WP01"));
    LanesManifest.Lane lane = new LanesManifest.Lane("lane-a", ids);
    ids.add("WP09");
    assertThat(lane.wpIds()).containsExactly("WP01");
    List<LanesManifest.Lane> lanes = new ArrayList<>(List.of(lane));
    LanesManifest manifest = new LanesManifest("alpha", null, lanes);
    lanes.clear();
    assertThat(manifest.lanes()).hasSize(1);
    assertThat(manifest.missionId()).isNull();
    assertThatThrownBy(() -> manifest.lanes().add(B)).isInstanceOf(UnsupportedOperationException.class);
    assertThatNullPointerException().isThrownBy(() -> new LanesManifest(null, null, List.of()));
    assertThatNullPointerException().isThrownBy(() -> new LanesManifest.Lane(null, List.of()));
  }
}
