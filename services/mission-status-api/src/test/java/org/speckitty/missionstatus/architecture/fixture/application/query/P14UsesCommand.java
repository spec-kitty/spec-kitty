package org.speckitty.missionstatus.architecture.fixture.application.query;

/** Architecture-rule fixture, planted violation of rule 14: the query side depends on the command side. */
public final class P14UsesCommand {
  public Object reach() {
    return new org.speckitty.missionstatus.architecture.fixture.application.command.Cmd();
  }
}
