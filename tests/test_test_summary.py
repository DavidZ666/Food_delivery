from pathlib import Path

import pytest

from scripts.summarize_tests import summarize


@pytest.mark.parametrize("wrapper", ["testsuite", "testsuites"])
def test_summary_counts_and_failure_names(tmp_path: Path, wrapper: str):
    suite = '''<testsuite tests="5" failures="1" errors="1" skipped="1">
      <testcase classname="tests.example" name="passed"/>
      <testcase classname="tests.example" name="also_passed"/>
      <testcase classname="tests.example" name="failed"><failure/></testcase>
      <testcase classname="tests.example" name="error"><error/></testcase>
      <testcase classname="tests.example" name="skipped"><skipped/></testcase>
    </testsuite>'''
    report = tmp_path / "results.xml"
    report.write_text(suite if wrapper == "testsuite" else f"<testsuites>{suite}</testsuites>")
    summary = summarize(report)
    assert "| 5 | 2 | 1 | 1 | 1 |" in summary
    assert "<code>tests.example.failed</code>" in summary
    assert "<code>tests.example.error</code>" in summary
    assert "tests.example.passed" not in summary


def test_all_passing_report(tmp_path: Path):
    report = tmp_path / "results.xml"
    report.write_text('<testsuite tests="2" failures="0" errors="0" skipped="0"/>')
    summary = summarize(report)
    assert "| 2 | 2 | 0 | 0 | 0 |" in summary
    assert "Failed tests" not in summary


@pytest.mark.parametrize("content", [None, "invalid xml", "<testsuites/>"])
def test_unavailable_results(tmp_path: Path, content: str | None):
    report = tmp_path / "results.xml"
    if content is not None:
        report.write_text(content)
    assert "Results unavailable" in summarize(report)


def test_failure_names_escape_html(tmp_path: Path):
    report = tmp_path / "results.xml"
    report.write_text('''<testsuite tests="1" failures="1">
      <testcase name="&lt;script&gt;"><failure/></testcase>
    </testsuite>''')
    assert "<code>&lt;script&gt;</code>" in summarize(report)
