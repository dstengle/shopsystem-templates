"""BDD scenarios — lead-po PM discipline sufficiency criteria.

Pins scenario_hash:25038c88fec521ba from lead-y8rz dispatch.
Verifies that the problem discovery & selection and outcome ownership
discipline blocks in the lead-po template carry explicit, measurable
sufficiency criteria.
"""
from pytest_bdd import scenarios

scenarios("../features/lead_po_pm_discipline_criteria.feature")
