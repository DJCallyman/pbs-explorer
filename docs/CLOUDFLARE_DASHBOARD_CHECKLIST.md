# Cloudflare Dashboard Checklist

Use this checklist when setting up PBS Explorer behind Cloudflare from the Mac mini.

Assumptions:

- your domain is already on Cloudflare
- PBS Explorer is running on the Mac mini
- the app is bound to `127.0.0.1:8000`
- your final hostname will be `app.yourdomain.com`

## A. Prepare The Mac Mini

1. Copy the Cloudflare example environment:

```bash
cp deploy/mac-mini-cloudflare.env.example .env
```

2. Edit `.env` and replace:

- `your_real_subscription_key`
- `app.yourdomain.com`
- `admin`
- `use_a_long_random_password_here`
- `another_long_random_secret`

3. Start the app locally:

```bash
./scripts/run_server.sh
```

4. Confirm local access on the Mac mini:

```text
http://127.0.0.1:8000/login
```

## B. Install `cloudflared`

On the Mac mini:

```bash
brew install cloudflared
cloudflared --version
```

## C. Create The Tunnel

In the Cloudflare dashboard:

1. Open `Zero Trust`
2. Go to `Networks` -> `Tunnels`
3. Click `Create a tunnel`
4. Choose `Cloudflared`
5. Name it `pbs-explorer-mini`
6. Choose `macOS`
7. Copy the generated install command

Run the command on the Mac mini. It will resemble:

```bash
sudo cloudflared service install <TUNNEL_TOKEN>
```

After installation:

```bash
sudo cloudflared service uninstall
```

is the rollback command if you need to start over.

## D. Add The Public Hostname

Still in the tunnel setup:

1. Add a public hostname
2. Subdomain: `app`
3. Domain: `yourdomain.com`
4. Path: leave blank
5. Type: `HTTP`
6. URL: `127.0.0.1:8000`
7. Save tunnel

Cloudflare should create the required DNS route automatically.

## E. Create The Access App

In the Cloudflare dashboard:

1. Go to `Zero Trust`
2. Go to `Access` -> `Applications`
3. Click `Add an application`
4. Choose `Self-hosted`
5. Application name: `PBS Explorer`
6. Domain: `app.yourdomain.com`
7. Session duration: start with a moderate value such as 8 to 24 hours
8. Leave advanced settings at defaults unless you know you need them

## F. Create The Access Policy

For a small user group:

1. Create an `Allow` policy
2. Include your own email address
3. Include the 2-3 other users by email address
4. Save the policy

If you want stricter control later, add:

- country restrictions
- device posture rules
- shorter session durations

## G. Test Public Access

Test from a personal device first:

1. Open `https://app.yourdomain.com`
2. Confirm Cloudflare Access prompts before the app loads
3. Sign in through Cloudflare Access
4. Confirm PBS Explorer then shows its own login page
5. Sign in to PBS Explorer
6. Test browse, search, admin, and CSV export

Then test from your work network.

## H. If Something Fails

Check these first:

- `.env` has `PBS_EXPLORER_SERVER_HOST=127.0.0.1`
- `.env` includes `app.yourdomain.com` in `PBS_EXPLORER_SERVER_TRUSTED_HOSTS`
- `./scripts/run_server.sh` is running
- the tunnel is healthy in Cloudflare
- `cloudflared` is running on the Mac mini
- Cloudflare Access policy includes the correct email addresses

Useful local checks:

```bash
lsof -nP -iTCP:8000
tail -f .run/pbs-explorer.log
```
