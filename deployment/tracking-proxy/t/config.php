<?php
// Same-domain open-tracking config. No Cloudflare tunnel required.
// open.php logs opens to opens.log; events.php serves them to the app
// (protected by shared_secret — must match TRACKING_PROXY_SECRET in the app .env).
return [
    'shared_secret' => 'XQ1UsY4PX36yd_qrBc_2TpxPEOYoeeLSlydeUMkjeWM',
    'log_file' => __DIR__ . '/opens.log',
    // Rotate (delete) the log once it grows past this many bytes.
    'max_log_bytes' => 5 * 1024 * 1024,
];
