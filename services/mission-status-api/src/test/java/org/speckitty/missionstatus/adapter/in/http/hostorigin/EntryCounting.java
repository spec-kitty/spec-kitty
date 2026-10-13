package org.speckitty.missionstatus.adapter.in.http.hostorigin;

import jakarta.servlet.Filter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.ServletRequest;
import jakarta.servlet.ServletResponse;
import java.io.IOException;
import java.util.concurrent.atomic.AtomicInteger;
import org.springframework.beans.factory.config.BeanPostProcessor;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * The test-profile counter of {@code reachesFilter}. It is added to a test context by {@code spring.main.sources} and wraps the filter
 * of the Host/Origin registration, so it counts exactly the requests that ENTER the production filter (a request the container answers
 * itself never does, and with the filter unregistered the count stays zero). Production code carries no counter.
 */
@Configuration(proxyBeanMethods = false)
public class EntryCounting {

  private static final String COUNTED = EntryCounting.class.getName() + ".counted";

  public static final String SOURCE = "spring.main.sources=" + EntryCounting.class.getName();

  /** Counts the entries of every filter registration that is not the framework's own: only the Host/Origin one exists in this application. */
  public static final class Counter implements BeanPostProcessor {
    private final AtomicInteger entries = new AtomicInteger();
    private volatile int registrations;

    public int entries() {
      return entries.get();
    }

    /** How many registrations were wrapped (a counter that wrapped nothing proves nothing). */
    public int registrations() {
      return registrations;
    }

    @Override
    @SuppressWarnings({"unchecked", "rawtypes"})
    public Object postProcessAfterInitialization(Object bean, String beanName) {
      if (bean instanceof FilterRegistrationBean registration && registration.getFilter() != null && registration.getFilter().getClass().getSimpleName().equals("HostOriginFilter")) {
        Filter inner = registration.getFilter();
        registration.setFilter(
            new Filter() {
              @Override
              public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain) throws IOException, ServletException {
                // one count per request: an ERROR redispatch of a request that already entered is the same entry
                if (request.getAttribute(COUNTED) == null) {
                  request.setAttribute(COUNTED, Boolean.TRUE);
                  entries.incrementAndGet();
                }
                inner.doFilter(request, response, chain);
              }
            });
        registrations++;
      }
      return bean;
    }
  }

  @Bean
  static Counter hostOriginEntryCounter() {
    return new Counter();
  }
}
