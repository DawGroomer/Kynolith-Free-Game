#!/usr/bin/env python3
"""Validate canon entries in Data/ JSON.

Reports the entry id, field name, and rule name. Does not print field values,
matched text, or symlink targets. An id that matches a blocked name is omitted.

Placeholder text stays allowed. It is still scanned for blocked names and for
forbidden characters. Non-placeholder text also needs the VS-001-S0 book-text
gate: the pinned approval line must already exist byte-for-byte on the base,
source pages 8-20, and no blocked name.

A minimal append-only guard compares Metrics/tasks.jsonl to a git base.
The default base is origin/main, or the pinned main SHA when that ref is absent.
Task 000-4 owns the full metrics append-only check and may take this over.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

# Will has not named a canon-approval event. Do not add names here.
APPROVAL_EVENTS = frozenset({"plan_approved"})

UNAPPROVED = "UNAPPROVED"
APPROVER_NAME = "Will Harris"
# Book-text entries may cite only this task's pinned plan_approved line.
BOOK_TEXT_TASK_ID = "VS-001-S0"
BOOK_PAGE_MIN = 8
BOOK_PAGE_MAX = 20
BOOK_APPROVAL_LINE = 9
# SHA-256 of Metrics/tasks.jsonl line 9, including its trailing newline.
BOOK_APPROVAL_SHA256 = (
    "d89102d4ab42dce11f2744d78627b8ffa91ca6fd2e14b1e2da2439b3cb682b02"
)
# main at the PR #4 merge. Used when origin/main cannot be resolved.
PINNED_MAIN_SHA = "3086759cd3349ccbd6dedbc0866f194aae3c1edb"
REF_RE = re.compile(r"^Metrics/tasks\.jsonl#L(0|[1-9][0-9]*)$")
ID_RE = re.compile(r"^[A-Z0-9_]+$")
ID_MAX = 64
# Placeholder text stays allowed, including UNAPPROVED with no approval_ref.
TEXT_RE = re.compile(r"^PLACEHOLDER_[A-Z0-9_]+$")
PLACEHOLDER_MAX = 200
ALLOWED_SCHEMA = "Data/schemas/canon.schema.json"
DATA_README = "Data/README.md"

# pp.8-20 maker and model strings supplied for S0-1. The bare word Live is
# not listed. Matching uses a letters-only projection with word boundaries.
# A plural s or es, or a possessive apostrophe-s, may follow the whole name.
BLOCKED_BRANDS = (
    "Ableton Live",
    "Dark Magic",
    "Ableton",
    "Audeze",
    "Maxwell",
    "Nike",
    "Cortez",
)

# Explicit Cyrillic and Greek look-alikes. No confusables package.
_CONFUSABLES = {
    "\u0430": "a",
    "\u0432": "b",
    "\u0441": "c",
    "\u0501": "d",
    "\u0435": "e",
    "\u0433": "r",
    "\u04bb": "h",
    "\u0456": "i",
    "\u0457": "i",
    "\u0458": "j",
    "\u043a": "k",
    "\u04cf": "l",
    "\u043c": "m",
    "\u043f": "n",
    "\u043e": "o",
    "\u0440": "p",
    "\u0455": "s",
    "\u0442": "t",
    "\u0443": "y",
    "\u0445": "x",
    "\u051b": "q",
    "\u051d": "w",
    "\u0475": "v",
    "\u0461": "w",
    "\u03b1": "a",
    "\u03b2": "b",
    "\u03b5": "e",
    "\u03b7": "n",
    "\u03b9": "i",
    "\u03ba": "k",
    "\u03bc": "m",
    "\u03bd": "v",
    "\u03bf": "o",
    "\u03c1": "p",
    "\u03c4": "t",
    "\u03c5": "u",
    "\u03c7": "x",
    "\u03c9": "w",
    "\u03b6": "z",
    "\u03b3": "y",
}

RULE_TEXT_NOT_PLACEHOLDER = "text_not_placeholder"
RULE_CANON_TAG_MISSING = "canon_tag_missing"
RULE_CANON_TAG_EMPTY = "canon_tag_empty"
RULE_APPROVAL_REF_REQUIRED = "approval_ref_required"
RULE_APPROVAL_REF_MALFORMED = "approval_ref_malformed"
RULE_APPROVAL_REF_LINE_OUT_OF_RANGE = "approval_ref_line_out_of_range"
RULE_APPROVAL_REF_EVENT_NOT_APPROVAL = "approval_ref_event_not_approval"
RULE_APPROVAL_REF_APPROVER_MISMATCH = "approval_ref_approver_mismatch"
RULE_APPROVAL_REF_WORDS_EMPTY = "approval_ref_words_empty"
RULE_APPROVAL_REF_TASK_MISMATCH = "approval_ref_task_mismatch"
RULE_APPROVAL_REF_NOT_AT_BASE = "approval_ref_not_at_base"
RULE_SOURCE_PAGES_OUT_OF_RANGE = "source_pages_out_of_range"
RULE_BRAND_NAME_BLOCKED = "brand_name_blocked"
RULE_FORBIDDEN_INVISIBLE = "forbidden_invisible_char"
RULE_PLACEHOLDER_TOO_LONG = "placeholder_too_long"
RULE_SCHEMA_FILE_NOT_SCHEMA_JSON = "schema_file_not_schema_json"
RULE_METRICS_LINE_NOT_BYTE_IDENTICAL = "metrics_line_not_byte_identical"
RULE_METRICS_BASE_UNREADABLE = "metrics_base_unreadable"
RULE_METRICS_UNREADABLE = "metrics_unreadable"
RULE_METRICS_APPROVAL_PIN_MISMATCH = "metrics_approval_pin_mismatch"
RULE_METRICS_DUPLICATE_PLAN_APPROVED = "metrics_duplicate_plan_approved"
RULE_METRICS_DUPLICATE_KEY = "metrics_duplicate_key"
RULE_SCHEMA_INVALID = "schema_invalid"
RULE_JSON_INVALID = "json_invalid"
RULE_JSON_DUPLICATE_KEY = "json_duplicate_key"
RULE_JSON_NESTING_TOO_DEEP = "json_nesting_too_deep"
RULE_METRICS_JSON_INVALID = "metrics_json_invalid"
RULE_DATA_UNREADABLE = "data_unreadable"
RULE_DATA_FILE_NOT_JSON = "data_file_not_json"
RULE_DATA_SYMLINK = "data_symlink"


class DuplicateKeyError(Exception):
    def __init__(self, key: str) -> None:
        self.key = key


def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    obj: dict[str, object] = {}
    for key, value in pairs:
        if key in obj:
            raise DuplicateKeyError(str(key))
        obj[key] = value
    return obj


def parse_json(text: str) -> object:
    return json.loads(text, object_pairs_hook=reject_duplicate_keys)


def fold_text(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text).casefold()
    folded = unicodedata.normalize("NFD", folded)
    out: list[str] = []
    for char in folded:
        if unicodedata.category(char) == "Mn":
            continue
        out.append(_CONFUSABLES.get(char, char))
    return "".join(out)


def _collapse(chars: list[str]) -> str:
    return re.sub(r" +", " ", "".join(chars)).strip()


def project_join(folded: str) -> str:
    """Drop hyphens, dots, digits, and newlines so split letters join."""
    chars: list[str] = []
    for char in folded:
        if char == "_":
            chars.append(" ")
        elif char in "\n\r":
            continue
        elif char.isalpha():
            chars.append(char)
        elif char.isspace():
            chars.append(" ")
    return _collapse(chars)


def project_separate(folded: str) -> str:
    """Treat every non-letter as a word boundary."""
    chars: list[str] = []
    for char in folded:
        if char.isalpha():
            chars.append(char)
        else:
            chars.append(" ")
    return _collapse(chars)


def _brand_pattern(phrase: str) -> re.Pattern[str]:
    folded = project_join(fold_text(phrase))
    body = " ".join(re.escape(word) for word in folded.split(" "))
    return re.compile(rf"(?<![a-z]){body}(?:es|s)?(?![a-z])")


BRAND_PATTERNS = tuple(_brand_pattern(phrase) for phrase in BLOCKED_BRANDS)


def repo_root() -> Path:
    start = Path.cwd()
    for candidate in [start, *start.parents]:
        if (candidate / ".git").exists():
            return candidate
    return start


def repo_relative(path: Path, repo: Path) -> str:
    """Repo-relative path. Does not resolve symlinks."""
    try:
        return path.absolute().relative_to(repo.absolute()).as_posix()
    except (OSError, ValueError):
        return path.as_posix()


def report(rule: str, entry: str, field: str) -> str:
    return f"FAIL rule={rule} entry={entry} field={field}"


def has_forbidden_invisible(value: str) -> bool:
    def flagged(text: str) -> bool:
        for char in text:
            if unicodedata.category(char) == "Cf" or char in "\u2028\u2029\r":
                return True
        return False

    if flagged(value):
        return True
    normalized = unicodedata.normalize("NFKC", value)
    return normalized != value and flagged(normalized)


def has_blocked_brand(value: str) -> bool:
    folded = fold_text(value)
    views = (project_join(folded), project_separate(folded))
    return any(pattern.search(view) for view in views for pattern in BRAND_PATTERNS)


def shown_entry(instance: object) -> str:
    if not isinstance(instance, dict):
        return "-"
    value = instance.get("id")
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        return "-"
    if len(value) > ID_MAX or has_blocked_brand(value):
        return "-"
    return value


def safe_field(field: str) -> str:
    if has_blocked_brand(field):
        return "$"
    return field


def string_fields(value: object, field: str = "") -> list[tuple[str, str]]:
    if isinstance(value, str):
        return [(field, value)] if field else []
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key)
            child = key_text if not field else f"{field}.{key_text}"
            if isinstance(key, str):
                found.append((child, key))
            found.extend(string_fields(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            child = f"{field}.{index}" if field else str(index)
            found.extend(string_fields(item, child))
    return found


def blocked_brand_field(instance: dict) -> str | None:
    for field, value in string_fields(instance):
        if has_blocked_brand(value):
            return safe_field(field)
    return None


def invisible_field(instance: dict) -> str | None:
    for field, value in string_fields(instance):
        if has_forbidden_invisible(value):
            return safe_field(field)
    return None


def split_lines(data: bytes) -> list[bytes]:
    if data == b"":
        return []
    parts = data.split(b"\n")
    if parts[-1] == b"":
        parts.pop()
    return parts


def line_digest(raw: bytes) -> str:
    return hashlib.sha256(raw + b"\n").hexdigest()


def load_validator(schema_path: Path) -> Draft202012Validator:
    schema = parse_json(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def default_base(root: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--verify", "--quiet", "origin/main"],
        capture_output=True,
    )
    if proc.returncode == 0:
        return "origin/main"
    return PINNED_MAIN_SHA


def read_base_lines(base: str, root: Path) -> tuple[list[str], list[bytes]]:
    proc = subprocess.run(
        ["git", "-C", str(root), "show", f"{base}:Metrics/tasks.jsonl"],
        capture_output=True,
    )
    if proc.returncode != 0:
        return [report(RULE_METRICS_BASE_UNREADABLE, "-", "Metrics/tasks.jsonl")], []
    return [], split_lines(proc.stdout)


def check_append_only(work_lines: list[bytes], base_lines: list[bytes]) -> list[str]:
    failures = []
    for index, base_line in enumerate(base_lines, start=1):
        missing = index - 1 >= len(work_lines)
        if missing or work_lines[index - 1] != base_line:
            failures.append(
                report(RULE_METRICS_LINE_NOT_BYTE_IDENTICAL, "-", f"line_{index}")
            )
    return failures


def load_metrics(metrics_path: Path) -> tuple[list[bytes], list[object], list[str]]:
    raw_lines = split_lines(metrics_path.read_bytes())
    parsed: list[object] = []
    failures: list[str] = []
    for index, raw in enumerate(raw_lines, start=1):
        try:
            parsed.append(parse_json(raw.decode("utf-8")))
        except DuplicateKeyError:
            parsed.append(None)
            failures.append(report(RULE_METRICS_DUPLICATE_KEY, "-", f"line_{index}"))
        except RecursionError:
            parsed.append(None)
            failures.append(report(RULE_JSON_NESTING_TOO_DEEP, "-", f"line_{index}"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            parsed.append(None)
    failures.extend(metrics_policy(parsed, raw_lines))
    return raw_lines, parsed, failures


def metrics_policy(rows: list[object], raw_lines: list[bytes]) -> list[str]:
    failures: list[str] = []
    seen: dict[str, list[int]] = {}
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict) or row.get("event") != "plan_approved":
            continue
        task = row.get("task_id")
        if not isinstance(task, str):
            continue
        seen.setdefault(task, []).append(index)
        if task != BOOK_TEXT_TASK_ID:
            continue
        digest = line_digest(raw_lines[index - 1])
        if index != BOOK_APPROVAL_LINE or digest != BOOK_APPROVAL_SHA256:
            failures.append(
                report(RULE_METRICS_APPROVAL_PIN_MISMATCH, "-", f"line_{index}")
            )
    for indexes in seen.values():
        if len(indexes) > 1:
            failures.append(
                report(
                    RULE_METRICS_DUPLICATE_PLAN_APPROVED,
                    "-",
                    f"line_{indexes[1]}",
                )
            )
    return failures


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


def book_approval_rule(
    instance: dict,
    metrics: list[object],
    work_lines: list[bytes],
    base_lines: list[bytes],
) -> str | None:
    ref = instance.get("approval_ref")
    if not isinstance(ref, str):
        return RULE_APPROVAL_REF_TASK_MISMATCH
    match = REF_RE.fullmatch(ref)
    if match is None:
        return RULE_APPROVAL_REF_TASK_MISMATCH
    line_no = int(match.group(1))
    if line_no < 1 or line_no > len(metrics) or line_no - 1 >= len(work_lines):
        return RULE_APPROVAL_REF_TASK_MISMATCH
    row = metrics[line_no - 1]
    if not isinstance(row, dict) or row.get("task_id") != BOOK_TEXT_TASK_ID:
        return RULE_APPROVAL_REF_TASK_MISMATCH
    if line_no != BOOK_APPROVAL_LINE:
        return RULE_APPROVAL_REF_TASK_MISMATCH
    if line_digest(work_lines[line_no - 1]) != BOOK_APPROVAL_SHA256:
        return RULE_METRICS_APPROVAL_PIN_MISMATCH
    if line_no - 1 >= len(base_lines) or base_lines[line_no - 1] != work_lines[line_no - 1]:
        return RULE_APPROVAL_REF_NOT_AT_BASE
    return None


def pages_in_slice(instance: dict) -> bool:
    pages = instance.get("source_pages")
    if not isinstance(pages, list) or not pages:
        return False
    for page in pages:
        if isinstance(page, bool) or not isinstance(page, int):
            return False
        if page < BOOK_PAGE_MIN or page > BOOK_PAGE_MAX:
            return False
    return True


def schema_field(error: object) -> str:
    path = getattr(error, "absolute_path", ())
    parts = [str(part) for part in path]
    if parts:
        return safe_field(".".join(parts))
    return "$"


def check_tag_and_ref(
    instance: dict,
    entry: str,
    metrics: list[object],
) -> list[str]:
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


def check_entry(
    instance: object,
    validator: Draft202012Validator,
    metrics: list[object],
    work_lines: list[bytes],
    base_lines: list[bytes],
) -> list[str]:
    entry = shown_entry(instance)
    if not isinstance(instance, dict):
        return [report(RULE_SCHEMA_INVALID, entry, "$")]
    hidden = invisible_field(instance)
    if hidden is not None:
        return [report(RULE_FORBIDDEN_INVISIBLE, entry, hidden)]
    branded = blocked_brand_field(instance)
    if branded is not None:
        return [report(RULE_BRAND_NAME_BLOCKED, entry, branded)]
    schema_failures = [
        report(RULE_SCHEMA_INVALID, entry, schema_field(error))
        for error in validator.iter_errors(instance)
    ]
    if schema_failures:
        return schema_failures
    tag_failures = check_tag_and_ref(instance, entry, metrics)
    if tag_failures:
        return tag_failures
    text = instance.get("text")
    if isinstance(text, str) and TEXT_RE.fullmatch(text):
        if len(text) > PLACEHOLDER_MAX:
            return [report(RULE_PLACEHOLDER_TOO_LONG, entry, "text")]
        return []
    if not isinstance(text, str):
        return [report(RULE_TEXT_NOT_PLACEHOLDER, entry, "text")]
    approval = book_approval_rule(instance, metrics, work_lines, base_lines)
    if approval is not None:
        return [report(approval, entry, "approval_ref")]
    if not pages_in_slice(instance):
        return [report(RULE_SOURCE_PAGES_OUT_OF_RANGE, entry, "source_pages")]
    return []


def raw_text_failures(path: Path, relative: str) -> list[str]:
    shown = safe_field(relative)
    try:
        data = path.read_bytes()
    except OSError:
        return [report(RULE_DATA_UNREADABLE, "-", shown)]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return [report(RULE_DATA_UNREADABLE, "-", shown)]
    if has_forbidden_invisible(text):
        return [report(RULE_FORBIDDEN_INVISIBLE, "-", shown)]
    if has_blocked_brand(text):
        return [report(RULE_BRAND_NAME_BLOCKED, "-", shown)]
    return []


def under_data_schemas(relative: str) -> bool:
    return relative == "Data/schemas" or relative.startswith("Data/schemas/")


def consider_file(path: Path, repo: Path) -> tuple[list[Path], list[str]]:
    relative = repo_relative(path, repo)
    if under_data_schemas(relative) and relative != ALLOWED_SCHEMA:
        failures = [report(RULE_SCHEMA_FILE_NOT_SCHEMA_JSON, "-", safe_field(relative))]
        failures.extend(raw_text_failures(path, relative))
        return [], failures
    if relative in {ALLOWED_SCHEMA, DATA_README}:
        return [], raw_text_failures(path, relative)
    if not path.name.endswith(".json"):
        failures = [report(RULE_DATA_FILE_NOT_JSON, "-", safe_field(relative))]
        failures.extend(raw_text_failures(path, relative))
        return [], failures
    return [path], []


def walk_entries(path: Path, repo: Path) -> tuple[list[Path], list[str]]:
    if path.is_symlink():
        return [], [report(RULE_DATA_SYMLINK, "-", safe_field(repo_relative(path, repo)))]
    if not path.exists():
        return [], [report(RULE_DATA_UNREADABLE, "-", safe_field(repo_relative(path, repo)))]
    if path.is_file():
        return consider_file(path, repo)
    if not path.is_dir():
        return [], [report(RULE_DATA_UNREADABLE, "-", safe_field(repo_relative(path, repo)))]
    files: list[Path] = []
    failures: list[str] = []
    for child in sorted(path.iterdir(), key=lambda item: item.name):
        found, errors = walk_entries(child, repo)
        files.extend(found)
        failures.extend(errors)
    return files, failures


def check_file(
    path: Path,
    validator: Draft202012Validator,
    metrics: list[object],
    work_lines: list[bytes],
    base_lines: list[bytes],
    repo: Path,
) -> list[str]:
    shown = safe_field(repo_relative(path, repo))
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return [report(RULE_JSON_INVALID, "-", shown)]
    try:
        instance = parse_json(text)
    except DuplicateKeyError as exc:
        field = exc.key if exc.key and not has_blocked_brand(exc.key) else "$"
        return [report(RULE_JSON_DUPLICATE_KEY, "-", field)]
    except RecursionError:
        return [report(RULE_JSON_NESTING_TOO_DEEP, "-", shown)]
    except json.JSONDecodeError:
        return [report(RULE_JSON_INVALID, "-", shown)]
    try:
        return check_entry(instance, validator, metrics, work_lines, base_lines)
    except RecursionError:
        return [report(RULE_JSON_NESTING_TOO_DEEP, "-", shown)]


def collect_entries(paths: list[Path], root: Path) -> tuple[list[Path], list[str]]:
    targets = paths or [root / "Data"]
    files: list[Path] = []
    failures: list[str] = []
    for target in targets:
        found, errors = walk_entries(target, root)
        files.extend(found)
        failures.extend(errors)
    return files, failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate canon Data entries.")
    parser.add_argument("--schema", type=Path)
    parser.add_argument("--metrics", type=Path)
    parser.add_argument("--base", default=None)
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args(argv)

    root = repo_root()
    schema_path = args.schema or (root / "Data" / "schemas" / "canon.schema.json")
    metrics_path = args.metrics or (root / "Metrics" / "tasks.jsonl")
    base = args.base if args.base is not None else default_base(root)

    if not metrics_path.is_file():
        print(report(RULE_METRICS_UNREADABLE, "-", "Metrics/tasks.jsonl"))
        return 1

    failures, base_lines = read_base_lines(base, root)
    try:
        work_lines, metrics, metric_failures = load_metrics(metrics_path)
    except OSError:
        print(report(RULE_METRICS_UNREADABLE, "-", "Metrics/tasks.jsonl"))
        return 1
    if base_lines:
        failures.extend(check_append_only(work_lines, base_lines))
    failures.extend(metric_failures)
    try:
        validator = load_validator(schema_path)
    except RecursionError:
        print(report(RULE_JSON_NESTING_TOO_DEEP, "-", "$"))
        return 1
    except DuplicateKeyError:
        print(report(RULE_JSON_DUPLICATE_KEY, "-", "$"))
        return 1
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, SchemaError):
        print(report(RULE_SCHEMA_INVALID, "-", "$"))
        return 1

    files, entry_errors = collect_entries(args.paths, root)
    failures.extend(entry_errors)
    for path in files:
        failures.extend(
            check_file(path, validator, metrics, work_lines, base_lines, root)
        )

    if failures:
        for line in failures:
            print(line)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
