package fixture.steps;

// Fixture step definitions for tests/architectural/test_scenario_contract.py.
// Not compiled; the contract check reads the annotations as text.
public final class FixtureSteps {

    @Given("a thing named {string}")
    public void aThingNamed(String name) {}

    @When("I count {int} things")
    public void iCountThings(int n) {}

    @Then("the word {word} is shown")
    public void theWordIsShown(String w) {}

    @Given("a quote \"inside\" a step")
    public void aQuote() {}

    @Given("an ambiguous step")
    public void ambiguousOne() {}

    @When("an {word} step")
    public void ambiguousTwo(String w) {}

    @Then("a table is accepted")
    public void tableAccepted() {}

    @Given("a literal \\(with parens\\) and a dot.")
    public void literalParens() {}
}
