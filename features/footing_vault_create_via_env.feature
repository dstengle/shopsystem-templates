Feature: footing provisions the product vault via AGENT_VAULT_ADDR env (not --address)
  footing creates the product-slug vault before the scoped-session mint. `vault create`
  rejects an --address flag and reads the broker address from AGENT_VAULT_ADDR; footing
  passes no --address and does not mask the create — tolerating only an idempotent
  already-exists and surfacing any genuine failure — so the vault exists before the
  first `vault token` and the mint succeeds.

@scenario_hash:a3242f1f65e52caf @bc:shopsystem-templates
Scenario: footing provisions the product-slug vault via AGENT_VAULT_ADDR env so the scoped-session mint finds it
  Given footing has exported AGENT_VAULT_ADDR with the in-network broker address and AGENT_VAULT_VAULT set to the product slug
  And the broker holds no vault for the product slug yet
  And the broker's "agent-vault vault create" subcommand rejects an "--address" flag with "unknown flag: --address" and reads its broker address only from the AGENT_VAULT_ADDR environment
  When footing reaches the vault-provisioning step that precedes the first "agent-vault vault token --vault <slug>" call in the auth gate
  Then footing runs its rendered "agent-vault vault create <slug>" with the exact flags footing passes, carrying the broker address through the AGENT_VAULT_ADDR environment and NOT through an "--address" flag
  And that create invocation does not pass "--address" to "agent-vault vault create"
  And the create's exit status is not swallowed by a "2>/dev/null || true" mask, so an "unknown flag: --address" or other genuine create failure aborts footing with a surfaced diagnostic rather than continuing
  And a create that fails only because the slug vault already exists is tolerated as idempotent and footing continues
  And after the provisioning step the <slug> vault exists in the broker and "agent-vault vault token --vault <slug>" succeeds with no "Vault not found" error
