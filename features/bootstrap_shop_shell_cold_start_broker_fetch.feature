Feature: bootstrap of a lead shop writes bin/shop-shell so that on a COLD start — the agent-vault broker container running and ZERO BC containers present — the agent-vault MITM CA is obtained FROM THE BROKER via "agent-vault ca fetch" (multi-line PEM captured intact, ungated by broker-token presence) and the brokered shell launches with that trusted CA, requiring NO BC donor; donor-BC recovery is demoted to a lower-priority fallback (lead-4him, tightening additive to scenario 183 @scenario_hash:2adc62a25c401e4b and scenario 172 @scenario_hash:5335c39eb06f7493, whose assertions still hold)

  @scenario_hash:513cf8ea1a8ff4e9 @bc:shopsystem-templates
  Scenario Outline: bootstrap of a "lead" shop named "<slug>" writes "bin/shop-shell" so that on a COLD start — the agent-vault broker container running and ZERO BC containers present — it obtains the agent-vault MITM CA FROM THE BROKER via "agent-vault ca fetch" (multi-line PEM captured intact, ungated by broker-token presence) and launches the brokered shell with that trusted CA, requiring NO BC donor; donor-BC recovery is only a lower-priority fallback (additive to scenario 183 @scenario_hash:2adc62a25c401e4b and scenario 172 @scenario_hash:5335c39eb06f7493, whose assertions still hold)
    Given an existing git repository at a target directory "/tmp/example-lead-shop" with no "bin/" subdirectory
    When I invoke the "shop-templates" bootstrap entry point with shop type "lead", shop name "<slug>", and target directory "/tmp/example-lead-shop"
    Then the exit code is 0
    And the body of "bin/shop-shell", on the path taken when "AGENT_VAULT_CA_PEM" is empty or unset, sources the agent-vault CA from the running broker by the literal substring "agent-vault ca fetch" executed against the agent-vault container, and this broker-fetch path does not depend on any BC container being present
    And the body of "bin/shop-shell" captures the multi-line PEM returned by that broker fetch intact into the environment variable "AGENT_VAULT_CA_PEM" — the capture is not truncated to a single line — and the resulting CA material is passed into the launched container by referencing "AGENT_VAULT_CA_PEM" on the "docker run" invocation
    And the body of "bin/shop-shell" does not gate the broker-fetch of the CA on the presence of the broker token: the "agent-vault ca fetch" path is reachable even when only the broker address is known
    And the body of "bin/shop-shell" orders CA sourcing so that the broker fetch is attempted before, or independently of, any donor-BC recovery that inspects existing containers — donor-BC recovery (the literal substring "docker inspect") is present only as a lower-priority fallback and is not required for the CA to be obtained on a cold start
    And the body of "bin/shop-shell" reaches the "docker run" invocation that launches the brokered shell with a non-empty "AGENT_VAULT_CA_PEM" on the cold-start path where the broker is reachable and zero BC containers are present, so a fresh operator gets a working shell with a trusted CA and no donor BC

    Examples:
      | slug       |
      | shopsystem |
      | dummyco    |
