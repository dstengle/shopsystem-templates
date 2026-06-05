"""BDD scenarios — lead-po identity-precedes-procedure structural integrity.

Pins scenario_hash:662c5822dbc6a896 from lead-y8rz dispatch.
Verifies that the empowered-PM expansion preserves the identity-precedes-procedure
ordering in the lead-po template: the identity header and posture header precede
all CLI mechanics, and all PM discipline headings are at depth ### or deeper.
"""
from pytest_bdd import scenarios

scenarios("../features/lead_po_identity_precedes_procedure.feature")
