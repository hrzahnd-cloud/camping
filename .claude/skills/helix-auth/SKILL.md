---
name: helix-auth
description: How to implement "Login with Helix" (OAuth2 authorization_code + PKCE, plus optional OpenID Connect) in an external application — getting a client_id/secret from a Helix workspace admin, driving the authorize/consent/token exchange, refreshing tokens, verifying id_tokens, and calling the Helix REST API with the resulting access token. Also covers gate-only integrations that use Helix solely to authenticate a user and confirm workspace membership, while keeping authorization/roles/user records entirely inside the app's own system. Use when integrating a new application with Helix authentication/SSO, or when the user asks how to "log in with Helix," connect to Helix OAuth/OIDC, set up Helix as an identity provider, or gate access by workspace membership without inheriting Helix's own permissions.
---

# Login with Helix (OAuth2 / OIDC)

Helix can act as an OAuth2 **authorization server** — and, optionally, a full **OpenID
Connect provider** — letting a third-party application let its users log in with their
Helix account, get back a verifiable identity (id_token), and call the Helix REST API on
their behalf. This is standard OAuth2 **authorization_code + PKCE** (OIDC on top is just
adding `openid` to the requested scope) — no Helix-specific SDK is needed, any HTTP client
or standard OIDC library works.

## Before you start

You have no access to this Helix instance's source code, database, or an existing
browser/admin session — everything must go through the HTTP endpoints below and the
Helix admin UI, using values the user supplies. Every URL here is written relative to
`<base_url>` — get the real value before doing anything else.

**Never print, echo, or log the value of `HELIX_OAUTH_CLIENT_SECRET`, any `code_verifier`,
or any issued `access_token`/`refresh_token`** anywhere in your output — not in chat, not
in command echoes, not in error messages. Treat them as write-only once obtained.

1. **`HELIX_BASE_URL`** — the root URL of the user's Helix deployment (e.g.
   `https://helix.example.com`). Ask the user; there's no way to derive or guess it.

