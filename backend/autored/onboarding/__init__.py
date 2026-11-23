"""Dynamic target onboarding: turn an authorized website URL into a
mission-compatible Target, with SSRF protection and authorization verification.

This never relaxes the existing scope guarantees — an onboarded Target is a
normal Target registered into the live ScopeRegistry, so OriginGuard, rate
limits, concurrency and emergency-stop all apply unchanged. What is added is a
safe path to *create* that Target at runtime instead of hand-editing YAML.
"""
from .ssrf import SSRFError, ResolvedTarget, validate_target_url
from .registry import OnboardingError, OnboardingRegistry, OnboardedTarget

__all__ = [
    "SSRFError", "ResolvedTarget", "validate_target_url",
    "OnboardingError", "OnboardingRegistry", "OnboardedTarget",
]
