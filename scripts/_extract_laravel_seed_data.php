<?php

/**
 * One-off mechanical extractor: pulls each Laravel seeder's private rows()
 * array (and BusSeeder's bus_bus_service pivot mapping) into JSON files
 * under app/db/seed_data/, without booting the Laravel framework.
 *
 * Seeder files only need `Illuminate\Database\Seeder` (base class, for the
 * `extends` clause to resolve) and, for BusSeeder's pivot insert,
 * `Illuminate\Support\Facades\DB` (to capture the insert() call). Both are
 * stubbed below so the seeder classes can be `require`d and reflected on
 * directly, no `composer`/`artisan` bootstrap required.
 *
 * Usage:
 *   php scripts/_extract_laravel_seed_data.php <laravel-seeders-dir> <output-dir>
 *
 * Re-run this whenever kingexpressbus-laravel's seed data changes before
 * final cutover; app/db/seed_data/*.json is the checked-in source of truth
 * afterwards.
 */

declare(strict_types=1);

if ($argc < 3) {
    fwrite(STDERR, "Usage: php _extract_laravel_seed_data.php <laravel-seeders-dir> <output-dir>\n");
    exit(1);
}

$seedersDir = rtrim($argv[1], '/\\');
$outputDir = rtrim($argv[2], '/\\');

if (!is_dir($seedersDir)) {
    fwrite(STDERR, "Seeders dir not found: {$seedersDir}\n");
    exit(1);
}

if (!is_dir($outputDir) && !mkdir($outputDir, 0777, true) && !is_dir($outputDir)) {
    fwrite(STDERR, "Could not create output dir: {$outputDir}\n");
    exit(1);
}

// --- Stubs so seeder files can be required standalone ----------------------

if (!class_exists('Illuminate\\Database\\Seeder')) {
    eval('namespace Illuminate\\Database; class Seeder {}');
}

if (!class_exists('Illuminate\\Support\\Facades\\DB')) {
    eval(<<<'PHP'
        namespace Illuminate\Support\Facades;

        class DB
        {
            public static array $captured = [];

            public static function table(string $name): DBTableCapture
            {
                return new DBTableCapture($name);
            }
        }

        class DBTableCapture
        {
            public function __construct(private string $table) {}

            public function insert(array $rows): void
            {
                DB::$captured[$this->table] = array_merge(
                    DB::$captured[$this->table] ?? [],
                    $rows,
                );
            }

            public function truncate(): void
            {
                // no-op: extraction never touches a real database
            }
        }
        PHP
    );
}

// --- Seeder class -> output table/file name (Laravel run order) -----------

$seederToTable = [
    'UserSeeder' => 'users',
    'WebProfileSeeder' => 'web_profiles',
    'ProvinceSeeder' => 'provinces',
    'DistrictTypeSeeder' => 'district_types',
    'BusServiceSeeder' => 'bus_services',
    'BusSeeder' => 'buses',
    'HolidaySurchargeSeeder' => 'holiday_surcharges',
    'DistrictSeeder' => 'districts',
    'StopSeeder' => 'stops',
    'RouteSeeder' => 'routes',
    'RouteStopSeeder' => 'route_stops',
    'TripSeeder' => 'trips',
    'HolidaySurchargeRouteSeeder' => 'holiday_surcharge_routes',
    'MenuSeeder' => 'menus',
];

$jsonFlags = JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES;

foreach ($seederToTable as $class => $table) {
    $file = $seedersDir . DIRECTORY_SEPARATOR . $class . '.php';
    if (!is_file($file)) {
        fwrite(STDERR, "Missing seeder file: {$file}\n");
        exit(1);
    }

    require_once $file;

    $fqcn = 'Database\\Seeders\\' . $class;
    $ref = new ReflectionClass($fqcn);
    $instance = $ref->newInstanceWithoutConstructor();

    $rowsMethod = $ref->getMethod('rows');
    $rowsMethod->setAccessible(true);
    $rows = $rowsMethod->invoke($instance);

    file_put_contents(
        $outputDir . DIRECTORY_SEPARATOR . $table . '.json',
        json_encode($rows, $jsonFlags) . "\n",
    );
    echo "Extracted {$table}: " . count($rows) . " rows\n";

    if ($class === 'BusSeeder') {
        $mappingMethod = $ref->getMethod('insertServiceMappings');
        $mappingMethod->setAccessible(true);
        $mappingMethod->invoke($instance);

        $pivotRows = \Illuminate\Support\Facades\DB::$captured['bus_bus_service'] ?? [];
        file_put_contents(
            $outputDir . DIRECTORY_SEPARATOR . 'bus_bus_service.json',
            json_encode($pivotRows, $jsonFlags) . "\n",
        );
        echo "Extracted bus_bus_service: " . count($pivotRows) . " rows\n";
    }
}

echo "Done.\n";
