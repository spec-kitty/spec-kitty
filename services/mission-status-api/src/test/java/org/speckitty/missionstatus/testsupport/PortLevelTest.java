package org.speckitty.missionstatus.testsupport;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;
import org.junit.jupiter.api.Test;

/**
 * Marks one test of the port-level subset (FR-013) and names its id in {@code portlevel-tests.txt}. The id is the line the file holds
 * for this method; a consistency test fails when the annotation and the file disagree. A port-level test is a plain public method: no
 * parameters, no lifecycle callbacks, a class with a no-arg constructor, so {@link PortLevelRun} can invoke it by reflection against
 * whichever source {@link PortSourceSelector} currently selects.
 */
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
@Test
public @interface PortLevelTest {

  /** The test id, for example {@code AC-4a/L3a}. */
  String value();
}
