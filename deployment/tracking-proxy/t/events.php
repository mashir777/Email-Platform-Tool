<?php
/**
 * Returns recently logged opens as JSON so the app can mark recipients "opened".
 * Protected by shared_secret (config.php). The app calls:
 *   https://YOURDOMAIN.com/t/events.php?key={shared_secret}&limit=2000
 */
declare(strict_types=1);

$config = require __DIR__ . '/config.php';

header('Content-Type: application/json');
header('Cache-Control: no-store, no-cache, must-revalidate, max-age=0');

$secret = (string) ($config['shared_secret'] ?? '');
$key = isset($_GET['key']) ? (string) $_GET['key'] : '';
if ($secret === '' || !hash_equals($secret, $key)) {
    http_response_code(403);
    echo json_encode(['error' => 'forbidden']);
    exit;
}

$limit = isset($_GET['limit']) ? (int) $_GET['limit'] : 2000;
if ($limit < 1) {
    $limit = 1;
}
if ($limit > 5000) {
    $limit = 5000;
}

$logFile = (string) ($config['log_file'] ?? (__DIR__ . '/opens.log'));
$events = [];
if (is_file($logFile)) {
    $lines = file($logFile, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
    if ($lines !== false) {
        $lines = array_slice($lines, -$limit);
        foreach ($lines as $line) {
            $parts = explode("\t", $line);
            $events[] = [
                'ts' => $parts[0] ?? '',
                'path' => $parts[1] ?? '',
                'ua' => $parts[2] ?? '',
                'ip' => $parts[3] ?? '',
            ];
        }
    }
}

echo json_encode(['events' => $events]);
