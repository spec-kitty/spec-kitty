package org.speckitty.missionstatus.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.method.HandlerTypePredicate;
import org.springframework.web.servlet.config.annotation.PathMatchConfigurer;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

/**
 * The /api/v1 prefix is an MVC path prefix, never a servlet path or a context path: with spring.mvc.servlet.path an unknown path
 * outside the prefix is answered 404 by the container without entering any filter, which would let the Host/Origin filter miss it
 * (research.md spike record, Review cycle 2 F2).
 */
@Configuration(proxyBeanMethods = false)
class MissionStatusApplicationWeb implements WebMvcConfigurer {

  static final String API_PREFIX = "/api/v1";

  @Override
  public void configurePathMatch(PathMatchConfigurer configurer) {
    configurer.addPathPrefix(API_PREFIX, HandlerTypePredicate.forBasePackage("org.speckitty.missionstatus.adapter.in.http"));
  }
}