2. **A registered OAuth application.** A Helix workspace admin (someone with permission to
   manage OAuth on their workspace) must register your application at
   `<base_url>/auth/oauth/apps/new/` before anything else works. **There is no API to
   self-register an app** — only that UI form — so ask the user for the values below, or
   walk them through registering one if they have admin access:
   - **`HELIX_OAUTH_CLIENT_ID`**
   - **`HELIX_OAUTH_CLIENT_SECRET`** — only if the app was registered as *confidential*
     (see [Client type](#client-type) below); public clients don't get one.
   - **`HELIX_OAUTH_TENANT`** — the workspace **slug** the app was registered
     under (shown in the Helix UI, e.g. `acme-corp`). Every login is scoped to exactly
     one workspace, chosen at registration+authorize time — see
     [Calling the REST API](#calling-the-rest-api).
   - **`HELIX_WORKSPACE_TENANT`** — the workspace **slug** a logged-in Helix user must
     belong to for this app to let them in, verified via `GET /api/v1/tenants/` after
     login (see [gate-only integration](#pattern-gate-only-integration-app-owns-its-own-authorization)).
     **Not necessarily the same workspace as `HELIX_OAUTH_TENANT`**: the OAuth app can be
     registered under (and its token scoped to) one workspace while access is gated on
     membership of another. Set it equal to `HELIX_OAUTH_TENANT` if you want the app's own
     registration workspace to also be the one that admits users.

3. **A redirect URI your application controls.** Decide/implement a callback route in
   your own app first (e.g. `https://yourapp.example.com/auth/helix/callback`), then have
   the admin register that *exact* URL (or a wildcarded version of it, see below) when
   creating the app. A mismatch here is the most common integration failure — see
   [Redirect URI matching](#redirect-uri-matching).

Suggested local credential storage (plain dotenv, gitignore it before writing):
```
HELIX_BASE_URL=https://helix.example.com
HELIX_OAUTH_CLIENT_ID=<client id>
# HELIX_OAUTH_CLIENT_SECRET is issued only for confidential clients; leave it
# blank for public clients (never send it at all — see Client type below).
HELIX_OAUTH_CLIENT_SECRET=<client secret>
HELIX_OAUTH_TENANT=<workspace slug>
# Workspace a logged-in Helix user must belong to for this app to let them
# in (checked via GET /api/v1/tenants/ after login) — not necessarily the
# same workspace as HELIX_OAUTH_TENANT above.
HELIX_WORKSPACE_TENANT=changeme
```

When these variables also go into the app's committed `.env.example` (so Atoll
prompts an operator for them), list each one as a **live, uncommented** line —
never `# HELIX_...`, or Atoll skips the key entirely and blocks the deploy when
the code reads it. Leave the values blank there and don't use inline `# ...`
comments (Atoll keeps them as part of the value); put any note on its own line
*above* the key. The five keys, as they belong in `.env.example`:
```
HELIX_BASE_URL=
HELIX_OAUTH_CLIENT_ID=
HELIX_OAUTH_CLIENT_SECRET=
HELIX_OAUTH_TENANT=
HELIX_WORKSPACE_TENANT=
```

## Redirect URI matching

OAuth2 redirect URIs must match **exactly** by default (this is a spec requirement, not a
Helix quirk — it prevents open-redirect attacks). A Helix admin can optionally register
one of two relaxations instead of an exact URL:

- **Leading hostname wildcard**: `https://*.example.com/callback` matches any subdomain
  (`https://preview.example.com/callback`, `https://staging.example.com/callback`, ...).
- **Trailing path wildcard**: `http://localhost:4200/*` matches any path under that exact
  origin (`http://localhost:4200/callback/`, `http://localhost:4200/anything`, ...) —
  useful for local development. Scheme, host, and port must still match exactly.

If the authorize step below returns an "invalid redirect_uri" error, the fix is always to
re-register the correct exact-or-wildcarded URI via the admin UI — there is no
client-side workaround.

## Client type

Chosen by the admin when registering the app:

- **Confidential** — for server-side applications that can keep `HELIX_OAUTH_CLIENT_SECRET`
  secret (never shipped to a browser/mobile binary). Include `client_secret` in the token
  exchange below.
- **Public** — for SPAs, mobile apps, or CLIs that cannot keep a secret. No
  `client_secret` is issued; **never send a `client_secret` param at all** for these
  (omit it, don't send it blank) — PKCE is the only protection.

PKCE (`S256`) is **mandatory for both** client types.

## Full flow

1. **Generate a PKCE pair** per login attempt:
   - `code_verifier` — a random string (43–128 chars, unreserved URL characters).
   - `code_challenge` — `BASE64URL(SHA256(code_verifier))`.
   Keep `code_verifier` in memory/session for step 4; never send it in step 2.

2. **Redirect the user's browser** to:
   ```
   GET <base_url>/auth/oauth/authorize/
       ?client_id=<HELIX_OAUTH_CLIENT_ID>
       &response_type=code
       &redirect_uri=<your registered callback URL>
       &tenant=<HELIX_OAUTH_TENANT>
       &scope=read+write+openid
       &code_challenge=<code_challenge>
       &code_challenge_method=S256
       &state=<random, unguessable value your app generates and remembers>
       &nonce=<random value, only needed if you want it echoed back in the id_token>
   ```
   Drop `openid` from `scope` if you only need API access, not a verified identity — see
   [Identity (OpenID Connect)](#identity-openid-connect) below.

   The user authenticates against Helix (their existing session, password, or SSO) and
   sees a consent screen naming your application and the workspace it's requesting
   access to. (Some apps are configured by their admin to skip this screen and
   auto-approve — nothing your app needs to handle differently either way.)

3. **Handle the redirect back** to your callback URL:
   `<redirect_uri>?code=<authorization code>&state=<same state you sent>`.
   Verify `state` matches what you generated in step 2 before proceeding (CSRF check).

4. **Exchange the code for tokens** — `application/x-www-form-urlencoded` POST:
   ```
   POST <base_url>/auth/oauth/token/
   grant_type=authorization_code
   &code=<code from step 3>
   &redirect_uri=<same URL used in step 2, exactly>
   &client_id=<HELIX_OAUTH_CLIENT_ID>
   &client_secret=<HELIX_OAUTH_CLIENT_SECRET>   # confidential clients only
   &code_verifier=<code_verifier from step 1>
   ```
   Response (`200`):
   ```json
   {
     "access_token": "...",
     "refresh_token": "...",
     "expires_in": 3600,
     "token_type": "Bearer",
     "scope": "read write openid",
     "id_token": "eyJ..."
   }
   ```
   `id_token` is only present if `openid` was in the requested `scope` — see
   [Identity (OpenID Connect)](#identity-openid-connect).

## Calling the REST API

Send `Authorization: Bearer <access_token>` to `<base_url>/api/v1/...`. Every
workspace-scoped call still requires the usual `?tenant_id=<uuid>` query param — that part of
the API contract is unchanged. Resolve your workspace's slug to its UUID once via:
```
GET <base_url>/api/v1/tenants/
Authorization: Bearer <access_token>
```

**CORS is enabled** on the token endpoint, `/userinfo/`, the OIDC discovery/JWKS
documents, and every `/api/v1/...` REST call (`Access-Control-Allow-Origin: *`) — a
browser-based SPA can call all of them directly with `fetch()`/`XMLHttpRequest` from any
origin, no backend proxy required. `Access-Control-Allow-Credentials` is deliberately
**not** set (these endpoints authenticate via the `Authorization` header/PKCE code, never
cookies), so don't send `credentials: 'include'` — it isn't needed and the browser would
reject the response if you did.

**The access token is permanently bound to the one workspace chosen at authorize time**
(`HELIX_OAUTH_TENANT`). Passing any other `tenant_id` — even one the underlying Helix user
also belongs to — gets rejected with `403`. If your app needs to act across multiple
workspaces, take the user through the authorize flow again with a different `tenant=` value;
each login yields a token scoped to just that one workspace.

## Refreshing

Access tokens expire (`expires_in` seconds, typically 3600). Refresh before/on expiry:
```
POST <base_url>/auth/oauth/token/
grant_type=refresh_token
&refresh_token=<current refresh_token>
&client_id=<HELIX_OAUTH_CLIENT_ID>
&client_secret=<HELIX_OAUTH_CLIENT_SECRET>   # confidential clients only
```
Returns a new `access_token` **and a new `refresh_token`** — refresh tokens rotate on
every use. Store the new one immediately; the old one is invalidated right away, and
reusing it returns `400 invalid_grant` (a sign your stored refresh token is stale —
usually because a previous refresh response wasn't persisted).

## Identity (OpenID Connect)

Every registered app is OIDC-capable — add `openid` to `scope` (step 2 of the flow above)
to get a signed `id_token` back from the token exchange, in addition to the access/refresh
tokens. Standard OIDC, no Helix-specific handling needed if you're using an OIDC library —
point it at the discovery document and it will find everything else itself:

```
GET <base_url>/auth/oauth/.well-known/openid-configuration
```
Returns `issuer`, `authorization_endpoint`, `token_endpoint`, `userinfo_endpoint`,
`jwks_uri`, `scopes_supported`, etc. Only `response_type=code` is supported (no
hybrid/implicit flows) — `response_types_supported` in the discovery doc reflects that.

**Verifying the id_token**: it's a JWT, signed `RS256`. Fetch the public key from:
```
GET <base_url>/auth/oauth/.well-known/jwks.json
```
and verify against it (any standard JWT/JOSE library) rather than trusting the token
unverified. If you sent `nonce` in step 2, confirm the id_token's `nonce` claim matches it.

**Claims** included in both the id_token and the `/userinfo/` endpoint response:

| claim | source |
|---|---|
| `sub` | Helix user's internal id |
| `email`, `given_name`, `family_name`, `name`, `preferred_username` | the Helix user's profile |
| `helix_tenant_id`, `helix_tenant_slug` | the workspace this login/token is scoped to (same as `HELIX_OAUTH_TENANT`) |

No `profile`/`email` sub-scopes to worry about — requesting `openid` alone returns the
full claim set above; Helix doesn't gate individual claims behind extra scopes.

**Userinfo endpoint** — same claims, callable any time the access token is still valid
(doesn't require re-parsing the id_token):
```
GET <base_url>/auth/oauth/userinfo/
Authorization: Bearer <access_token>
```

## Pattern: gate-only integration (app owns its own authorization)

Some integrations don't want to inherit anything from Helix beyond "who is
this person, and are they allowed near this app at all." The app has its own
user/permission model, fully managed inside the app itself — Helix login is
used only to (a) verify the person's identity and (b) confirm they belong to
the one workspace this app instance gates access on. **Do not** map Helix
roles/permissions/claims into the app's own authorization in this pattern —
the id_token/userinfo claims are for identity (who), not authority (what
they can do); that's entirely the app's own config/logic.

Two different workspace slugs are in play here, and they need not be the same:
`HELIX_OAUTH_TENANT` is what the OAuth app was registered under and what you
pass as `tenant=` at authorize time (it scopes the token); `HELIX_WORKSPACE_TENANT`
is the workspace the human must actually be a member of for this app to admit
them. The gate check below is against `HELIX_WORKSPACE_TENANT`.

1. Run the standard PKCE + token exchange flow from [Full flow](#full-flow)
   above, still passing `tenant=<HELIX_OAUTH_TENANT>` at authorize time as
   usual.
2. Immediately after obtaining `access_token`, call:
   ```
   GET <base_url>/api/v1/tenants/
   Authorization: Bearer <access_token>
   ```
   Response (`200`):
   ```json
   [
     {"id": "...", "name": "Acme Corp", "slug": "acme-corp"},
     {"id": "...", "name": "Other Co",  "slug": "other-co"}
   ]
   ```
   This lists **every** workspace the authenticated Helix user belongs to, not
   just the one `HELIX_OAUTH_TENANT` the access token is bound to — no
   `tenant_id` query param is needed or accepted here, it's the one
   discovery endpoint that isn't scoped that way. That's exactly what makes
   it useful for this check: it reflects the human's actual workspace
   memberships, independent of whatever workspace value the client happened to
   request at authorize time.
3. Check whether `HELIX_WORKSPACE_TENANT` (the app's own configured gating
   slug) appears among the returned `slug` values. This is a security check —
   treat a missing membership as an authorization failure, not a retryable
   error:
   - **Match** → proceed with app-local login. Beyond whatever's needed to
     hold the access/refresh tokens for this request/session, no Helix user
     record is created or persisted in the app's own database — what the
     user is allowed to do next is decided entirely by the app's own
     config/logic, never by anything read from Helix.
   - **No match** → deny access. Respond `403` (the app's own response — this
     isn't something Helix returns) and show the user a clear denial:
     **"Permission denied — contact your administrator."** **Discard the tokens
     immediately**: no session is created, no user record is created or
     updated, nothing is persisted. Don't leak *why* access was denied (which
     workspace was expected, what the user is a member of) into that message —
     "contact your administrator" is the whole recovery path.

If the app is already verifying the `id_token` for other reasons, its
`helix_tenant_slug` claim (see the claims table above) carries the workspace
the token was bound to — i.e. `HELIX_OAUTH_TENANT`, whatever was requested at
authorize time. When `HELIX_WORKSPACE_TENANT` differs from `HELIX_OAUTH_TENANT`
that claim is **not** a valid shortcut for this gate, and even when they match
it's a snapshot rather than live membership, so `/api/v1/tenants/` remains the
required check for this pattern.

## Gotchas

- **MCP is not supported.** These OAuth tokens only work against the REST API
  (`/api/v1/...`), not Helix's MCP server (`/api/mcp/...`). If the integration also needs
  MCP access, that requires a separate, manually-issued personal API token from a Helix
  user (see the `helix-mcp-api` skill if present) — the two token types are not
  interchangeable.
- No token introspection endpoint, and no RP-initiated logout endpoint — don't build a
  flow that depends on either. (The userinfo endpoint *is* available — see
  [Identity (OpenID Connect)](#identity-openid-connect).)
- Three scopes exist: `read`, `write`, `openid`. Omitting `scope` defaults to `read write`
  (no identity) — `openid` must always be requested explicitly.
- A registered app's `client_id`/`client_secret`/redirect URIs can only be viewed or
  changed by the Helix workspace admin who manages it, via the same `/auth/oauth/apps/`
  admin UI — ask the user to make changes there, you cannot do it via API.
