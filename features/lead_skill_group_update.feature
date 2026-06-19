Feature: shop-templates update mirrors the canonical lead skill-group into a lead shop

  @scenario_hash:e803b4c9cdf36c21 @bc:shopsystem-templates
  Scenario: shop-templates update re-pours every bootstrap-managed skill in the lead skill-group in the target directory from the current canonical package data
    Given an existing git repository at a target directory "/tmp/example-lead-shop" that was previously bootstrapped as a "lead" shop named "example-lead-shop"
    And the file at ".claude/skills/bring-up-bc/SKILL.md" in the target directory equals the current canonical "bring-up-bc" lead-skill template package-data file contents byte-for-byte
    When I invoke the "shop-templates" update entry point against the target directory "/tmp/example-lead-shop"
    Then the exit code is 0
    And after the invocation the file at ".claude/skills/bring-up-bc/SKILL.md" in the target directory still equals the current canonical "bring-up-bc" lead-skill template package-data file contents byte-for-byte

  @scenario_hash:4a008549dafc905c @bc:shopsystem-templates
  Scenario: update replaces a stale bootstrap-managed lead skill file with the current canonical content when the package-data template has changed since the shop was bootstrapped
    Given an existing git repository at a target directory "/tmp/example-lead-shop" that was previously bootstrapped as a "lead" shop named "example-lead-shop"
    And the file at ".claude/skills/bring-up-bc/SKILL.md" in the target directory holds an older version of the "bring-up-bc" canonical lead-skill template content
    And the current canonical "bring-up-bc" lead-skill template package-data file contents differ from that older version
    When I invoke the "shop-templates" update entry point against the target directory "/tmp/example-lead-shop"
    Then the exit code is 0
    And after the invocation the file at ".claude/skills/bring-up-bc/SKILL.md" in the target directory equals the current canonical "bring-up-bc" lead-skill template package-data file contents byte-for-byte

  @scenario_hash:a14e5a0aacb58285 @bc:shopsystem-templates
  Scenario: update is idempotent for the managed lead skill-group when the poured skills already match the current canonical package data
    Given an existing git repository at a target directory "/tmp/example-lead-shop" that was previously bootstrapped as a "lead" shop named "example-lead-shop"
    And every skill in the ".claude/skills/" directory equals its current canonical lead-skill template package-data file contents byte-for-byte
    When I invoke the "shop-templates" update entry point against the target directory "/tmp/example-lead-shop"
    Then the exit code is 0
    And after the invocation every skill in the ".claude/skills/" directory still equals its current canonical lead-skill template package-data file contents byte-for-byte
    And the set of skill directories under ".claude/skills/" in the target directory is unchanged

  # lead-bdsq / scenario 159 (supersedes the prior vacuous bootstrap-path pin):
  # the over-prune contract is pinned NON-VACUOUSLY on the UPDATE entry point —
  # the path where _mirror_skills actually prunes. The retired bootstrap-path
  # pin exercised _pour_skills, which never prunes, so it could not catch the
  # over-prune regression. This scenario exercises update, so reverting the
  # prune-scoping fix flips it RED.
  @scenario_hash:9a064e8f6ed915e3 @bc:shopsystem-templates
  Scenario: "shop-templates update" on a lead shop scopes skill-directory pruning to canonical-managed members only, so an unmanaged experimentally-adopted skill directory survives byte-for-byte
    Given an existing git repository at a target directory "/tmp/example-lead-shop" previously bootstrapped as a lead shop
    And the target directory contains an unmanaged skill directory ".claude/skills/problem-framing-canvas/" with a "SKILL.md" file whose directory name is not a member of the canonical lead skill-group
    When I invoke the "shop-templates" update entry point with shop type "lead" and target directory "/tmp/example-lead-shop"
    Then the exit code is 0
    And the unmanaged skill directory ".claude/skills/problem-framing-canvas/" and its "SKILL.md" file are still present after the invocation with their pre-invocation contents preserved byte-for-byte
    And any pruning the invocation performs under ".claude/skills/" removes only directories whose name is a member of the canonical lead skill-group, and never removes a directory whose name is not a canonical lead skill-group member
