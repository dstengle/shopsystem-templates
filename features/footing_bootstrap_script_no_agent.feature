Feature: the footing phase invokes no agent

  @scenario_hash:44d534b52c4925e2 @bc:shopsystem-templates
  Scenario: the footing phase invokes no agent
    Given the bootstrap script for a "<product>-lead" repository
    When the script is inspected and run through to footing
    Then it completes the footing sequence without launching any Claude or PM agent session
    And its only non-deterministic step is the single human auth gate
