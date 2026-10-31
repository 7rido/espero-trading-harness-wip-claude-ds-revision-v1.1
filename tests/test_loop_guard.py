"""The model is only ever offered catalog tools; privileged verbs are refused."""
import unittest

from agent import catalog, loop


class TestLoopGuard(unittest.TestCase):
    def test_offered_tools_exclude_privileged(self):
        names = {s["function"]["name"] for s in loop.tool_schema()}
        self.assertFalse({n.replace(" ", "_") for n in catalog.PRIVILEGED} & names)

    def test_a_model_asking_for_trade_is_stopped(self):
        def fake(messages):
            return {"choices": [{"message": {"content": "", "tool_calls": [
                {"id": "1", "function": {"name": "trade", "arguments": "{}"}}]}}]}

        with self.assertRaises(SystemExit):
            loop.run("do something", client=fake)

    def test_there_is_no_loop_without_a_key(self):
        with self.assertRaises(SystemExit):
            loop.run("anything", client=None, key=None)
