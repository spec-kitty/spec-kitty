package org.speckitty.missionstatus.config;

import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/** The scheduled executor that runs the change feed's poll tick (the application creates no thread; this is where one is made). */
@Configuration(proxyBeanMethods = false)
class FeedExecutorConfig {

  @Bean(destroyMethod = "shutdownNow")
  ScheduledExecutorService feedExecutor() {
    return Executors.newSingleThreadScheduledExecutor(
        task -> {
          Thread thread = new Thread(task, "mission-status-feed");
          thread.setDaemon(true);
          return thread;
        });
  }
}
