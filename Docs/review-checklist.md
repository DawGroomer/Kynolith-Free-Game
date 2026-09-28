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

Branch protection can't be read by any agent. `GET /branches/main/protection` returns HTTP 403.

The evidence for these protection settings is Will Harris's screenshot of the saved rule for `main`, taken at setup and at each release. The Challenger compares that screenshot with this list:

- Pull requests are required.
- Approvals = 0.
- Required checks are set: not applicable until 000-5. CI arrives in 000-5, and required checks get turned on after that.
- `enforce_admins` is on.
- Force push is blocked.
- Deletion is blocked.
