"""Carry sleeve gates: entry thresholds and exit conditions (pure functions, no network)."""
import importlib.util
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("carry_mod", ROOT / "research" / "carry_sleeve.py")
carry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(carry)


def pos(**kw):
    base = {"neg_funding_days": 0, "neg_basis_days": 0, "perp_pnl": 0.0}
    base.update(kw)
    return base


class TestEntry(unittest.TestCase):
    def test_enters_when_funding_basis_and_spread_are_fine(self):
        self.assertTrue(carry.should_enter(6.0, 3.0, 2.0))

    def test_rejects_expensive_spread(self):
        self.assertFalse(carry.should_enter(6.0, 3.0, 6.0))

    def test_rejects_inverted_basis(self):
        self.assertFalse(carry.should_enter(6.0, -1.0, 2.0))

    def test_rejects_thin_funding(self):
        self.assertFalse(carry.should_enter(4.0, 3.0, 2.0))


class TestExit(unittest.TestCase):
    def test_stays_when_healthy(self):
        self.assertIsNone(carry.should_exit(pos(), 8.0, 5.0))

    def test_funding_negative_two_checks(self):
        self.assertIn("funding", carry.should_exit(pos(neg_funding_days=2), -1.0, 5.0))

    def test_basis_inverted_two_checks(self):
        self.assertIn("basis", carry.should_exit(pos(neg_basis_days=2), 8.0, -20.0))

    def test_margin_buffer(self):
        self.assertIn("buffer", carry.should_exit(pos(perp_pnl=-800.0), 8.0, 5.0))
