# Canon

Canon documentation. All lore is authored by Will. Only approved canon content is public.

## Where canon text lives

Narrative text and canon fields live only in Data/ JSON. Engine Resources are generated from that JSON later. This task does not generate Resources and does not add gameplay code.

Each canon entry is one JSON object in a file under `Data/`. The file name must end in lowercase `.json`. Any other file fails `data_file_not_json`, except the exact path `Data/README.md`, which is not a canon entry. Every file under `Data/`, including `Data/README.md` and the canon schema, is read as raw text and scanned for blocked names and forbidden characters. The failure field is the repo-relative path, for example `field=Data/sub/README.md` or `field=Tools/tests/fixtures/not_json/entry.txt`. `json_invalid` and `data_unreadable` use that same path style. The validator does not print an absolute path or a symlink target.

Under `Data/schemas/`, the only allowed file is `Data/schemas/canon.schema.json`. Any other file there, including a nested path and a name that ends in `.schema.json`, fails `schema_file_not_schema_json`. A symlink anywhere under `Data/` fails `data_symlink` and is not followed. A `schemas` folder that is not the top `Data/schemas/` folder is still scanned as canon entries.

The entry fields are `id`, `canon_tag`, `text`, `source_pages`, and, when approval is required, `approval_ref`. `id` matches `^[A-Z0-9_]+$` and is at most 64 characters. `canon_tag` is at most 32 characters and matches `^[A-Za-z0-9_]*$`. The docs require the exact uppercase value `UNAPPROVED` when `approval_ref` is omitted, and they do not enumerate other tags, so the pattern keeps that alphabet. `source_pages`, when present, is a non-empty array of integers. The validator, not the schema, requires those integers to fall on pages 8 through 20 for non-placeholder text. Duplicate JSON keys fail `json_duplicate_key`.

## Book text

On 2026-10-02 at 5:12 PM CT, Will decided that book text may be added word for word, scene by scene, as the game follows the story. There is no per-entry approval. Will approves each slice plan. Real brand names are swapped for generic ones. Character names stay.

Placeholder text matches `PLACEHOLDER_` plus uppercase letters, digits, and underscores, and is at most 200 characters. A longer placeholder fails `placeholder_too_long`. An entry whose `text` is a placeholder, whose `canon_tag` is `UNAPPROVED`, and which omits `approval_ref`, passes only when every string field is free of blocked names and forbidden characters.

Every entry is scanned, including placeholders. The scan covers `id`, `canon_tag`, `approval_ref`, `text`, and any other string. An `id` that continues a blocked name with an underscore fails `brand_name_blocked`, and the id is not printed.

Non-placeholder `text` passes only when all three of these hold:

- `approval_ref` resolves under the rules below, the line is the pinned `VS-001-S0` `plan_approved` line, and that line's bytes already exist at the same position on the base. A line that exists only in the working tree does not qualify. Citing `#L1`, another task's `plan_approved` line, or a near miss such as `VS-001-S0-1`, fails `approval_ref_task_mismatch`. A pinned line that is not on the base fails `approval_ref_not_at_base`.
- `source_pages` is present and every page is an integer from 8 through 20 inclusive. A missing list, or a page of 7 or 21, fails `source_pages_out_of_range`.
- No blocked maker name or product model name appears. The check folds case, compatibility forms, and a small explicit set of look-alike letters, and it compares a letters-only projection with word boundaries. An ordinary longer word that only contains those letters stays allowed. The bare word Live stays allowed. A plural `s` or `es`, or a possessive apostrophe-s, may follow the whole name. The failure is `brand_name_blocked` on the field that matched. The validator does not print the matched name or any field value. Characters in category Cf, U+2028, U+2029, and a bare carriage return fail `forbidden_invisible_char`.

Book-text entries keep `canon_tag` `UNAPPROVED` and include an `approval_ref`. The validator does not invent other tag values.

## Tags and approval

`UNAPPROVED` is the only tag allowed without approval. The match is exact. Any other `canon_tag` needs an `approval_ref` that resolves. An empty `canon_tag` fails. A missing `canon_tag` fails.

Other tag names are not listed. Will has not chosen them.

## How approval_ref resolves

`approval_ref` has the form `Metrics/tasks.jsonl#L<n>`. `<n>` is a 1-based line number in `Metrics/tasks.jsonl`.

A reference resolves only when all of these are true:

- `<n>` is between 1 and the last line of the file. Line 0 and any line past the end do not resolve.
- That line's `event` is an approval event. The only approval event in the validator today is `plan_approved`. Will has not named a separate canon-approval event.
- That line's `approver` is exactly `Will Harris`.
- That line's `words` is a non-empty string.

For non-placeholder text, the resolved line's `task_id` must also be exactly `VS-001-S0`.

The Challenger checks on every pull request that the metrics event matches Will's actual words.

`Tools/canon_validator.py` checks these rules on the local machine. It reports the entry id, the field name, and the rule name. It does not print field values. Task 000-5 is expected to call this validator later. This task does not add a workflow file.

## Metrics lines already in the log

The validator takes `--base`. When `--base` is omitted, the base is `origin/main`, or `3086759cd3349ccbd6dedbc0866f194aae3c1edb` when that ref cannot be resolved. A shallow CI checkout that wants `origin/main` needs a fetch first. A full commit SHA does not need that ref. A line of `Metrics/tasks.jsonl` at the base must be byte-identical at the same position in the file being checked. Appending new lines is allowed. Editing, reordering, or deleting an existing line fails `metrics_line_not_byte_identical`. Duplicate keys in a metrics line fail `metrics_duplicate_key`. More than one `plan_approved` line for the same `task_id` fails `metrics_duplicate_plan_approved`. The `VS-001-S0` approval is pinned to line 9 and the SHA-256 of that line; any other line claiming that approval fails `metrics_approval_pin_mismatch`. Task 000-4 owns the full metrics append-only check and may take this guard over.
