package fixture.steps;

public final class BadSteps {

    @Given("a thing{s}")
    public void unknownParameter() {}

    @Given("{int} cuke(s)")
    public void optionalText() {}

    @When("I open/close the door")
    public void alternation() {}
}
