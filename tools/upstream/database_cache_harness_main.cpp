// Project-generated research harness for pinned DIE engine cache behavior.
// It links the unmodified upstream engine and changes only cache reachability.

#include "die_script.h"

#include <QByteArray>
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QStandardPaths>
#include <QString>

#include <fcntl.h>
#include <sys/stat.h>

#include <cstdio>

namespace {

constexpr const char *UPSTREAM_COMMIT =
    "74eaf505c250ab47e709024e9dc41657cd8f2254";
constexpr const char *XSCANENGINE_COMMIT =
    "dfe4a419e4f491bb23688ba03c5a5bf39e34da83";
constexpr const char *WORK_ROOT = "/tmp/diec-database-cache-harness";
constexpr qint64 FIXED_MTIME_SECONDS = 1700000000;
constexpr qint64 FIXED_MTIME_NANOSECONDS = 123000000;

struct CacheSnapshot {
    bool exists = false;
    qint64 size = 0;
    QString sha256;
};

bool setTimes(
    const QString &path,
    qint64 seconds,
    qint64 nanoseconds,
    QString *error
)
{
    const QByteArray nativePath = QFile::encodeName(path);
    struct timespec times[2] = {};
    times[0].tv_sec = seconds;
    times[0].tv_nsec = nanoseconds;
    times[1] = times[0];
    if (::utimensat(
            AT_FDCWD,
            nativePath.constData(),
            times,
            0
        ) != 0) {
        *error = QString("utimensat failed: %1").arg(path);
        return false;
    }
    return true;
}

bool copyFixture(
    const QString &fixtureRoot,
    QString *databasePath,
    QString *rulePath,
    QString *error
)
{
    const QString workRoot = QString::fromLatin1(WORK_ROOT);
    QDir work(workRoot);
    if (work.exists() && !work.removeRecursively()) {
        *error = "cannot clear harness work root";
        return false;
    }

    *databasePath = workRoot + "/database";
    *rulePath = *databasePath + "/Binary/fixture.1.sg";
    if (!QDir().mkpath(*databasePath + "/Binary")) {
        *error = "cannot create harness database";
        return false;
    }

    const QString source =
        fixtureRoot + "/valid-main/Binary/fixture.1.sg";
    if (!QFile::copy(source, *rulePath)) {
        *error = "cannot copy fixture rule";
        return false;
    }
    return setTimes(
        *rulePath,
        FIXED_MTIME_SECONDS,
        FIXED_MTIME_NANOSECONDS,
        error
    );
}

QString cachePathForDatabase(const QString &databasePath)
{
    const QString cacheDir =
        QStandardPaths::writableLocation(
            QStandardPaths::AppDataLocation
        ) + QDir::separator() + "db_cache";
    const QByteArray hash = QCryptographicHash::hash(
        databasePath.toUtf8(),
        QCryptographicHash::Md5
    ).toHex();
    return cacheDir + QDir::separator() +
        QString::fromLatin1(hash) + ".cache";
}

CacheSnapshot cacheSnapshot(const QString &path)
{
    CacheSnapshot result;
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly)) {
        return result;
    }
    const QByteArray data = file.readAll();
    result.exists = true;
    result.size = data.size();
    result.sha256 = QString::fromLatin1(
        QCryptographicHash::hash(
            data,
            QCryptographicHash::Sha256
        ).toHex()
    );
    return result;
}

QJsonObject serializeCache(const CacheSnapshot &snapshot)
{
    QJsonObject result;
    result.insert("exists", snapshot.exists);
    result.insert("size", snapshot.size);
    result.insert("sha256", snapshot.sha256);
    return result;
}

qint32 binarySignatureCount(DiE_Script *engine)
{
    const QList<XScanEngine::SIGNATURE_STATE> states =
        engine->getSignatureStates();
    for (const XScanEngine::SIGNATURE_STATE &state : states) {
        if (state.fileType == XBinary::FT_BINARY) {
            return state.nNumberOfSignatures;
        }
    }
    return 0;
}

