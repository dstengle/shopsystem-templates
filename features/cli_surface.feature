Feature: shopsystem-templates — CLI surface and role-discipline structure

  @scenario_hash:b8f9b464718ca32e @bc:shopsystem-templates
  Scenario: shop-templates list outputs the four expected role-template names, one per line, sorted
    When I run "shop-templates list"
    Then the exit code is 0
    And stdout is exactly the four names "bc-implementer", "bc-reviewer", "lead-architect", "lead-po", one per line in that sorted order
    And stderr is empty

  @scenario_hash:91ce9dc16dec6a13 @bc:shopsystem-templates
  Scenario: shop-templates show writes the named template's content to stdout with no extra leading or trailing data
    Given a template name "bc-implementer" that is in the list output by "shop-templates list"
    When I run "shop-templates show bc-implementer"
    Then the exit code is 0
    And stdout equals the package-data file contents for that template, byte-for-byte (no extra trailing newline beyond what the file itself carries)
    And stderr is empty

  @scenario_hash:864852562cf9239d @bc:shopsystem-templates
  Scenario: shop-templates show with an unknown template name exits non-zero and names both the bad input and the available list on stderr
    Given a template name "no-such-template" that is not in the list output by "shop-templates list"
    When I run "shop-templates show no-such-template"
    Then the exit code is non-zero
    And stdout is empty
    And stderr names the offending input "no-such-template"
    And stderr cites the list of available templates so the caller can recover
