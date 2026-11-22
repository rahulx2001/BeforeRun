"""Run mapped offline core contracts once and save pass/fail without inference claims."""

from __future__ import annotations

import argparse
import json
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    matrix = json.loads(Path(__file__).with_name("core_matrix.json").read_text())
    selectors = sorted({selector for case in matrix["cases"] for selector in case["selectors"]})
    with tempfile.TemporaryDirectory(prefix="beforerun-gates-") as directory:
        report = Path(directory) / "junit.xml"
        result = pytest.main(
            ["-q", "-m", "not live and not browser", *selectors, "--junitxml=" + str(report)]
        )
        records = list(ET.parse(report).getroot().iter("testcase")) if report.exists() else []
    cases = []
    for case in matrix["cases"]:
        matched = []
        missing = []
        for selector in case["selectors"]:
            module, function = selector.split("::", 1)
            module_name = Path(module).stem
            tests = [
                record
                for record in records
                if record.get("classname", "").endswith(module_name)
                and (
                    record.get("name") == function
                    or record.get("name", "").startswith(function + "[")
                )
            ]
            matched.extend(tests)
            if not tests:
                missing.append(selector)
        failed = any(
            record.find("failure") is not None or record.find("error") is not None
            for record in matched
        )
        skipped = any(record.find("skipped") is not None for record in matched)
        cases.append(
            {
                "id": case["id"],
                "case": case["case"],
                "status": "not_run"
                if missing
                else "failed"
                if failed
                else "skipped"
                if skipped
                else "passed",
                "tests": len(matched),
                "missing": missing,
                "scope": "offline development contract",
            }
        )
    value = {
        "scope": matrix["scope"],
        "live_status": matrix["live_status"],
        "cases": cases,
        "release_ready": False,
        "pytest_exit_code": int(result),
    }
    args.output.write_text(json.dumps(value, indent=2) + "\n")
    return int(result) or int(any(case["status"] != "passed" for case in cases))


if __name__ == "__main__":
    raise SystemExit(main())
