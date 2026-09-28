# Review checklist

Use this before sign-off. The approved plan is KG-FREE-000 v0.11. Will Harris approved it on Sep 27 2026, 5:49 PM CT: "Repo has been created and I approve the plan".

- [ ] No drift from the approved plan.
- [ ] Gates required by the approved plan were followed.
- [ ] Tests assert the rule that fired.
- [ ] No invented metrics or log lines.
- [ ] No lore or story text was written by an agent.
- [ ] Any change under `.github/` has Will Harris's written sign-off.
- [ ] Do not merge until the Challenger and the Debugger sign off and Will Harris gives written go-ahead.

## Branch protection

The plan's decision is that branch protection is not checked in CI. `GITHUB_TOKEN` lacks Administration read, and no admin token exists.

The Challenger verifies protection at setup and at each release:

- Pull requests are required.
- Approvals = 0.
- Required checks are set.
- `enforce_admins` is on.
- Force push is blocked.
- Deletion is blocked.
