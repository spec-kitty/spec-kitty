package org.speckitty.missionstatus.adapter.out.filesystem;

import static org.assertj.core.api.Assertions.assertThat;

import java.io.IOException;
import java.lang.reflect.Method;
import java.nio.file.DirectoryStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.OpenMode;
import org.speckitty.missionstatus.adapter.out.filesystem.Allowlist.PathClass;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;

/** D-92 and PLAN-FRESH2-006: scoped views, the bounded name window, and the pin that no implementation falls through to a default. */
class AllowlistAccessScopedTest {

  private static final String P = "kitty-specs/m-01ABCDEF";

  @TempDir Path root;

  // ---- the pin ------------------------------------------------------------------------------------------------------------

  @Test
  void bothProductionAndRecorderOverrideBothNewMethods() throws NoSuchMethodException {
    for (Class<?> type : List.of(AllowlistPassThrough.class, RecordingAllowlistAccess.class)) {
      Method scoped = type.getDeclaredMethod("scoped", ReadScope.class);
      Method window = type.getDeclaredMethod("listNames", Path.class, int.class);
      assertThat(scoped.isDefault()).as(type.getSimpleName() + ".scoped").isFalse();
      assertThat(window.isDefault()).as(type.getSimpleName() + ".listNames").isFalse();
      assertThat(scoped.getDeclaringClass()).isEqualTo(type);
      assertThat(window.getDeclaringClass()).isEqualTo(type);
    }
  }

  @Test
  void theInterfaceDefaultsExistSoAnExistingDoubleStillCompiles() throws NoSuchMethodException {
    assertThat(AllowlistAccess.class.getMethod("scoped", ReadScope.class).isDefault()).isTrue();
    assertThat(AllowlistAccess.class.getMethod("listNames", Path.class, int.class).isDefault()).isTrue();
  }

  // ---- scoped views --------------------------------------------------------------------------------------------------------

  @Test
  void aScopedViewTagsEveryAccessWithItsScopeAndTheClassOfThatScope() throws IOException {
    Files.createDirectories(root.resolve(P));
    Files.writeString(root.resolve(P).resolve("spec.md"), "x");
    RecordingAllowlistAccess recorder = new RecordingAllowlistAccess(root);
    AllowlistAccess authored = recorder.scoped(ReadScope.AUTHORED);
    AllowlistAccess artifact = recorder.scoped(ReadScope.ARTIFACT);
    authored.stat(root.resolve(P).resolve("spec.md"), false);
    artifact.stat(root.resolve(P).resolve("spec.md"), false);
    artifact.listNames(root.resolve(P));
    recorder.stat(root.resolve(P).resolve("spec.md"), false);
    assertThat(recorder.scopedAccesses())
        .extracting(RecordingAllowlistAccess.ScopedAccess::scope, RecordingAllowlistAccess.ScopedAccess::pathClass, RecordingAllowlistAccess.ScopedAccess::mode)
        .containsExactly(
            org.assertj.core.groups.Tuple.tuple(ReadScope.AUTHORED, PathClass.PLANNING_FILE, OpenMode.STAT),
            org.assertj.core.groups.Tuple.tuple(ReadScope.ARTIFACT, PathClass.ARTIFACT_FILE, OpenMode.STAT),
            org.assertj.core.groups.Tuple.tuple(ReadScope.ARTIFACT, PathClass.ARTIFACT_DIR, OpenMode.LIST),
            org.assertj.core.groups.Tuple.tuple(ReadScope.AUTHORED, PathClass.PLANNING_FILE, OpenMode.STAT));
    assertThat(recorder.violations()).isEmpty();
  }

  @Test
  void theRecorderNotesTheRouteFromItsSupplierWithADashByDefault() throws IOException {
    Files.createDirectories(root.resolve(P));
    RecordingAllowlistAccess recorder = new RecordingAllowlistAccess(root);
    recorder.stat(root.resolve(P), false);
    String[] route = {"getArtifactContent"};
    recorder.routeSupplier(() -> route[0]);
    recorder.stat(root.resolve(P), false);
    route[0] = "listArtifacts";
    recorder.stat(root.resolve(P), false);
    assertThat(recorder.scopedAccesses()).extracting(RecordingAllowlistAccess.ScopedAccess::route).containsExactly("-", "getArtifactContent", "listArtifacts");
  }

