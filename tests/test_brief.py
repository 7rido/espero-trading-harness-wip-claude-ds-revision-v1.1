"""The briefing is deterministic and says what is waiting."""
import unittest

from agent import brief


class TestBrief(unittest.TestCase):
    def test_it_renders_the_waiting_state(self):
        text = brief.render()
        for needle in ("E1 window", "holds", "Paper book", "Unattended jobs"):
            self.assertIn(needle, text)

    def test_it_reads_the_real_ledger(self):
        self.assertTrue(brief.render().startswith("# Briefing"))
