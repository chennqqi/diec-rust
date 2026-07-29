// Windows adapter entry point for the shared 19-case database-cache harness.
// The compatibility include path supplies Win32 implementations of the
// POSIX-only file-time, permission, and identity calls used by the harness.

#define main diecSharedDatabaseCacheHarnessMain
#include "database_cache_harness_main.cpp"
#undef main

int main(int argc, char *argv[])
{
    QStandardPaths::setTestModeEnabled(true);
    return diecSharedDatabaseCacheHarnessMain(argc, argv);
}
