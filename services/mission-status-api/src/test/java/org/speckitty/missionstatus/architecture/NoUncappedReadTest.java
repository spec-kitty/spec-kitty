package org.speckitty.missionstatus.architecture;

import static org.assertj.core.api.Assertions.assertThat;

import com.tngtech.archunit.core.domain.JavaClass;
import com.tngtech.archunit.core.domain.JavaClasses;
import com.tngtech.archunit.core.domain.JavaMethod;
import com.tngtech.archunit.core.domain.JavaModifier;
import java.nio.channels.SeekableByteChannel;
import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;
import org.junit.jupiter.api.Test;

/**
 * Pre-merge fold J2: there is no uncapped read helper. The only whole-file read, {@code SafeFiles.readRegular}, takes a required
 * {@code int} cap; the helper that opened a channel for a caller to drain is private; and only {@code SafeFiles}, the ledger (which
 * checks its own cap on the stat and again while reading) and the allowlist access seam it reads through ({@code AllowlistAccess} and
 * its pass-through implementation) open a file for reading at all.
 */
class NoUncappedReadTest {

  private static final JavaClasses MAIN = ArchitectureRules.mainClasses();
  private static final String FILESYSTEM = "org.speckitty.missionstatus.adapter.out.filesystem.";
  private static final Set<String> MAY_OPEN_FOR_READ = Set.of(FILESYSTEM + "SafeFiles", FILESYSTEM + "FilesystemMissionEventSourceLedger", FILESYSTEM + "AllowlistPassThrough", FILESYSTEM + "AllowlistAccess");

  @Test
  void everyReadRegularTakesAnIntCap() {
    List<JavaMethod> reads = MAIN.get(FILESYSTEM + "SafeFiles").getMethods().stream().filter(method -> method.getName().equals("readRegular")).toList();
    assertThat(reads).as("readRegular overloads").isNotEmpty();
    for (JavaMethod read : reads) {
      assertThat(read.getRawParameterTypes().stream().map(JavaClass::getName)).as("parameters of " + read.getFullName()).contains("int");
    }
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
    List<String> openers =
        MAIN.stream()
            .filter(c -> c.getPackageName().startsWith("org.speckitty.missionstatus.adapter"))
            .filter(c -> !MAY_OPEN_FOR_READ.contains(c.getName()) && !c.getName().startsWith(FILESYSTEM + "SafeFiles$") && !c.getName().startsWith(FILESYSTEM + "FilesystemMissionEventSourceLedger$"))
            .filter(c -> c.getMethodCallsFromSelf().stream().anyMatch(call -> call.getTarget().getName().equals("openRead")))
            .map(JavaClass::getName)
            .toList();
    assertThat(openers).as("classes that call openRead").isEmpty();
  }
}
