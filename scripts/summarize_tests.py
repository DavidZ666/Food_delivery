"""Render a pytest JUnit report as a GitHub Actions job summary."""

import html
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


def summarize(report: Path) -> str:
    heading = "## Automated test results\n\n"
    if not report.is_file():
        return heading + "Results unavailable: no JUnit report was generated. Check the job logs for setup or test execution errors.\n"
    try:
        root = ET.parse(report).getroot()
        suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
        if not suites:
            raise ValueError("No test suites found")
        counts = {
            key: sum(int(suite.get(key, "0")) for suite in suites)
            for key in ("tests", "failures", "errors", "skipped")
        }
    except (ET.ParseError, ValueError, OSError):
        return heading + "Results unavailable: the JUnit report could not be read. Check the job logs and report artifact.\n"

    passed = counts["tests"] - counts["failures"] - counts["errors"] - counts["skipped"]
    summary = heading + (
        "| Total | Passed | Failed | Errors | Skipped |\n"
        "| --- | --- | --- | --- | --- |\n"
        f"| {counts['tests']} | {passed} | {counts['failures']} | {counts['errors']} | {counts['skipped']} |\n"
    )
    failed = []
    for case in root.iter("testcase"):
        if case.find("failure") is not None or case.find("error") is not None:
            name = ".".join(filter(None, (case.get("classname"), case.get("name"))))
            failed.append(f"- <code>{html.escape(name)}</code>\n")
    if failed:
        summary += "\n### Failed tests and errors\n\n" + "".join(failed)
    if counts["tests"] == 0:
        summary += "\nNo tests were reported. Check the test execution logs.\n"
    return summary


if __name__ == "__main__":
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as output:
        output.write(summarize(Path(sys.argv[1])))
