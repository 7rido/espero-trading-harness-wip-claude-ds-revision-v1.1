"""Generate the number-indexed audit: reference docs + our runs -> AUDIT_BY_NUMBER.md.

    python research/audit_by_number.py            # write the document
    python research/audit_by_number.py --check    # validate only (CI)
    python research/audit_by_number.py --compare-original PATH   # name+hash drift check (read-only)

Inputs
    research/audit_base.csv       one row per id (1-45 plus 9b): document, decision, rescore, note
    research/audit_findings.csv   one row per id: failure layer, why, remedy, evidence
    research/liqspike_run.json    our #21 replication (R1)
    research/sma-panel*.json      our SMA run (P1, no original number)
    reference/*.md                the original corpus, read-only

Writes only research/AUDIT_BY_NUMBER.md. Never touches reference/ or the original folder.
"""
from __future__ import annotations

import csv
import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
REF = ROOT / "reference"
BASE = ROOT / "research" / "audit_base.csv"
FINDINGS = ROOT / "research" / "audit_findings.csv"
OUT = ROOT / "research" / "AUDIT_BY_NUMBER.md"

DECISION_TO_VERDICT = {
    "pass": "PASS", "pass (prov.)": "PASS", "pass (plumbing)": "PASS",
    "fail": "FAIL", "real, not tradable": "REAL", "confirmed": "CONFIRMED",
    "running": "RUNNING", "measurement": "MEASUREMENT", "audit": "AUDIT",
    "no edge": "EXPLORATORY", "part A flat": "RUNNING",
}
NO_VERDICT_OK = {"RUNNING", "MEASUREMENT", "AUDIT", "PLUMBING"}
LAYERS = ("estimator", "economic", "selection", "execution", "process", "none")


def sort_key(i: str):
    m = re.match(r"(\d+)([a-z]?)", i)
    return (int(m.group(1)), m.group(2)) if m else (999, i)


def load_base() -> list[dict]:
    rows = list(csv.DictReader(BASE.open()))
    return sorted(rows, key=lambda r: sort_key(r["id"]))


def load_findings() -> dict[str, dict]:
    rows = list(csv.DictReader(FINDINGS.open()))
    return {r["id"]: r for r in rows}


def verdict_of(doc: pathlib.Path) -> tuple[str, str]:
    """(normalised verdict, quoted line) from the first 20 lines of a result document."""
    try:
        head = "\n".join(doc.read_text().splitlines()[:20])
    except OSError:
        return "", ""
    m = re.search(r"Verdict:?\s*\**\s*([^\n*]{0,120})", head)
    if m:
        line = m.group(0).strip()
        low = line.lower()
        if "fail" in low:
            return "FAIL", line
        if "pass" in low:
            return "PASS", line
        if "real, not tradable" in low:
            return "REAL", line
        if "no" in low and ("NO" in line or low.strip().endswith("no")):
            return "NO", line
    if re.search(r"\bCONFIRMED\b", head):
        return "CONFIRMED", next(l for l in head.splitlines() if "CONFIRMED" in l).strip()
    if re.search(r"\bexploratory\b", head, re.I):
        return "EXPLORATORY", next(l for l in head.splitlines() if "exploratory" in l.lower()).strip()
    return "", ""


def own_runs() -> list[dict]:
    runs = []
    liq = ROOT / "research" / "liqspike_run.json"
    if liq.exists():
        r = json.loads(liq.read_text())
        runs.append({"id": "R1", "maps_to": "21", "test": "#21 replication on sealed months",
                     "statistic": (f"day-mean {r['c1']['mean_bps']:+.1f} bps (t {r['c1']['t']:.2f}); "
                                   f"trade-weighted {r['c1']['trade_weighted_bps']:+.1f} bps "
                                   f"(t {r['c1']['trade_weighted_t']:.2f})"),
                     "verdict": r["verdict"], "artifact": "research/RESULTS_2026-10-30-liqspike.md"})
    sma = ROOT / "research" / "sma-panel.json"
    if sma.exists():
        r = json.loads(sma.read_text())
        long_only = ROOT / "research" / "sma-panel-long.json"
        lo = json.loads(long_only.read_text()) if long_only.exists() else None
        stat = (f"long/short {r['stats']['cagr_pct']:+.1f}% CAGR, Sharpe {r['stats']['sharpe']:.2f}, "
                f"DD {r['stats']['maxdd_pct']:.1f}%")
        if lo:
            stat += (f"; long-only {lo['stats']['cagr_pct']:+.1f}% CAGR, "
                     f"Sharpe {lo['stats']['sharpe']:.2f}")
        runs.append({"id": "P1", "maps_to": "", "test": "SMA 20/50 regime on the panel",
                     "statistic": stat, "verdict": "EXPLORATORY",
                     "artifact": "research/2026-10-30-sma-panel.md"})
    return runs


