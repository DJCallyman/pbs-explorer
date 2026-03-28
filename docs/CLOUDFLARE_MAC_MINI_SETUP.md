# Mac Mini + Cloudflare Setup

This guide publishes PBS Explorer from the Mac mini through Cloudflare without opening inbound router ports.

Recommended shape:

- PBS Explorer runs on the Mac mini
- the app listens on `127.0.0.1:8000`
- `cloudflared` runs on the Mac mini and creates an outbound tunnel to Cloudflare
- Cloudflare Access protects the public hostname before traffic reaches the app
- the app's own login remains enabled as a second layer

This is the recommended first Cloudflare deployment because it preserves the app's current operating model while improving public posture versus direct home hosting.

## 1. Prerequisites

You need:

- a Mac mini that already runs PBS Explorer successfully
- a custom domain you control
- a Cloudflare account
- the domain delegated to Cloudflare DNS

Before exposing anything through Cloudflare, confirm the app works locally on the Mac mini:

```bash
cd /Users/YOUR_USER/pbs-explorer-main
./scripts/run_server.sh
```

Then test on the Mac mini itself:

```text
http://127.0.0.1:8000/login
```

## 2. Lock The App To Localhost

Use a `.env` on the Mac mini similar to:

```bash
PBS_EXPLORER_PBS_SUBSCRIPTION_KEY=your_real_key_here
PBS_EXPLORER_DB_TYPE=sqlite
PBS_EXPLORER_DB_PATH=./pbs_data.db
PBS_EXPLORER_SERVER_HOST=127.0.0.1
PBS_EXPLORER_SERVER_PORT=8000
PBS_EXPLORER_SERVER_TRUSTED_HOSTS=127.0.0.1,localhost,::1,app.yourdomain.com
PBS_EXPLORER_WEB_USERNAME=your_bootstrap_admin
PBS_EXPLORER_WEB_PASSWORD=use_a_long_random_password
PBS_EXPLORER_SERVER_ENABLE_DOCS=false
PBS_EXPLORER_LOG_LEVEL=INFO
```

Notes:

- keep the app bound to `127.0.0.1`
- include the final Cloudflare hostname in `PBS_EXPLORER_SERVER_TRUSTED_HOSTS`
- keep the in-app login enabled

## 3. Install `cloudflared`

On the Mac mini:

```bash
brew install cloudflared
cloudflared --version
```

## 4. Create The Tunnel In Cloudflare

In the Cloudflare dashboard:

1. Go to `Zero Trust` or `Networking > Tunnels`
2. Create a named tunnel such as `pbs-explorer-mini`
3. Choose `macOS`
4. Copy the install command Cloudflare gives you

It will look similar to:

```bash
sudo cloudflared service install <TUNNEL_TOKEN>
```

Run that on the Mac mini.

This installs `cloudflared` as a service so the tunnel persists across reboots.

## 5. Route A Public Hostname To The Local App

In the Cloudflare Tunnel configuration:

- create a public hostname such as `app.yourdomain.com`
- service type: `HTTP`
- service URL: `http://127.0.0.1:8000`

Do not point the tunnel directly at a LAN IP unless you have a reason to. The app can remain localhost-only.

## 6. Add Cloudflare Access In Front

In Cloudflare Access:

1. Add an application
2. Choose `Self-hosted`
3. Set the application domain to `app.yourdomain.com`
4. Create a simple allow policy for just your small user set

Good first policy choices:

- allow your own email address
- allow 2-3 specific email addresses for the other users

If your company uses a supported identity provider and you are allowed to use it, that is ideal. Otherwise, use a small external identity option that Cloudflare supports for your user group.

Suggested session posture:

- require login before access
- short or moderate session duration
- keep one-time PIN disabled unless needed for the user group

## 7. Keep The App Login As A Second Layer

For the first deployment, keep PBS Explorer's own login enabled as well:

- Cloudflare Access becomes the outer gate
- PBS Explorer login remains the app-level gate

This is slightly less convenient, but it gives you defense in depth while the deployment is still new.

You can simplify later once you are confident in the Cloudflare setup.

## 8. Router / Firewall Guidance

If you use Cloudflare Tunnel:

- do not forward port `8000`
- do not forward `80` or `443` just for PBS Explorer
- the Mac mini only needs outbound internet access

This is one of the biggest security improvements versus direct home exposure.

## 9. Test In Order

Test in this order:

1. `http://127.0.0.1:8000/login` on the Mac mini
2. `cloudflared` service is running
3. `https://app.yourdomain.com` from a personal device
4. confirm Cloudflare Access blocks unauthenticated access
5. sign in through Cloudflare Access
6. sign in through PBS Explorer
7. test search, browse, CSV export, and admin access
8. test from a work network

## 10. Operational Checklist

After initial setup:

- keep `cloudflared` updated
- keep macOS updated
- rotate app passwords if they have been shared
- review Cloudflare Access logs if users are blocked
- keep backups of `pbs_data.db` and `.env`
- monitor the local app log and tunnel health after Mac reboots

## 11. Suggested First Public Shape

Use:

- one hostname: `app.yourdomain.com`
- Cloudflare Tunnel
- Cloudflare Access for the 2-3 known users
- in-app login still enabled
- no public docs endpoint
- no direct port exposure

That is the cleanest first deployment before considering Oracle or a larger redesign.
