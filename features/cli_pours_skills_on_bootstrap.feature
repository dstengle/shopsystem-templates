Feature: shop-templates bootstrap pours canonical skills into a BC

  @bc:shopsystem-templates
  Scenario: bootstrapping a bc shop pours every skill file under .claude/skills byte-for-byte
    Given an existing git repository at a target directory "/tmp/skills-bc-shop"
    When I bootstrap a "bc" shop named "skills-bc-shop" at "/tmp/skills-bc-shop"
    Then the exit code of the bootstrap invocation is 0
    And every shipped skill file appears under ".claude/skills/" in the target byte-for-byte

  @bc:shopsystem-templates
  Scenario: bootstrapping a lead shop pours no skills
    Given an existing git repository at a target directory "/tmp/skills-lead-shop"
    When I bootstrap a "lead" shop named "skills-lead-shop" at "/tmp/skills-lead-shop"
    Then the exit code of the bootstrap invocation is 0
    And the target directory contains no ".claude/skills/" directory
