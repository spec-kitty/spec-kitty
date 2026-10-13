package org.speckitty.missionstatus.testsupport;

import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.opentest4j.TestAbortedException;
import org.speckitty.missionstatus.testsupport.PortLevelIds.Entry;

/**
 * Runs the tests of the port-level subset by id, against whichever source {@link PortSourceSelector} currently selects, and records
 * what happened to each. A run is in-process and reflective (the JUnit launcher API is not on the compile classpath of this build, and
 * the build script is another work package's), which the plain-method rule of {@link PortLevelTest} makes sufficient.
 *
 * <p>An outcome is EXECUTED (returned normally), SKIPPED (an assumption failure, {@link TestAbortedException}) or FAILED (anything else,
 * including an id the file names that no annotated method carries).
 */
public final class PortLevelRun {

  /** What became of one id. */
  public enum Status {
    EXECUTED,
    SKIPPED,
    FAILED
  }

  /** One recorded outcome. {@code detail} is the abort message or the failure, empty when executed. */
  public record Outcome(Entry entry, Status status, String detail) {}

  private PortLevelRun() {}

  /** Runs every entry in file order and returns the outcome per id. */
  public static Map<String, Outcome> run(List<Entry> entries) {
    Map<String, Outcome> outcomes = new LinkedHashMap<>();
    for (Entry entry : entries) {
      outcomes.put(entry.id(), runOne(entry));
    }
    return outcomes;
  }

  private static Outcome runOne(Entry entry) {
    try {
      Class<?> type = Class.forName(entry.qualifiedClassName());
      Method method = type.getDeclaredMethod(entry.method());
      PortLevelTest marker = method.getAnnotation(PortLevelTest.class);
      if (marker == null || !marker.value().equals(entry.id())) {
        return new Outcome(entry, Status.FAILED, "the method does not carry @PortLevelTest(\"" + entry.id() + "\")");
      }
      var constructor = type.getDeclaredConstructor();
      constructor.setAccessible(true);
      method.setAccessible(true);
      method.invoke(constructor.newInstance());
      return new Outcome(entry, Status.EXECUTED, "");
    } catch (InvocationTargetException thrown) {
      Throwable cause = thrown.getCause();
      if (cause instanceof TestAbortedException aborted) {
        return new Outcome(entry, Status.SKIPPED, String.valueOf(aborted.getMessage()));
      }
      return new Outcome(entry, Status.FAILED, String.valueOf(cause));
    } catch (ReflectiveOperationException | RuntimeException unresolvable) {
      return new Outcome(entry, Status.FAILED, String.valueOf(unresolvable));
    }
  }
}
