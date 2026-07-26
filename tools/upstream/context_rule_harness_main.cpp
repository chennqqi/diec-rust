// Project-generated research harness for pinned Binary context rule behavior.
// It links the unmodified upstream Binary_Script implementation and executes
// three byte-identical fixed rules with QScriptEngine.

#include "binary_script.h"
#include "xbinary.h"

#include <QBuffer>
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QScriptEngine>
#include <QScriptValue>
#include <QString>

#include <cstdio>

namespace {

constexpr const char *UPSTREAM_COMMIT =
    "74eaf505c250ab47e709024e9dc41657cd8f2254";
constexpr const char *XSCANENGINE_COMMIT =
    "dfe4a419e4f491bb23688ba03c5a5bf39e34da83";
constexpr const char *RULES_COMMIT =
    "c2c17dfa5ea4e078ba31eab55d87430c96622fb6";

constexpr const char *RESOURCE_RULE_PATH =
    "/opt/die-source/Detect-It-Easy/db/Binary/win_resources.1.sg";
constexpr const char *RESOURCE_RULE_SHA256 =
    "2fdad41d666d32467cabe83dae7d16625ade5935e3061c58dfefeb1fb7b99db7";
constexpr const char *DEBUG_RULE_PATH =
    "/opt/die-source/Detect-It-Easy/db/Binary/"
    "debug_data_debugData.1.sg";
constexpr const char *DEBUG_RULE_SHA256 =
    "381b6259b239f2633b92fbd84fd0d99b972751e20cab12b6e09139a260f1f47d";
constexpr const char *DESKTOP_RULE_PATH =
    "/opt/die-source/Detect-It-Easy/db/Binary/format_DESKTOP.1.sg";
constexpr const char *DESKTOP_RULE_SHA256 =
    "9318de29fa4b3ea3c36f0fb286dc70fd77020cde092e1cf078aa57dc21562ff3";

constexpr const char *RESULT_SHIM = R"JS(
var __detections = [];
var bDetected, sType, sName, sVersion, sOptions, sLang, sLangVersion;

function meta(type, name, version, options, lang, langVersion) {
    sType = type;
    sName = name ? name : String();
    sVersion = version ? version : String();
    sOptions = options ? options : String();
    sLang = lang ? lang : String();
    sLangVersion = langVersion ? langVersion : String();
    bDetected = false;
}

function _setResult(type, name, version, options) {
    __detections.push([
        String(type),
        String(name),
        String(version),
        String(options)
    ]);
}

function _setLang() {}
function _error(message) { throw new Error(String(message)); }

function result() {
    if (bDetected) {
        sVersion = sVersion ? sVersion : String();
        sOptions = sOptions ? sOptions : String();
        if (!sName) _error("No input detection name.");
        _setResult(sType, sName, sVersion, sOptions);
    }
    sName = sVersion = sOptions = sLang = sLangVersion = "";
    var value = bDetected;
    bDetected = false;
    return value;
}
)JS";

struct RuleSource {
    QString path;
    QByteArray sha256;
    QByteArray bytes;
};

struct CaseSpec {
    const char *id;
    const char *ruleKey;
    const char *dataHex;
    XBinary::FILEPART filePart;
    const char *filePartName;
    const char *scanId;
    const char *fileName;
};

bool loadRule(
    const QString &path,
    const QByteArray &expectedSha256,
    RuleSource *output,
    QString *error
)
{
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly)) {
        *error = QString("cannot open fixed rule: %1").arg(path);
        return false;
    }
    QByteArray bytes = file.readAll();
    QByteArray actualSha256 =
        QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex();
    if (actualSha256 != expectedSha256) {
        *error = QString("fixed rule hash mismatch: %1").arg(path);
        return false;
    }
    output->path = path;
    output->sha256 = actualSha256;
    output->bytes = bytes;
    return true;
}

QJsonObject scriptError(
    const QString &stage,
    const QScriptValue &value,
    QScriptEngine *engine
)
{
    QJsonArray backtrace;
    for (const QString &line : engine->uncaughtExceptionBacktrace()) {
        backtrace.append(line);
    }
    QJsonObject output;
    output.insert("stage", stage);
    output.insert("name", value.property("name").toString());
    output.insert("message", value.property("message").toString());
    output.insert("line", value.property("lineNumber").toInt32());
    output.insert("backtrace", backtrace);
    return output;
}

