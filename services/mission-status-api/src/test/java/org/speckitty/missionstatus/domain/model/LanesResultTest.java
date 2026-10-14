package org.speckitty.missionstatus.domain.model;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatNullPointerException;

import java.util.List;
import org.junit.jupiter.api.Test;

class LanesResultTest {

  @Test
  void theThreeVariantsAreDistinctAndASwitchOverThemIsExhaustive() {
    LanesManifest manifest = new LanesManifest("alpha", null, List.of());
    List<LanesResult> results = List.of(new LanesResult.Manifest(manifest), new LanesResult.Corrupt(), new LanesResult.Legacy());
    List<String> names =
        results.stream()
            .map(
                result ->
                    switch (result) {
                      case LanesResult.Manifest m -> "manifest " + m.manifest().missionSlug();
                      case LanesResult.Corrupt c -> "corrupt";
                      case LanesResult.Legacy l -> "legacy";
                    })
            .toList();
    assertThat(names).containsExactly("manifest alpha", "corrupt", "legacy");
    assertThat(new LanesResult.Corrupt()).isEqualTo(new LanesResult.Corrupt()).isNotEqualTo(new LanesResult.Legacy());
    assertThat(new LanesResult.Manifest(manifest)).isEqualTo(new LanesResult.Manifest(manifest));
  }

  @Test
  void aManifestVariantRequiresItsManifest() {
    assertThatNullPointerException().isThrownBy(() -> new LanesResult.Manifest(null));
  }
}
