"""BDD scenarios — lead-po commitment-owner identity + three durable disciplines.

Pins scenario_hash:8417a90ab75a9c4f (lead-vfg9, PDR-033 amendment-a). Terminal
replacement for the retired 1e49cc3a526d4272: names the commitment-owner
identity (owns the outcome, receives a shaped candidate, distinct from an
order-taker) and the three durable disciplines the lead-po retains after
discovery/shaping/option-facilitation re-home to the lead-pm mode.
"""
from pytest_bdd import scenarios

scenarios("../features/lead_po_commitment_owner_identity.feature")
