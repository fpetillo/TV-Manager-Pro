# Browser & LAN Security

## Localhost behavior

TV Manager remains easy to run locally:

```text
http://127.0.0.1:5050
```

If browser authentication has never been enabled, requests originating from loopback are allowed.

This compatibility bypass does **not** apply to other PCs.

## Create the administrator account

From the TV Manager PC, either open:

```text
http://127.0.0.1:5050/security/setup
```

or use **Settings → Security**.

Administrator passwords must contain at least 12 characters.

The password is not stored in plaintext. TV Manager stores a PBKDF2-HMAC-SHA256 derived value, a unique random salt, and the iteration count.

## Enable browser authentication

In **Settings → Security**, enable **Require browser login**.

Once enabled:

- browser pages require a login;
- browser API writes require a valid session and CSRF token;
- bearer API tokens can still authenticate integrations;
- sign-out is available from the navigation bar.

## LAN access

The production runner defaults to:

```text
HOST=127.0.0.1
```

Before using a LAN binding such as:

```text
HOST=0.0.0.0
```

you must:

1. Create an administrator password.
2. Enable browser authentication.
3. Restart `run-prod.ps1`.
4. Add only the Windows Firewall rule needed for trusted LAN access.

`server.py` deliberately refuses non-loopback binding when browser security is not ready.

Do not expose TV Manager directly to the public Internet.

## CSRF protection

Authenticated browser sessions receive a random CSRF value in the session and a matching non-HttpOnly SameSite cookie. `global.js` automatically attaches the value as:

```text
X-CSRF-Token
```

to same-origin browser write requests.

Bearer-token API clients are not required to use the browser CSRF mechanism.

## Login throttling

Five failed attempts from the same address within 15 minutes temporarily block further login attempts from that address.

Security activity is visible under **Settings → Security → Recent Security Events**.

## Session secret

TV Manager uses:

```text
.tvmanager-session-key
```

unless `TVMANAGER_SESSION_SECRET` is explicitly configured.

The file is generated automatically and is excluded by `.gitignore`.

It should not be committed to GitHub.

Losing the file invalidates active browser sessions but does not change the administrator password, which is stored in `tvmanager.db`.

## API tokens

API tokens remain managed from the System page.

Only a hash of each API token is stored. The clear token is shown once when it is created.

v16 records authenticated bearer-token requests in `api_access_log`.
