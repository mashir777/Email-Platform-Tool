<?php
/**
 * Same-domain click-tracking proxy.
 * Upload folder `t` to public_html/t/
 */
declare(strict_types=1);

$config = require __DIR__ . '/config.php';
$path = isset($_GET['path']) ? (string) $_GET['path'] : '';
$path = trim($path, "/ \t\n\r");
$query = $_SERVER['QUERY_STRING'] ?? '';
// Remove path= from query if present when rewriting
parse_str($query, $params);
unset($params['path']);
$qs = http_build_query($params);

if ($path === '' || !preg_match('/^[\w=-]+$/', $path)) {
    http_response_code(404);
    echo 'Not found';
    exit;
}

$origin = rtrim((string) ($config['origin_backend_url'] ?? ''), '/');
$target = $origin . '/t/c/' . $path . '/';
if ($qs !== '') {
    $target .= '?' . $qs;
}

header('Location: ' . $target, true, 302);
exit;
