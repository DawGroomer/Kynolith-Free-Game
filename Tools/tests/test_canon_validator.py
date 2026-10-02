#!/usr/bin/env python3
"""Run canon validator fixtures and assert the named rule for each failure."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "Tools" / "canon_validator.py"
FIX = ROOT / "Tools" / "tests" / "fixtures"
BASE = "8cf25ae349e7c0a7c1f344dcb3af5cd6188014a6"
BASE_ARG = ["--base", BASE]

PASS_CASES = [
    ("pass_unapproved.json", BASE_ARG),
    ("pass_approved.json", BASE_ARG),
    (
        "pass_append.json",
        ["--metrics", str(FIX / "metrics_appended.jsonl"), "--base", BASE],
    ),
]

# name, rule, extra args, expected FAIL count, required field tokens
FAIL_CASES = [
    ("fail_ref_past_end.json", "approval_ref_line_out_of_range", BASE_ARG, 1, []),
    ("fail_ref_line_zero.json", "approval_ref_line_out_of_range", BASE_ARG, 1, []),
    ("fail_ref_line_4.json", "approval_ref_event_not_approval", BASE_ARG, 1, []),
    ("fail_ref_line_3.json", "approval_ref_event_not_approval", BASE_ARG, 1, []),
    ("fail_ref_line_6.json", "approval_ref_event_not_approval", BASE_ARG, 1, []),
    ("fail_ref_line_7.json", "approval_ref_event_not_approval", BASE_ARG, 1, []),
    ("fail_tag_unapproved.json", "approval_ref_required", BASE_ARG, 1, []),
    ("fail_tag_unaproved.json", "approval_ref_required", BASE_ARG, 1, []),
    ("fail_tag_empty.json", "canon_tag_empty", BASE_ARG, 1, []),
    ("fail_tag_missing.json", "canon_tag_missing", BASE_ARG, 1, []),
    ("fail_no_echo.json", "approval_ref_malformed", BASE_ARG, 1, []),
    ("fail_text_canon.json", "text_not_placeholder", BASE_ARG, 1, ["text"]),
    ("fail_text_unapproved.json", "text_not_placeholder", BASE_ARG, 1, ["text"]),
    ("fail_id_spaces.json", "schema_invalid", BASE_ARG, 1, ["id"]),
    (
        "fail_approver.json",
        "approval_ref_approver_mismatch",
        ["--metrics", str(FIX / "metrics_approver.jsonl"), "--base", BASE],
        1,
        [],
    ),
    (
        "fail_words.json",
        "approval_ref_words_empty",
        ["--metrics", str(FIX / "metrics_words.jsonl"), "--base", BASE],
        1,
        [],
    ),
    (
        "fail_append_only.json",
        "metrics_line_not_byte_identical",
        ["--metrics", str(FIX / "metrics_edited.jsonl"), "--base", BASE],
        1,
        ["line_2"],
    ),
    (
        "fail_append_deleted.json",
        "metrics_line_not_byte_identical",
        ["--metrics", str(FIX / "metrics_deleted.jsonl"), "--base", BASE],
        1,
        ["line_5"],
    ),
    (
        "fail_append_swapped.json",
        "metrics_line_not_byte_identical",
        ["--metrics", str(FIX / "metrics_swapped.jsonl"), "--base", BASE],
        2,
        ["line_1", "line_2"],
    ),
    (
        "fail_base.json",
        "metrics_base_unreadable",
        ["--base", "deadbeef"],
        1,
        ["Metrics/tasks.jsonl"],
    ),
]


def run(args: list[str]) -> subprocess.CompletedProcess[str]:
    if "--base" not in args:
        raise SystemExit("missing explicit --base")
    cmd = [sys.executable, str(VALIDATOR), *args]
    print("COMMAND", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    print("EXIT", proc.returncode)
    print("STDOUT")
    sys.stdout.write(proc.stdout)
    if proc.stdout and not proc.stdout.endswith("\n"):
        print()
    print("STDERR")
    sys.stdout.write(proc.stderr)
    if proc.stderr and not proc.stderr.endswith("\n"):
        print()
    print("---")
    return proc


def string_values(value: object) -> list[str]:
    found: list[str] = []
    if isinstance(value, str):
        found.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            found.extend(string_values(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(string_values(item))
    return found


def values_that_must_stay_hidden(canon: dict, metrics_path: Path | None) -> list[str]:
    hidden = [item for key, item in canon.items() if key != "id" and isinstance(item, str)]
    if metrics_path is None:
        metrics_path = ROOT / "Metrics" / "tasks.jsonl"
    ref = canon.get("approval_ref")
    if not isinstance(ref, str) or "#L" not in ref:
        return [item for item in hidden if item]
    number = ref.rsplit("#L", 1)[-1]
    if not number.isdigit():
        return [item for item in hidden if item]
    line_no = int(number)
    lines = metrics_path.read_text(encoding="utf-8").splitlines()
    if 1 <= line_no <= len(lines):
        hidden.extend(string_values(json.loads(lines[line_no - 1])))
    return [item for item in hidden if item]


def metrics_arg(extra: list[str]) -> Path | None:
    if "--metrics" not in extra:
        return None
    return Path(extra[extra.index("--metrics") + 1])


def main() -> int:
    problems: list[str] = []
    approved = json.loads((FIX / "pass_approved.json").read_text(encoding="utf-8"))
    if approved.get("text") != "PLACEHOLDER_TEXT_001":
        problems.append("pass_approved.json text is not the placeholder")

    for name, extra in PASS_CASES:
        path = FIX / name
        proc = run([str(path), *extra])
        if proc.returncode != 0:
            problems.append(f"{name} should pass, exit {proc.returncode}")
        if proc.stdout.strip() != "OK":
            problems.append(f"{name} stdout is not OK")
        if proc.stderr:
            problems.append(f"{name} wrote stderr")
        canon = json.loads(path.read_text(encoding="utf-8"))
        blob = proc.stdout + proc.stderr
        for value in values_that_must_stay_hidden(canon, metrics_arg(extra)):
            if value in blob:
                problems.append(f"{name} echoed a field value")

    for name, rule, extra, count, fields in FAIL_CASES:
        path = FIX / name
        proc = run([str(path), *extra])
        fail_lines = [line for line in proc.stdout.splitlines() if line.startswith("FAIL ")]
        if proc.returncode == 0:
            problems.append(f"{name} should fail")
        if len(fail_lines) != count:
            problems.append(f"{name} expected {count} FAIL lines, got {len(fail_lines)}")
        for line in fail_lines:
            if f"rule={rule}" not in line:
                problems.append(f"{name} expected rule {rule}")
        for field in fields:
            if not any(f"field={field}" in line for line in fail_lines):
                problems.append(f"{name} missing field {field}")
        if proc.stderr:
            problems.append(f"{name} wrote stderr")
        canon = json.loads(path.read_text(encoding="utf-8"))
        blob = proc.stdout + proc.stderr
        for value in values_that_must_stay_hidden(canon, metrics_arg(extra)):
            if value in blob:
                problems.append(f"{name} echoed a field value")
        if name == "fail_no_echo.json":
            for sentinel in ("PLACEHOLDER_TEXT_001", "TAGVALUE_NO_ECHO", "REFVALUE_NO_ECHO"):
                if sentinel in blob:
                    problems.append(f"no-echo output contains {sentinel}")
            if "entry=ENTRY_NO_ECHO" not in proc.stdout:
                problems.append("no-echo output missing entry id")
            if "field=approval_ref" not in proc.stdout:
                problems.append("no-echo output missing field name")
        if name == "fail_append_only.json" and "pr_merged_before_reviewX" in blob:
            problems.append("append-only output echoed the edited line")
        if name == "fail_id_spaces.json":
            if "BAD ID" in blob:
                problems.append("schema output printed the bad id")
            if "entry=-" not in proc.stdout:
                problems.append("schema output did not use entry=-")
        if name == "fail_text_canon.json" and "Any real sentence." in blob:
            problems.append("text rule printed the text value")
        if name == "fail_text_unapproved.json" and "Any real sentence." in blob:
            problems.append("text rule printed the text value")

    non_json = run([str(FIX / "not_json" / "entry.txt"), "--base", BASE])
    non_json_fails = [line for line in non_json.stdout.splitlines() if line.startswith("FAIL ")]
    if non_json.returncode == 0 or non_json_fails != [
        "FAIL rule=data_file_not_json entry=- field=entry.txt"
    ]:
        problems.append("non-json fixture did not fail data_file_not_json")
    if "PLACEHOLDER_TEXT_001" in non_json.stdout + non_json.stderr:
        problems.append("non-json fixture echoed file text")
    if non_json.stderr:
        problems.append("non-json fixture wrote stderr")

    nested = FIX / "nested_schemas"
    nested_proc = run([str(nested), "--base", BASE])
    nested_fails = [line for line in nested_proc.stdout.splitlines() if line.startswith("FAIL ")]
    if nested_proc.returncode == 0 or nested_fails != [
        "FAIL rule=text_not_placeholder entry=ENTRY_NESTED_SCHEMAS field=text"
    ]:
        problems.append("nested schemas fixture did not fail text_not_placeholder")
    if "Any real sentence." in nested_proc.stdout + nested_proc.stderr:
        problems.append("nested schemas fixture echoed text")
    if nested_proc.stderr:
        problems.append("nested schemas fixture wrote stderr")

    data_proc = run(["--base", BASE])
    if data_proc.returncode != 0 or data_proc.stdout.strip() != "OK":
        problems.append("real Data/ folder did not pass")
    if "Structured project data." in data_proc.stdout + data_proc.stderr:
        problems.append("Data/ scan echoed README text")
    if data_proc.stderr:
        problems.append("real Data/ run wrote stderr")

    if problems:
        print("PROBLEMS")
        for problem in problems:
            print(problem)
        return 1
    print("ALL FIXTURE ASSERTIONS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