  @Test
  void theExistingTripleAccessorsKeepWorkingAndAScopedListNamesIsRecordedOnce() throws IOException {
    Files.createDirectories(root.resolve(P));
    RecordingAllowlistAccess recorder = new RecordingAllowlistAccess(root);
    recorder.scoped(ReadScope.ARTIFACT).listNames(root.resolve(P), 5);
    assertThat(recorder.accesses()).containsExactly(new Allowlist.Access(PathClass.ARTIFACT_DIR, P, OpenMode.LIST));
  }

  @Test
  void theProductionScopedViewIsTheInstanceItself() {
    assertThat(AllowlistAccess.passThrough().scoped(ReadScope.ARTIFACT)).isSameAs(AllowlistAccess.passThrough());
  }

  // ---- bounded listing -----------------------------------------------------------------------------------------------------

  /** A directory stream that counts the names pulled from it. */
  private static DirectoryStream<Path> counting(int entries, AtomicInteger pulled) {
    List<Path> all = new ArrayList<>();
    for (int i = 0; i < entries; i++) {
      all.add(Path.of("n" + i));
    }
    return new DirectoryStream<>() {
      @Override
      public Iterator<Path> iterator() {
        Iterator<Path> inner = all.iterator();
        return new Iterator<>() {
          @Override
          public boolean hasNext() {
            return inner.hasNext();
          }

          @Override
          public Path next() {
            pulled.incrementAndGet();
            return inner.next();
          }
        };
      }

      @Override
      public void close() {}
    };
  }

  @Test
  void aDirectoryOfLimitPlusTwoEntriesPullsAtMostLimitPlusOneNames() throws IOException {
    AtomicInteger pulled = new AtomicInteger();
    AllowlistAccess.NameWindow window = AllowlistPassThrough.window(counting(12, pulled), 10);
    assertThat(pulled.get()).as("names pulled from the stream").isEqualTo(11);
    assertThat(window.names()).hasSize(10);
    assertThat(window.limitReached()).isTrue();
  }

  @Test
  void aDirectoryOfExactlyTheLimitIsNotLimitReached() throws IOException {
    AtomicInteger pulled = new AtomicInteger();
    AllowlistAccess.NameWindow window = AllowlistPassThrough.window(counting(10, pulled), 10);
    assertThat(pulled.get()).isEqualTo(10);
    assertThat(window.names()).hasSize(10);
    assertThat(window.limitReached()).isFalse();
  }

  @Test
  void aSmallerDirectoryAndAZeroLimitBehave() throws IOException {
    assertThat(AllowlistPassThrough.window(counting(3, new AtomicInteger()), 10).names()).containsExactly("n0", "n1", "n2");
    AllowlistAccess.NameWindow zero = AllowlistPassThrough.window(counting(3, new AtomicInteger()), 0);
    assertThat(zero.names()).isEmpty();
    assertThat(zero.limitReached()).isTrue();
  }

  @Test
  void theProductionBoundedListingReadsARealDirectory() throws IOException {
    for (int i = 0; i < 12; i++) {
      Files.writeString(root.resolve("f" + i), "x");
    }
    AllowlistAccess.NameWindow window = AllowlistAccess.passThrough().listNames(root, 5);
    assertThat(window.names()).hasSize(5);
    assertThat(window.limitReached()).isTrue();
  }

  @Test
  void theDefaultBoundedViewTruncatesTheUnboundedListing() throws IOException {
    AllowlistAccess unbounded = new AllowlistAccess() {
      @Override
      public java.nio.channels.SeekableByteChannel openRead(Path path) {
        throw new UnsupportedOperationException();
      }

      @Override
      public java.nio.file.attribute.BasicFileAttributes stat(Path path, boolean followLinks) {
        throw new UnsupportedOperationException();
      }

      @Override
      public Path realPath(Path path) {
        throw new UnsupportedOperationException();
      }

      @Override
      public List<String> listNames(Path dir) {
        return List.of("a", "b", "c", "d");
      }
    };
    AllowlistAccess.NameWindow window = unbounded.listNames(root, 3);
    assertThat(window.names()).containsExactly("a", "b", "c");
    assertThat(window.limitReached()).isTrue();
    assertThat(unbounded.listNames(root, 4).limitReached()).isFalse();
    assertThat(unbounded.scoped(ReadScope.ARTIFACT)).isSameAs(unbounded);
  }
}
