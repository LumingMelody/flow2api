import types
import unittest
from unittest.mock import AsyncMock, patch

from src.core.models import Token
from src.services.generation_handler import GenerationHandler
from src.services.token_manager import TokenManager


class TokenErrorClassifierTests(unittest.TestCase):
    def setUp(self):
        self.handler = GenerationHandler.__new__(GenerationHandler)

    def test_content_filter_errors_do_not_count(self):
        errors = (
            "PUBLIC_ERROR_AUDIO_FILTERED",
            RuntimeError("PUBLIC_ERROR_UNSAFE_GENERATION: Request contains an invalid argument."),
            "PUBLIC_ERROR_PROMINENT_PEOPLE_FILTER_FAILED",
            "Generation stopped because the output was blocked by a safety filter",
            "Request contains sensitive content and might violate our policies",
        )

        for error in errors:
            with self.subTest(error=error):
                self.assertFalse(self.handler._should_count_token_error(error))

    def test_real_account_errors_still_count(self):
        errors = (
            "401 UNAUTHENTICATED: access token expired",
            RuntimeError("PUBLIC_ERROR_USER_QUOTA_REACHED"),
            "403 PUBLIC_ERROR_MODEL_ACCESS_DENIED",
            "Account blocked because authentication was revoked",
            "RESOURCE_EXHAUSTED: quota exceeded",
        )

        for error in errors:
            with self.subTest(error=error):
                self.assertTrue(self.handler._should_count_token_error(error))


class GenerationFailurePathTests(unittest.IsolatedAsyncioTestCase):
    def _make_handler(self, failure_mode: str, error):
        token = Token(
            id=7,
            st="session-token",
            at="access-token",
            email="tester@example.com",
            user_paygate_tier="PAYGATE_TIER_TWO",
        )
        token_manager = types.SimpleNamespace(
            ensure_valid_token=AsyncMock(return_value=token),
            ensure_project_exists=AsyncMock(return_value="project-1"),
            record_error=AsyncMock(),
        )
        load_balancer = types.SimpleNamespace(
            select_token=AsyncMock(return_value=token),
            release_pending=AsyncMock(),
        )
        flow_client = types.SimpleNamespace(
            prefill_remote_browser_pool=AsyncMock(),
        )

        handler = GenerationHandler.__new__(GenerationHandler)
        handler.flow_client = flow_client
        handler.token_manager = token_manager
        handler.load_balancer = load_balancer
        handler.db = types.SimpleNamespace()
        handler._log_request = AsyncMock(return_value=None)

        async def fail_generation(_self, *args, **kwargs):
            if failure_mode == "exception":
                raise error if isinstance(error, Exception) else RuntimeError(str(error))
            _self._mark_generation_failed(kwargs["generation_result"], str(error))
            if False:
                yield None

        handler._handle_image_generation = types.MethodType(fail_generation, handler)
        return handler, token_manager

    async def test_result_and_exception_paths_use_same_classification(self):
        cases = (
            ("result", "PUBLIC_ERROR_AUDIO_FILTERED", False),
            ("exception", RuntimeError("PUBLIC_ERROR_AUDIO_FILTERED"), False),
            ("result", "PUBLIC_ERROR_USER_QUOTA_REACHED", True),
            ("exception", RuntimeError("401 UNAUTHENTICATED: token expired"), True),
        )

        for failure_mode, error, should_count in cases:
            with self.subTest(failure_mode=failure_mode, error=error):
                handler, token_manager = self._make_handler(failure_mode, error)
                with patch("src.services.generation_handler.debug_logger.log_info") as log_info:
                    responses = [
                        response
                        async for response in handler.handle_generation(
                            model="gemini-3.0-pro-image-landscape",
                            prompt="test prompt",
                        )
                    ]

                if should_count:
                    token_manager.record_error.assert_awaited_once_with(7)
                else:
                    token_manager.record_error.assert_not_awaited()
                    self.assertTrue(
                        any("跳过 token 错误计数" in call.args[0] for call in log_info.call_args_list)
                    )

                self.assertIsInstance(responses, list)


class ConsecutiveErrorBanReasonTests(unittest.IsolatedAsyncioTestCase):
    async def test_threshold_disable_persists_visible_reason(self):
        db = types.SimpleNamespace(
            increment_token_stats=AsyncMock(),
            get_token_stats=AsyncMock(
                return_value=types.SimpleNamespace(consecutive_error_count=3)
            ),
            get_admin_config=AsyncMock(
                return_value=types.SimpleNamespace(error_ban_threshold=3)
            ),
            update_token=AsyncMock(),
        )
        manager = TokenManager(db, types.SimpleNamespace())

        await manager.record_error(7)

        db.update_token.assert_awaited_once()
        token_id = db.update_token.call_args.args[0]
        update_fields = db.update_token.call_args.kwargs
        self.assertEqual(token_id, 7)
        self.assertFalse(update_fields["is_active"])
        self.assertEqual(update_fields["ban_reason"], "consecutive_errors")
        self.assertIsNotNone(update_fields["banned_at"].tzinfo)


if __name__ == "__main__":
    unittest.main()
