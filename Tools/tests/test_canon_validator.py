#!/usr/bin/env python3
"""Run canon validator fixtures and assert the named rule for each failure."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "Tools" / "canon_validator.py"
FIX = ROOT / "Tools" / "tests" / "fixtures"
BASE = "8cf25ae349e7c0a7c1f344dcb3af5cd6188014a6"
# PR #4 merge. Lines 6 and 7 are unprotected against BASE.
BASE_PROTECTED = "3086759cd3349ccbd6dedbc0866f194aae3c1edb"
BASE_ARG = ["--base", BASE]
PROTECTED = ["--base", BASE_PROTECTED]
OTHER_METRICS = [
    "--metrics",
    str(FIX / "metrics_other_task.jsonl"),
    "--base",
    BASE_PROTECTED,
]

PASS_CASES = [
    ("pass_unapproved.json", BASE_ARG),
    ("pass_approved.json", BASE_ARG),
    (
        "pass_append.json",
        ["--metrics", str(FIX / "metrics_appended.jsonl"), "--base", BASE],
    ),
    ("pass_book.json", PROTECTED),
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
    ("fail_text_canon.json", "approval_ref_task_mismatch", BASE_ARG, 1, ["approval_ref"]),
    (
        "fail_text_unapproved.json",
        "approval_ref_task_mismatch",
        BASE_ARG,
        1,
        ["approval_ref"],
    ),
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
    ("fail_pages_missing.json", "source_pages_out_of_range", PROTECTED, 1, ["source_pages"]),
    ("fail_pages_7.json", "source_pages_out_of_range", PROTECTED, 1, ["source_pages"]),
    ("fail_pages_21.json", "source_pages_out_of_range", PROTECTED, 1, ["source_pages"]),
    ("fail_pages_mixed.json", "source_pages_out_of_range", PROTECTED, 1, ["source_pages"]),
    ("fail_brand_caps.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_phrase.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_split.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_model.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_short.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_word.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_spaced.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_plural.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_plural_caps.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_line.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_id.json", "brand_name_blocked", PROTECTED, 1, ["id"]),
    ("fail_book_other.json", "approval_ref_task_mismatch", OTHER_METRICS, 1, ["approval_ref"]),
    ("fail_book_near.json", "approval_ref_task_mismatch", OTHER_METRICS, 1, ["approval_ref"]),
]

# Validator stdout must not contain these. Entry ids are chosen so they do not.
HIDDEN_TOKENS = {
    "fail_brand_caps.json": ["ABLETON", "Ableton"],
    "fail_brand_phrase.json": ["Ableton", "Live"],
    "fail_brand_split.json": ["Audeze", "Au\ndeze"],
    "fail_brand_model.json": ["Maxwell"],
    "fail_brand_short.json": ["NIKE", "Nike"],
    "fail_brand_word.json": ["Cortez"],
    "fail_brand_spaced.json": ["Dark", "Magic"],
    "fail_brand_plural.json": ["Maxwells", "Maxwell"],
    "fail_brand_plural_caps.json": ["NIKES", "NIKE", "Nike"],
    "fail_brand_line.json": ["Dark", "Magic"],
    "fail_brand_id.json": ["NIKE", "Nike"],
    "fail_book_other.json": ["KG-OTHER-000", "A different task approval"],
    "fail_book_near.json": ["VS-001-S0-1", "A near miss approval"],
}


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


def load_validator():
    spec = importlib.util.spec_from_file_location("canon_validator", VALIDATOR)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load canon_validator")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_brand_probes(problems: list[str]) -> None:
    module = load_validator()
    blocked = [
        "ABLETON",
        "Ableton\nLive",
        "Au\ndeze",
        "Maxwell",
        "NIKE",
        "Cortez",
        "Cor\ntez",
        "Dark   Magic",
        "Dark\nMagic",
        "Audeze",
        "Maxwells",
        "NIKES",
        "Nikes",
        "Nike's",
        "Nike\u2019s",
    ]
    clear = [
        "live",
        "Live",
        "olive",
        "magic",
        "the show is live tonight",
        "nikel",
        "Maxwellian",
        "cortezes",
        "AbletonLive",
        "A neutral sentence says the show is live near olive and magic, nikel, Maxwellian, and cortezes.",
    ]
    for text in blocked:
        if not module.has_blocked_brand(text):
            problems.append("brand probe should match a blocked string")
    for text in clear:
        if module.has_blocked_brand(text):
            problems.append("brand probe matched a clear string")
    for path in sorted(FIX.rglob("*.json")):
        if path.name.startswith("fail_brand"):
            continue
        if path.parent.name == "broken_json":
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for field, value in module.string_fields(data):
            if module.has_blocked_brand(value):
                problems.append(f"brand false positive in {path.name} field {field}")
    for path in sorted(FIX.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            for field, value in module.string_fields(json.loads(line)):
                if module.has_blocked_brand(value):
                    problems.append(f"brand false positive in {path.name} field {field}")


def expect_fail(proc: subprocess.CompletedProcess[str], expected: list[str], label: str, problems: list[str]) -> None:
    fail_lines = [line for line in proc.stdout.splitlines() if line.startswith("FAIL ")]
    if proc.returncode == 0 or fail_lines != expected:
        problems.append(f"{label} did not fail as expected")
    if proc.stderr:
        problems.append(f"{label} wrote stderr")


def main() -> int:
    problems: list[str] = []
    approved = json.loads((FIX / "pass_approved.json").read_text(encoding="utf-8"))
    if approved.get("text") != "PLACEHOLDER_TEXT_001":
        problems.append("pass_approved.json text is not the placeholder")
    book = json.loads((FIX / "pass_book.json").read_text(encoding="utf-8"))
    if not isinstance(book.get("text"), str) or book["text"].startswith("PLACEHOLDER_"):
        problems.append("pass_book.json text should be non-placeholder")

    check_brand_probes(problems)

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
        for token in HIDDEN_TOKENS.get(name, []):
            if token in blob:
                problems.append(f"{name} echoed a blocked token")
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
        if name == "fail_brand_id.json":
            if "entry=-" not in proc.stdout:
                problems.append("brand id fixture should hide the entry id")
            if "entry=NIKE" in proc.stdout:
                problems.append("brand id fixture printed the entry id")

    non_json = run([str(FIX / "not_json" / "entry.txt"), "--base", BASE])
    expect_fail(
        non_json,
        ["FAIL rule=data_file_not_json entry=- field=Tools/tests/fixtures/not_json/entry.txt"],
        "non-json fixture",
        problems,
    )
    if "PLACEHOLDER_TEXT_001" in non_json.stdout + non_json.stderr:
        problems.append("non-json fixture echoed file text")

    nested = FIX / "nested_schemas"
    nested_proc = run([str(nested), "--base", BASE])
    expect_fail(
        nested_proc,
        [
            "FAIL rule=approval_ref_task_mismatch entry=ENTRY_NESTED_SCHEMAS field=approval_ref"
        ],
        "nested schemas fixture",
        problems,
    )
    if "Any real sentence." in nested_proc.stdout + nested_proc.stderr:
        problems.append("nested schemas fixture echoed text")

    broken = run([str(FIX / "broken_json" / "entry.json"), "--base", BASE])
    expect_fail(
        broken,
        ["FAIL rule=json_invalid entry=- field=Tools/tests/fixtures/broken_json/entry.json"],
        "broken json fixture",
        problems,
    )
    if "Broken json note 4403." in broken.stdout + broken.stderr:
        problems.append("broken json fixture echoed file text")

    missing = run([str(FIX / "missing_entry.json"), "--base", BASE])
    expect_fail(
        missing,
        ["FAIL rule=data_unreadable entry=- field=Tools/tests/fixtures/missing_entry.json"],
        "missing file",
        problems,
    )

    schema_sentence = "Neutral schema note number 4401."
    schema_extra = ROOT / "Data" / "schemas" / "x.json"
    schema_extra.write_text(
        json.dumps({"text": schema_sentence}, indent=2) + "\n",
        encoding="utf-8",
    )
    try:
        schema_proc = run([str(schema_extra), *PROTECTED])
        expect_fail(
            schema_proc,
            ["FAIL rule=schema_file_not_schema_json entry=- field=Data/schemas/x.json"],
            "Data/schemas/x.json",
            problems,
        )
        if schema_sentence in schema_proc.stdout + schema_proc.stderr:
            problems.append("Data/schemas/x.json echoed its sentence")
    finally:
        schema_extra.unlink(missing_ok=True)

    bad_sentence = "Broken schema note 4404."
    bad_schema = ROOT / "Data" / "schemas" / "broken.schema.json"
    bad_schema.write_text('{"title": "' + bad_sentence + '"\n', encoding="utf-8")
    try:
        bad_proc = run([str(bad_schema), *PROTECTED])
        expect_fail(
            bad_proc,
            ["FAIL rule=json_invalid entry=- field=Data/schemas/broken.schema.json"],
            "broken schema json",
            problems,
        )
        if bad_sentence in bad_proc.stdout + bad_proc.stderr:
            problems.append("broken schema json echoed its sentence")
    finally:
        bad_schema.unlink(missing_ok=True)

    sub = ROOT / "Data" / "sub"
    sub.mkdir(exist_ok=True)
    readme = sub / "README.md"
    readme_note = "Nested readme note 4402."
    readme.write_text(readme_note + "\n", encoding="utf-8")
    try:
        readme_proc = run([str(readme), *PROTECTED])
        expect_fail(
            readme_proc,
            ["FAIL rule=data_file_not_json entry=- field=Data/sub/README.md"],
            "Data/sub/README.md",
            problems,
        )
        if readme_note in readme_proc.stdout + readme_proc.stderr:
            problems.append("Data/sub/README.md echoed its text")
    finally:
        readme.unlink(missing_ok=True)
        if sub.exists():
            sub.rmdir()

    edited = run(
        [
            str(FIX / "pass_unapproved.json"),
            "--metrics",
            str(FIX / "metrics_line7_edited.jsonl"),
            "--base",
            BASE_PROTECTED,
        ]
    )
    expect_fail(
        edited,
        ["FAIL rule=metrics_line_not_byte_identical entry=- field=line_7"],
        "edited line 7 against base 3086759",
        problems,
    )
    edited_blob = edited.stdout + edited.stderr
    if "correction_of_line_2_EDIT" in edited_blob or "PLACEHOLDER_TEXT_001" in edited_blob:
        problems.append("edited line 7 output echoed text")

    data_proc = run(PROTECTED)
    if data_proc.returncode != 0 or data_proc.stdout.strip() != "OK":
        problems.append("real Data/ folder did not pass against base 3086759")
    data_blob = data_proc.stdout + data_proc.stderr
    if "Structured project data." in data_blob:
        problems.append("Data/ scan echoed README text")
    if "Kynolith canon entry" in data_blob:
        problems.append("Data/ scan echoed schema text")
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
