"""Account tier and model capability helpers."""

from typing import Optional

from .logger import debug_logger


PAYGATE_TIER_NOT_PAID = "PAYGATE_TIER_NOT_PAID"
PAYGATE_TIER_ONE = "PAYGATE_TIER_ONE"
PAYGATE_TIER_ONE_P5 = "PAYGATE_TIER_TIER1P5"
PAYGATE_TIER_TWO = "PAYGATE_TIER_TWO"
VALID_USER_PAYGATE_TIERS = frozenset({
    PAYGATE_TIER_NOT_PAID,
    PAYGATE_TIER_ONE,
    PAYGATE_TIER_ONE_P5,
    PAYGATE_TIER_TWO,
})


def normalize_user_paygate_tier(user_paygate_tier: Optional[str]) -> str:
    """Normalize an account tier, defaulting unknown values to free tier."""
    normalized = (user_paygate_tier or "").strip()
    if normalized in VALID_USER_PAYGATE_TIERS:
        return normalized
    debug_logger.log_info(
        f"[ACCOUNT_TIER] Unknown user_paygate_tier {user_paygate_tier!r}; "
        f"falling back to {PAYGATE_TIER_NOT_PAID}"
    )
    return PAYGATE_TIER_NOT_PAID


def get_effective_user_paygate_tier(
    user_paygate_tier: Optional[str],
    user_paygate_tier_override: Optional[str] = None,
) -> str:
    """Resolve the tier used for local checks and upstream reporting."""
    override = str(user_paygate_tier_override or "").strip()
    if not override:
        return normalize_user_paygate_tier(user_paygate_tier)
    if override in VALID_USER_PAYGATE_TIERS:
        return override

    allowed_values = ", ".join(sorted(VALID_USER_PAYGATE_TIERS))
    debug_logger.log_error(
        f"[ACCOUNT_TIER] Invalid flow.user_paygate_tier_override {override!r}; "
        f"ignoring override and using /v1/credits tier. Allowed values: {allowed_values}"
    )
    return normalize_user_paygate_tier(user_paygate_tier)


def get_paygate_tier_rank(user_paygate_tier: Optional[str]) -> int:
    """Map account tier to a comparable rank."""
    normalized = normalize_user_paygate_tier(user_paygate_tier)
    if normalized == PAYGATE_TIER_TWO:
        return 3
    if normalized == PAYGATE_TIER_ONE_P5:
        return 2
    if normalized == PAYGATE_TIER_ONE:
        return 1
    return 0


def get_paygate_tier_label(user_paygate_tier: Optional[str]) -> str:
    """Return a readable account tier label."""
    normalized = normalize_user_paygate_tier(user_paygate_tier)
    if normalized == PAYGATE_TIER_TWO:
        return "Ult"
    if normalized == PAYGATE_TIER_ONE_P5:
        return "Pro+"
    if normalized == PAYGATE_TIER_ONE:
        return "Pro"
    return "Free"


def get_required_paygate_tier_for_model(
    model_name: Optional[str],
    model_type: Optional[str] = None,
) -> str:
    """Infer the minimum account tier from a model name and trusted model type."""
    normalized = (model_name or "").strip().lower()
    normalized_type = (model_type or "").strip().lower()
    if not normalized:
        return PAYGATE_TIER_NOT_PAID

    if "_ultra" in normalized:
        return PAYGATE_TIER_TWO

    if normalized_type == "video" and (
        normalized.endswith("_1080p")
        or normalized.endswith("-4k")
        or normalized.endswith("_4k")
    ):
        return PAYGATE_TIER_TWO

    if normalized.endswith("-4k") or normalized.endswith("_4k"):
        if normalized_type == "image":
            return PAYGATE_TIER_ONE_P5
        return PAYGATE_TIER_TWO

    if normalized.endswith("-2k") or normalized.endswith("_1080p"):
        return PAYGATE_TIER_ONE

    return PAYGATE_TIER_NOT_PAID


def supports_model_for_tier(
    model_name: Optional[str],
    user_paygate_tier: Optional[str],
    model_type: Optional[str] = None,
) -> bool:
    """Check whether the current account tier can use the given model."""
    required_tier = get_required_paygate_tier_for_model(model_name, model_type)
    return get_paygate_tier_rank(user_paygate_tier) >= get_paygate_tier_rank(required_tier)
