from __future__ import annotations

from pathlib import Path

import pytest

from review_workflow.adapters.extraction import load_domain_profile

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "profile_name",
    ["engineering-generic.yaml", "natural-science-generic.yaml"],
)
def test_generic_domain_profiles_validate_without_engine_overrides(profile_name: str) -> None:
    profile = load_domain_profile(REPOSITORY_ROOT / "profiles" / profile_name)

    assert profile.profile_id
    assert profile.newcomer_concepts
    assert not hasattr(profile, "phase_transitions")
    assert not hasattr(profile, "privacy_policy")
