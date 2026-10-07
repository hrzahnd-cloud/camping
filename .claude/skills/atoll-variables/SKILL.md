---
name: atoll-variables
description: Sets the environment variables of an Atoll deployment environment through the Atoll MCP server - applying Atoll's recommended database/Redis/allowed-hosts values, determining DJANGO_SETTINGS_MODULE from the code, generating secrets only with the user's consent, and checking which required variables are still missing. Use when the user asks to "set the variables/env vars/secrets on Atoll", "configure production settings", when a deployment is blocked by missing variables, or right after creating an Atoll environment.
---

# Set Atoll environment variables (MCP)

Each Atoll environment has its own variables, stored encrypted. The keys an app
needs come from the repository's `.env.example` - every uncommented `KEY=` line is
expected, and **a deployment is blocked while an expected key has no value**. You
set them with the `atoll` MCP server's `set_environment_variables` tool.

## Before you start

- The `atoll` MCP server must be connected and approved for this repository (see
  "Before you start: the MCP connection" in the `atoll-environments` skill). If the
  tools aren't available, say so and stop.
- The environment must exist - `list_environments` shows the names. Create it
  first with the `atoll-environments` skill if needed.
- `.env.example` should be complete (see the `atoll-compatible` / `env-example-sync`
  skills). A key the code reads but `.env.example` doesn't list is never asked for.

## Tools

| Tool | What it does |
|------|--------------|
| `describe_environment(environment)` | Which variable keys are set and which expected keys are still missing. Values are never returned. |
| `set_environment_variables(environment, overrides?, generate?)` | Applies the recommended values, then generated secrets, then your `overrides` (in that order; later wins). Returns `keys_set`, `secrets_to_offer`, `missing_variable_keys`. |

## What the tool does for you

Every call to `set_environment_variables`:

- Seeds the playbook's preset variables - **only** if the environment has none yet,
  so an existing `DB_PASSWORD` is never rotated by accident.
- Applies the recommended values: `REDIS_HOST=redis`, `REDIS_PORT=6379`,
  `DB_PORT=5432`, `DB_NAME=db`; every database-host key (`DB_HOST`,
  `POSTGRES_HOST`, `PGHOST`, ...) is set to `db` (the database container's name);
  `HELIX_BASE_URL`, when the code uses it, is set to `helix.eutima.ch`.
- Adds `localhost` to every allowed-hosts key (`ALLOWED_HOSTS`,
  `DJANGO_ALLOWED_HOSTS`, ...) without dropping the hosts already there - the
  health check calls the container on `localhost`.

Don't pass these recommended keys again unless the user explicitly wants a
different value.

## Procedure

1. Call `describe_environment` to see what's set and what's missing.
2. Work out the values you *can* determine from the code - never guess:
   - **`DJANGO_SETTINGS_MODULE`** (Django projects): find the production settings
     module from `manage.py`, `wsgi.py`/`asgi.py` and the settings package (e.g.
     `config.settings.production`) and pass it via `overrides`. The tool never
     sets it for you.
   - The environment's public host name(s) for `ALLOWED_HOSTS`/`CSRF_TRUSTED_ORIGINS`
     etc.: use its custom domains (see `list_environments`), and ask the user when
     unsure.
3. Call `set_environment_variables(environment, overrides={...})`.
4. **Secrets** (`DB_PASSWORD`, `SECRET_KEY`, encryption/signing keys, ...): the
   result's `secrets_to_offer` lists them. **Do not invent secret values.** Ask
   the user whether to generate strong random values; only on their OK call the
   tool again with those keys in `generate`. Values the user provides themselves
   (API keys of third-party services, ...) go in `overrides`. `generate` only
   accepts secret/encryption keys - for anything else use `overrides`.
5. Check `missing_variable_keys` in the result. For each remaining key ask the user
   for its value (or where to find it), or tell them to set it in the Atoll
   console's Variables tab.

Never echo secret values back in your summary, and never write them into files in
the repository.

## Reporting back

List which keys were set (names only), which were generated, and which are still
missing and what the user needs to do about them. Once nothing is missing, the
environment can be deployed (see `atoll-deploy`).
