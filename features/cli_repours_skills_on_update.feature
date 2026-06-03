Feature: shop-templates update mirrors canonical skills into a BC

  @bc:shopsystem-templates
  Scenario: update re-pours a drifted skill file to canonical bytes
    Given a bootstrapped "bc" shop at a target directory "/tmp/upd-skills-bc"
    And the skill file ".claude/skills/test-driven-development/SKILL.md" has drifted to "STALE"
    When I run update for shop type "bc" at "/tmp/upd-skills-bc"
    Then the exit code of the update invocation is 0
    And every shipped skill file appears under ".claude/skills/" in the target byte-for-byte

  @bc:shopsystem-templates
  Scenario: update leaves an already-current skill file byte-and-mtime unchanged
    Given a bootstrapped "bc" shop at a target directory "/tmp/upd-skills-idem"
    When I record the mtime of ".claude/skills/test-driven-development/SKILL.md"
    And I run update for shop type "bc" at "/tmp/upd-skills-idem"
    Then the exit code of the update invocation is 0
    And the mtime of ".claude/skills/test-driven-development/SKILL.md" is unchanged

  @bc:shopsystem-templates
  Scenario: update removes a managed skill file that the package no longer ships
    Given a bootstrapped "bc" shop at a target directory "/tmp/upd-skills-orphan"
    And an extra file ".claude/skills/removed-skill/SKILL.md" exists in the target
    When I run update for shop type "bc" at "/tmp/upd-skills-orphan"
    Then the exit code of the update invocation is 0
    And the target directory contains no file at ".claude/skills/removed-skill/SKILL.md"
