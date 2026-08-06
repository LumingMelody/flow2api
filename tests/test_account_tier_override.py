import unittest
from unittest.mock import patch

from src.core.account_tiers import (
    PAYGATE_TIER_ONE_P5,
    PAYGATE_TIER_TWO,
    get_effective_user_paygate_tier,
)
from src.core.config import Config


class AccountTierOverrideTests(unittest.TestCase):
    def test_valid_override_wins_over_upstream_tier(self):
        self.assertEqual(
            get_effective_user_paygate_tier(
                PAYGATE_TIER_ONE_P5,
                PAYGATE_TIER_TWO,
            ),
            PAYGATE_TIER_TWO,
        )

    def test_missing_override_preserves_upstream_tier(self):
        self.assertEqual(
            get_effective_user_paygate_tier(PAYGATE_TIER_ONE_P5, None),
            PAYGATE_TIER_ONE_P5,
        )

    def test_invalid_override_is_logged_and_ignored(self):
        with patch("src.core.account_tiers.debug_logger.log_error") as log_error:
            effective_tier = get_effective_user_paygate_tier(
                PAYGATE_TIER_ONE_P5,
                "PAYGATE_TIER_UNKNOWN",
            )

        self.assertEqual(effective_tier, PAYGATE_TIER_ONE_P5)
        log_error.assert_called_once()
        self.assertIn("PAYGATE_TIER_UNKNOWN", log_error.call_args.args[0])

    def test_config_property_treats_blank_as_disabled(self):
        test_config = Config.__new__(Config)
        test_config._config = {"flow": {"user_paygate_tier_override": "  "}}
        self.assertIsNone(test_config.flow_user_paygate_tier_override)


if __name__ == "__main__":
    unittest.main()
