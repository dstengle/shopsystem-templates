"""BDD scenarios — lead-po post-PDR-033 activities, no Interview-stakeholder.

Pins scenario_hash:3cb958e1572e9532 (lead-vfg9, PDR-033 amendment-a). Terminal
replacement for the retired 6465b30fe62fb935: names every post-PDR-033 PO
activity and no longer presents "Interview stakeholder" as a lead-po activity,
attributing interview and discovery to the lead-pm main-session mode.
"""
from pytest_bdd import scenarios

scenarios("../features/lead_po_post_pdr033_activities.feature")
