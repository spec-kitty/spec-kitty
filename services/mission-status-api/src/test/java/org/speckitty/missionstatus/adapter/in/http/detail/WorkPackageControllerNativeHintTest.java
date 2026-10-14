package org.speckitty.missionstatus.adapter.in.http.detail;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Arrays;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.adapter.in.http.dto.WorkPackage;
import org.speckitty.missionstatus.adapter.in.http.model.HistoryEntry;
import org.speckitty.missionstatus.adapter.in.http.model.Review;
import org.springframework.aot.hint.RuntimeHints;
import org.springframework.aot.hint.predicate.RuntimeHintsPredicates;
import org.springframework.aot.hint.annotation.RegisterReflectionForBinding;
import org.springframework.aot.hint.BindingReflectionHintsRegistrar;

/**
 * The native image needs the reflection hints of the response record (a native binary built without them answered {@code internal_error}:
 * "Record components not available for record class ...WorkPackage"). The controller returns {@code ResponseEntity<?>}, so the AOT
 * processing cannot read the body type from the handler signature, and the controller carries the binding hint instead. This
 * JVM test pins that the annotation is there and that the registrar covers the record and the generated model classes it holds; the proof
 * in the real binary is the manual replay recorded in the hand-off (no native test or smoke stage is added by this route, D-99).
 */
class WorkPackageControllerNativeHintTest {

  @Test
  void theControllerOfTheRouteRegistersTheBindingHintOfTheResponseRecord() {
    RegisterReflectionForBinding hint = WorkPackageController.class.getAnnotation(RegisterReflectionForBinding.class);

    assertThat(hint).as("the controller carries @RegisterReflectionForBinding").isNotNull();
    assertThat(Arrays.asList(hint.value())).containsExactly(WorkPackage.class);
  }

  @Test
  void theRegistrarCoversTheRecordItsComponentsAndTheGeneratedModelClassesItHolds() {
    RuntimeHints hints = new RuntimeHints();

    new BindingReflectionHintsRegistrar().registerReflectionHints(hints.reflection(), WorkPackage.class);

    assertThat(RuntimeHintsPredicates.reflection().onType(WorkPackage.class)).accepts(hints);
    assertThat(RuntimeHintsPredicates.reflection().onType(Review.class)).as("a nested generated class").accepts(hints);
    assertThat(RuntimeHintsPredicates.reflection().onType(HistoryEntry.class)).as("an element type of the history list").accepts(hints);
  }
}
