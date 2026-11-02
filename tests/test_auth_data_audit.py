"""Auth audit helpers: env parsing and deterministic Coinbase signing."""
import base64
import hashlib
import hmac
import importlib.util
import pathlib
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("auth_data_audit", ROOT / "research" / "auth_data_audit.py")
audit = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(audit)


class TestAuthHelpers(unittest.TestCase):
    def test_load_env_ignores_comments_and_quotes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / ".env"
            path.write_text("# comment\nA=1\nB='two'\n\nC=\"three\"\n")
            self.assertEqual(audit.load_env(path), {"A": "1", "B": "two", "C": "three"})

    def test_coinbase_signature_is_stable(self):
        secret = base64.b64encode(b"test-secret").decode()
        expected = base64.b64encode(
            hmac.new(b"test-secret", b"1700000000GET/api/v3/brokerage/accounts",
                     hashlib.sha256).digest()
        ).decode()
        self.assertEqual(
            audit.sign_coinbase(secret, "1700000000", "GET", "/api/v3/brokerage/accounts"),
            expected,
        )


if __name__ == "__main__":
    unittest.main()
