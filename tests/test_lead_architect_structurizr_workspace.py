"""BDD scenarios pinning the lead-architect template's Maintain structurizr
workspace activity (lead-y8rz / 9fac437e075784fe).

The scenario verifies that the activity block:
  1. Names all three view families (containers, components, dynamic views)
  2. States the assign-per-structurizr coupling explicitly
  3. States the ADR-workspace traceability gate explicitly
  4. Expresses each as a sufficiency criterion, not bare advisory prose
"""
from pytest_bdd import scenarios

scenarios("../features/lead_architect_structurizr_workspace.feature")
