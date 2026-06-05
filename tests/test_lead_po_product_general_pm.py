"""BDD scenarios — lead-po product-general PM role with consumer/framework fork.

Pins scenario_hash:6465b30fe62fb935 from lead-y8rz dispatch.
Verifies that the lead-po template states the PM role is product-general and
that its discovery inputs fork between consumer and framework instances.
"""
from pytest_bdd import scenarios

scenarios("../features/lead_po_product_general_pm.feature")
