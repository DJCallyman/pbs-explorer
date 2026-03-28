# Mac Mini + Tailscale Setup

This guide is the recommended first deployment path for PBS Explorer:

- host it on your always-on Mac Mini
- access it privately over Tailscale
- run the web app automatically on boot
- run a weekly incremental sync automatically

## 1. Copy The Project To The Mac Mini

Copy the full project folder to the Mini.

You can use AirDrop, a shared folder, `rsync`, GitHub, or any other method you prefer.

Assume the final path is:

```bash
/Users/YOUR_USER/pbs-explorer-main
```

## 2. Install Tailscale On The Mini

Install Tailscale on the Mac Mini and sign in with the same account you already created.

Once connected, the Mini will get a private Tailscale name and IP.

## 3. Install Python And Create The Virtualenv

From the project folder on the Mini:

```bash
cd /Users/YOUR_USER/pbs-explorer-main
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
mkdir -p logs
```

## 4. Create Your `.env`

Copy the example file:

```bash
cp .env.example .env
```

Then edit `.env` and set at least:

```bash
PBS_EXPLORER_PBS_SUBSCRIPTION_KEY=your_real_key_here
PBS_EXPLORER_DB_TYPE=sqlite
PBS_EXPLORER_DB_PATH=./pbs_data.db
PBS_EXPLORER_SERVER_HOST=0.0.0.0
PBS_EXPLORER_SERVER_PORT=8000
PBS_EXPLORER_SERVER_TRUSTED_HOSTS=127.0.0.1,localhost,::1,YOUR-MINI-TAILSCALE-NAME,YOUR-MINI-TAILSCALE-IP
PBS_EXPLORER_WEB_USERNAME=your_username
PBS_EXPLORER_WEB_PASSWORD=use_a_long_random_password
PBS_EXPLORER_LOG_LEVEL=INFO
```

These web credentials are the bootstrap admin account:

- this account can access the full app, including `Admin`
- from the `Admin` page, you can create additional managed users
- managed `user` accounts can use the app but cannot access `Admin`

Optional:

```bash
PBS_EXPLORER_ADMIN_API_KEY=generate_a_random_secret_if_you_want_one
```

## 5. First-Time Database Setup

Run this once on the Mini:

```bash
source venv/bin/activate
python -m tasks.bootstrap_db
python -m tasks.sync
```

The first full sync can take a long time.

## 6. Test Local Run On The Mini

Start the app manually first:

```bash
./scripts/run_server.sh
```

Then from another machine on your tailnet, open:

```text
http://YOUR-MINI-TAILSCALE-NAME:8000/web
```

or:

```text
http://YOUR-MINI-TAILSCALE-IP:8000/web
```

You can also check:

```text
http://YOUR-MINI-TAILSCALE-NAME:8000/docs
```

## 7. Set Up Automatic Start With `launchd`

Create the LaunchAgents directory if needed:

```bash
mkdir -p ~/Library/LaunchAgents
mkdir -p logs
```

Open the template files in `launchd/` and replace:

```text
__REPO_ROOT__
```

with the real project path, for example:

```text
/Users/YOUR_USER/pbs-explorer-main
```

Copy them into place:

```bash
cp launchd/com.pbs-explorer.web.plist ~/Library/LaunchAgents/
cp launchd/com.pbs-explorer.sync.weekly.plist ~/Library/LaunchAgents/
```

Load them:

```bash
launchctl load ~/Library/LaunchAgents/com.pbs-explorer.web.plist
launchctl load ~/Library/LaunchAgents/com.pbs-explorer.sync.weekly.plist
```

If you update a plist later:

```bash
launchctl unload ~/Library/LaunchAgents/com.pbs-explorer.web.plist
launchctl unload ~/Library/LaunchAgents/com.pbs-explorer.sync.weekly.plist
launchctl load ~/Library/LaunchAgents/com.pbs-explorer.web.plist
launchctl load ~/Library/LaunchAgents/com.pbs-explorer.sync.weekly.plist
```

## 8. Weekly Sync Behavior

The weekly job runs:

```bash
./scripts/run_incremental_sync.sh
```

That calls:

```bash
python -m tasks.sync_incremental
```

The incremental sync will:

- do nothing if the DB is already current
- sync only changes when a newer schedule exists
- fall back to a full sync if there is no sync state yet

## 9. Logs

The launchd jobs write logs to:

- `logs/web.stdout.log`
- `logs/web.stderr.log`
- `logs/sync.stdout.log`
- `logs/sync.stderr.log`

You can tail them with:

```bash
tail -f logs/web.stdout.log
tail -f logs/sync.stdout.log
```

## 10. Suggested Weekly Schedule

The template is set to:

- Monday
- 4:00 AM

That is easy to change in:

- `launchd/com.pbs-explorer.sync.weekly.plist`

## 11. Recommended Next Step

Once this is running successfully on the Mini over Tailscale:

- keep this deployment path stable
- then redesign the search UI on top of a known-good remote environment
