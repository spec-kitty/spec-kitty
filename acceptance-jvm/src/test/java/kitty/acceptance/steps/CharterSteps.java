package kitty.acceptance.steps;

import static org.assertj.core.api.Assertions.assertThat;

import io.cucumber.java.en.Given;
import io.cucumber.java.en.Then;
import io.cucumber.java.en.When;

import kitty.acceptance.driver.CliResult;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;

/**
 * Charter-offering consumer-outcome steps: a small, coarse, reusable outcome-verb vocabulary for
 * the three offering promises (governance in force is what I chose; refuses unsound governance
 * with a clear reason; share governance across a team or project safely).
 *
 * <p>Authored to the {@code feature-and-scenario-authoring} styleguide: the steps assert the
 * governed OUTCOME a consumer experiences, never a command's output surface, and they are kept
 * high-granularity on purpose — one coarse promise per Then. Each Act drives the command that
 * actually performs the governed check, so a red is honest: {@code doctor charter-packs} evaluates
 * pack/charter soundness and exits non-zero when it is unhealthy (an invalid profile, an org-DRG
 * error, an unhealthy skill surface); {@code charter synthesize} fails closed on a broken charter.
 * Arrange steps reach a state only by authoring what a user authors (the charter source and a team
 * pack a user drops in) and by running the CLI through the driver (constraint C-002).
 *
 * <p>The richer black-box governance fixtures — a provable project-over-org override with layer
 * provenance — are tracked under #6137; the one scenario that needs them is {@code @wip}.
 */
public final class CharterSteps {

    private static final String TEAM_PACK_DIR = ".kittify/team-pack";
    private static final String OFFERED_SKILL_ID = "team-report";
    private static final String PROJECT_RULE_MARKER = "team-rule";

    private final ScenarioContext context;

    public CharterSteps(ScenarioContext context) {
        this.context = context;
    }

    // -- Arrange -----------------------------------------------------------

    @Given("the shared governance would silently drop part of a profile")
    public void theSharedGovernanceWouldSilentlyDropPartOfAProfile() {
        writeTeamPack(VALID_ORG_CHARTER, DROP_STEPS_NODES);
        writeFile(TEAM_PACK_DIR + "/agent_profiles/thin-enhance.agent.yaml", DROP_STEPS_PROFILE);
    }

    @Given("one piece of governance points at another by a name that does not exist")
    public void onePiecePointsAtANameThatDoesNotExist() {
        writeTeamPack(VALID_ORG_CHARTER, DANGLING_EDGE_NODES);
    }

    @Given("the charter has been left in a broken state")
    public void theCharterHasBeenLeftInABrokenState() {
        writeFile(".kittify/charter/charter.yaml", "this: is not: a valid charter\n\t- broken\n:::\n");
    }

    @Given("the team pack offers a skill it does not require")
    public void theTeamPackOffersASkillItDoesNotRequire() {
        writeTeamPack(VALID_ORG_CHARTER, OFFERED_SKILL_NODES);
        writeFile(TEAM_PACK_DIR + "/skills/team-report.skill.yaml", OFFERED_SKILL_BODY);
    }

    @Given("the project shares governance through a team pack")
    public void theProjectSharesGovernanceThroughATeamPack() {
        writeTeamPack(VALID_ORG_CHARTER, VALID_NODES);
    }

    @Given("the team pack carries a profile that is not sound")
    public void theTeamPackCarriesAProfileThatIsNotSound() {
        writeFile(TEAM_PACK_DIR + "/agent_profiles/broken.agent.yaml", "profile-id: broken\n# missing every required field below\n");
    }

    @Given("the team pack requires a rule the project did not select")
    public void theTeamPackRequiresARuleTheProjectDidNotSelect() {
        writeTeamPack(REQUIRE_RULE_ORG_CHARTER, RULE_NODES);
        writeFile(TEAM_PACK_DIR + "/directive/team-rule.directive.yaml", teamRule("the team-wide default"));
    }

    @Given("the team pack ships an asset that points outside its own folder")
    public void theTeamPackShipsAnAssetThatPointsOutsideItsOwnFolder() {
        writeTeamPack(VALID_ORG_CHARTER, ESCAPING_ASSET_NODES);
    }

