// macOS adapter for the shared 19-case database-cache research harness.
// Test mode plus a collector-controlled HOME isolates QStandardPaths output
// from the ordinary Detect It Easy application-data namespace.

#include <QStandardPaths>

#define main diecSharedDatabaseCacheHarnessMain
#include "database_cache_harness_main.cpp"
#undef main

int main(int argc, char *argv[])
{
    QStandardPaths::setTestModeEnabled(true);
    return diecSharedDatabaseCacheHarnessMain(argc, argv);
}
