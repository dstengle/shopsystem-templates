"""BDD scenarios — lead-po outcome-ownership sufficiency criterion (commitment).

Pins scenario_hash:627723b55dd2ed7e (lead-vfg9, PDR-033 amendment-a). Terminal
replacement for the retired 25038c88fec521ba: the outcome-ownership sufficiency
criterion is scoped to the commitment, the shaped candidate carries the
validated problem/JTBD, and upstream problem discovery/selection is re-homed to
the lead-pm main-session mode (not a lead-po sufficiency criterion).
"""
from pytest_bdd import scenarios

scenarios("../features/lead_po_outcome_ownership_criterion.feature")
