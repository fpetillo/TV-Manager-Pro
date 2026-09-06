# Security

TV Manager is local-first and binds to localhost by default.

## API authentication
API token enforcement is opt-in under Settings. When enabled, non-health `/api/*` endpoints require either:
- `Authorization: Bearer <token>`
- `X-TVManager-Token: <token>`

Create tokens in **System → API Tokens**. Tokens are shown once and stored only as hashes.

## Secrets
Imported passwords/API keys/tokens are masked in the UI. Diagnostic bundles redact settings marked secret.

## Remote access
Do not expose the Flask development server directly to the Internet. Put authenticated remote deployments behind a production reverse proxy/TLS layer and keep application API authentication enabled.

## Managed trash
Upgrade replacement files are retained locally in managed trash to support rollback. Access to the TV Manager data directory therefore grants access to previous media versions; protect it with normal filesystem permissions.


## Production server binding
`server.py` binds to `127.0.0.1` by default. Changing `HOST` to a LAN-accessible address increases exposure. API-token support does not replace full browser authentication and CSRF protection, which remain roadmap work; do not expose TV Manager directly to the public Internet.


## v16 browser authentication

v16 adds optional browser sessions, PBKDF2 password hashing, CSRF checks, login throttling, security-event logging, and a non-loopback production binding guard.

Localhost retains the no-login compatibility path until browser security is enabled. Remote addresses never receive that bypass.

See [Browser & LAN Security](BROWSER_SECURITY.md).
