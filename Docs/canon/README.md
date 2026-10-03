# Canon

Canon documentation. All lore is authored by Will. Only approved canon content is public.

## Where canon text lives

Narrative text and canon fields live only in Data/ JSON. Engine Resources are generated from that JSON later. This task does not generate Resources and does not add gameplay code.

Each canon entry is one JSON object in a file under `Data/`. The file name must end in lowercase `.json`. Any other file fails `data_file_not_json`, except the exact path `Data/README.md`, which is not a canon entry. Every file under `Data/`, including `Data/README.md` and the canon schema, is read as raw text and scanned for blocked names and forbidden characters. The failure field is the repo-relative path, for example `field=Data/sub/README.md` or `field=Tools/tests/fixtures/not_json/entry.txt`. `json_invalid` and `data_unreadable` use that same path style. The validator does not print an absolute path or a symlink target.

Under `Data/schemas/`, the only allowed file is `Data/schemas/canon.schema.json`. Any other file there, including a nested path and a name that ends in `.schema.json`, fails `schema_file_not_schema_json`. A symlink anywhere under `Data/` fails `data_symlink` and is not followed. A `schemas` folder that is not the top `Data/schemas/` folder is still scanned as canon entries.

The entry fields are `id`, `canon_tag`, `text`, `source_pages`, and, when approval is required, `approval_ref`. `id` matches `^[A-Z0-9_]+$` and is at most 64 characters. `canon_tag` is at most 32 characters. The allowed values are exactly `CANON`, `GAME CANON`, and `UNAPPROVED`. The final tag vocabulary is still open. Any other value fails `canon_tag_not_allowed`. An empty tag fails `canon_tag_empty`. `source_pages`, when present, is a non-empty array of integers. The validator, not the schema, requires those integers to fall on pages 8 through 20 for non-placeholder text. Duplicate JSON keys fail `json_duplicate_key`.

## Book text

On 2026-10-02 at 5:12 PM CT, Will decided that book text may be added word for word, scene by scene, as the game follows the story. There is no per-entry approval. Will approves each slice plan. Real brand names are swapped for generic ones. Character names stay.

Placeholder text matches `PLACEHOLDER_` plus uppercase letters, digits, and underscores, and is at most 200 characters. A longer placeholder fails `placeholder_too_long`. An entry whose `text` is a placeholder, whose `canon_tag` is `UNAPPROVED`, and which omits `approval_ref`, passes only when every string field is free of blocked names and forbidden characters.

Every entry is scanned, including placeholders. The scan covers `id`, `canon_tag`, `approval_ref`, `text`, and any other string. An `id` that continues a blocked name with an underscore fails `brand_name_blocked`, and the id is not printed.

Non-placeholder `text` passes only when all four of these hold:

- `canon_tag` is exactly `UNAPPROVED`. `CANON` and `GAME CANON` stay allowlisted for placeholder entries. On book text they fail `book_text_must_be_unapproved`. That leaves the final tag value open.
- `approval_ref` resolves under the rules below, the line is the pinned `VS-001-S0` `plan_approved` line, and that line's bytes already exist at the same position on the base. A line that exists only in the working tree does not qualify. Citing `#L1`, another task's `plan_approved` line, or a near miss such as `VS-001-S0-1`, fails `approval_ref_task_mismatch`. A pinned line that is not on the base fails `approval_ref_not_at_base`.
- `source_pages` is present and every page is an integer from 8 through 20 inclusive. A missing list, or a page of 7 or 21, fails `source_pages_out_of_range`.
- No blocked maker name or product model name appears. The check folds a copy of the text and leaves the stored file byte-for-byte, including ellipsis, right single quotation mark, em dash, é, and ā. The copy gets a case-sensitive map of U+03F9 and U+03F2 (lunate sigma) to c before NFKC, then NFKC, then a case-sensitive map rewrites U+039D to n before casefold, then casefold, then category Mn is dropped, then a small in-repo table maps Latin, Cyrillic, Greek, and Coptic look-alike letters, including U+0274 to n and U+2CA5 to c. Between any two letters of a blocked name, any run of non-letters is allowed, including none. The boundaries on that folded copy are `[a-z]` only: `(?<![a-z])` before the name and `(?![a-z])` after it, so a digit, an underscore, or any character outside `[a-z]` is a separator. After the name, an optional `s`, `es`, or apostrophe-s may appear. An ordinary longer word that only contains those letters stays allowed. The bare word Live stays allowed. The failure is `brand_name_blocked` on the field that matched. The validator does not print the matched name or any field value. Characters in category Cf, U+2028, U+2029, a bare carriage return, and U+115F, U+1160, U+3164, U+FFA0, U+2800, and U+20DD fail `forbidden_invisible_char`. That check runs on the raw file text before JSON parsing, so a leading U+FEFF fails `forbidden_invisible_char`.

Book-text entries keep `canon_tag` `UNAPPROVED` and include an `approval_ref`. A placeholder may use any allowlisted tag, including `CANON` and `GAME CANON`.

## Tags and approval

`UNAPPROVED` is the only allowlisted tag that may omit approval. The match is exact. `CANON` and `GAME CANON` are both allowed, and each needs an `approval_ref` that resolves. An empty `canon_tag` fails. A missing `canon_tag` fails. A tag outside the allowlist fails `canon_tag_not_allowed`.

The final tag value is still open. The allowlist is exactly `CANON`, `GAME CANON`, and `UNAPPROVED`. No file under `Data/` uses a tag yet.

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

The validator takes `--base`. When `--base` is omitted, the base is `origin/main`, or `3086759cd3349ccbd6dedbc0866f194aae3c1edb` when that ref cannot be resolved. The base must be that commit or an ancestor of it. Any other resolved commit, including `HEAD` on a branch that has moved past main, fails `metrics_base_not_ancestor`. A name that does not resolve fails `metrics_base_unreadable`. A shallow CI checkout that wants `origin/main` needs a fetch first. A full commit SHA does not need that ref. A line of `Metrics/tasks.jsonl` at the base must be byte-identical at the same position in the file being checked. Appending new lines is allowed. Editing, reordering, or deleting an existing line fails `metrics_line_not_byte_identical`. Duplicate keys in a metrics line fail `metrics_duplicate_key`. More than one `plan_approved` line for the same `task_id` fails `metrics_duplicate_plan_approved`. The `VS-001-S0` approval is pinned to line 9 and the SHA-256 of that line; any other line claiming that approval, including a copy cited as a later line, fails `metrics_approval_pin_mismatch`. Task 000-4 owns the full metrics append-only check and may take this guard over.
