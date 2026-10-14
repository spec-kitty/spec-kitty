package org.speckitty.missionstatus.architecture;

import static org.assertj.core.api.Assertions.assertThat;

import com.tngtech.archunit.core.domain.JavaClass;
import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import java.io.IOException;
import java.nio.channels.SeekableByteChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.attribute.BasicFileAttributes;
import java.util.ArrayList;
import java.util.List;
import java.util.Set;
import java.util.concurrent.atomic.AtomicInteger;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.io.TempDir;
import org.speckitty.missionstatus.adapter.out.filesystem.AllowlistAccess;
import org.speckitty.missionstatus.adapter.out.filesystem.FilesystemTextSource;
import org.speckitty.missionstatus.adapter.out.filesystem.NameEncoding;
import org.speckitty.missionstatus.application.query.port.out.dto.DirListing;
import org.speckitty.missionstatus.application.query.port.out.dto.FileRef;
import org.speckitty.missionstatus.application.query.port.out.dto.MissionRef;
import org.speckitty.missionstatus.application.query.port.out.dto.ReadScope;
import org.speckitty.missionstatus.application.query.port.out.dto.RelativePath;

/**
 * D-92 and AC-4.9: {@code FilesystemTextSource} lists only through the bounded {@code listNames(Path, int)}; a call of the unbounded
 * {@code listNames(Path)} from it is red, and a directory of {@code limit + 2} entries is asked for at most {@code limit} names.
 */
class NoUnboundedListingTest {

  private static final JavaClasses MAIN = ArchitectureRules.mainClasses();
  private static final String FILESYSTEM = "org.speckitty.missionstatus.adapter.out.filesystem.";
  private static final Set<String> SUBJECTS = Set.of(FILESYSTEM + "FilesystemTextSource");

  /** A planted violation: a text-source-shaped class that lists a directory without a bound. */
  static final class PlantedUnboundedLister {
    List<String> list(AllowlistAccess access, Path dir) throws IOException {
      return access.listNames(dir);
    }
  }

  /** The subject classes that call the one-argument {@code listNames}. */
  static List<String> unboundedCallers(JavaClasses classes, Set<String> subjects) {
    return classes.stream()
        .filter(c -> subjects.stream().anyMatch(name -> c.getName().equals(name) || c.getName().startsWith(name + "$")))
        .filter(c -> c.getMethodCallsFromSelf().stream().anyMatch(call -> call.getTarget().getName().equals("listNames") && call.getTarget().getRawParameterTypes().size() == 1))
        .map(JavaClass::getName)
        .toList();
  }

  @Test
  void theTextSourceNeverCallsTheUnboundedListing() {
    assertThat(MAIN.contain(FILESYSTEM + "FilesystemTextSource")).isTrue();
    assertThat(unboundedCallers(MAIN, SUBJECTS)).isEmpty();
    JavaClass source = MAIN.get(FILESYSTEM + "FilesystemTextSource");
    assertThat(source.getMethodCallsFromSelf().stream().filter(call -> call.getTarget().getName().equals("listNames") && call.getTarget().getRawParameterTypes().size() == 2))
        .as("the bounded call is there: the guard is not vacuous")
        .isNotEmpty();
  }

  @Test
  void aPlantedUnboundedCallFromASubjectClassIsRed() {
    JavaClasses planted = new ClassFileImporter().importClasses(PlantedUnboundedLister.class);
    assertThat(unboundedCallers(planted, Set.of(PlantedUnboundedLister.class.getName()))).containsExactly(PlantedUnboundedLister.class.getName());
    assertThat(unboundedCallers(planted, SUBJECTS)).as("the guard names its subjects").isEmpty();
  }

  /** An access that records which listing method was asked for and with what limit. */
  private static final class Counting implements AllowlistAccess {
    final AllowlistAccess real = AllowlistAccess.passThrough();
    final AtomicInteger unbounded = new AtomicInteger();
    final List<Integer> limits = new ArrayList<>();

    @Override
    public SeekableByteChannel openRead(Path path) throws IOException {
      return real.openRead(path);
    }

    @Override
    public BasicFileAttributes stat(Path path, boolean followLinks) throws IOException {
      return real.stat(path, followLinks);
    }

    @Override
    public Path realPath(Path path) throws IOException {
      return real.realPath(path);
    }

    @Override
    public List<String> listNames(Path dir) throws IOException {
      unbounded.incrementAndGet();
      return real.listNames(dir);
    }

    @Override
    public NameWindow listNames(Path dir, int limit) throws IOException {
      limits.add(limit);
      return real.listNames(dir, limit);
    }
  }

  @Test
  void aDirectoryOfLimitPlusTwoEntriesIsAskedForTheBoundedWindowOnly(@TempDir Path sandbox) throws IOException {
    Path root = Files.createDirectory(sandbox.resolve("project"));
    Path primary = Files.createDirectories(root.resolve("kitty-specs").resolve("m-01ABCDEF"));
    int limit = 7;
    for (int i = 0; i < limit + 2; i++) {
      Files.writeString(primary.resolve("f" + i), "x");
    }
    Counting counting = new Counting();
    DirListing.Names names =
        (DirListing.Names) new FilesystemTextSource(root, counting, NameEncoding.fixed(true)).list(new FileRef.MissionFile(new MissionRef("m-01ABCDEF"), RelativePath.ROOT), limit, ReadScope.ARTIFACT);
    assertThat(names.names()).hasSize(limit);
    assertThat(names.limitReached()).isTrue();
    assertThat(counting.unbounded.get()).as("the unbounded listing is never called").isZero();
    assertThat(counting.limits).containsExactly(limit);
  }
}
