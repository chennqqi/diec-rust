// Project-generated research harness for pinned DIE engine-only contracts.
// It links the unmodified upstream engine and changes only option reachability.

#include "die_script.h"

#include <QBuffer>
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QString>

#include <cstdio>

namespace {

constexpr const char *UPSTREAM_COMMIT =
    "74eaf505c250ab47e709024e9dc41657cd8f2254";
constexpr const char *XSCANENGINE_COMMIT =
    "dfe4a419e4f491bb23688ba03c5a5bf39e34da83";
constexpr const char *DIE_SCRIPT_COMMIT =
    "5d82316c110abf0eb863b50bc679d330e05067b6";
constexpr const char *INPUT_SHA256 =
    "b9e88c21a74e1be0f85e85465c3f6bb831a55ef1d626af3fa11164e5f353ac60";

enum class ScanMethod {
    File,
    Memory,
    Device,
    Subdevice,
};

enum class CallbackMode {
    None,
    Continue,
    StopFirst,
};

struct CaseSpec {
    const char *id;
    const char *database;
    const char *signatureName;
    bool deep;
    bool sort;
    CallbackMode callbackMode;
    bool preStopped;
    ScanMethod method;
};

struct CallbackState {
    CallbackMode mode = CallbackMode::None;
    QJsonArray events;
};

bool scanCallback(
    const QString &currentSignature,
    qint32 numberOfSignatures,
    qint32 currentIndex,
    void *userData
)
{
    CallbackState *state = static_cast<CallbackState *>(userData);
    QJsonObject event;
    event.insert("signature", currentSignature);
    event.insert("number_of_signatures", numberOfSignatures);
    event.insert("current_index", currentIndex);
    state->events.append(event);
    return !(
        state->mode == CallbackMode::StopFirst &&
        state->events.size() == 1
    );
}

QString layerPath(
    const QString &fixtureRoot,
    const QString &database,
    const QString &layer
)
{
    if (database == "orchestration") {
        return fixtureRoot + "/" + layer;
    }
    return fixtureRoot + "/" + database + "-" + layer;
}

QJsonObject serializeRecord(const XScanEngine::SCANSTRUCT &record)
{
    QJsonObject output;
    output.insert("type", record.sType);
    output.insert("name", record.sName);
    output.insert("version", record.sVersion);
    output.insert("info", record.sInfo);
    output.insert("priority", record.nPrio);
    output.insert("unknown", record.bIsUnknown);
    output.insert("heuristic", record.bIsHeuristic);
    output.insert("aggressive_heuristic", record.bIsAHeuristic);
    output.insert("signature", record.varInfo);
    output.insert("signature_file", record.varInfo2);
    return output;
}

QJsonArray serializeRecords(
    const QList<XScanEngine::SCANSTRUCT> &records
)
{
    QJsonArray output;
    for (const XScanEngine::SCANSTRUCT &record : records) {
        output.append(serializeRecord(record));
    }
    return output;
}

QJsonArray serializeErrors(
    const QList<XScanEngine::ERROR_RECORD> &errors
)
{
    QJsonArray output;
    for (const XScanEngine::ERROR_RECORD &error : errors) {
        QJsonObject item;
        item.insert("script", error.sScript);
        item.insert("message", error.sErrorString);
        output.append(item);
    }
    return output;
}

const char *methodName(ScanMethod method)
{
    switch (method) {
        case ScanMethod::File:
            return "scanFile";
        case ScanMethod::Memory:
            return "scanMemory";
        case ScanMethod::Device:
            return "scanDevice";
        case ScanMethod::Subdevice:
            return "scanSubdevice";
    }
    return "unknown";
}

XScanEngine::SCAN_RESULT runScan(
    DiE_Script *engine,
    const CaseSpec &spec,
    const QString &inputPath,
    QByteArray *input,
    XScanEngine::SCAN_OPTIONS *options,
    XBinary::PDSTRUCT *state,
    QString *error
)
{
    if (spec.method == ScanMethod::File) {
        return engine->scanFile(inputPath, options, state);
    }
    if (spec.method == ScanMethod::Memory) {
        return engine->scanMemory(
            input->data(),
            input->size(),
            options,
            state
        );
    }
    if (spec.method == ScanMethod::Device) {
        QBuffer buffer(input);
        buffer.setProperty("FileName", "probe.bin");
        if (!buffer.open(QIODevice::ReadOnly)) {
            *error = "cannot open scanDevice buffer";
            return {};
        }
        return engine->scanDevice(&buffer, options, state);
    }

    QByteArray wrapped("pre", 3);
    wrapped.append(*input);
    wrapped.append("post", 4);
    QBuffer buffer(&wrapped);
    buffer.setProperty("FileName", "wrapped.bin");
    if (!buffer.open(QIODevice::ReadOnly)) {
        *error = "cannot open scanSubdevice buffer";
        return {};
    }
    return engine->scanSubdevice(
        &buffer,
        3,
        input->size(),
        options,
        state
    );
}

QJsonObject runCase(
    const CaseSpec &spec,
    const QString &fixtureRoot,
    const QString &inputPath,
    QByteArray *input,
    QString *error
)
{
    XScanEngine::SCAN_OPTIONS options = {};
    options.bUseCustomDatabase = true;
    options.bUseExtraDatabase = true;
    options.bShowType = true;
    options.bShowInfo = true;
    options.bShowVersion = true;
    options.bIsDeepScan = spec.deep;
    options.bIsSort = spec.sort;
    options.sSignatureName = QString::fromLatin1(spec.signatureName);
    const QString database = QString::fromLatin1(spec.database);
    options.sMainDatabasePath = layerPath(
        fixtureRoot,
        database,
        "main"
    );
    options.sExtraDatabasePath = layerPath(
        fixtureRoot,
        database,
        "extra"
    );
    options.sCustomDatabasePath = layerPath(
        fixtureRoot,
        database,
        "custom"
    );

    CallbackState callbackState;
    callbackState.mode = spec.callbackMode;
    if (spec.callbackMode != CallbackMode::None) {
        options.scanEngineCallback = scanCallback;
        options.pUserData = &callbackState;
    }

    DiE_Script engine;
    XBinary::PDSTRUCT loadState = XBinary::createPdStruct();
    const bool loaded = engine.loadDatabase(&options, &loadState);
    if (!loaded) {
        *error = QString("cannot load fixture database: %1").arg(
            spec.id
        );
        return {};
    }

    XBinary::PDSTRUCT scanState = XBinary::createPdStruct();
    if (spec.preStopped) {
        XBinary::setPdStructStopped(&scanState);
    }
    XScanEngine::SCAN_RESULT result = runScan(
        &engine,
        spec,
        inputPath,
        input,
        &options,
        &scanState,
        error
    );
    if (!error->isEmpty()) {
        return {};
    }

    QJsonObject output;
    output.insert("id", QString::fromLatin1(spec.id));
    output.insert("database", database);
    output.insert("method", QString::fromLatin1(methodName(spec.method)));
    output.insert(
        "signature_name",
        QString::fromLatin1(spec.signatureName)
    );
    output.insert("deep", spec.deep);
    output.insert("sort", spec.sort);
    output.insert("pre_stopped", spec.preStopped);
    output.insert("database_loaded", loaded);
    output.insert("records", serializeRecords(result.listRecords));
    output.insert("errors", serializeErrors(result.listErrors));
    output.insert("callback_events", callbackState.events);
    output.insert(
        "pd_stopped",
        XBinary::isPdStructStopped(&scanState)
    );
    output.insert(
        "pd_success",
        XBinary::isPdStructSuccess(&scanState)
    );
    output.insert(
        "pd_finished",
        XBinary::isPdStructFinished(&scanState)
    );
    output.insert(
        "pd_not_canceled",
        XBinary::isPdStructNotCanceled(&scanState)
    );
    output.insert(
        "pd_n_finished",
        static_cast<qint64>(scanState.nFinished)
    );
    output.insert("result_size", result.nSize);
    return output;
}

}  // namespace

