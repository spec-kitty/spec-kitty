package org.speckitty.missionstatus.architecture;

import static org.assertj.core.api.Assertions.assertThat;

import com.tngtech.archunit.core.domain.JavaClass;
import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.domain.JavaMethod;
import com.tngtech.archunit.core.domain.JavaModifier;
import com.tngtech.archunit.core.importer.ClassFileImporter;
import java.nio.channels.SeekableByteChannel;
import java.nio.file.Path;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;
import org.junit.jupiter.api.Test;

/**
 * Pre-merge fold J2: there is no uncapped read helper. The only whole-file reads, {@code SafeFiles.readRegular} and
 * {@code SafeFiles.readCapped}, take a required {@code int} cap; the helper that opened a channel for a caller to drain is private; and
 * only {@code SafeFiles}, the ledger (which checks its own cap on the stat and again while reading) and the allowlist access seam it reads
 * through ({@code AllowlistAccess} and its pass-through implementation) open a file for reading at all. The guards are functions over a
 * set of classes, so a planted violation shows each one red.
 */
class NoUncappedReadTest {

  private static final JavaClasses MAIN = ArchitectureRules.mainClasses();
  private static final String FILESYSTEM = "org.speckitty.missionstatus.adapter.out.filesystem.";
  private static final Set<String> MAY_OPEN_FOR_READ = Set.of(FILESYSTEM + "SafeFiles", FILESYSTEM + "FilesystemMissionEventSourceLedger", FILESYSTEM + "AllowlistPassThrough", FILESYSTEM + "AllowlistAccess");

  /** A planted violation: a class outside {@code SafeFiles} that opens a file for reading. */
  static final class PlantedOpener {
    java.nio.channels.SeekableByteChannel open(org.speckitty.missionstatus.adapter.out.filesystem.AllowlistAccess access, Path file) throws java.io.IOException {
      return access.openRead(file);
    }
  }

  /** A planted violation: a whole-file read helper that takes no cap. */
  static final class PlantedUncappedReader {
    public byte[] readAll(Path file) {
      return new byte[0];
    }

    public byte[] readCapped(Path file) {
      return new byte[0];
    }
  }

  private static final String[] CAPPED_READERS = {"readRegular", "readCapped"};

  /** Public or package-visible methods named {@code read...} of {@code type} that take no {@code int} cap. */
  static List<String> readsWithoutACap(JavaClass type) {
    return type.getMethods().stream()
        .filter(method -> !method.getModifiers().contains(JavaModifier.PRIVATE))
        .filter(method -> method.getName().startsWith("read"))
        .filter(method -> method.getRawParameterTypes().stream().noneMatch(parameter -> parameter.getName().equals("int")))
        .map(JavaMethod::getFullName)
        .collect(Collectors.toList());
  }

  /** The classes of {@code classes} that call {@code openRead} and are not allowed to. */
  static List<String> openersOutside(JavaClasses classes, Set<String> allowed) {
    return classes.stream()
        .filter(c -> allowed.stream().noneMatch(name -> c.getName().equals(name) || c.getName().startsWith(name + "$")))
        .filter(c -> c.getMethodCallsFromSelf().stream().anyMatch(call -> call.getTarget().getName().equals("openRead")))
        .map(JavaClass::getName)
        .toList();
  }

  @Test
  void everyReadRegularAndReadCappedTakesAnIntCap() {
    for (String name : CAPPED_READERS) {
      List<JavaMethod> reads = MAIN.get(FILESYSTEM + "SafeFiles").getMethods().stream().filter(method -> method.getName().equals(name)).toList();
      assertThat(reads).as(name + " overloads").isNotEmpty();
      for (JavaMethod read : reads) {
        assertThat(read.getRawParameterTypes().stream().map(JavaClass::getName)).as("parameters of " + read.getFullName()).contains("int");
      }
    }
  }

  @Test
  void noReadHelperOfSafeFilesLacksACap() {
    assertThat(readsWithoutACap(MAIN.get(FILESYSTEM + "SafeFiles"))).as("read methods of SafeFiles without an int cap").isEmpty();
  }

  @Test
  void aPlantedReaderWithoutACapIsRed() {
    JavaClasses planted = new ClassFileImporter().importClasses(PlantedUncappedReader.class);
    assertThat(readsWithoutACap(planted.get(PlantedUncappedReader.class.getName()))).containsExactlyInAnyOrder(
        PlantedUncappedReader.class.getName() + ".readAll(" + Path.class.getName() + ")",
        PlantedUncappedReader.class.getName() + ".readCapped(" + Path.class.getName() + ")");
  }

  @Test
  void noUncappedChannelOpeningHelperIsVisibleOutsideSafeFiles() {
    List<String> leaking =
        MAIN.get(FILESYSTEM + "SafeFiles").getMethods().stream()
            .filter(method -> !method.getModifiers().contains(JavaModifier.PRIVATE))
            .filter(method -> method.getRawReturnType().isAssignableTo(SeekableByteChannel.class) || method.getRawReturnType().getName().equals("java.util.Optional") && method.getName().startsWith("open"))
            .map(JavaMethod::getFullName)
            .collect(Collectors.toList());
    assertThat(leaking).as("non-private methods of SafeFiles that hand out an open channel").isEmpty();
  }

  @Test
  void onlySafeFilesAndTheLedgerOpenAFileForReading() {
    assertThat(openersOutside(MAIN, MAY_OPEN_FOR_READ)).as("classes that call openRead").isEmpty();
  }

  @Test
  void theTextSourceReadsOnlyThroughSafeFiles() {
    JavaClass source = MAIN.get(FILESYSTEM + "FilesystemTextSource");
    assertThat(source.getMethodCallsFromSelf().stream().filter(call -> call.getTarget().getName().equals("openRead"))).isEmpty();
    assertThat(source.getMethodCallsFromSelf().stream().filter(call -> call.getTargetOwner().getName().equals(FILESYSTEM + "SafeFiles")).map(call -> call.getTarget().getName()))
        .contains("readCapped");
  }

  @Test
  void aPlantedOpenerOutsideSafeFilesIsRed() {
    JavaClasses planted = new ClassFileImporter().importClasses(PlantedOpener.class);
    assertThat(openersOutside(planted, MAY_OPEN_FOR_READ)).containsExactly(PlantedOpener.class.getName());
  }
}
