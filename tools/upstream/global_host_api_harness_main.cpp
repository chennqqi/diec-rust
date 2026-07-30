// Project-generated research harness for pinned Qt native script globals.
// It links and constructs the unmodified upstream DiE_ScriptEngine.

#include "die_scriptengine.h"

#include <QBuffer>
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#ifdef QT_SCRIPT_LIB
#include <QScriptValue>
#else
#include <QJSValue>
#endif
#include <QStringList>

#include <cstdio>

namespace {

constexpr const char *UPSTREAM_COMMIT =
    "74eaf505c250ab47e709024e9dc41657cd8f2254";
constexpr const char *DIE_SCRIPT_COMMIT =
    "5d82316c110abf0eb863b50bc679d330e05067b6";
constexpr const char *RULES_COMMIT =
    "c2c17dfa5ea4e078ba31eab55d87430c96622fb6";

QJsonObject evaluate(
    DiE_ScriptEngine *engine,
    const QString &source,
    const QString &fileName
)
{
#ifdef QT_SCRIPT_LIB
    engine->clearExceptions();
#endif
    XSCRIPTVALUE value = engine->evaluate(source, fileName);

    QJsonObject output;
    output.insert("source", source);
    output.insert("is_error", value.isError());
    output.insert("is_undefined", value.isUndefined());
    output.insert("is_null", value.isNull());
    output.insert("is_boolean", value.isBool());
    output.insert("is_number", value.isNumber());
    output.insert("is_string", value.isString());
    if (value.isBool()) {
        output.insert("boolean", value.toBool());
    }
    if (value.isNumber()) {
        output.insert("number", value.toNumber());
    }
    if (value.isString() || value.isError()) {
        output.insert("string", value.toString());
    }
    if (value.isError()) {
        output.insert("error_name", value.property("name").toString());
        output.insert(
            "error_message",
            value.property("message").toString()
        );
        output.insert(
            "error_line",
#ifdef QT_SCRIPT_LIB
            value.property("lineNumber").toInt32()
#else
            value.property("lineNumber").toInt()
#endif
        );
        QJsonArray backtrace;
#ifdef QT_SCRIPT_LIB
        for (const QString &line : engine->uncaughtExceptionBacktrace()) {
            backtrace.append(line);
        }
#else
        for (
            const QString &line :
            value.property("stack").toString().split('\n')
        ) {
            if (!line.isEmpty()) {
                backtrace.append(line);
            }
        }
#endif
        output.insert("backtrace", backtrace);
    }
    return output;
}

QJsonArray recordSnapshot(const QList<XScanEngine::SCANSTRUCT> &records)
{
    QJsonArray output;
    for (const XScanEngine::SCANSTRUCT &record : records) {
        output.append(
            QJsonObject{
                {"type", record.sType},
                {"name", record.sName},
                {"version", record.sVersion},
                {"info", record.sInfo},
                {"is_heuristic", record.bIsHeuristic},
                {"is_advanced_heuristic", record.bIsAHeuristic},
                {"priority", record.nPrio},
            }
        );
    }
    return output;
}

QJsonArray messageSnapshot(const QStringList &messages)
{
    QJsonArray output;
    for (const QString &message : messages) {
        output.append(message);
    }
    return output;
}

class EngineFixture {
public:
    explicit EngineFixture(bool firstWrapper = false)
        : bytes("ABC\0", 4),
          buffer(&bytes),
          options{},
          state(XBinary::createPdStruct())
    {
        buffer.open(QIODevice::ReadOnly);
        options.bIsFirstWrapperScan = firstWrapper;
        engine = new DiE_ScriptEngine(
            &signatures,
            &records,
            &buffer,
            XBinary::FT_BINARY,
            XBinary::FILEPART_HEADER,
            &options,
            &state
        );
        QObject::connect(
            engine,
            &XScriptEngine::infoMessage,
            [&] (const QString &message) {
                infoMessages.append(message);
            }
        );
        QObject::connect(
            engine,
            &XScriptEngine::errorMessage,
            [&] (const QString &message) {
                errorMessages.append(message);
            }
        );
    }

    ~EngineFixture()
    {
        delete engine;
    }

