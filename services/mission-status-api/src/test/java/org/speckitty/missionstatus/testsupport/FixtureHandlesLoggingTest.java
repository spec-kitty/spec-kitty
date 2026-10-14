package org.speckitty.missionstatus.testsupport;

import static org.assertj.core.api.Assertions.assertThat;

import ch.qos.logback.classic.Level;
import ch.qos.logback.classic.spi.ILoggingEvent;
import ch.qos.logback.core.read.ListAppender;
import java.lang.reflect.Constructor;
import java.lang.reflect.Method;
import java.util.List;
import java.util.function.Consumer;
import org.junit.jupiter.api.Test;
import org.slf4j.LoggerFactory;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.speckitty.missionstatus.domain.model.DiagnosticCode;

/**
 * The fixture service writes the diagnostics of the stream's projection (it no longer happens in the controller with the Spring
 * consumer), so the recorder must write the very line {@code config.LoggingDiagnostics} writes, or {@code CanaryScanTest} would read an
 * empty log. This pins the parity: same logger, same level, same text, for a diagnostic with and without a line.
 */
class FixtureHandlesLoggingTest {

  private static final String LOGGER = "org.speckitty.missionstatus.diagnostics";

  /** The production consumer, which the package-private configuration class builds. */
  @SuppressWarnings("unchecked")
  private static Consumer<Diagnostic> production() throws ReflectiveOperationException {
    Class<?> type = Class.forName("org.speckitty.missionstatus.config.LoggingDiagnostics");
    Constructor<?> constructor = type.getDeclaredConstructor();
    constructor.setAccessible(true);
    Method bean = type.getDeclaredMethod("diagnosticsLine");
    bean.setAccessible(true);
    return (Consumer<Diagnostic>) bean.invoke(constructor.newInstance());
  }

  private static ListAppender<ILoggingEvent> capture() {
    ListAppender<ILoggingEvent> appender = new ListAppender<>();
    appender.start();
    ((ch.qos.logback.classic.Logger) LoggerFactory.getLogger(LOGGER)).addAppender(appender);
    return appender;
  }

  private static void release(ListAppender<ILoggingEvent> appender) {
    ((ch.qos.logback.classic.Logger) LoggerFactory.getLogger(LOGGER)).detachAppender(appender);
    appender.stop();
  }

  private static List<String> lines(Consumer<Diagnostic> consumer, Diagnostic diagnostic) {
    ListAppender<ILoggingEvent> appender = capture();
    try {
      consumer.accept(diagnostic);
      assertThat(appender.list).singleElement().satisfies(event -> {
        assertThat(event.getLevel()).isEqualTo(Level.WARN);
        assertThat(event.getLoggerName()).isEqualTo(LOGGER);
      });
      return List.of(appender.list.getFirst().getFormattedMessage());
    } finally {
      release(appender);
    }
  }

  @Test
  void theRecordersLineIsTheProductionLineForADiagnosticWithAndWithoutALine() throws Exception {
    Diagnostic whole = new Diagnostic(DiagnosticCode.PROJECTION_REFUSED, "01J01000", null);
    Diagnostic withLine = new Diagnostic(DiagnosticCode.LEDGER_UNPARSEABLE, "01J02000", 7);
    Consumer<Diagnostic> production = production();

    for (Diagnostic diagnostic : List.of(whole, withLine)) {
      FixtureHandles handles = new FixtureHandles(new MutableClock(java.time.Instant.parse("2026-10-01T12:00:00Z")));

      assertThat(lines(handles.recorder(), diagnostic)).isEqualTo(lines(production, diagnostic));
    }
    assertThat(lines(production, whole)).containsExactly("diagnostic code=projection_refused mid8=01J01000 line=-");
    assertThat(lines(production, withLine)).containsExactly("diagnostic code=ledger_unparseable mid8=01J02000 line=7");
  }

  @Test
  void theRecorderStillRecordsTheDiagnostic() {
    FixtureHandles handles = new FixtureHandles(new MutableClock(java.time.Instant.parse("2026-10-01T12:00:00Z")));
    Diagnostic diagnostic = new Diagnostic(DiagnosticCode.PROJECTION_REFUSED, "01J01000", null);

    handles.recorder().accept(diagnostic);

    assertThat(handles.diagnostics()).containsExactly(diagnostic);
  }
}
