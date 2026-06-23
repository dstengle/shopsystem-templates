Feature: shop-templates update — ops scaffolding coverage

  @scenario_hash:3c496f8858b6b033 @bc:shopsystem-templates
  Scenario: "shop-templates update" against a "lead" shop does not modify the ops scaffolding files ("compose.yaml", "bin/shop-shell") under any circumstances on the success path, because per PDR-003 path F's two-bucket model those files are shop-owned (not canonical-managed) — this is the ops-scaffolding analogue of scenarios 86, 87, and 88 (".claude/shop/" non-touch invariants)
    Given an existing git repository at a target directory "/tmp/example-lead-shop" that was previously bootstrapped as a "lead" shop named "shopsystem-product"
    And the file at "compose.yaml" in the target directory has been hand-edited so that its byte contents are not equal to the canonical "compose.yaml" template body for shop type "lead"
    And the file at "bin/shop-shell" in the target directory has been hand-edited so that its byte contents are not equal to the canonical "bin/shop-shell" template body for shop type "lead"
    And I record the byte contents of those two files before the invocation
    When I invoke the "shop-templates" update entry point against the target directory "/tmp/example-lead-shop"
    Then the exit code is 0
    And after the invocation the byte contents of the file at "compose.yaml" in the target directory equal the recorded byte contents
    And after the invocation the byte contents of the file at "bin/shop-shell" in the target directory equal the recorded byte contents

  @scenario_hash:29caed838aebe9f7 @bc:shopsystem-templates
  Scenario Outline: "shop-templates update" against a "lead" shop emits an advisory on stderr (naming the file, the drift, and the canonical refresh path) for each ops scaffolding file whose on-disk content differs from the current canonical template — surfacing canonical evolution to the operator without violating the shop-owned-file rule from scenario 139; this is the ops-scaffolding analogue of scenario 132's "name.md" advisory pattern
    Given an existing git repository at a target directory "/tmp/example-lead-shop" that was previously bootstrapped as a "lead" shop named "shopsystem-product"
    And the file at "<path>" in the target directory has byte contents that differ from the current canonical "<path>" template body for shop type "lead"
    And I record the byte contents of the file at "<path>" in the target directory before the invocation
    When I invoke the "shop-templates" update entry point against the target directory "/tmp/example-lead-shop"
    Then the exit code is 0
    And after the invocation the file at "<path>" in the target directory has byte-for-byte the same on-disk contents as before the invocation
    And stderr contains an advisory naming the file path "<path>" and noting that the file has drifted from canonical
    And the advisory explicitly notes that "shop-templates update" did not modify the shop-owned file
    And the advisory names a means for the operator to view the canonical body (e.g., the literal substring "shop-templates show" or an equivalent operator-visible path the canonical body can be read from)

    Examples:
      | path                          |
      | compose.yaml                  |
      | bin/shop-shell                |

  @scenario_hash:953b2102a6924c28 @bc:shopsystem-templates
  Scenario Outline: "shop-templates update" against a "lead" shop whose ops scaffolding files match the current canonical template body byte-for-byte exits zero, emits no advisory for those files on stderr, and leaves on-disk byte contents and mtimes unchanged — the same idempotence guarantee scenario 89 pins for the canonical-managed surface, extended to the shop-owned ops scaffolding for the "already up to date" case
    Given an existing git repository at a target directory "/tmp/example-lead-shop" that was previously bootstrapped as a "lead" shop named "shopsystem-product"
    And the file at "<path>" in the target directory has byte contents equal to the current canonical "<path>" template body for shop type "lead"
    And I record the byte contents and mtime of the file at "<path>" in the target directory before the invocation
    When I invoke the "shop-templates" update entry point against the target directory "/tmp/example-lead-shop"
    Then the exit code is 0
    And after the invocation the byte contents of the file at "<path>" in the target directory equal the recorded byte contents
    And after the invocation the mtime of the file at "<path>" in the target directory equals the recorded mtime
    And stderr does not contain any advisory naming the file path "<path>"

    Examples:
      | path                          |
      | compose.yaml                  |
      | bin/shop-shell                |

