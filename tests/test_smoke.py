"""The operator smoke test runs end to end and the guard holds."""
import unittest

from agent import smoke


class TestSmoke(unittest.TestCase):
    def test_the_operator_session_completes(self):
        self.assertEqual(smoke.main(), 0)
