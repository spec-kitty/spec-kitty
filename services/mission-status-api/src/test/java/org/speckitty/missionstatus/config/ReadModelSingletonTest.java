package org.speckitty.missionstatus.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.lang.reflect.Method;
import org.junit.jupiter.api.Test;
import org.speckitty.missionstatus.application.query.MissionReadModel;
import org.speckitty.missionstatus.application.query.MissionStatusQueryService;
import org.speckitty.missionstatus.application.query.port.in.MissionStatusQuery;
import org.speckitty.missionstatus.testsupport.FilesystemFixtureFactory;
import org.speckitty.missionstatus.testsupport.FixtureSpec;
import org.speckitty.missionstatus.testsupport.http.HttpHarness;

/** The read model is one bean: every service of the query side is built from the same instance and so reaches the same projection cache. */
class ReadModelSingletonTest {

  /** {@code cache()} is package-private on purpose; the test reaches it reflectively and reads only its identity. */
  private static Object cacheOf(Object holder) throws ReflectiveOperationException {
    Method cache = holder.getClass().getDeclaredMethod("cache");
    cache.setAccessible(true);
    return cache.invoke(holder);
  }

  @Test
  void theWiredContextHoldsExactlyOneReadModelBeanAndTheServiceWasBuiltFromIt() throws Exception {
    try (HttpHarness server = HttpHarness.startWired(FilesystemFixtureFactory.fromSpec(FixtureSpec.of()).root())) {
      assertThat(server.context().getBeansOfType(MissionReadModel.class)).hasSize(1);

      MissionReadModel model = server.context().getBean(MissionReadModel.class);
      MissionStatusQuery query = server.context().getBean(MissionStatusQuery.class);

      assertThat(query).isInstanceOf(MissionStatusQueryService.class);
      assertThat(cacheOf(query)).as("the cache reached through the service").isSameAs(cacheOf(model));
    }
  }
}