QJsonArray scanNames(
    DiE_Script *engine,
    XScanEngine::SCAN_OPTIONS *options,
    QJsonArray *errors
)
{
    QByteArray input("diec-rust deterministic corpus\n");
    XBinary::PDSTRUCT state = XBinary::createPdStruct();
    const XScanEngine::SCAN_RESULT result = engine->scanMemory(
        input.data(),
        input.size(),
        options,
        &state
    );
    QJsonArray names;
    for (const XScanEngine::SCANSTRUCT &record : result.listRecords) {
        names.append(record.sName);
    }
    for (const XScanEngine::ERROR_RECORD &record : result.listErrors) {
        QJsonObject item;
        item.insert("script", record.sScript);
        item.insert("message", record.sErrorString);
        errors->append(item);
    }
    return names;
}

QJsonObject observeLoad(
    const QString &id,
    const QString &databasePath,
    const QString &cachePath,
    bool stopBeforeLoad
)
{
    XScanEngine::SCAN_OPTIONS options = {};
    options.sMainDatabasePath = databasePath;
    options.bUseCache = true;
    options.bIsSort = true;
    options.bShowType = true;
    options.bShowVersion = true;
    options.bShowInfo = true;

    DiE_Script engine;
    XBinary::PDSTRUCT loadState = XBinary::createPdStruct();
    if (stopBeforeLoad) {
        XBinary::setPdStructStopped(&loadState);
    }
    const bool loaded = engine.loadDatabase(&options, &loadState);

    QJsonArray errors;
    QJsonObject result;
    result.insert("id", id);
    result.insert("loaded", loaded);
    result.insert("stop_before_load", stopBeforeLoad);
    result.insert(
        "load_pd_not_canceled",
        XBinary::isPdStructNotCanceled(&loadState)
    );
    result.insert(
        "binary_signature_count",
        binarySignatureCount(&engine)
    );
    result.insert("scan_names", scanNames(&engine, &options, &errors));
    result.insert("scan_errors", errors);
    result.insert("cache", serializeCache(cacheSnapshot(cachePath)));
    return result;
}

bool replaceRulePreservingStats(
    const QString &rulePath,
    QString *error
)
{
    QFile file(rulePath);
    if (!file.open(QIODevice::ReadWrite)) {
        *error = "cannot open rule for same-stat replacement";
        return false;
    }
    QByteArray data = file.readAll();
    const QByteArray before("Fixture");
    const QByteArray after("Changed");
    if (
        before.size() != after.size() ||
        !data.contains(before)
    ) {
        *error = "fixture replacement invariant failed";
        return false;
    }
    data.replace(before, after);
    if (!file.resize(0) || file.write(data) != data.size()) {
        *error = "cannot rewrite rule";
        return false;
    }
    file.close();
    return setTimes(
        rulePath,
        FIXED_MTIME_SECONDS,
        FIXED_MTIME_NANOSECONDS,
        error
    );
}

bool corruptMagic(const QString &cachePath, QString *error)
{
    QFile file(cachePath);
    if (!file.open(QIODevice::ReadWrite)) {
        *error = "cannot open cache for magic corruption";
        return false;
    }
    if (file.write(QByteArray(4, '\0')) != 4) {
        *error = "cannot corrupt cache magic";
        return false;
    }
    return true;
}

bool truncateCache(const QString &cachePath, QString *error)
{
    QFile file(cachePath);
    if (!file.open(QIODevice::ReadWrite)) {
        *error = "cannot open cache for truncation";
        return false;
    }
    const qint64 size = file.size();
    if (size < 2 || !file.resize(size / 2)) {
        *error = "cannot truncate cache";
        return false;
    }
    return true;
}

}  // namespace

