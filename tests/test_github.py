import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))


class TestGitHubAuth(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self.tmp.name)
        import github as github_mod
        self._orig_dir = github_mod.GITHUB_CONFIG_DIR
        self._orig_file = github_mod.GITHUB_TOKEN_FILE
        github_mod.GITHUB_CONFIG_DIR = self.tmp_dir
        github_mod.GITHUB_TOKEN_FILE = self.tmp_dir / "github_token.json"

    def tearDown(self):
        import github as github_mod
        github_mod.GITHUB_CONFIG_DIR = self._orig_dir
        github_mod.GITHUB_TOKEN_FILE = self._orig_file
        self.tmp.cleanup()

    def _mod(self):
        import github as github_mod
        return github_mod

    def test_authenticate_and_status(self):
        mod = self._mod()
        mod.authenticate_github("ghp_test")
        self.assertTrue(mod.is_authenticated())
        status = mod.github_status()
        self.assertIn("authenticated", status.lower())

    def test_logout_clears_token(self):
        mod = self._mod()
        mod.authenticate_github("ghp_test")
        mod.logout_github()
        self.assertFalse(mod.is_authenticated())

    def test_list_repos_uses_authenticated_user(self):
        mod = self._mod()
        mod.authenticate_github("ghp_test")
        fake_body = [{"name": "alpha"}, {"name": "beta"}]

        class FakeResponse:
            def __init__(self, body):
                self._body = body
            def read(self):
                return str(self._body).replace("'", '"').encode()
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False

        with patch("urllib.request.urlopen", return_value=FakeResponse(fake_body)):
            repos = mod.list_repositories()

        self.assertEqual(repos, ["alpha", "beta"])
