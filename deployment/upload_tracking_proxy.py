"""
Upload same-domain tracking proxy to Namecheap hosting.

Usage (PowerShell):
  $env:FTP_USER="your_cpanel_username"
  $env:FTP_PASS="your_cpanel_password"
  python D:\twilio\email_platform\deployment\upload_tracking_proxy.py

After upload, https://datrixworld.com/t/open.php should return HTTP 200.
Then resend a campaign — open tracking uses same-domain pixels (Gmail-safe).
"""
from __future__ import annotations

import ftplib
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOCAL_DIR = ROOT / "tracking-proxy" / "t"
REMOTE_DIR = "public_html/t"
FTP_HOST = os.environ.get("FTP_HOST", "ftp.datrixworld.com")
FTP_USER = os.environ.get("FTP_USER", "").strip()
FTP_PASS = os.environ.get("FTP_PASS", "")


def live_tunnel() -> str:
    try:
        with urllib.request.urlopen("http://127.0.0.1:20241/quicktunnel", timeout=2) as resp:
            data = json.loads(resp.read().decode())
            host = (data.get("hostname") or "").strip()
            if host:
                return f"https://{host}"
    except Exception:
        pass
    return os.environ.get(
        "TRACKING_ORIGIN_BACKEND_URL",
        "https://passport-systems-brands-surgical.trycloudflare.com",
    ).rstrip("/")


def write_config(origin: str) -> None:
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    (LOCAL_DIR / "config.php").write_text(
        "<?php\nreturn [\n    'origin_backend_url' => "
        + repr(origin)
        + ",\n];\n",
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

    origin = live_tunnel()
    write_config(origin)
    files = [p for p in LOCAL_DIR.iterdir() if p.is_file()]
    if not files:
        print(f"No files in {LOCAL_DIR}")
        sys.exit(1)

    print(f"Uploading to {FTP_HOST}:{REMOTE_DIR} origin={origin}")
    ftp = ftplib.FTP()
    ftp.connect(FTP_HOST, 21, timeout=30)
    ftp.login(FTP_USER, FTP_PASS)
    ensure_remote_dir(ftp, REMOTE_DIR)
    for path in files:
        with path.open("rb") as handle:
            ftp.storbinary(f"STOR {path.name}", handle)
        print(f"  uploaded {path.name}")
    ftp.quit()

    probe = "https://datrixworld.com/t/open.php"
    try:
        with urllib.request.urlopen(probe, timeout=10) as resp:
            print(f"OK {probe} → {resp.status}")
    except Exception as exc:
        print(f"Probe {probe} failed: {exc}")
        sys.exit(2)


if __name__ == "__main__":
    upload()
