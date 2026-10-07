---
name: atoll-compatible
description: Adapts the current repository so it can be deployed on the Atoll deployment platform (Dockerfile, health-check endpoint, .env.example, DB/worker conventions). Use when the user asks to "make this atoll compatible", "prepare this repo for atoll deployment", "onboard this app to atoll", or similar.
---

# Make this repository Atoll-compatible

Atoll is a self-hosted deployment platform. It has **no manifest file** (no
`atoll.yaml`, no `Procfile`, no buildpacks) and **no callback API the app must
implement**. Its entire compatibility contract boils down to four things:

1. A root `Dockerfile` that builds and runs a production-ready image with a
   plain `docker build .` — no build args, no build-time secrets, no
   `--target` flag. Whatever the **last stage** of the Dockerfile is, that's
   what gets built and run.
2. A root `.env.example` (or `example.env`) file listing every environment
   variable the app needs, one **uncommented** `KEY=value` per line. Atoll reads
   the key names (so it knows which variables an operator must supply) and also
   reads whatever you put after the `=` as that key's **default**: it pre-fills
   the operator's console with it, and for non-secret keys creates the variable
   automatically. Rules that follow from this:
   - **Never comment a variable out.** A line starting with `#` is ignored
     entirely, so the key is neither shown in the console nor created — and if
     the code reads it, **the deployment is blocked** as a missing variable.
   - **No inline `# ...` comments after a value.** Atoll does not strip them, so
     `KEY=value # note` makes the default the literal `value # note`. Put any
     explanation on its own `#` line *above* the key instead.
   - Give safe, non-secret keys a real default (e.g. `DB_HOST=db`); leave
     secrets blank (`SECRET_KEY=`) so an operator sets them by hand.

   If a key is expected but left without a value, **the deployment is blocked**
   before the image is even built.
3. Exactly one HTTP health-check endpoint that returns HTTP `200`. The port
   and path are **fixed by which deployment profile an Atoll operator picks
   for this app** — the repo cannot declare a custom port or path itself.
   The three profiles in use today:

   | Profile          | Container port | Health-check path |
   |------------------|-----------------|--------------------|
   | Generic           | `8000`          | `/metrics`                |
   | Static hosting    | `8000`          | `/`                       |

4. If the app needs a database or a background worker, it should read their
   connection info from a fixed set of env var names (below) — Atoll
   provisions sibling `db`/`redis` containers and pre-seeds these values, it
   does not let the app name them itself.

Explicitly **out of scope** — do not add these, they are not part of the
contract and Atoll will not use them:
- Any `atoll.yaml`/`atoll.json`/manifest file.
- A GitHub Actions workflow or any other CI pipeline (Atoll deploys via its
  own webhook-triggered pipeline, not via CI).
- Any webhook, callback, or "report deployment status" endpoint the app must
  expose — Atoll never calls back into the deployed app except the single
  health-check GET.
