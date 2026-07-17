# Upload the `t` folder to Namecheap cPanel → File Manager → public_html →
# so these URLs work:
#   https://datrixworld.com/t/o/{token}/
#   https://datrixworld.com/t/c/{token}/
#
# 1. Edit config.php → set origin_backend_url to your Cloudflare tunnel
#    (the URL that reaches local Django on port 8000).
# 2. Keep Django running + Cloudflare tunnel running.
# 3. In project .env:
#      TRACKING_PUBLIC_BASE_URL=https://datrixworld.com
#      TRACKING_ORIGIN_BACKEND_URL=https://YOUR-TUNNEL.trycloudflare.com
# 4. Restart Django, then Send Again a campaign.
#
# Why: Gmail trusts images on datrixworld.com (same as From).
# Tunnel hosts (trycloudflare) look suspicious and hide images.