QJsonObject runCase(
    const CaseSpec &spec,
    const RuleSource &rule,
    QString *error
)
{
    QByteArray data = QByteArray::fromHex(spec.dataHex);
    QBuffer buffer(&data);
    buffer.setProperty("FileName", QString::fromLatin1(spec.fileName));
    if (!buffer.open(QIODevice::ReadOnly)) {
        *error = QString("cannot open case buffer: %1").arg(spec.id);
        return {};
    }

    XBinary binary(&buffer);
    Binary_Script::OPTIONS options = {};
    options.sScanID = QString::fromLatin1(spec.scanId);
    XBinary::PDSTRUCT state = XBinary::createPdStruct();
    Binary_Script script(&binary, spec.filePart, options, &state);
    QScriptEngine engine;
    QScriptValue object = engine.newQObject(&script);
    engine.globalObject().setProperty("Binary", object);
    engine.globalObject().setProperty("X", object);

    QJsonObject output;
    output.insert("id", QString::fromLatin1(spec.id));
    output.insert("rule_path", rule.path);
    output.insert("rule_sha256", QString::fromLatin1(rule.sha256));
    output.insert("data_hex", QString::fromLatin1(spec.dataHex));
    output.insert("file_part", QString::fromLatin1(spec.filePartName));
    output.insert("scan_id", QString::fromLatin1(spec.scanId));
    output.insert("file_name", QString::fromLatin1(spec.fileName));

    QScriptValue shimValue =
        engine.evaluate(QString::fromUtf8(RESULT_SHIM), "result-shim.js");
    if (shimValue.isError()) {
        output.insert("error", scriptError("shim", shimValue, &engine));
        *error = QString("result shim failed: %1").arg(spec.id);
        return output;
    }

    QScriptValue ruleValue =
        engine.evaluate(QString::fromUtf8(rule.bytes), rule.path);
    if (ruleValue.isError()) {
        output.insert("error", scriptError("rule", ruleValue, &engine));
        *error = QString("fixed rule evaluation failed: %1").arg(spec.id);
        return output;
    }

    QScriptValue detectValue = engine.evaluate(
        "typeof detect === 'function' ? detect() : undefined",
        "invoke-detect.js"
    );
    if (detectValue.isError()) {
        output.insert(
            "error",
            scriptError("detect", detectValue, &engine)
        );
        *error = QString("fixed rule detect failed: %1").arg(spec.id);
        return output;
    }

    QScriptValue detectionsValue =
        engine.evaluate("JSON.stringify(__detections)", "detections.js");
    QJsonParseError parseError;
    QJsonDocument detections = QJsonDocument::fromJson(
        detectionsValue.toString().toUtf8(),
        &parseError
    );
    if (
        detectionsValue.isError() ||
        parseError.error != QJsonParseError::NoError ||
        !detections.isArray()
    ) {
        *error = QString("cannot serialize detections: %1").arg(spec.id);
        return output;
    }

    output.insert("detect_is_boolean", detectValue.isBool());
    output.insert("detect_result", detectValue.toBool());
    output.insert("detections", detections.array());
    output.insert(
        "binary_script_error",
        XBinary::getPdStructErrorString(&state)
    );
    return output;
}

}  // namespace

int main(int argc, char *argv[])
{
    QCoreApplication application(argc, argv);

    RuleSource resourceRule;
    RuleSource debugRule;
    RuleSource desktopRule;
    QString error;
    if (
        !loadRule(
            QString::fromLatin1(RESOURCE_RULE_PATH),
            QByteArray(RESOURCE_RULE_SHA256),
            &resourceRule,
            &error
        ) ||
        !loadRule(
            QString::fromLatin1(DEBUG_RULE_PATH),
            QByteArray(DEBUG_RULE_SHA256),
            &debugRule,
            &error
        ) ||
        !loadRule(
            QString::fromLatin1(DESKTOP_RULE_PATH),
            QByteArray(DESKTOP_RULE_SHA256),
            &desktopRule,
            &error
        )
    ) {
        std::fprintf(stderr, "%s\n", error.toUtf8().constData());
        return 1;
    }

    const CaseSpec cases[] = {
        {
            "resource_manifest",
            "resource",
            "00",
            XBinary::FILEPART_RESOURCE,
            "resource",
            "24",
            "resource.bin",
        },
        {
            "resource_unknown_id",
            "resource",
            "00",
            XBinary::FILEPART_RESOURCE,
            "resource",
            "999",
            "resource.bin",
        },
        {
            "resource_header_gate",
            "resource",
            "00",
            XBinary::FILEPART_HEADER,
            "header",
            "24",
            "resource.bin",
        },
        {
            "debug_rsds",
            "debug",
            "52534453",
            XBinary::FILEPART_DEBUGDATA,
            "debugdata",
            "",
            "debug.bin",
        },
        {
            "debug_header_gate",
            "debug",
            "52534453",
            XBinary::FILEPART_HEADER,
            "header",
            "",
            "debug.bin",
        },
        {
            "desktop_entry",
            "desktop",
            "5b4465736b746f7020456e7472795d0a",
            XBinary::FILEPART_HEADER,
            "header",
            "",
            "sample.desktop",
        },
        {
            "desktop_missing_marker",
            "desktop",
            "68656c6c6f0a",
            XBinary::FILEPART_HEADER,
            "header",
            "",
            "sample.desktop",
        },
        {
            "desktop_binary_gate",
            "desktop",
            "00010203",
            XBinary::FILEPART_HEADER,
            "header",
            "",
            "sample.desktop",
        },
    };

    QJsonArray outputs;
    for (const CaseSpec &spec : cases) {
        const RuleSource *rule = nullptr;
        QString ruleKey = QString::fromLatin1(spec.ruleKey);
        if (ruleKey == "resource") {
            rule = &resourceRule;
        } else if (ruleKey == "debug") {
            rule = &debugRule;
        } else if (ruleKey == "desktop") {
            rule = &desktopRule;
        } else {
            std::fprintf(stderr, "unknown rule key\n");
            return 1;
        }
        QJsonObject output = runCase(spec, *rule, &error);
        outputs.append(output);
        if (!error.isEmpty()) {
            std::fprintf(stderr, "%s\n", error.toUtf8().constData());
            return 1;
        }
    }

    QJsonObject root;
    root.insert("schema_version", 1);
    root.insert("upstream_commit", UPSTREAM_COMMIT);
    root.insert("xscanengine_commit", XSCANENGINE_COMMIT);
    root.insert("rules_commit", RULES_COMMIT);
    root.insert("qt_version", qVersion());
    root.insert("engine", "QScriptEngine");
    root.insert("case_count", outputs.size());
    root.insert("cases", outputs);
    QByteArray json = QJsonDocument(root).toJson(QJsonDocument::Indented);
    std::fwrite(json.constData(), 1, static_cast<size_t>(json.size()), stdout);
    return 0;
}
