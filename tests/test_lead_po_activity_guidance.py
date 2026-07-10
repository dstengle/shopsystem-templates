"""BDD scenarios — every post-PDR-033 PO activity carries guidance.

Pins scenario_hash:eaa4fc5b6bc7ed75 (lead-kz33). Each post-PDR-033 PO activity
named in the lead-po template carries at least one sentence of guidance OR an
explicit "guidance pending" marker; no bare list items.
"""
from pytest_bdd import scenarios

scenarios("../features/lead_po_activity_guidance.feature")
