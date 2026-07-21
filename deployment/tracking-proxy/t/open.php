<?php
/**
 * Same-domain open-tracking pixel (tunnel-free).
 * Email pixel: https://YOURDOMAIN.com/t/open.php?path={token}
 * Records the open into opens.log and returns a 1x1 transparent GIF.
 * The app pulls opens.log via events.php and marks recipients as opened.
 */
declare(strict_types=1);

$config = require __DIR__ . '/config.php';

$path = isset($_GET['path']) ? (string) $_GET['path'] : '';
$path = urldecode($path);
$path = trim($path, "/ \t\n\r");
if (substr($path, -4) === '.gif') {
    $path = substr($path, 0, -4);
}

// 1x1 transparent GIF — always returned so the email client shows nothing broken.
$gif = base64_decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7');
header('Content-Type: image/gif');
header('Content-Length: ' . strlen($gif));
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');
header('Pragma: no-cache');
header('Expires: 0');

if ($path !== '' && preg_match('/^[\w=.-]+$/', $path)) {
    $logFile = (string) ($config['log_file'] ?? (__DIR__ . '/opens.log'));
    $max = (int) ($config['max_log_bytes'] ?? (5 * 1024 * 1024));
    if ($max > 0 && is_file($logFile) && filesize($logFile) > $max) {
        @unlink($logFile);
    }
    $line = implode("\t", [
        gmdate('c'),
        $path,
        substr((string) ($_SERVER['HTTP_USER_AGENT'] ?? ''), 0, 300),
        (string) ($_SERVER['REMOTE_ADDR'] ?? ''),
    ]) . "\n";
    @file_put_contents($logFile, $line, FILE_APPEND | LOCK_EX);
}

echo $gif;
