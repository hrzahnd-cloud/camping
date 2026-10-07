---
name: atoll-deploy
description: Deploys an Atoll environment through the Atoll MCP server and helps when a deployment fails - checking the environment is ready, making sure the user's changes are pushed, warning that Atoll deploys the latest commit on GitHub of the environment's branch, triggering the deployment and reporting its status. Use when the user asks to "deploy to Atoll", "deploy production/staging", "redeploy", "ship this", "check the last deployment", or to fix a failed Atoll deployment.
---

# Deploy with Atoll (MCP)

Atoll builds and deploys the **latest commit on GitHub** of an environment's git
branch. It never sees the local working copy: uncommitted or unpushed changes
are **not** deployed. A push to a mapped branch deploys automatically; the
`deploy_environment` tool of the `atoll` MCP server triggers a deployment on
demand (like the Deploy button in the Atoll console).

## Before you start

- The `atoll` MCP server must be connected and approved for this repository (see
  "Before you start: the MCP connection" in the `atoll-environments` skill). If the
  tools aren't available, say so and stop.

## Tools

| Tool | What it does |
|------|--------------|
| `list_environments()` | Environments with their branch, host and **latest deployment** (status, branch, commit, time). |
| `describe_environment(environment)` | Readiness detail: branch, host, domains, and **missing variable keys**. |
| `deploy_environment(environment)` | Deploys the latest GitHub commit of the environment's branch. Returns the deployment id, commit, status, a `notice` and a `deployment_url` in the Atoll console. |

## Procedure

1. **Pick the environment.** Call `list_environments`; if the user didn't say which
   one, ask. Only pass the environment's name - the branch is always the
   environment's own mapped branch.
2. **Check it's ready** with `describe_environment`:
   - exactly one mapped branch (with several, the tool refuses - the user deploys
     from the Atoll console instead);
   - a deployment host (else set one up with the `atoll-environments` skill);
   - no `missing_variable_keys` (else fix them with the `atoll-variables` skill -
     Atoll blocks a deployment with missing variables).
3. **Make sure the code is on GitHub.** Check `git status` and whether the
   environment's branch is ahead of its remote (`git fetch` then compare with
   `origin/<branch>`). If there are uncommitted or unpushed changes the user wants
   deployed, offer to commit and push them first - and only push with their OK.
4. **Tell the user and get confirmation.** Say plainly: *"This deploys the latest
   commit on GitHub of branch `<branch>` to `<environment>`. Local, uncommitted or
   unpushed changes are not included."* Name the commit if you know it. Wait for a
   clear yes. Take extra care with production. A manual deployment is **not** held
   for approval, even where approvals are enabled.
5. **Deploy**: call `deploy_environment(environment)`. A deployment already in
   progress for that environment is superseded by the new one.
6. **Report**: relay the `notice`, the short commit SHA and message, and the
   `deployment_url` where the user can follow the build and deploy. The deployment
   runs asynchronously; `list_environments` shows its latest status
   (`QUEUED` -> `BUILDING` -> `DEPLOYING` -> `SUCCESS`, or `FAILED`; it can also wait
   in `PENDING_SECURITY_APPROVAL` if the image scan found issues).

## When a deployment fails

1. `list_environments` / the `deployment_url` show the failed deployment; the
   Atoll console's deployment page has the build/deploy log (or the user can copy
   the "fix with AI" prompt from there, which includes the error output).
2. Typical causes and where to fix them:
   - Docker build errors, wrong port, health check not returning `200` at the
     profile's path (`/metrics` on `8000` for the generic profile) -> fix in the
     repo (see the `atoll-compatible` skill), commit and push.
   - Missing or wrong variables (app crashes on start, can't reach the database)
     -> `describe_environment` + the `atoll-variables` skill.
3. After a fix is pushed, a push to the mapped branch deploys by itself. Otherwise
   redeploy with `deploy_environment` - again after telling the user it deploys
   the latest GitHub commit of the branch.
