"""Bind the effectively-empty / product-discovery lead-primer feature.

The Given / When / "a non-empty template body is returned" legs reuse the
shared CLAUDE.md primer step definitions in conftest
(given_package_ships_canonical_primer, when_ask_for_that_canonical_primer_body,
then_returned_body_non_empty). The contiguous-block Then steps for these four
scenarios live in conftest alongside the other lead-primer block assertions.
"""
from pytest_bdd import scenarios

scenarios("../features/lead_primer_effectively_empty_product_discovery.feature")
