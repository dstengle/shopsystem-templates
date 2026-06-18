Feature: bootstrap renders .beads/config.yaml with the product beads remote and issue prefix

  Bootstrap initializes .beads/ via a `bd init` subprocess. On top of that
  it renders .beads/config.yaml so the new shop's bd tracker is wired to the
  product beads remote (sync.remote) and carries the product-derived
  issue_prefix — so a freshly bootstrapped shop's tracker syncs to the right
  remote and stamps issues with the right prefix without a manual follow-up
  step. (tmpl-4k7 / PDR-019 U5 / ADR-040.)

  @scenario_hash:9e15d8cfd55b9541 @bc:shopsystem-templates
  Scenario: shop-templates bootstrap renders the beads config with the sync remote and issue prefix
    Given an existing git repository at a target directory "<target>"
    When I invoke the "shop-templates" bootstrap entry point with shop type "lead", shop name "<shop_name>", and target directory "<target>"
    Then the exit code is 0
    And the file ".beads/config.yaml" in the target directory sets "sync.remote" to the product beads remote
    And the file ".beads/config.yaml" in the target directory sets "issue_prefix" to the product-derived prefix
