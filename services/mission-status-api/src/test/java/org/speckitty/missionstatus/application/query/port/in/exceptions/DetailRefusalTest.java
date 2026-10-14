package org.speckitty.missionstatus.application.query.port.in.exceptions;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.List;
import java.util.function.Supplier;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.port.in.exceptions.DetailRefusal.Kind;

/** A refusal carries its kind and nothing else: no text beyond the wire word, no cause, no stack trace. */
class DetailRefusalTest {

  private static final List<Supplier<DetailRefusal>> FACTORIES =
      List.of(
          DetailRefusal::notFound, DetailRefusal::invalidArtifactPath, DetailRefusal::artifactTooLarge, DetailRefusal::artifactNotText,
          DetailRefusal::artifactSecret, DetailRefusal::artifactUnreadable, DetailRefusal::artifactListingUnreadable, DetailRefusal::sourceUnreadable);

  @Test
  void eachFactoryMakesItsKindInTheDeclaredOrder() {
    assertThat(FACTORIES.stream().map(f -> f.get().kind())).containsExactly(Kind.values());
    assertThat(Kind.values()).hasSize(8);
  }

  @Test
  void theMessageIsTheWireWordAndNothingElse() {
    for (Kind kind : Kind.values()) {
      DetailRefusal refusal = new DetailRefusal(kind);

      assertThat(refusal.getMessage()).isEqualTo(kind.wire());
      assertThat(refusal.getCause()).isNull();
      assertThat(refusal.getStackTrace()).as("no stack trace to leak a location").isEmpty();
      assertThat(refusal.getSuppressed()).isEmpty();
    }
  }

  @Test
  void theWireWordsAreTheContractCodes() {
    assertThat(List.of(Kind.values()).stream().map(Kind::wire))
        .containsExactly(
            "not_found", "invalid_artifact_path", "artifact_too_large", "artifact_not_text", "artifact_secret", "artifact_unreadable",
            "artifact_listing_unreadable", "source_unreadable");
  }

  @Test
  void itIsAnUncheckedFinalException() {
    assertThat(RuntimeException.class).isAssignableFrom(DetailRefusal.class);
    assertThat(java.lang.reflect.Modifier.isFinal(DetailRefusal.class.getModifiers())).isTrue();
    assertThatThrownBy(() -> new DetailRefusal(null)).isInstanceOf(NullPointerException.class);
  }
}
