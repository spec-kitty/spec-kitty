package org.speckitty.missionstatus.application.query.artifact;

import static org.assertj.core.api.Assertions.assertThat;

import java.lang.invoke.MethodHandles;
import java.lang.invoke.MethodType;
import java.lang.reflect.Method;
import java.lang.reflect.Modifier;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.port.out.dto.EntryStat;
import org.speckitty.missionstatus.application.query.port.out.dto.EntryStat.EntryKind;

/** The eligibility rule over strings and {@code EntryStat} values the caller passes: no I/O, no path type. */
class EligibilityTest {

  private static EntryStat file() {
    return new EntryStat.Present(EntryKind.FILE, 10, 1L);
  }

  private static EntryStat directory() {
    return new EntryStat.Present(EntryKind.DIRECTORY, 0, 1L);
  }

  @Test
  void theClassAndEveryMethodTheLaterPackagesCallArePublic() throws Exception {
    assertThat(Modifier.isPublic(Eligibility.class.getModifiers())).isTrue();
    assertThat(Modifier.isFinal(Eligibility.class.getModifiers())).isTrue();
    for (Method method : Eligibility.class.getDeclaredMethods()) {
      if (!method.isSynthetic() && !Modifier.isPrivate(method.getModifiers())) {
        assertThat(Modifier.isPublic(method.getModifiers())).as(method.getName()).isTrue();
      }
    }
    // publicLookup resolves only what a class in any other package may call.
    assertThat(MethodHandles.publicLookup().findStatic(Eligibility.class, "isEligiblePath", MethodType.methodType(boolean.class, String.class))).isNotNull();
    assertThat(MethodHandles.publicLookup().findStatic(Eligibility.class, "isEligibleName", MethodType.methodType(boolean.class, String.class))).isNotNull();
    assertThat(MethodHandles.publicLookup().findStatic(Eligibility.class, "isRootRecord", MethodType.methodType(boolean.class, String.class))).isNotNull();
    assertThat(MethodHandles.publicLookup().findStatic(Eligibility.class, "isEligible", MethodType.methodType(boolean.class, String.class, EntryStat.class, List.class))).isNotNull();
  }

  @Test
  void theRootStatusRecordsAreNeverEligibleInAnyCaseAtTheRootOnly() {
    for (String record : List.of("status.json", "Status.JSON", "STATUS.JSON", "status.events.jsonl", "Status.Events.JSONL")) {
      assertThat(Eligibility.isRootRecord(record)).as(record).isTrue();
      assertThat(Eligibility.isEligiblePath(record)).as(record).isFalse();
    }
    for (String nested : List.of("a/status.json", "sub/status.events.jsonl", "status.json.bak", "status.events.jsonl2")) {
      assertThat(Eligibility.isRootRecord(nested)).as(nested).isFalse();
      assertThat(Eligibility.isEligiblePath(nested)).as(nested).isTrue();
    }
  }

  @Test
  void aPathIsEligibleOnlyWhenTheArtifactPathRuleAcceptsIt() {
    assertThat(Eligibility.isEligiblePath("spec.md")).isTrue();
    assertThat(Eligibility.isEligiblePath("tasks/WP01-x.md")).isTrue();
    assertThat(Eligibility.isEligiblePath("a\\b.md")).as("a backslash").isFalse();
    assertThat(Eligibility.isEligiblePath("a".repeat(513))).isFalse();
    assertThat(Eligibility.isEligiblePath("")).isFalse();
    assertThat(Eligibility.isEligiblePath("tasks/../x")).isFalse();
  }

  @Test
  void aNameHoldingTheReplacementCharacterOrABackslashIsIneligible() {
    assertThat(Eligibility.isEligibleName("WP01-\ufffd.md")).isFalse();
    assertThat(Eligibility.isEligibleName(".md\\")).isFalse();
    assertThat(Eligibility.isEligibleName("a".repeat(513))).as("513 characters").isFalse();
    assertThat(Eligibility.isEligibleName("WP01-\u00e9.md")).isTrue();
    assertThat(Eligibility.isEligibleName("notes.md")).isTrue();
    assertThat(Eligibility.isEligibleName("a/b")).as("a name is one segment").isFalse();
    assertThat(Eligibility.isEligibleName("")).isFalse();
    assertThat(Eligibility.isEligibleName("..")).isFalse();
  }

  @Test
  void aRegularFileUnderRealDirectoriesIsEligible() {
    assertThat(Eligibility.isEligible("tasks/x.md", file(), List.of(directory()))).isTrue();
    assertThat(Eligibility.isEligible("spec.md", file(), List.of())).isTrue();
  }

  @Test
  void aDirectoryALinkAnOtherEntryAndAnAbsentEntryAreNotFiles() {
    for (EntryStat leaf :
        List.of(
            directory(),
            new EntryStat.Present(EntryKind.SYMLINK, 1, 1L),
            new EntryStat.Present(EntryKind.OTHER, 1, 1L),
            new EntryStat.Absent())) {
      assertThat(Eligibility.isEligible("a.md", leaf, List.of())).as(leaf.toString()).isFalse();
    }
  }

  @Test
  void aLinkOrAFileOrAnAbsentEntryAmongTheComponentsMakesItIneligible() {
    for (EntryStat bad : List.of(new EntryStat.Present(EntryKind.SYMLINK, 1, 1L), file(), new EntryStat.Absent(), new EntryStat.Present(EntryKind.OTHER, 1, 1L))) {
      assertThat(Eligibility.isEligible("d/e/a.md", file(), List.of(directory(), bad))).as(bad.toString()).isFalse();
    }
  }

  @Test
  void aRootRecordOrAnInvalidPathIsNotEligibleWhateverTheStats() {
    assertThat(Eligibility.isEligible("status.json", file(), List.of())).isFalse();
    assertThat(Eligibility.isEligible("a\\b", file(), List.of())).isFalse();
    assertThat(Eligibility.isEligible("sub/status.json", file(), List.of(directory()))).isTrue();
  }

  @Test
  void theNumberOfComponentStatsMustMatchThePath() {
    assertThat(Eligibility.isEligible("d/e/a.md", file(), List.of(directory()))).as("one directory stat missing").isFalse();
    assertThat(Eligibility.isEligible("a.md", file(), List.of(directory()))).as("one directory stat too many").isFalse();
  }
}
