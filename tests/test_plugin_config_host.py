import unittest

from src.plugin_config import build_plugin_connection_url


class PluginConfigHostTests(unittest.TestCase):
    def build_url(self, host_header):
        return build_plugin_connection_url(host_header, "0.0.0.0", 38000)

    def test_normal_host_is_used(self):
        self.assertEqual(
            self.build_url("localhost:38000"),
            "http://localhost:38000/api/plugin/update-token",
        )

    def test_http_scheme_prefix_is_removed(self):
        self.assertEqual(
            self.build_url("http://localhost:38000"),
            "http://localhost:38000/api/plugin/update-token",
        )
        self.assertEqual(
            self.build_url("http://localhost/:38000"),
            "http://localhost/api/plugin/update-token",
        )

    def test_path_is_removed(self):
        self.assertEqual(
            self.build_url("localhost:38000/unexpected/path"),
            "http://localhost:38000/api/plugin/update-token",
        )

    def test_trailing_slash_is_removed(self):
        self.assertEqual(
            self.build_url("localhost:38000/"),
            "http://localhost:38000/api/plugin/update-token",
        )

    def test_empty_host_uses_config_fallback(self):
        self.assertEqual(
            self.build_url(""),
            "http://127.0.0.1:38000/api/plugin/update-token",
        )

    def test_invalid_host_uses_config_fallback(self):
        self.assertEqual(
            self.build_url("bad host:38000"),
            "http://127.0.0.1:38000/api/plugin/update-token",
        )
        self.assertEqual(
            self.build_url("999.999.999.999:38000"),
            "http://127.0.0.1:38000/api/plugin/update-token",
        )


if __name__ == "__main__":
    unittest.main()
