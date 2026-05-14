Feature: Bootstrap CLI surface — bd-init side-effect closure (lead-k8v round 2)

  @scenario_hash:32d99f6d4a2dad37 @bc:shopsystem-templates
  Scenario Outline: bootstrap invokes "bd init" with the "--skip-agents" flag so bd's own AGENTS.md and Claude settings generation is suppressed and the shop's canonical agent surface is the sole source of agent-prompt content
    Given an existing git repository at a target directory "<target>" with no ".beads/" directory
    When I invoke the "shop-templates" bootstrap entry point with shop type "<shop_type>", shop name "<shop_name>", and target directory "<target>"
    Then the exit code is 0
    And the target directory contains a ".beads/" directory
    And during the invocation a subprocess named "bd" was executed with first argument "init"
    And the argument list passed to that "bd" subprocess contains the exact token "--skip-agents"

    Examples:
      | shop_type | shop_name               | target                       |
      | bc        | shopsystem-messaging    | /tmp/example-bc-shop         |
      | lead      | shopsystem-product      | /tmp/example-lead-shop       |

  @scenario_hash:5ec07c275350ba81 @bc:shopsystem-templates
  Scenario Outline: the canonical "CLAUDE.md" primer template for each shop type references the bd (beads) discipline that the shop is expected to follow, naming "bd prime" as the entry point a reader runs to learn the workflow
    When I ask the "shop-templates" package for the canonical "CLAUDE.md" primer template for shop type "<shop_type>" through its public template-access surface
    Then a non-empty template body is returned
    And the returned body contains the literal substring "bd prime"
    And the returned body contains at least one instruction directing the reader to run a "bd" subcommand as part of the shop's working discipline

    Examples:
      | shop_type |
      | bc        |
      | lead      |

  @scenario_hash:2afb5cba3ea3de25 @bc:shopsystem-templates
  Scenario Outline: the top-level "CLAUDE.md" that bootstrap writes into the target directory references the bd (beads) discipline by naming "bd prime", for both shop types, so the bootstrapped shop is self-describing about its working discipline without depending on bd's own AGENTS.md generation
    Given an existing git repository at a target directory "<target>" with no top-level "CLAUDE.md"
    When I invoke the "shop-templates" bootstrap entry point with shop type "<shop_type>", shop name "<shop_name>", and target directory "<target>"
    Then the exit code is 0
    And the target directory contains a top-level file named "CLAUDE.md"
    And the content of that file contains the literal substring "bd prime"

    Examples:
      | shop_type | shop_name               | target                       |
      | bc        | shopsystem-messaging    | /tmp/example-bc-shop         |
      | lead      | shopsystem-product      | /tmp/example-lead-shop       |
