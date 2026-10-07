---
name: atoll-environments
description: Creates, inspects and configures this repository's Atoll deployment environments through the Atoll MCP server - listing environments, creating one (branch, deployment host, custom domains, deployment approval), adapting an existing one, and managing the repository's bind-mount volumes. Use when the user asks to "create a production/staging environment on Atoll", "map a branch", "add a domain", "set up approvals", "list my Atoll environments", "what's deployed where", or "add a volume/persistent storage" for an Atoll-deployed app.
---

# Manage Atoll environments (MCP)

Atoll deploys a repository into one or more **environments** (e.g. `production`,
`staging`). Each environment has: the git **branch** that deploys to it, a
**deployment host** (target), optional **custom domains**, and optional
**deployment approval**. You manage them with the tools of the `atoll` MCP
server.

## Before you start: the MCP connection

- The repo's `.mcp.json` registers the server (`"atoll"`, type `http`,
  `https://atoll.eutima.ch/mcp`). If it's missing, the `atoll-compatible` skill
  adds it. After creating/changing `.mcp.json`, the user must **start a new
  agent session** - `.mcp.json` is only read when a session starts.
- There is no token to paste. On first use the agent opens the browser: the user
  logs in to Atoll and **approves the agent for one repository**. Every tool then
  acts on exactly that repository.
- If a tool says the user no longer has access, or the agent is connected to the
  wrong repository, have the user clear the server's authentication (in Claude
  Code: `/mcp` -> `atoll` -> clear authentication) and log in again, picking the
  right repository.
- If the `atoll` tools aren't available at all, say so and stop - don't try to
  reach Atoll another way.

## Tools

| Tool | What it does |
|------|--------------|
| `list_environments()` | All environments of the repository: name, branch(es), host, domains + status, approval, latest deployment. Start here - it gives the names the other tools take. |
| `describe_environment(environment)` | Full read-only detail of one environment, including which variable keys are set or still missing (never values). |
| `list_hosts()` | Deployment hosts available to the user's customer. `auto_select` is set when there is exactly one. |
| `create_environment(name, branch?, host?, domain?/domains?, require_approval?, approvers?)` | Creates the environment (idempotent: an existing one with that name is reconciled), seeds the playbook's preset variables, and applies the given settings. |
| `setup_environment(environment, branch?, host?, domain?/domains?, require_approval?, approvers?)` | Changes an existing environment. Only the arguments you pass change. |
| `list_volumes()` / `create_volume(name, container_path)` / `delete_volume(name)` | Bind-mount volumes of the repository (host `./data/<name>` -> `container_path`), shared by every environment. |

## Creating an environment

The repository must be Atoll-compatible first (Dockerfile, health check,
`.env.example` - see the `atoll-compatible` skill), committed and **pushed**.

Then **ask the user for every value - never invent them**, in this order:

1. **Name** - e.g. `production` or `staging`.
2. **Branch** that deploys to it - e.g. `main`. Suggest the repo's default branch.
3. **Deployment host** - call `list_hosts` first. If `auto_select` is set, use that
   host without asking; otherwise show the hosts and let the user pick by name.
4. **Custom domains** - optional, one or several (up to 10).
5. **Approval** - optional: should deployments need approval? If the user has no
   preference, leave `require_approval` out: it then defaults to **on** only for
   environments named `prod`/`production`. Approvers default to the customer's
   members; pass `approvers` (emails) to restrict them. Approval gates deployments
   triggered by a git push only - a manual deploy is never held.

Call `create_environment` with those values, then:

- If domains were given, relay each domain's `cname_instructions` **verbatim** so
  the user can create the DNS CNAME record. A domain stays `pending_verification`
  until DNS resolves; `list_environments` / `describe_environment` show the status.
- Relay any `warnings` (e.g. the repository has no playbook yet).
- Point out `missing_variable_keys` and continue with the `atoll-variables` skill -
  a deployment is blocked while required variables are missing.

## Changing an environment

Use `setup_environment` with the environment's name and only the settings that
change. Adding a domain that's already attached is harmless. A host can only be
bound once; to move an environment to another host, the user does that in the
Atoll console.

## Volumes

For data that must survive redeploys (uploads, SQLite files, ...), create a volume:
`name` is the host directory under `./data/` (letters, digits, `_`, `-`) and
`container_path` the absolute path inside the container (e.g. `/app/media`). Make
sure the app actually writes there. Volumes apply to every environment. Ask before
`delete_volume` - the user may lose the data stored in it.

## Reporting back

Summarize per environment: name, branch, host, domains (with the DNS records still
to create), approval setting, and what's still needed (missing variables, a first
deployment - see `atoll-deploy`).