    QByteArray bytes;
    QBuffer buffer;
    XScanEngine::SCAN_OPTIONS options;
    XBinary::PDSTRUCT state;
    QList<XScanEngine::SIGNATURE_RECORD> signatures;
    QList<XScanEngine::SCANSTRUCT> records;
    QStringList infoMessages;
    QStringList errorMessages;
    DiE_ScriptEngine *engine;
};

QJsonObject step(
    EngineFixture *fixture,
    const QString &source,
    const QString &name
)
{
    return QJsonObject{
        {"evaluation", evaluate(fixture->engine, source, name)},
        {"records", recordSnapshot(fixture->records)},
        {"engine_is_stopped", fixture->engine->isStopped()},
    };
}

QJsonObject surfaceObservations()
{
    EngineFixture fixture;
    const QStringList names = {
        "includeScript",
        "_log",
        "_setResult",
        "_isResultPresent",
        "_getNumberOfResults",
        "_removeResult",
        "_isStop",
        "_encodingList",
        "_isConsoleMode",
        "_isLiteMode",
        "_isGuiMode",
        "_isLibraryMode",
        "_breakScan",
        "_getEngineVersion",
        "_getOS",
        "_getQtVersion",
    };
    QJsonObject methods;
    for (const QString &name : names) {
        methods.insert(
            name,
            QJsonObject{
                {
                    "type",
                    evaluate(
                        fixture.engine,
                        QString("typeof %1").arg(name),
                        QString("typeof-%1.js").arg(name)
                    )
                },
                {
                    "length",
                    evaluate(
                        fixture.engine,
                        QString(
                            "typeof %1 === 'function' ? %1.length : null"
                        ).arg(name),
                        QString("length-%1.js").arg(name)
                    )
                },
            }
        );
    }
    return QJsonObject{{"methods", methods}};
}

QJsonObject resultObservations()
{
    EngineFixture fixture;
    QJsonArray steps;
    steps.append(
        step(
            &fixture,
            "_setResult('compiler','Rust','1.0','first')",
            "result-add-first.js"
        )
    );
    steps.append(
        step(
            &fixture,
            "_setResult('COMPILER','rust','2.0','duplicate')",
            "result-add-duplicate.js"
        )
    );
    steps.append(
        step(
            &fixture,
            "_isResultPresent('compiler','RUST')",
            "result-present-case.js"
        )
    );
    steps.append(
        step(
            &fixture,
            "_getNumberOfResults('')",
            "result-count-wildcard.js"
        )
    );
    steps.append(
        step(
            &fixture,
            "_removeResult('compiler','Rust')",
            "result-remove-first.js"
        )
    );
    steps.append(
        step(
            &fixture,
            "_setResult('compiler','Rust','3.0','blocked')",
            "result-add-blocked.js"
        )
    );
    steps.append(
        step(
            &fixture,
            "_removeResult('compiler','')",
            "result-remove-empty-name.js"
        )
    );
    return QJsonObject{{"steps", steps}};
}

QJsonObject arrayRemovalObservations()
{
    EngineFixture fixture;
    evaluate(
        fixture.engine,
        "_setResult('protector','Enigma','','')",
        "array-remove-seed-enigma.js"
    );
    evaluate(
        fixture.engine,
        "_setResult('protector','Denuvo','','')",
        "array-remove-seed-denuvo.js"
    );
    QJsonArray before = recordSnapshot(fixture.records);
    QJsonObject removal = step(
        &fixture,
        "_removeResult('protector',['Enigma','Denuvo'])",
        "array-remove-call.js"
    );
    QJsonObject addCombined = step(
        &fixture,
        "_setResult('protector','Enigma,Denuvo','','blocked-combined')",
        "array-remove-block-combined.js"
    );
    return QJsonObject{
        {"before", before},
        {"removal", removal},
        {"add_combined", addCombined},
    };
}

QJsonObject missingArgumentObservations()
{
    EngineFixture fixture;
    QJsonObject setResult = step(
        &fixture,
        "_setResult()",
        "missing-set-result.js"
    );
    QJsonObject present = step(
        &fixture,
        "_isResultPresent()",
        "missing-is-present.js"
    );
    QJsonObject count = step(
        &fixture,
        "_getNumberOfResults()",
        "missing-count.js"
    );
    return QJsonObject{
        {"set_result", setResult},
        {"is_present", present},
        {"count", count},
    };
}

QJsonObject queryConversionObservations()
{
    EngineFixture fixture;
    evaluate(
        fixture.engine,
        "_setResult('compiler','Rust','','')",
        "query-conversion-seed-compiler.js"
    );
    evaluate(
        fixture.engine,
        "_setResult('compiler,linker','ArrayName','','')",
        "query-conversion-seed-array.js"
    );
    evaluate(
        fixture.engine,
        "_setResult('[object Object]','PlainObject','','')",
        "query-conversion-seed-plain-object.js"
    );
    evaluate(
        fixture.engine,
        "_setResult('custom-type','CustomObject','','')",
        "query-conversion-seed-custom-object.js"
    );
    for (const QString &type : {
             "NaN",
             "Infinity",
             "-Infinity",
             "0",
             "9007199254740992",
         }) {
        evaluate(
            fixture.engine,
            QString("_setResult('%1','Numeric','','')").arg(type),
            QString("query-conversion-seed-%1.js").arg(type)
        );
    }

    const QList<QPair<QString, QString>> probes = {
        {
            "undefined_count",
            "_getNumberOfResults(undefined)",
        },
        {
            "null_count",
            "_getNumberOfResults(null)",
        },
        {
            "array_single_present",
            "_isResultPresent(['compiler'],['Rust'])",
        },
        {
            "array_multiple_present",
            "_isResultPresent(['compiler','linker'],'ArrayName')",
        },
        {
            "array_count",
            "_getNumberOfResults(['compiler'])",
        },
        {
            "plain_object_count",
            "_getNumberOfResults({})",
        },
        {
            "custom_object_count",
            "_getNumberOfResults({"
            "toString:function(){return 'custom-type';}})",
        },
        {
            "throwing_object_count",
            "_getNumberOfResults({"
            "toString:function(){throw new Error('conversion-boom');}})",
        },
        {
            "nan_count",
            "_getNumberOfResults(NaN)",
        },
        {
            "positive_infinity_count",
            "_getNumberOfResults(Infinity)",
        },
        {
            "negative_infinity_count",
            "_getNumberOfResults(-Infinity)",
        },
        {
            "negative_zero_count",
            "_getNumberOfResults(-0)",
        },
        {
            "large_integer_count",
            "_getNumberOfResults(9007199254740992)",
        },
        {
            "invalid_utf16_count",
            "(function(){var s=String.fromCharCode(0xD800);"
            "_setResult(s,'Surrogate','','');"
            "return _getNumberOfResults(s);})()",
        },
        {
            "extra_present_arguments",
            "_isResultPresent('compiler','Rust','ignored')",
        },
        {
            "extra_count_arguments",
            "_getNumberOfResults('compiler','ignored')",
        },
    };
    QJsonObject evaluations;
    for (const auto &probe : probes) {
        evaluations.insert(
            probe.first,
            evaluate(
                fixture.engine,
                probe.second,
                QString("query-conversion-%1.js").arg(probe.first)
            )
        );
    }
    return QJsonObject{
        {"seed_record_count", 9},
        {"evaluations", evaluations},
        {"final_records", recordSnapshot(fixture.records)},
    };
}

QJsonObject stopObservations()
{
    EngineFixture fixture(true);
    QJsonObject compiler = step(
        &fixture,
        "_setResult('compiler','Example','','')",
        "first-wrapper-compiler.js"
    );
    QJsonObject protection = step(
        &fixture,
        "_setResult('protection','Example','','')",
        "first-wrapper-protection.js"
    );
    QJsonObject jsStopBefore = step(
        &fixture,
        "_isStop()",
        "first-wrapper-js-stop-before-break.js"
    );
    QJsonObject breakScan = step(
        &fixture,
        "_breakScan()",
        "first-wrapper-break.js"
    );
    QJsonObject jsStopAfter = step(
        &fixture,
        "_isStop()",
        "first-wrapper-js-stop-after-break.js"
    );
    return QJsonObject{
        {"compiler", compiler},
        {"protection", protection},
        {"js_stop_before_break", jsStopBefore},
        {"break_scan", breakScan},
        {"js_stop_after_break", jsStopAfter},
    };
}

QJsonObject includeObservations()
{
    EngineFixture fixture;
    XScanEngine::SIGNATURE_RECORD normalSignature = {};
    normalSignature.fileType = XBinary::FT_UNKNOWN;
    normalSignature.sName = "probe-include";
    normalSignature.sText =
        "var includedProbe = "
        "(typeof includedProbe === 'undefined' ? 1 : includedProbe + 1);";
    fixture.signatures.append(normalSignature);

    XScanEngine::SIGNATURE_RECORD parseErrorSignature = {};
    parseErrorSignature.fileType = XBinary::FT_UNKNOWN;
    parseErrorSignature.sName = "probe-include-parse-error";
    parseErrorSignature.sText =
        "var includeParseBefore = 1; function broken( {";
    fixture.signatures.append(parseErrorSignature);

    XScanEngine::SIGNATURE_RECORD runtimeErrorSignature = {};
    runtimeErrorSignature.fileType = XBinary::FT_UNKNOWN;
    runtimeErrorSignature.sName = "probe-include-runtime-error";
    runtimeErrorSignature.sText =
        "var includeRuntimeBefore = 1; "
        "throw new Error('include-runtime-boom'); "
        "var includeRuntimeAfter = 1;";
    fixture.signatures.append(runtimeErrorSignature);

    QJsonObject first = step(
        &fixture,
        "includeScript('PrObE-InClUdE')",
        "include-first.js"
    );
    QJsonObject valueAfterFirst = step(
        &fixture,
        "includedProbe",
        "include-value-first.js"
    );
    QJsonObject second = step(
        &fixture,
        "includeScript('probe-include')",
        "include-second.js"
    );
    QJsonObject valueAfterSecond = step(
        &fixture,
        "includedProbe",
        "include-value-second.js"
    );
    QJsonObject missing = step(
        &fixture,
        "includeScript('missing-include')",
        "include-missing.js"
    );
    QJsonArray errorsAfterMissing = messageSnapshot(fixture.errorMessages);
    QJsonObject parseError = step(
        &fixture,
        "includeScript('probe-include-parse-error')",
        "include-parse-error.js"
    );
    QJsonObject parseVisibility = step(
        &fixture,
        "typeof includeParseBefore",
        "include-parse-visibility.js"
    );
    QJsonArray errorsAfterParse = messageSnapshot(fixture.errorMessages);
    QJsonObject runtimeError = step(
        &fixture,
        "includeScript('probe-include-runtime-error')",
        "include-runtime-error.js"
    );
    QJsonObject runtimeBeforeVisibility = step(
        &fixture,
        "typeof includeRuntimeBefore",
        "include-runtime-before-visibility.js"
    );
    QJsonObject runtimeAfterVisibility = step(
        &fixture,
        "typeof includeRuntimeAfter",
        "include-runtime-after-visibility.js"
    );
    QJsonArray errorsAfterRuntime = messageSnapshot(fixture.errorMessages);
    return QJsonObject{
        {"first", first},
        {"value_after_first", valueAfterFirst},
        {"second", second},
        {"value_after_second", valueAfterSecond},
        {"missing", missing},
        {"errors_after_missing", errorsAfterMissing},
        {"parse_error", parseError},
        {"parse_visibility", parseVisibility},
        {"errors_after_parse", errorsAfterParse},
        {"runtime_error", runtimeError},
        {"runtime_before_visibility", runtimeBeforeVisibility},
        {"runtime_after_visibility", runtimeAfterVisibility},
        {"errors_after_runtime", errorsAfterRuntime},
    };
}

QJsonObject infoObservations()
{
    EngineFixture fixture;
    QString initialPdInfo = fixture.state.sInfoString;
    QJsonObject missing = step(
        &fixture,
        "_log()",
        "log-missing.js"
    );
    QString pdInfoAfterMissing = fixture.state.sInfoString;
    QJsonObject nullValue = step(
        &fixture,
        "_log(null)",
        "log-null.js"
    );
    QString pdInfoAfterNull = fixture.state.sInfoString;
    QJsonObject number = step(
        &fixture,
        "_log(42)",
        "log-number.js"
    );
    QString pdInfoAfterNumber = fixture.state.sInfoString;
    qint32 beforeEncoding = fixture.infoMessages.count();
    QJsonObject encoding = step(
        &fixture,
        "_encodingList()",
        "encoding-list.js"
    );
    QString pdInfoAfterEncoding = fixture.state.sInfoString;
    QStringList encodingMessages =
        fixture.infoMessages.mid(beforeEncoding);
    QByteArray encodingBytes;
    for (const QString &message : encodingMessages) {
        if (!encodingBytes.isEmpty()) {
            encodingBytes.append('\0');
        }
        encodingBytes.append(message.toUtf8());
    }
    QJsonArray logMessages;
    for (qint32 i = 0; i < beforeEncoding; i++) {
        logMessages.append(fixture.infoMessages.at(i));
    }
    return QJsonObject{
        {"missing", missing},
        {"null", nullValue},
        {"number", number},
        {"log_messages", logMessages},
        {"pd_info_initial", initialPdInfo},
        {"pd_info_after_missing", pdInfoAfterMissing},
        {"pd_info_after_null", pdInfoAfterNull},
        {"pd_info_after_number", pdInfoAfterNumber},
        {"pd_info_after_encoding", pdInfoAfterEncoding},
        {"encoding_call", encoding},
        {"encoding_message_count", encodingMessages.count()},
        {
            "encoding_messages_sha256",
            QString::fromLatin1(
                QCryptographicHash::hash(
                    encodingBytes,
                    QCryptographicHash::Sha256
                ).toHex()
            )
        },
        {
            "encoding_first",
            encodingMessages.isEmpty()
                ? QString()
                : encodingMessages.first()
        },
        {
            "encoding_last",
            encodingMessages.isEmpty()
                ? QString()
                : encodingMessages.last()
        },
    };
}

QJsonObject modeObservations()
{
    EngineFixture fixture;
    QJsonObject output;
    QCoreApplication::setApplicationName("die");
    output.insert(
        "die",
        QJsonObject{
            {
                "application_name",
                QCoreApplication::applicationName()
            },
            {
                "console",
                evaluate(
                    fixture.engine,
                    "_isConsoleMode()",
                    "mode-die-console.js"
                )
            },
            {
                "gui",
                evaluate(
                    fixture.engine,
                    "_isGuiMode()",
                    "mode-die-gui.js"
                )
            },
            {
                "lite",
                evaluate(
                    fixture.engine,
                    "_isLiteMode()",
                    "mode-die-lite.js"
                )
            },
            {
                "library",
                evaluate(
                    fixture.engine,
                    "_isLibraryMode()",
                    "mode-die-library.js"
                )
            },
        }
    );
    QCoreApplication::setApplicationName("diel");
    output.insert(
        "diel",
        QJsonObject{
            {
                "application_name",
                QCoreApplication::applicationName()
            },
            {
                "lite",
                evaluate(
                    fixture.engine,
                    "_isLiteMode()",
                    "mode-diel-lite.js"
                )
            },
        }
    );
    QCoreApplication::setApplicationName("");
    output.insert(
        "empty_requested",
        QJsonObject{
            {
                "application_name",
                QCoreApplication::applicationName()
            },
            {
                "library",
                evaluate(
                    fixture.engine,
                    "_isLibraryMode()",
                    "mode-empty-library.js"
                )
            },
        }
    );
    QCoreApplication::setApplicationName("die");
    output.insert(
        "engine_version",
        evaluate(
            fixture.engine,
            "_getEngineVersion()",
            "engine-version.js"
        )
    );
    output.insert(
        "os",
        evaluate(fixture.engine, "_getOS()", "os.js")
    );
#ifndef QT_SCRIPT_LIB
    output.insert(
        "qt_version",
        evaluate(
            fixture.engine,
            "_getQtVersion()",
            "qt-version.js"
        )
    );
#endif
    return output;
}

}  // namespace

