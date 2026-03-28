# Secure Deployment Guide

This app now supports a safer Mac mini deployment shape:

- bind the app to `127.0.0.1`
- put Caddy in front for HTTPS
- use the app's own session-based login page for browser access
- restrict trusted hosts to the real domain names you use
- disable FastAPI docs in production
- optionally disable PSD Search for a cleaner deployment

## User Accounts

The browser UI uses the built-in login page at `/login`.

- the `.env` credentials are the bootstrap admin account
- that admin can access everything, including `/admin`
- from the Admin page, the admin can create additional managed users
- managed users can use the app normally but do not see the Admin page

Managed users and browser sessions are stored in the app database support tables, not long-term JSON files.

## Recommended Option: Private Access Over Tailscale

This is still the safest and simplest remote-access option.

Set these in `.env` on the Mac mini:

```bash
PBS_EXPLORER_SERVER_HOST=0.0.0.0
PBS_EXPLORER_SERVER_PORT=8000
PBS_EXPLORER_SERVER_TRUSTED_HOSTS=127.0.0.1,localhost,::1,YOUR-MINI-TAILSCALE-NAME,YOUR-MINI-TAILSCALE-IP
PBS_EXPLORER_WEB_USERNAME=your_bootstrap_admin
PBS_EXPLORER_WEB_PASSWORD=use_a_long_random_password
PBS_EXPLORER_SERVER_ENABLE_DOCS=false
```

Then start with:

```bash
./scripts/run_server.sh
```

From another device on your tailnet, browse to:

```text
http://YOUR-MINI-TAILSCALE-NAME:8000/login
```

This avoids public DNS, public port forwarding, and the risk profile of a home-hosted public site.

## Public Internet Option: Reverse Proxy + HTTPS

If you want browser access over the public internet:

1. keep PBS Explorer behind a reverse proxy
2. use HTTPS only
3. do not expose port `8000` directly to the internet
4. use strong managed-user passwords
5. restrict trusted hosts to your actual domain names
6. prefer a custom domain you control over dynamic DNS if possible

Recommended `.env` settings:

```bash
PBS_EXPLORER_SERVER_HOST=127.0.0.1
PBS_EXPLORER_SERVER_PORT=8000
PBS_EXPLORER_SERVER_TRUSTED_HOSTS=127.0.0.1,localhost,::1,YOUR-DOMAIN.example.com
PBS_EXPLORER_WEB_USERNAME=your_bootstrap_admin
PBS_EXPLORER_WEB_PASSWORD=use_a_long_random_password
PBS_EXPLORER_SERVER_ENABLE_DOCS=false
PBS_EXPLORER_SERVER_ENABLE_PSD=true
PBS_EXPLORER_ADMIN_API_KEY=another_long_random_secret
```

In this mode:

- the app listens only on localhost
- Caddy terminates HTTPS and forwards to `127.0.0.1:8000`
- browser users sign in through `/login`
- Power Query / CSV sharing can still use report-specific tokenized links

## CSV / Power Query Links

Saved report CSV URLs can use per-report access tokens:

```text
https://YOUR-DOMAIN.example.com/web/saved-reports/<slug>.csv?access_token=...
```

Important:

- anyone with that full URL can fetch that one CSV
- it does not grant access to the rest of the app
- rotate the URL from `Saved Searches` if a link is over-shared
- these links are convenient for Excel, but they are still bearer-token URLs

## Firewall / Router Rules

- if using Tailscale only: do not forward any router ports
- if using a public reverse proxy: forward only `80` and `443` to Caddy
- do not expose `8000` directly

## Caddy

Use the example in:

- `deploy/Caddyfile.example`

That example reflects the app's current session-based login flow. The reverse proxy does HTTPS and forwarding only; the app itself handles browser authentication.

## Corporate Network Considerations

Public home-hosted sites are more likely to be flagged by enterprise filtering when they use:

- dynamic DNS domains such as `duckdns.org`
- residential IP addresses
- unknown login forms
- downloadable CSV files
- bearer tokens in query strings

To reduce risk perception:

- prefer Tailscale or a corporate-approved VPN when possible
- if public, prefer a custom domain you control over dynamic DNS
- keep the site behind HTTPS only
- avoid exposing the app directly on a raw port
- use strong managed-user passwords and revoke unused report links

## Deployment Bundle

To create a Mac-mini-ready bundle from the laptop:

```bash
chmod +x scripts/build_deploy_bundle.sh
./scripts/build_deploy_bundle.sh
```

To exclude the SQLite DB from the archive:

```bash
./scripts/build_deploy_bundle.sh --without-db
```

For the staged deployment choices:

- use `deploy/mac-mini-public.env.example` for the normal public deployment
- use `deploy/mac-mini-public-no-psd.env.example` if you want PSD hidden until it is ready