def validate(base, findings, runs) -> list[str]:
    errors = []
    ids = [r["id"] for r in base]
    expected = [str(i) for i in range(1, 46)] + ["9b"]
    if sorted(ids) != sorted(expected):
        errors.append(f"coverage: expected 46 ids, got {len(ids)} ({' '.join(ids)})")
    if set(findings) != set(ids):
        errors.append(f"findings ids differ: missing {set(ids) - set(findings)}, "
                      f"extra {set(findings) - set(ids)}")
    for r in base:
        doc = ROOT / r["document"]
        if not doc.exists():
            errors.append(f"{r['id']}: missing document {r['document']}")
            continue
        f = findings.get(r["id"], {})
        if f.get("failure_layer") not in LAYERS:
            errors.append(f"{r['id']}: bad failure_layer {f.get('failure_layer')!r}")
        if not f.get("why") or not f.get("remedy"):
            errors.append(f"{r['id']}: why/remedy missing")
        evidence = f.get("evidence", "")
        ev = (ROOT / evidence).resolve() if evidence else None
        inside = ev is not None and ROOT.resolve() in ev.parents and ev.is_file()
        if not inside:
            errors.append(f"{r['id']}: evidence {evidence!r} does not resolve to a file "
                          "inside the repository")
        want = DECISION_TO_VERDICT.get(r["decision"], "")
        got, _ = verdict_of(doc)
        if want and got and want != got:
            errors.append(f"{r['id']}: document says {got}, base says {want}")
        no_standalone = pathlib.Path(r["document"]).name in {"FINDINGS.md", "LP_NOTES.md"}
        if want and not got and want not in NO_VERDICT_OK and not no_standalone:
            errors.append(f"{r['id']}: no verdict found in {r['document']} (base says {want})")
    for run in runs:
        art = ROOT / run["artifact"]
        if not art.exists():
            errors.append(f"{run['id']}: artifact {run['artifact']} missing")
    return errors


def compare_original(path: pathlib.Path) -> list[str]:
    diffs = []
    if not path.exists():
        return [f"original folder not found: {path}"]
    for doc in sorted(REF.glob("*.md")):
        other = path / doc.name
        if not other.exists():
            diffs.append(f"only in reference: {doc.name}")
            continue
        a = hashlib.sha256(doc.read_bytes()).hexdigest()
        b = hashlib.sha256(other.read_bytes()).hexdigest()
        if a != b:
            diffs.append(f"content differs: {doc.name}")
    for other in sorted(path.glob("*.md")):
        if not (REF / other.name).exists():
            diffs.append(f"only in original: {other.name}")
    return diffs


