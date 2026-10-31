"""The catalog must cover the CLI exactly, and never hide a privileged verb."""
import pathlib
import unittest

from agent import catalog
from espero2.cli import build_parser

ROOT = pathlib.Path(__file__).resolve().parents[1]


class TestCatalog(unittest.TestCase):
    def test_every_cli_subcommand_is_classified(self):
        parser = build_parser()
        sub = next(a for a in parser._actions if a.__class__.__name__ == "_SubParsersAction")
        self.assertEqual(set(sub.choices), set(catalog.CLI_COVERAGE))

    def test_privileged_set_is_exact(self):
        privileged = {t.name for t in catalog.TOOLS if t.klass == "privileged"}
        self.assertEqual(privileged, set(catalog.PRIVILEGED))
        self.assertTrue({"run", "order", "trade", "cb order"} <= privileged)

    def test_agents_never_see_privileged_tools(self):
        visible = {t.name for t in catalog.AGENT_VISIBLE}
        self.assertFalse(visible & set(catalog.PRIVILEGED))

    def test_no_shell_metacharacters_in_any_template(self):
        for t in catalog.TOOLS:
            for part in t.argv:
                self.assertFalse(any(ch in part for ch in ";|&`$><"), f"{t.name}: {part!r}")

    def test_research_tools_point_at_real_files(self):
        for t in catalog.TOOLS:
            if t.klass == "research":
                script = next(p for p in t.argv if p.endswith(".py"))
                self.assertTrue((ROOT / script).exists(), script)

    def test_unknown_tool_raises(self):
        with self.assertRaises(KeyError):
            catalog.get("rm -rf")


class TestArgumentGuards(unittest.TestCase):
    def test_shell_metacharacters_are_refused(self):
        spec = catalog.get("book")
        with self.assertRaises(ValueError):
            catalog.validate_args(spec, {"coin": "BTC; rm -rf /"})

    def test_path_traversal_is_refused(self):
        spec = catalog.get("book")
        for bad in ("../../etc/passwd", "/etc/passwd", "~/x"):
            with self.assertRaises(ValueError):
                catalog.validate_args(spec, {"coin": bad})

    def test_undeclared_argument_is_refused(self):
        spec = catalog.get("book")
        with self.assertRaises(ValueError):
            catalog.validate_args(spec, {"coin": "BTC", "extra": "1"})
