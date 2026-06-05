"""BDD scenarios — lead-po anti-build-trap structural gate.

Pins scenario_hash:c96e0d7e37de2079 from lead-y8rz dispatch.
Verifies that the lead-po template names the build trap as the structural
failure mode the empowered-PM role exists to prevent, states that the
build trap is more dangerous in this system, and frames the anti-build-trap
gate as a sufficiency criterion (not bare advisory prose).
"""
from pytest_bdd import scenarios

scenarios("../features/lead_po_anti_build_trap.feature")
