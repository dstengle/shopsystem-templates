Feature: shop-templates bootstrap CLI surface (brief 002, items A-E)

  @scenario_hash:0f50666b7e86f1ba @bc:shopsystem-templates
  Scenario: shop-templates exposes a bootstrap entry point that accepts a shop type, a shop name, and a target directory and scaffolds the named existing repository
    Given an existing git repository at a target directory "/tmp/example-shop"
    And the target directory contains no ".claude/agents/" directory and no ".beads/" directory and no top-level "CLAUDE.md" and no top-level ".gitignore"
    When I invoke the "shop-templates" bootstrap entry point with shop type "bc", shop name "example-shop", and target directory "/tmp/example-shop"
    Then the exit code is 0
    And the invocation completes without prompting for any input on stdin
    And stderr does not contain any prompt-style text such as "y/n" or "press enter"
    And after the invocation the target directory contains a ".claude/agents/" directory, a ".beads/" directory, a top-level "CLAUDE.md", and a top-level ".gitignore"

  @scenario_hash:8893150c874eb179 @bc:shopsystem-templates
  Scenario Outline: the bootstrap entry point accepts the same shape of arguments (shop type, shop name, target directory) for both shop types and exits 0 when invoked against an empty existing repository
    Given an existing git repository at a target directory "<target>"
    And the target directory contains no ".claude/agents/" directory and no ".beads/" directory and no top-level "CLAUDE.md" and no top-level ".gitignore"
    When I invoke the "shop-templates" bootstrap entry point with shop type "<shop_type>", shop name "<shop_name>", and target directory "<target>"
    Then the exit code is 0
    And the invocation completes without prompting for any input on stdin

    Examples:
      | shop_type | shop_name               | target                       |
      | bc        | shopsystem-messaging    | /tmp/example-bc-shop         |
      | lead      | shopsystem-product      | /tmp/example-lead-shop       |

  @scenario_hash:d6e935bca62d0039 @bc:shopsystem-templates
  Scenario: the bootstrap entry point exits non-zero and writes a usage diagnostic to stderr when invoked without a shop type, with no default applied
    Given an existing git repository at a target directory "/tmp/example-shop"
    When I invoke the "shop-templates" bootstrap entry point with a shop name and a target directory but with no shop type argument
    Then the exit code is non-zero
    And the target directory still contains no ".claude/agents/" directory and no ".beads/" directory and no top-level "CLAUDE.md" and no top-level ".gitignore"
    And stderr names "shop type" (or an equivalent phrase identifying the missing argument) as the missing required input
    And stderr lists the accepted shop-type values "bc" and "lead" so the caller can recover

  @scenario_hash:7941cdc591cd2c3b @bc:shopsystem-templates
  Scenario: the bootstrap entry point exits non-zero when invoked with a shop type that is neither "bc" nor "lead", names the offending input on stderr, and writes no scaffold
    Given an existing git repository at a target directory "/tmp/example-shop"
    And the target directory contains no ".claude/agents/" directory and no ".beads/" directory and no top-level "CLAUDE.md" and no top-level ".gitignore"
    When I invoke the "shop-templates" bootstrap entry point with shop type "neither-bc-nor-lead", shop name "example-shop", and target directory "/tmp/example-shop"
    Then the exit code is non-zero
    And stderr names the offending shop-type value "neither-bc-nor-lead"
    And stderr lists the accepted shop-type values "bc" and "lead"
    And the target directory still contains no ".claude/agents/" directory and no ".beads/" directory and no top-level "CLAUDE.md" and no top-level ".gitignore"

  @scenario_hash:6830d0f1100055a0 @bc:shopsystem-templates
  Scenario Outline: bootstrap writes the canonical role-prompt copies for the shop type into ".claude/agents/", and writes no other agent files
    Given an existing git repository at a target directory "<target>" with no ".claude/agents/" directory
    When I invoke the "shop-templates" bootstrap entry point with shop type "<shop_type>", shop name "<shop_name>", and target directory "<target>"
    Then the exit code is 0
    And the target directory contains a file at ".claude/agents/<role_a>.md" whose content equals the package-data file contents of the canonical "<role_a>" template byte-for-byte
    And the target directory contains a file at ".claude/agents/<role_b>.md" whose content equals the package-data file contents of the canonical "<role_b>" template byte-for-byte
    And the directory ".claude/agents/" in the target directory contains no files other than those two

    Examples:
      | shop_type | shop_name               | target                       | role_a            | role_b            |
      | bc        | shopsystem-messaging    | /tmp/example-bc-shop         | bc-implementer    | bc-reviewer       |
      | lead      | shopsystem-product      | /tmp/example-lead-shop       | lead-po           | lead-architect    |

  @scenario_hash:b1bd59e48496d438 @bc:shopsystem-templates
  Scenario Outline: bootstrap writes a top-level "CLAUDE.md" to the target directory for both shop types
    Given an existing git repository at a target directory "<target>" with no top-level "CLAUDE.md"
    When I invoke the "shop-templates" bootstrap entry point with shop type "<shop_type>", shop name "<shop_name>", and target directory "<target>"
    Then the exit code is 0
    And the target directory contains a top-level file named "CLAUDE.md"
    And that file is non-empty

    Examples:
      | shop_type | shop_name               | target                       |
      | bc        | shopsystem-messaging    | /tmp/example-bc-shop         |
      | lead      | shopsystem-product      | /tmp/example-lead-shop       |

  @scenario_hash:0c6f1c5d9bc4226e @bc:shopsystem-templates
  Scenario: bootstrap initializes the ".beads/" directory in the target directory by invoking "bd init" as a subprocess, not by importing or reproducing bd's internal behavior in-process
    Given an existing git repository at a target directory "/tmp/example-shop" with no ".beads/" directory
    When I invoke the "shop-templates" bootstrap entry point with shop type "bc", shop name "example-shop", and target directory "/tmp/example-shop"
    Then the exit code is 0
    And the target directory contains a ".beads/" directory
    And during the invocation a subprocess named "bd" was executed with first argument "init"
    And during the invocation no symbol from a Python module whose top-level package name is "bd" or "beads" was imported into the running "shop-templates" process
    And during the invocation the contents of the ".beads/" directory were written by that "bd" subprocess and not by file-writes issued directly from the "shop-templates" process

  @scenario_hash:6b0006b5fc93b637 @bc:shopsystem-templates
  Scenario Outline: bootstrap writes a top-level ".gitignore" to the target directory for both shop types
    Given an existing git repository at a target directory "<target>" with no top-level ".gitignore"
    When I invoke the "shop-templates" bootstrap entry point with shop type "<shop_type>", shop name "<shop_name>", and target directory "<target>"
    Then the exit code is 0
    And the target directory contains a top-level file named ".gitignore"
    And that file is non-empty

    Examples:
      | shop_type | shop_name               | target                       |
      | bc        | shopsystem-messaging    | /tmp/example-bc-shop         |
      | lead      | shopsystem-product      | /tmp/example-lead-shop       |

  @scenario_hash:69496ea1e5c82ed3 @bc:shopsystem-templates
  Scenario Outline: bootstrap does not create any of the explicitly out-of-scope paths in the target directory, regardless of shop type
    Given an existing git repository at a target directory "<target>" containing none of "inbox/", "outbox/", "features/", "tests/", "pyproject.toml", or "README.md"
    When I invoke the "shop-templates" bootstrap entry point with shop type "<shop_type>", shop name "<shop_name>", and target directory "<target>"
    Then the exit code is 0
    And the target directory contains no directory named "inbox/"
    And the target directory contains no directory named "outbox/"
    And the target directory contains no directory named "features/"
    And the target directory contains no directory named "tests/"
    And the target directory contains no top-level file named "pyproject.toml"
    And the target directory contains no top-level file named "README.md"

    Examples:
      | shop_type | shop_name               | target                       |
      | bc        | shopsystem-messaging    | /tmp/example-bc-shop         |
      | lead      | shopsystem-product      | /tmp/example-lead-shop       |

  @scenario_hash:b8dd3bbc45674f90 @bc:shopsystem-templates
  Scenario: shop-templates exposes an update entry point that re-pours every bootstrap-managed agent file in the target directory from the current canonical package data
    Given an existing git repository at a target directory "/tmp/example-shop" that was previously bootstrapped as a "bc" shop named "example-shop"
    And the file at ".claude/agents/bc-implementer.md" in the target directory equals the current canonical "bc-implementer" template package-data file contents byte-for-byte
    And the file at ".claude/agents/bc-reviewer.md" in the target directory equals the current canonical "bc-reviewer" template package-data file contents byte-for-byte
    When I invoke the "shop-templates" update entry point against the target directory "/tmp/example-shop"
    Then the exit code is 0
    And after the invocation the file at ".claude/agents/bc-implementer.md" in the target directory still equals the current canonical "bc-implementer" template package-data file contents byte-for-byte
    And after the invocation the file at ".claude/agents/bc-reviewer.md" in the target directory still equals the current canonical "bc-reviewer" template package-data file contents byte-for-byte

  @scenario_hash:32d21a2277dbbc94 @bc:shopsystem-templates
  Scenario: update replaces a stale bootstrap-managed agent file with the current canonical content when the package-data template has changed since the shop was bootstrapped
    Given an existing git repository at a target directory "/tmp/example-shop" that was previously bootstrapped as a "bc" shop named "example-shop"
    And the file at ".claude/agents/bc-implementer.md" in the target directory holds an older version of the "bc-implementer" canonical template content
    And the current canonical "bc-implementer" template package-data file contents differ from that older version
    When I invoke the "shop-templates" update entry point against the target directory "/tmp/example-shop"
    Then the exit code is 0
    And after the invocation the file at ".claude/agents/bc-implementer.md" in the target directory equals the current canonical "bc-implementer" template package-data file contents byte-for-byte

  @scenario_hash:264322ae65312bc7 @bc:shopsystem-templates
  Scenario: invoking update against a shop whose bootstrap-managed files are already byte-equal to the current canonical templates leaves every file on disk unchanged
    Given an existing git repository at a target directory "/tmp/example-shop" that was previously bootstrapped as a "bc" shop named "example-shop"
    And every file in ".claude/agents/" in the target directory equals the corresponding current canonical template package-data file contents byte-for-byte
    And I record the on-disk byte contents and modification metadata of every file under the target directory before the invocation
    When I invoke the "shop-templates" update entry point against the target directory "/tmp/example-shop"
    Then the exit code is 0
    And after the invocation every file under the target directory has byte-for-byte the same on-disk contents as before the invocation

  @scenario_hash:03b4e3fa31d72031 @bc:shopsystem-templates
  Scenario: update brings the set of bootstrap-managed agent files in the target directory into alignment with the current canonical role set for the shop type — adding canonical files that are missing and removing managed files whose canonical template no longer exists
    Given an existing git repository at a target directory "/tmp/example-shop" that was previously bootstrapped as a "bc" shop named "example-shop"
    And the current canonical role set for shop type "bc" is exactly the names listed by "shop-templates list" filtered to those that the bootstrap surface treats as "bc" roles
    And the directory ".claude/agents/" in the target directory contains a file named "<former-bc-role>.md" whose name is not in that current canonical role set
    And the directory ".claude/agents/" in the target directory does not contain a file named "<new-bc-role>.md" whose name is in that current canonical role set
    When I invoke the "shop-templates" update entry point against the target directory "/tmp/example-shop"
    Then the exit code is 0
    And after the invocation the directory ".claude/agents/" in the target directory does not contain a file named "<former-bc-role>.md"
    And after the invocation the directory ".claude/agents/" in the target directory contains a file named "<new-bc-role>.md" whose content equals the current canonical "<new-bc-role>" template package-data file contents byte-for-byte
    And after the invocation the set of files in ".claude/agents/" whose names match the canonical role-set naming convention equals the current canonical role set for shop type "bc"

  @scenario_hash:56a0ac7107ba5c15 @bc:shopsystem-templates
  Scenario: update does not overwrite or otherwise modify the target directory's top-level "CLAUDE.md", even when the canonical "CLAUDE.md" primer template has changed since the shop was bootstrapped
    Given an existing git repository at a target directory "/tmp/example-shop" that was previously bootstrapped as a "bc" shop named "example-shop"
    And the file at "CLAUDE.md" in the target directory has been edited since bootstrap so that its content includes a literal shop-authored sentence that the canonical "CLAUDE.md" primer template does not contain
    And I record the byte contents of the file at "CLAUDE.md" in the target directory before the invocation
    When I invoke the "shop-templates" update entry point against the target directory "/tmp/example-shop"
    Then the exit code is 0
    And after the invocation the file at "CLAUDE.md" in the target directory has byte-for-byte the same on-disk contents as before the invocation

  @scenario_hash:ca0f0a249d025267 @bc:shopsystem-templates
  Scenario: update does not overwrite or otherwise modify the target directory's top-level ".gitignore", even when the canonical ".gitignore" template has changed since the shop was bootstrapped
    Given an existing git repository at a target directory "/tmp/example-shop" that was previously bootstrapped as a "bc" shop named "example-shop"
    And the file at ".gitignore" in the target directory has been edited since bootstrap so that its content includes a shop-authored entry that the canonical ".gitignore" template does not contain
    And I record the byte contents of the file at ".gitignore" in the target directory before the invocation
    When I invoke the "shop-templates" update entry point against the target directory "/tmp/example-shop"
    Then the exit code is 0
    And after the invocation the file at ".gitignore" in the target directory has byte-for-byte the same on-disk contents as before the invocation

  @scenario_hash:3f4d7d2256a97ae7 @bc:shopsystem-templates
  Scenario: update does not read from, write to, or invoke any bd subcommand against the target directory's ".beads/" directory
    Given an existing git repository at a target directory "/tmp/example-shop" that was previously bootstrapped as a "bc" shop named "example-shop"
    And I record the byte contents of every file under ".beads/" in the target directory before the invocation
    When I invoke the "shop-templates" update entry point against the target directory "/tmp/example-shop"
    Then the exit code is 0
    And during the invocation no subprocess named "bd" was executed
    And after the invocation every file under ".beads/" in the target directory has byte-for-byte the same on-disk contents as before the invocation

  @scenario_hash:efae77e534588357 @bc:shopsystem-templates
  Scenario: update does not create, remove, or modify any path in the target directory that is outside the bootstrap-managed set
    Given an existing git repository at a target directory "/tmp/example-shop" that was previously bootstrapped as a "bc" shop named "example-shop"
    And the target directory additionally contains a non-empty file at "features/example.feature" authored by the shop
    And the target directory additionally contains a non-empty file at "tests/test_example.py" authored by the shop
    And the target directory additionally contains a non-empty top-level file at "pyproject.toml" authored by the shop
    And the target directory additionally contains a non-empty top-level file at "README.md" authored by the shop
    And I record the byte contents of those four files before the invocation
    When I invoke the "shop-templates" update entry point against the target directory "/tmp/example-shop"
    Then the exit code is 0
    And after the invocation each of those four files has byte-for-byte the same on-disk contents as before the invocation
    And after the invocation the target directory contains no path that did not exist before the invocation other than paths inside ".claude/agents/"

  @scenario_hash:575c0f31c5e6e8e6 @bc:shopsystem-templates
  Scenario: update overwrites hand-edits made to a bootstrap-managed agent file, restoring it to the current canonical template content
    Given an existing git repository at a target directory "/tmp/example-shop" that was previously bootstrapped as a "bc" shop named "example-shop"
    And the file at ".claude/agents/bc-implementer.md" in the target directory has been hand-edited so that its content differs from the current canonical "bc-implementer" template package-data file contents
    When I invoke the "shop-templates" update entry point against the target directory "/tmp/example-shop"
    Then the exit code is 0
    And after the invocation the file at ".claude/agents/bc-implementer.md" in the target directory equals the current canonical "bc-implementer" template package-data file contents byte-for-byte

  @scenario_hash:0cce58eb573d3c91 @bc:shopsystem-templates
  Scenario Outline: shopsystem-templates ships a canonical "CLAUDE.md" primer template for each shop type, accessible through the same package-data surface as the role-prompt templates
    When I ask the "shop-templates" package for the canonical "CLAUDE.md" primer template for shop type "<shop_type>" through its public template-access surface
    Then a non-empty template body is returned
    And the returned body is the source of truth from which the bootstrap entry point generates the target directory's top-level "CLAUDE.md" for a shop of type "<shop_type>"
    And the returned body is not read from any path under this product's top-level working directory at lookup time

    Examples:
      | shop_type |
      | bc        |
      | lead      |

  @scenario_hash:a15dac2f87549b8a @bc:shopsystem-templates
  Scenario Outline: the top-level "CLAUDE.md" that bootstrap writes into the target directory names the shop's own identity — its shop name and its role set — and is consistent with the canonical primer template for the chosen shop type
    Given an existing git repository at a target directory "<target>" with no top-level "CLAUDE.md"
    When I invoke the "shop-templates" bootstrap entry point with shop type "<shop_type>", shop name "<shop_name>", and target directory "<target>"
    Then the exit code is 0
    And the target directory contains a top-level file named "CLAUDE.md"
    And the content of that file contains the literal substring "<shop_name>"
    And the content of that file names every role in the canonical role set for shop type "<shop_type>" by name
    And the content of that file does not name any role from the canonical role set of the other shop type

    Examples:
      | shop_type | shop_name               | target                       |
      | bc        | shopsystem-messaging    | /tmp/example-bc-shop         |
      | lead      | shopsystem-product      | /tmp/example-lead-shop       |
