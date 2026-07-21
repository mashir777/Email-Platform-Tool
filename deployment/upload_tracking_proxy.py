"""
Upload the same-domain tracking proxy to Namecheap hosting (no tunnel needed).

Usage (PowerShell):
  $env:FTP_USER="your_cpanel_username"
  $env:FTP_PASS="your_cpanel_password"
  python deployment/upload_tracking_proxy.py

After upload these must work in a browser:
  https://datrixworld.com/t/ping.txt   -> ok
  https://datrixworld.com/t/open.php   -> a tiny transparent image (HTTP 200)

Then in the app .env keep:
  TRACKING_PROXY_BASE_URL=https://datrixworld.com
  TRACKING_PROXY_SECRET=<same value as shared_secret in config.php>
Restart Django and Send Again a campaign — opens record with no tunnel.
"""
from __future__ import annotations

import ftplib
import os
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOCAL_DIR = ROOT / "tracking-proxy" / "t"
REMOTE_DIR = "public_html/t"
FTP_HOST = os.environ.get("FTP_HOST", "ftp.datrixworld.com")
FTP_USER = os.environ.get("FTP_USER", "").strip()
FTP_PASS = os.environ.get("FTP_PASS", "")
PUBLIC_DOMAIN = os.environ.get("TRACKING_PROXY_DOMAIN", "https://datrixworld.com").rstrip("/")


def current_secret() -> str:
    """Prefer TRACKING_PROXY_SECRET env; otherwise reuse config.php's value."""
    secret = (os.environ.get("TRACKING_PROXY_SECRET") or "").strip()
    if secret:
        return secret
    config = LOCAL_DIR / "config.php"
    if config.exists():
        match = re.search(r"'shared_secret'\s*=>\s*'([^']+)'", config.read_text(encoding="utf-8"))
        if match:
            return match.group(1)
    return ""


def write_config(secret: str) -> None:
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    (LOCAL_DIR / "config.php").write_text(
        "<?php\n"
        "// Same-domain open-tracking config. No Cloudflare tunnel required.\n"
        "return [\n"
        f"    'shared_secret' => {secret!r},\n"
        "    'log_file' => __DIR__ . '/opens.log',\n"
        "    'max_log_bytes' => 5 * 1024 * 1024,\n"
        "];\n",
        encoding="utf-8",
    )


def ensure_remote_dir(ftp: ftplib.FTP, path: str) -> None:
    parts = [p for p in path.replace("\\", "/").split("/") if p]
    ftp.cwd("/")
    for part in parts:
        try:
            ftp.cwd(part)
        except ftplib.error_perm:
            ftp.mkd(part)
            ftp.cwd(part)


def upload() -> None:
    if not FTP_USER or not FTP_PASS:
        print("Set FTP_USER and FTP_PASS env vars (Namecheap cPanel FTP).")
        sys.exit(1)

    secret = current_secret()
    if not secret:
        print("No shared secret found. Set TRACKING_PROXY_SECRET or fill config.php.")
        sys.exit(1)
    write_config(secret)

    files = [p for p in LOCAL_DIR.iterdir() if p.is_file() and p.name != "opens.log"]
    if not files:
        print(f"No files in {LOCAL_DIR}")
        sys.exit(1)

    print(f"Uploading to {FTP_HOST}:{REMOTE_DIR}")
    ftp = ftplib.FTP()
    ftp.connect(FTP_HOST, 21, timeout=30)
    ftp.login(FTP_USER, FTP_PASS)
    ensure_remote_dir(ftp, REMOTE_DIR)
    for path in files:
        with path.open("rb") as handle:
            ftp.storbinary(f"STOR {path.name}", handle)
        print(f"  uploaded {path.name}")
    ftp.quit()

    ok = True
    for probe in (f"{PUBLIC_DOMAIN}/t/ping.txt", f"{PUBLIC_DOMAIN}/t/open.php"):
        try:
            with urllib.request.urlopen(probe, timeout=10) as resp:
                print(f"OK {probe} -> {resp.status}")
        except Exception as exc:  # noqa: BLE001
            ok = False
            print(f"Probe {probe} failed: {exc}")
    if not ok:
        sys.exit(2)
    print("\nDone. Now: Restart Django -> Send Again a campaign -> open email -> Refresh.")


if __name__ == "__main__":
    upload()
