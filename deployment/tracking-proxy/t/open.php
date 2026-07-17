<?php
/**
 * Same-domain open-tracking proxy for Gmail-safe pixels.
 * Upload this whole `t` folder to: public_html/t/
 * Emails use: https://YOURDOMAIN.com/t/o/{token}/
 * This forwards the request to your local Django (Cloudflare tunnel / server).
 */
declare(strict_types=1);

$config = require __DIR__ . '/config.php';
$path = isset($_GET['path']) ? (string) $_GET['path'] : '';
$path = trim($path, "/ \t\n\r");
if ($path === '' || !preg_match('/^[\w=-]+$/', $path)) {
    http_response_code(404);
    header('Content-Type: image/png');
    echo base64_decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=');
    exit;
}

$origin = rtrim((string) ($config['origin_backend_url'] ?? ''), '/');
$target = $origin . '/t/o/' . $path . '/';

$context = stream_context_create([
    'http' => [
        'method' => 'GET',
        'timeout' => 12,
        'ignore_errors' => true,
        'header' => "User-Agent: DatrixTrackingProxy/1.0\r\nAccept: image/*,*/*\r\n",
    ],
    'ssl' => [
        'verify_peer' => true,
        'verify_peer_name' => true,
    ],
]);

$data = @file_get_contents($target, false, $context);
header('Content-Type: image/png');
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
header('Pragma: no-cache');

if ($data === false || $data === '') {
    // Still return a transparent pixel so the email client is happy.
    echo base64_decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=');
    exit;
}

echo $data;