    @Given("the project shares governance through a team pack speaking to a rule")
    public void theProjectSharesATeamPackSpeakingToARule() {
        writeTeamPack(VALID_ORG_CHARTER, RULE_NODES);
        writeFile(TEAM_PACK_DIR + "/directive/team-rule.directive.yaml", teamRule("defer to the team default"));
    }

    @Given("the project's own governance speaks to the same rule differently")
    public void theProjectsOwnGovernanceSpeaksToTheSameRuleDifferently() {
        writeFile(".kittify/charter-packs/directive/team-rule.directive.yaml", teamRule("use the project override"));
    }

    @Given("the team pack shares a skill under a reserved name")
    public void theTeamPackSharesASkillUnderAReservedName() {
        writeTeamPack(RESERVED_NAMESPACE_ORG_CHARTER, OFFERED_SKILL_NODES);
        writeFile(TEAM_PACK_DIR + "/skills/team-report.skill.yaml", OFFERED_SKILL_BODY);
    }

    // -- Act ---------------------------------------------------------------

    @When("the author sets up the governance")
    public void theAuthorSetsUpTheGovernance() {
        run("spec-kitty", "charter", "synthesize");
    }

    @When("the author asks what governs the work")
    public void theAuthorAsksWhatGovernsTheWork() {
        run("spec-kitty", "charter", "list");
    }

    @When("the author checks the shared governance is sound")
    public void theAuthorChecksTheSharedGovernanceIsSound() {
        run("spec-kitty", "doctor", "charter-packs");
    }

    // -- Assert ------------------------------------------------------------

    @Then("the system refuses with a clear reason")
    public void theSystemRefusesWithAClearReason() {
        CliResult result = context.lastResult();
        assertThat(result.exitCode()).as("the command should refuse unsound governance (non-zero exit):%n%s", result).isNotZero();
        assertThat(combined(result).strip()).as("a refusal should carry a reason, not be silent").isNotEmpty();
    }

    @Then("the governance in force is only what the charter puts in force")
    public void theGovernanceInForceIsOnlyWhatTheCharterPutsInForce() {
        CliResult inForce = context.lastResult();
        assertThat(inForce.exitCode()).as("listing the governance in force should succeed:%n%s", inForce).isZero();
        CliResult available = run("spec-kitty", "charter", "list", "--all");
        assertThat(available.exitCode()).as("listing every available artifact should succeed:%n%s", available).isZero();
        assertThat(combined(available))
                .as("the offered skill should be available across the layers")
                .contains(OFFERED_SKILL_ID);
        assertThat(combined(inForce))
                .as("an offered-but-unrequired skill must not be in force merely because it exists")
                .doesNotContain(OFFERED_SKILL_ID);
    }

    @Then("the shared governance is not reported healthy")
    public void theSharedGovernanceIsNotReportedHealthy() {
        CliResult result = context.lastResult();
        assertThat(result.exitCode()).as("a pack with an unsound artifact must not be reported healthy (non-zero exit):%n%s", result).isNotZero();
    }

    @Then("the governance in force includes the team's required rule")
    public void theGovernanceInForceIncludesTheTeamsRequiredRule() {
        CliResult inForce = context.lastResult();
        assertThat(inForce.exitCode()).as("listing the governance in force should succeed:%n%s", inForce).isZero();
        assertThat(combined(inForce))
                .as("an org-required rule should be in force even though the project did not select it")
                .contains(PROJECT_RULE_MARKER);
    }

    @Then("the project's own choice is the governance in force")
    public void theProjectsOwnChoiceIsTheGovernanceInForce() {
        CliResult inForce = context.lastResult();
        assertThat(inForce.exitCode()).as("listing the governance in force should succeed:%n%s", inForce).isZero();
        assertThat(combined(inForce))
                .as("the project's own rule should be the one in force")
                .contains(PROJECT_RULE_MARKER);
    }

    // -- helpers -----------------------------------------------------------

    private CliResult run(String... args) {
        CliResult result = context.run(List.of(args));
        context.recordResult(result);
        return result;
    }

    private static String combined(CliResult result) {
        return result.stdout() + "\n" + result.stderr();
    }

