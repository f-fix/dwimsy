#!/usr/bin/env python3
"""tests.test_cli_env - verify -D/--env-set, -U/--env-unset, and --env-help universal CLI options."""

import io
import os
import sys
import unittest
from pathlib import Path
from contextlib import redirect_stdout

from dwimsy.meta import unbundle
from dwimsy.cli.__main__ import main as cli_main


class TestCliEnvOptions(unittest.TestCase):
    def setUp(self):
        self.orig_env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.orig_env)

    def test_env_set_and_unset(self):
        # Test setting via -D with explicit value
        pipeline, _ = unbundle.parse_early_pipeline_flags(["-D", "MY_TEST_VAR=hello_world"])
        self.assertEqual(unbundle.get_env_casefolded("my_test_var"), "hello_world")
        self.assertEqual(os.environ.get("MY_TEST_VAR"), "hello_world")

        # Test default value 1 when =VALUE is omitted
        pipeline, _ = unbundle.parse_early_pipeline_flags(["-D", "DEFAULT_ONE_FLAG"])
        self.assertEqual(os.environ.get("DEFAULT_ONE_FLAG"), "1")
        self.assertEqual(unbundle.get_env_casefolded("default_one_flag"), "1")

        # Test unsetting via -U
        pipeline, _ = unbundle.parse_early_pipeline_flags(["-U", "my_test_var"])
        self.assertNotIn("MY_TEST_VAR", os.environ)
        self.assertIsNone(unbundle.get_env_casefolded("my_test_var"))

        # Test case-insensitivity: lowercase -d
        pipeline, _ = unbundle.parse_early_pipeline_flags(["-d", "lower_test=value1"])
        self.assertEqual(os.environ.get("LOWER_TEST"), "value1")
        self.assertEqual(unbundle.get_env_casefolded("lower_test"), "value1")

        # Test case-insensitivity: lowercase -u
        pipeline, _ = unbundle.parse_early_pipeline_flags(["-u", "LOWER_TEST"])
        self.assertNotIn("LOWER_TEST", os.environ)

        # Test setting via --env-set without value (defaults to 1)
        pipeline, _ = unbundle.parse_early_pipeline_flags(["--env-set=ANOTHER_VAR"])
        self.assertEqual(os.environ.get("ANOTHER_VAR"), "1")

        # Test unsetting via --env-unset
        pipeline, _ = unbundle.parse_early_pipeline_flags(["--env-unset=ANOTHER_VAR"])
        self.assertNotIn("ANOTHER_VAR", os.environ)

    def test_http_proxy_exception(self):
        # Setting HTTP_PROXY case-insensitively sets both HTTP_PROXY and http_proxy
        pipeline, _ = unbundle.parse_early_pipeline_flags(["-D", "http_proxy=http://proxy.example.com:8080"])
        self.assertEqual(os.environ.get("HTTP_PROXY"), "http://proxy.example.com:8080")
        self.assertEqual(os.environ.get("http_proxy"), "http://proxy.example.com:8080")

        # Unsetting clears both
        pipeline, _ = unbundle.parse_early_pipeline_flags(["-U", "HTTP_PROXY"])
        self.assertNotIn("HTTP_PROXY", os.environ)
        self.assertNotIn("http_proxy", os.environ)

    def test_attached_test_flags(self):
        pipeline, remaining = unbundle.parse_early_pipeline_flags(["-Tmeta integrity"])
        self.assertTrue(pipeline["test_mode"])
        self.assertEqual(pipeline["test_pattern"], "meta integrity")

    def test_env_help_flag(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = cli_main(["--env-help"])
            self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("### Environment Variables", out)
        self.assertIn("DWIMSY_BUNDLE_BUILD", out)
        self.assertIn("DWIMSY_IN_PROCESS_VERIFICATION", out)
        self.assertIn("DWIMSY_WITHOUT_SUBPROCESS", out)


if __name__ == "__main__":
    unittest.main()
