# Canon

Canon documentation. All lore is authored by Will. Only approved canon content is public.

## Where canon text lives

Narrative text and canon fields live only in Data/ JSON. Engine Resources are generated from that JSON later. This task does not generate Resources and does not add gameplay code.

Each canon entry is one JSON object in a `.json` file under `Data/`, outside `Data/schemas/`. The fields are `id`, `canon_tag`, `text`, and, when approval is required, `approval_ref`. The `text` field holds the narrative text. Real canon entries are written by Will.

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

The Challenger checks on every pull request that the metrics event matches Will's actual words.

`Tools/canon_validator.py` checks these rules on the local machine. It reports the entry id, the field name, and the rule name. It does not print field values. Task 000-5 is expected to call this validator later. This task does not add a workflow file.

## Metrics lines already in the log

The validator takes `--base` (default `origin/main`). A line of `Metrics/tasks.jsonl` at that base must be byte-identical at the same position in the file being checked. Appending new lines is allowed. Editing, reordering, or deleting an existing line fails. Task 000-4 owns the full metrics append-only check and may take this guard over.
