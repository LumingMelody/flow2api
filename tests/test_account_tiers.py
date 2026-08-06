import json
import types
import unittest
from unittest.mock import AsyncMock, PropertyMock, patch

from src.core.account_tiers import (
    PAYGATE_TIER_NOT_PAID,
    PAYGATE_TIER_ONE,
    PAYGATE_TIER_ONE_P5,
    PAYGATE_TIER_TWO,
    get_paygate_tier_label,
    get_paygate_tier_rank,
    get_required_paygate_tier_for_model,
    normalize_user_paygate_tier,
    supports_model_for_tier,
)
from src.core.models import Token
from src.services.generation_handler import GenerationHandler
from src.services.load_balancer import LoadBalancer


class AccountTierOneP5Tests(unittest.TestCase):
    def test_tier_one_p5_is_preserved_and_ranked_as_pro_plus(self):
        self.assertEqual(normalize_user_paygate_tier(PAYGATE_TIER_ONE_P5), PAYGATE_TIER_ONE_P5)
        self.assertLess(
            get_paygate_tier_rank(PAYGATE_TIER_ONE),
            get_paygate_tier_rank(PAYGATE_TIER_ONE_P5),
        )
        self.assertLess(
            get_paygate_tier_rank(PAYGATE_TIER_ONE_P5),
            get_paygate_tier_rank(PAYGATE_TIER_TWO),
        )
        self.assertEqual(get_paygate_tier_label(PAYGATE_TIER_ONE_P5), "Pro+")

    def test_tier_matrix_keeps_image_4k_separate_from_video_ultra(self):
        image_4k_model = "gemini-3.0-pro-image-three-four-4k"
        video_ultra_model = "veo_3_1_i2v_s_fast_portrait_fl_1080p"

        self.assertEqual(
            get_required_paygate_tier_for_model(image_4k_model, "image"),
            PAYGATE_TIER_ONE_P5,
        )
        self.assertEqual(
            get_required_paygate_tier_for_model(video_ultra_model, "video"),
            PAYGATE_TIER_TWO,
        )

        self.assertTrue(
            supports_model_for_tier(image_4k_model, PAYGATE_TIER_ONE_P5, "image")
        )
        self.assertFalse(
            supports_model_for_tier(video_ultra_model, PAYGATE_TIER_ONE_P5, "video")
        )

        for model_name, model_type in (
            (image_4k_model, "image"),
            (video_ultra_model, "video"),
        ):
            self.assertFalse(
                supports_model_for_tier(
                    model_name,
                    PAYGATE_TIER_NOT_PAID,
                    model_type,
                )
            )
            self.assertTrue(
                supports_model_for_tier(
                    model_name,
                    PAYGATE_TIER_TWO,
                    model_type,
                )
            )

    def test_contextless_4k_check_remains_conservative(self):
        model = "gemini-3.0-pro-image-three-four-4k"

        self.assertEqual(
            get_required_paygate_tier_for_model(model),
            PAYGATE_TIER_TWO,
        )
        self.assertFalse(supports_model_for_tier(model, PAYGATE_TIER_ONE_P5))

    def test_video_1080p_requires_ultra_only_with_video_context(self):
        model = "veo_3_1_i2v_s_fast_portrait_fl_1080p"

        self.assertEqual(
            get_required_paygate_tier_for_model(model, "video"),
            PAYGATE_TIER_TWO,
        )
        self.assertFalse(
            supports_model_for_tier(model, PAYGATE_TIER_ONE_P5, "video")
        )

    def test_unknown_tier_falls_back_to_free_and_is_logged(self):
        unknown_tier = "PAYGATE_TIER_FUTURE"

        with patch("src.core.account_tiers.debug_logger.log_info") as log_info:
            normalized = normalize_user_paygate_tier(unknown_tier)

        self.assertEqual(normalized, PAYGATE_TIER_NOT_PAID)
        log_info.assert_called_once()
        self.assertIn(unknown_tier, log_info.call_args.args[0])


class _TokenManagerStub:
    def __init__(self, token):
        self.token = token

    async def get_active_tokens(self):
        return [self.token]

    def needs_at_refresh(self, token):
        return False

    async def ensure_valid_token(self, token):
        return token


class LoadBalancerTierTests(unittest.IsolatedAsyncioTestCase):
    @patch(
        "src.core.config.Config.flow_user_paygate_tier_override",
        new_callable=PropertyMock,
        return_value=None,
    )
    async def test_tier_one_p5_is_selected_for_image_4k_but_not_video_ultra(
        self,
        _tier_override,
    ):
        video_model = "veo_3_1_i2v_s_portrait_1080p"
        token = Token(
            id=1,
            st="session-token",
            email="tier1p5@example.com",
            user_paygate_tier=PAYGATE_TIER_ONE_P5,
        )
        load_balancer = LoadBalancer(_TokenManagerStub(token))
        load_balancer._check_extension_route = AsyncMock(return_value=(True, ""))

        selected = await load_balancer.select_token(
            for_image_generation=True,
            model="gemini-3.0-pro-image-three-four-4k",
        )
        self.assertIs(selected, token)

        selected = await load_balancer.select_token(
            for_video_generation=True,
            model=video_model,
        )
        self.assertIsNone(selected)

        image_reason = await load_balancer.get_unavailable_reason(
            for_image_generation=True,
            model="gemini-3.0-pro-image-three-four-4k",
        )
        video_reason = await load_balancer.get_unavailable_reason(
            for_video_generation=True,
            model=video_model,
        )
        self.assertIsNone(image_reason)
        self.assertIn("Ult", video_reason)

    @patch(
        "src.core.config.Config.flow_user_paygate_tier_override",
        new_callable=PropertyMock,
        return_value=None,
    )
    async def test_generation_handler_secondary_gate_still_rejects_video_ultra(
        self,
        _tier_override,
    ):
        token = Token(
            id=1,
            st="session-token",
            email="tier1p5@example.com",
            user_paygate_tier=PAYGATE_TIER_ONE_P5,
        )
        load_balancer = types.SimpleNamespace(
            select_token=AsyncMock(return_value=token),
            release_pending=AsyncMock(),
        )
        token_manager = types.SimpleNamespace(
            ensure_valid_token=AsyncMock(return_value=token),
            ensure_project_exists=AsyncMock(),
        )
        handler = GenerationHandler.__new__(GenerationHandler)
        handler.flow_client = types.SimpleNamespace()
        handler.load_balancer = load_balancer
        handler.token_manager = token_manager

        responses = [
            json.loads(response)
            async for response in handler.handle_generation(
                model="veo_3_1_i2v_s_portrait_1080p",
                prompt="tier gate test",
            )
        ]

        self.assertEqual(responses[-1]["error"]["status_code"], 403)
        self.assertIn("Ult", responses[-1]["error"]["message"])
        token_manager.ensure_project_exists.assert_not_awaited()
        load_balancer.release_pending.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