int main(int argc, char *argv[])
{
    QCoreApplication application(argc, argv);
    if (argc != 2) {
        std::fprintf(
            stderr,
            "usage: diec-engine-contract-harness <fixture-root>\n"
        );
        return 2;
    }

    const QString fixtureRoot = QString::fromLocal8Bit(argv[1]);
    const QString inputPath = fixtureRoot + "/input/probe.bin";
    QFile inputFile(inputPath);
    if (!inputFile.open(QIODevice::ReadOnly)) {
        std::fprintf(stderr, "cannot open fixture input\n");
        return 1;
    }
    QByteArray input = inputFile.readAll();
    const QByteArray inputHash = QCryptographicHash::hash(
        input,
        QCryptographicHash::Sha256
    ).toHex();
    if (inputHash != QByteArray(INPUT_SHA256)) {
        std::fprintf(stderr, "fixture input hash mismatch\n");
        return 1;
    }

    const CaseSpec cases[] = {
        {
            "filter_all",
            "priority",
            "",
            false,
            false,
            CallbackMode::None,
            false,
            ScanMethod::File,
        },
        {
            "filter_exact_extra",
            "orchestration",
            "a_extra.0.sg",
            false,
            false,
            CallbackMode::None,
            false,
            ScanMethod::File,
        },
        {
            "filter_missing",
            "priority",
            "missing.0.sg",
            false,
            false,
            CallbackMode::None,
            false,
            ScanMethod::File,
        },
        {
            "filter_case_mismatch",
            "priority",
            "Z_PRIORITY.1.SG",
            false,
            false,
            CallbackMode::None,
            false,
            ScanMethod::File,
        },
        {
            "filter_deep_disabled",
            "orchestration",
            "DS.deep.2.sg",
            false,
            false,
            CallbackMode::None,
            false,
            ScanMethod::File,
        },
        {
            "filter_deep_enabled",
            "orchestration",
            "DS.deep.2.sg",
            true,
            false,
            CallbackMode::None,
            false,
            ScanMethod::File,
        },
        {
            "sort_disabled",
            "sort",
            "",
            false,
            false,
            CallbackMode::None,
            false,
            ScanMethod::File,
        },
        {
            "sort_enabled",
            "sort",
            "",
            false,
            true,
            CallbackMode::None,
            false,
            ScanMethod::File,
        },
        {
            "callback_continue",
            "priority",
            "",
            false,
            false,
            CallbackMode::Continue,
            false,
            ScanMethod::File,
        },
        {
            "callback_stop_first",
            "priority",
            "",
            false,
            false,
            CallbackMode::StopFirst,
            false,
            ScanMethod::File,
        },
        {
            "break_scan",
            "break",
            "",
            false,
            false,
            CallbackMode::None,
            false,
            ScanMethod::File,
        },
        {
            "pre_stopped",
            "priority",
            "",
            false,
            false,
            CallbackMode::None,
            true,
            ScanMethod::File,
        },
        {
            "entry_file",
            "priority",
            "z_priority.1.sg",
            false,
            false,
            CallbackMode::None,
            false,
            ScanMethod::File,
        },
        {
            "entry_memory",
            "priority",
            "z_priority.1.sg",
            false,
            false,
            CallbackMode::None,
            false,
            ScanMethod::Memory,
        },
        {
            "entry_device",
            "priority",
            "z_priority.1.sg",
            false,
            false,
            CallbackMode::None,
            false,
            ScanMethod::Device,
        },
        {
            "entry_subdevice",
            "priority",
            "z_priority.1.sg",
            false,
            false,
            CallbackMode::None,
            false,
            ScanMethod::Subdevice,
        },
    };

    QJsonArray outputs;
    QString error;
    for (const CaseSpec &spec : cases) {
        QJsonObject output = runCase(
            spec,
            fixtureRoot,
            inputPath,
            &input,
            &error
        );
        if (!error.isEmpty()) {
            std::fprintf(stderr, "%s\n", error.toUtf8().constData());
            return 1;
        }
        outputs.append(output);
    }

    QJsonObject root;
    root.insert("schema_version", 1);
    root.insert("upstream_commit", UPSTREAM_COMMIT);
    root.insert("xscanengine_commit", XSCANENGINE_COMMIT);
    root.insert("die_script_commit", DIE_SCRIPT_COMMIT);
    root.insert("qt_version", qVersion());
    root.insert("case_count", outputs.size());
    root.insert("input_sha256", QString::fromLatin1(inputHash));
    root.insert("cases", outputs);
    const QByteArray json = QJsonDocument(root).toJson(
        QJsonDocument::Indented
    );
    std::fwrite(
        json.constData(),
        1,
        static_cast<size_t>(json.size()),
        stdout
    );
    return 0;
}
