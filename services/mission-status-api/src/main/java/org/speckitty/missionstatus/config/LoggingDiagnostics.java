package org.speckitty.missionstatus.config;

import java.util.function.Consumer;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.speckitty.missionstatus.domain.model.Diagnostic;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/** Writes each diagnostic as one path-free line: the stable code, the Mission's mid8 and the line number. Never a path, line text or OS message. */
@Configuration(proxyBeanMethods = false)
class LoggingDiagnostics {

  private static final Logger LOG = LoggerFactory.getLogger("org.speckitty.missionstatus.diagnostics");

  @Bean
  Consumer<Diagnostic> diagnosticsLine() {
    return diagnostic -> LOG.warn("diagnostic code={} mid8={} line={}", diagnostic.code().wire(), diagnostic.mid8(), diagnostic.line() == null ? "-" : diagnostic.line());
  }
}
