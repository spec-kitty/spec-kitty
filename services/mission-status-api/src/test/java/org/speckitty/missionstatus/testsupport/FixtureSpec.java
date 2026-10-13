package org.speckitty.missionstatus.testsupport;

import java.nio.charset.StandardCharsets;
import java.util.List;

/**
 * The source-neutral description of a fixture: per Mission the {@code meta.json} text, the raw ledger bytes and the optional
 * {@code lanes.json} and {@code .kittify} text, plus the project-header inputs. It names no source: the in-memory factory realises it
 * in memory and the filesystem factory (a later work package) as a temporary tree.
 */
public record FixtureSpec(Project project, List<Mission> missions) {

  /** The project-header inputs: configuration slug, metadata and branch name. */
  public record Project(String name, String specKittyVersion, Integer schemaVersion, String branchName) {

    public static Project healthy() {
      return new Project("fixture-project", "3.2.7", 3, "main");
    }
  }

  /** One Mission directory. {@code ledger} is null when the ledger file is absent. */
  public record Mission(String name, byte[] metaJson, byte[] ledger, String lanesJson, String kittifyText) {

    public static Mission of(String name, String metaJson, String ledgerText) {
      return new Mission(name, metaJson.getBytes(StandardCharsets.UTF_8), ledgerText == null ? null : ledgerText.getBytes(StandardCharsets.UTF_8), null, null);
    }

    public static Mission ofBytes(String name, byte[] metaJson, byte[] ledger) {
      return new Mission(name, metaJson, ledger, null, null);
    }
  }

  public FixtureSpec {
    missions = List.copyOf(missions);
  }

  public static FixtureSpec of(Mission... missions) {
    return new FixtureSpec(Project.healthy(), List.of(missions));
  }

  public FixtureSpec with(Project replacement) {
    return new FixtureSpec(replacement, missions);
  }
}
