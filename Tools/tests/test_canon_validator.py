#!/usr/bin/env python3
"""Run canon validator fixtures and assert the named rule for each failure."""

from __future__ import annotations

import importlib.util
import json
import re
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
HEAD_ARG = ["--base", "HEAD"]
OTHER_METRICS = [
    "--metrics",
    str(FIX / "metrics_other_task.jsonl"),
    "--base",
    BASE_PROTECTED,
]

PASS_CASES = [
    ("pass_unapproved.json", BASE_ARG),
    ("pass_approved.json", BASE_ARG),
    ("pass_game_canon.json", BASE_ARG),
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
    ("fail_tag_unapproved.json", "canon_tag_not_allowed", BASE_ARG, 1, ["canon_tag"]),
    ("fail_tag_unaproved.json", "canon_tag_not_allowed", BASE_ARG, 1, ["canon_tag"]),
    ("fail_tag_needs_ref.json", "approval_ref_required", BASE_ARG, 1, ["approval_ref"]),
    ("fail_tag_empty.json", "canon_tag_empty", BASE_ARG, 1, []),
    ("fail_tag_missing.json", "canon_tag_missing", BASE_ARG, 1, []),
    ("fail_no_echo.json", "approval_ref_malformed", BASE_ARG, 1, []),
    ("fail_text_canon.json", "book_text_must_be_unapproved", BASE_ARG, 1, ["canon_tag"]),
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
    ("fail_pages_missing.json", "approval_ref_not_at_base", PROTECTED, 1, ["approval_ref"]),
    ("fail_pages_7.json", "approval_ref_not_at_base", PROTECTED, 1, ["approval_ref"]),
    ("fail_pages_21.json", "approval_ref_not_at_base", PROTECTED, 1, ["approval_ref"]),
    ("fail_pages_mixed.json", "approval_ref_not_at_base", PROTECTED, 1, ["approval_ref"]),
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
    ("fail_brand_placeholder.json", "brand_name_blocked", PROTECTED, 1, ["canon_tag"]),
    ("fail_brand_id_suffix.json", "brand_name_blocked", PROTECTED, 1, ["id"]),
    ("fail_tag_long.json", "schema_invalid", PROTECTED, 1, ["canon_tag"]),
    ("fail_tag_pattern.json", "canon_tag_not_allowed", PROTECTED, 1, ["canon_tag"]),
    ("fail_id_long.json", "schema_invalid", PROTECTED, 1, ["id"]),
    ("fail_placeholder_long.json", "placeholder_too_long", PROTECTED, 1, ["text"]),
    ("fail_brand_homoglyph.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_fullwidth.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_math.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_combining.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_hyphen.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_hyphen_nl.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_dotted.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_es.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_gap_01.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_gap_02.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_gap_03.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_gap_04.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_gap_05.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_gap_06.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_gap_07.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_gap_08.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_cyrillic_i.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_suffix_x.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_suffix_digit.json", "brand_name_blocked", PROTECTED, 1, ["text"]),
    ("fail_brand_zwsp.json", "forbidden_invisible_char", PROTECTED, 1, ["Tools/tests/fixtures/fail_brand_zwsp.json"]),
    ("fail_brand_zwnj.json", "forbidden_invisible_char", PROTECTED, 1, ["Tools/tests/fixtures/fail_brand_zwnj.json"]),
    ("fail_brand_zwj.json", "forbidden_invisible_char", PROTECTED, 1, ["Tools/tests/fixtures/fail_brand_zwj.json"]),
    ("fail_brand_bom.json", "forbidden_invisible_char", PROTECTED, 1, ["Tools/tests/fixtures/fail_brand_bom.json"]),
    ("fail_feff_leading.json", "forbidden_invisible_char", PROTECTED, 1, ["Tools/tests/fixtures/fail_feff_leading.json"]),
    ("fail_brand_wj.json", "forbidden_invisible_char", PROTECTED, 1, ["Tools/tests/fixtures/fail_brand_wj.json"]),
    ("fail_brand_shy.json", "forbidden_invisible_char", PROTECTED, 1, ["Tools/tests/fixtures/fail_brand_shy.json"]),
    ("fail_brand_cr.json", "forbidden_invisible_char", PROTECTED, 1, ["text"]),
    ("fail_brand_ls.json", "forbidden_invisible_char", PROTECTED, 1, ["Tools/tests/fixtures/fail_brand_ls.json"]),
    ("fail_brand_ps.json", "forbidden_invisible_char", PROTECTED, 1, ["Tools/tests/fixtures/fail_brand_ps.json"]),
    ("fail_brand_rtl.json", "forbidden_invisible_char", PROTECTED, 1, ["Tools/tests/fixtures/fail_brand_rtl.json"]),
    ("fail_book_marks.json", "approval_ref_not_at_base", PROTECTED, 1, ["approval_ref"]),
    ("fail_book_tag_canon.json", "book_text_must_be_unapproved", PROTECTED, 1, ["canon_tag"]),
    ("fail_book_tag_game.json", "book_text_must_be_unapproved", PROTECTED, 1, ["canon_tag"]),
    ("fail_dup_text.json", "json_duplicate_key", PROTECTED, 1, ["text"]),
    ("fail_dup_pages.json", "json_duplicate_key", PROTECTED, 1, ["source_pages"]),
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
        "cortezes",
        "Cortezes",
        "N\u0456ke",
        "N\u0131ke",
        "Ni-ke",
        "N.i.k.e",
        "Ni-\nke",
        "Nike_x",
        "Nike7",
        "NIKE_SCENE",
        "N" + "\u0456" + "k" + "\u0435",
        "C" + "\u03bf" + "rtez",
        "".join(chr(0xFF21 + ord(char) - ord("A")) for char in "NIKE"),
        "".join(chr(0x1D41A + (ord(char) - ord("a"))) for char in "nike"),
        "Ni\u0301ke",
        "N i k e",
        "Ni ke",
        "Ni_ke",
        "N\tike",
        "Max well",
        "A ble ton",
        "AbletonLive",
        "DarkMagic",
    ]
    clear = [
        "live",
        "Live",
        "olive",
        "magic",
        "the show is live tonight",
        "nikel",
        "Maxwellian",
        "magical",
        "lives",
        "olives",
        "a dark, magical evening",
        "well-known",
        "See note 3.1. The show is live.",
        "a well-known live show near an olive tree.",
        "The well-known show is live tonight near an olive tree and a magic lantern.",
        "A neutral sentence says the show is live near olive and magic, nikel, and Maxwellian.",
    ]
    forbidden = [
        "Ni\u200bke",
        "Ni\u200cke",
        "Ni\u200dke",
        "\ufeffNike",
        "Ni\u2060ke",
        "Ni\u00adke",
        "Ni\rke",
        "Ni\u2028ke",
        "Ni\u2029ke",
        "\u202eNike",
    ]
    for text in blocked:
        if not module.has_blocked_brand(text):
            problems.append("brand probe should match a blocked string")
    for text in clear:
        if module.has_blocked_brand(text):
            problems.append("brand probe matched a clear string")
    for text in forbidden:
        if not module.has_forbidden_invisible(text):
            problems.append("invisible probe was not rejected")
    for path in sorted(FIX.rglob("*.json")):
        if path.name.startswith("fail_brand"):
            continue
        if path.parent.name == "broken_json":
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
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
    module = load_validator()
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
        before_bytes = path.read_bytes()
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
        raw_text = path.read_text(encoding="utf-8")
        if name == "fail_book_marks.json":
            if path.read_bytes() != before_bytes:
                problems.append("validator rewrote stored book punctuation")
            marks = "\u2026\u2019\u2014\u00e9\u0101"
            if any(char not in raw_text for char in marks):
                problems.append("book punctuation missing from the stored fixture")
            if module.has_forbidden_invisible(raw_text):
                problems.append("book punctuation was flagged as invisible")
        try:
            canon = json.loads(raw_text)
        except json.JSONDecodeError:
            canon = None
        blob = proc.stdout + proc.stderr
        if canon is not None:
            for value in values_that_must_stay_hidden(canon, metrics_arg(extra)):
                if value in blob:
                    problems.append(f"{name} echoed a field value")
        for token in HIDDEN_TOKENS.get(name, []):
            if token in blob:
                problems.append(f"{name} echoed a blocked token")
        for token in re.findall(r"[^\W\d_]+", raw_text, flags=re.UNICODE):
            if module.has_blocked_brand(token) and token in blob:
                problems.append(f"{name} echoed a blocked token")
        if isinstance(canon, dict) and isinstance(canon.get("id"), str):
            entry_name = canon["id"]
            if module.has_blocked_brand(entry_name) and entry_name in blob:
                problems.append(f"{name} printed a blocked entry id")
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
            [
                "FAIL rule=schema_file_not_schema_json entry=- field=Data/schemas/broken.schema.json"
            ],
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

    metric_bytes = (ROOT / "Metrics" / "tasks.jsonl").read_bytes().split(b"\n")
    if metric_bytes[-1] == b"":
        metric_bytes.pop()
    if module.line_digest(metric_bytes[8]) != module.BOOK_APPROVAL_SHA256:
        problems.append("approval line digest does not match the pin")
    if module.BOOK_APPROVAL_LINE != 9:
        problems.append("approval line number is not 9")

    expected_tags = {
        "CANON",
        "GAME CANON",
        "PLACEHOLDER_TAG",
        "TAGVALUE_NO_ECHO",
        "UNAPPROVED",
    }
    if set(module.ALLOWED_CANON_TAGS) != expected_tags:
        problems.append("canon tag allowlist does not match the closed set")

    book_at_head = run([str(FIX / "pass_book.json"), *HEAD_ARG])
    expect_fail(
        book_at_head,
        ["FAIL rule=metrics_base_not_ancestor entry=- field=Metrics/tasks.jsonl"],
        "base HEAD is not an ancestor of origin/main",
        problems,
    )
    book_off_base = run([str(FIX / "pass_book.json"), *PROTECTED])
    expect_fail(
        book_off_base,
        ["FAIL rule=approval_ref_not_at_base entry=ENTRY_BOOK_OK field=approval_ref"],
        "book text before the pinned line is on the base",
        problems,
    )

    def metrics_case(label: str, metrics_name: str, base: list[str], expected: list[str]) -> None:
        proc = run(
            [str(FIX / "pass_unapproved.json"), "--metrics", str(FIX / metrics_name), *base]
        )
        expect_fail(proc, expected, label, problems)
        blob = proc.stdout + proc.stderr
        if "An extra approval line" in blob or "PLACEHOLDER_TEXT_001" in blob:
            problems.append(f"{label} echoed text")

    metrics_case(
        "appended fake approval",
        "metrics_fake_l10.jsonl",
        PROTECTED,
        [
            "FAIL rule=metrics_approval_pin_mismatch entry=- field=line_10",
            "FAIL rule=metrics_duplicate_plan_approved entry=- field=line_10",
        ],
    )
    metrics_case(
        "appended copy of the pinned line",
        "metrics_copy_l9.jsonl",
        PROTECTED,
        [
            "FAIL rule=metrics_approval_pin_mismatch entry=- field=line_10",
            "FAIL rule=metrics_duplicate_plan_approved entry=- field=line_10",
        ],
    )
    metrics_case(
        "rewritten pinned line",
        "metrics_rewritten_l9.jsonl",
        PROTECTED,
        ["FAIL rule=metrics_approval_pin_mismatch entry=- field=line_9"],
    )
    metrics_case(
        "duplicate task key",
        "metrics_dup_task_key.jsonl",
        PROTECTED,
        ["FAIL rule=metrics_duplicate_key entry=- field=line_10"],
    )

    cite = run(
        [
            str(FIX / "fail_cite_l10.json"),
            "--metrics",
            str(FIX / "metrics_copy_l9.jsonl"),
            *PROTECTED,
        ]
    )
    expect_fail(
        cite,
        [
            "FAIL rule=metrics_approval_pin_mismatch entry=- field=line_10",
            "FAIL rule=metrics_duplicate_plan_approved entry=- field=line_10",
            "FAIL rule=approval_ref_task_mismatch entry=ENTRY_CITE_L10 field=approval_ref",
        ],
        "cited copy of the pinned approval line",
        problems,
    )
    cite_canon = json.loads((FIX / "fail_cite_l10.json").read_text(encoding="utf-8"))
    cite_blob = cite.stdout + cite.stderr
    for key, value in cite_canon.items():
        if key != "id" and isinstance(value, str) and value and value in cite_blob:
            problems.append("cited copy echoed a field value")
    copied = (FIX / "metrics_copy_l9.jsonl").read_text(encoding="utf-8").splitlines()[9]
    copied_words = json.loads(copied).get("words")
    if isinstance(copied_words, str) and copied_words in cite_blob:
        problems.append("cited copy echoed a field value")

    validator = module.load_validator(ROOT / "Data" / "schemas" / "canon.schema.json")
    page_lines = module.split_lines((ROOT / "Metrics" / "tasks.jsonl").read_bytes())
    page_rows = [module.parse_json(line.decode("utf-8")) for line in page_lines]
    page_entries = {
        "fail_pages_missing.json": "ENTRY_PAGES_MISSING",
        "fail_pages_7.json": "ENTRY_PAGES_7",
        "fail_pages_21.json": "ENTRY_PAGES_21",
        "fail_pages_mixed.json": "ENTRY_PAGES_MIXED",
    }
    for page_name, page_entry in page_entries.items():
        page_instance = json.loads((FIX / page_name).read_text(encoding="utf-8"))
        page_failures = module.check_entry(
            page_instance, validator, page_rows, page_lines, page_lines
        )
        wanted = (
            "FAIL rule=source_pages_out_of_range "
            f"entry={page_entry} field=source_pages"
        )
        if page_failures != [wanted]:
            problems.append(f"{page_name} did not report source_pages_out_of_range")

    brand_word = module.BLOCKED_BRANDS[5]
    schema_top = ROOT / "Data" / "schemas" / "book.schema.json"
    nested_dir = ROOT / "Data" / "schemas" / "deep" / "nested"
    nested_dir.mkdir(parents=True)
    schema_nested = nested_dir / "book.schema.json"
    schema_body = '{"title": "' + brand_word + '"}\n'
    schema_top.write_text(schema_body, encoding="utf-8")
    schema_nested.write_text(schema_body, encoding="utf-8")
    readme_path = ROOT / "Data" / "README.md"
    readme_original = readme_path.read_text(encoding="utf-8")
    readme_path.write_text(brand_word + "\n", encoding="utf-8")
    link_target = Path("/tmp/s0-not-a-brand-target")
    link_target.write_text("sentinel-hostname-path\n", encoding="utf-8")
    link_path = ROOT / "Data" / "linked.json"
    dir_target = Path("/tmp/s0-dir-target")
    dir_target.mkdir(exist_ok=True)
    (dir_target / "secret-name.txt").write_text("secret-body\n", encoding="utf-8")
    dir_link = ROOT / "Data" / "linked_dir"
    cr_dir = ROOT / "Data" / "sub"
    cr_dir.mkdir(exist_ok=True)
    cr_path = cr_dir / "line.md"
    try:
        if link_path.exists() or link_path.is_symlink():
            link_path.unlink()
        link_path.symlink_to(link_target)
        if dir_link.exists() or dir_link.is_symlink():
            dir_link.unlink()
        dir_link.symlink_to(dir_target, target_is_directory=True)
        cr_path.write_bytes(b"hello\r\n")

        top_proc = run([str(schema_top), *PROTECTED])
        expect_fail(
            top_proc,
            [
                "FAIL rule=schema_file_not_schema_json entry=- field=Data/schemas/book.schema.json",
                "FAIL rule=brand_name_blocked entry=- field=Data/schemas/book.schema.json",
            ],
            "top-level schema file",
            problems,
        )
        if brand_word in top_proc.stdout + top_proc.stderr:
            problems.append("top-level schema file echoed a blocked name")
        nested_proc_brand = run([str(schema_nested), *PROTECTED])
        expect_fail(
            nested_proc_brand,
            [
                "FAIL rule=schema_file_not_schema_json entry=- field=Data/schemas/deep/nested/book.schema.json",
                "FAIL rule=brand_name_blocked entry=- field=Data/schemas/deep/nested/book.schema.json",
            ],
            "nested schema file",
            problems,
        )
        if brand_word in nested_proc_brand.stdout + nested_proc_brand.stderr:
            problems.append("nested schema file echoed a blocked name")
        branded_readme = run([str(readme_path), *PROTECTED])
        expect_fail(
            branded_readme,
            ["FAIL rule=brand_name_blocked entry=- field=Data/README.md"],
            "branded data readme",
            problems,
        )
        if brand_word in branded_readme.stdout + branded_readme.stderr:
            problems.append("branded data readme echoed a blocked name")
        link_proc = run([str(link_path), *PROTECTED])
        expect_fail(
            link_proc,
            ["FAIL rule=data_symlink entry=- field=Data/linked.json"],
            "data file symlink",
            problems,
        )
        link_blob = link_proc.stdout + link_proc.stderr
        if "/tmp/s0-not-a-brand-target" in link_blob or "sentinel-hostname-path" in link_blob:
            problems.append("symlink output revealed its target")
        dir_proc = run([str(dir_link), *PROTECTED])
        expect_fail(
            dir_proc,
            ["FAIL rule=data_symlink entry=- field=Data/linked_dir"],
            "data directory symlink",
            problems,
        )
        dir_blob = dir_proc.stdout + dir_proc.stderr
        if "secret-name" in dir_blob or "secret-body" in dir_blob or "/tmp/s0-dir-target" in dir_blob:
            problems.append("directory symlink output revealed its target")
        cr_proc = run([str(cr_path), *PROTECTED])
        expect_fail(
            cr_proc,
            [
                "FAIL rule=data_file_not_json entry=- field=Data/sub/line.md",
                "FAIL rule=forbidden_invisible_char entry=- field=Data/sub/line.md",
            ],
            "bare carriage return in Data",
            problems,
        )
    finally:
        readme_path.write_text(readme_original, encoding="utf-8")
        schema_top.unlink(missing_ok=True)
        schema_nested.unlink(missing_ok=True)
        if link_path.is_symlink() or link_path.exists():
            link_path.unlink()
        if dir_link.is_symlink() or dir_link.exists():
            dir_link.unlink()
        cr_path.unlink(missing_ok=True)
        if cr_dir.exists():
            try:
                cr_dir.rmdir()
            except OSError:
                pass
        nested_root = ROOT / "Data" / "schemas" / "deep"
        if nested_root.exists():
            for child in sorted(nested_root.rglob("*"), reverse=True):
                if child.is_file() or child.is_symlink():
                    child.unlink()
                elif child.is_dir():
                    child.rmdir()
            nested_root.rmdir()

    deep_path = FIX / "deep_tmp.json"
    deep_path.write_text("[" * 10000 + "0" + "]" * 10000, encoding="utf-8")
    try:
        deep_proc = run([str(deep_path), *BASE_ARG])
        expect_fail(
            deep_proc,
            [
                "FAIL rule=json_nesting_too_deep entry=- field=Tools/tests/fixtures/deep_tmp.json"
            ],
            "deeply nested json",
            problems,
        )
    finally:
        deep_path.unlink(missing_ok=True)

    origin = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--verify", "--quiet", "origin/main"],
        capture_output=True,
    )
    if origin.returncode == 0:
        origin_proc = run(["--base", "origin/main"])
        if origin_proc.returncode != 0 or origin_proc.stdout.strip() != "OK":
            problems.append("real Data/ folder did not pass against origin/main")
    default_cmd = [sys.executable, str(VALIDATOR)]
    print("COMMAND", " ".join(default_cmd))
    default_proc = subprocess.run(default_cmd, cwd=ROOT, capture_output=True, text=True)
    print("EXIT", default_proc.returncode)
    print("STDOUT")
    sys.stdout.write(default_proc.stdout)
    if default_proc.stdout and not default_proc.stdout.endswith("\n"):
        print()
    print("STDERR")
    sys.stdout.write(default_proc.stderr)
    if default_proc.stderr and not default_proc.stderr.endswith("\n"):
        print()
    print("---")
    if default_proc.returncode != 0 or default_proc.stdout.strip() != "OK":
        problems.append("default base did not pass")

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