int main(int argc, char *argv[])
{
    QCoreApplication application(argc, argv);
    QCoreApplication::setOrganizationName("NTInfo");
    QCoreApplication::setApplicationName("die");

    if (argc != 2) {
        std::fprintf(
            stderr,
            "usage: diec-database-cache-harness <fixture-root>\n"
        );
        return 2;
    }

    QString databasePath;
    QString rulePath;
    QString error;
    if (!copyFixture(
            QString::fromLocal8Bit(argv[1]),
            &databasePath,
            &rulePath,
            &error
        )) {
        std::fprintf(stderr, "%s\n", error.toUtf8().constData());
        return 1;
    }

    const QString cachePath = cachePathForDatabase(databasePath);
    const QFileInfo cacheInfo(cachePath);
    QDir cacheDirectory = cacheInfo.dir();
    if (
        cacheDirectory.exists() &&
        !cacheDirectory.removeRecursively()
    ) {
        std::fprintf(stderr, "cannot clear cache directory\n");
        return 1;
    }

    QJsonArray cases;
    cases.append(observeLoad(
        "initial_miss",
        databasePath,
        cachePath,
        false
    ));
    cases.append(observeLoad(
        "unchanged_hit",
        databasePath,
        cachePath,
        false
    ));

    if (!replaceRulePreservingStats(rulePath, &error)) {
        std::fprintf(stderr, "%s\n", error.toUtf8().constData());
        return 1;
    }
    cases.append(observeLoad(
        "same_stats_stale_hit",
        databasePath,
        cachePath,
        false
    ));

    if (!setTimes(
            rulePath,
            FIXED_MTIME_SECONDS + 2,
            FIXED_MTIME_NANOSECONDS,
            &error
        )) {
        std::fprintf(stderr, "%s\n", error.toUtf8().constData());
        return 1;
    }
    cases.append(observeLoad(
        "stats_changed_rebuild",
        databasePath,
        cachePath,
        false
    ));

    if (!corruptMagic(cachePath, &error)) {
        std::fprintf(stderr, "%s\n", error.toUtf8().constData());
        return 1;
    }
    cases.append(observeLoad(
        "bad_magic_fallback",
        databasePath,
        cachePath,
        false
    ));

    if (!truncateCache(cachePath, &error)) {
        std::fprintf(stderr, "%s\n", error.toUtf8().constData());
        return 1;
    }
    cases.append(observeLoad(
        "truncated_cache_fallback",
        databasePath,
        cachePath,
        false
    ));

    cases.append(observeLoad(
        "canceled_cache_hit",
        databasePath,
        cachePath,
        true
    ));

    if (!QFile::remove(cachePath)) {
        std::fprintf(stderr, "cannot remove cache before canceled miss\n");
        return 1;
    }
    cases.append(observeLoad(
        "canceled_cache_miss",
        databasePath,
        cachePath,
        true
    ));
    cases.append(observeLoad(
        "poisoned_empty_cache_hit",
        databasePath,
        cachePath,
        false
    ));

    QJsonObject output;
    output.insert("schema_version", 1);
    output.insert("upstream_commit", UPSTREAM_COMMIT);
    output.insert("xscanengine_commit", XSCANENGINE_COMMIT);
    output.insert("database_path", databasePath);
    output.insert("rule_path", rulePath);
    output.insert("cache_path", cachePath);
    output.insert("fixed_mtime_seconds", FIXED_MTIME_SECONDS);
    output.insert(
        "fixed_mtime_nanoseconds",
        FIXED_MTIME_NANOSECONDS
    );
    output.insert("cases", cases);

    const QByteArray serialized =
        QJsonDocument(output).toJson(QJsonDocument::Indented);
    if (
        std::fwrite(
            serialized.constData(),
            1,
            static_cast<size_t>(serialized.size()),
            stdout
        ) != static_cast<size_t>(serialized.size())
    ) {
        return 1;
    }
    return 0;
}
