@bc_internal
Feature: shopsystem-templates — canonical lead primer PDR-033 re-homing

@scenario_hash:e813a6f3a3b575ea @bc:shopsystem-templates
  Scenario: the canonical lead primer carries the PM-mode-entry classification standing rule in place of the retired discovery gate
    Given the "shop-templates" package ships a canonical "CLAUDE.md" primer template for shop type "lead" through its public template-access surface
    When I ask the package for that canonical primer body for shop type "lead"
    Then a non-empty template body is returned
    And the returned body carries a standing rule that classifies input which is directional, exploratory, ambiguous, or multi-option as PM-mode entry — the router enters the lead-pm main-session mode rather than dispatching a discovery subagent
    And that standing rule directs input that is a committed contract task to the lead-po and technical or dispatch work to the existing routes
    And that standing rule states that when the router is unsure between PM and PO it prefers PM, because a mis-route to PM costs one session while a mis-route to PO produces an unanchored brief
    And that standing rule requires the router, on PM-mode entry, to ensure a session record is opened and, on exit, to verify it is closed with a non-empty produced or revised list before releasing the turn flow
    And that standing rule states the router holds no product judgment — option framing, brainstorm facilitation, and intent probing live in the lead-pm mode, not at the router
    And the returned body no longer carries the retired router-level product-authority discovery gate that required the router to conduct the discovery dialogue itself or cite a brief before dispatching a discovery subagent
    And the returned body still carries the idle-detection and choice-suppression standing rules unaltered

@scenario_hash:6273ec4a54466f6f @bc:shopsystem-templates
  Scenario: the canonical lead primer directs the router, on the effectively-empty state at session start or the idle-detection checkpoint, to enter the lead-pm main-session mode rather than declare idle
    Given the "shop-templates" package ships a canonical "CLAUDE.md" primer template for shop type "lead" through its public template-access surface
    When I ask the package for that canonical primer body for shop type "lead"
    Then a non-empty template body is returned
    And the returned body contains a contiguous block directing the router, on detecting the effectively-empty / no-product-defined state at session start or during the idle-detection checklist, to enter the lead-pm main-session mode and open a product-discovery conversation with the product authority rather than declaring idle
    And that block states the discovery conversation is held in the lead-pm main-session mode — the only interactive seat — and is not delegated to a non-interactive discovery subagent
    And that block states the router itself holds no product judgment; entering PM mode is the router's classification action, and the discovery dialogue belongs to the lead-pm mode

@scenario_hash:41f7ce92d19ce620 @bc:shopsystem-templates
  Scenario: the canonical lead primer directs the router to open the product-discovery conversation as a brainstorming opener inside PM mode, with the structured discovery-skill selection re-homed to the lead-pm mode
    Given the "shop-templates" package ships a canonical "CLAUDE.md" primer template for shop type "lead" through its public template-access surface
    When I ask the package for that canonical primer body for shop type "lead"
    Then a non-empty template body is returned
    And the returned body contains a contiguous block directing the router, on PM-mode entry for the effectively-empty state, to open the product-discovery conversation as a general brainstorming conversation first, before committing to any single structured discovery skill
    And that block states the selection of a structured discovery skill happens within the lead-pm main-session mode, driven by the lead-pm skill group, and is not a router-level triage step
    And that block does not require the router itself to enumerate or select from a named discovery-skill list, that responsibility having re-homed to the lead-pm mode

