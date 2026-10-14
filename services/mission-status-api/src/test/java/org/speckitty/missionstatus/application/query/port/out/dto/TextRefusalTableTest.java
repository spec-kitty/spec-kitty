package org.speckitty.missionstatus.application.query.port.out.dto;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.Arrays;
import java.util.EnumSet;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.port.out.exceptions.TextFault;
import org.speckitty.missionstatus.domain.redaction.TextScreen;

/**
 * Plan 7.2, the closed set of refusal kinds #5533 imports: the enum names equal the first column of the table, the pure function is
 * total over every outcome that can refuse, and a planted eighth kind is red.
 */
class TextRefusalTableTest {

  /** The first column of the table of plan section 7.2, in order. */
  private static final List<String> TABLE = List.of("NOT_FOUND", "NOT_REGULAR", "PATH_REFUSED", "OVER_CAP", "NOT_TEXT", "SECRET_REFUSED", "IO_FAILURE");

  /** A test-local copy of the enum with one more value: the planted eighth kind. */
  private enum Planted {
    NOT_FOUND,
    NOT_REGULAR,
    PATH_REFUSED,
    OVER_CAP,
    NOT_TEXT,
    SECRET_REFUSED,
    IO_FAILURE,
    EXTRA
  }

  private static List<String> names(Class<? extends Enum<?>> type) {
    return Arrays.stream(type.getEnumConstants()).map(Enum::name).toList();
  }

  @Test
  void theEnumHoldsExactlyTheSevenKindsOfThePlanTableInOrder() {
    assertThat(names(TextRefusal.class)).containsExactlyElementsOf(TABLE);
  }

  @Test
  void aPlantedEighthKindIsRed() {
    assertThat(names(Planted.class)).isNotEqualTo(TABLE);
    assertThat(names(Planted.class)).hasSize(TABLE.size() + 1);
  }

  @Test
  void everyBytesReadOutcomeMapsToItsKindOrToNothing() {
    assertThat(TextRefusals.of(new BytesRead.Bytes(new byte[0]))).isEmpty();
    assertThat(TextRefusals.of(new BytesRead.Absent())).contains(TextRefusal.NOT_FOUND);
    assertThat(TextRefusals.of(new BytesRead.NotRegular())).contains(TextRefusal.NOT_REGULAR);
    assertThat(TextRefusals.of(new BytesRead.OverCap())).contains(TextRefusal.OVER_CAP);
  }

  @Test
  void everyTextReadOutcomeMapsToItsKindOrToNothing() {
    assertThat(TextRefusals.of(new TextRead.Text("x", 1))).isEmpty();
    assertThat(TextRefusals.of(new TextRead.Absent())).contains(TextRefusal.NOT_FOUND);
    assertThat(TextRefusals.of(new TextRead.NotRegular())).contains(TextRefusal.NOT_REGULAR);
    assertThat(TextRefusals.of(new TextRead.OverCap())).contains(TextRefusal.OVER_CAP);
    assertThat(TextRefusals.of(new TextRead.NotText())).contains(TextRefusal.NOT_TEXT);
  }

  @Test
  void everyFaultKindMapsAndOverCapIsNeverAnIoFailure() {
    assertThat(TextRefusals.of(TextFault.Kind.PATH_REFUSED)).isEqualTo(TextRefusal.PATH_REFUSED);
    assertThat(TextRefusals.of(TextFault.Kind.VANISHED)).isEqualTo(TextRefusal.NOT_FOUND);
    assertThat(TextRefusals.of(TextFault.Kind.DIR_UNREADABLE)).isEqualTo(TextRefusal.IO_FAILURE);
    assertThat(TextRefusals.of(TextFault.Kind.FILE_UNREADABLE)).isEqualTo(TextRefusal.IO_FAILURE);
    for (TextFault.Kind kind : TextFault.Kind.values()) {
      assertThat(TextRefusals.of(kind)).as(kind.name()).isNotEqualTo(TextRefusal.OVER_CAP);
    }
  }

  @Test
  void aCredentialIsSecretRefusedAndTheFunctionIsTotalAcrossTheKindsItCanProduce() {
    assertThat(TextRefusals.of(new TextScreen.Screened.SecretFound())).isEqualTo(TextRefusal.SECRET_REFUSED);
    Set<TextRefusal> produced = EnumSet.noneOf(TextRefusal.class);
    for (TextFault.Kind kind : TextFault.Kind.values()) {
      produced.add(TextRefusals.of(kind));
    }
    produced.add(TextRefusals.of(new TextScreen.Screened.SecretFound()));
    for (Optional<TextRefusal> refusal :
        List.of(
            TextRefusals.of(new BytesRead.Absent()),
            TextRefusals.of(new BytesRead.NotRegular()),
            TextRefusals.of(new BytesRead.OverCap()),
            TextRefusals.of(new TextRead.NotText()))) {
      produced.add(refusal.orElseThrow());
    }
    assertThat(produced).containsExactlyInAnyOrder(TextRefusal.values());
  }

  /** The path vocabulary of the port (plan 7.1 row 3): what it refuses and how it moves. */
  @Nested
  class RelativePathCases {

