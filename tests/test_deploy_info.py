"""Deploy provenance reads Railway-injected env (or falls back)."""

import os
import unittest
from unittest import mock

from src.web.server import _deploy_info


class TestDeployInfo(unittest.TestCase):
    def test_railway_env(self):
        env = {"RAILWAY_ENVIRONMENT_NAME": "production",
               "RAILWAY_SERVICE_NAME": "bot",
               "RAILWAY_GIT_COMMIT_SHA": "abcdef1234567890",
               "RAILWAY_DEPLOYMENT_ID": "dep1234567890xyz"}
        with mock.patch.dict(os.environ, env, clear=False):
            d = _deploy_info()
        self.assertEqual(d["provider"], "railway")
        self.assertEqual(d["commit"], "abcdef1")
        self.assertEqual(d["service"], "bot")

    def test_no_env(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            d = _deploy_info()
        self.assertEqual(d["provider"], "other/local")
        self.assertEqual(d["commit"], "–")


if __name__ == "__main__":
    unittest.main()
