package org.speckitty.missionstatus.config;

import java.util.Optional;
import org.speckitty.missionstatus.adapter.out.filesystem.ProjectRootCheck;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.event.ApplicationEnvironmentPreparedEvent;
import org.springframework.context.ApplicationListener;
import org.springframework.context.annotation.ImportRuntimeHints;

/** Entry point of the Mission Status API service. The project root is validated before the web server starts. */
@SpringBootApplication(scanBasePackages = {"org.speckitty.missionstatus.config", "org.speckitty.missionstatus.adapter.in.http"})
@ImportRuntimeHints(MissionStatusApplicationHints.class)
public class MissionStatusApplication {

  /** Set by Spring's AOT processor while it runs main() at build time. */
  private static final String AOT_PROCESSING = "spring.aot.processing";

  public static void main(String[] args) {
    SpringApplication application = new SpringApplication(MissionStatusApplication.class);
    application.addListeners(new ProjectRootGuard());
    application.run(args);
  }

  /** Exits non-zero, naming the key, when the project root is unset, blank or not a directory. */
  static final class ProjectRootGuard implements ApplicationListener<ApplicationEnvironmentPreparedEvent> {
    @Override
    public void onApplicationEvent(ApplicationEnvironmentPreparedEvent event) {
      if (Boolean.getBoolean(AOT_PROCESSING)) {
        return; // the build runs main() for ahead-of-time processing with no project root; nothing is served then
      }
      Optional<String> refusal = ProjectRootCheck.refusal(event.getEnvironment().getProperty(ProjectRootCheck.KEY));
      if (refusal.isPresent()) {
        System.err.println(refusal.get());
        System.exit(1);
      }
    }
  }
}
