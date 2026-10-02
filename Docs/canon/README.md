# Canon

Canon documentation. All lore is authored by Will. Only approved canon content is public.

## Where canon text lives

Narrative text and canon fields live only in Data/ JSON. Engine Resources are generated from that JSON later. This task does not generate Resources and does not add gameplay code.

Each canon entry is one JSON object in a file under `Data/`. The file name must end in lowercase `.json`. Any other file fails `data_file_not_json`, except the exact path `Data/README.md`. The failure field is the repo-relative path, for example `field=Data/sub/README.md` or `field=Tools/tests/fixtures/not_json/entry.txt`. `json_invalid` and `data_unreadable` use that same path style.

Under the top folder `Data/schemas/`, a file is accepted only when its name ends in `.schema.json` and it parses as JSON. Any other file there fails `schema_file_not_schema_json`. Accepted schema files are not canon entries. A `schemas` folder nested under another folder is scanned as canon entries.

The entry fields are `id`, `canon_tag`, `text`, `source_pages`, and, when approval is required, `approval_ref`. `id` matches `^[A-Z0-9_]+$`. `source_pages`, when present, is a non-empty array of integers. The validator, not the schema, requires those integers to fall on pages 8 through 20 for non-placeholder text.

## Book text

On 2026-10-02 at 5:12 PM CT, Will decided that book text may be added word for word, scene by scene, as the game follows the story. There is no per-entry approval. Will approves each slice plan. Real brand names are swapped for generic ones. Character names stay.

Placeholder text matches `PLACEHOLDER_` plus uppercase letters, digits, and underscores. An entry whose `text` is a placeholder, whose `canon_tag` is `UNAPPROVED`, and which omits `approval_ref`, passes.

Non-placeholder `text` passes only when all three of these hold:

- `approval_ref` resolves under the rules below, and that line's `task_id` is exactly `VS-001-S0`. Citing `#L1`, or any other task's `plan_approved` line (including a near miss such as `VS-001-S0-1`), fails `approval_ref_task_mismatch`.
- `source_pages` is present and every page is an integer from 8 through 20 inclusive. A missing list, or a page of 7 or 21, fails `source_pages_out_of_range`.
- No blocked maker name or product model name appears in any string field of the entry. The check ignores capital letters. A multi-word name still matches when any whitespace or a newline splits the words, and a single name still matches when a newline breaks it. A plural s, or a possessive apostrophe-s, may follow the name. The match uses word boundaries, so an ordinary longer word that only contains those letters stays allowed. The bare word Live stays allowed. The failure is `brand_name_blocked` on the field that matched. The validator does not print the matched name or any field value.

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

The validator takes `--base` (default `origin/main`). That default requires `origin/main` to be fetched already. A shallow CI checkout needs a fetch of `origin/main` before the validator runs. A full commit SHA does not need that ref. The real-repo check for this gate uses `3086759cd3349ccbd6dedbc0866f194aae3c1edb`. A line of `Metrics/tasks.jsonl` at that base must be byte-identical at the same position in the file being checked. Appending new lines is allowed. Editing, reordering, or deleting an existing line fails `metrics_line_not_byte_identical`. Task 000-4 owns the full metrics append-only check and may take this guard over.
