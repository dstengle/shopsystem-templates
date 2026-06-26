Feature: footing stores the GitHub PAT via a broker-local credential set
  agent-vault 0.32.0 'vault credential set' requires Member role and fails 'Member role
  required' through the owner's remote vault-scoped session; it works only broker-locally
  (docker exec into the broker). footing stores the collected PAT broker-locally and
  continues past the step without aborting.

@scenario_hash:7c96f830aa7c0a50 @bc:shopsystem-templates
Scenario: footing stores the collected GitHub PAT via a broker-local credential set and continues past the step
  Given footing has collected the GitHub PAT in the single up-front auth gate
  And the "<slug>" vault exists with no "GITHUB_TOKEN" credential yet
  When footing reaches the step that stores the PAT into the "<slug>" vault
  Then it sets the credential broker-locally by registering a broker-local owner session in the broker container and running "agent-vault vault credential set GITHUB_TOKEN=<pat> --vault <slug>" via "docker exec" into the broker, the same mechanism "bin/agent-vault-provision" uses
  And it does NOT set the credential through the owner's remote vault-scoped session, which fails "Member role required"
  And the stored "GITHUB_TOKEN" is a "static" credential retrievable by a broker-local "agent-vault vault credential get GITHUB_TOKEN --vault <slug>" returning the exact PAT value
  And footing continues past the store step without aborting on a "Member role required" error, the store either succeeding via the broker-local mechanism or degrading to a surfaced non-fatal warning rather than crashing the script
  And the single up-front human auth gate is not repeated for the credential
