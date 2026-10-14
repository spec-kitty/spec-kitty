package org.speckitty.missionstatus.application.query.artifact;

import static org.assertj.core.api.Assertions.assertThat;

import java.lang.reflect.Field;
import java.lang.reflect.Modifier;
import java.util.Arrays;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.domain.readmodel.derive.ArtifactPaths;
import org.speckitty.missionstatus.domain.readmodel.detail.ArtifactListing;

/** The numbers of the artifact routes, pinned against the contract's rule and against the types that carry the same bound. */
class ArtifactLimitsTest {

  @Test
  void theConstantsStateTheRuleOfTheRoutes() {
    assertThat(ArtifactLimits.LISTING_ENTRIES).isEqualTo(1000);
    assertThat(ArtifactLimits.COLLECTOR_ENTRIES).isEqualTo(1001);
    assertThat(ArtifactLimits.PATH_CHARACTERS).isEqualTo(512);
    assertThat(ArtifactLimits.WALK_NAMES).isEqualTo(100_000);
    assertThat(ArtifactLimits.CONTENT_CAP_BYTES).isEqualTo(262_144);
    assertThat(ArtifactLimits.READ_REQUEST_BYTES).isEqualTo(262_145);
  }

  @Test
  void theBoundsAgreeWithTheTypesThatCarryThem() {
    assertThat(ArtifactLimits.LISTING_ENTRIES).isEqualTo(ArtifactListing.MAX_ENTRIES);
    assertThat(ArtifactLimits.PATH_CHARACTERS).isEqualTo(ArtifactPaths.MAX_LENGTH);
    assertThat(ArtifactLimits.COLLECTOR_ENTRIES).isEqualTo(ArtifactLimits.LISTING_ENTRIES + 1);
    assertThat(ArtifactLimits.READ_REQUEST_BYTES).isEqualTo(ArtifactLimits.CONTENT_CAP_BYTES + 1);
  }

  /** The declared fields; the coverage agent adds a synthetic one, which is not part of the class. */
  private static java.util.stream.Stream<Field> declaredFields() {
    return Arrays.stream(ArtifactLimits.class.getDeclaredFields()).filter(field -> !field.isSynthetic());
  }

  @Test
  void theClassHoldsConstantsAndNothingElse() {
    assertThat(declaredFields()).allSatisfy(field -> {
      int modifiers = field.getModifiers();
      assertThat(Modifier.isPublic(modifiers) && Modifier.isStatic(modifiers) && Modifier.isFinal(modifiers)).as(field.getName()).isTrue();
      assertThat(field.getType()).isEqualTo(int.class);
    });
    assertThat(Arrays.stream(ArtifactLimits.class.getDeclaredMethods()).filter(method -> !method.isSynthetic())).isEmpty();
    assertThat(ArtifactLimits.class.getDeclaredConstructors()).allSatisfy(constructor -> assertThat(Modifier.isPrivate(constructor.getModifiers())).isTrue());
    assertThat(declaredFields().map(Field::getName)).hasSize(6);
  }
}