- Reading `PORT` from the environment to decide what to bind to — the port
  is fixed by the profile, not passed in at runtime as a `PORT` var (unless
  the app already does this for other reasons; don't add it solely for Atoll).

## Procedure

Work through these steps in order. Make the changes directly in this repo.

### 1. Detect the stack

Identify the language/framework and existing entrypoint: look for
`package.json`, `requirements.txt`/`pyproject.toml`, `go.mod`, `Gemfile`,
`composer.json`, an existing `Dockerfile`, and the app's web framework
(Django, Express, Flask, Rails, Spring, etc.) and its router/URL config.

### 2. Ask which profile applies

Before writing the Dockerfile and health check, ask the user (they'll need to
confirm this with whoever administers their Atoll instance, since it's an
operator-side setting):

- Pick the generic profile's port/path (`8000` / `/metrics`) as the safe
  default for an app with server-side logic; pick the static hosting profile
  (`8000` / `/`) instead if this repo only serves static files (no backend
  process, no `/metrics` route to add). Note that the operator may need to
  add a custom profile on their end if a different port is required.
- Does this app need a database? (assume PostgreSQL if yes — that's the only
  database Atoll provisions today)
- Does this app run a background worker process?
- Will this app need a custom domain?

Don't guess these — they change what you build in steps 3–7.

### 3. Root Dockerfile

- If a root `Dockerfile` already exists, check that its **final stage**
  produces a directly runnable production image (not a dev/test stage) and
  that `docker build .` would succeed with no required `--build-arg` or
  secrets. Fix it if it fails either check (e.g. reorder multi-stage builds
  so the production stage is last, remove reliance on build args for
  required config — config should come from env vars at runtime instead).
- If no Dockerfile exists, create a minimal production one appropriate to
  the detected stack: install dependencies, copy source, expose the port
  chosen in step 2, and run the production entrypoint (e.g. `gunicorn`,
  `node server.js`, a compiled binary, an nginx-served static build, etc.)
  — whatever is idiomatic for this stack.
- Make sure the app listens on `0.0.0.0` on the chosen container port, not
  `127.0.0.1`/`localhost`.
- For the static hosting profile: serve the built assets with a static web
  server (nginx, `caddy`, `busybox httpd`, etc.) configured to **listen
  internally on `8000`**, not its default port (e.g. nginx's default `80`) —
  the profile's fixed container port is `8000` regardless of what the server
  normally defaults to.

### 4. Health-check endpoint

Add (or verify) a route at the path chosen in step 2 that returns a plain
HTTP `200` with no required auth. Wire it into the app's actual router in a
way idiomatic to the framework (e.g. a Django URL pattern, an Express route,
a Rails route, a Spring `@GetMapping`). A trivial static `up 1` body is
sufficient — Atoll only checks the status code. But make it prometeus compatible.

For the static hosting profile, no custom route is needed: `/` already
returns `200` as long as an `index.html` exists at the site root, which the
health check just re-checks on every deploy. Only add anything here if the
build produces no file at `/` (e.g. a SPA whose router 404s on unknown paths
but happens to also break the root) — otherwise this step is a no-op.

### 5. `.env.example`

Scan the codebase for every place it reads configuration from the
environment (`os.environ`/`os.getenv` in Python, `process.env` in
Node/JS/TS, `System.getenv`/Spring `@Value` in Java, `ENV[...]` in Ruby,
`os.Getenv` in Go, etc.). Create or update a root `.env.example` (or
`example.env` if the repo already uses that name) so **every discovered key is
a live, uncommented line** — `KEY=<safe default>` for non-secret config that
has an obvious default, `KEY=` (blank) for secrets and anything with no safe
default. Follow the `.env.example` rules in the compatibility contract above:
no commented-out keys, no inline `# ...` comments. If the existing file has any
of these keys commented out (`# KEY=...`), uncomment them so Atoll registers
them. Preserve existing entries; add missing ones; don't remove entries you
can't confirm are unused.

### 6. Testing (Python projects only)

If the detected stack is Python, make sure **pytest** is the test runner used
to validate your changes:
- If a test suite already exists under a different runner (`unittest`,
  `nose`, etc.), don't rewrite it — pytest can discover and run
  `unittest`-style tests natively. Just make sure `pytest` is installed
  (added to `requirements-dev.txt`/`pyproject.toml`'s dev/test dependency
  group, whichever the repo already uses) and that running `pytest` from the
  repo root actually discovers and runs the existing tests.
- If no test suite exists yet, add a minimal smoke test (e.g.
  `tests/test_health.py`) that exercises the health-check route added in
  step 4, using `pytest`.
- Run `pytest` and confirm it passes before considering the adaptation
  complete. This is a sanity check on the changes you just made (Dockerfile,
  health-check route), not something Atoll itself requires — Atoll's
  pipeline does not run the app's test suite.

### 7. Database and worker conventions (only if applicable)

- **If a database was requested in step 2**: make sure the app's DB config
  resolves connection info from `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`,
  `DB_PASSWORD` (default `DB_HOST=db`, `DB_PORT=5432` once deployed). If the
  app currently uses differently-named variables (e.g. `DATABASE_URL`,
  `POSTGRES_HOST`), either add support for these names alongside the
  existing ones, or note the mapping on its own `#` comment line *above* the
  keys in `.env.example` (never by commenting the keys themselves out). Add all
  five keys as live, uncommented `KEY=` lines in `.env.example`.
- **If a worker was requested in step 2**: make sure the worker/queue config
  resolves `REDIS_HOST` and `REDIS_PORT` (default `REDIS_HOST=redis`,
  `REDIS_PORT=6379`) and add them to `.env.example`. Whenever an app has a
  background worker it must ship a **`run_worker.sh`** script that starts the
  worker — one place, version-controlled, no start command duplicated across
  compose files or memorised by an operator. Put it wherever the repo keeps
  its other docker scripts (e.g. next to an existing `docker/entrypoint.sh`,
  otherwise the repo root), make it executable (`chmod +x` in the Dockerfile
  too so it stays executable in the image), and have it exec the stack's
  worker command, e.g.:

  ```sh
  #!/bin/sh
  set -e

  exec python manage.py run_huey   # or: celery -A app worker, node worker.js, bin/worker
  ```

  Point the worker service's `command:` in `docker-compose.yml` (and any
  prod compose file) at this script rather than inlining the raw command. The
  Atoll worker profile is likewise pointed at `run_worker.sh`.
- **If a custom domain was requested in step 2**: no repo change is needed;
  note in your final summary that the operator will need to set a
  `HOST_PORT` variable on their end and configure the domain in the Atoll
  console.

### 8. Register the Atoll MCP server (`.mcp.json`)

Make sure the repo root has a project-level `.mcp.json` that registers the
Atoll MCP server, so any AI agent opened in this repo can manage its Atoll
environments and deployments (it logs in to Atoll in the browser on first use -
never put a token or `headers` in this file):

```json
{
  "mcpServers": {
    "atoll": {
      "type": "http",
      "url": "https://atoll.eutima.ch/mcp"
    }
  }
}
```

- **No `.mcp.json` yet**: create it with exactly the content above.
- **`.mcp.json` already exists** (other MCP servers registered): **merge**, don't
  overwrite. Parse it, add the `atoll` entry under `mcpServers` and keep every
  other server and top-level key exactly as it is. If an `atoll` entry already
  exists, set its `type`/`url` to the values above and leave the rest of the
  file untouched. Keep the file valid JSON (no comments, no trailing commas) and
  preserve its existing indentation style.
- Don't add `.mcp.json` to `.gitignore` - it's meant to be committed so everyone
  working on the repo gets the server.

An agent only reads `.mcp.json` when a session starts: if you created or
changed it, tell the user to close this session and open a new one in the repo
to pick up the Atoll MCP server (and to approve it when their agent asks).

Once connected, the MCP tools are used through the companion skills that ship in
the same Atoll skills bundle - make sure they're present under `.claude/skills/`
(`atoll-environments/`, `atoll-variables/`, `atoll-deploy/`; if they're missing,
the user can fetch them with `atoll skills sync`):

- `atoll-environments` - create/list/configure environments, domains, volumes.
- `atoll-variables` - set the environment's variables and secrets.
- `atoll-deploy` - deploy an environment and handle failed deployments.

### 9. Final summary

Report back concisely:
- What files you created/changed (Dockerfile, health-check route,
  `.env.example`, `.mcp.json`, any config changes for DB/worker env var names,
  any test files added).
- For Python projects: confirmation that `pytest` runs and passes.
- The exact container port and health-check path the app now serves, and
  which profile that matches.
- If `.mcp.json` was created or changed: a reminder to close this AI agent
  session and start a new one so the Atoll MCP server is loaded.
- Next steps via the MCP skills: create the environment(s) (`atoll-environments`),
  set their variables (`atoll-variables`), then deploy (`atoll-deploy`).
- A short checklist of what's left for the user to coordinate with their
  Atoll operator, e.g.:
  - Confirm/select the matching deployment profile for this repo.
  - Set real values for every key in `.env.example` in the Atoll console.
  - Map the deployment branch(es) to environment(s).
  - If a worker is used: it starts via `run_worker.sh`; tell the operator to
    point the worker profile at that script.
  - If a custom domain is planned: request a `HOST_PORT` variable and
    domain configuration.
  - If deployment approval gates are desired: ask the operator to enable
    them and list approvers for the relevant environment.