int main(int argc, char *argv[])
{
    QCoreApplication application(argc, argv);
    if (argc != 1) {
        std::fprintf(stderr, "global HostApi harness takes no arguments\n");
        return 2;
    }
    QCoreApplication::setApplicationName("die");
    QCoreApplication::setApplicationVersion("9.9.9");

    QJsonObject output;
    output.insert("schema_version", 3);
    output.insert("upstream_commit", UPSTREAM_COMMIT);
    output.insert("die_script_commit", DIE_SCRIPT_COMMIT);
    output.insert("rules_commit", RULES_COMMIT);
    output.insert("qt_version", QT_VERSION_STR);
    output.insert("surface", surfaceObservations());
    output.insert("results", resultObservations());
    output.insert("array_removal", arrayRemovalObservations());
    output.insert("missing_arguments", missingArgumentObservations());
    output.insert("query_conversions", queryConversionObservations());
    output.insert("stop", stopObservations());
    output.insert("include", includeObservations());
    output.insert("info", infoObservations());
    output.insert("modes", modeObservations());

    QByteArray serialized =
        QJsonDocument(output).toJson(QJsonDocument::Compact);
    std::fwrite(
        serialized.constData(),
        1,
        static_cast<size_t>(serialized.size()),
        stdout
    );
    std::fputc('\n', stdout);
    return 0;
}
