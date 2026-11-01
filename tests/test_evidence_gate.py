"""The evidence gate must refuse broken evidence, not print a reassuring summary.

`scripts/check.sh` runs the suite, the audit-citation check and the ledger check. These tests
keep the two non-suite halves honest by driving their failure paths: a citation that does not
resolve, a verdict that contradicts its document, and a ledger row whose note points nowhere.
"""
import csv
import tempfile
import unittest
from pathlib import Path

from espero2 import ledger
from research import audit_by_number as audit

FIELDS = ["id", "strategy", "status", "estimator", "estimator_matches_claim",
          "economic_bar", "basis", "note"]
ROW = dict(id="P1", strategy="sma", status="plumbing", estimator="plain",
           estimator_matches_claim="na", economic_bar="na", basis="", note="")


def ledger_file(tmp: str, **over) -> Path:
    p = Path(tmp) / "ledger.csv"
    with p.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerow({**ROW, **over})
    return p


class TestAuditCitationGate(unittest.TestCase):
    def findings(self) -> dict[str, dict]:
        return {k: dict(v) for k, v in audit.load_findings().items()}

    def test_the_committed_audit_still_validates(self):
        errors = audit.validate(audit.load_base(), audit.load_findings(), audit.own_runs())
        self.assertEqual(errors, [])

    def test_a_citation_to_a_missing_document_is_refused(self):
        findings = self.findings()
        findings["1"]["evidence"] = "research/no-such-evidence.md"
        errors = audit.validate(audit.load_base(), findings, audit.own_runs())
        self.assertTrue(any("no-such-evidence.md" in e for e in errors), errors)

    def test_a_citation_outside_the_repository_is_refused(self):
        findings = self.findings()
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("other project's file\n")
            outside = Path(f.name)
        self.addCleanup(outside.unlink)
        findings["1"]["evidence"] = str(outside)
        errors = audit.validate(audit.load_base(), findings, audit.own_runs())
        self.assertTrue(any("inside the repository" in e for e in errors), errors)

    def test_a_verdict_that_contradicts_the_recorded_decision_is_refused(self):
        base = [dict(r) for r in audit.load_base()]
        row = next(r for r in base if r["id"] == "2")     # the document says FAIL
        row["decision"] = "pass"
        errors = audit.validate(base, audit.load_findings(), audit.own_runs())
        self.assertTrue(any(e.startswith("2:") and "PASS" in e for e in errors), errors)


class TestLedgerCitationGate(unittest.TestCase):
    def test_the_committed_ledger_still_loads(self):
        self.assertGreater(len(ledger.load()), 0)

    def test_a_row_citing_a_real_document_loads(self):
        with tempfile.TemporaryDirectory() as d:
            rows = ledger.load(ledger_file(d, note="see research/AUDIT_BY_NUMBER.md"))
        self.assertEqual(rows["sma"].id, "P1")

    def test_a_row_citing_a_missing_document_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit) as e:
                ledger.load(ledger_file(d, note="see research/no-such-evidence.md"))
        self.assertIn("no-such-evidence.md", str(e.exception))


if __name__ == "__main__":
    unittest.main()
