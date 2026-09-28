# Review checklist

Use this before sign-off against the current approved plan.

- [ ] No drift from the approved plan.
- [ ] Gates required by the approved plan were followed.
- [ ] Tests assert the rule that fired.
- [ ] No invented metrics or log lines.
- [ ] No lore or story text was written by an agent.
- [ ] Merge rule, quoted from Will Harris at 8:06 PM CT on 2026-09-27: "The team can merge PRs inside an approved plan once the Challenger and Debugger sign off. Tell me after each merge." This covers `.github/` files. Both sign-offs must be on the same head. Will is told after each merge.
- [ ] New plans, canon, lore, and feature decisions still need Will's written approval.
- [ ] Any change under `.github/workflows/` also needs the Security & Governance Auditor's review before it merges. Will Harris wrote in the Dev Team at 3:19 AM CT on 2026-09-28: "yes that is the auditors pupose to catch the hallucinations and straying."

## Branch protection

The plan's decision is that branch protection is not checked in CI. `GITHUB_TOKEN` lacks Administration read, and no admin token exists.

The full protection settings can't be read by any agent (`GET /branches/main/protection` returns 403). `GET /branches/main` does work, and line 4 of `Metrics/tasks.jsonl` records what it returned.

The evidence for these protection settings is Will Harris's screenshot of the saved rule for `main`, taken at setup and at each release. The Challenger compares that screenshot with this list:

- Pull requests are required.
- Approvals = 0.
- Required checks are set: not applicable until 000-5. CI arrives in 000-5, and required checks get turned on after that.
- `enforce_admins` is on.
- Force push is blocked.
- Deletion is blocked.
