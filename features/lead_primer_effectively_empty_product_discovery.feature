Feature: Lead primer drives effectively-empty detection and proactive product discovery

  The canonical lead primer (shop-templates package data, shop type "lead",
  served through read_claude_md_primer("lead")) must teach the router how to
  recognise a brand-new shop that has no product defined yet, and what to do
  about it: proactively open a product-discovery conversation with the product
  authority rather than declaring idle, re-firing the nudge idempotently each
  session until the product surface is non-empty, and running that discovery
  as a brainstorming opener that branches into one router-selected structured
  discovery skill. Each scenario pins one contiguous block of that guidance
  against the rendered lead primer body through the package's public
  template-access surface.

  @scenario_hash:00bdd6985ab94756 @bc:shopsystem-templates
  Scenario: the canonical lead primer defines the effectively-empty / no-product-defined detection signal as a two-signal test requiring no product-bearing bead AND no product-bearing features/ scenario
    Given the "shop-templates" package ships a canonical "CLAUDE.md" primer template for shop type "lead" through its public template-access surface
    When I ask the package for that canonical primer body for shop type "lead"
    Then a non-empty template body is returned
    And the returned body contains a contiguous block defining an effectively-empty / no-product-defined repo state as a two-signal test requiring BOTH signals to hold
    And that block names the first signal as the beads registry carrying no product-bearing bead and the second signal as the "features/" tree carrying no product-bearing scenario
    And that block states the bootstrap scaffold — the canonical-managed files, "CLAUDE.md", the typed ".claude/" files, the role templates, the placeholder shop primer, and the initialized-but-empty beads registry — is ignored by the test and does not by itself defeat either signal
