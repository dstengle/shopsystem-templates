@bc_internal
Feature: shopsystem-templates — lead-pm template structural sections (PDR-033)

@scenario_hash:4a4ef884012be9dc @bc:shopsystem-templates
  Scenario: lead-pm template carries the structural sections that PM-mode discipline depends on
    When I read the lead-pm template via "shop-templates show lead-pm"
    Then a non-empty template body is returned
    And the content contains a "## Position" section header
    And the content contains a "## Mode entry and exit" section header
    And the content contains a "## Session-opening rule" section header
    And the content contains a "## What you own" section header
    And the content contains a "## Posture" section header
    And the content contains a "## Altitude rule" section header
    And the content contains a "## Boundaries" section header
    And the content contains a "## Skills" section header
