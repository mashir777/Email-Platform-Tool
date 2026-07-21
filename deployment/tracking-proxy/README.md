# Same-domain open tracking (no Cloudflare tunnel needed)

Emails carry a 1x1 pixel on your OWN domain:

    https://datrixworld.com/t/open.php?path={token}

When Gmail loads that image, `open.php` writes the open to `opens.log` on your
hosting (always online — no tunnel, no PC required). Your app periodically reads
`opens.log` through `events.php` and marks the recipient as "opened" (Yes).

## One-time setup

1. Upload the whole `t` folder to your hosting so it lives at:
   `public_html/t/` (Namecheap cPanel → File Manager, or FTP).
   Files: `open.php`, `events.php`, `config.php`, `ping.txt`.

   You can also run the uploader (needs cPanel FTP login):

       $env:FTP_USER="your_cpanel_username"
       $env:FTP_PASS="your_cpanel_password"
       python deployment/upload_tracking_proxy.py

2. Confirm it is live — open in a browser:
   - `https://datrixworld.com/t/ping.txt`  → shows `ok`
   - `https://datrixworld.com/t/open.php`   → returns a tiny (transparent) image

3. In the project `.env` set (already done for you):

       TRACKING_PROXY_BASE_URL=https://datrixworld.com
       TRACKING_PROXY_SECRET=<same value as shared_secret in config.php>

4. Restart Django, then **Send Again** a campaign.
   Open the new email in Gmail, then click **Refresh** in the Email Tracking
   popup — the opened recipients turn to **Yes**.

## Why same-domain?

Gmail trusts images on `datrixworld.com` (same as the From address). Free tunnel
hosts (trycloudflare/ngrok) rotate and often get images hidden, so opens stayed
"No". This setup needs no tunnel and works even when your PC is off.

`config.php.shared_secret` must equal `TRACKING_PROXY_SECRET` in `.env` — it stops
strangers from reading your opens log.
