package org.speckitty.missionstatus.testsupport;

import java.lang.annotation.Documented;
import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

/**
 * Marks one leg of a permission-denied case. Each case id has exactly two legs: one with an injected fault (the recorder throws
 * {@code AccessDeniedException}) and one with real permissions removed from a real file ({@link RealPermissionFixture}). The coverage
 * function in {@code PermissionCaseCoverageTest} reads these annotations; it demands one test of each leg per id (D-32, D-101).
 */
@Documented
@Retention(RetentionPolicy.RUNTIME)
@Target({ElementType.METHOD, ElementType.TYPE})
public @interface PermissionCase {

  /** The two legs of a case. */
  enum Leg {
    /** The fault is injected through the recording seam. */
    INJECTED,
    /** The permission is removed from a real file and the operating system refuses. */
    REAL
  }

  /** The case id, for example {@code readText-denied}. */
  String value();

  /** Which leg this test is. */
  Leg leg();
}
