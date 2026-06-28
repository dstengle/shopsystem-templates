Feature: bin/shop-shell carries zero product-specific literals — every product value is a single-sourced env-overridable reference (ADR-043 Phase 1 / ADR-046)
  The 2026-06-27 product-authority decision tightens ADR-043 Phase 1: the rendered
  bin/shop-shell spells NO product-specific literal. Every product coordinate — the
  container names, the docker network, the persistent data root, the agent-vault
  env-file path, the beads repo names, AND the framework launcher/leaf runtime image
  (ADR-046 amends the ADR-028 product-neutral-image exemption) — is a shell-variable
  reference whose default is read from the single bootstrap-rendered ops-coordinates
  artifact and is environment-overridable.

@scenario_hash:1885dea2b4550fde @bc:shopsystem-templates
Scenario: the rendered "bin/shop-shell" references the framework launcher/leaf-BC runtime image as an env-overridable shell variable whose default is sourced from the single ADR-043 ops-coordinates artifact — NOT as the fixed literal "ghcr.io/dstengle/shopsystem-bc-lead:latest" — overriding ADR-028's product-neutral-framework-image exemption per the 2026-06-27 product-authority decision
  Given an existing git repository at a target directory "/tmp/example-lead-shop" with no "bin/" subdirectory
  When I invoke the "shop-templates" bootstrap entry point with shop type "lead", shop name "dummyco", and target directory "/tmp/example-lead-shop"
  Then the exit code is 0
  And the body of "bin/shop-shell" passes the framework image to "docker run" and to the inner "bc-container launch --image" as a shell variable expansion, a "$"-prefixed reference, not as the fixed literal substring "ghcr.io/dstengle/shopsystem-bc-lead:latest"
  And that framework-image variable's default value is sourced from the single bootstrap-rendered ops-coordinates artifact (the ADR-043 D2 derivation root), not hardcoded in "bin/shop-shell"
  And that framework-image variable is environment-overridable, so an operator can point shop-shell at a different image reference without editing the script
  And the byte contents of "bin/shop-shell" for shop name "dummyco" contain no occurrence of the literal substring "ghcr.io/dstengle/shopsystem-bc-lead", confirming the framework image is no longer a baked product-neutral literal

