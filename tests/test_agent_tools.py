"""Executor guards: allowlist, privilege, env stripping, audit log."""
import json
import pathlib
import unittest
from unittest.mock import patch

from agent import tools


class TestExecutor(unittest.TestCase):
    def test_privileged_is_refused_for_agents(self):
        for name in ("run", "order", "trade", "cb order", "ui"):
            with self.assertRaises(tools.Refused):
                tools.run_tool(name, {"coin": "BTC", "side": "buy"})

    def test_dry_run_never_spawns_a_process(self):
        with patch.object(tools.subprocess, "run", side_effect=AssertionError("spawned")):
            out = tools.run_tool("ledger", dry_run=True)
        self.assertTrue(out["dry_run"])
        self.assertIn("espero2.cli", " ".join(out["argv"]))

    def test_unknown_tool_raises(self):
        with self.assertRaises(KeyError):
            tools.run_tool("does-not-exist")

    def test_unsafe_argument_is_refused(self):
        with self.assertRaises(ValueError):
            tools.run_tool("book", {"coin": "BTC; touch /tmp/x"})

    def test_secrets_are_removed_from_the_environment(self):
        import os
        with patch.dict(os.environ, {"HL_PRIVATE_KEY": "deadbeef", "APCA_API_SECRET_KEY": "x",
                                     "PATH": "/usr/bin"}, clear=False):
            env = tools.clean_env()
        self.assertNotIn("HL_PRIVATE_KEY", env)
        self.assertNotIn("APCA_API_SECRET_KEY", env)
        self.assertIn("PATH", env)

    def test_a_real_call_appends_one_audit_record(self):
        before = tools.LOG.read_text().count("\n") if tools.LOG.exists() else 0
        out = tools.run_tool("ledger")
        self.assertEqual(out["exit"], 0, out["stderr"])
        lines = tools.LOG.read_text().splitlines()
        self.assertEqual(len(lines), before + 1)
        rec = json.loads(lines[-1])
        self.assertEqual(rec["tool"], "ledger")
        self.assertEqual(rec["mode"], "agent")
