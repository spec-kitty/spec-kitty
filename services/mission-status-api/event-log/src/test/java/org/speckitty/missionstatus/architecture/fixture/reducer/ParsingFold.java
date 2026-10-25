package org.speckitty.missionstatus.architecture.fixture.reducer;

import tools.jackson.core.json.JsonFactory;

/** Planted violation: a fold that parses JSON itself (the reducer must take decoded events only). */
public final class ParsingFold {

  private ParsingFold() {}

  public static boolean parses(String line) {
    return new JsonFactory().createParser(line).nextToken() != null;
  }
}
