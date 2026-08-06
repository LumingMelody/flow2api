import unittest
from unittest.mock import patch

from src.core.config import Config
from src.services.flow_client import FlowClient


class AudioFailurePreferenceTests(unittest.TestCase):
    def _build_context(self, flow_config):
        test_config = Config.__new__(Config)
        test_config._config = {"flow": flow_config}
        client = FlowClient.__new__(FlowClient)

        with patch("src.services.flow_client.config", test_config):
            return client._build_video_media_generation_context("batch-1")

    def test_default_preserves_block_silenced_videos(self):
        context = self._build_context({})

        self.assertEqual(context["batchId"], "batch-1")
        self.assertEqual(
            context["audioFailurePreference"],
            "BLOCK_SILENCED_VIDEOS",
        )

    def test_valid_return_silenced_videos_override_is_used(self):
        context = self._build_context({
            "audio_failure_preference": "RETURN_SILENCED_VIDEOS",
        })

        self.assertEqual(
            context["audioFailurePreference"],
            "RETURN_SILENCED_VIDEOS",
        )

    def test_invalid_override_logs_error_and_falls_back(self):
        with patch("src.core.config.logger.error") as log_error:
            context = self._build_context({
                "audio_failure_preference": "RETURN_ANY_VIDEO",
            })

        self.assertEqual(
            context["audioFailurePreference"],
            "BLOCK_SILENCED_VIDEOS",
        )
        log_error.assert_called_once()
        self.assertIn("RETURN_ANY_VIDEO", log_error.call_args.args[0])
        self.assertIn("BLOCK_SILENCED_VIDEOS", log_error.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
