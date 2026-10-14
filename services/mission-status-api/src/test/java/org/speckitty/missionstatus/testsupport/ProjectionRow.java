package org.speckitty.missionstatus.testsupport;

import java.lang.annotation.Documented;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * Marks a test as the test of one {@code (row, route)} pair of the projection table (D-102), for example row {@code T5} of route
 * {@code getMission}. Only the annotation is here; the discovery guard that demands every pair is covered belongs to the work package
 * that owns the whole set of routes.
 */
@Documented
@Retention(RetentionPolicy.RUNTIME)
@Target({ElementType.METHOD, ElementType.TYPE})
public @interface ProjectionRow {

  /** The row of the projection table, for example {@code T5}. */
  String row();

  /** The route the row is checked on, for example {@code getMission}. */
  String route();
}