def render(base, findings, runs, checks: dict) -> str:
    from collections import Counter
    dist = Counter(r["rescore"] for r in base)
    layers = Counter(findings[r["id"]]["failure_layer"] for r in base)
    lines = [
        "# Audit by number",
        "",
        "Every test in the original corpus, one row each, with what it claimed, what it decided, what",
        "evidence exists here, why it failed, and the smallest change that would give it a chance.",
        "Generated by `research/audit_by_number.py` from `reference/` (read-only), `audit_base.csv`,",
        "`audit_findings.csv` and our own runs. Do not edit by hand; edit the inputs.",
        "",
        "## Scope and provenance",
        "",
        f"- 46 ids: #1-#45 plus #9b. Documents: {checks['docs']} reference files, all resolved.",
        f"- Verdict check: {checks['verdict_ok']}/{checks['verdict_checked']} parsed verdicts agree "
        "with the recorded decision.",
        f"- Original comparison: {checks['original']}.",
        "- Forward tests are listed but not judged; nothing here reads a running result.",
        "",
        "## Distribution",
        "",
        "| rescored | count |", "|---|---|",
    ]
    for k, v in dist.most_common():
        lines.append(f"| {k} | {v} |")
    lines += ["", "## Why they failed, by layer", "",
              "| layer | count | what it means |", "|---|---|---|",
              f"| estimator | {layers['estimator']} | the statistic did not match the claim (day-mean, "
              "overlapping labels, untested Sharpe) |",
              f"| process | {layers['process']} | a criterion was not computed, a run repeated, a window "
              "dropped, or a step not judged |",
              f"| selection | {layers['selection']} | the window or universe was chosen after seeing the data |",
              f"| execution | {layers['execution']} | the fills were not obtainable at the assumed price or queue |",
              f"| none | {layers['none']} | clean failures, running tests, measurements and audits |",
              "", "## The table", "",
              "| # | hypothesis | original | our evidence | layer | why it failed | what would fix it |",
              "|---|---|---|---|---|---|---|"]
    runs_by_id = {r["maps_to"]: r for r in runs if r["maps_to"]}
    for r in base:
        f = findings[r["id"]]
        ev = "replicated (R1)" if r["id"] in runs_by_id else "ported audit"
        lines.append(f"| {r['id']} | {r['hypothesis']} | {r['rescore']} | {ev} | "
                     f"{f['failure_layer']} | {f['why']} | {f['remedy']} |")
    lines += ["", "## Our own runs", "",
              "| id | maps to | test | statistic | verdict | artifact |", "|---|---|---|---|---|---|"]
    for run in runs:
        lines.append(f"| {run['id']} | {run['maps_to'] or '-'} | {run['test']} | {run['statistic']} | "
                     f"{run['verdict']} | `{run['artifact']}` |")
    lines += ["",
              "## What would make it work — by family", "",
              "- **Event studies (#18-#35):** trade-weighted, day-clustered, net of the venue's measured",
              "  cost; classify at signal time, not at day end; hold where the edge survives cost. Needs",
              "  new days: the sealed months are exhausted.",
              "- **Cross-sectional (#2, #7, #8, #16, #17):** a survivorship-free panel including dead",
              "  coins, a spread-or-P&L hurdle paired with every IC hurdle, turnover priced at the",
              "  measured fee.",
              "- **Carry (#11, #12, #14):** the fee-real venue, a maker-queue model, funding at the venue",
              "  that holds the position; no zero-cost assumption.",
              "- **Trend (#4):** deflated Sharpe against an exposure-matched benchmark, inputs committed",
              "  with a hash manifest.",
              "- **Microstructure (#30, #39, #41):** real queue and fill data; this family is the repo's",
              "  strongest work and needs no rescue.",
              "", "## What cannot be fixed", "",
              "- #21 on this dataset (sealed months exhausted), #4 without its input series, #9b by",
              "  construction, #7's abandoned forward test.",
              "",
              "## Verification", "",
              "```",
              f"documents resolved   {checks['docs']}/{checks['docs']}",
              f"verdicts checked     {checks['verdict_ok']}/{checks['verdict_checked']}",
              f"findings cited       {checks['cited']}/{len(base)}",
              f"original comparison  {checks['original']}",
              "```", ""]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    base, findings, runs = load_base(), load_findings(), own_runs()
    errors = validate(base, findings, runs)
    checks = {"docs": sum(1 for r in base if (ROOT / r["document"]).exists()),
              "verdict_checked": 0, "verdict_ok": 0,
              "cited": sum(1 for r in base if (ROOT / findings[r["id"]]["evidence"]).exists()),
              "original": "not run"}
    for r in base:
        got, _ = verdict_of(ROOT / r["document"])
        if got:
            checks["verdict_checked"] += 1
            if got == DECISION_TO_VERDICT.get(r["decision"], got):
                checks["verdict_ok"] += 1
    if "--compare-original" in argv:
        path = pathlib.Path(argv[argv.index("--compare-original") + 1])
        diffs = compare_original(path)
        checks["original"] = "identical" if not diffs else f"{len(diffs)} difference(s)"
        errors += diffs
    if errors:
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        return 1
    if "--check" in argv:
        print(f"ok: {len(base)} ids, {checks['docs']} documents, "
              f"{checks['verdict_ok']}/{checks['verdict_checked']} verdicts agree, "
              f"{checks['cited']} findings cited")
        return 0
    OUT.write_text(render(base, findings, runs, checks))
    print(f"wrote {OUT.relative_to(ROOT)} ({len(base)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
