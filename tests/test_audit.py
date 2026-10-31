"""The audit must stay complete, cited, deterministic and honest about drift."""
import csv
import hashlib
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "audit_by_number.py"
BASE = ROOT / "research" / "audit_base.csv"
FINDINGS = ROOT / "research" / "audit_findings.csv"
OUT = ROOT / "research" / "AUDIT_BY_NUMBER.md"
EXPECTED = [str(i) for i in range(1, 46)] + ["9b"]


def run(*args, cwd=ROOT):
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd,
                          capture_output=True, text=True)


class TestAuditInputs(unittest.TestCase):
    def test_coverage_is_46_ids(self):
        ids = [r["id"] for r in csv.DictReader(BASE.open())]
        self.assertEqual(sorted(ids), sorted(EXPECTED))

    def test_every_id_has_a_finding_with_evidence(self):
        findings = {r["id"]: r for r in csv.DictReader(FINDINGS.open())}
        for i in EXPECTED:
            f = findings[i]
            self.assertIn(f["failure_layer"],
                          {"estimator", "economic", "selection", "execution", "process", "none"})
            self.assertTrue(f["why"] and f["remedy"])
            self.assertTrue((ROOT / f["evidence"]).exists(), f"{i}: {f['evidence']}")


class TestAuditRun(unittest.TestCase):
    def test_check_passes(self):
        r = run("--check")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("46 ids", r.stdout)

    def test_output_is_deterministic(self):
        r1 = run()
        self.assertEqual(r1.returncode, 0, r1.stderr)
        first = hashlib.sha256(OUT.read_bytes()).hexdigest()
        run()
        self.assertEqual(hashlib.sha256(OUT.read_bytes()).hexdigest(), first)

    def test_document_has_one_row_per_id(self):
        text = OUT.read_text()
        header = text.index("| # | hypothesis |")
        table = text[header:].split("\n\n")[0]
        rows = [l for l in table.splitlines() if l.startswith("| ") and not l.startswith("| # ")]
        self.assertEqual(len(rows), 46)
        for i in EXPECTED:
            self.assertIn(f"| {i} |", text)


class TestOriginalComparison(unittest.TestCase):
    def test_drift_is_detected(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = pathlib.Path(d) / "research"
            tmp.mkdir()
            for doc in (ROOT / "reference").glob("*.md"):
                shutil.copy2(doc, tmp / doc.name)
            victim = tmp / "RESULTS_MF.md"
            victim.write_text(victim.read_text() + "\ndrift\n")
            r = run("--compare-original", str(tmp), "--check")
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("content differs", r.stderr)

    def test_identical_copy_passes(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = pathlib.Path(d) / "research"
            tmp.mkdir()
            for doc in (ROOT / "reference").glob("*.md"):
                shutil.copy2(doc, tmp / doc.name)
            r = run("--compare-original", str(tmp), "--check")
            self.assertEqual(r.returncode, 0, r.stderr)
