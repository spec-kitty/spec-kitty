package org.speckitty.missionstatus.config;

import jakarta.servlet.DispatcherType;
import java.util.EnumSet;
import org.speckitty.missionstatus.adapter.in.http.HostOriginFilter;
import org.speckitty.missionstatus.adapter.in.http.OwnPortSource;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.Ordered;
import tools.jackson.databind.json.JsonMapper;

/** Registers the Host and Origin filter ahead of everything else. */
@Configuration(proxyBeanMethods = false)
class HostOriginRegistration {

  @Bean
  FilterRegistrationBean<HostOriginFilter> hostOriginFilter(OwnPortSource ownPort, JsonMapper mapper) {
    FilterRegistrationBean<HostOriginFilter> registration = new FilterRegistrationBean<>(new HostOriginFilter(ownPort, mapper));
    registration.setOrder(Ordered.HIGHEST_PRECEDENCE);
    registration.setDispatcherTypes(EnumSet.of(DispatcherType.REQUEST, DispatcherType.ERROR));
    registration.addUrlPatterns("/*");
    return registration;
  }
}
