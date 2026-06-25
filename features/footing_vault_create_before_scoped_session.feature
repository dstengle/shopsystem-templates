Feature: footing creates the product vault before minting a scoped session
  footing's auth gate mints a vault-scoped session and creates the Claude OAuth
  proposal against the product-slug vault, but never created that vault — so the
  mint failed with 'Vault not found'. footing now creates the vault idempotently
  before the first vault token / proposal call against it.

@scenario_hash:04426cc490f7a388 @bc:shopsystem-templates
Scenario: footing creates the vault before minting a vault-scoped session in the auth gate
  Given the footing bootstrap script is run for a product whose broker holds no vault for the product slug yet
  And the owner account has just been created via "agent-vault auth register"
  When the script reaches the Claude OAuth provisioning sequence in its auth gate
  Then it runs "agent-vault vault create" for the product-slug vault before the first "agent-vault vault token" or "agent-vault vault proposal" call against that vault
  And the vault-scoped session mint succeeds without a "Vault not found" error
  And the vault creation is idempotent, completing without failure when the vault already exists
