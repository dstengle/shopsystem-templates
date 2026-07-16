@bc:shopsystem-templates @origin:lead-5mr5
Feature: shop-templates ships and pours the canonical lead skill-group

  @scenario_hash:c207853320920de7
  Scenario Outline: the canonical lead skill-group is shipped as package data and exposed through the "shop-templates" public template-access surface, parallel to the role templates and primer
    Given the installed "shop-templates" distribution
    When I query the "shop-templates" public template-access surface for the canonical "<shop_type>" skill-group
    Then the access surface reports the skill-group has at least one member
    And the member named "bring-up-bc" is present in the reported skill-group
    And for each reported member the access surface returns package-data "SKILL.md" contents byte-for-byte

    Examples:
      | shop_type |
      | lead      |

  @scenario_hash:cc52003444ea63f7
  Scenario Outline: the poured "bring-up-bc" skill is a member of the canonical lead skill-group and its body names launching via bc-container, the BCLAUNCHER_HOST_HOME devcontainer fact, and the shop-msg bc-status online check
    Given an existing git repository at a target directory "<target>" with no ".claude/skills/" directory
    When I invoke the "shop-templates" bootstrap entry point with shop type "<shop_type>", shop name "<shop_name>", and target directory "<target>"
    Then the exit code is 0
    And the target directory contains a file at ".claude/skills/bring-up-bc/SKILL.md"
    And the content of ".claude/skills/bring-up-bc/SKILL.md" names launching a BC via "bc-container launch"
    And the content of ".claude/skills/bring-up-bc/SKILL.md" names setting "BCLAUNCHER_HOST_HOME" for a devcontainer with a bind-mounted home
    And the content of ".claude/skills/bring-up-bc/SKILL.md" names verifying the BC reaches "online" via "shop-msg bc-status"

    Examples:
      | shop_type | shop_name          | target                 |
      | lead      | shopsystem-product | /tmp/example-lead-shop |

  @scenario_hash:7df4006ce0d43d8b
  Scenario Outline: the poured "bring-up-bc" skill scopes the BCLAUNCHER_HOST_HOME requirement to the workspace-mount / bind-mounted-home launch case and does not present it as required for a clone-path launch or universally
    Given an existing git repository at a target directory "<target>" with no ".claude/skills/" directory
    When I invoke the "shop-templates" bootstrap entry point with shop type "<shop_type>", shop name "<shop_name>", and target directory "<target>"
    Then the exit code is 0
    And the target directory contains a file at ".claude/skills/bring-up-bc/SKILL.md"
    And the content of ".claude/skills/bring-up-bc/SKILL.md" presents setting "BCLAUNCHER_HOST_HOME" as required for the workspace-mount / bind-mounted-home devcontainer launch case
    And the content of ".claude/skills/bring-up-bc/SKILL.md" names that a clone-path BC launch does NOT require "BCLAUNCHER_HOST_HOME"
    And the content of ".claude/skills/bring-up-bc/SKILL.md" does not present "BCLAUNCHER_HOST_HOME" as universally required for every launch

    Examples:
      | shop_type | shop_name          | target                 |
      | lead      | shopsystem-product | /tmp/example-lead-shop |

  @scenario_hash:f75eb04e359f4833
  Scenario Outline: the poured "create-bc" skill is a member of the canonical lead skill-group and its body names the scaffold, remote, manifest, launch, gotcha, and experimental-honesty elements of the proven create-a-BC-from-scratch procedure
    Given an existing git repository at a target directory "<target>" with no ".claude/skills/" directory
    When I invoke the "shop-templates" bootstrap entry point with shop type "<shop_type>", shop name "<shop_name>", and target directory "<target>"
    Then the exit code is 0
    And the target directory contains a file at ".claude/skills/create-bc/SKILL.md"
    And the content of ".claude/skills/create-bc/SKILL.md" names scaffolding a new BC via "shop-templates bootstrap --shop-type bc"
    And the content of ".claude/skills/create-bc/SKILL.md" names creating the remote via "gh repo create" and pushing, and names prompting the user for the GitHub org/owner and the public/private visibility rather than hardcoding them
    And the content of ".claude/skills/create-bc/SKILL.md" names registering the BC in "bc-manifest.yaml" via "bc-container manifest"
    And the content of ".claude/skills/create-bc/SKILL.md" names launching via "bc-container launch" with the brokered flags "--repo-url", "--image" at bc-base "v0.3.1+" rather than ":latest", "--network", "--agent-vault-broker", and "--env-file", and cross-references the "bring-up-bc" skill for the launch leg
    And the content of ".claude/skills/create-bc/SKILL.md" names the gotchas that "AGENT_VAULT_VAULT" is the plain "<product>" not "<product>:proxy", that credential keys are SCREAMING_SNAKE, and that bc-base is pinned to "v0.3.1+"
    And the content of ".claude/skills/create-bc/SKILL.md" names that the full scaffold-to-repo-to-launch flow is experimental and not yet verified end-to-end, so the lead narrates and confirms with the user as it proceeds

    Examples:
      | shop_type | shop_name          | target                 |
      | lead      | shopsystem-product | /tmp/example-lead-shop |

  @scenario_hash:ebc6436bdbeea485
  Scenario Outline: each graduated PM skill is a member of the canonical lead skill-group and its "SKILL.md" is returned as package data
    Given the installed "shop-templates" distribution
    When I query the "shop-templates" public template-access surface for the canonical "lead" skill-group
    Then the access surface reports the skill-group has the member "<skill>"
    And for the member "<skill>" the access surface returns package-data "SKILL.md" contents byte-for-byte

    Examples:
      | skill                 |
      | discovery-dialogue    |
      | shaping               |
      | option-tradeoff       |
      | prioritization        |
      | problem-space-mapping |
      | product-narrative     |

  @scenario_hash:fd2e4444df9913e2
  Scenario Outline: the bootstrap pour writes each graduated PM skill into the target ".claude/skills/" tree
    Given an existing git repository at a target directory "<target>" with no ".claude/skills/" directory
    When I invoke the "shop-templates" bootstrap entry point with shop type "lead", shop name "shopsystem-product", and target directory "<target>"
    Then the exit code is 0
    And the target directory contains a file at ".claude/skills/<skill>/SKILL.md"
    And the content of ".claude/skills/<skill>/SKILL.md" names its terminal artifact for the lead-pm mode

    Examples:
      | skill                 | target                 |
      | discovery-dialogue    | /tmp/example-lead-shop |
      | shaping               | /tmp/example-lead-shop |
      | option-tradeoff       | /tmp/example-lead-shop |
      | prioritization        | /tmp/example-lead-shop |
      | problem-space-mapping | /tmp/example-lead-shop |
      | product-narrative     | /tmp/example-lead-shop |

  @scenario_hash:107bb9e2d7ddb530 @bc:shopsystem-templates
  Scenario Outline: the poured "<skill>" skill names fetching the "<type>" canonical template and validating its produced artifact via shop-knowledge before closing
    Given an existing git repository at a target directory "<target>" with no ".claude/skills/" directory
    When I invoke the "shop-templates" bootstrap entry point with shop type "lead", shop name "shopsystem-product", and target directory "<target>"
    Then the exit code is 0
    And the target directory contains a file at ".claude/skills/<skill>/SKILL.md"
    And the content of ".claude/skills/<skill>/SKILL.md" names fetching the canonical "<type>" template via "shop-knowledge template <type>" before or while producing the artifact
    And the content of ".claude/skills/<skill>/SKILL.md" names running "shop-knowledge validate" against the produced "<type>" document before the session closes
    And the content of ".claude/skills/<skill>/SKILL.md" names surfacing a validation failure to the product authority rather than closing the session silently

    Examples:
      | skill               | type                   | target                  |
      | discovery-dialogue  | intent-record          | /tmp/example-lead-shop  |
      | shaping             | candidate              | /tmp/example-lead-shop  |
      | option-tradeoff     | pdr                    | /tmp/example-lead-shop  |
      | option-tradeoff     | candidate              | /tmp/example-lead-shop  |
      | prioritization      | prioritization-record  | /tmp/example-lead-shop  |
      | product-narrative   | current-state          | /tmp/example-lead-shop  |

  @scenario_hash:cfdf2213b1c77bfb @bc:shopsystem-templates
  Scenario: product-narrative's README and site renderings are not gated by shop-knowledge validation because no typedef governs them
    Given an existing git repository at a target directory "/tmp/example-lead-shop" with no ".claude/skills/" directory
    When I invoke the "shop-templates" bootstrap entry point with shop type "lead", shop name "shopsystem-product", and target directory "/tmp/example-lead-shop"
    Then the exit code is 0
    And the content of ".claude/skills/product-narrative/SKILL.md" names that its README and site closing branches do not require "shop-knowledge validate", because README and site are not among the knowledge BC's eight recognized artifact types
    And the content of ".claude/skills/product-narrative/SKILL.md" names that only its current-state-revision closing branch requires "shop-knowledge validate"

  @scenario_hash:c0c636fb86c5579c @bc:shopsystem-templates
  Scenario: problem-space-mapping is not gated by shop-knowledge validation because no typedef exists for a problem-space-map artifact type
    Given an existing git repository at a target directory "/tmp/example-lead-shop" with no ".claude/skills/" directory
    When I invoke the "shop-templates" bootstrap entry point with shop type "lead", shop name "shopsystem-product", and target directory "/tmp/example-lead-shop"
    Then the exit code is 0
    And the target directory contains a file at ".claude/skills/problem-space-mapping/SKILL.md"
    And the content of ".claude/skills/problem-space-mapping/SKILL.md" does not name "shop-knowledge validate" or "shop-knowledge template" as a required closing step

  @scenario_hash:c47a92f5486ea893 @bc:shopsystem-templates
  Scenario Outline: each gated PM skill's closing protocol step names "shop-knowledge validate" literally, never a bare description, when describing the validation gate
    Given the poured "<skill>" SKILL.md's closing protocol step
    When I locate the step describing validating the produced artifact against its schema
    Then that step names the literal substring "shop-knowledge validate" on the same step
    And that step does not describe the validation using a bare verb — "check", "verify", "confirm", or "ensure" — without naming the literal substring "shop-knowledge validate" on the same step

    Examples:
      | skill              |
      | discovery-dialogue |
      | shaping            |
      | option-tradeoff    |
      | prioritization     |
      | product-narrative  |
