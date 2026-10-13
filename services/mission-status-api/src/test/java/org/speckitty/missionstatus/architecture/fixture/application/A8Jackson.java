package org.speckitty.missionstatus.architecture.fixture.application;

/** Architecture-rule fixture: planted violation of rule 8 (Jackson in application). */
public final class A8Jackson {
  public Object mapper() {
    return tools.jackson.databind.json.JsonMapper.builder().build();
  }
}