    @Test
    void ofParsesSlashSeparatedSegments() {
      assertThat(RelativePath.of("a/b/c").segments()).containsExactly("a", "b", "c");
      assertThat(RelativePath.of("spec.md").segments()).containsExactly("spec.md");
      assertThat(RelativePath.of("a b/\u00e9").segments()).containsExactly("a b", "\u00e9");
      assertThat(RelativePath.of("a/b").toString()).isEqualTo("a/b");
    }

    @Test
    void ofRefusesAnEmptySegmentADotSegmentABackslashAndANul() {
      for (String bad : List.of("", "/a", "a/", "a//b", ".", "..", "a/./b", "a/../b", "../a", "a\\b", "a\u0000b", "/")) {
        assertThatThrownBy(() -> RelativePath.of(bad)).as(bad.replace("\u0000", "NUL")).isInstanceOf(IllegalArgumentException.class);
      }
    }

    @Test
    void theCanonicalConstructorRefusesWhatOfRefuses() {
      assertThatThrownBy(() -> new RelativePath(List.of("a", ""))).isInstanceOf(IllegalArgumentException.class);
      assertThatThrownBy(() -> new RelativePath(List.of("a/b"))).isInstanceOf(IllegalArgumentException.class);
      assertThatThrownBy(() -> new RelativePath(java.util.Arrays.asList("a", null))).isInstanceOf(NullPointerException.class);
    }

    @Test
    void childParentAndLastMoveAlongThePath() {
      RelativePath path = RelativePath.of("a/b");
      assertThat(path.child("c").segments()).containsExactly("a", "b", "c");
      assertThat(path.parent()).isEqualTo(RelativePath.of("a"));
      assertThat(path.last()).isEqualTo("b");
      assertThat(RelativePath.of("a").parent()).isEqualTo(RelativePath.ROOT);
      assertThatThrownBy(() -> path.child("..")).isInstanceOf(IllegalArgumentException.class);
      assertThatThrownBy(() -> path.child("x/y")).isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void theRootHasNoSegmentsNoParentAndNoLast() {
      assertThat(RelativePath.ROOT.isRoot()).isTrue();
      assertThat(RelativePath.ROOT.segments()).isEmpty();
      assertThat(RelativePath.ROOT.toString()).isEmpty();
      assertThat(RelativePath.of("a").isRoot()).isFalse();
      assertThat(RelativePath.ROOT.child("a")).isEqualTo(RelativePath.of("a"));
      assertThatThrownBy(RelativePath.ROOT::parent).isInstanceOf(IllegalStateException.class);
      assertThatThrownBy(RelativePath.ROOT::last).isInstanceOf(IllegalStateException.class);
    }

    @Test
    void theSegmentsCannotBeChangedThroughTheRecord() {
      java.util.List<String> source = new java.util.ArrayList<>(List.of("a"));
      RelativePath path = new RelativePath(source);
      source.add("b");
      assertThat(path.segments()).containsExactly("a");
      assertThatThrownBy(() -> path.segments().add("c")).isInstanceOf(UnsupportedOperationException.class);
    }
  }

  /** The value types of the port refuse a null where a result needs a value. */
  @Nested
  class ResultCases {

    @Test
    void aFileReferenceNeedsItsParts() {
      assertThatThrownBy(() -> new FileRef.MissionFile(null, RelativePath.ROOT)).isInstanceOf(NullPointerException.class);
      assertThatThrownBy(() -> new FileRef.MissionFile(new MissionRef("m"), null)).isInstanceOf(NullPointerException.class);
      assertThatThrownBy(() -> new FileRef.ProjectFile(null)).isInstanceOf(NullPointerException.class);
      assertThat(new FileRef.ProjectFile(RelativePath.of("a")).path()).isEqualTo(RelativePath.of("a"));
      assertThat(new FileRef.MissionFile(new MissionRef("m"), RelativePath.of("a")).path()).isEqualTo(RelativePath.of("a"));
    }

    @Test
    void namesAreCopiedAndTheResultsRefuseNull() {
      java.util.List<String> source = new java.util.ArrayList<>(List.of("a"));
      DirListing.Names names = new DirListing.Names(source, false, true);
      source.add("b");
      assertThat(names.names()).containsExactly("a");
      assertThatThrownBy(() -> new DirListing.Names(null, false, true)).isInstanceOf(NullPointerException.class);
      assertThatThrownBy(() -> new EntryStat.Present(null, 1, 1)).isInstanceOf(NullPointerException.class);
      assertThatThrownBy(() -> new BytesRead.Bytes(null)).isInstanceOf(NullPointerException.class);
      assertThatThrownBy(() -> new TextRead.Text(null, 1)).isInstanceOf(NullPointerException.class);
    }

    @Test
    void theScopeHasExactlyTheTwoValuesAndEntryKindTheFour() {
      assertThat(Arrays.stream(ReadScope.values()).map(Enum::name).toList()).containsExactly("AUTHORED", "ARTIFACT");
      assertThat(Arrays.stream(EntryStat.EntryKind.values()).map(Enum::name).toList()).containsExactly("FILE", "DIRECTORY", "SYMLINK", "OTHER");
    }
  }
}
