#!/usr/bin/env python3
"""Validate canon entries in Data/ JSON.

Reports the entry id, field name, and rule name. Does not print field values.

A minimal append-only guard compares Metrics/tasks.jsonl to a git base.
Task 000-4 owns the full metrics append-only check and may take this over.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

# Will has not named a canon-approval event. Do not add names here.
APPROVAL_EVENTS = frozenset({"plan_approved"})

UNAPPROVED = "UNAPPROVED"
APPROVER_NAME = "Will Harris"
REF_RE = re.compile(r"^Metrics/tasks\.jsonl#L(0|[1-9][0-9]*)$")

RULE_CANON_TAG_MISSING = "canon_tag_missing"
RULE_CANON_TAG_EMPTY = "canon_tag_empty"
RULE_APPROVAL_REF_REQUIRED = "approval_ref_required"
RULE_APPROVAL_REF_MALFORMED = "approval_ref_malformed"
RULE_APPROVAL_REF_LINE_OUT_OF_RANGE = "approval_ref_line_out_of_range"
RULE_APPROVAL_REF_EVENT_NOT_APPROVAL = "approval_ref_event_not_approval"
RULE_APPROVAL_REF_APPROVER_MISMATCH = "approval_ref_approver_mismatch"
RULE_APPROVAL_REF_WORDS_EMPTY = "approval_ref_words_empty"
RULE_METRICS_LINE_NOT_BYTE_IDENTICAL = "metrics_line_not_byte_identical"
RULE_METRICS_BASE_UNREADABLE = "metrics_base_unreadable"
RULE_METRICS_UNREADABLE = "metrics_unreadable"
RULE_SCHEMA_INVALID = "schema_invalid"
RULE_JSON_INVALID = "json_invalid"
RULE_METRICS_JSON_INVALID = "metrics_json_invalid"
RULE_DATA_UNREADABLE = "data_unreadable"


def repo_root() -> Path:
    start = Path.cwd()
    for candidate in [start, *start.parents]:
        if (candidate / ".git").exists():
            return candidate
    return start


def report(rule: str, entry: str, field: str) -> str:
    return f"FAIL rule={rule} entry={entry} field={field}"


def entry_id(instance: object) -> str:
    if isinstance(instance, dict):
        value = instance.get("id")
        if isinstance(value, str) and value:
            return value
    return "-"


def split_lines(data: bytes) -> list[bytes]:
    if data == b"":
        return []
    parts = data.split(b"\n")
    if parts[-1] == b"":
        parts.pop()
    return parts


def load_validator(schema_path: Path) -> Draft202012Validator:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def check_append_only(metrics_path: Path, base: str, root: Path) -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(root), "show", f"{base}:Metrics/tasks.jsonl"],
        capture_output=True,
    )
    if proc.returncode != 0:
        return [report(RULE_METRICS_BASE_UNREADABLE, "-", "Metrics/tasks.jsonl")]
    base_lines = split_lines(proc.stdout)
    work_lines = split_lines(metrics_path.read_bytes())
    failures = []
    for index, base_line in enumerate(base_lines, start=1):
        missing = index - 1 >= len(work_lines)
        if missing or work_lines[index - 1] != base_line:
            failures.append(
                report(RULE_METRICS_LINE_NOT_BYTE_IDENTICAL, "-", f"line_{index}")
            )
    return failures


def load_metrics(metrics_path: Path) -> list[object]:
    parsed: list[object] = []
    for line in split_lines(metrics_path.read_bytes()):
        try:
            parsed.append(json.loads(line.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError):
            parsed.append(None)
    return parsed


def resolve_ref(ref: str, metrics: list[object]) -> str | None:
    match = REF_RE.fullmatch(ref)
    if match is None:
        return RULE_APPROVAL_REF_MALFORMED
    line_no = int(match.group(1))
    if line_no < 1 or line_no > len(metrics):
        return RULE_APPROVAL_REF_LINE_OUT_OF_RANGE
    row = metrics[line_no - 1]
    if not isinstance(row, dict):
        return RULE_METRICS_JSON_INVALID
    if row.get("event") not in APPROVAL_EVENTS:
        return RULE_APPROVAL_REF_EVENT_NOT_APPROVAL
    if row.get("approver") != APPROVER_NAME:
        return RULE_APPROVAL_REF_APPROVER_MISMATCH
    words = row.get("words")
    if not isinstance(words, str) or words == "":
        return RULE_APPROVAL_REF_WORDS_EMPTY
    return None


def schema_field(error: object) -> str:
    path = getattr(error, "absolute_path", ())
    parts = [str(part) for part in path]
    if parts:
        return ".".join(parts)
    return "$"


def check_entry(
    instance: object,
    validator: Draft202012Validator,
    metrics: list[object],
) -> list[str]:
    entry = entry_id(instance)
    if not isinstance(instance, dict):
        return [report(RULE_SCHEMA_INVALID, entry, "$")]
    schema_failures = [
        report(RULE_SCHEMA_INVALID, entry, schema_field(error))
        for error in validator.iter_errors(instance)
    ]
    if schema_failures:
        return schema_failures
    if "canon_tag" not in instance:
        return [report(RULE_CANON_TAG_MISSING, entry, "canon_tag")]
    tag = instance.get("canon_tag")
    if tag == "":
        return [report(RULE_CANON_TAG_EMPTY, entry, "canon_tag")]
    ref = instance.get("approval_ref")
    if tag != UNAPPROVED and ref is None:
        return [report(RULE_APPROVAL_REF_REQUIRED, entry, "approval_ref")]
    if ref is None:
        return []
    if not isinstance(ref, str):
        return [report(RULE_SCHEMA_INVALID, entry, "approval_ref")]
    rule = resolve_ref(ref, metrics)
    if rule is None:
        return []
    return [report(rule, entry, "approval_ref")]


def entry_files(path: Path) -> tuple[list[Path], list[str]]:
    if not path.exists():
        return [], [report(RULE_DATA_UNREADABLE, "-", "$")]
    if path.is_file():
        return [path], []
    files = []
    for candidate in sorted(path.rglob("*.json")):
        if not candidate.is_file():
            continue
        relative = candidate.relative_to(path)
        if "schemas" in relative.parts:
            continue
        files.append(candidate)
    return files, []


def check_file(
    path: Path,
    validator: Draft202012Validator,
    metrics: list[object],
) -> list[str]:
    try:
        instance = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return [report(RULE_JSON_INVALID, "-", "$")]
    return check_entry(instance, validator, metrics)


def collect_entries(paths: list[Path], root: Path) -> tuple[list[Path], list[str]]:
    targets = paths or [root / "Data"]
    files: list[Path] = []
    failures: list[str] = []
    for target in targets:
        found, errors = entry_files(target)
        files.extend(found)
        failures.extend(errors)
    return files, failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate canon Data entries.")
    parser.add_argument("--schema", type=Path)
    parser.add_argument("--metrics", type=Path)
    parser.add_argument("--base", default="origin/main")
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args(argv)

    root = repo_root()
    schema_path = args.schema or (root / "Data" / "schemas" / "canon.schema.json")
    metrics_path = args.metrics or (root / "Metrics" / "tasks.jsonl")

    if not metrics_path.is_file():
        print(report(RULE_METRICS_UNREADABLE, "-", "Metrics/tasks.jsonl"))
        return 1

    failures = check_append_only(metrics_path, args.base, root)
    try:
        validator = load_validator(schema_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, SchemaError):
        print(report(RULE_SCHEMA_INVALID, "-", "$"))
        return 1

    metrics = load_metrics(metrics_path)
    files, entry_errors = collect_entries(args.paths, root)
    failures.extend(entry_errors)
    for path in files:
        failures.extend(check_file(path, validator, metrics))

    if failures:
        for line in failures:
            print(line)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
