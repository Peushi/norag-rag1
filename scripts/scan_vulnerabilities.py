"""Scan BakeFix's pinned packages for known vulnerabilities and write a VEX file.

    python -m pip install -r requirements-dev.txt   # once (pip-audit)
    python scripts/scan_vulnerabilities.py

1. pip-audit checks every package in requirements.lock.txt (PyPI advisory
   and OSV databases); npm audit checks frontend/package-lock.json.
2. Each finding is matched with our decision in aibom/vulnerability-triage.json.
3. aibom/bakefix.vex.cdx.json (CycloneDX 1.6 VEX) records every finding and
   decision, pointing at the components in aibom/bakefix.cdx.json.

Exits 1 if a finding has no decision yet, so a new vulnerability cannot be
ignored silently. Needs network access; the result changes as new
vulnerabilities are published, so it is a command to run, not a unit test.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOM_FILE = ROOT / "aibom" / "bakefix.cdx.json"
TRIAGE_FILE = ROOT / "aibom" / "vulnerability-triage.json"
VEX_FILE = ROOT / "aibom" / "bakefix.vex.cdx.json"


def pip_findings() -> list[dict]:
    # pip-audit cannot resolve direct URL lines (the spaCy model wheel); that
    # wheel is pinned by hash and is not in the PyPI advisory database anyway.
    lines = [l for l in (ROOT / "requirements.lock.txt").read_text().splitlines() if " @ " not in l]
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as handle:
        handle.write("\n".join(lines) + "\n")
    result = subprocess.run(
        [sys.executable, "-m", "pip_audit", "-r", handle.name, "--no-deps", "--disable-pip",
         "-f", "json", "--progress-spinner", "off"],
        capture_output=True, text=True,
    )
    Path(handle.name).unlink()
    if result.returncode not in (0, 1) or not result.stdout.strip():
        raise SystemExit(f"pip-audit failed:\n{result.stderr}")
    findings = []
    for package in json.loads(result.stdout)["dependencies"]:
        for vuln in package.get("vulns", []):
            normalised = re.sub(r"[-_.]+", "-", package["name"]).lower()
            findings.append({
                "id": vuln["id"],
                "aliases": vuln.get("aliases", []),
                "package": package["name"],
                "ref": f"pkg:pypi/{normalised}@{package['version']}",
                "description": vuln.get("description", "").strip().split("\n")[0][:500],
                "fix_versions": vuln.get("fix_versions", []),
                "source": "pip-audit",
            })
    return findings


def npm_findings() -> list[dict]:
    result = subprocess.run(
        ["npm", "audit", "--package-lock-only", "--json"],
        cwd=ROOT / "frontend", capture_output=True, text=True,
    )
    report = json.loads(result.stdout or "{}")
    if "vulnerabilities" not in report:
        raise SystemExit(f"npm audit failed:\n{result.stderr}")
    lock = json.loads((ROOT / "frontend" / "package-lock.json").read_text())["packages"]
    findings = []
    for name, entry in report["vulnerabilities"].items():
        version = lock.get(f"node_modules/{name}", {}).get("version", "unknown")
        purl_name = name.replace("@", "%40", 1) if name.startswith("@") else name
        for via in entry["via"]:
            if not isinstance(via, dict):
                continue  # vulnerable only through another package, listed on its own
            advisory = via.get("url", "").rstrip("/").split("/")[-1]
            findings.append({
                "id": advisory or str(via.get("source")),
                "aliases": [],
                "package": name,
                "ref": f"pkg:npm/{purl_name}@{version}",
                "description": via.get("title", ""),
                "fix_versions": [],
                "severity": via.get("severity"),
                "source": "npm audit",
            })
    return findings


def find_decision(decisions: list[dict], finding: dict) -> dict | None:
    names = {finding["id"], *finding["aliases"]}
    return next(
        (d for d in decisions if d["package"] == finding["package"] and names & set(d["ids"])),
        None,
    )


def vulnerability(finding_id, aliases, source, description, affects_ref, decision, serial, fixes=()):
    entry = {
        "id": finding_id,
        "source": {"name": source},
        "description": description,
        "affects": [{"ref": f"{serial}/1#{affects_ref}"}],
        "analysis": {"state": decision["state"] if decision else "in_triage"},
    }
    if aliases:
        entry["references"] = [{"id": a, "source": {"name": "alias"}} for a in sorted(set(aliases))]
    if decision:
        entry["analysis"]["detail"] = decision["detail"]
        if decision.get("justification"):
            entry["analysis"]["justification"] = decision["justification"]
        entry["analysis"]["response"] = decision["response"]
        entry["analysis"]["lastUpdated"] = f"{decision['decided']}T00:00:00Z"
    if fixes:
        entry["recommendation"] = f"Upgrade to {', '.join(fixes)}."
    return entry


def main() -> int:
    bom = json.loads(BOM_FILE.read_text())
    serial = bom["serialNumber"].replace("urn:uuid:", "urn:cdx:")
    refs = {c["bom-ref"] for c in bom["components"]}
    decisions = json.loads(TRIAGE_FILE.read_text())["decisions"]

    findings = pip_findings() + npm_findings()
    vulnerabilities, untriaged, seen = [], [], set()
    for finding in findings:
        key = (finding["package"], finding["id"])
        if key in seen:
            continue
        seen.add(key)
        if finding["ref"] not in refs:
            print(f"WARNING: {finding['ref']} is not in the AI-BOM; regenerate it first", file=sys.stderr)
        decision = find_decision(decisions, finding)
        if decision is None or decision["state"] == "resolved":
            untriaged.append(finding)
            decision = None
        vulnerabilities.append(vulnerability(
            finding["id"], finding["aliases"], finding["source"], finding["description"],
            finding["ref"], decision, serial, finding["fix_versions"],
        ))

    # Keep a record of what we fixed by upgrading (no longer reported by the scanners).
    for decision in decisions:
        if decision["state"] != "resolved":
            continue
        normalised = re.sub(r"[-_.]+", "-", decision["package"]).lower()
        vulnerabilities.append(vulnerability(
            decision["ids"][0], decision["ids"][1:], "pip-audit", decision["detail"],
            f"pkg:pypi/{normalised}@{decision['affected_version']}", decision, serial,
            [decision["fixed_in"]],
        ))
        # The affected version is no longer in the BOM; say which version replaced it.
        vulnerabilities[-1]["affects"] = [{
            "ref": f"{serial}/1#pkg:pypi/{normalised}@{decision['fixed_in']}",
            "versions": [{"version": decision["affected_version"], "status": "affected"},
                         {"version": decision["fixed_in"], "status": "unaffected"}],
        }]

    vex = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "version": 1,
        "metadata": {
            "timestamp": f"{date.today().isoformat()}T00:00:00Z",
            "component": bom["metadata"]["component"],
            "properties": [{"name": "bakefix:scanned", "value": "pip-audit on requirements.lock.txt; npm audit on frontend/package-lock.json"}],
        },
        "vulnerabilities": vulnerabilities,
    }
    VEX_FILE.write_text(json.dumps(vex, indent=2, ensure_ascii=False) + "\n")

    open_count = sum(v["analysis"]["state"] in {"in_triage", "exploitable"} for v in vulnerabilities)
    print(f"{len(findings)} findings from the scanners ({len(seen)} unique); "
          f"{len(vulnerabilities)} recorded in {VEX_FILE.relative_to(ROOT)}; {open_count} open")
    for finding in untriaged:
        print(f"NEEDS A DECISION: {finding['package']} {finding['id']}: {finding['description'][:120]}",
              file=sys.stderr)
    return 1 if untriaged else 0


if __name__ == "__main__":
    sys.exit(main())
