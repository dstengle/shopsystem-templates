"""BDD scenarios — lead-po strategy-before-backlog and specification-as-contract sufficiency criteria.

Pins scenario_hash:6773a984439f2a9e from lead-y8rz dispatch.
Verifies that the strategy before backlog and specification as the contract
discipline blocks in the lead-po template carry explicit, measurable
sufficiency criteria.
"""
from pytest_bdd import scenarios

scenarios("../features/lead_po_strategy_spec_criteria.feature")