    private void writeFile(String relative, String content) {
        Path path = context.world().resolve(relative);
        try {
            Files.createDirectories(path.getParent());
            Files.writeString(path, content);
        } catch (IOException exception) {
            throw new UncheckedIOException("Could not author " + relative + " for the charter fixture", exception);
        }
    }

    /** Lays down a minimal org-tier team pack (a user-authored pack) and registers it in config. */
    private void writeTeamPack(String orgCharter, String fragmentNodes) {
        writeFile(TEAM_PACK_DIR + "/pack.yaml", PACK_DESCRIPTOR);
        writeFile(TEAM_PACK_DIR + "/org-charter.yaml", orgCharter);
        writeFile(TEAM_PACK_DIR + "/drg/fragment.yaml", FRAGMENT_HEADER + fragmentNodes);
        registerTeamPack();
    }

    private void registerTeamPack() {
        Path config = context.world().resolve(".kittify/config.yaml");
        try {
            String existing = Files.exists(config) ? Files.readString(config) : "";
            if (!existing.contains("charter_packs:")) {
                Files.writeString(config, existing + "\n" + TEAM_PACK_REGISTRATION);
            }
        } catch (IOException exception) {
            throw new UncheckedIOException("Could not register the team pack in config.yaml", exception);
        }
    }

    private static String teamRule(String body) {
        return "schema_version: \"1.0\"\nid: team-rule\ntitle: Team rule\nscope: docs\nbody: >\n  " + body + "\n";
    }

    // -- fixture content (kept inline and minimal; the richer fixtures are #6137) -----------

    private static final String PACK_DESCRIPTOR =
            "pack_id: 01M4P01D5TWB5FKZGNNQG3900A\nparent_pack: null\nname: team-pack\npack_level: org\n"
            + "active_charter: org-charter.yaml\npack_drg: drg/fragment.yaml\n";

    private static final String TEAM_PACK_REGISTRATION =
            "charter_packs:\n  org:\n    packs:\n    - name: team-pack\n      local_path: " + TEAM_PACK_DIR + "\n";

    private static final String FRAGMENT_HEADER =
            "pack_name: team-pack\nsource_kind: local_path\nsource_ref: " + TEAM_PACK_DIR + "\nlayer_index: 1\nprovenance_marker: org\n";

    private static final String VALID_ORG_CHARTER = "org_name: team\nskill_namespace: team\n";

    private static final String RESERVED_NAMESPACE_ORG_CHARTER = "org_name: team\nskill_namespace: spk-team\n";

    private static final String REQUIRE_RULE_ORG_CHARTER = "org_name: team\nskill_namespace: team\nrequired_directives:\n  - team-rule\n";

    private static final String VALID_NODES = "nodes: []\n";

    private static final String OFFERED_SKILL_NODES =
            "nodes:\n  - id: team-report\n    kind: skills\n    title: Team report command\n    body_path: skills/team-report.skill.yaml\n";

    private static final String RULE_NODES =
            "nodes:\n  - id: team-rule\n    kind: directives\n    title: Team rule\n    body_path: directive/team-rule.directive.yaml\n";

    private static final String ESCAPING_ASSET_NODES =
            "nodes:\n  - id: team-asset\n    kind: assets\n    title: Team asset\n    body_path: ../../../../etc/hostname\n";

    private static final String DANGLING_EDGE_NODES =
            "nodes: []\nedges:\n  - source: \"directive:team-rule\"\n    target: \"directive:does-not-exist\"\n    relation: suggests\n";

    private static final String DROP_STEPS_NODES =
            "nodes:\n  - id: thin-enhance\n    kind: agent_profiles\n    title: Thin enhance\n    body_path: agent_profiles/thin-enhance.agent.yaml\n";

    private static final String DROP_STEPS_PROFILE =
            "profile-id: thin-enhance\nname: Thin enhance\nschema-version: \"1.0\"\n"
            + "collaboration:\n  enhances: researcher-ryan\n  operating-procedures: []\n";

    private static final String OFFERED_SKILL_BODY =
            "schema_version: \"1.0\"\nid: team-report\ntitle: Team report\nnamespace: team\n"
            + "command:\n  summary: Produce the team report\nbody: >\n  Produce the team report.\n";
}
