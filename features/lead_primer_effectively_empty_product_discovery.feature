@bc:shopsystem-templates @origin:lead-vglj
Feature: Lead primer drives effectively-empty detection and proactive product discovery

  The canonical lead primer (shop-templates package data, shop type "lead",
  served through read_claude_md_primer("lead")) must teach the router how to
  recognise a brand-new shop that has no product defined yet, and what to do
  about it. The DETECTION signal (a two-signal test) and the idempotent
  per-session RE-FIRE of the discovery nudge are pinned here. PDR-033 re-homes
  the discovery dialogue and the structured discovery-skill selection into the
  lead-pm main-session mode; the two scenarios that pinned router-level
  conduct/selection are RETIRED below and superseded by the lead-kz33
  PM-mode-entry primer scenarios (6273ec4a54466f6f, 41f7ce92d19ce620).

  @scenario_hash:00bdd6985ab94756
  Scenario: the canonical lead primer defines the effectively-empty / no-product-defined detection signal as a two-signal test requiring no product-bearing bead AND no product-bearing features/ scenario
    Given the "shop-templates" package ships a canonical "CLAUDE.md" primer template for shop type "lead" through its public template-access surface
    When I ask the package for that canonical primer body for shop type "lead"
    Then a non-empty template body is returned
    And the returned body contains a contiguous block defining an effectively-empty / no-product-defined repo state as a two-signal test requiring BOTH signals to hold
    And that block names the first signal as the beads registry carrying no product-bearing bead and the second signal as the "features/" tree carrying no product-bearing scenario
    And that block states the bootstrap scaffold — the canonical-managed files, "CLAUDE.md", the typed ".claude/" files, the role templates, the placeholder shop primer, and the initialized-but-empty beads registry — is ignored by the test and does not by itself defeat either signal

  # @scenario_hash:32b4fd22cfcf55d2 RETIRED (lead-kz33 / PDR-033)
  # Asserted the router conducts the effectively-empty product-discovery
  # conversation AT THE MAIN-AGENT / ROUTER LEVEL "consistent with the
  # product-authority discovery gate". PDR-033 retires that router-level gate
  # and re-homes the dialogue into the lead-pm main-session mode; superseded by
  # 6273ec4a54466f6f (router ENTERS lead-pm mode — the only interactive seat —
  # rather than conducting discovery at the router level).

  @scenario_hash:6273ec4a54466f6f @bc:shopsystem-templates
  Scenario: the canonical lead primer directs the router, on the effectively-empty state at session start or the idle-detection checkpoint, to enter the lead-pm main-session mode rather than declare idle
    Given the "shop-templates" package ships a canonical "CLAUDE.md" primer template for shop type "lead" through its public template-access surface
    When I ask the package for that canonical primer body for shop type "lead"
    Then a non-empty template body is returned
    And the returned body contains a contiguous block directing the router, on detecting the effectively-empty / no-product-defined state at session start or during the idle-detection checklist, to enter the lead-pm main-session mode and open a product-discovery conversation with the product authority rather than declaring idle
    And that block states the discovery conversation is held in the lead-pm main-session mode — the only interactive seat — and is not delegated to a non-interactive discovery subagent
    And that block states the router itself holds no product judgment; entering PM mode is the router's classification action, and the discovery dialogue belongs to the lead-pm mode

  @scenario_hash:bdba904f4f64f4a2
  Scenario: the canonical lead primer directs the router to re-fire the product-discovery prompt on each session while the effectively-empty state holds, and to suppress it only once the product surface is non-empty
    Given the "shop-templates" package ships a canonical "CLAUDE.md" primer template for shop type "lead" through its public template-access surface
    When I ask the package for that canonical primer body for shop type "lead"
    Then a non-empty template body is returned
    And the returned body contains a contiguous block directing the router to re-fire the product-discovery prompt on each session while the effectively-empty / no-product-defined state still holds
    And that block states the nudge is idempotent so that a previously dismissed prompt is re-issued the next session rather than fired only once
    And that block states the router suppresses the prompt only once the product surface becomes non-empty — that is, once either signal of the two-signal detection test no longer holds

  # @scenario_hash:46afaafc507e7d6f RETIRED (lead-kz33 / PDR-033)
  # Asserted the router PERFORMS the structured discovery-skill selection
  # ITSELF at the router / main-agent level, enumerating from a named
  # discovery-skill list (jobs-to-be-done, problem-framing-canvas,
  # opportunity-solution-tree, customer-journey-map). PDR-033 re-homes that
  # selection into the lead-pm main-session mode (driven by the lead-pm skill
  # group); superseded by 41f7ce92d19ce620 (brainstorming opener, selection
  # NOT a router-level triage and NOT a router-enumerated list).

  @scenario_hash:41f7ce92d19ce620 @bc:shopsystem-templates
  Scenario: the canonical lead primer directs the router to open the product-discovery conversation as a brainstorming opener inside PM mode, with the structured discovery-skill selection re-homed to the lead-pm mode
    Given the "shop-templates" package ships a canonical "CLAUDE.md" primer template for shop type "lead" through its public template-access surface
    When I ask the package for that canonical primer body for shop type "lead"
    Then a non-empty template body is returned
    And the returned body contains a contiguous block directing the router, on PM-mode entry for the effectively-empty state, to open the product-discovery conversation as a general brainstorming conversation first, before committing to any single structured discovery skill
    And that block states the selection of a structured discovery skill happens within the lead-pm main-session mode, driven by the lead-pm skill group, and is not a router-level triage step
    And that block does not require the router itself to enumerate or select from a named discovery-skill list, that responsibility having re-homed to the lead-pm mode
